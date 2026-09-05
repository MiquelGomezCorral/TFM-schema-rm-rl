"""Convert in-memory Reward Machine structures to read-only Cytoscape data."""

from src.compiler.reward_machine import RewardMachineStructure


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
    """Return one Cytoscape node per state and one edge per explicit transition."""
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

    for index, transition in enumerate(reward_machine.transitions):
        guard = ",".join(transition.condition) or "true"
        elements.append(
            {
                "data": {
                    "id": f"transition-{index}",
                    "source": f"state-{transition.source}",
                    "target": f"state-{transition.destination}",
                    "guard": guard,
                    "reward": transition.reward,
                    "label": f"{guard} | r={transition.reward:.2f}",
                }
            }
        )
    return elements


# Keep a short conversion name for callers that only need the presentation boundary.
to_cytoscape_elements = reward_machine_to_elements
