"""Render Cytoscape Reward Machine elements to a standalone SVG document.

The web graph view, the step report and the ``render_rm`` script share this module: the
app passes the live node positions so an export keeps whatever placement the user
arranged, while the others omit them and get a deterministic layered layout.

Sizing comes from :class:`src.config.GraphStyle`, adjustable in ``config.py``.
"""

from __future__ import annotations

from math import cos, hypot, radians, sin

from src.compiler.reward_machine import RewardMachineStructure
from src.config import GraphStyle

from .layout import element_positions
from .visualization import (
    CYTOSCAPE_STYLESHEET,
    SELF_LOOP_LABEL_DROP,
    SELF_LOOP_LABEL_OFFSET,
    SELF_LOOP_REACH,
    edge_label_offsets,
    reward_machine_to_elements,
)

GRAPH = GraphStyle()
RADIUS = GRAPH.node_diameter / 2
LOOP_HALF_SWEEP = radians(22.5)  # a self-loop leaves and returns this far above and below the right

STYLES = {entry["selector"]: entry["style"] for entry in CYTOSCAPE_STYLESHEET}
BACKGROUND = STYLES["edge"]["text-background-color"]

EDGE_CLASSES = ("edge-positive", "edge-negative", "edge-zero")
EDGE_COLOURS = {name: STYLES[f".{name}"]["line-color"] for name in EDGE_CLASSES}
EDGE_WIDTH = STYLES["edge"]["width"]

BACK_EDGE_REACH = 26
EDGE_PADDING = 6


def render_structure_svg(structure: RewardMachineStructure) -> str:
    """Return a standalone SVG document for one numeric Reward Machine structure."""
    return render_elements_svg(reward_machine_to_elements(structure))


def render_elements_svg(elements: list[dict], positions: dict | None = None) -> str:
    """Render Cytoscape elements as a standalone SVG document.

    When ``positions`` maps state ids to model coordinates, those placements are
    preserved and only translated, so pan and zoom do not affect the export.
    Without positions the states keep the ``position`` their elements carry, and
    are laid out only if one of them has none.
    """
    nodes = [element for element in elements if "source" not in element["data"]]
    edges = [element for element in elements if "source" in element["data"]]
    if not nodes:
        raise ValueError("A Reward Machine graph needs at least one state")

    if positions is None:
        positions = element_positions(elements)

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


def _fit(positions: dict) -> tuple[dict, float, float]:
    """Translate positions into the canvas and size it to the full bounding box."""
    left = max(GRAPH.margin, BACK_EDGE_REACH + EDGE_PADDING)
    min_x = min(x for x, _ in positions.values())
    min_y = min(y for _, y in positions.values())
    shifted = {
        node: (
            x - min_x + left + RADIUS,
            y - min_y + GRAPH.margin + RADIUS,
        )
        for node, (x, y) in positions.items()
    }
    width = max(x for x, _ in shifted.values()) + RADIUS + GRAPH.margin + GRAPH.arc_room
    height = max(y for _, y in shifted.values()) + RADIUS + GRAPH.margin
    return shifted, width, height


def _clip(centre: tuple[float, float], target: tuple[float, float]) -> tuple[float, float]:
    """Return where a centre-to-target ray leaves the node circle."""
    dx = target[0] - centre[0]
    dy = target[1] - centre[1]
    distance = hypot(dx, dy)
    if distance == 0:
        return centre
    scale = RADIUS / distance
    return centre[0] + dx * scale, centre[1] + dy * scale


# ======================================================================================
#                                   SVG OUTPUT
# ======================================================================================


