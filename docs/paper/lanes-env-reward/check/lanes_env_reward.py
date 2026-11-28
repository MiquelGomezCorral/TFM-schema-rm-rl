"""Zombie lanes with the environment's reward added to FARM's (no training, no model call).

The two soft-only lane tasks of the templates group were trained a second time with
``reward_source: both``: FARM's machine plus the environment's 1 per zombie killed. This script
recounts those runs from the run folders and sets them beside FARM's own runs, the runs trained
with no RM, and the idle agent (the judge's idle plan, ``SOFT_ONLY_IDLE_PLAN`` of
``app/scripts/test_rl.py``, played on the same 100 reset seeds as the judge).

"Learned" is the thesis's soft-only rule (user ruling of 2026-11-22): the run's every-break figure
(``mean_soft_break_count``) is compared with the idle plan's every-break figure, not one break per
rule. See ``learned_every_break``.

Two steps. ``collect`` reads ``outputs/runs/`` and the app: it copies each run's ``judge.json``,
counts kills and breaches per judged episode from the saved traces, plays the idle plan, and copies
the cards and the machine text into ``evidence/``. ``summarize`` reads only ``evidence/``: it
writes ``evidence/runs.json`` and ``evidence/tables.md``. Traces are not copied.

Run from the repository root, inside RM_RL_env:
env PYTHONPATH=app python -P -W ignore docs/paper/lanes-env-reward/check/lanes_env_reward.py
Add --evidence-only to run ``summarize`` alone (no run folders, no rollouts).
"""

import argparse
import json
import math
import shutil
from pathlib import Path
from statistics import fmean, stdev

import yaml

from scripts.test_rl import SOFT_ONLY_IDLE_PLAN, _label_changes
from src.benchmark import judge_trace
from src.benchmark.cards import Card
from src.benchmark.plans import run_plan

ENTRY = Path(__file__).resolve().parents[1]
EVIDENCE = ENTRY / "evidence"
REPO = ENTRY.parents[2]
RUNS = REPO / "outputs" / "runs"
TASKS_FILE = REPO / "experiments" / "benchmark" / "templates" / "tasks.json"

ABSENCE, NOT_BOTH = "tpl-absence-soft-1-nogoal", "tpl-not-co-existence-soft-1-nogoal"
TASKS = (ABSENCE, NOT_BOTH)
# key, label, run group of a task, and the ``reward_source`` of its config.yaml
METHODS = (
    (
        "farm-env",
        "FARM + environment's reward",
        "bench__templates-lanes-both__{}__farm__ppo",
        "both",
    ),
    ("farm", "FARM alone", "bench__templates__{}__farm__ppo", "rm"),
    ("no-rm", "No RM", "bench__templates__{}__no-rm__ppo", "env"),
)
EVENTS = {"kills": "zombie_killed", "top": "top_breach", "side": "side_breach"}
STATS = (
    "kills",
    "top",
    "side",
    "no_top",
    "top_same_as_idle",
    "soft_break_count",
    "rules_broken",
    "rules_open",
)
RUN_COLUMNS = ["reset_seed", "kills", "top", "side"]
IDLE_COLUMNS = [*RUN_COLUMNS, "soft_break_count", "soft_breaks", "soft_open", "label_changes"]
SEED_BASE, EPISODES = 2_000_000, 100  # the judge's test seeds: eval_seed_base + i
RUNS_PER_GROUP = 3
T975_DF2 = 4.302652729911275  # two-sided 95% Student t, 2 degrees of freedom (3 runs)
# The idle every-break figures of docs/paper/soft-breaks-vs-idle/evidence/soft-breaks.txt (the
# builder's IDLE_EVERY, final-results/build_results.py, holds the same two values).
IDLE_SOFT_BREAKS = {ABSENCE: 26.18, NOT_BOTH: 7.49}
# The Idle column of thesis table tab:res-lanes-counts (paper/plantillatfg.tex), one decimal.
THESIS_IDLE = {"kills": 0.0, "top": 8.7, "side": 17.5}


