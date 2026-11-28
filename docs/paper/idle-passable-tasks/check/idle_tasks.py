"""Which no-goal tasks of the benchmark an idle agent passes (no training, no model call).

The idle agent only waits (``_IDLE_STEPS`` of ``app/src/benchmark/plan_check.py``). Its episodes
are judged as the judge judges a trained agent's (``JudgeRecorder`` in ``app/scripts/test_rl.py``):
``judge_trace`` on the card's ``expect`` clauses over the reference labels of the run, on the
judge's 100 test seeds
(``eval_seed_base`` 2,000,000 + i). A task passes when 0.8 or more of those episodes are judged
successful, the bar a training run must clear. A task with a goal is never passed idle and is not
judged. A task with no hard clause (soft-only) has no pass or fail, so its idle soft figures are
reported instead, as the results builder's ``IDLE_EVERY`` does; those 8 rows are checked against it.

Tasks are the cards of the group task files at ``COMMIT``, kept verbatim in
``evidence/tasks-<commit>/`` (made with ``git show <commit>:experiments/benchmark/<group>/tasks.json``);
the repository's current task files are compared with them. Trained: the 60 rows of
``records.learned_rows()``. Writes ``evidence/idle.json`` and ``evidence/idle.md``.

Run from the repository root:
env CC_ROOT=$PWD OMP_NUM_THREADS=4
PYTHONPATH=app:.git/agent-memory/artifacts/final-results:docs/paper/level-benchmark-freeze/check:docs/paper/results-figures
nice -n 19 python -P -W ignore docs/paper/idle-passable-tasks/check/idle_tasks.py
"""

import contextlib
import io
import json
import math
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from statistics import fmean

from scripts.test_rl import _label_changes
from src.benchmark import judge_trace
from src.benchmark.cards import Card
from src.benchmark.declare_judge import HARD, SOFT
from src.benchmark.plan_check import _IDLE_STEPS
from src.benchmark.plans import run_plan

with contextlib.redirect_stdout(io.StringIO()):  # the results builder prints its report on import
    import records

ENTRY = Path(__file__).resolve().parents[1]
EVIDENCE = ENTRY / "evidence"
BENCH = ENTRY.parents[2] / "experiments" / "benchmark"
COMMIT = "9841d4b3"  # the task files the final run was cut from
FROZEN = EVIDENCE / f"tasks-{COMMIT}"  # verbatim `git show <commit>:<group>/tasks.json` copies
GROUPS = ("base", "pilot", "complex", "templates", "box-carry", "forcing", "forced-start", "shop")
SEED_BASE, EPISODES = 2_000_000, 100  # the judge's test seeds: eval_seed_base + i, 100 episodes
BAR = 0.8  # a run passes when 0.8 or more of its judged episodes succeed
WORKERS = 4
# The 14 cards the task notes mark as passed by an idle agent.
NOTES_MARKED = (
    "cx-rules-only",
    "tpl-absence-1-nogoal",
    "tpl-absence-2-nogoal",
    "tpl-absence-3-nogoal",
    "tpl-response-1-nogoal",
    "tpl-response-3-nogoal",
    "tpl-precedence-1-nogoal",
    "tpl-precedence-2-nogoal",
    "tpl-precedence-3-nogoal",
    "tpl-responded-existence-1-nogoal",
    "tpl-responded-existence-3-nogoal",
    "tpl-not-co-existence-1-nogoal",
    "tpl-not-co-existence-2-nogoal",
    "tpl-not-co-existence-3-nogoal",
)


# ======================================================================================
#                                       CARDS
# ======================================================================================


def cards_of(tasks_file: Path) -> list[dict]:
    """The card dicts of one group task file."""
    return json.loads(tasks_file.read_text(encoding="utf-8"))["cards"]


def rules_of(card: Card) -> str:
    """``hard``, ``soft-only``, ``hard+soft`` or ``no clauses``, from the card's ``expect``."""
    priorities = {clause[2] for clause in card.expect}
    if priorities == {HARD}:
        return "hard"
    if priorities == {SOFT}:
        return "soft-only"
    return "hard+soft" if priorities else "no clauses"


def current_changes() -> tuple[list[str], dict[str, int]]:
    """The frozen cards that differ or are gone in the repository's task files, and the cards added."""
    changed, added = [], {}
    for group in GROUPS:
        frozen = {card["id"]: card for card in cards_of(FROZEN / f"{group}.json")}
        current = {card["id"]: card for card in cards_of(BENCH / group / "tasks.json")}
        changed += [f"{group}/{name}" for name, card in frozen.items() if current.get(name) != card]
        if new := set(current) - set(frozen):
            added[group] = len(new)
    return changed, added


# ======================================================================================
#                                     IDLE AGENT
# ======================================================================================