def _document(
    nodes: list[dict], edges: list[dict], positions: dict, width: float, height: float
) -> str:
    """Assemble the SVG document from positioned nodes and routed edges."""
    offsets = edge_label_offsets(edges)
    pairs = {(edge["data"]["source"], edge["data"]["target"]) for edge in edges}
    routed = [
        _edge_parts(
            edge,
            positions,
            width,
            offsets[index],
            (edge["data"]["target"], edge["data"]["source"]) in pairs,
        )
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
    """Draw one state as a labelled circle."""
    x, y = positions[node["data"]["id"]]
    style = _node_style(node.get("classes", ""))
    return (
        f'<g><circle cx="{x:.0f}" cy="{y:.0f}" r="{RADIUS:.0f}" '
        f'fill="{style["background-color"]}" stroke="{style["border-color"]}" '
        f'stroke-width="{style["border-width"]}"/>'
        f'<text x="{x:.0f}" y="{y:.0f}" fill="{style["color"]}" font-size="{style["font-size"]}" '
        f'font-weight="600" text-anchor="middle" dominant-baseline="central">'
        f"{_escape(node['data']['label'])}</text></g>"
    )


def _edge_parts(
    edge: dict, positions: dict, canvas_width: float, y_offset: float, has_reverse: bool
) -> tuple[str, str]:
    """Route one grouped transition into a path group and a label group.

    Paths and labels are returned separately so labels can be drawn above the
    nodes when a user-arranged layout overlaps them. An upward edge is curved only
    when the transition the other way exists, to keep the pair apart; every other
    edge is straight, as the app draws it.
    """
    data = edge["data"]
    classes = edge.get("classes", "")
    source = data["source"]
    target = data["target"]

    if source == target:
        path, label_x, label_y = _self_loop(positions[source])
    elif has_reverse and positions[target][1] < positions[source][1]:
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
        f"<g><title>{_escape(_case_text(edge))}</title>"
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

    The path ends on the node boundary so the arrowhead falls outside the circle.
    The label sits under the loop, centred on it, clear of a right neighbour.
    """
    x, y = position
    start = (x + RADIUS * cos(LOOP_HALF_SWEEP), y - RADIUS * sin(LOOP_HALF_SWEEP))
    end = (start[0], y + RADIUS * sin(LOOP_HALF_SWEEP))
    control_x = x + RADIUS + SELF_LOOP_REACH
    path = (
        f"M {start[0]:.0f} {start[1]:.0f} "
        f"C {control_x:.0f} {start[1] - 24:.0f} {control_x:.0f} {end[1] + 24:.0f} "
        f"{end[0]:.0f} {end[1]:.0f}"
    )
    return (
        path,
        x + RADIUS + SELF_LOOP_LABEL_OFFSET,
        y + RADIUS + SELF_LOOP_LABEL_DROP,
    )


def _back_edge(
    source: tuple[float, float],
    target: tuple[float, float],
) -> tuple[str, float, float]:
    """Route a backward transition around the left of the node column."""
    start = (source[0] - RADIUS, source[1])
    end = (target[0] - RADIUS, target[1])
    control = (
        min(source[0], target[0]) - RADIUS - 52,
        (start[1] + end[1]) / 2,
    )
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
    width = GRAPH.label_width(text)
    return (
        f'<rect x="{x - width / 2:.0f}" y="{y - GRAPH.label_height / 2:.0f}" width="{width:.0f}" '
        f'height="{GRAPH.label_height}" rx="4" fill="{BACKGROUND}" '
        f'stroke="{style["text-border-color"]}" stroke-width="1"/>'
        f'<text x="{x:.0f}" y="{y:.0f}" fill="{style["color"]}" font-size="11" '
        f'text-anchor="middle" dominant-baseline="central">{_escape(text)}</text>'
    )


def _clamped_x(x: float, text: str, canvas_width: float) -> float:
    """Keep a label chip inside the canvas however small the margin is."""
    half = GRAPH.label_width(text) / 2
    return max(half + 2, min(x, canvas_width - half - 2))


def _case_text(edge: dict) -> str:
    """Summarise the individual guards grouped under one drawn edge."""
    cases = edge["data"].get("cases", [])
    joined = "; ".join(" ".join(case.get("condition", [])) for case in cases)
    return joined or edge["data"].get("label", "")


def _escape(text: str) -> str:
    """Escape the XML characters that can appear in guards and labels."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