# ======================================================================================
#                                       COLLECT
# ======================================================================================


def event_counts(labels: list[dict[str, bool]]) -> list[int]:
    """Steps of one episode on which each event of ``EVENTS`` holds."""
    return [sum(bool(step.get(name)) for step in labels) for name in EVENTS.values()]


def run_folders(group: str) -> list[Path]:
    """The judged seed folders of a run group, ``seed1`` to ``seed3``."""
    folders = sorted(
        folder
        for folder in (RUNS / group).glob("seed*-*")
        if folder.is_dir() and "." not in folder.name and (folder / "judge.json").exists()
    )
    assert len(folders) == RUNS_PER_GROUP, f"{group}: {len(folders)} judged runs"
    return folders


def collect_run(folder: Path, group: str, source: str, dest: Path) -> tuple[dict, dict]:
    """One run: its evidence row, and its judge file (copied to ``dest``)."""
    config = yaml.safe_load((folder / "config.yaml").read_text())
    assert config.get("reward_source", "rm") == source, f"{folder.name}: reward_source"
    judge = json.loads((folder / "judge.json").read_text())
    seeds = [episode["reset_seed"] for episode in judge["per_episode"]]
    assert seeds == list(range(SEED_BASE, SEED_BASE + EPISODES)), f"{folder.name}: reset seeds"
    episodes = [
        [
            episode["reset_seed"],
            *event_counts(json.loads((folder / episode["file"]).read_text())["labels"]),
        ]
        for episode in judge["per_episode"]
    ]
    shutil.copyfile(folder / "judge.json", dest)
    shared = folder / "shared-run.json"
    return judge, {
        "group": group,
        "folder": folder.name,
        "reward_source": source,
        "shared_owner": json.loads(shared.read_text())["owner_exp_name"]
        if shared.exists()
        else None,
        "episodes": episodes,
    }


def idle_rows(card: dict) -> list[list[float]]:
    """The idle plan on the judge's reset seeds: event counts and the judge's soft figures."""
    parsed = Card.from_dict(card)
    rows = []
    for seed in range(SEED_BASE, SEED_BASE + EPISODES):
        rollout = run_plan(parsed.env, SOFT_ONLY_IDLE_PLAN, seed)
        assert rollout.terminated or rollout.truncated, f"seed {seed}: the idle plan was cut short"
        verdict = judge_trace(parsed.expect, rollout.labels).to_dict()
        rows.append(
            [
                seed,
                *event_counts(rollout.labels),
                verdict["soft_break_count"],
                verdict["soft_breaks"],
                verdict["soft_open"],
                _label_changes(rollout.labels),
            ]
        )
    return rows


def check_idle_against_judge(rows: list[list[float]], judge: dict) -> None:
    """The idle replay must equal the idle figures the judge stored in its own file."""
    soft = judge["soft_only"]
    for name, column in (
        ("idle_mean_soft_breaks", "soft_breaks"),
        ("idle_mean_soft_open", "soft_open"),
        ("idle_mean_label_changes", "label_changes"),
    ):
        mean = fmean(row[IDLE_COLUMNS.index(column)] for row in rows)
        assert math.isclose(mean, soft[name], abs_tol=0.006), f"idle {name}: {mean} vs {soft[name]}"


