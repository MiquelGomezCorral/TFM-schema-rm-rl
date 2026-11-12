"""Aggregate a benchmark suite's runs into ``results.csv``, ``results.json`` and ``results.md``.

Usage:
    python app/main.py aggregate-suite --suite <runs.yaml> --output outputs/results/pilot

One row per run of the suite (``run_suite.expand_runs``), with the run's status, then a
per-card table that sets the arms side by side. Judged success, hard and soft breaks and open
at end are the episode means in the run's ``judge.json`` (``test-rl --judge``); open at end is
the hard and soft clauses still open, added together. A run without one shows "not evaluated". Env
success, returns and episode length come from the last ``eval.csv`` row.
An optional ``replay_summary:`` in the runs.yaml names a ``replay-traces`` summary JSON with a
``machine_check`` per bundle, keyed by the bundle path under the suite's ``bundles:`` folder
(``<arm>/<card-id>``, or ``<card-id>/off-<switch>`` for ablation); a failed check flags
``machine-wrong``, and a bundle with no check stays unknown.
Every table carries the time-limit asymmetry line, and ``results.csv`` a column with it; at
fewer than 3 seeds there is no verdict.
"""

import csv
import json
from collections import Counter
from pathlib import Path

from src.benchmark.traces import read_json
from src.config import Configuration

from .run_suite import FINISHED, ROOT, TIMED_OUT, Run, expand_runs, load_suite, run_state

ASYMMETRY = (
    "Time-limit asymmetry: FARM machines charge open items at any end; "
    "ARM-FM machines get 0 at the time limit."
)
NOT_EVALUATED = "not evaluated"
SEED_TARGET = 3
JUDGE_KEYS = ("judged_success", "hard_breaks", "soft_breaks")  # open_at_end is built apart
# (table header, results key) of the metric columns, in table order.
METRICS = (
    ("judged success", "judged_success"),
    ("env success", "env_success"),
    ("hard breaks", "hard_breaks"),
    ("soft breaks", "soft_breaks"),
    ("open at end", "open_at_end"),
    ("first env success", "first_env_success_step"),
    ("last-3 eval success", "eval_success_last3"),
    ("env return", "env_return"),
    ("RM return", "rm_return"),
    ("episode length", "episode_length"),
    ("wall s", "wall_time_s"),
    ("peak GB", "peak_rss_gb"),
    ("machine-wrong", "machine_wrong"),
)
COLUMNS = (
    "exp_name",
    "card",
    "arm",
    "learner",
    "variant",
    "seed",
    "status",
    *(key for _, key in METRICS),
    "note",
    "bundle",
    "run_folder",
    "time_limit_asymmetry",
)


# ======================================================================================
#                                      ONE RUN ROW
# ======================================================================================


def number(text: str | None) -> float | None:
    """A CSV cell as a float; empty or absent is None."""
    return float(text) if text else None


def eval_rows(folder: Path) -> list[dict]:
    """The overall rows of the run's ``eval.csv`` (the per-task rows of a multi-task run skip)."""
    path = folder / "eval.csv"
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as file:
        return [row for row in csv.DictReader(file) if not row["task"]]


def eval_columns(card: dict, rows: list[dict], status: str) -> dict:
    """Env success, first success step, last-3 success, returns and length from the eval rows."""
    if not rows:
        return {}
    last = rows[-1]
    solved = [row for row in rows if (number(row["exit_rate"]) or 0) > 0]
    if not card.get("env_reward_matches"):
        first = "n/a"  # the env reward does not pay for this card's task
    else:
        no_success = "not reached" if status == TIMED_OUT else "never"
        first = int(solved[0]["global_step"]) if solved else no_success
    tail = [number(row["exit_rate"]) for row in rows[-3:]]
    return {
        "env_success": number(last["exit_rate"]),
        "first_env_success_step": first,
        "eval_success_last3": round(sum(tail) / len(tail), 3),
        "env_return": number(last["mean_env_return"]),
        "rm_return": number(last["mean_rm_return"]),  # empty for the no-RM arm
        "episode_length": number(last["mean_length"]),
    }


