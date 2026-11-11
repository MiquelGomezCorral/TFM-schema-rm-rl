"""One to-do list for every Reward Machine: progress per clause, end judgment, charged wells.

Run from the repository root, inside RM_RL_env (no LLM calls; MONA and FL-AT run locally). It
prints the checks and writes the new RM texts to `rm/s3-ex*.txt` and `rm/thesis-ex2-after.txt`:

    PYTHONPATH=app:docs/paper/rule-only-progress/check python -W ignore \
        docs/paper/rule-only-rewards/check/todo_list_check.py

Each state is a to-do list: every clause owes the steps its own DFA still needs, a step done pays
+0.1, a new item or a step back costs -0.1, and an episode the environment ends with items open
is charged per item (-1 hard, -0.5 soft; a goal is hard). An edge into the well pays -1 plus the
same charge of the state it leaves. Compiles the three examples of Slice 2 that the old longest
path priced badly, and thesis example 2 ("Reach the goal. If the key is dropped, pick it up right
away."), with the helpers of `rule-only-progress/check/end_judgment_check.py`, and for each:

- prints every edge's reward in the old machine (`rm/s2-ex*.txt`, `rm/thesis-ex2-before.txt`) and
  in the new one;
- asserts the table of changed and unchanged edges;
- asserts that every reward off the final and the well is a potential difference, so every loop
  sums to 0, and that each event loop pays -x one way and +x the other;
- asserts that every edge into the well pays -1 plus the end charge of its source state;
- writes the new RM text (`rm/s3-ex*.txt`, `rm/thesis-ex2-after.txt`).

Then plays the end judgment of example 5 and the time limit of thesis example 2 through
`RewardMachineEnvironment` with the time limit after the last step. Exits 1 on any difference.
"""

import sys
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import NamedTuple

import end_judgment_check as box
from window_check import step_rewards

from src.compiler import parse_paper_reward_machine, serialize_paper_reward_machine
from src.config import Configuration

RM_DIR = Path(__file__).resolve().parents[1] / "rm"
EPSILON = 1e-9


class Example(NamedTuple):
    name: str
    task: str
    clauses: list[tuple[str, list[str], str]]
    phi: dict[str, float]  # what each state owes, as a (negative) potential
    table: dict[tuple[str, str], set[tuple[float, float]]]  # (source, destination): {(old, new)}
    loops: int  # how many state pairs have an edge each way
    old_file: str  # the machine as the old code built it, in `rm/`
    new_file: str  # where the new machine is written, in `rm/`


EXAMPLES = [
    Example(
        "ex3",
        "Whenever the box falls off the shelf, put it back. Preferably pick up the key at some point.",
        [("Response", ["box_fell", "box_on_shelf"], "hard"), ("Existence", ["has_key"], "soft")],
        {"u0": -0.1, "u1": 0, "u2": -0.2, "u3": -0.1},
        {
            ("u0", "u1"): {(0.2, 0.1)},
            ("u0", "u2"): {(0, -0.1)},
            ("u0", "u3"): {(0.1, 0)},
            ("u1", "u3"): {(-0.1, -0.1)},
            ("u2", "u0"): {(0, 0.1)},
            ("u2", "u1"): {(0.2, 0.2)},
            ("u2", "u3"): {(0.1, 0.1)},
            ("u3", "u1"): {(0.1, 0.1)},
        },
        2,
        "s2-ex3.txt",
        "s3-ex3.txt",
    ),
    Example(
        "ex4",
        "When the alarm rings, switch it off at the very next step. Preferably, if the power ever "
        "goes out, run the generator.",
        [
            ("ChainResponse", ["alarm_rings", "alarm_off"], "hard"),
            ("RespondedExistence", ["power_cut", "generator_on"], "soft"),
        ],
        {"u0": 0, "u1": -0.1, "u2": 0, "u3": -0.1, "u4": -0.2, "u5": -0.1},
        {
            ("u0", "u1"): {(-0.2, -0.1)},
            ("u0", "u2"): {(0, 0)},
            ("u0", "u3"): {(-0.3, -0.1)},
            ("u0", "u4"): {(-0.2, -0.2)},
            ("u0", "u5"): {(-0.1, -0.1)},
            ("u1", "u2"): {(0.2, 0.1)},
            ("u1", "u4"): {(0, -0.1)},
            ("u1", "u5"): {(0.1, 0)},
            ("u2", "u5"): {(-0.1, -0.1)},
            ("u3", "u0"): {(0.3, 0.1)},
            ("u3", "u1"): {(0.1, 0)},
            ("u3", "u2"): {(0.3, 0.1)},
            ("u3", "u4"): {(0.1, -0.1)},
            ("u3", "u5"): {(0.2, 0)},
            ("u3", "u6"): {(-1, -2)},
            ("u4", "u1"): {(0, 0.1)},
            ("u4", "u2"): {(0.2, 0.2)},
            ("u4", "u5"): {(0.1, 0.1)},
            ("u4", "u6"): {(-1, -2.5)},
            ("u5", "u2"): {(0.1, 0.1)},
            ("u5", "u6"): {(-1, -2)},
        },
        3,
        "s2-ex4.txt",
        "s3-ex4.txt",
    ),
    Example(
        "ex5",
        "Open the door. Whenever the box falls off the shelf, preferably put it back.",
        [("Existence", ["door_open"], "hard"), ("Response", ["box_fell", "box_on_shelf"], "soft")],
        {"u0": -0.1, "u2": -0.2},
        {
            ("u0", "u1"): {(1.1, 1.1), (0.6, 0.6)},
            ("u0", "u2"): {(0, -0.1)},
            ("u2", "u0"): {(0, 0.1)},
            ("u2", "u1"): {(0.6, 0.7), (1.1, 1.2)},
        },
        1,
        "s2-ex5.txt",
        "s3-ex5.txt",
    ),
    Example(
        "thesis-ex2",
        "Reach the goal. If the key is dropped, pick it up right away.",
        [("Existence", ["at_goal"], "hard"), ("ChainResponse", ["key_lost", "has_key"], "hard")],
        {"u0": -0.1, "u1": -0.2, "u3": -0.1},
        {
            ("u0", "u1"): {(0, -0.1)},
            ("u1", "u0"): {(0, 0.1)},
            ("u0", "u2"): {(1.2, 1.1)},
            ("u0", "u3"): {(0.1, 0)},
            ("u1", "u2"): {(1.2, 1.2)},
            ("u1", "u3"): {(0.1, 0.1)},
            ("u3", "u2"): {(1.1, 1.1)},
            ("u1", "u4"): {(-1, -3)},
            ("u3", "u4"): {(-1, -2)},
        },
        1,
        "thesis-ex2-before.txt",
        "thesis-ex2-after.txt",
    ),
]