def collect_task(card: dict) -> tuple[dict, list, dict]:
    """The runs, idle rows and card record of one task; copies judge files and the machine text."""
    task = card["id"]
    runs, judges = {}, []
    (EVIDENCE / "judge" / task).mkdir(parents=True, exist_ok=True)
    for method, _, pattern, source in METHODS:
        group = pattern.format(task)
        runs[method] = {}
        for folder in run_folders(group):
            seed = folder.name.split("-")[0]
            dest = EVIDENCE / "judge" / task / f"{method}-{seed}.json"
            judge, runs[method][seed] = collect_run(folder, group, source, dest)
            judges.append((method, judge))
    idle = idle_rows(card)
    for _, judge in judges:
        check_idle_against_judge(idle, judge)
    bundles = {judge["rm_bundle"] for method, judge in judges if method.startswith("farm")}
    assert len(bundles) == 1, f"{task}: the FARM runs used {len(bundles)} bundles"
    bundle = Path(bundles.pop())
    (EVIDENCE / "rm").mkdir(exist_ok=True)
    shutil.copyfile(bundle / "reward_machine.txt", EVIDENCE / "rm" / f"{task}.rm")
    generation = json.loads((bundle / "manifest.json").read_text())["generation"]
    first = judges[0][1]
    info = {
        "task": card["task"],
        "template": card["template"],
        "goal": card["goal"],
        "expect": card["expect"],
        "ltlf": [clause["ltlf"]["readable"] for clause in first["expect"]],
        "rm_bundle": str(bundle.relative_to(REPO)),
        "farm_clauses": generation["clauses"],
        "farm_clause_texts": generation["clause_texts"],
    }
    return runs, idle, info


def collect() -> None:
    """Fill ``evidence/`` from the run folders and the app."""
    cards = {card["id"]: card for card in json.loads(TASKS_FILE.read_text())["cards"]}
    EVIDENCE.mkdir(exist_ok=True)
    record = {"run_columns": RUN_COLUMNS, "idle_columns": IDLE_COLUMNS, "runs": {}, "idle": {}}
    infos = {}
    for task in TASKS:
        record["runs"][task], record["idle"][task], infos[task] = collect_task(cards[task])
        print(f"collected {task}: idle replay equals the judge's stored idle figures", flush=True)
    (EVIDENCE / "episodes.json").write_text(json.dumps(record, separators=(",", ":")) + "\n")
    (EVIDENCE / "cards.json").write_text(json.dumps(infos, indent=1) + "\n")


# ======================================================================================
#                                      SUMMARIZE
# ======================================================================================


def interval(values: list[float]) -> dict[str, float]:
    """Mean and 95% t interval over the runs (low end clipped at 0: every figure is a count)."""
    assert len(values) == RUNS_PER_GROUP
    mean = fmean(values)
    half = T975_DF2 * stdev(values) / math.sqrt(len(values))
    return {"mean": mean, "low": max(0.0, mean - half), "high": mean + half}


def mean_of(rows: list[list[float]], column: str, columns: list[str]) -> float:
    """The mean of one column of the per-episode rows."""
    return fmean(row[columns.index(column)] for row in rows)


def learned_every_break(judge: dict, idle_every: float) -> bool:
    """The soft-only rule of the thesis and the 60 rows: every break against idle's every break.

    A copy of ``every_break.rule`` (``freeze-prep/tools/soft_every_break.py``), as ``seed_learned``
    of ``final-results/build_results.py`` applies it (user ruling 2026-11-22: the once-per-rule
    count, ``soft_only.mean_soft_breaks``, saturates in Lanes). Learned: neither every break nor
    the open clauses exceed idle's, one is below it, and the label changes exceed idle's. Idle's
    open and label-change figures are the ones the judge stored.
    """
    soft = judge["soft_only"]
    every, open_ = judge["mean_soft_break_count"], soft["mean_soft_open"]
    idle_open = soft["idle_mean_soft_open"]
    no_worse = every <= idle_every and open_ <= idle_open
    better = every < idle_every or open_ < idle_open
    return no_worse and better and soft["mean_label_changes"] > soft["idle_mean_label_changes"]


def run_stats(
    judge: dict, episodes: list[list[int]], idle_top: dict[int, int], idle_every: float
) -> dict:
    """One run's figures: event means from the traces, soft figures from the judge file.

    ``idle_top`` is the idle plan's top-lane count per reset seed. A reset seed fixes when and
    where the zombies enter, so an agent whose count equals idle's on a seed stopped none of
    that episode's top-lane zombies. ``idle_every`` is idle's mean every-break figure.
    """
    soft = judge["soft_only"]
    return {
        **{name: mean_of(episodes, name, RUN_COLUMNS) for name in EVENTS},
        "no_top": sum(row[RUN_COLUMNS.index("top")] == 0 for row in episodes),
        "top_same_as_idle": sum(
            row[RUN_COLUMNS.index("top")] == idle_top[row[0]] for row in episodes
        ),
        "soft_break_count": judge["mean_soft_break_count"],
        "rules_broken": soft["mean_soft_breaks"],
        "rules_open": soft["mean_soft_open"],
        "learned": learned_every_break(judge, idle_every),
    }


