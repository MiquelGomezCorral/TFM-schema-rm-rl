"""Build a results page (the artifacts skill's ``data.json``) from real Reward Machine runs.

Every shown result carries its natural-language task, its IBM clauses with their LTLf and its
Reward Machine (``src.utils.presentation`` owns that format). This script adds nothing to the
real clauses, LTLf or machine, so no future result needs a new page builder. Nothing calls a
language model.

Usage, from the repository root inside ``RM_RL_env``; a run directory is what the CLI wrote
with ``--trace-dir`` (``outputs/traces/<name>.json`` under it):

    PAGE=$(python3 ~/.claude/skills/artifacts/scripts/hub.py dir results-demo)
    PYTHONPATH=app python -W ignore app/scripts/present_results.py RUN_DIR [RUN_DIR ...] --out "$PAGE"
    python3 ~/.claude/skills/artifacts/scripts/fill.py "$PAGE/data.json" "$PAGE/index.html"
    python3 ~/.claude/skills/artifacts/scripts/hub.py publish "$PAGE" --title "..." --desc "..." --by "..."

A run without a task is shown with ``--illustrative-task RUN=TEXT``; the page marks that task as
illustrative and hand-written.
"""

import argparse
import json
from pathlib import Path

from src.compiler import paper_to_structure, parse_paper_reward_machine
from src.utils import (
    Example,
    dfa_items,
    load_step_trace,
    pipeline_rows,
    render_elements_html,
    result_card,
    reward_machine_to_elements,
)

NOTHING_ADDED = (
    "Every section shows one accepted task of a real run, exactly as the compiler recorded it. "
    "No clause, LTLf formula or Reward Machine state was added, renamed or trimmed for this page."
)
THREE_THINGS = [
    "**Every result shows the three things:** the natural-language task, the IBM clauses with their LTLf, and the Reward Machine.",
    "**LTLf is shown with spaces for reading** (`(F has_key)`); IBM writes it without them (`(Fhas_key)`), and that raw string is what MONA gets. The fold-out under each graph shows both.",
    "**An illustrative task** is hand-written for clauses that came from no real task, and is marked as such.",
    "**Each graph is the live component:** drag a state, hover an edge for its cases.",
]


# ======================================================================================
#                                      READ A RUN
# ======================================================================================


def read_run(run_dir: Path) -> list[dict]:
    """Return one dict per task of the run's trace: task, attempt, clauses, LTLf, DFAs, RM text."""
    trace = next(iter(sorted((run_dir / "outputs" / "traces").glob("*.json"))), None)
    if trace is None:
        raise SystemExit(f"{run_dir}: no outputs/traces/*.json (run with --trace-dir)")

    tasks = []
    for entry in load_step_trace(trace.read_text(encoding="utf-8")):
        steps = entry["steps"]
        clauses = json.loads(steps["generate"])
        clauses = clauses["clauses"] if isinstance(clauses, dict) else clauses
        tasks.append(
            {
                "task": entry["task"],
                "attempt": entry["attempt"],
                "clauses": clauses,
                "ltlf": [item["formula"] for item in json.loads(steps["ltlf"])],
                "dfas": steps["dfa"].split("\n\n"),
                "rm_text": steps["reward_machine"],
            }
        )
    return tasks


# ======================================================================================
#                                      BUILD THE PAGE
# ======================================================================================


def run_section(name: str, task: dict, illustrative_task: str | None, page: Path) -> dict:
    """Return the page section of one task: its task, pipeline table, DFAs, graph and fold-out."""
    clauses = [
        (c["pattern"], c["propositions"], c["priority"], formula)
        for c, formula in zip(task["clauses"], task["ltlf"], strict=True)
    ]
    text = illustrative_task or task["task"]
    example = Example(text, clauses, task["rm_text"], illustrative=illustrative_task is not None)

    structure = paper_to_structure(parse_paper_reward_machine(task["rm_text"]))
    graph = page / "graphs" / f"{name}.html"
    elements = reward_machine_to_elements(structure)
    graph.write_text(render_elements_html(elements, theme="auto"), encoding="utf-8")

    final = "final" if structure.final_state is not None else "no final"
    well = "well" if structure.rejecting_states else "no well"
    caption = f"**{name}** · {len(structure.states)} states · {final} · {well}"
    dfas = [
        (p, props, raw, dfa) for (p, props, _, raw), dfa in zip(clauses, task["dfas"], strict=True)
    ]
    return {
        "title": name,
        "id": name,
        "intro": f"{'Task (illustrative, hand-written)' if example.illustrative else 'Task'}: {text}",
        "blocks": [
            {
                "type": "table",
                "heading": "What goes into the pipeline",
                "columns": ["Version", "Task", "IBM clauses", "LTLf"],
                "rows": pipeline_rows([(f"attempt {task['attempt']}", text, clauses)]),
            },
            {
                "type": "details",
                "heading": f"One MONA DFA per clause ({len(clauses)} in this proposal); the reward layer works on their product",
                "items": dfa_items(dfas),
            },
            {
                "type": "gallery",
                "heading": "What comes out: the Reward Machine",
                "width": 490,
                "items": [result_card(f"graphs/{name}.html", caption, example, alt=name)],
            },
        ],
    }


def intro_section(illustrative: bool) -> dict:
    """Return the top section: the three-things rule and the "nothing added" decision."""
    items = (
        THREE_THINGS
        if illustrative
        else [item for item in THREE_THINGS if "illustrative" not in item]
    )
    return {
        "title": "How to read this",
        "id": "intro",
        "blocks": [
            {
                "type": "callout",
                "tone": "ok",
                "title": "Decision: nothing added",
                "text": NOTHING_ADDED,
            },
            {"type": "list", "items": items},
        ],
    }


def build_page(
    run_dirs: list[Path], illustrative_tasks: dict[str, str], page: Path, title: str
) -> dict:
    """Write the graphs under ``page/graphs`` and return the page data."""
    (page / "graphs").mkdir(parents=True, exist_ok=True)
    sections = []
    for run_dir in run_dirs:
        tasks = read_run(run_dir)
        for index, task in enumerate(tasks, start=1):
            name = run_dir.name if len(tasks) == 1 else f"{run_dir.name}-task{index}"
            sections.append(run_section(name, task, illustrative_tasks.get(run_dir.name), page))
    return {
        "title": title,
        "eyebrow": "Reward Machine compiler · real runs",
        "subtitle": f"{len(sections)} accepted task(s): the task, the IBM clauses with their LTLf, the DFAs and the Reward Machine, as the compiler wrote them.",
        "sections": [intro_section(bool(illustrative_tasks)), *sections],
    }


# ======================================================================================
#                                          CLI
# ======================================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build a results page from run directories.")
    parser.add_argument(
        "runs", nargs="+", type=Path, help="Run directories with outputs/traces/*.json"
    )
    parser.add_argument("--out", type=Path, required=True, help="Page folder (hub.py dir <name>)")
    parser.add_argument("--title", default="Results: task, clauses, LTLf and Reward Machine")
    parser.add_argument("--illustrative-task", action="append", default=[], metavar="RUN=TEXT")
    args = parser.parse_args()

    illustrative = dict(item.split("=", 1) for item in args.illustrative_task)
    data = build_page(args.runs, illustrative, args.out, args.title)
    target = args.out / "data.json"
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(target)