# The goal task at the time limit: trace -> (step rewards with the end judgment, with the flat -0.5).
# A token lists the propositions true in a step, joined by "+"; "-" is a step with none.
END_JUDGMENT = {
    "-": ([-1.0], [-0.5]),
    "box_fell -": ([-0.1, -1.5], [-0.1, -0.5]),
    "box_fell box_on_shelf -": ([-0.1, 0.1, -1.0], [-0.1, 0.1, -0.5]),
    "door_open": ([1.1], [1.1]),
    "box_fell door_open": ([-0.1, 0.7], [-0.1, 0.7]),
    "box_fell box_on_shelf+door_open": ([-0.1, 1.2], [-0.1, 1.2]),
}
# Thesis example 2 at the time limit: trace -> step rewards. Timing out in u1 costs -2 (two hard
# items open) and breaking there costs -3; in u3 timing out costs -1 and breaking costs -2.
THESIS_TIME_LIMIT = {
    "-": [-1.0],
    "key_lost": [-2.1],
    "key_lost -": [-0.1, -3.0],
    "at_goal+key_lost": [-1.0],
    "at_goal+key_lost -": [0.0, -2.0],
}
# Walks into the final, as the old machine paid them: the total must not change.
OLD_WALK_TOTALS = {"box_fell door_open": 0.6, "box_fell box_on_shelf+door_open": 1.1}


def tidy(value: float) -> float:
    return round(value, 9) + 0.0


def edge_rewards(machine: box.PaperRewardMachine) -> dict[tuple[str, str, str], float]:
    return {(t.source, t.condition, t.destination): t.reward for t in machine.transitions}


def compare_edges(
    example: Example, old: box.PaperRewardMachine, new: box.PaperRewardMachine
) -> list[str]:
    """Print every edge, old and new; return the edges that differ from the example's table."""
    before, after = edge_rewards(old), edge_rewards(new)
    if before.keys() != after.keys():
        return [f"{example.name}: the old and the new machine do not have the same edges"]
    seen = defaultdict(set)
    for source, guard, destination in sorted(after, key=lambda key: (key[0], key[2], key[1])):
        old_reward, new_reward = (
            before[source, guard, destination],
            after[source, guard, destination],
        )
        print(f"  {source} -> {destination}  {guard:62} old {old_reward:>5g}  new {new_reward:>5g}")
        seen[source, destination].add((tidy(old_reward), tidy(new_reward)))
    return [
        f"{example.name} {pair[0]} -> {pair[1]}: {seen.get(pair)} != {want}"
        for pair, want in example.table.items()
        if seen.get(pair) != want
    ] + [f"{example.name} {pair}: not in the table" for pair in seen.keys() - example.table.keys()]


