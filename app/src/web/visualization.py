"""Convert in-memory Reward Machine structures to read-only Cytoscape data."""

from src.compiler.reward_machine import RewardMachineStructure, Transition


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
            "height": "56px",
            "width": "92px",
        },
    },
    {"selector": ".initial", "style": {"border-color": "#38bdf8", "border-width": 4}},
    {"selector": ".final", "style": {"background-color": "#14532d", "border-color": "#86efac"}},
    {"selector": ".rejecting", "style": {"background-color": "#572033", "border-color": "#fb7185"}},
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
            "edge-text-rotation": "autorotate",
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
    """Return nodes and grouped visual edges for one Reward Machine."""
    elements: list[dict[str, dict[str, object] | str]] = []
    rejecting_states = set(reward_machine.rejecting_states)
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

    grouped: dict[tuple[int, int], list[Transition]] = {}
    for transition in reward_machine.transitions:
        grouped.setdefault((transition.source, transition.destination), []).append(transition)

    for index, ((source, destination), transitions) in enumerate(grouped.items()):
        rewards = {transition.reward for transition in transitions}
        reward_label = (
            "mixed r"
            if len(rewards) != 1
            else f"r={format_reward_label(next(iter(rewards)))}"
        )
        edge_class = _edge_class(transitions)
        elements.append(
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
                    "label": f"{len(transitions)} case{'' if len(transitions) == 1 else 's'} · {reward_label}",
                },
                "classes": edge_class,
            }
        )
    return elements


def format_reward_label(reward: float) -> str:
    """Format rewards compactly while preserving their sign."""
    if reward == 0:
        return "0"
    return f"{reward:+.2f}"


def _edge_class(transitions: list[Transition]) -> str:
    """Return the presentation class for a grouped transition."""
    rewards = {transition.reward for transition in transitions}
    if any(reward < 0 for reward in rewards):
        return "edge-negative" if not any(reward > 0 for reward in rewards) else "edge-zero"
    if any(reward > 0 for reward in rewards):
        return "edge-positive"
    return "edge-zero"
