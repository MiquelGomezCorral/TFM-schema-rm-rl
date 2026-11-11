"""Build data.json of the page from results.json (written by p2_sim.py); `fill.py` of the artifacts skill renders it.

Run from the repository root, inside RM_RL_env:

    PYTHONPATH=app python -W ignore docs/paper/rule-only-progress/check/build_page.py
"""

import json
from pathlib import Path

from src.utils import Example, pretty_ltlf, result_card

HERE = Path(__file__).resolve().parent
ENTRY = HERE.parent
GAMMA = 0.99
SECTIONS = [
    ("Existence", "has_key"),
    ("ExistenceTwo", "door_open"),
    ("RespondedExistence", "power_cut"),
    ("Response", "box_fell"),
    ("ChainResponse", "alarm_rings"),
]
ENVIRONMENT_NOTE = (
    "The trigger costs 0.1 until the promise is kept, so the examples use events the environment causes (a box falls, an alarm "
    "rings, the power goes out) and the agent only recovers. When the agent controls the trigger, the 0.1 comes back when it keeps "
    "the promise, so the total is the same (apart from discounting)."
)


def fmt(rewards: list[float]) -> str:
    return "`" + ", ".join(f"{r:g}" for r in rewards) + "`"


def stat_line(row: dict, key: str) -> str:
    stats = row[f"{key}_stats"]
    return " · ".join(
        [
            f"{stats['states']} states",
            "final" if row["has_final"] else "no final",
            "well" if row["well"] else "no well",
            "rewards " + ", ".join(f"{r:g}" for r in stats["rewards"]),
        ]
    )


def entries(rows: list[dict]) -> list[dict]:
    """The rows of one clause, with hard and soft merged when both compile to the same machines."""
    merged = []
    has_off = any(not row["recurrent"] for row in rows)
    for row in sorted(rows, key=lambda r: (r["priority"] != "hard", not r["recurrent"])):
        twin = next(
            (
                e
                for e in merged
                if e["rows"][0]["today"] == row["today"] and e["rows"][0]["p2"] == row["p2"]
            ),
            None,
        )
        if twin:
            assert twin["rows"][0]["traces"] == row["traces"]
            twin["rows"].append(row)
        else:
            merged.append({"rows": [row]})
    for entry in merged:
        row = entry["rows"][0]
        both = len(entry["rows"]) > 1
        if both:
            entry["title"] = "Hard and soft: identical machines"
        else:
            entry["title"] = row["priority"].capitalize() + (
                f", recurrent soft rules {'on' if row['recurrent'] else 'off'}"
                if has_off and row["priority"] == "soft"
                else ""
            )
        entry["task"] = (
            " / ".join(f"{r['priority']}: {r['task']}" for r in entry["rows"])
            if both
            else row["task"]
        )
        entry["label"] = "hard / soft" if both else row["priority"]
    return merged


def cards(row: dict, entry: dict) -> list[dict]:
    clause = [(row["pattern"], row["propositions"], entry["label"])]
    soft = next((r for r in entry["rows"] if r["priority"] == "soft"), None)
    out = []
    for key, name in (("today", "Today"), ("p2", "With P2")):
        example = Example(
            entry["task"],
            clause,
            row[key],
            illustrative=True,
            inert_soft=bool(soft and soft["inert_soft"]),
        )
        caption = f"**{name}** · {stat_line(row, key)}" + (
            "" if len(entry["rows"]) > 1 else f"\nTask (illustrative): *{entry['task']}*"
        )
        out.append(
            result_card(
                f"graphs/{row['slug']}.{key}.html", caption, example, alt=f"{row['name']} {name}"
            )
        )
    return out


def trace_table(entry: dict) -> dict:
    rows = []
    for t in entry["rows"][0]["traces"]:
        changed = t["p2"]["total"] != t["today"]["total"]
        rows.append(
            [
                f"`{t['trace']}`",
                t["case"],
                fmt(t["today"]["rewards"]),
                f"{t['today']['total']:g}",
                fmt(t["p2"]["rewards"]),
                {"text": f"{t['p2']['total']:g}", "tone": "info"}
                if changed
                else f"{t['p2']['total']:g}",
                t["today"]["ended"]
                if t["today"]["ended"] != "well"
                else {"text": "well", "tone": "bad"},
            ]
        )
    return {
        "type": "table",
        "heading": f"Traces: {entry['title'].lower()}",
        "columns": [
            "Trace",
            "Case",
            "Today: reward per step",
            "Today: total",
            "P2: reward per step",
            "P2: total",
            "Clause at the end",
        ],
        "rows": rows,
    }


