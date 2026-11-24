"""Draw figure.html from data/levels.json: right RMs against median seconds per RM, final rows only.

The share right has 95% Wilson bars; x is the median seconds per RM on a log axis, one colour per
model, points labelled by level. A preview of the thesis figure (its Figure 6.5 for the production pair), drawn as plain SVG so the page opens
from disk with no script. The thesis draws its own version from data/levels.csv.

Run from the repository root, after build.py (standard library only):
python -I docs/paper/other-llms-by-level/check/figure.py
"""

import json
import math
from html import escape
from pathlib import Path

ENTRY = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 780, 470
LEFT, RIGHT, TOP, BOTTOM = 62, 22, 16, 54
Y_TOP = 102  # a little above 100 so a bar that reaches 100% is not cut by the frame
X_TICKS = [mantissa * 10**power for power in range(-1, 5) for mantissa in (1, 2, 5)]
# Series colours of the artifact pages, light then dark; the model order of the data picks the colour.
SERIES_LIGHT = [
    "#2f5bd3",
    "#d96f00",
    "#1f7a4d",
    "#b3261e",
    "#b03a9a",
    "#1b7f8c",
    "#6b52c0",
    "#8a6d3b",
]
SERIES_DARK = [
    "#8fb0ff",
    "#ffa24d",
    "#5fd394",
    "#ff8a80",
    "#e58ad2",
    "#5ccfdc",
    "#b9a2ff",
    "#d8b56b",
]


def tokens(colors: list[str]) -> str:
    return "".join(f"--c{i}:{color};" for i, color in enumerate(colors))


CSS = f"""
:root {{ --bg:#fff; --fg:#1d1d1f; --line:#5b5b66; --grid:#5b5b6633; {tokens(SERIES_LIGHT)} }}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{ --bg:#1d1d21; --fg:#ececf0; --line:#b9b9c4; --grid:#b9b9c433;
    {tokens(SERIES_DARK)} }}
}}
:root[data-theme="dark"] {{ --bg:#1d1d21; --fg:#ececf0; --line:#b9b9c4; --grid:#b9b9c433; {tokens(SERIES_DARK)} }}
body {{ background:var(--bg); color:var(--fg); font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  margin:0; }}
main {{ max-width:860px; margin:0 auto; padding:24px 16px 48px; }}
h1 {{ font-size:1.3rem; margin:0 0 8px; }}
p {{ margin:8px 0; }}
.legend {{ display:flex; flex-wrap:wrap; gap:4px 18px; margin:12px 0 4px; font-size:.9rem; }}
.swatch {{ display:inline-block; width:12px; height:12px; border-radius:50%; margin-right:6px; vertical-align:-1px; }}
svg {{ width:100%; height:auto; display:block; }}
svg text {{ fill:var(--fg); font-size:12px; }}
.grid {{ stroke:var(--grid); }}
.axis {{ stroke:var(--line); }}
.series {{ fill:none; stroke-width:1.5; opacity:.55; }}
.dot {{ stroke:var(--bg); stroke-width:1.5; }}
.table-wrap {{ overflow-x:auto; }}
table {{ border-collapse:collapse; font-size:.85rem; width:100%; }}
th, td {{ text-align:left; padding:3px 10px 3px 0; border-bottom:1px solid var(--grid); white-space:nowrap; }}
tr.pending {{ opacity:.55; }}
"""


