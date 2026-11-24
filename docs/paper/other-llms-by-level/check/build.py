"""Recount the thinking-level rows of every model; write data/levels.csv and data/levels.json (no model call).

One row per (model, level): the production pair (DeepSeek V4.1 Flash writes, GLM 5.3 Flash checks) from the
records of ``level-benchmark-freeze``, and Haiku 5.5 and GPT-6 Luna from the run folders of the multi-llm
plan folder. Every row is scored by the level benchmark's scorer (``arm_stats.arm``) against the cards of
``level-benchmark-freeze/evidence/cards``, so the rows line up. ``median_s_per_rm`` is the median ``wall_s``
of the level's records, as in ``results-figures/records.py``. A Haiku or Luna level that is final (138 runs
scored and its driver run ended in the driver log) has its records copied to ``records/``.

Run from the repository root, in RM_RL_env, as often as levels finish:
env CC_ROOT=$PWD PYTHONPATH=app:docs/paper/level-benchmark-freeze/check \
    python -P -W ignore docs/paper/other-llms-by-level/check/build.py
It stops on a half-written record while a driver is still running: run it again.
"""

import csv
import json
import shutil
import statistics
from pathlib import Path
from typing import NamedTuple

import arm_stats  # docs/paper/level-benchmark-freeze/check: the scorer behind its stats.md
from scipy.stats import binomtest

ENTRY = Path(__file__).resolve().parents[1]
REPO = ENTRY.parents[2]
FREEZE = REPO / "docs/paper/level-benchmark-freeze"
PLAN = REPO / ".git/agent-memory/plans/farm-final-20261119/multi-llm-20261124"
RUNS_PER_LEVEL = 138  # 46 cases x 3 runs

# What one request is, per route (the README says what each covers).
OPENCODE_API = "opencode-api-stream"  # streamed chat completion over HTTPS, no process start
CLAUDE_CLI = "claude-cli-oneshot"  # one `claude --print` process per request
CODEX_CLI = "codex-cli-oneshot"  # one `codex exec` process per request

FIELDS = (
    "model",
    "level",
    "right",
    "n",
    "rate",
    "wilson_low",
    "wilson_high",
    "median_s_per_rm",
    "final",
    "timing",
    "source",
)


class Source(NamedTuple):
    model: str
    timing: str
    level: str
    folder: Path  # the run folder the records are read from
    log: Path  # the driver log whose "end <round>:" line says the level's run ended
    round_name: str
    copy_to: Path | None  # where a final level's records are kept (None: already kept by an entry)


def sources() -> list[Source]:
    rows = [
        Source(
            "DeepSeek V4.1 Flash + GLM 5.3 Flash",
            OPENCODE_API,
            level,
            FREEZE / "records" / level,
            FREEZE / "evidence/level-bench.log",
            f"freeze-{level}",
            None,
        )
        for level in ("none", "low", "medium", "high", "max")
    ]
    for model, slug, timing, levels in (
        (
            "Haiku 5.5",
            "haiku",
            CLAUDE_CLI,
            ("low", "medium", "high", "max"),
        ),  # no "none": see README
        ("GPT-6 Luna", "luna", CODEX_CLI, ("none", "low", "medium", "high", "max")),
    ):
        rows += [
            Source(
                model,
                timing,
                level,
                PLAN / "runs" / f"subs-{slug}-{level}",
                PLAN / "c-subs-run.log",
                f"subs-{slug}-{level}",
                ENTRY / "records" / f"{slug}-{level}",
            )
            for level in levels
        ]
    return rows


def wilson(right: int, n: int) -> tuple[float, float]:
    """95% Wilson interval, as ``wilson_ci`` of the final-results builder."""
    ci = binomtest(right, n).proportion_ci(method="wilson")
    return ci.low, ci.high


def recount(src: Source) -> dict | None:
    """The row of one level, or None while it has no finished run."""
    counts, walls, _, _ = arm_stats.arm([src.folder])
    n, right = counts["runs"], counts["right"]
    if n == 0:
        return None
    # arm_stats counts a record without wall_s (a timeout) as 0 s, which would skew the median.
    assert min(walls) > 0, f"{src.round_name}: a run has no wall_s"
    ended = f" end {src.round_name}:" in src.log.read_text(encoding="utf-8")
    final = n == RUNS_PER_LEVEL and ended
    if final and src.copy_to is not None:
        src.copy_to.mkdir(parents=True, exist_ok=True)
        for record in sorted(src.folder.glob("*-r*.json")):
            shutil.copy2(record, src.copy_to / record.name)
    kept = src.copy_to if final and src.copy_to is not None else src.folder
    low, high = wilson(right, n)
    return {
        "model": src.model,
        "level": src.level,
        "right": right,
        "n": n,
        "rate": round(right / n, 4),
        "wilson_low": round(low, 4),
        "wilson_high": round(high, 4),
        "median_s_per_rm": round(statistics.median(walls), 2),
        "final": final,
        "timing": src.timing,
        "source": str(kept.relative_to(REPO)),
    }


def main() -> None:
    rows = [row for src in sources() if src.folder.exists() and (row := recount(src))]
    data = ENTRY / "data"
    data.mkdir(exist_ok=True)
    (data / "levels.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    with (data / "levels.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows({**row, "final": str(row["final"]).lower()} for row in rows)
    for row in rows:
        print(
            f"{row['model']} | {row['level']} | {row['right']}/{row['n']} | "
            f"{row['wilson_low']:.3f}-{row['wilson_high']:.3f} | {row['median_s_per_rm']} s | "
            f"final={row['final']}"
        )


if __name__ == "__main__":
    main()
