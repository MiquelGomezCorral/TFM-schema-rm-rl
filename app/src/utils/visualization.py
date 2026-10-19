"""Shared Reward Machine graph data and display styles."""

from collections import defaultdict
from math import cos, radians

from src.compiler.reward_machine import RewardMachineStructure, Transition
from src.config import GraphStyle

from .layout import reward_machine_positions

_GRAPH = GraphStyle()
_RADIUS = _GRAPH.node_diameter / 2
EDGE_LABEL_SPACING = 1.25
SELF_LOOP_REACH = 56
SELF_LOOP_LABEL_OFFSET = 23
SELF_LOOP_LABEL_DROP = 10
HOVER_CLASS = "rm-hover"  # set by rm_graph.js while an edge, or its source state, is hovered

# Cytoscape takes literal colours, so the dark palette lives here once, keyed by its UI role.
_DARK = {
    "page": "#0a0c10",
    "raised": "#171b21",
    "hover": "#1e232b",
    "border": "#23272f",
    "border_strong": "#3d434d",
    "text": "#e9edf2",
    "muted": "#8b95a3",
    "accent": "#7c9cff",
    "success": "#4ec9a0",
    "success_tint": "#17352c",
    "success_ink": "#8fe3c4",
    "warning": "#e2b04a",
    "danger": "#f0707a",
    "danger_tint": "#3a2024",
    "danger_ink": "#f6a6ac",
}

CYTOSCAPE_STYLESHEET = [
    {
        "selector": "node",
        "style": {
            "label": "data(label)",
            "shape": "ellipse",
            "text-valign": "center",
            "text-halign": "center",
            "background-color": _DARK["raised"],
            "border-color": _DARK["border_strong"],
            "border-width": 2,
            "color": _DARK["text"],
            "font-size": "14px",
            "font-weight": 600,
            "height": f"{_GRAPH.node_diameter}px",
            "width": f"{_GRAPH.node_diameter}px",
        },
    },
    {
        "selector": ".initial",
        "style": {"border-color": _DARK["accent"], "border-width": 4},
    },
    {
        "selector": ".final",
        "style": {"background-color": _DARK["success_tint"], "border-color": _DARK["success"]},
    },
    {
        "selector": ".rejecting",
        "style": {"background-color": _DARK["danger_tint"], "border-color": _DARK["danger"]},
    },
    {
        "selector": "edge",
        "style": {
            "label": "data(label)",
            "curve-style": "bezier",
            "line-color": _DARK["border_strong"],
            "target-arrow-color": _DARK["border_strong"],
            "target-arrow-shape": "triangle",
            "arrow-scale": 1.1,
            "width": 2,
            "color": _DARK["muted"],
            "font-size": "11px",
            "text-rotation": "none",
            "text-margin-y": "data(label_offset)",
            "text-background-color": _DARK["page"],
            "text-background-opacity": 1,
            "text-background-shape": "roundrectangle",
            "text-border-color": _DARK["border"],
            "text-border-width": 1,
            "text-border-opacity": 1,
        },
    },
    {
        "selector": ".edge-positive",
        "style": {
            "line-color": _DARK["success"],
            "target-arrow-color": _DARK["success"],
            "color": _DARK["success_ink"],
            "text-border-color": _DARK["success_tint"],
        },
    },
    {
        "selector": ".edge-zero",
        "style": {
            "line-color": _DARK["muted"],
            "target-arrow-color": _DARK["muted"],
            "color": _DARK["text"],
        },
    },
    {
        "selector": ".edge-negative",
        "style": {
            "line-color": _DARK["danger"],
            "target-arrow-color": _DARK["danger"],
            "color": _DARK["danger_ink"],
            "text-border-color": _DARK["danger_tint"],
        },
    },
    {
        "selector": ".edge-loop",
        "style": {
            "loop-direction": "90deg",
            "loop-sweep": "45deg",
            # Match the SVG cubic's rightmost point using Cytoscape's two quadratic curves.
            "control-point-step-size": (_RADIUS + 0.75 * SELF_LOOP_REACH)
            / (1.4 * cos(radians(22.5))),
            "text-margin-x": SELF_LOOP_LABEL_OFFSET - 0.75 * SELF_LOOP_REACH,
            "text-margin-y": _RADIUS + SELF_LOOP_LABEL_DROP,
        },
    },
    {
        "selector": f"edge.{HOVER_CLASS}",
        "style": {
            "width": 4,
            "overlay-color": _DARK["accent"],
            "overlay-opacity": 0.18,
            "overlay-padding": "4px",
        },
    },
    {
        "selector": "node:selected, edge:selected",
        "style": {
            "overlay-color": _DARK["warning"],
            "overlay-opacity": 0.14,
            "overlay-padding": "6px",
        },
    },
]


# The light theme reuses the dark stylesheet and swaps only the colors listed here, by selector.
_LIGHT_OVERRIDES = {
    "node": {"background-color": "#f1f5f9", "border-color": "#64748b", "color": "#0f172a"},
    ".initial": {"border-color": "#0284c7"},
    ".final": {"background-color": "#dcfce7", "border-color": "#16a34a"},
    ".rejecting": {"background-color": "#ffe4e6", "border-color": "#e11d48"},
    "edge": {
        "line-color": "#64748b",
        "target-arrow-color": "#64748b",
        "color": "#1e293b",
        "text-background-color": "#ffffff",
        "text-border-color": "#cbd5e1",
    },
    ".edge-positive": {
        "line-color": "#16a34a",
        "target-arrow-color": "#16a34a",
        "color": "#14532d",
        "text-border-color": "#86efac",
    },
    ".edge-zero": {
        "line-color": "#94a3b8",
        "target-arrow-color": "#94a3b8",
        "color": "#1e293b",
    },
    ".edge-negative": {
        "line-color": "#e11d48",
        "target-arrow-color": "#e11d48",
        "color": "#881337",
        "text-border-color": "#fda4af",
    },
    f"edge.{HOVER_CLASS}": {"overlay-color": "#0284c7"},
    "node:selected, edge:selected": {"overlay-color": "#d97706"},
}

CYTOSCAPE_STYLESHEET_LIGHT = [
    {
        "selector": rule["selector"],
        "style": {**rule["style"], **_LIGHT_OVERRIDES.get(rule["selector"], {})},
    }
    for rule in CYTOSCAPE_STYLESHEET
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

    edges = elements[len(reward_machine.states) :]
    for edge, offset in zip(edges, edge_label_offsets(edges), strict=True):
        edge["data"]["label_offset"] = offset

    positions = reward_machine_positions(elements)
    for element in elements[: len(reward_machine.states)]:
        x, y = positions[element["data"]["id"]]
        element["position"] = {"x": x, "y": y}
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
                        "reward_label": format_reward_label(transition.reward),
                    }
                    for transition in transitions
                ],
                "label": _edge_label(transitions),
            },
            "classes": _edge_class(transitions) + (" edge-loop" if source == destination else ""),
        }
        for index, ((source, destination), transitions) in enumerate(grouped.items())
    ]


def edge_label_offsets(edges: list[dict]) -> list[float]:
    """Separate labels of sibling transitions vertically in both renderers."""
    groups: dict[str, list[int]] = defaultdict(list)
    for index, edge in enumerate(edges):
        data = edge["data"]
        if data["source"] != data["target"]:
            groups[data["source"]].append(index)

    offsets = [0.0] * len(edges)
    step = _GRAPH.label_height * EDGE_LABEL_SPACING
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
