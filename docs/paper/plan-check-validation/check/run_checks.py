"""Run `check-plans` on every set/suite folder of S/copies with a given app tree, at most 4 at once.

Usage (cwd = the main checkout): python run_checks.py S_DIR APP_DIR LOG_DIR
APP_DIR is the app/ folder whose main.py and src/ run (e.g. S/code-e6c3acb/app, or app for main).
Each check-plans run is one process; outputs go to LOG_DIR/<set>-<suite>.txt.
"""

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MAX_PROCESSES = 4  # the packet's RAM limit


def run(app: Path, folder: Path, log_dir: Path) -> str:
    suite, set_name = folder.name, folder.parent.name
    env = {
        **os.environ,
        "PYTHONPATH": str(app),
        "PYTHONDONTWRITEBYTECODE": "1",
        "OMP_NUM_THREADS": "1",
    }
    argv = [
        sys.executable,
        str(app / "main.py"),
        "check-plans",
        "--tasks",
        f"experiments/benchmark/{suite}/tasks.json",
        "--bundles",
        str(folder),
    ]
    done = subprocess.run(argv, capture_output=True, text=True, env=env, check=False)  # noqa: S603  fixed argv, no shell
    (log_dir / f"{set_name}-{suite}.txt").write_text(done.stdout + done.stderr, encoding="utf-8")
    return f"{set_name}/{suite}: exit {done.returncode}, {done.stdout.strip().splitlines()[-1] if done.stdout.strip() else ''}"


def main() -> None:
    study, app, log_dir = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    log_dir.mkdir(parents=True, exist_ok=True)
    folders = sorted(p for p in (study / "copies").glob("*/*") if p.is_dir())
    with ThreadPoolExecutor(MAX_PROCESSES) as pool:
        for line in pool.map(lambda folder: run(app, folder, log_dir), folders):
            print(line)


if __name__ == "__main__":
    main()
