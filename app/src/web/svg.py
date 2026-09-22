"""Render Cytoscape Reward Machine elements to a standalone SVG document.

The web graph view and the ``render_rm`` script share this module: the app passes
the live node positions so an export keeps whatever placement the user arranged,
while the script omits them and gets a deterministic layered layout.

Sizing comes from :class:`src.config.GraphStyle`, adjustable in ``config.py``.
"""

from __future__ import annotations

from collections import defaultdict, deque

from src.config import GraphStyle

from .visualization import CYTOSCAPE_STYLESHEET


GRAPH = GraphStyle()

STYLES = {entry["selector"]: entry["style"] for entry in CYTOSCAPE_STYLESHEET}
BACKGROUND = STYLES["edge"]["text-background-color"]

EDGE_CLASSES = ("edge-positive", "edge-negative", "edge-zero")
EDGE_COLOURS = {name: STYLES[f".{name}"]["line-color"] for name in EDGE_CLASSES}
EDGE_WIDTH = STYLES["edge"]["width"]

CHIP_HEIGHT = 18
CHIP_SPACING = 1.25
BACK_EDGE_REACH = 26
EDGE_PADDING = 6


def render_elements_svg(elements: list[dict], positions: dict | None = None) -> str:
    """Render Cytoscape elements as a standalone SVG document.

    When ``positions`` maps state ids to model coordinates, those placements are
    preserved and only translated, so pan and zoom do not affect the export.
    Without positions the states are placed on a top-down layered grid.
    """
    nodes = [element for element in elements if "source" not in element["data"]]
    edges = [element for element in elements if "source" in element["data"]]
    if not nodes:
        raise ValueError("A Reward Machine graph needs at least one state")

    if positions is None:
        initial = next(
            (node["data"]["id"] for node in nodes if "initial" in node.get("classes", "")),
            None,
        )
        if initial is None:
            raise ValueError("A Reward Machine graph needs an initial state")
        positions = _layered_positions(nodes, edges, initial)

    positions, width, height = _fit(positions)
    return _document(nodes, edges, positions, width, height)


def _node_style(classes: str) -> dict:
    """Merge the base node style with the classes assigned by the app."""
    style = dict(STYLES["node"])
    for name in classes.split():
        style.update(STYLES.get(f".{name}", {}))
    return style


def _edge_class(classes: str) -> str:
    """Return the app's edge class for one grouped transition."""
    return next((name for name in EDGE_CLASSES if name in classes), "edge-zero")


def _marker_id(classes: str) -> str:
    """Return the arrow marker id matching the edge class."""
    return f"arrow-{_edge_class(classes).removeprefix('edge-')}"


def _label_style(classes: str) -> dict:
    """Merge the base edge style with the classes so chips match the screen."""
    style = dict(STYLES["edge"])
    style.update(STYLES[f".{_edge_class(classes)}"])
    return style


# ======================================================================================
#                                    LAYOUT
# ======================================================================================

def _layered_positions(nodes: list[dict], edges: list[dict], initial: str) -> dict:
    """Place states on a top-down grid by breadth-first depth from the initial state."""
    order = [node["data"]["id"] for node in nodes]
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        adjacency[edge["data"]["source"]].append(edge["data"]["target"])

    depths = {initial: 0}
    queue = deque([initial])
    while queue:
        current = queue.popleft()
        for destination in adjacency[current]:
            if destination not in depths:
                depths[destination] = depths[current] + 1
                queue.append(destination)

    fallback = max(depths.values(), default=0) + 1
    for node in order:
        depths.setdefault(node, fallback)

    layers: dict[int, list[str]] = defaultdict(list)
    for node in order:
        layers[depths[node]].append(node)

    widest = max(len(group) for group in layers.values())
    positions: dict[str, tuple[float, float]] = {}
    for depth, group in layers.items():
        left = (widest - len(group)) * GRAPH.node_gap / 2
        for index, node in enumerate(group):
            positions[node] = (left + index * GRAPH.node_gap, depth * GRAPH.layer_gap)
    return positions


