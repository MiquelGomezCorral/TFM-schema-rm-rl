"""Shared paths and run lookup of the shop-ground-up run tools (make_runs, scheduler, watch, judge).

``runs.json`` (written by make_runs.py) lists every run; a tool takes a round name (``r1``, ``r2``,
``dry``, ``all``) or exact run names and gets the matching entries. Run folders are looked up
under ``RUNS_ROOT`` (the worktree's ``outputs/runs`` unless ``SGU_RUNS_ROOT`` is set).
"""

import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKTREE = Path(
    os.environ.get(
        "SGU_WORKTREE", "/home/turbotowerlnx/orca/workspaces/TFM-schema-rm-rl/tp-shop-ground-up"
    )
)
RUNS_ROOT = Path(os.environ.get("SGU_RUNS_ROOT", WORKTREE / "outputs/runs"))
CARDS = HERE / "cards"
CONFIGS = HERE / "configs"
LOGS = HERE / "logs"
PIDS = HERE / "pids"
ROUNDS = ("r1", "r2", "dry")


def load_runs() -> list[dict]:
    return json.loads((HERE / "runs.json").read_text(encoding="utf-8"))


def select(names: list[str]) -> list[dict]:
    """The runs of the given rounds (``all`` = every round) and exact run names, in file order."""
    runs = load_runs()
    known = {run["name"] for run in runs}
    unknown = [name for name in names if name not in (*ROUNDS, "all", *known)]
    if unknown:
        raise SystemExit(f"unknown run or round: {', '.join(unknown)}")
    return [run for run in runs if "all" in names or run["round"] in names or run["name"] in names]


def run_folder(name: str) -> Path | None:
    """The newest ``seed*-*`` folder of a run (archived ``<folder>.<status>`` ones are skipped)."""
    folders = sorted(
        folder
        for folder in (RUNS_ROOT / name).glob("seed*-*")
        if folder.is_dir() and "." not in folder.name
    )
    return folders[-1] if folders else None


def is_finished(folder: Path | None) -> bool:
    return folder is not None and (folder / "summary.json").is_file()


def pid_alive(name: str) -> bool:
    """Whether the process in the run's pid file is a live ``train-rl`` of this run."""
    try:
        pid = int((PIDS / f"{name}.pid").read_text().strip())
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
    except (OSError, ValueError):
        return False
    return b"train-rl" in cmdline and f"{name}.yaml".encode() in cmdline
