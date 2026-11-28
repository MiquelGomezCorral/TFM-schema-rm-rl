"""Build data/summary.csv and index.html of the shop two-jobs entry from the data and graph files.

Run from the repository root with any Python 3, after count_farm.py, count_no_rm.py, collect.py and
render_graphs.py (reads docs/paper/shop-two-jobs/data and graphs, writes summary.csv and index.html):
    python -I docs/paper/shop-two-jobs/check/build.py
Every number on the page is computed here from the data files. The script stops when a total, an interval or the
paired test differs from the values written down when the experiment ended, or when a figure the Reading quotes
is not what the Reading says.
"""

import csv
import html
import json
import math
import re
from pathlib import Path

ENTRY = Path("docs/paper/shop-two-jobs")
DATA = ENTRY / "data"
GRAPHS = ENTRY / "graphs"
COMMIT = "48484e55"
Z = 1.959964  # 95% two-sided normal quantile
LEARNED_AT = 2
PASS_AT = 0.8
SHOPS = ("3x3", "5x5", "7x7", "grow")
SHOP_NAMES = {"3x3": "3x3", "5x5": "5x5", "7x7": "7x7", "grow": "Grown"}
METHODS = {"farm": "FARM", "no-rm": "No RM"}
TASK_PARTS = {
    "serve-falls": ("deliver", "food falls"),
    "serve-siren": ("deliver", "siren (no falls)"),
    "full-falls": ("order, cook, deliver", "food falls"),
    "full-siren": ("order, cook, deliver", "siren (no falls)"),
}
# Written down when the experiment ended: (count, total, low %, high %) of each Wilson interval, and the paired test.
EXPECTED = {
    "learned": {"farm": (8, 16, 28.0, 72.0), "no-rm": (6, 16, 18.5, 61.4)},
    "runs": {"farm": (21, 48, 30.7, 57.7), "no-rm": (15, 48, 19.9, 45.3)},
    "mcnemar": (3, 1, 0.625),  # 10/16, written down as 0.63 after rounding
}


# ======================================================================================
#                                       DATA
# ======================================================================================
def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def runs_passing(name: str) -> dict[str, int]:
    """Card -> runs passing of 3, from a counts file."""
    passes: dict[str, int] = {}
    for row in read_csv(name):
        passes[row["card"]] = passes.get(row["card"], 0) + int(row["pass"])
    return passes


def wilson(count: int, total: int) -> tuple[float, float]:
    """95% Wilson interval of a share, in percent."""
    share = count / total
    scale = 1 + Z * Z / total
    centre = (share + Z * Z / (2 * total)) / scale
    half = Z * math.sqrt(share * (1 - share) / total + Z * Z / (4 * total * total)) / scale
    return 100 * (centre - half), 100 * (centre + half)


def mcnemar_exact(only_a: int, only_b: int) -> float:
    """Two-sided exact p of a paired comparison with these two discordant counts."""
    total = only_a + only_b
    tail = sum(math.comb(total, k) for k in range(min(only_a, only_b) + 1)) / 2**total
    return min(1.0, 2 * tail)


def totals(passes: dict[str, dict[str, int]]) -> dict:
    """The learned and run totals with their intervals, and the paired test; stops on any change."""
    learned = {m: sum(p >= LEARNED_AT for p in passes[m].values()) for m in METHODS}
    runs = {m: sum(passes[m].values()) for m in METHODS}
    cards = passes["farm"].keys()
    only_farm = sum(passes["farm"][c] >= LEARNED_AT > passes["no-rm"][c] for c in cards)
    only_no_rm = sum(passes["no-rm"][c] >= LEARNED_AT > passes["farm"][c] for c in cards)
    result = {
        "learned": {m: (learned[m], len(cards), *wilson(learned[m], len(cards))) for m in METHODS},
        "runs": {m: (runs[m], 3 * len(cards), *wilson(runs[m], 3 * len(cards))) for m in METHODS},
        "mcnemar": (only_farm, only_no_rm, mcnemar_exact(only_farm, only_no_rm)),
    }
    for kind in ("learned", "runs"):
        for method in METHODS:
            got = result[kind][method]
            want = EXPECTED[kind][method]
            assert (
                got[:2] == want[:2] and round(got[2], 1) == want[2] and round(got[3], 1) == want[3]
            ), (kind, method, got, want)
    got = result["mcnemar"]
    assert got[:2] == EXPECTED["mcnemar"][:2] and math.isclose(got[2], EXPECTED["mcnemar"][2]), got
    return result


