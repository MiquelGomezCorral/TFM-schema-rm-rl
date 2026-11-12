"""Shared helpers of the C2 reproductions: paths, the phase argument and the verdict file.

Usage of every script: ``PYTHONPATH=app python <script> before|after``. The verdict goes to
``outputs/wave-tests/c2-review-fix/<phase>/<name>.json`` and is printed; ``pass`` is true when
the behaviour is the fixed one.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "outputs" / "wave-tests" / "c2-review-fix"
REVIEW = ROOT / "outputs" / "wave-tests" / "final-review"
PYTHON = sys.executable
PHASE = sys.argv[1]


def work_dir(name: str) -> Path:
    """A clean scratch folder for one script, inside the phase's output folder."""
    path = OUT / PHASE / f"{name}-work"
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def main_py(*arguments: str) -> subprocess.CompletedProcess:
    """Run ``python app/main.py ...`` from the repository root and capture its output."""
    return subprocess.run(  # noqa: S603  fixed argv, no shell
        [PYTHON, "app/main.py", *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def save(name: str, verdict: dict) -> None:
    """Write and print the verdict of one finding."""
    path = OUT / PHASE / f"{name}.json"
    path.write_text(json.dumps(verdict, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(verdict, indent=2, default=str))
    print(f"-> {path}")