def idle_row(card_dict: dict) -> dict:
    """The idle plan's judged episodes on one card (runs in a worker process).

    Same calls as ``JudgeRecorder._soft_only_summary``, with the verdict's ``success`` kept. The
    plan is the plan check's wait, which runs to the end of the env's episode like an agent's
    judged episode; the judge's ``SOFT_ONLY_IDLE_PLAN`` stops at 1000 steps, 80 short of
    KeyCorridorS6R3, and is identical on the 8 soft-only cards (their episodes last 200 to 300).
    """
    card = Card.from_dict(card_dict)
    assert card.env["layout"] == "procedural", f"{card.id}: a fixed layout resets on its own seed"
    episodes = []
    for seed in range(SEED_BASE, SEED_BASE + EPISODES):
        rollout = run_plan(card.env, _IDLE_STEPS, seed)
        verdict = judge_trace(card.expect, rollout.labels).to_dict()
        episodes.append(
            {
                **verdict,
                "label_changes": _label_changes(rollout.labels),
                "ended_by_env": rollout.terminated or rollout.truncated,
            }
        )
    successes = sum(episode["success"] for episode in episodes)
    mean = {
        name: fmean(episode[name] for episode in episodes)
        for name in ("soft_break_count", "soft_breaks", "soft_open", "label_changes")
    }
    return {
        "rules": rules_of(card),
        "env": card.env["gym_id"],
        "successes": successes,
        "share": successes / EPISODES,
        "non_empty_share": sum(episode["non_empty_success"] for episode in episodes) / EPISODES,
        "ended_by_env": sum(episode["ended_by_env"] for episode in episodes),
        "idle_soft": {**mean, "unmet": mean["soft_breaks"] + mean["soft_open"]},
    }


def measure(no_goal: list[tuple[str, dict]], trained: set[tuple[str, str]]) -> list[dict]:
    """One row per no-goal task: its idle figures, trained or not, and whether it passes."""
    with ProcessPoolExecutor(WORKERS) as pool:
        measured = list(pool.map(idle_row, [card for _, card in no_goal]))
    rows = []
    for (group, card), row in zip(no_goal, measured, strict=True):
        soft_only = row["rules"] == "soft-only"
        rows.append(
            {
                "group": group,
                "id": card["id"],
                **row,
                "trained": (group, card["id"]) in trained,
                "passes": None if soft_only else row["share"] >= BAR,  # soft-only: all succeed
                "at_one": None if soft_only else row["share"] == 1.0,
            }
        )
        print(f"{group}/{card['id']}: {row['rules']}, idle success {row['share']:.2f}", flush=True)
    return rows


def check_against_judge(rows: list[dict]) -> int:
    """The soft-only rows the judge already played its idle plan on must come out the same."""
    stored = records.b.IDLE_EVERY
    seeds = f"{SEED_BASE}..{SEED_BASE + EPISODES - 1} ({EPISODES})"
    found = 0
    for row in rows:
        idle = stored.get(f"{row['group']}/{row['id']}")
        if idle is None:
            continue
        found += 1
        assert row["rules"] == "soft-only" and idle["seeds"] == seeds, row["id"]
        for name in ("soft_break_count", "soft_breaks", "soft_open", "label_changes"):
            assert math.isclose(row["idle_soft"][name], idle[name]), f"{row['id']}: {name}"
    assert found == len(stored), f"{len(stored)} judged idle rows, {found} found among the tasks"
    return found


# ======================================================================================
#                                      SUMMARY
# ======================================================================================


def summarize(rows: list[dict], entries: list[tuple[str, dict]]) -> dict:
    """The counts the entry reports, by group, for the tasks idle passes, and against the notes."""
    hard = [row for row in rows if row["rules"] != "soft-only"]
    passing = [row for row in hard if row["passes"]]
    marked = set(NOTES_MARKED)
    names = {row["id"] for row in passing}
    by_group = {}
    for group in GROUPS:
        members = [row for row in rows if row["group"] == group]
        by_group[group] = {
            "no_goal": len(members),
            "soft_only": sum(row["rules"] == "soft-only" for row in members),
            "idle_passes": [row["id"] for row in passing if row["group"] == group],
            "idle_passes_at_one": [
                row["id"] for row in passing if row["group"] == group and row["at_one"]
            ],
        }
    return {
        "cards": len(entries),
        "tasks": len({card["id"] for _, card in entries}),
        "no_goal": len(rows),
        "with_goal": len({card["id"] for _, card in entries}) - len(rows),
        "no_goal_with_hard_clause": len(hard),
        "no_goal_soft_only": len(rows) - len(hard),
        "idle_passes": len(passing),
        "idle_passes_at_one": sum(row["at_one"] for row in passing),
        "idle_passes_trained": [row["id"] for row in passing if row["trained"]],
        "by_group": by_group,
        "notes_marked": len(marked),
        "passes_marked_by_notes": sorted(names & marked),
        "passes_not_marked_by_notes": sorted(names - marked),
        "marked_by_notes_not_passed": sorted(marked - names),
    }