def write_summary(passes: dict[str, dict[str, int]]) -> None:
    with (DATA / "summary.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["card", "method", "runs_passing", "learned"])
        for card in passes["farm"]:
            for method in METHODS:
                runs = passes[method][card]
                writer.writerow([card, method, runs, int(runs >= LEARNED_AT)])


# ======================================================================================
#                                    READING FIGURES
# ======================================================================================
def reading_figures(
    judged: list[dict[str, str]],
    rings: list[dict[str, str]],
    passes: dict[str, dict[str, int]],
    tasks: dict,
) -> dict[str, str]:
    """Figures the Reading quotes; each claim it makes is checked against the data first."""
    siren_clause = tasks["serve-siren"]["clauses"][0]
    assert (siren_clause["template"], siren_clause["args"], siren_clause["priority"]) == (
        "Response",
        ["siren_ringing", "switch_toggled"],
        "hard",
    )
    judged_by = {(r["method"], r["card"], r["run"]): r for r in judged}
    for ring in rings:  # the clause fails exactly when a ring is left unanswered at the end
        siren_holds = float(
            judged_by[("no-rm", ring["card"], ring["run"])]["clause_pass_rates"].split()[0]
        )
        assert math.isclose(1 - float(ring["unanswered_per_episode"]), siren_holds), ring

    t2 = [r for r in rings if "-serve-siren-" in r["card"]]
    pressing = [r for r in t2 if float(r["presses_per_episode"]) > 0]
    assert len(t2) == 12 and [(r["card"], r["run"]) for r in pressing] == [
        ("shop-two-serve-siren-3x3", "2")
    ]
    exception = pressing[0]
    assert all(float(r["unanswered_per_episode"]) == 1 for r in t2 if r not in pressing)
    delivering = [r for r in t2 if r not in pressing and float(r["served_per_episode"]) >= 19]
    assert len(delivering) == 8, len(delivering)
    fines = [float(r["fine_per_episode"]) for r in delivering]
    pay = [float(r["pay_per_episode"]) for r in delivering]
    assert (min(fines), max(fines), round(min(pay)), round(max(pay))) == (-1.48, -0.075, 19, 22)
    served_3x3 = {r["served_per_episode"] for r in t2 if r["card"].endswith("-3x3")}
    farm_served = [
        float(r["mean_served_count"])
        for r in judged
        if r["card"] == "shop-two-serve-siren-3x3" and r["method"] == "farm"
    ]
    assert len(served_3x3) == 1 and (min(farm_served), max(farm_served)) == (19.78, 21.31)

    t4_learned = [
        r
        for r in rings
        if "-full-siren-" in r["card"]
        and float(judged_by[("no-rm", r["card"], r["run"])]["judged_success"]) >= PASS_AT
    ]
    at_3x3 = [r for r in t4_learned if r["card"].endswith("-3x3")]
    at_5x5 = [r for r in t4_learned if r["card"].endswith("-5x5")]
    assert (len(at_3x3), len(at_5x5)) == (3, 2)
    assert all(r["rings_per_episode"] == r["answered_per_episode"] for r in at_3x3)
    cook = {m: {s: passes[m][f"shop-two-full-siren-{s}"] for s in SHOPS} for m in METHODS}
    assert (
        cook["no-rm"]["3x3"],
        cook["no-rm"]["5x5"],
        cook["farm"]["3x3"],
        cook["farm"]["5x5"],
    ) == (3, 2, 2, 0)
    answered_3x3 = [float(r["answered_per_episode"]) for r in at_3x3]
    return {
        "no_rm_served": f"{float(next(iter(served_3x3))):g}",
        "farm_low": f"{min(farm_served):g}",
        "farm_high": f"{max(farm_served):g}",
        "exception_answered": f"{float(exception['answered_per_episode']):g}",
        "exception_rings": f"{float(exception['rings_per_episode']):g}",
        "exception_unanswered": f"{round(100 * float(exception['unanswered_per_episode']))}",
        "fine_low": f"{abs(max(fines)):g}",
        "fine_high": f"{abs(min(fines)):g}",
        "pay_low": f"{min(pay):g}",
        "pay_high": f"{max(pay):g}",
        "t4_3x3": f"{min(answered_3x3):g} to {max(answered_3x3):g}",
        "t4_5x5": " and ".join(
            f"{float(r['answered_per_episode']):g} of {float(r['rings_per_episode']):g}"
            for r in at_5x5
        ),
    }


# ======================================================================================
#                                       HTML
# ======================================================================================
CSS = """
:root {
  --bg: #fbfbfa; --surface: #ffffff; --ink: #1d232b; --muted: #5a6573; --line: #d9dee5;
  --accent: #2f5fd0; --accent-soft: #dfe8fb; --learned-bg: #e3f1e8; --learned-ink: #1d5a37;
  --code-bg: #f1f3f6; --bar-track: #e6e9ee; --bar-farm: #2f5fd0; --bar-norm: #8a6a1f;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #12151a; --surface: #181c22; --ink: #e8ebef; --muted: #a2acb9; --line: #2e353f;
    --accent: #8fb0ff; --accent-soft: #24304d; --learned-bg: #1d3a2a; --learned-ink: #9be0b8;
    --code-bg: #1f242c; --bar-track: #2a3039; --bar-farm: #8fb0ff; --bar-norm: #d9b45f;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 16px/1.55 system-ui, sans-serif; }
main { max-width: 1060px; margin: 0 auto; padding: 24px 16px 64px; }
h1 { font-size: 1.7rem; line-height: 1.25; margin: 0 0 12px; }
h2 { font-size: 1.25rem; margin: 40px 0 12px; }
h3 { font-size: 1.05rem; margin: 0 0 4px; }
p { margin: 0 0 12px; max-width: 70ch; }
code, pre, .num { font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; }
code { font-size: 0.85em; background: var(--code-bg); padding: 1px 5px; border-radius: 4px; overflow-wrap: anywhere; }
a { color: var(--accent); }
a:focus-visible, summary:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
.meta { color: var(--muted); font-size: 0.9rem; }
dl.setup { display: grid; grid-template-columns: max-content 1fr; gap: 6px 16px; margin: 0; max-width: 80ch; }
dl.setup dt { font-weight: 600; }
dl.setup dd { margin: 0; }
.stat { margin: 0 0 20px; }
.stat h3 { margin-bottom: 8px; }
.row { display: grid; grid-template-columns: 4.5rem 13rem 1fr; gap: 4px 12px; align-items: center; margin-bottom: 6px; }
.row .name { font-weight: 600; }
.row .val b { font-weight: 700; }
.row .val span { color: var(--muted); }
.track { position: relative; height: 12px; background: var(--bar-track); border-radius: 6px; }
.span { position: absolute; top: 0; bottom: 0; border-radius: 6px; opacity: 0.45; }
.dot { position: absolute; top: -3px; width: 4px; height: 18px; border-radius: 2px; }
.farm .span, .farm .dot { background: var(--bar-farm); }
.norm .span, .norm .dot { background: var(--bar-norm); }
.axis { display: grid; grid-template-columns: 4.5rem 13rem 1fr; gap: 12px; color: var(--muted); font-size: 0.8rem; }
.axis div { display: flex; justify-content: space-between; grid-column: 3; }
.wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; max-width: 640px; font-size: 0.95rem; }
th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--line); white-space: nowrap; }
thead th, tbody th[colspan] { white-space: normal; }
thead th { font-size: 0.85rem; color: var(--muted); font-weight: 600; }
tbody th[colspan] { background: var(--code-bg); font-size: 0.9rem; }
td.learned { background: var(--learned-bg); color: var(--learned-ink); }
td .num { font-weight: 700; }
.tasks { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 490px), 490px)); justify-content: start; gap: 24px; align-items: start; }
article.task { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 16px; min-width: 0; }
.label { margin: 14px 0 4px; font-size: 0.8rem; font-weight: 600; color: var(--muted); text-transform: none; }
blockquote { margin: 0; padding-left: 12px; border-left: 3px solid var(--line); }
ul.clauses { margin: 0; padding: 0; list-style: none; }
ul.clauses li { margin: 0 0 8px; }
ul.clauses code { display: inline-block; max-width: 100%; }
iframe { width: 100%; height: 480px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); }
details { margin-top: 10px; }
summary { cursor: pointer; font-weight: 600; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; margin: 8px 0 0; padding: 12px; max-height: 360px; overflow: auto; background: var(--code-bg); border-radius: 6px; font-size: 0.8rem; line-height: 1.45; }
ul.read { padding-left: 20px; max-width: 75ch; }
ul.read li { margin-bottom: 12px; }
@media (max-width: 600px) {
  th, td { padding: 6px 6px; }
  .row { grid-template-columns: 4.5rem 1fr; }
  .row .track { grid-column: 1 / -1; }
  .axis { grid-template-columns: 1fr; }
  .axis div { grid-column: 1; }
  dl.setup { grid-template-columns: 1fr; gap: 0; }
  dl.setup dd { margin-bottom: 8px; }
}
"""


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def stat_block(title: str, rows: dict[str, tuple]) -> str:
    """One statistic for both methods: the count, its interval as text and as a bar."""
    lines = [f'<div class="stat"><h3>{esc(title)}</h3>']
    for method, (count, total, low, high) in rows.items():
        style = "farm" if method == "farm" else "norm"
        lines.append(
            f'<div class="row {style}"><span class="name">{METHODS[method]}</span>'
            f'<span class="val"><b>{count} of {total}</b> <span>({low:.1f}&ndash;{high:.1f}%)</span></span>'
            f'<div class="track" aria-hidden="true"><div class="span" style="left:{low:.2f}%;width:{high - low:.2f}%"></div>'
            f'<div class="dot" style="left:calc({100 * count / total:.2f}% - 2px)"></div></div></div>'
        )
    lines.append(
        '<div class="axis" aria-hidden="true"><div><span>0%</span><span>50%</span><span>100%</span></div></div></div>'
    )
    return "\n".join(lines)


def table_html(tasks: dict, passes: dict[str, dict[str, int]]) -> str:
    """The 16 cards by 2 methods, grouped by task."""
    head = (
        "<thead><tr><th>Shop</th><th>FARM</th><th>No RM</th><th>Learned only by</th></tr></thead>"
    )
    body = []
    for key, task in tasks.items():
        body.append(
            f'<tr><th colspan="4" scope="colgroup">{esc(task["label"])} · cards <code>shop-two-{key}-*</code>'
            f" · RM <code>{esc(task['bundle'])}</code></th></tr>"
        )
        for shop in SHOPS:
            card = f"shop-two-{key}-{shop}"
            cells, learned = [], {}
            for method in METHODS:
                runs = passes[method][card]
                learned[method] = runs >= LEARNED_AT
                word = "learned" if learned[method] else "no"
                cells.append(
                    f'<td class="{"learned" if learned[method] else ""}"><span class="num">{runs}/3</span> {word}</td>'
                )
            only = (
                "FARM"
                if learned["farm"] > learned["no-rm"]
                else "No RM"
                if learned["no-rm"] > learned["farm"]
                else ""
            )
            body.append(
                f'<tr><th scope="row">{SHOP_NAMES[shop]}</th>{cells[0]}{cells[1]}<td>{only}</td></tr>'
            )
    return f'<div class="wrap"><table>{head}<tbody>{"".join(body)}</tbody></table></div>'


def rm_facts(text: str) -> tuple[int, int]:
    """Number of states and of transitions of an RM text."""
    states = len(re.search(r"^STATES: (.*)$", text, re.MULTILINE).group(1).split(","))
    transitions = (
        text.split("TRANSITION_FUNCTION:")[1].split("REWARD_FUNCTION:")[0].strip().count("\n") + 1
    )
    return states, transitions


def task_card(key: str, task: dict) -> str:
    bundle = task["bundle"]
    text = (GRAPHS / f"{bundle}.rm").read_text(encoding="utf-8")
    states, transitions = rm_facts(text)
    job, hard = TASK_PARTS[key]
    clauses = "".join(
        f"<li><code>{esc(c['template'])}({esc(', '.join(c['args']))})</code> {esc(c['priority'])}<br>"
        f"<code>{esc(c['ltlf'])}</code></li>"
        for c in task["clauses"]
    )
    return f"""<article class="task" id="{key}">
<h3>{esc(task["label"])}</h3>
<p class="meta">Serving job: {job}. Hard part: {hard}. FARM's RM comes from bundle <code>{esc(bundle)}</code>: {states} states, {transitions} transitions.</p>
<p class="label">Task, in natural language</p>
<blockquote>{esc(task["task"])}</blockquote>
<p class="label">LTL clauses (LTLf)</p>
<ul class="clauses">{clauses}</ul>
<p class="label">RM, drawn by <code>render-rm --html</code> (drag a state, click an edge for its cases, Ctrl + scroll to zoom)</p>
<iframe id="{key}-graph" src="graphs/{esc(bundle)}.html" title="RM graph of {esc(bundle)}" sandbox="allow-scripts"></iframe>
<p class="meta"><a href="graphs/{esc(bundle)}.html">Open the graph alone</a></p>
<details><summary>RM text</summary><pre id="{key}-text">{esc(text)}</pre></details>
</article>"""


def reading_html(figures: dict[str, str], result: dict, passes: dict[str, dict[str, int]]) -> str:
    only_farm, only_no_rm, p_value = result["mcnemar"]
    cook = {m: [passes[m][f"shop-two-full-siren-{s}"] for s in ("3x3", "5x5")] for m in METHODS}
    return f"""<ul class="read">
<li><b>No RM delivers as much as FARM on T2, but 11 of its 12 runs never press the switch.</b> At 3x3 no RM serves {figures["no_rm_served"]} orders per episode in
all 3 runs, against {figures["farm_low"]} to {figures["farm_high"]} for FARM's 3 runs. Of the 12 no-RM runs of T2, 11 never press the switch in any of their 100
judged episodes. The exception, 3x3 run 2, answers {figures["exception_answered"]} of {figures["exception_rings"]} rings per episode but leaves one unanswered at the end in
{figures["exception_unanswered"]}% of its episodes.</li>
<li><b>The siren clause has no deadline.</b> In T2 it is <code>Response(siren_ringing, switch_toggled)</code>, hard. It fails only when a ring is still
unanswered at the end of the episode, so a run that never presses fails in every episode.</li>
<li><b>The environment's reward barely fines it.</b> It fines a ring only when a waiting client hears it past a step limit
(<code>app/src/arm_fm/shop.py:506-520</code>, &minus;0.5 each time). Over the 8 no-RM runs of T2 that never press and still deliver, the fines average
&minus;{figures["fine_low"]} to &minus;{figures["fine_high"]} per judged episode, against +{figures["pay_low"]} to +{figures["pay_high"]} for serving.</li>
<li><b>In cook + siren, the no-RM runs that learn it turn off nearly every ring.</b> At 3x3 all three answer {figures["t4_3x3"]} rings per episode, every
ring they get. At 5x5 the two that learn it answer {figures["t4_5x5"]}. No RM learns T4 at 3x3 ({cook["no-rm"][0]} of 3 runs) and 5x5 ({cook["no-rm"][1]} of 3);
FARM learns it at 3x3 ({cook["farm"][0]} of 3) and not at 5x5.</li>
<li><b>The difference between the methods is small.</b> {only_farm} cards are learned by FARM only and {only_no_rm} by no RM only (McNemar exact p = {p_value:.3f}), and the
intervals above overlap.</li>
</ul>
<p class="meta">A ring starts when the siren turns on; it is answered when the switch is pressed while it rings. Counts are means over the 100 judged
episodes of each run, read from the agent's traces (<code>data/rings.csv</code>, <code>check/traces.py</code>).</p>"""


def page(
    tasks: dict, passes: dict[str, dict[str, int]], result: dict, figures: dict[str, str]
) -> str:
    only_farm, only_no_rm, p_value = result["mcnemar"]
    setup = "".join(
        f"<dt>{esc(k)}</dt><dd>{v}</dd>"
        for k, v in {
            "Tasks": "T1 serve + falls, T2 serve + siren, T3 full serve + falls, T4 full serve + siren. Each pairs a serving job (deliver, or order, cook and deliver) with one hard part: food falls, or the siren rings.",
            "Shops": "3x3, 5x5, 7x7 and a grown shop that goes through 3x3, 5x5 and 7x7. A task at a shop size is a card, so there are 16.",
            "Curriculum": "At each fixed size the agent first plays the task with its hard part off, then on. The grown shop plays 3x3 off, 3x3, 5x5 and 7x7. The judge plays the final stage (the grown shop at 7x7).",
            "Methods": "FARM trains on its RM's reward alone; no RM trains on the environment's own reward. PPO, 5M steps per run, 3 runs per card.",
            "Pass and learned": "A run passes at a judged success of 0.8 or more. A card is learned when 2 of its 3 runs pass.",
        }.items()
    )
    stats = stat_block("Learned cards", result["learned"]) + stat_block(
        "Runs passing", result["runs"]
    )
    cards = "".join(task_card(key, task) for key, task in tasks.items())
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Shop, two jobs at once</title>
<style>{CSS}</style>
</head>
<body>
<main>
<h1>Shop, two jobs at once: FARM against no RM</h1>
<p>Four tasks, each a serving job plus one hard part, at four shop sizes: 16 cards, each trained 3 times with FARM's RM and 3 times with no RM.
FARM learns {result["learned"]["farm"][0]} of the 16 cards and no RM learns {result["learned"]["no-rm"][0]}. The difference is small and the intervals overlap.</p>
<p class="meta">Runs of 2026-11-26 and 2026-11-27, commit <code>{COMMIT}</code>. Data and rerun steps in <code>README.md</code>.</p>

<h2>Setup</h2>
<dl class="setup">{setup}</dl>

<h2 id="result">Result</h2>
<p class="meta">Bars show the 95% Wilson interval; the mark is the observed share.</p>
{stats}
<p>Paired on the 16 cards: {only_farm} are learned by FARM only and {only_no_rm} by no RM only, so McNemar exact p = {p_value:.3f}.</p>

<h2 id="table">The 16 cards, by method</h2>
<p class="meta">Runs passing out of 3, then whether the card is learned. Source: <code>data/summary.csv</code>.</p>
{table_html(tasks, passes)}

<h2 id="tasks">The four tasks</h2>
<div class="tasks">{cards}</div>

<h2 id="reading">Reading</h2>
{reading_html(figures, result, passes)}

<h2>Files</h2>
<p><a href="data/summary.csv">summary.csv</a> (one row per card and method), <a href="data/counts-farm.csv">counts-farm.csv</a> and
<a href="data/counts-no-rm.csv">counts-no-rm.csv</a> (one row per run), <a href="data/judged.csv">judged.csv</a> (served orders, the environment's reward and
the clause pass rates of each run), <a href="data/rings.csv">rings.csv</a> (rings, presses, fines and pay of the no-RM siren runs, from their traces),
<a href="data/tasks.json">tasks.json</a>, and the RM files in <code>graphs/</code>.</p>
</main>
</body>
</html>
"""


def main() -> None:
    passes = {"farm": runs_passing("counts-farm.csv"), "no-rm": runs_passing("counts-no-rm.csv")}
    assert len(passes["farm"]) == len(passes["no-rm"]) == 16
    result = totals(passes)
    write_summary(passes)
    tasks = json.loads((DATA / "tasks.json").read_text(encoding="utf-8"))
    figures = reading_figures(read_csv("judged.csv"), read_csv("rings.csv"), passes, tasks)
    (ENTRY / "index.html").write_text(page(tasks, passes, result, figures), encoding="utf-8")
    for kind in ("learned", "runs"):
        for method in METHODS:
            count, total, low, high = result[kind][method]
            print(f"{kind} {method}: {count} of {total} ({low:.1f}-{high:.1f}%)")
    print(
        f"McNemar exact: {result['mcnemar'][0]} against {result['mcnemar'][1]}, p = {result['mcnemar'][2]:.3f}"
    )
    print(
        "OK: totals, intervals and paired test equal the written-down values; wrote summary.csv and index.html"
    )


if __name__ == "__main__":
    main()
