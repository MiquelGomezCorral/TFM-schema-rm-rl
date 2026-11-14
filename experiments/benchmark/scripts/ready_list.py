"""Ready list: which generated bundles are complete and trainable now. Read-only.

Usage (repository root, `RM_RL_env`):
    PYTHONPATH=app python experiments/benchmark/scripts/ready_list.py --output <dir> \
        [--root experiments/benchmark] [--suite NAME ...]

A bundle is ready when `ArtifactBundle.load(path)` and `validate(require_complete=True)` pass: the
calls training makes. Reads `<root>/<suite>/bundles/<arm>/<name>/` for every suite (or the named
ones; an ablation's `<card>/off-<switch>` bundles count as arm `ablation`). Prints ready counts per
suite and arm and writes `<output>/ready-list.md` (per card, with the reason a bundle is not
ready) and `<output>/ready-list.json` (per bundle). Safe to rerun; it overwrites both files.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from src.arm_fm import ArtifactBundle
from src.benchmark.labeling_repair import status_path
from src.benchmark.traces import find_bundles
from src.config import Configuration


def bundle_rows(root: Path, suites: list[str]) -> list[dict]:
    """One row per bundle: suite, arm, card, bundle name, ready, generation status, why not."""
    rows = []
    for suite in suites:
        for ref in find_bundles(root / suite / "bundles"):
            status_file = status_path(ref.path)
            status = (
                json.loads(status_file.read_text())["status"] if status_file.is_file() else None
            )
            try:
                ArtifactBundle.load(ref.path).validate(require_complete=True)
                ready, why = True, ""
            except Exception as error:  # any load or validation failure means not trainable
                ready, why = False, f"{type(error).__name__}: {error}"[:220]
            arm, card = ("ablation", ref.arm) if ref.ablation else (ref.arm, ref.name.split("~")[0])
            rows.append(
                {
                    "suite": suite,
                    "arm": arm,
                    "card": card,
                    "bundle": ref.name,
                    "ready": ready,
                    "status": status,
                    "why_not": why,
                }
            )
    return rows


def per_card_table(rows: list[dict]) -> str:
    """The Markdown table: ready bundles out of all, per suite, arm and card."""
    cards = defaultdict(lambda: {"ready": 0, "total": 0, "not_ready": []})
    for row in rows:
        entry = cards[(row["suite"], row["arm"], row["card"])]
        entry["total"] += 1
        entry["ready"] += row["ready"]
        if not row["ready"]:
            entry["not_ready"].append(f"{row['bundle']} ({row['why_not']})")
    lines = ["| suite | arm | card | ready / bundles | not ready |", "|---|---|---|---|---|"]
    for (suite, arm, card), entry in sorted(cards.items()):
        not_ready = "; ".join(entry["not_ready"]) or "-"
        lines.append(
            f"| {suite} | {arm} | {card} | {entry['ready']}/{entry['total']} | {not_ready} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--output", type=Path, required=True, help="folder for the two files")
    parser.add_argument(
        "--root",
        type=Path,
        default=Configuration.WORKSPACE_PATH / "experiments/benchmark",
        help="folder of suites (default: this checkout's experiments/benchmark)",
    )
    parser.add_argument("--suite", nargs="+", help="only these suites (default: every suite)")
    args = parser.parse_args()

    suites = args.suite or sorted(path.parent.name for path in args.root.glob("*/bundles"))
    rows = bundle_rows(args.root, suites)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "ready-list.md").write_text(per_card_table(rows), encoding="utf-8")
    (args.output / "ready-list.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    for suite, arm in sorted({(row["suite"], row["arm"]) for row in rows}):
        chosen = [row for row in rows if row["suite"] == suite and row["arm"] == arm]
        print(f"{suite} {arm}: ready {sum(row['ready'] for row in chosen)}/{len(chosen)}")
    print(f"wrote {args.output / 'ready-list.md'} and {args.output / 'ready-list.json'}")


if __name__ == "__main__":
    main()