def table(rows: list[dict]) -> list[str]:
    """The Markdown table: one row per no-goal task."""
    lines = [
        "| group | ID | rules | trained | idle judged success | passes | idle soft breaks per episode "
        "(every break) | idle soft rules unmet per episode |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        soft = row["idle_soft"]
        figures = (
            [f"{soft['soft_break_count']:.2f}", f"{soft['unmet']:.2f}"]
            if row["rules"] == "soft-only"
            else ["", ""]
        )
        passes = (
            "n/a (no hard clause)" if row["passes"] is None else "yes" if row["passes"] else "no"
        )
        lines.append(
            f"| {row['group']} | `{row['id']}` | {row['rules']} | {'yes' if row['trained'] else 'no'} "
            f"| {row['share']:.2f} ({row['successes']}/{EPISODES}) | {passes} | {figures[0]} | {figures[1]} |"
        )
    return lines


def write_outputs(
    rows: list[dict], counts: dict, changed: list[str], added: dict[str, int]
) -> None:
    record = {
        "commit": COMMIT,
        "seeds": f"{SEED_BASE}..{SEED_BASE + EPISODES - 1}",
        "episodes": EPISODES,
        "bar": BAR,
        "counts": counts,
        "frozen_cards_differing_now": changed,
        "cards_added_since": added,
        "rows": rows,
    }
    (EVIDENCE / "idle.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")

    groups = [
        f"| {group} | {c['no_goal']} | {c['no_goal'] - c['soft_only']} | {c['soft_only']} "
        f"| {len(c['idle_passes'])} | {len(c['idle_passes_at_one'])} |"
        for group, c in counts["by_group"].items()
        if c["no_goal"]
    ]
    text = [
        "# Idle-passable tasks",
        "",
        f"Tasks of the group task files at `{COMMIT}`. Idle agent: a plan that only waits to the end of "
        f"the episode (`_IDLE_STEPS`), judged with `judge_trace` on the card's clauses, test seeds "
        f"{record['seeds']} ({EPISODES} episodes). Passes: idle judged success {BAR} or more. Soft-only: "
        "no hard clause, so every episode succeeds and the idle soft figures are shown instead.",
        "",
        f"{counts['no_goal']} of {counts['tasks']} tasks have no goal ({counts['with_goal']} have one and are "
        f"not judged). Of the {counts['no_goal']}, {counts['no_goal_with_hard_clause']} have a hard clause "
        f"and {counts['no_goal_soft_only']} are soft-only. Idle passes {counts['idle_passes']} "
        f"({counts['idle_passes_at_one']} at exactly 1.00); trained among them: "
        f"{counts['idle_passes_trained'] or 'none'}.",
        "",
        "| group | no-goal tasks | with a hard clause | soft-only | idle passes | idle passes at 1.00 |",
        "|---|---|---|---|---|---|",
        *groups,
        "",
        *table(rows),
        "",
    ]
    (EVIDENCE / "idle.md").write_text("\n".join(text), encoding="utf-8")


def main() -> None:
    entries = [(group, card) for group in GROUPS for card in cards_of(FROZEN / f"{group}.json")]
    no_goal = [(group, card) for group, card in entries if not card.get("goal")]
    names = [card["id"] for _, card in no_goal]
    assert len(names) == len(set(names)), "a no-goal task sits in two groups"
    trained_rows = records.learned_rows()
    assert len(trained_rows) == 60, "the final run trained 60 rows"
    trained = {
        ("shop" if row["suite"] == "shop-reward" else row["suite"], row["card"])
        for row in trained_rows
    }

    rows = measure(no_goal, trained)
    cut = [row["id"] for row in rows if row["ended_by_env"] != EPISODES]
    assert not cut, f"the idle plan was cut before the env ended on {cut}"
    judged = check_against_judge(rows)
    changed, added = current_changes()
    counts = summarize(rows, entries)
    write_outputs(rows, counts, changed, added)

    print(
        f"\n{counts['tasks']} tasks ({counts['cards']} cards), {counts['with_goal']} with a goal, "
        f"{counts['no_goal']} without: {counts['no_goal_with_hard_clause']} with a hard clause, "
        f"{counts['no_goal_soft_only']} soft-only"
    )
    for group, group_counts in counts["by_group"].items():
        if group_counts["idle_passes"]:
            print(
                f"idle passes in {group}: {len(group_counts['idle_passes'])}, {group_counts['idle_passes']}"
            )
    print(f"idle passes: {counts['idle_passes']} (at 1.00: {counts['idle_passes_at_one']})")
    print(f"trained tasks idle passes: {counts['idle_passes_trained'] or 'none'}")
    print(
        f"marked by the notes ({counts['notes_marked']}) but not passed: {counts['marked_by_notes_not_passed']}"
    )
    print(f"passed but not marked by the notes: {counts['passes_not_marked_by_notes']}")
    print(f"frozen cards differing now: {changed or 'none'}; cards added since: {added}")
    print(f"OK: {judged} soft-only idle rows equal the judge's stored idle figures")


if __name__ == "__main__":
    main()