def draw(final: list[dict], colors: dict[str, int]) -> str:
    seconds = [row["median_s_per_rm"] for row in final]
    lo, hi = math.log10(min(seconds) / 1.4), math.log10(max(seconds) * 1.4)  # log10 range, padded
    y_min = 10 * math.floor((min(row["wilson_low"] for row in final) * 100 - 2) / 10)
    inner_w, inner_h = WIDTH - LEFT - RIGHT, HEIGHT - TOP - BOTTOM

    def x_of(value: float) -> float:
        return LEFT + (math.log10(value) - lo) / (hi - lo) * inner_w

    def y_of(percent: float) -> float:
        return TOP + (Y_TOP - percent) / (Y_TOP - y_min) * inner_h

    parts = [
        f'<svg viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="Right share against median seconds">'
    ]
    for percent in range(y_min, 101, 10):
        y = y_of(percent)
        parts.append(
            f'<line class="grid" x1="{LEFT}" x2="{WIDTH - RIGHT}" y1="{y:.1f}" y2="{y:.1f}"/>'
        )
        parts.append(f'<text x="{LEFT - 8}" y="{y + 4:.1f}" text-anchor="end">{percent}%</text>')
    for tick in X_TICKS:
        if 10**lo <= tick <= 10**hi:
            x = x_of(tick)
            parts.append(
                f'<line class="grid" x1="{x:.1f}" x2="{x:.1f}" y1="{TOP}" y2="{HEIGHT - BOTTOM}"/>'
            )
            parts.append(
                f'<text x="{x:.1f}" y="{HEIGHT - BOTTOM + 16}" text-anchor="middle">{tick:g}</text>'
            )
    bottom = HEIGHT - BOTTOM
    parts.append(
        f'<line class="axis" x1="{LEFT}" x2="{WIDTH - RIGHT}" y1="{bottom}" y2="{bottom}"/>'
    )
    parts.append(f'<line class="axis" x1="{LEFT}" x2="{LEFT}" y1="{TOP}" y2="{bottom}"/>')
    label_x = LEFT + inner_w / 2
    parts.append(
        f'<text x="{label_x}" y="{HEIGHT - 10}" text-anchor="middle">Median seconds per RM (log scale)</text>'
    )
    y_label = f"translate(14 {TOP + inner_h / 2}) rotate(-90)"
    parts.append(
        f'<text transform="{y_label}" text-anchor="middle">Right RMs, % of 138 runs (95% Wilson)</text>'
    )

    for model, index in colors.items():
        rows = [row for row in final if row["model"] == model]
        color = f"var(--c{index})"
        path = " ".join(
            f"{x_of(r['median_s_per_rm']):.1f},{y_of(r['rate'] * 100):.1f}" for r in rows
        )
        parts.append(f'<polyline class="series" points="{path}" style="stroke:{color}"/>')
        for row in rows:
            x, y = x_of(row["median_s_per_rm"]), y_of(row["rate"] * 100)
            top, low = y_of(row["wilson_high"] * 100), y_of(row["wilson_low"] * 100)
            tip = (
                f"{model}, {row['level']}: {row['right']}/{row['n']} = {row['rate']:.1%} "
                f"(95% Wilson {row['wilson_low']:.1%} to {row['wilson_high']:.1%}), "
                f"median {row['median_s_per_rm']:g} s per RM"
            )
            dy = (
                -9 if index % 2 == 0 else 17
            )  # alternate above and below so nearby models do not overlap
            parts.append(
                f'<g style="color:{color}"><title>{escape(tip)}</title>'
                f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{top:.1f}" y2="{low:.1f}" stroke="currentColor" stroke-width="1.6"/>'
                f'<line x1="{x - 4:.1f}" x2="{x + 4:.1f}" y1="{top:.1f}" y2="{top:.1f}" stroke="currentColor" stroke-width="1.6"/>'
                f'<line x1="{x - 4:.1f}" x2="{x + 4:.1f}" y1="{low:.1f}" y2="{low:.1f}" stroke="currentColor" stroke-width="1.6"/>'
                f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="currentColor"/>'
                f'<text x="{x + 8:.1f}" y="{y + dy:.1f}">{escape(row["level"])}</text></g>'
            )
    parts.append("</svg>")
    return "\n".join(parts)


def table(rows: list[dict]) -> str:
    head = ["Model", "Level", "Right", "Share", "95% Wilson", "Median s per RM", "Final", "Timing"]
    lines = ["<tr>" + "".join(f"<th>{cell}</th>" for cell in head) + "</tr>"]
    for row in rows:
        final = "yes" if row["final"] else f"no ({row['n']} of 138 runs)"
        cells = [
            escape(row["model"]),
            row["level"],
            f"{row['right']}/{row['n']}",
            f"{row['rate']:.1%}",
            f"{row['wilson_low']:.1%} to {row['wilson_high']:.1%}",
            f"{row['median_s_per_rm']:g}",
            final,
            row["timing"],
        ]
        css = "" if row["final"] else ' class="pending"'
        lines.append(f"<tr{css}>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
    return "\n".join(lines)


def main() -> None:
    rows = json.loads((ENTRY / "data/levels.json").read_text(encoding="utf-8"))
    final = [row for row in rows if row["final"]]
    assert final, "no final row to draw"
    colors = {model: i for i, model in enumerate(dict.fromkeys(row["model"] for row in rows))}
    legend = "".join(
        f'<span><i class="swatch" style="background:var(--c{i})"></i>{escape(model)}</span>'
        for model, i in colors.items()
    )
    left_out = len(rows) - len(final)
    note = (
        f" {left_out} level(s) still running or partial are left out of the plot and listed below."
        if left_out
        else ""
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Thinking level by model</title>
<style>{CSS}</style>
</head>
<body>
<main>
<h1>Right Reward Machines against time, by thinking level</h1>
<p>One point is one model at one thinking level over 138 runs (46 task cases, 3 runs each). The bar is the 95%
Wilson interval of the share right; the position is the median wall-clock seconds per RM. The models are not
timed the same way (see the README), so read a model's own levels first.{note}</p>
<div class="legend">{legend}</div>
{draw(final, colors)}
<div class="table-wrap"><table>
{table(rows)}
</table></div>
</main>
</body>
</html>
"""
    (ENTRY / "figure.html").write_text(html, encoding="utf-8")
    print(f"figure.html: {len(final)} final rows drawn, {left_out} left out")


if __name__ == "__main__":
    main()
