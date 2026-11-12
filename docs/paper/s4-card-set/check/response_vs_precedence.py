"""Response and Precedence on a state that can turn false are not trace-equivalent.

Run from the repository root, inside RM_RL_env (no LLM call):

    PYTHONPATH=app python -W ignore docs/paper/s4-card-set/check/response_vs_precedence.py

Judges two hand-written DoorKey traces and then every trace of up to 4 steps over `has_key` and
`door_open` with the benchmark's own judge (`app/src/benchmark/declare_judge.py`), for
Precedence(has_key, door_open) (the base card) and Response(has_key, door_open) (its `also_ok`).
"""

from itertools import product

from src.benchmark.declare_judge import judge_clause

PRECEDENCE = ("Precedence", ("has_key", "door_open"), "hard")
RESPONSE = ("Response", ("has_key", "door_open"), "hard")
MAX_STEPS = 4

NAMED_TRACES = {
    "picks up the key, never opens the door": [(True, False)],
    "opens the door, then it shuts again": [(True, False), (True, True), (True, False)],
}


def labels(steps: list[tuple[bool, bool]]) -> list[dict[str, bool]]:
    return [{"has_key": key, "door_open": door} for key, door in steps]


def status(clause: tuple, steps: list[tuple[bool, bool]]) -> str:
    return judge_clause(clause, labels(steps)).status


def main() -> None:
    for name, steps in NAMED_TRACES.items():
        print(f"{name}: Precedence {status(PRECEDENCE, steps)}, Response {status(RESPONSE, steps)}")

    states = list(product([False, True], repeat=2))
    differ = total = 0
    for length in range(1, MAX_STEPS + 1):
        for steps in product(states, repeat=length):
            total += 1
            differ += (status(PRECEDENCE, list(steps)) == "holds") != (
                status(RESPONSE, list(steps)) == "holds"
            )
    print(f"{differ} of {total} traces up to {MAX_STEPS} steps are judged differently")


if __name__ == "__main__":
    main()