def idle_stats(rows: list[list[float]]) -> dict:
    """The idle agent's figures over the judge's 100 reset seeds."""
    return {
        **{name: mean_of(rows, name, IDLE_COLUMNS) for name in EVENTS},
        "no_top": sum(row[IDLE_COLUMNS.index("top")] == 0 for row in rows),
        "soft_break_count": mean_of(rows, "soft_break_count", IDLE_COLUMNS),
        "rules_broken": mean_of(rows, "soft_breaks", IDLE_COLUMNS),
        "rules_open": mean_of(rows, "soft_open", IDLE_COLUMNS),
    }


def summarize_task(task: str, runs: dict, idle: list[list[float]]) -> dict:
    """Per method: each run's figures and the mean with its interval; plus the idle row."""
    methods = {}
    idle_top = {row[0]: row[IDLE_COLUMNS.index("top")] for row in idle}
    stats = idle_stats(idle)
    assert math.isclose(stats["soft_break_count"], IDLE_SOFT_BREAKS[task], abs_tol=0.006)
    for method, label, pattern, source in METHODS:
        per_run = {}
        for seed, run in runs[method].items():
            judge = json.loads((EVIDENCE / "judge" / task / f"{method}-{seed}.json").read_text())
            seeds = [row["reset_seed"] for row in judge["per_episode"]]
            assert seeds == [row[0] for row in run["episodes"]], f"{method}-{seed}: seeds"
            if task == ABSENCE:  # two soft Absences: the judge counts one break per lane event
                assert all(
                    row["soft_break_count"] == counts[2] + counts[3]
                    for row, counts in zip(judge["per_episode"], run["episodes"], strict=True)
                ), f"{method}-{seed}: judge soft_break_count differs from the trace counts"
            per_run[seed] = {
                "folder": run["folder"],
                "shared_owner": run["shared_owner"],
                **run_stats(judge, run["episodes"], idle_top, stats["soft_break_count"]),
            }
        methods[method] = {
            "label": label,
            "group": pattern.format(task),
            "reward_source": source,
            "runs": per_run,
            "mean": {name: interval([run[name] for run in per_run.values()]) for name in STATS},
        }
    return {"methods": methods, "idle": stats}


def cell(stat: dict[str, float], digits: int = 2) -> str:
    """``mean [low, high]``."""
    return f"{stat['mean']:.{digits}f} [{stat['low']:.{digits}f}, {stat['high']:.{digits}f}]"


