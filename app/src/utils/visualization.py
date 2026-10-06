"""Shared Reward Machine graph data, layered placement, and display styles."""

from collections import defaultdict, deque
from math import cos, radians

from src.compiler.reward_machine import RewardMachineStructure, Transition
from src.config import GraphStyle

_GRAPH = GraphStyle()
EDGE_LABEL_HEIGHT = 18
EDGE_LABEL_SPACING = 1.25
SELF_LOOP_REACH = 56
SELF_LOOP_LABEL_OFFSET = 23
SELF_LOOP_LABEL_DROP = 10

CYTOSCAPE_STYLESHEET = [
    {
        "selector": "node",
        "style": {
            "label": "data(label)",
            "shape": "roundrectangle",
            "text-valign": "center",
            "text-halign": "center",
            "background-color": "#18263d",
            "border-color": "#5878a8",
            "border-width": 2,
            "color": "#f7f9fc",
            "font-size": "14px",
            "font-weight": 600,
            "height": f"{_GRAPH.node_height}px",
            "width": f"{_GRAPH.node_width}px",
        },
    },
    {"selector": ".initial", "style": {"border-color": "#38bdf8", "border-width": 4}},
    {
        "selector": ".final",
        "style": {"background-color": "#14532d", "border-color": "#86efac"},
    },
    {
        "selector": ".rejecting",
        "style": {"background-color": "#572033", "border-color": "#fb7185"},
    },
    {
        "selector": "edge",
        "style": {
            "label": "data(label)",
            "curve-style": "bezier",
            "line-color": "#7189ad",
            "target-arrow-color": "#7189ad",
            "target-arrow-shape": "triangle",
            "arrow-scale": 1.1,
            "width": 2,
            "color": "#dce7f7",
            "font-size": "11px",
            "text-rotation": "none",
            "text-margin-y": "data(label_offset)",
            "text-background-color": "#0d1728",
            "text-background-opacity": 1,
            "text-background-shape": "roundrectangle",
            "text-border-color": "#385071",
            "text-border-width": 1,
            "text-border-opacity": 1,
        },
    },
    {
        "selector": ".edge-positive",
        "style": {
            "line-color": "#86efac",
            "target-arrow-color": "#86efac",
            "color": "#dcfce7",
            "text-border-color": "#166534",
        },
    },
    {
        "selector": ".edge-zero",
        "style": {
            "line-color": "#b8c7dc",
            "target-arrow-color": "#b8c7dc",
            "color": "#dce7f7",
        },
    },
    {
        "selector": ".edge-negative",
        "style": {
            "line-color": "#fb7185",
            "target-arrow-color": "#fb7185",
            "color": "#fecdd3",
            "text-border-color": "#9f1239",
        },
    },
    {
        "selector": ".edge-loop",
        "style": {
            "loop-direction": "90deg",
            "loop-sweep": "45deg",
            # Match the SVG cubic's rightmost point using Cytoscape's two quadratic curves.
            "control-point-step-size": (_GRAPH.node_width / 2 + 0.75 * SELF_LOOP_REACH)
            / (1.4 * cos(radians(22.5))),
            "text-margin-x": SELF_LOOP_LABEL_OFFSET - 0.75 * SELF_LOOP_REACH,
            "text-margin-y": _GRAPH.node_height / 2 + SELF_LOOP_LABEL_DROP,
        },
    },
    {
        "selector": "node:selected, edge:selected",
        "style": {
            "overlay-color": "#fbbf24",
            "overlay-opacity": 0.14,
            "overlay-padding": "6px",
        },
    },
]


def reward_machine_to_elements(
    reward_machine: RewardMachineStructure,
) -> list[dict[str, dict[str, object] | str]]:
    """Return nodes and grouped visual edges for one Reward Machine.

    Every state without an explicit outgoing ``else`` transition gets a
    presentation-only zero-reward self-loop so the graph shows the runtime's
    implicit fallback. The input structure is not modified.
    """
    elements = _state_elements(reward_machine)
    elements.extend(_edge_elements(reward_machine))

    positions = reward_machine_positions(elements)
    for element in elements[: len(reward_machine.states)]:
        x, y = positions[element["data"]["id"]]
        element["position"] = {"x": x, "y": y}
    edges = elements[len(reward_machine.states) :]
    for edge, offset in zip(edges, edge_label_offsets(edges), strict=True):
        edge["data"]["label_offset"] = offset
    return elements


def _state_elements(
    reward_machine: RewardMachineStructure,
) -> list[dict[str, dict[str, object] | str]]:
    rejecting_states = set(reward_machine.rejecting_states)
    elements: list[dict[str, dict[str, object] | str]] = []
    for state in reward_machine.states:
        classes = ["state"]
        if state == reward_machine.initial_state:
            classes.append("initial")
        if state == reward_machine.final_state:
            classes.append("final")
        if state in rejecting_states:
            classes.append("rejecting")
        elements.append(
            {
                "data": {
                    "id": f"state-{state}",
                    "state": state,
                    "label": f"u{state}",
                },
                "classes": " ".join(classes),
            }
        )
    return elements