def _fit(positions: dict) -> tuple[dict, float, float]:
    """Translate positions into the canvas and size it to the full bounding box."""
    left = max(GRAPH.margin, BACK_EDGE_REACH + EDGE_PADDING)
    min_x = min(x for x, _ in positions.values())
    min_y = min(y for _, y in positions.values())
    shifted = {
        node: (
            x - min_x + left + GRAPH.node_width / 2,
            y - min_y + GRAPH.margin + GRAPH.node_height / 2,
        )
        for node, (x, y) in positions.items()
    }
    width = (
        max(x for x, _ in shifted.values())
        + GRAPH.node_width / 2
        + GRAPH.margin
        + GRAPH.arc_room
    )
    height = max(y for _, y in shifted.values()) + GRAPH.node_height / 2 + GRAPH.margin
    return shifted, width, height


def _clip(centre: tuple[float, float], target: tuple[float, float]) -> tuple[float, float]:
    """Return where a centre-to-target ray leaves the node rectangle."""
    dx = target[0] - centre[0]
    dy = target[1] - centre[1]
    if dx == 0 and dy == 0:
        return centre
    horizontal = abs(dx) / (GRAPH.node_width / 2)
    vertical = abs(dy) / (GRAPH.node_height / 2)
    scale = 1 / max(horizontal, vertical)
    return centre[0] + dx * scale, centre[1] + dy * scale


def _label_offsets(edges: list[dict]) -> list[float]:
    """Vertical offsets so chips of sibling edges from one state do not overlap."""
    groups: dict[str, list[int]] = defaultdict(list)
    for index, edge in enumerate(edges):
        data = edge["data"]
        if data["source"] != data["target"]:
            groups[data["source"]].append(index)

    offsets = [0.0] * len(edges)
    step = CHIP_HEIGHT * CHIP_SPACING
    for indices in groups.values():
        middle = (len(indices) - 1) / 2
        for position, index in enumerate(indices):
            offsets[index] = (position - middle) * step
    return offsets


# ======================================================================================
#                                   SVG OUTPUT
# ======================================================================================

def _document(nodes: list[dict], edges: list[dict], positions: dict, width: float, height: float) -> str:
    """Assemble the SVG document from positioned nodes and routed edges."""
    offsets = _label_offsets(edges)
    routed = [
        _edge_parts(edge, positions, width, offsets[index])
        for index, edge in enumerate(edges)
    ]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" '
        f'font-family="-apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif">',
        _markers(),
        f'<rect width="100%" height="100%" fill="{BACKGROUND}"/>',
    ]
    parts.extend(path for path, _ in routed)
    parts.extend(_node_svg(node, positions) for node in nodes)
    parts.extend(label for _, label in routed)
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _markers() -> str:
    """Build one arrowhead marker per edge colour."""
    markers = "".join(
        f'<marker id="arrow-{name.removeprefix("edge-")}" viewBox="0 0 10 10" '
        f'refX="9.5" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{colour}"/></marker>'
        for name, colour in EDGE_COLOURS.items()
    )
    return f"<defs>{markers}</defs>"


def _node_svg(node: dict, positions: dict) -> str:
    """Draw one state as a labelled rounded rectangle."""
    x, y = positions[node["data"]["id"]]
    style = _node_style(node.get("classes", ""))
    return (
        f'<g><rect x="{x - GRAPH.node_width / 2:.0f}" y="{y - GRAPH.node_height / 2:.0f}" '
        f'width="{GRAPH.node_width}" height="{GRAPH.node_height}" rx="9" '
        f'fill="{style["background-color"]}" stroke="{style["border-color"]}" '
        f'stroke-width="{style["border-width"]}"/>'
        f'<text x="{x:.0f}" y="{y:.0f}" fill="{style["color"]}" font-size="{style["font-size"]}" '
        f'font-weight="600" text-anchor="middle" dominant-baseline="central">'
        f'{_escape(node["data"]["label"])}</text></g>'
    )


