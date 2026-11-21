"""The judge's soft-break count against the compiled machine's soft-break charges (D8, 2026-11-21).

For each DECLARE template: compile a one-clause soft machine from the LTLf the pipeline gives it
(MONA through FL-AT, today's reward layer with its default structure switches), walk random label
traces through the serialized machine, and compare its soft-break charges with the judge's
``breaks``. Only the soft-break charge pays, so each charge is one ``-soft_break_cost`` step.
The old judge count (a break lasts while the labels stay as on the break step) is shown beside it.
No model call.

Run from the worktree: ``env -C WT PYTHONPATH=app PY <this file> [traces per template] [seed]``.
"""

import random
import sys
from itertools import zip_longest

from flat_tool import compile_dfa

from src.arm_fm.runtime import RewardMachineRuntime
from src.benchmark.declare_judge import BROKEN, LTLF_DISPLAY, RULES, judge_clause, ltlf_of
from src.compiler import parse_paper_reward_machine, serialize_reward_machine
from src.compiler.reward_layer import RewardSwitches, build_reward_machine
from src.config import Configuration

SWITCHES = RewardSwitches(
    reward_progress=False, reward_well=False, reward_soft_pending=False, hard_ceiling=False
)
# The supervisor's examples (docs/COMPILER_REWARD_DESIGN.md, recurrent soft rules) and the cases
# the old count read as one break: (template, a, b) as step strings, "1" true.
FIXED = (
    ("Absence", "11", ""),
    ("Absence", "101", ""),
    ("Absence", "111", ""),
    ("Absence", "1011", ""),
    ("Precedence", "100", "011"),
    ("Precedence", "0001", "1010"),
    ("Precedence", "00", "11"),
    ("ChainResponse", "10", "01"),
    ("ChainResponse", "1010", "0000"),
    ("ChainResponse", "110", "000"),
    ("ChainResponse", "1110", "0000"),
    ("NotCoExistence", "10", "01"),
    ("NotCoExistence", "101", "010"),
    ("NotCoExistence", "1010", "0101"),
    ("NotCoExistence", "11", "11"),
)


def old_count(template: str, a: list[bool], b: list[bool]) -> int:
    """The judge's count before D8, copied from ``_break_count`` at commit 23ac6dd."""
    rule, count, start = RULES[template], 0, 0
    steps = list(zip_longest(a, b))
    while True:
        status, step = rule(a[start:], b[start:])
        if status != BROKEN:
            return count
        count += 1
        broken = start + step - 1
        start = next(
            (i for i in range(broken + 1, len(steps)) if steps[i] != steps[broken]), len(steps)
        )


def machine_for(template: str, CONFIG: Configuration) -> RewardMachineRuntime:
    names = ("a", "b")[: LTLF_DISPLAY[template][0]]
    raw = ltlf_of((template, names, "soft"))["raw"]
    dfa = compile_dfa(raw, mona_executable=CONFIG.mona_executable)
    machine = build_reward_machine([dfa], [True], SWITCHES).reward_machine
    parsed = parse_paper_reward_machine(serialize_reward_machine(machine), propositions=names)
    return RewardMachineRuntime(parsed)


def machine_charges(runtime: RewardMachineRuntime, labels: list[dict[str, bool]]) -> int:
    runtime.reset()
    charges = 0
    for step in labels:
        reward = runtime.step(step).reward
        assert reward in (0.0, -SWITCHES.soft_break_cost), f"unexpected step reward {reward}"
        charges += reward != 0.0
    return charges


def labels_of(a: list[bool], b: list[bool]) -> list[dict[str, bool]]:
    if not b:
        return [{"a": value} for value in a]
    return [{"a": x, "b": y} for x, y in zip(a, b, strict=True)]


def compare(template: str, runtime: RewardMachineRuntime, a: list[bool], b: list[bool]) -> tuple:
    names = ("a", "b")[: LTLF_DISPLAY[template][0]]
    labels = labels_of(a, b)
    judged = judge_clause((template, names, "soft"), labels).breaks
    return judged, machine_charges(runtime, labels), old_count(template, a, b)


def main(traces: int, seed: int) -> None:
    CONFIG = Configuration()
    rng = random.Random(seed)
    mismatches = 0
    print(f"{traces} random traces per template (length 1-12, P(true)=0.4), seed {seed}")
    print("template            traces  with_charge  max  judge!=machine  old!=machine")
    for template in LTLF_DISPLAY:
        runtime = machine_for(template, CONFIG)
        two = LTLF_DISPLAY[template][0] == 2
        rows = [
            ([c == "1" for c in a], [c == "1" for c in b]) for t, a, b in FIXED if t == template
        ]
        for _ in range(traces):
            length = rng.randint(1, 12)
            a = [rng.random() < 0.4 for _ in range(length)]
            b = [rng.random() < 0.4 for _ in range(length)] if two else []
            rows.append((a, b))

        results = [compare(template, runtime, a, b) for a, b in rows]
        bad = [(row, res) for row, res in zip(rows, results, strict=True) if res[0] != res[1]]
        old_bad = sum(1 for res in results if res[2] != res[1])
        charged = sum(1 for res in results if res[1])
        top = max(res[1] for res in results)
        print(
            f"{template:<19} {len(rows):>6}  {charged:>11}  {top:>3}  {len(bad):>14}  {old_bad:>12}"
        )
        for (a, b), (judged, charges, _) in bad[:3]:
            print(f"  mismatch a={a} b={b}: judge {judged}, machine {charges}")
        mismatches += len(bad)

    print(
        "RESULT:",
        "judge == machine on every trace" if not mismatches else f"{mismatches} mismatches",
    )
    for template, a, b in FIXED:
        runtime = machine_for(template, CONFIG)
        judged, charges, old = compare(
            template, runtime, [c == "1" for c in a], [c == "1" for c in b]
        )
        print(
            f"  {template}({a}{',' + b if b else ''}): judge {judged}, machine {charges}, old {old}"
        )


if __name__ == "__main__":
    main(
        int(sys.argv[1]) if len(sys.argv) > 1 else 300, int(sys.argv[2]) if len(sys.argv) > 2 else 7
    )
