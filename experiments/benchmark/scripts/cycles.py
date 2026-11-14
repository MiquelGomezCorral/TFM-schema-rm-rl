"""Positive reward cycles of ARM-FM Reward Machines. Read-only, no provider call.

Usage (repository root, `RM_RL_env`):
    PYTHONPATH=app python experiments/benchmark/scripts/cycles.py \
        [--root experiments/benchmark] [--suite NAME ...] [--card NAME ...] [--output cycles.md]

A lap is a simple cycle of the machine (a self-loop counts) whose rewards add to more than zero:
an agent can loop it for reward without finishing the task. An edge is `(source, guard) ->
destination` from TRANSITION_FUNCTION with its REWARD_FUNCTION entry (0 when it has none). Final
states count: the runtime pays per firing and does not stop a cycle there unless the environment
ends. Reads `<root>/<suite>/bundles/arm-fm/<card>/reward_machine.txt` for every suite and card
(or the named ones) and writes a Markdown table, one row per card, to `--output` or the terminal.
`results_table.py` imports `positive_cycles` to flag cards in its tables.
"""

import argparse
from pathlib import Path

from src.benchmark.traces import find_bundles
from src.compiler.rm_format import PaperRewardMachine, parse_paper_reward_machine
from src.config import Configuration

REWARD_EPSILON = 1e-9
NO_VALUE = chr(0x2013)  # an en dash, the placeholder of the earlier tables


def positive_cycles(machine: PaperRewardMachine) -> list[tuple[str, float, str]]:
    """Distinct positive-reward laps as (``u0 -> u1 -> u0``, net reward, guard of the closing edge).

    Sorted by reward, largest first, then by path. Each lap is found once, from its smallest state in the
    machine's state order.
    """
    order = {state: index for index, state in enumerate(machine.states)}
    found: set[tuple[str, float, str]] = set()

    def walk(start: str, node: str, path: list[str], total: float) -> None:
        for edge in machine.transitions:
            if edge.source != node:
                continue
            gain = total + edge.reward
            if edge.destination == start:
                found.add((" -> ".join([*path, start]), round(gain, 4), edge.condition.strip()))
            elif order[edge.destination] > order[start] and edge.destination not in path:
                walk(start, edge.destination, [*path, edge.destination], gain)

    for state in machine.states:
        walk(state, state, [state], 0.0)
    positive = (lap for lap in found if lap[1] > REWARD_EPSILON)
    return sorted(positive, key=lambda lap: (-lap[1], lap[0], lap[2]))


def card_row(name: str, reward_machine: Path) -> str:
    """One table row: whether the card has a positive cycle, and which."""
    if not reward_machine.is_file():
        return f"| {name} | no machine | {NO_VALUE} |"
    laps = positive_cycles(parse_paper_reward_machine(reward_machine.read_text(encoding="utf-8")))
    if not laps:
        return f"| {name} | no | {NO_VALUE} |"
    return f"| {name} | **yes** | " + "; ".join(f"{p} ({g}) = +{t:g}" for p, t, g in laps) + " |"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=Configuration.WORKSPACE_PATH / "experiments/benchmark",
        help="folder of suites (default: this checkout's experiments/benchmark)",
    )
    parser.add_argument("--suite", nargs="+", help="only these suites (default: every suite)")
    parser.add_argument("--card", nargs="+", help="only these bundle names (default: every one)")
    parser.add_argument("--output", type=Path, help="Markdown file to write (default: print)")
    args = parser.parse_args()

    suites = args.suite or sorted(path.parent.name for path in args.root.glob("*/bundles"))
    lines = [
        "| card | positive reward cycle | cycle (states, guard of the closing edge)"
        " and net reward per lap |",
        "|---|---|---|",
    ]
    for suite in suites:
        for ref in find_bundles(args.root / suite / "bundles"):
            if ref.arm == "arm-fm" and (not args.card or ref.name in args.card):
                lines.append(card_row(ref.name, ref.rm_path))
    table = "\n".join(lines) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(table, encoding="utf-8")
        print(f"wrote {len(lines) - 2} rows to {args.output}")
    else:
        print(table, end="")


if __name__ == "__main__":
    main()