def mean_table(result: dict, clauses: int) -> list[str]:
    """The Markdown table of one task: a row per method, then the idle row."""
    lines = [
        f"| method | runs | kills | top-lane breaches | side-lane breaches | episodes with no top-lane "
        f"breach (of {EPISODES}) | every break | rules broken at least once (of {clauses}) "
        "| runs learned |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for method in result["methods"].values():
        mean, runs = method["mean"], method["runs"]
        lines.append(
            f"| {method['label']} | {len(runs)} | {cell(mean['kills'])} "
            f"| {cell(mean['top'])} | {cell(mean['side'])} | {cell(mean['no_top'], 1)} "
            f"| {cell(mean['soft_break_count'])} | {cell(mean['rules_broken'])} "
            f"| {sum(run['learned'] for run in runs.values())} of {len(runs)} |"
        )
    idle = result["idle"]
    lines.append(
        f"| Idle (one fixed plan) | - | {idle['kills']:.2f} | {idle['top']:.2f} | {idle['side']:.2f} "
        f"| {idle['no_top']} | {idle['soft_break_count']:.2f} | {idle['rules_broken']:.2f} | - |"
    )
    return lines


def run_table(result: dict) -> list[str]:
    """One row per run, with its folder, every break against idle's, and the learned mark."""
    idle_every = result["idle"]["soft_break_count"]
    lines = [
        "| method | run | kills | top | side | no top breach | top count = idle's "
        f"| every break (idle's {idle_every:.2f}) | rules broken at least once "
        "| learned (every-break rule) | folder |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for method in result["methods"].values():
        for seed, run in method["runs"].items():
            lines.append(
                f"| {method['label']} | {seed} | {run['kills']:.2f} | {run['top']:.2f} "
                f"| {run['side']:.2f} | {run['no_top']} | {run['top_same_as_idle']} "
                f"| {run['soft_break_count']:.2f} | {run['rules_broken']:.2f} "
                f"| {'yes' if run['learned'] else 'no'} | `{run['folder']}` |"
            )
    return lines


def thesis_check(idle: dict) -> list[str]:
    """The thesis table's Idle column against the measured idle figures."""
    lines = []
    for name, printed in THESIS_IDLE.items():
        verdict = "matches" if round(idle[name], 1) == printed else "differs"
        lines.append(f"idle {name}: measured {idle[name]:.3f}, thesis {printed} ({verdict})")
    lines.append(
        f"idle episodes with no top-lane breach: {idle['no_top']} of {EPISODES}, thesis --"
    )
    return lines


def summarize() -> None:
    """Write ``runs.json`` and ``tables.md`` from ``evidence/`` alone."""
    record = json.loads((EVIDENCE / "episodes.json").read_text())
    cards = json.loads((EVIDENCE / "cards.json").read_text())
    assert record["run_columns"] == RUN_COLUMNS and record["idle_columns"] == IDLE_COLUMNS
    out = {
        "reset_seeds": f"{SEED_BASE}..{SEED_BASE + EPISODES - 1}",
        "episodes": EPISODES,
        "interval": "95% Student t interval over the 3 runs (t = 4.3027, 2 df), low end clipped at 0",
        "tasks": {},
    }
    text = [
        "# Zombie lanes with the environment's reward added (tables of `check/lanes_env_reward.py`)",
        "",
        f"Mean over the 3 runs of each method [95% t interval over the runs, low end clipped at 0]; "
        f"{EPISODES} judged episodes per run on reset seeds {out['reset_seeds']}; idle: the judge's "
        "idle plan on the same seeds, one fixed policy, so no interval. Every break: the judge's "
        "`mean_soft_break_count`. Rules broken at least once: `soft_only.mean_soft_breaks`. Learned: "
        "every break and open clauses no more than idle's, one below it, label changes above idle's "
        "(user ruling 2026-11-22).",
        "",
    ]
    for task in TASKS:
        result = summarize_task(task, record["runs"][task], record["idle"][task])
        out["tasks"][task] = {"card": cards[task], **result}
        table = mean_table(result, len(cards[task]["expect"]))
        text += [f"## `{task}`", "", *table, "", *run_table(result), ""]
        print(f"\n{task}", *table, sep="\n")
    (EVIDENCE / "runs.json").write_text(json.dumps(out, indent=1) + "\n")
    (EVIDENCE / "tables.md").write_text("\n".join(text))
    idle = [out["tasks"][task]["idle"] for task in TASKS]
    assert all(row[name] == idle[0][name] for row in idle for name in (*EVENTS, "no_top"))
    assert all(
        run["learned"]
        for task in out["tasks"].values()
        for method in task["methods"].values()
        for run in method["runs"].values()
    ), "the thesis counts all 18 runs as learned by the every-break rule"
    print("\nthe thesis table's Idle column (the idle episodes are the same on both tasks):")
    print(*thesis_check(idle[0]), sep="\n")
    print("OK: 18 runs summarized")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--evidence-only", action="store_true", help="skip collect")
    args = parser.parse_args()
    if not args.evidence_only:
        collect()
    summarize()


if __name__ == "__main__":
    main()
