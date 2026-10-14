"""Render Cytoscape Reward Machine elements to one self-contained interactive HTML page.

The page inlines the vendored Cytoscape.js, the app's graph stylesheet and the same
``rm_graph.js`` / ``rm_graph.css`` the web UI loads, so hovering, the transition panel,
pan, zoom and dragging behave like the app. Without positions the states use the same
top-down layout as the SVG export.
"""

import json
from pathlib import Path

from src.compiler.reward_machine import RewardMachineStructure

from .layout import element_positions
from .visualization import CYTOSCAPE_STYLESHEET, HOVER_CLASS, reward_machine_to_elements

_APP_ROOT = Path(__file__).resolve().parents[2]
_CYTOSCAPE_JS = _APP_ROOT / "vendor" / "cytoscape" / "cytoscape.min.js"
_GRAPH_JS = _APP_ROOT / "assets" / "rm_graph.js"
_GRAPH_CSS = _APP_ROOT / "assets" / "rm_graph.css"

# The graph stage uses the same dark background as the web UI's graph panel.
_PAGE_STYLE = """
html, body { height: 100%; margin: 0; background: #0c1626; }
.rm-graph-stage { position: relative; width: 100%; height: 100%; overflow: hidden; }
#rm-graph { width: 100%; height: 100%; }
"""

# Same Cytoscape options as the web UI's graph component.
_BOOT_SCRIPT = """
const data = JSON.parse(document.getElementById("rm-graph-data").textContent);
const cy = cytoscape({
  container: document.getElementById("rm-graph"),
  elements: data.elements,
  style: data.style,
  layout: { name: "preset", fit: true, padding: 60 },
  wheelSensitivity: 0.15,
  boxSelectionEnabled: false,
});
const stage = document.getElementById("rm-graph-stage");
window.rmGraph.attach(cy, stage);
window.rmGraph.guardFrameWheel(cy, stage);
"""


def render_structure_html(structure: RewardMachineStructure) -> str:
    """Return a standalone interactive HTML page for one numeric Reward Machine structure."""
    return render_elements_html(reward_machine_to_elements(structure))


def render_elements_html(elements: list[dict], positions: dict | None = None) -> str:
    """Render Cytoscape elements as a standalone interactive HTML page.

    When ``positions`` maps state ids to model coordinates, the page opens with those
    placements, so an export keeps whatever the user arranged. Without positions the
    states keep the ``position`` their elements carry, and are laid out (as for the SVG)
    only if one of them has none.
    """
    if positions is None:
        positions = element_positions(elements)

    page_elements = []
    for element in elements:
        data = element["data"]
        # A hover highlight caught mid-export must not open the page highlighted.
        classes = [name for name in element.get("classes", "").split() if name != HOVER_CLASS]
        page_element = {"data": data, "classes": " ".join(classes)}
        if "source" not in data:
            x, y = positions[data["id"]]
            page_element["position"] = {"x": x, "y": y}
        page_elements.append(page_element)

    # Labels and guards come from model output, so "<" must not close the script block.
    payload = json.dumps({"elements": page_elements, "style": CYTOSCAPE_STYLESHEET})
    payload = payload.replace("<", "\\u003c")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reward Machine graph</title>
<style>{_PAGE_STYLE}{_GRAPH_CSS.read_text(encoding="utf-8")}</style>
</head>
<body>
<div id="rm-graph-stage" class="rm-graph-stage"><div id="rm-graph"></div></div>
<script id="rm-graph-data" type="application/json">{payload}</script>
<script>{_CYTOSCAPE_JS.read_text(encoding="utf-8")}</script>
<script>{_GRAPH_JS.read_text(encoding="utf-8")}</script>
<script>{_BOOT_SCRIPT}</script>
</body>
</html>
"""
