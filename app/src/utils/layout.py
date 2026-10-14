"""Deterministic top-down layout of Reward Machine graphs, shared by the app, SVG and HTML export.

The flow runs from the initial state down to the final one:

1. Rank: the longest path from the initial state over forward edges (self-loops are ignored and
   edges back to a state on the current depth-first path are dropped), so every forward edge
   points down at least one rank. The final state is moved to the bottom rank.
2. Order: barycenter sweeps and adjacent swaps cut crossings. An edge that skips ranks holds a
   placeholder slot in every rank it passes, so no state is ordered into its way.
3. Place: the states of a rank sit on an even grid in that order. Each well gets its own lane
   to the left of the main flow, the side away from the self-loops, at the mean height of its
   neighbours.
4. Settle: states, wells included, then slide until none is near an edge it is not part of,
   no label chip lies on a state, and fewer edges cross. A graph too dense for every state
   to clear every straight edge is laid out again with the ranks further apart, which makes
   its edges steeper and leaves more room beside them.
"""

from collections import defaultdict
from dataclasses import dataclass
from itertools import pairwise

from src.config import GraphStyle

from .settle import TOLERANCE, place_wells, preferred_heights, settle

_GRAPH = GraphStyle()

_STRETCHES = (1.0, 1.3, 1.7, 2.2, 3.0)  # rank spacing, in units of ``layer_gap``
_ORDER_SWEEPS = 12

# A node of the layered graph: a state id, or (source, target, rank) for an edge's placeholder.
Node = str | tuple[str, str, int]


@dataclass(frozen=True)
class _Graph:
    states: list[str]
    initial: str
    final: str | None
    wells: frozenset[str]
    edges: list[tuple[str, str]]
    chips: dict[tuple[str, str], tuple[float, float]]  # an edge label's half width and lift

    @property
    def main(self) -> list[str]:
        return [state for state in self.states if state not in self.wells]


def element_positions(elements: list[dict]) -> dict[str, tuple[float, float]]:
    """Return the positions stored on the state elements, or lay the states out if one is missing."""
    nodes = [element for element in elements if "source" not in element["data"]]
    if nodes and all("position" in node for node in nodes):
        return {
            node["data"]["id"]: (node["position"]["x"], node["position"]["y"]) for node in nodes
        }
    return reward_machine_positions(elements)


def reward_machine_positions(elements: list[dict]) -> dict[str, tuple[float, float]]:
    """Place graph states in one top-down layered layout for the app, SVG and HTML export."""
    graph = _read_graph(elements)
    forward = _forward_edges(graph)
    ranks = _ranks(graph, forward)
    layers, up, down = _layers(graph, forward, ranks)
    _order_layers(layers, up, down, _well_neighbours(graph), graph.states)
    positions = _arrange(graph, layers, ranks)

    left = min(x for x, _ in positions.values())
    top = min(y for _, y in positions.values())
    return {state: (round(x - left), round(y - top)) for state, (x, y) in positions.items()}


def _arrange(
    graph: _Graph, layers: list[list[Node]], ranks: dict[str, int]
) -> dict[str, tuple[float, float]]:
    """Put the states on the rank grid and settle them.

    The ranks are spaced further apart, one stretch at a time, until every state clears
    every edge; the least crowded drawing is kept if none does.
    """
    columns = {
        node: (slot - (len(layer) - 1) / 2) * _GRAPH.node_gap
        for layer in layers
        for slot, node in enumerate(layer)
        if isinstance(node, str)
    }
    best = None
    for stretch in _STRETCHES:
        positions = {
            state: (columns[state], ranks[state] * _GRAPH.layer_gap * stretch)
            for state in graph.main
        }
        wells = [state for state in graph.states if state in graph.wells]
        preferred = preferred_heights(wells, graph.edges, positions, positions[graph.initial][1])
        place_wells(wells, positions, preferred)
        shortfall = settle(positions, graph.edges, preferred, graph.chips)
        if best is None or shortfall < best[0]:
            best = (shortfall, positions)
        if shortfall <= TOLERANCE:
            break
    return best[1]


# ======================================================================================
#                                   GRAPH AND RANKS
# ======================================================================================


def _read_graph(elements: list[dict]) -> _Graph:
    nodes = [element for element in elements if "source" not in element["data"]]
    if not nodes:
        raise ValueError("A Reward Machine graph needs at least one state")

    def with_class(name: str) -> list[str]:
        return [node["data"]["id"] for node in nodes if name in node.get("classes", "").split()]

    initial = next(iter(with_class("initial")), None)
    if initial is None:
        raise ValueError("A Reward Machine graph needs an initial state")

    states = [node["data"]["id"] for node in nodes]
    order = {state: index for index, state in enumerate(states)}
    final = next(iter(with_class("final")), None)
    chips = {
        (element["data"]["source"], element["data"]["target"]): (
            _GRAPH.label_width(element["data"].get("label", "")) / 2,
            element["data"].get("label_offset", 0.0),
        )
        for element in elements
        if "source" in element["data"] and element["data"]["source"] != element["data"]["target"]
    }
    edges = sorted(chips, key=lambda edge: (order[edge[0]], order[edge[1]]))
    wells = frozenset(with_class("rejecting")) - {initial}
    return _Graph(states, initial, final, wells, edges, chips)


