"""List the judge state of every run folder and, on request, re-judge the stale ones.

Usage (repository root, `RM_RL_env`):
    PYTHONPATH=app python experiments/benchmark/scripts/judge_runs.py [--runs-root outputs/runs] \
        [--min-age 10] [--json rows.json]                          # list only, writes nothing
    PYTHONPATH=app python experiments/benchmark/scripts/judge_runs.py --rejudge \
        --results judged.jsonl --logs logs/ [--workers 2]          # judge what needs it

`--runs-root` holds the `bench__*` experiment folders (default `outputs/runs` of this checkout).
Each `seed*` folder has a state: `finished` (has `summary.json`), `training` (has none) or
`archived` (a `.interrupted` or `.timed-out` suffix); and a judge format: `new` (its `judge.json`
has `machine_too_simple`), `old` (it has not) or `none` (no `judge.json`). A finished folder needs a
judge when its format is not `new`; a `none` folder only once its summary is `--min-age` minutes old,
because the training run may still judge it itself.

With `--rejudge`, for each such folder: keep `judge.json` as `judge.v1.json` (an existing
`judge.v1.json` is never overwritten), then run `test-rl --run <folder> --episodes 100 --judge
<experiment>/card.json` from this checkout. A failed judge is retried once, then recorded. A folder
that is not finished, already new, or judged by another `test-rl` is skipped. The judges run
`--workers` at a time with two threads each, and a new one starts only while at least 8 GB of memory
is available. Besides what `test-rl` writes, the only file added to a run folder is `judge.v1.json`.
`--results` gets one JSONL line per folder (`judged`, `failed` or `skipped`, attempts, seconds) and
`--logs` one log per folder.
"""

import argparse
import json
import os
import shutil
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from scripts.generate_suite import _run
from scripts.run_suite import RUNS_PATH

MIN_AVAILABLE_GB = 8
MEMORY_POLL_SECONDS = 15
JUDGE_ENV = {
    "PYTHONPATH": "app",
    "OMP_NUM_THREADS": "2",
    "MKL_NUM_THREADS": "2",
    "OPENBLAS_NUM_THREADS": "2",
    "PYTHONDONTWRITEBYTECODE": "1",
}
_results_lock = threading.Lock()


def age_minutes(path: Path) -> float:
    return round((time.time() - path.stat().st_mtime) / 60, 1)


def judge_format(judge: Path) -> str:
    """`new`, `old`, `none` or `unreadable` for a run folder's `judge.json`."""
    if not judge.exists():
        return "none"
    try:
        return "new" if "machine_too_simple" in json.loads(judge.read_text()) else "old"
    except ValueError:
        return "unreadable"


def classify(seed_dir: Path, min_age: float) -> dict:
    """One row for a seed folder: state, judge format, ages, and whether it needs a judge."""
    row = {"exp": seed_dir.parent.name, "seed_dir": seed_dir.name, "path": str(seed_dir)}
    if "interrupted" in seed_dir.name or "timed-out" in seed_dir.name:
        return {**row, "state": "archived", "needs_judge": False}
    summary = seed_dir / "summary.json"
    if not summary.exists():
        return {**row, "state": "training", "needs_judge": False}
    judge_file = seed_dir / "judge.json"
    judge = judge_format(judge_file)
    summary_age = age_minutes(summary)
    row |= {
        "state": "finished",
        "judge": judge,
        "judge_age_min": age_minutes(judge_file) if judge != "none" else None,
        "summary_age_min": summary_age,
        "has_judge_v1": (seed_dir / "judge.v1.json").exists(),
    }
    row["needs_judge"] = judge != "new" and (judge != "none" or summary_age >= min_age)
    return row


def inventory(runs_root: Path, min_age: float) -> list[dict]:
    """A row for every `seed*` folder under every experiment folder of ``runs_root``."""
    if not runs_root.is_dir():
        print(f"no runs folder at {runs_root}")
        return []
    return [
        classify(seed_dir, min_age)
        for exp in sorted(runs_root.iterdir())
        if exp.is_dir() and not exp.name.endswith(".lock")
        for seed_dir in sorted(exp.glob("seed*"))
        if seed_dir.is_dir()
    ]


def available_gb() -> float:
    """Memory available to new processes, from `/proc/meminfo` (the `free` available column)."""
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 1024**2
    raise RuntimeError("/proc/meminfo has no MemAvailable line")