def _edge_parts(edge: dict, positions: dict, canvas_width: float, y_offset: float) -> tuple[str, str]:
    """Route one grouped transition into a path group and a label group.

    Paths and labels are returned separately so labels can be drawn above the
    nodes when a user-arranged layout overlaps them.
    """
    data = edge["data"]
    classes = edge.get("classes", "")
    source = data["source"]
    target = data["target"]

    if source == target:
        path, label_x, label_y = _self_loop(positions[source])
    elif positions[target][1] < positions[source][1]:
        path, label_x, label_y = _back_edge(positions[source], positions[target])
        label_y += y_offset
    else:
        start = _clip(positions[source], positions[target])
        end = _clip(positions[target], positions[source])
        path = f"M {start[0]:.0f} {start[1]:.0f} L {end[0]:.0f} {end[1]:.0f}"
        label_x = (start[0] + end[0]) / 2
        label_y = (start[1] + end[1]) / 2 + y_offset

    label = data.get("label", "")
    path_svg = (
        f'<g><title>{_escape(_case_text(edge))}</title>'
        f'<path d="{path}" fill="none" stroke="{EDGE_COLOURS[_edge_class(classes)]}" '
        f'stroke-width="{EDGE_WIDTH}" marker-end="url(#{_marker_id(classes)})"/></g>'
    )
    chip = _label_svg(
        _clamped_x(label_x, label, canvas_width),
        label_y,
        label,
        _label_style(classes),
    )
    return path_svg, chip


def _self_loop(position: tuple[float, float]) -> tuple[str, float, float]:
    """Route a self-transition as a loop on the right, with its label below.

    The path ends on the node boundary so the arrowhead falls outside the rect.
    The label sits under the loop, centred on it, clear of a right neighbour.
    """
    x, y = position
    start = (x + GRAPH.node_width / 2, y - GRAPH.node_height / 2 + 8)
    end = (x + GRAPH.node_width / 2, y + GRAPH.node_height / 2 - 8)
    control_x = x + GRAPH.node_width / 2 + 56
    path = (
        f"M {start[0]:.0f} {start[1]:.0f} "
        f"C {control_x:.0f} {start[1] - 24:.0f} {control_x:.0f} {end[1] + 24:.0f} "
        f"{end[0]:.0f} {end[1]:.0f}"
    )
    return path, x + GRAPH.node_width / 2 + 23, y + GRAPH.node_height / 2 + 10


def _back_edge(
    source: tuple[float, float],
    target: tuple[float, float],
) -> tuple[str, float, float]:
    """Route a backward transition around the left of the node column."""
    start = (source[0] - GRAPH.node_width / 2, source[1])
    end = (target[0] - GRAPH.node_width / 2, target[1])
    control = (min(source[0], target[0]) - GRAPH.node_width / 2 - 52, (start[1] + end[1]) / 2)
    path = (
        f"M {start[0]:.0f} {start[1]:.0f} "
        f"Q {control[0]:.0f} {control[1]:.0f} {end[0]:.0f} {end[1]:.0f}"
    )
    return path, *_quadratic_point(start, control, end, 0.35)


def _quadratic_point(
    start: tuple[float, float],
    control: tuple[float, float],
    end: tuple[float, float],
    t: float,
) -> tuple[float, float]:
    """Return the point at parameter ``t`` on a quadratic Bezier curve."""
    inverse = 1 - t
    return (
        inverse**2 * start[0] + 2 * inverse * t * control[0] + t**2 * end[0],
        inverse**2 * start[1] + 2 * inverse * t * control[1] + t**2 * end[1],
    )


def _label_svg(x: float, y: float, text: str, style: dict) -> str:
    """Draw an edge reward label on a rounded background chip."""
    width = _label_width(text)
    return (
        f'<rect x="{x - width / 2:.0f}" y="{y - CHIP_HEIGHT / 2:.0f}" width="{width:.0f}" '
        f'height="{CHIP_HEIGHT}" rx="4" fill="{BACKGROUND}" '
        f'stroke="{style["text-border-color"]}" stroke-width="1"/>'
        f'<text x="{x:.0f}" y="{y:.0f}" fill="{style["color"]}" font-size="11" '
        f'text-anchor="middle" dominant-baseline="central">{_escape(text)}</text>'
    )


def _label_width(text: str) -> float:
    """Approximate the chip width from the label length."""
    return len(text) * 6.2 + 12


def _clamped_x(x: float, text: str, canvas_width: float) -> float:
    """Keep a label chip inside the canvas however small the margin is."""
    half = _label_width(text) / 2
    return max(half + 2, min(x, canvas_width - half - 2))


def _case_text(edge: dict) -> str:
    """Summarise the individual guards grouped under one drawn edge."""
    cases = edge["data"].get("cases", [])
    joined = "; ".join(" ".join(case.get("condition", [])) for case in cases)
    return joined or edge["data"].get("label", "")


def _escape(text: str) -> str:
    """Escape the XML characters that can appear in guards and labels."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
