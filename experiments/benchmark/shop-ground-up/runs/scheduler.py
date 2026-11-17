"""Start shop-ground-up runs from the worktree, a few at a time, and print their run folders.

Usage:  python scheduler.py <r1|r2|dry|all|run name> [...]   (run with the RM_RL_env python)
Env:    SGU_MAX_ALIVE (default 11), SGU_MIN_AVAIL_GB (default 8), SGU_STAGGER_SECONDS (default 20),
        SGU_WORKTREE, SGU_RUNS_ROOT

For each run: skipped when its process is alive or its run folder is finished; refused when its bundle
lacks a file training needs; otherwise it waits until fewer than MAX_ALIVE of this tool's runs are alive
and free RAM is at least MIN_AVAIL_GB, then starts
``cd <worktree> && OMP_NUM_THREADS=2 PYTHONPATH=app python app/main.py train-rl --config <yaml> --seed <n>``
in its own session (it outlives this tool and the shell), log in ``logs/<run>.log``, PID in ``pids/<run>.pid``,
then pauses STAGGER seconds so its memory shows before the next start.
Only a run's own pid file counts as alive, and nothing here ever signals a process.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

from sgu import LOGS, PIDS, WORKTREE, is_finished, pid_alive, run_folder, select

MAX_ALIVE = int(os.environ.get("SGU_MAX_ALIVE", 11))
MIN_AVAIL_GB = float(os.environ.get("SGU_MIN_AVAIL_GB", 8))
STAGGER_SECONDS = float(os.environ.get("SGU_STAGGER_SECONDS", 20))
POLL_SECONDS = 30
FOLDER_WAIT_SECONDS = 90
# What training reads from a bundle (the files run-suite checks).
BUNDLE_FILES = (
    "manifest.json",
    "reward_machine.txt",
    "labeling.py",
    "state_descriptions.json",
    "embeddings.json",
)


def available_gb() -> float:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable"):
            return int(line.split()[1]) / 1e6
    return 0.0


def alive_count(names: list[str]) -> int:
    return sum(pid_alive(name) for name in names)


def bundle_problem(run: dict) -> str | None:
    if run["bundle"] is None:
        return None
    missing = [name for name in BUNDLE_FILES if not (Path(run["bundle"]) / name).is_file()]
    return f"bundle {run['bundle']} lacks {', '.join(missing)}" if missing else None


def wait_for_slot(all_names: list[str], label: str) -> None:
    waiting = False
    while alive_count(all_names) >= MAX_ALIVE or available_gb() < MIN_AVAIL_GB:
        if not waiting:
            print(f"{time.strftime('%H:%M:%S')} waiting for {label}", flush=True)
            waiting = True
        time.sleep(POLL_SECONDS)


def start(run: dict) -> int:
    """Start one train-rl process and return its pid."""
    LOGS.mkdir(exist_ok=True)
    PIDS.mkdir(exist_ok=True)
    command = [
        sys.executable,
        "app/main.py",
        "train-rl",
        "--config",
        run["config"],
        "--seed",
        str(run["seed"]),
    ]
    env = {**os.environ, "OMP_NUM_THREADS": "2", "PYTHONPATH": "app", "PYTHONUNBUFFERED": "1"}
    with (LOGS / f"{run['name']}.log").open("a", encoding="utf-8") as log:
        process = subprocess.Popen(  # noqa: S603  approved: fixed argv built here, no shell
            command,
            cwd=WORKTREE,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    (PIDS / f"{run['name']}.pid").write_text(f"{process.pid}\n", encoding="utf-8")
    return process.pid


def folder_of(run: dict, pid: int) -> Path | None:
    """The run folder train-rl made for this process (its name ends with the pid)."""
    deadline = time.monotonic() + FOLDER_WAIT_SECONDS
    while time.monotonic() < deadline:
        folder = run_folder(run["name"])
        if folder is not None and folder.name.endswith(f"-{pid}"):
            return folder
        time.sleep(2)
    return None


def main(names: list[str]) -> None:
    if not names:
        raise SystemExit(__doc__)
    runs = select(names)
    all_names = [run["name"] for run in select(["all"])]
    refused = []
    for run in runs:
        name = run["name"]
        if pid_alive(name) or is_finished(run_folder(name)):
            print(f"skip {name}: {'alive' if pid_alive(name) else 'finished'}", flush=True)
            continue
        problem = bundle_problem(run)
        if problem:
            print(f"REFUSED {name}: {problem}", flush=True)
            refused.append(name)
            continue
        wait_for_slot(all_names, name)
        pid = start(run)
        folder = folder_of(run, pid)
        print(
            f"started {name} pid {pid} -> {folder or 'no run folder yet, see logs/' + name + '.log'}",
            flush=True,
        )
        time.sleep(STAGGER_SECONDS)
    print(
        f"done: {len(runs) - len(refused)} handled, {len(refused)} refused {refused or ''}",
        flush=True,
    )


if __name__ == "__main__":
    main(sys.argv[1:])