def section(pattern_rows: list[dict], sid: str) -> dict:
    first = pattern_rows[0]
    props = first["propositions"]
    letters = (
        f"`x` is `{props[0]}`" if len(props) == 1 else f"`x` is `{props[0]}`, `y` is `{props[-1]}`"
    )
    ents = entries(pattern_rows)
    clause = f"{first['pattern']}({', '.join(props)})"
    hard_soft = "soft" if all(r["priority"] == "soft" for r in pattern_rows) else "hard and soft"
    tasks = " ".join(
        dict.fromkeys(
            f"*{e['task'] if len(e['rows']) > 1 else e['title'].split(',')[0].lower() + ': ' + e['task']}*"
            for e in ents
        )
    )
    return {
        "title": f"{clause}: {hard_soft}",
        "id": sid,
        "intro": f"Clause `{clause}`, LTLf `{pretty_ltlf(first['ltlf'])}`. Illustrative tasks, hand-written: {tasks}",
        "blocks": [
            {
                "type": "gallery",
                "heading": "The Reward Machine today and with P2",
                "width": 490,
                "groups": [{"title": e["title"], "items": cards(e["rows"][0], e)} for e in ents],
            },
            {
                "type": "text",
                "heading": "Traces walked on both machines",
                "text": f"{letters}; `-` is a step where neither holds. Each trace runs through the compiled machine today and with P2. A blue total is one P2 changed.",
            },
            *[trace_table(e) for e in ents],
        ],
    }


def glance(rows: list[dict], count: int) -> dict:
    table = []
    for row in rows:
        suffix = "" if row["recurrent"] or row["priority"] == "hard" else ", recurrent off"
        label = f"`{row['pattern']}({', '.join(row['propositions'])})` {row['priority']}{suffix}"
        if row["changed"]:
            table.append(
                [
                    f"[{label}](#{row['pattern'].lower()}-templates)",
                    {"text": "yes", "tone": "info"},
                    row["reason"],
                ]
            )
        else:
            table.append([label, {"text": "no", "tone": "muted"}, row["reason"]])
    return {
        "title": f"All {count} machines at a glance",
        "id": "glance",
        "intro": "The eight IBM templates alone, hard and soft. Soft rows use the default, recurrent soft rules on; where the setting changes today's machine, the soft row with it off follows.",
        "blocks": [
            {"type": "table", "columns": ["Machine", "Changes with P2", "Why"], "rows": table}
        ],
    }


def open_gaps() -> dict:
    late = round(0.1 * (1 - GAMMA**50), 3)
    gaps = [
        "**A promise left open costs 0.1.** In Response, RespondedExistence and ChainResponse, the kept trace totals 0 and the trace left open at the end totals -0.1 (`x - -`, `x -`, `- x`). Today both total 0. The box that stays on the floor until the episode ends costs 0.1, the same as a power cut that never gets its generator.",
        f"**Fixing late costs nothing.** `x y` and `x - - y` both total 0. Only the learner's discount prices the wait: a fix 50 steps late loses about {late:g} (0.1 \u00d7 (1 \u2212 {GAMMA}^50), computed, not measured).",
        "**A break the compiler already prices keeps its price.** Soft ChainResponse: broken is -0.5 today and -0.5 with P2 (-0.1, -0.4, 0). Hard ChainResponse: broken is -1 today and -1.1 with P2; the extra 0.1 is the step where the alarm rings.",
        "**Soft goals get 0.1, nothing more.** Soft Existence done = +0.1, done twice = +0.1, not done = 0. Soft ExistenceTwo: one of two = +0.1, both = +0.2, a third time = 0. The +1 for finishing needs a hard goal.",
    ]
    surprises = [
        '**Hard and soft are the same machine for Response and RespondedExistence.** Both can always be repaired, so no state is ever violated; today and with P2 the two compile to identical text. "You must" and "preferably" pay the same.',
        "**The trigger step is charged.** In Response, `x` costs -0.1 the moment it happens, before anything is wrong. The kept trace nets 0 only because the answer pays it back; a run that never triggers the rule also totals 0. This is why the examples use events the environment causes: a trigger the agent controls would look like a cost to avoid.",
        "**Breaking a rule pays the 0.1 too.** A violated state counts as a target, like a kept one. In soft ChainResponse the break edge reads -0.4: the -0.5 charge plus +0.1 for getting there.",
        "**Absence, Precedence and NotCoExistence are untouched,** so after P2 two kinds of rule sit on different scales: rules that wait are priced in tenths, rules that forbid keep -0.5 or the well.",
    ]
    return {
        "title": "What P2 leaves open",
        "id": "open",
        "intro": "From the traces above. P2 adds a signal to rule-only tasks, but a small one.",
        "blocks": [
            {
                "type": "list",
                "heading": "Where kept and broken episodes still end close",
                "items": gaps,
            },
            {"type": "list", "heading": "Surprises", "items": surprises},
        ],
    }


