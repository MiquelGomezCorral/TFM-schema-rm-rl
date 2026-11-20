"""How a proposition's label behaves on a run's test traces: steps true, and runs of true steps.

Usage: python label_runs.py RUN_FOLDER PROPOSITION [PROPOSITION ...]
Prints, per proposition, the totals over every agent-traces/ep<k>.json and the 1/0 series of the
first episodes where it is ever true.
"""

import json
import sys
from pathlib import Path


def runs(series: list[bool]) -> int:
    """Number of runs of consecutive true steps."""
    return sum(1 for i, value in enumerate(series) if value and (i == 0 or not series[i - 1]))


def main() -> None:
    folder, names = Path(sys.argv[1]), sys.argv[2:]
    traces = sorted((folder / "agent-traces").glob("ep*.json"), key=lambda p: int(p.stem[2:]))
    for name in names:
        steps_true = total_runs = shown = 0
        for path in traces:
            labels = json.loads(path.read_text(encoding="utf-8"))["labels"]
            series = [bool(step.get(name, False)) for step in labels]
            steps_true += sum(series)
            total_runs += runs(series)
            if any(series) and shown < 3:
                shown += 1
                text = "".join("1" if value else "0" for value in series)
                print(f"  {name} {path.stem} ({len(series)} steps): {text}")
        print(f"{name}: {len(traces)} episodes, {steps_true} steps true, {total_runs} runs of true")


if __name__ == "__main__":
    main()