def judge_columns(folder: Path) -> dict:
    """The judge's columns, or "not evaluated" when ``test-rl --judge`` has not run.

    ``judge.json`` holds the episode means (``mean_*``, see ``test_rl.JUDGE_MEANS``). Open at end
    is the mean number of clauses still open, hard and soft together; a missing mean stays empty.
    """
    judge = read_json(folder / "judge.json")
    if not judge:
        return {"judged_success": NOT_EVALUATED}
    columns = {key: judge.get(f"mean_{key}") for key in JUDGE_KEYS}
    hard_open, soft_open = judge.get("mean_hard_open"), judge.get("mean_soft_open")
    columns["open_at_end"] = None if None in (hard_open, soft_open) else hard_open + soft_open
    return columns


def machine_wrong(bundle: Path | None, bundles: Path, replay: dict | None) -> bool | None:
    """True when the replay summary's ``machine_check`` of this bundle failed; None if unknown.

    The summary is keyed by the bundle path relative to the suite's bundles folder.
    """
    if bundle is None or replay is None:
        return None
    entry = replay.get("bundles", replay).get(bundle.relative_to(bundles).as_posix())
    check = (entry or {}).get("machine_check")
    passed = check if isinstance(check, bool) else (check or {}).get("passed")
    return None if passed is None else not passed


def run_row(run: Run, bundles: Path, replay: dict | None) -> dict:
    """The results row of one run; ``bundles`` is the suite's bundles folder."""
    status, folder, note = run_state(run)
    row = dict.fromkeys(COLUMNS)
    row.update(
        exp_name=run.exp_name,
        card=run.card["id"],
        arm=run.arm,
        learner=run.learner,
        variant=run.variant or "",
        seed=run.seed,
        status=status,
        note=note,
        judged_success=NOT_EVALUATED,  # a run with no folder has no judge.json either
        bundle=str(run.bundle or ""),
        run_folder=str(folder or ""),
        time_limit_asymmetry=ASYMMETRY,
    )
    if folder is None:
        return row

    resources = read_json(folder / "resources.json")
    summary = read_json(folder / "summary.json")
    row.update(
        judge_columns(folder),
        **eval_columns(run.card, eval_rows(folder), status),
        wall_time_s=resources.get("wall_time_s", summary.get("wall_seconds")),
        peak_rss_gb=resources.get("peak_rss_gb"),
        machine_wrong=machine_wrong(run.bundle, bundles, replay),
    )
    return row


# ======================================================================================
#                                  PER-CARD, ACROSS ARMS
# ======================================================================================


def mean_cell(values: list) -> object:
    """Mean of the numeric values; a word when none is numeric; flags seeds that had none."""
    numbers = [value for value in values if isinstance(value, int | float)]
    if numbers:
        mean = round(sum(numbers) / len(numbers), 3)
        return mean if len(numbers) == len(values) else f"{mean} ({len(numbers)}/{len(values)})"
    words = [value for value in values if isinstance(value, str) and value]
    return Counter(words).most_common(1)[0][0] if words else None


def group_rows(rows: list[dict]) -> list[dict]:
    """One row per card x arm x learner x variant: the seeds' finished count and mean metrics."""
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        groups.setdefault((row["card"], row["arm"], row["learner"], row["variant"]), []).append(row)

    result = []
    for (card, arm, learner, variant), members in groups.items():
        finished = sum(member["status"] == FINISHED for member in members)
        cells = {
            key: mean_cell([member[key] for member in members])
            for _, key in METRICS
            if key != "machine_wrong"
        }
        checks = [m["machine_wrong"] for m in members if m["machine_wrong"] is not None]
        cells["machine_wrong"] = any(checks) if checks else None  # unknown stays unknown
        result.append(
            {
                "card": card,
                "arm": arm,
                "learner": learner,
                "variant": variant,
                "seeds": f"{finished}/{len(members)}",
                "bundle": members[0]["bundle"],
                **cells,
            }
        )
    return result