def judging_elsewhere(folder: Path) -> bool:
    """Whether another process runs `test-rl --run <folder>` (reads Linux `/proc`).

    A path in its arguments counts however it is spelled: it is resolved against that process's
    working directory.
    """
    target = folder.resolve()
    for cmdline in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            argv = cmdline.read_bytes().split(b"\0")
            if b"test-rl" in argv and any(
                (cmdline.parent / "cwd" / os.fsdecode(arg)).resolve() == target for arg in argv
            ):
                return True
        except OSError:  # the process ended meanwhile, or its folders are not ours to read
            continue
    return False


def wait_for_memory(folder: Path) -> None:
    """Block until `MIN_AVAILABLE_GB` are available; say so once, so a wait does not look like a hang."""
    announced = False
    while (free := available_gb()) < MIN_AVAILABLE_GB:
        if not announced:
            print(
                f"waiting for {MIN_AVAILABLE_GB} GB, have {free:.1f}: {folder.parent.name} {folder.name}",
                flush=True,
            )
            announced = True
        time.sleep(MEMORY_POLL_SECONDS)


def judge_once(folder: Path, log: Path) -> int:
    """Run `test-rl` with the new judge on one folder, output appended to ``log``; return its exit code."""
    command = [
        sys.executable, "app/main.py", "test-rl", "--run", str(folder),
        "--episodes", "100", "--judge", str(folder.parent / "card.json"),
    ]  # fmt: skip
    return _run(command, log, append=True)


def skip_reason(folder: Path) -> str | None:
    if not (folder / "summary.json").exists():
        return "no summary.json (still training)"
    if judge_format(folder / "judge.json") == "new":
        return "already new format"
    if judging_elsewhere(folder):
        return "another test-rl is judging it"
    return None


def rejudge(folder: Path, results: Path, logs: Path) -> None:
    """Judge one folder (retrying once) and append its outcome to ``results``."""
    started = time.time()
    row = {"folder": str(folder), "exp": folder.parent.name, "seed_dir": folder.name}
    if reason := skip_reason(folder):
        row["status"] = f"skipped: {reason}"
    else:
        judge, v1 = folder / "judge.json", folder / "judge.v1.json"
        if judge.exists() and not v1.exists():
            shutil.copy2(judge, v1)
        log = logs / f"{folder.parent.name}__{folder.name}.log"
        row |= {"status": "failed", "attempts": 0}
        for attempt in (1, 2):
            wait_for_memory(folder)
            row |= {"attempts": attempt, "exit": judge_once(folder, log)}
            if row["exit"] == 0 and judge_format(judge) == "new":
                row["status"] = "judged"
                break
        row |= {"seconds": round(time.time() - started, 1), "had_v1": v1.exists()}
    with _results_lock, results.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--runs-root", type=Path, default=RUNS_PATH, help="folder of bench__*")
    parser.add_argument("--min-age", type=float, default=10.0, help="minutes before a no-judge run")
    parser.add_argument("--json", type=Path, help="write every row as JSON")
    parser.add_argument("--rejudge", action="store_true", help="judge the folders that need it")
    parser.add_argument("--results", type=Path, help="JSONL file to append (with --rejudge)")
    parser.add_argument("--logs", type=Path, help="folder for the logs (with --rejudge)")
    parser.add_argument("--workers", type=int, default=2, help="judges at once (with --rejudge)")
    args = parser.parse_args()
    if args.rejudge and not (args.results and args.logs):
        parser.error("--rejudge needs --results and --logs")

    rows = inventory(args.runs_root.resolve(), args.min_age)  # one spelling for every judge's argv
    if args.json:
        args.json.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    for row in rows:
        age = row.get("judge_age_min") or row.get("summary_age_min") or ""
        flag = "NEEDS JUDGE" if row["needs_judge"] else ""
        print(row["state"].ljust(9), row.get("judge", "-").ljust(10), str(age).rjust(7), end=" ")
        print(row["exp"], row["seed_dir"], flag)
    print(dict(Counter((row["state"], row.get("judge", "-")) for row in rows)))
    todo = [Path(row["path"]) for row in rows if row["needs_judge"]]
    print(f"{len(todo)} folders need a judge")
    if args.rejudge:
        os.environ.update(JUDGE_ENV)  # the `test-rl` children inherit it
        args.logs.mkdir(parents=True, exist_ok=True)
        with ThreadPoolExecutor(args.workers) as pool:
            list(pool.map(lambda folder: rejudge(folder, args.results, args.logs), todo))
        print(f"done {len(todo)} folders at {time.strftime('%H:%M:%S')}")


if __name__ == "__main__":
    main()