def main() -> None:
    results = json.loads((HERE / "results.json").read_text(encoding="utf-8"))
    rows = results["rows"]
    shown = [r for r in rows if r["recurrent"] or r["priority"] == "hard"]
    changed = [r for r in rows if r["changed"]]
    count, changed_count = len(shown), sum(r["changed"] for r in shown)
    sections = [
        {
            "title": "What P2 changes",
            "id": "intro",
            "blocks": [
                {
                    "type": "callout",
                    "tone": "info",
                    "title": "P2 in plain words",
                    "text": "A task made only of rules has no goal to reach, so it has no final state and today's progress reward measures toward nothing: it pays 0. P2 gives it something to measure toward, the states where no clause is still waiting on something (each clause is kept or already broken). Each step that gets closer pays +0.1, each step that moves away costs 0.1.",
                },
                {
                    "type": "list",
                    "items": [
                        f"**{changed_count} of {count} machines change.** Soft Existence and ExistenceTwo; RespondedExistence, Response and ChainResponse, hard and soft.",
                        f"**{count - changed_count} stay the same.** Hard Existence and ExistenceTwo have a final state; Absence, Precedence and NotCoExistence never leave a clause waiting.",
                        f"**The examples.** {ENVIRONMENT_NOTE}",
                        "**The check passed.** No P2 machine has a positive reward cycle (`_has_positive_cycle`), and the hard Existence and ExistenceTwo machines are byte-identical. Each renamed example is the same machine as the one it replaces.",
                    ],
                },
                {
                    "type": "details",
                    "items": [
                        {
                            "title": "P2 in four steps (technical)",
                            "text": (
                                "Only when the task has no final state (no hard goal); otherwise nothing changes.\n\n"
                                "1. Targets are the product states where no clause is `PENDING`: each clause is `SATISFIED` or `VIOLATED`.\n"
                                "2. For measuring only, drop the targets' outgoing edges and the edges into the well. Without this, Response's `u0 -> u1 -> u0` loop collapses to one node and pays nothing.\n"
                                "3. `remaining(u)` is the longest number of steps to a target on that graph, cycles collapsed; 0 at targets, and 0 where no target is reachable.\n"
                                "4. Every real edge, targets' edges included and well edges excluded, pays `0.1 \u00d7 (remaining(source) \u2212 remaining(destination))` on top of today's price.\n\n"
                                "Run as a runtime patch of `_price_edges` in `check/p2_sim.py`; no tracked code file is edited."
                            ),
                        }
                    ],
                },
            ],
        },
        glance(shown, count),
        *[
            section(
                [r for r in changed if r["pattern"] == pattern and r["propositions"][0] == first],
                f"{pattern.lower()}-templates",
            )
            for pattern, first in SECTIONS
        ],
        open_gaps(),
    ]
    data = {
        "title": "Rule-only progress, simulated",
        "eyebrow": "rule-only rewards · proposal P2 · no code changed",
        "subtitle": "What the Reward Machines and their rewards would become if a task with no final state paid progress toward the states where every clause is fine. Simulated on the clauses alone: no model, no training.",
        "sections": sections,
    }
    (ENTRY / "data.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(ENTRY / "data.json")


if __name__ == "__main__":
    main()