# ======================================================================================
#                                       OUTPUT
# ======================================================================================


def cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        if value.is_integer() or abs(value) >= 1e6:
            return str(round(value))  # 90000.0 and 1234567.5, never e-notation
        return f"{value:.6g}"
    return str(value)


def markdown_table(headers: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(cell(value) for value in row) + " |" for row in rows]
    return "\n".join(lines)


def card_section(card: dict, groups: list[dict]) -> str:
    """One card: its task, clauses and machines, then the arms side by side."""
    clauses = "; ".join(
        f"{template}({', '.join(props)}) {level}" for template, props, level in card["expect"]
    )
    machines = "; ".join(
        f"{group['arm']}: {group['bundle']}/reward_machine.txt"
        for group in groups
        if group["bundle"]
    )
    table = markdown_table(
        ["arm", "learner", "variant", "seeds finished", *(header for header, _ in METRICS)],
        [
            [g["arm"], g["learner"], g["variant"], g["seeds"], *(g[key] for _, key in METRICS)]
            for g in groups
        ],
    )
    return (
        f"### {card['id']}\n\nTask: {card['task']}\n\nClauses: {clauses}\n\n"
        f"Machines: {machines or 'none (no-RM arm only)'}\n\n{ASYMMETRY}\n\n{table}"
    )


def results_markdown(spec: dict, rows: list[dict], groups: list[dict]) -> str:
    seeds = spec["seeds"]
    verdict = (
        f"{len(seeds)} seed(s) per cell, target {SEED_TARGET}: no verdict, compare behaviour only."
        if len(seeds) < SEED_TARGET
        else f"{len(seeds)} seeds per cell."
    )
    run_table = markdown_table(
        ["card", "arm", "learner", "variant", "seed", "status", *(h for h, _ in METRICS)],
        [
            [r["card"], r["arm"], r["learner"], r["variant"], r["seed"], r["status"]]
            + [r[key] for _, key in METRICS]
            for r in rows
        ],
    )
    sections = [
        card_section(card, [g for g in groups if g["card"] == card["id"]])
        for card in spec["cards"]
        if any(g["card"] == card["id"] for g in groups)
    ]
    return (
        f"# Suite {spec['suite']}\n\n{verdict}\n\n## Runs\n\n{ASYMMETRY}\n\n{run_table}\n\n"
        "## Per card, across arms\n\n" + "\n\n".join(sections) + "\n"
    )


# ======================================================================================
#                                      PUBLIC API
# ======================================================================================


def aggregate_suite(CONFIG: Configuration) -> None:
    """Write ``results.csv``, ``results.json`` and ``results.md`` for ``CONFIG.suite``.

    Raises:
        ValueError: If ``--suite`` or ``--output`` is missing.
    """
    if CONFIG.suite is None or CONFIG.suite_output is None:
        raise ValueError("aggregate-suite requires --suite and --output")
    spec = load_suite(CONFIG.suite)
    replay = None
    if spec.get("replay_summary"):  # written once: a missing or bad file raises, not "unknown"
        replay = json.loads((ROOT / spec["replay_summary"]).read_text(encoding="utf-8"))
    bundles = Path(spec["bundles"])
    rows = [run_row(run, bundles, replay) for run in expand_runs(spec)]
    groups = group_rows(rows)

    output = CONFIG.suite_output
    output.mkdir(parents=True, exist_ok=True)
    with (output / "results.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    results = {"suite": spec["suite"], "asymmetry": ASYMMETRY, "runs": rows, "cards": groups}
    (output / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    markdown = results_markdown(spec, rows, groups)
    (output / "results.md").write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"wrote {output / 'results.csv'}, results.json and results.md")