def _forward_edges(graph: _Graph) -> list[tuple[str, str]]:
    """Return the edges that rank the graph.

    None is into or out of a well, none is out of the final state, and none goes back to a
    state on the current depth-first path.
    """
    candidates = [
        (source, target)
        for source, target in graph.edges
        if not {source, target} & graph.wells and source != graph.final
    ]
    successors = defaultdict(list)
    for source, target in candidates:
        successors[source].append(target)

    visited: set[str] = set()
    on_path: set[str] = set()
    back: set[tuple[str, str]] = set()

    def visit(state: str) -> None:
        visited.add(state)
        on_path.add(state)
        for target in successors[state]:
            if target in on_path:
                back.add((state, target))
            elif target not in visited:
                visit(target)
        on_path.discard(state)

    for root in [graph.initial, *graph.main]:
        if root not in visited:
            visit(root)
    return [edge for edge in candidates if edge not in back]


def _ranks(graph: _Graph, forward: list[tuple[str, str]]) -> dict[str, int]:
    rank = dict.fromkeys(graph.main, 0)
    for _ in graph.main:  # longest paths over a DAG settle within one pass per state
        for source, target in forward:
            rank[target] = max(rank[target], rank[source] + 1)
    if graph.final is not None:
        rank[graph.final] = max(rank.values())
    return rank


# ======================================================================================
#                                  ORDER WITHIN RANKS
# ======================================================================================


def _layers(
    graph: _Graph, forward: list[tuple[str, str]], ranks: dict[str, int]
) -> tuple[list[list[Node]], dict[Node, list[Node]], dict[Node, list[Node]]]:
    """Build the ranks with a placeholder per skipped rank, and each node's neighbours."""
    layers: list[list[Node]] = [[] for _ in range(max(ranks.values()) + 1)]
    for state in graph.main:
        layers[ranks[state]].append(state)

    up: dict[Node, list[Node]] = defaultdict(list)
    down: dict[Node, list[Node]] = defaultdict(list)
    for source, target in forward:
        between = range(ranks[source] + 1, ranks[target])
        chain: list[Node] = [source, *((source, target, rank) for rank in between), target]
        for rank, placeholder in zip(between, chain[1:-1], strict=True):
            layers[rank].append(placeholder)
        for upper, lower in pairwise(chain):
            down[upper].append(lower)
            up[lower].append(upper)
    return layers, up, down


def _well_neighbours(graph: _Graph) -> dict[str, int]:
    """Count the wells each state shares an edge with; they pull a state towards the left."""
    pulls: dict[str, int] = defaultdict(int)
    for source, target in graph.edges:
        if target in graph.wells:
            pulls[source] += 1
        if source in graph.wells:
            pulls[target] += 1
    return pulls


def _order_layers(
    layers: list[list[Node]],
    up: dict[Node, list[Node]],
    down: dict[Node, list[Node]],
    pulls: dict[str, int],
    states: list[str],
) -> None:
    order = {state: index for index, state in enumerate(states)}

    def tie(node: Node) -> tuple[int, int]:
        return (order[node], -1) if isinstance(node, str) else (order[node[0]], order[node[1]])

    best = (_crossings(layers, down), [list(layer) for layer in layers])
    for sweep in range(_ORDER_SWEEPS):
        indices = range(1, len(layers)) if sweep % 2 == 0 else range(len(layers) - 2, -1, -1)
        neighbours = up if sweep % 2 == 0 else down
        for index in indices:
            _sort_by_barycenter(layers, index, neighbours, pulls, tie)
        count = _crossings(layers, down)
        if count < best[0]:
            best = (count, [list(layer) for layer in layers])

    layers[:] = best[1]
    _transpose(layers, down)


def _sort_by_barycenter(
    layers: list[list[Node]],
    index: int,
    neighbours: dict[Node, list[Node]],
    pulls: dict[str, int],
    tie,
) -> None:
    position = {
        node: slot - (len(layer) - 1) / 2 for layer in layers for slot, node in enumerate(layer)
    }
    lane = -max(len(layer) for layer in layers) / 2 - 1

    def barycenter(node: Node) -> float:
        slots = [position[other] for other in neighbours[node]]
        if isinstance(node, str):
            slots += [lane] * pulls.get(node, 0)
        return sum(slots) / len(slots) if slots else position[node]

    layers[index].sort(key=lambda node: (barycenter(node), tie(node)))


def _crossings(layers: list[list[Node]], down: dict[Node, list[Node]]) -> int:
    total = 0
    for upper, lower in pairwise(layers):
        slot = {node: index for index, node in enumerate(lower)}
        pairs = [(index, slot[other]) for index, node in enumerate(upper) for other in down[node]]
        total += sum(
            1
            for first, (a, b) in enumerate(pairs)
            for c, d in pairs[first + 1 :]
            if (a - c) * (b - d) < 0
        )
    return total


def _transpose(layers: list[list[Node]], down: dict[Node, list[Node]]) -> None:
    """Swap neighbours inside a rank while that removes crossings."""
    improved = True
    while improved:
        improved = False
        for layer in layers:
            for slot in range(len(layer) - 1):
                before = _crossings(layers, down)
                layer[slot], layer[slot + 1] = layer[slot + 1], layer[slot]
                if _crossings(layers, down) < before:
                    improved = True
                else:
                    layer[slot], layer[slot + 1] = layer[slot + 1], layer[slot]
