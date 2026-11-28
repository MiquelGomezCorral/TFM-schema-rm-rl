"""Recount the thinking-level rows of every model; write data/levels.csv and data/levels.json (no model call).

One row per (model, level): the production pair (DeepSeek V4.1 Flash writes, GLM 5.3 Flash checks) from the
records of ``level-benchmark-freeze``, Haiku 5.5 and GPT-6 Luna from the run folders of the multi-llm
plan folder, and the cluster models (``CLUSTER_MODELS``) and the small local models on the desktop GPU
(``SMALL_LOCAL_MODELS``) from the ``until-fix`` run folders next to it. Every
row is scored by the level benchmark's scorer (``arm_stats.arm``) against the final accepted-answer lists kept in
``evidence/cards`` (the freeze's cards plus the six answers added on 2026-11-22, commit ``21a3ef98``), not the frozen
copy in ``level-benchmark-freeze/evidence/cards``: every count in the thesis uses the final lists, and all rows are
scored the same way. ``median_s_per_rm`` is the median ``wall_s``
of the level's records, as in ``results-figures/records.py``; a run the driver killed at its 3600 s cap has no
``wall_s`` and counts as 3600 s. A Haiku, Luna, cluster or small local level that is final
(138 runs scored and its run ended in the driver or watcher log) has its records copied to ``records/``.

Run from the repository root, in RM_RL_env, as often as levels finish:
env CC_ROOT=$PWD PYTHONPATH=app:docs/paper/level-benchmark-freeze/check \
    python -P -W ignore docs/paper/other-llms-by-level/check/build.py
It stops on a half-written record while a driver is still running: run it again.
"""

import csv
import json
import re
import statistics
from pathlib import Path
from typing import NamedTuple

import arm_stats  # docs/paper/level-benchmark-freeze/check: the scorer behind its stats.md
import cases  # the scorer's card loader
from scipy.stats import binomtest

ENTRY = Path(__file__).resolve().parents[1]
# The scorer defaults to the frozen cards; score with the final answer lists. Set after the import: the CARD_DIR
# env var is read at import time, so setting it first would put code above the imports.
cases.CARD_DIR = ENTRY / "evidence/cards"
REPO = ENTRY.parents[2]
FREEZE = REPO / "docs/paper/level-benchmark-freeze"
PLAN = REPO / ".git/agent-memory/plans/farm-final-20261119/multi-llm-20261124"
UNTIL_FIX = PLAN.parent / "until-fix"
RUNS_PER_LEVEL = 138  # 46 cases x 3 runs
RUN_CAP_S = 3600  # the driver kills a run at this many seconds and its record says "timeout 3600s"

# What one request is, per route (the README says what each covers).
OPENCODE_API = "opencode-api-stream"  # streamed chat completion over HTTPS, no process start
CLAUDE_CLI = "claude-cli-oneshot"  # one `claude --print` process per request
CODEX_CLI = "codex-cli-oneshot"  # one `codex exec` process per request
LOCAL_API = "local-api-stream"  # streamed chat completion to a vLLM server on the cluster or an Ollama one here

# Cluster models, served by vLLM through the `local` provider, one model for both roles: (slug, name, levels).
# A run folder is until-fix/runs/multillm-<slug>-<level>/L and the watcher log has its `end` line.
CLUSTER_MODELS = (
    ("muse-glimmer-30b", "Muse Glimmer 30B", ("low", "medium", "high", "max")),
    ("gemma-4-31b", "Gemma 4 31B", ("none", "high")),
    ("qwen3.8-27b", "Qwen3.8 27B", ("none", "low", "medium", "max")),
    ("gpt-oss-120b", "gpt-oss-120b", ("low", "medium", "high")),
)

# Small models on the desktop GPU, served by Ollama through the same provider: (served tag, name, levels).
# The run folder is named after the tag as multi-llm-bench.sh does, and small-local.log has the `end` line.
SMALL_LOCAL_MODELS = (
    ("qwen3.5:9b-q4_K_M", "Qwen3.5 9B (Q4)", ("none", "high")),
    ("llama3.1:8b-instruct-q5_K_M", "Llama 3.1 8B Instruct (Q5)", ("none",)),
    ("gemma4:12b-it-q4_K_M", "Gemma 4 12B (Q4)", ("none", "high")),
    ("gpt-oss:20b", "gpt-oss-20b", ("low", "medium", "high")),
)

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
    end_line: str | None = None  # the log text of the run's end (default " end <round_name>:")


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
    rows += [
        Source(
            name,
            LOCAL_API,
            level,
            UNTIL_FIX / "runs" / f"multillm-{slug}-{level}" / "L",
            PLAN / "cluster-watch.log",
            f"multillm-{slug}-{level}",
            ENTRY / "records" / f"{slug}-{level}",
        )
        for slug, name, levels in CLUSTER_MODELS
        for level in levels
    ]
    for served, name, levels in SMALL_LOCAL_MODELS:
        slug = re.sub(r"[/:]", "-", served)
        rows += [
            Source(
                name,
                LOCAL_API,
                level,
                UNTIL_FIX / "runs" / f"multillm-{slug}-{level}" / "L",
                PLAN / "small-local.log",
                f"multillm-{slug}-{level}",
                ENTRY / "records" / f"{slug}-{level}",
                f" end {served} {level} rc=0",
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
    # arm_stats counts a record without wall_s as 0 s. A run the driver killed at the cap has none and lasted
    # the cap (the true time is longer, which the median does not see); any other missing wall_s stops the build.
    timed_out = sum(
        json.loads(path.read_text(encoding="utf-8")).get("error") == f"timeout {RUN_CAP_S}s"
        for path in src.folder.glob("*-r*.json")
    )
    assert walls.count(0) == timed_out, (
        f"{src.round_name}: a run has no wall_s and did not time out"
    )
    walls = [wall or RUN_CAP_S for wall in walls]
    ended = (src.end_line or f" end {src.round_name}:") in src.log.read_text(encoding="utf-8")
    final = n == RUNS_PER_LEVEL and ended
    if final and src.copy_to is not None:
        src.copy_to.mkdir(parents=True, exist_ok=True)
        for record in sorted(src.folder.glob("*-r*.json")):
            # One final newline, as the repository's end-of-file hook leaves a file, so a rerun changes nothing.
            text = record.read_text(encoding="utf-8").rstrip("\n") + "\n"
            (src.copy_to / record.name).write_text(text, encoding="utf-8")
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
