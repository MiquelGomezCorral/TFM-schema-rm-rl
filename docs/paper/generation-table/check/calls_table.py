"""Generation calls per bundle, by suite and arm, from the `<bundle>.status.json` beside each bundle.

`generation-table` has no calls column; `generate-suite` writes the call count of the bundle's last
generation run into its status file. A bundle without that field is left out and counted as missing.
Run from the repository root:

    python3 -I docs/paper/generation-table/check/calls_table.py experiments/benchmark
"""

import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean


def main(root: Path) -> None:
    calls: dict[tuple[str, str], list[int]] = defaultdict(list)
    missing: dict[tuple[str, str], int] = defaultdict(int)
    for path in sorted(root.glob("*/bundles/*/*.status.json")):
        suite, arm = path.parts[-4], path.parts[-2]
        value = json.loads(path.read_text(encoding="utf-8")).get("calls")
        if isinstance(value, int):
            calls[(suite, arm)].append(value)
        else:
            missing[(suite, arm)] += 1
    print(
        "| suite | arm | bundles with calls | calls in all | mean calls per bundle | status without calls |"
    )
    print("|---|---|---|---|---|---|")
    for key in sorted(set(calls) | set(missing)):
        values = calls[key]
        mean_text = f"{mean(values):.1f}" if values else "-"
        print(
            f"| {key[0]} | {key[1]} | {len(values)} | {sum(values)} | {mean_text} | {missing[key]} |"
        )


if __name__ == "__main__":
    main(Path(sys.argv[1]))