def _edge_elements(
    reward_machine: RewardMachineStructure,
) -> list[dict[str, dict[str, object] | str]]:
    grouped: dict[tuple[int, int], list[Transition]] = {}
    for transition in reward_machine.transitions:
        grouped.setdefault((transition.source, transition.destination), []).append(transition)

    explicit_else_sources = {
        transition.source for transition in reward_machine.transitions if _is_else(transition)
    }
    for state in reward_machine.states:
        if state not in explicit_else_sources:
            grouped.setdefault((state, state), []).append(Transition(state, state, ("else",), 0.0))

    return [
        {
            "data": {
                "id": f"transition-{index}",
                "source": f"state-{source}",
                "target": f"state-{destination}",
                "case_count": len(transitions),
                "cases": [
                    {
                        "condition": list(transition.condition),
                        "reward": transition.reward,
                    }
                    for transition in transitions
                ],
                "label": _edge_label(transitions),
            },
            "classes": _edge_class(transitions) + (" edge-loop" if source == destination else ""),
        }
        for index, ((source, destination), transitions) in enumerate(grouped.items())
    ]


def reward_machine_positions(elements: list[dict]) -> dict[str, tuple[float, float]]:
    """Place graph states in the same top-down layers for the app and SVG renderer."""
    nodes = [element for element in elements if "source" not in element["data"]]
    if not nodes:
        raise ValueError("A Reward Machine graph needs at least one state")
    initial = next(
        (node["data"]["id"] for node in nodes if "initial" in node.get("classes", "")),
        None,
    )
    if initial is None:
        raise ValueError("A Reward Machine graph needs an initial state")

    depths = _state_depths(initial, elements)
    fallback = max(depths.values()) + 1
    layers: dict[int, list[str]] = defaultdict(list)
    for node in nodes:
        state = node["data"]["id"]
        layers[depths.get(state, fallback)].append(state)

    widest = max(len(group) for group in layers.values())
    positions: dict[str, tuple[float, float]] = {}
    for depth, group in layers.items():
        left = (widest - len(group)) * _GRAPH.node_gap / 2
        for index, state in enumerate(group):
            positions[state] = (
                left + index * _GRAPH.node_gap,
                depth * _GRAPH.layer_gap,
            )
    return positions


def _state_depths(initial: str, elements: list[dict]) -> dict[str, int]:
    """Return each reachable state's breadth-first distance from the initial one."""
    adjacency: dict[str, list[str]] = defaultdict(list)
    for element in elements:
        if "source" in element["data"]:
            adjacency[element["data"]["source"]].append(element["data"]["target"])

    depths = {initial: 0}
    queue = deque([initial])
    while queue:
        current = queue.popleft()
        for destination in adjacency[current]:
            if destination not in depths:
                depths[destination] = depths[current] + 1
                queue.append(destination)
    return depths


def edge_label_offsets(edges: list[dict]) -> list[float]:
    """Separate labels of sibling transitions vertically in both renderers."""
    groups: dict[str, list[int]] = defaultdict(list)
    for index, edge in enumerate(edges):
        data = edge["data"]
        if data["source"] != data["target"]:
            groups[data["source"]].append(index)

    offsets = [0.0] * len(edges)
    step = EDGE_LABEL_HEIGHT * EDGE_LABEL_SPACING
    for indices in groups.values():
        middle = (len(indices) - 1) / 2
        for position, index in enumerate(indices):
            offsets[index] = (position - middle) * step
    return offsets


def format_reward_label(reward: float) -> str:
    """Format rewards compactly while preserving their sign."""
    if reward == 0:
        return "0"
    return f"{reward:+.2f}"


def _is_else(transition: Transition) -> bool:
    """Match the runtime's case-insensitive ``else`` fallback recognition."""
    return len(transition.condition) == 1 and transition.condition[0].strip().lower() == "else"


def _edge_label(transitions: list[Transition]) -> str:
    """Describe the formal cases under one grouped visual edge."""
    rewards = {transition.reward for transition in transitions}
    reward_label = (
        "mixed r" if len(rewards) != 1 else f"r={format_reward_label(next(iter(rewards)))}"
    )
    else_count = sum(1 for transition in transitions if _is_else(transition))
    if else_count == 0:
        return f"{_case_label(len(transitions))} · {reward_label}"

    ordinary_count = len(transitions) - else_count
    if ordinary_count == 0:
        return f"else · {reward_label}"
    return f"{_case_label(ordinary_count)} + else · {reward_label}"


def _case_label(count: int) -> str:
    """Format a transition-case count for an edge label."""
    return f"{count} case{'' if count == 1 else 's'}"


def _edge_class(transitions: list[Transition]) -> str:
    """Return the presentation class for a grouped transition."""
    rewards = {transition.reward for transition in transitions}
    if any(reward < 0 for reward in rewards):
        return "edge-negative" if not any(reward > 0 for reward in rewards) else "edge-zero"
    if any(reward > 0 for reward in rewards):
        return "edge-positive"
    return "edge-zero"