def potential_problems(example: Example, machine: box.PaperRewardMachine) -> list[str]:
    """Every reward off the final and the well must be the difference of the states' potentials."""
    ended = {*machine.final_states, *machine.rejecting_states}
    return [
        f"{example.name} {t.source} -> {t.destination}: {t.reward} is not a potential difference"
        for t in machine.transitions
        if t.destination not in ended
        and abs(t.reward - (example.phi[t.destination] - example.phi[t.source])) > EPSILON
    ]


def well_problems(example: Example, machine: box.PaperRewardMachine) -> list[str]:
    """An edge into the well pays the well reward plus the end charge of the state it leaves."""
    return [
        f"{example.name} {t.source} -> {t.destination}: {t.reward} is not the well charge"
        for t in machine.transitions
        if t.destination in machine.rejecting_states
        and abs(t.reward - (Configuration.WELL_REWARD + machine.judgment.end_charge(t.source)))
        > EPSILON
    ]


def loop_problems(example: Example, machine: box.PaperRewardMachine) -> list[str]:
    """Each pair of states with an edge each way must pay -x one way and +x the other."""
    ended = {*machine.final_states, *machine.rejecting_states}
    pays = defaultdict(set)
    for t in machine.transitions:
        if not {t.source, t.destination} & ended:
            pays[t.source, t.destination].add(tidy(t.reward))
    loops = sorted((a, b) for a, b in pays if a < b and (b, a) in pays)
    problems = [] if len(loops) == example.loops else [f"{example.name}: loops {loops}"]
    for a, b in loops:
        print(f"  event loop {a} <-> {b}: {sorted(pays[a, b])} there, {sorted(pays[b, a])} back")
        if pays[a, b] != {tidy(-reward) for reward in pays[b, a]}:
            problems.append(f"{example.name} loop {a} <-> {b} does not net to 0")
    return problems


def check_example(example: Example) -> list[str]:
    print(f"\n{example.name}: {example.task}")
    proposal = box.materialize_proposal(
        example.task, [box.sim.selection(*clause) for clause in example.clauses]
    )
    for clause, (_, _, priority) in zip(proposal.clauses, example.clauses, strict=True):
        print(
            f"  {priority} {clause.pattern}({', '.join(clause.propositions)}) = {clause.ltlf_formula}"
        )
    new = box.compile_machine(example.clauses)
    old = parse_paper_reward_machine((RM_DIR / example.old_file).read_text(encoding="utf-8"))
    text = serialize_paper_reward_machine(new)
    (RM_DIR / example.new_file).write_text(text, encoding="utf-8")
    print(text)
    return [
        *compare_edges(example, old, new),
        *potential_problems(example, new),
        *well_problems(example, new),
        *loop_problems(example, new),
    ]


def check_end_judgment() -> list[str]:
    """Play example 5 at the time limit: the open items are charged, a walk into the final is not."""
    print("\nex5 at the time limit (step rewards: end judgment, flat -0.5, old machine's total)")
    new = box.compile_machine(EXAMPLES[2].clauses)
    old = parse_paper_reward_machine((RM_DIR / "s2-ex5.txt").read_text(encoding="utf-8"))
    problems = []
    for trace, (judged, flat) in END_JUDGMENT.items():
        got = step_rewards(new, trace)
        got_flat = step_rewards(replace(new, judgment=None), trace)
        old_total = tidy(sum(step_rewards(old, trace)))
        print(f"  {trace!r:34} {got} | {got_flat} | old total {old_total}")
        problems += [] if (got, got_flat) == (judged, flat) else [f"{trace!r}: {got} {got_flat}"]
        if trace in OLD_WALK_TOTALS and {tidy(sum(got)), old_total} != {OLD_WALK_TOTALS[trace]}:
            problems.append(f"{trace!r}: total {tidy(sum(got))} changed from {old_total}")
    return problems


def check_thesis_time_limit() -> list[str]:
    """Play thesis example 2: in every state a break costs more than the time limit does."""
    print("\nthesis-ex2 at the time limit (step rewards: new machine | old machine)")
    example = EXAMPLES[3]
    new = box.compile_machine(example.clauses)
    old = parse_paper_reward_machine((RM_DIR / example.old_file).read_text(encoding="utf-8"))
    problems = []
    for trace, wanted in THESIS_TIME_LIMIT.items():
        got = step_rewards(new, trace)
        print(f"  {trace!r:24} {got} | {step_rewards(old, trace)}")
        problems += [] if got == wanted else [f"thesis-ex2 {trace!r}: {got} != {wanted}"]
    return problems


def main() -> int:
    bad = [problem for example in EXAMPLES for problem in check_example(example)]
    bad += check_end_judgment()
    bad += check_thesis_time_limit()
    print("\n" + ("\n".join(bad) or "PASS: every edge matches its table; every loop nets to 0"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
