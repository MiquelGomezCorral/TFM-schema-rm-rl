"""Doorkey in the two clause forms the generator can write, compiled by the code on PYTHONPATH.

Form A: one hard Existence per commanded step next to the Precedence chain (what the old prompts wrote).
Form B: the chain form, Existence of the last step plus one Precedence per pair (what the final prompts ask for).
Both are compiled with the compiler (MONA, no model call). The script writes each machine's text and prints its
per-step pay on the card's solving plan and whether the two machine texts are identical (`graphs/main-machine.rm`
is that shared text). It then prices the two
machines the loop saw before the chain-progress fix (`graphs/old-form-a.rm`, `graphs/old-form-b.rm`) on the same trace.

Usage (from the repository root): PYTHONPATH=app python -W ignore doorkey_forms.py OUT_DIR
"""

import json
import sys
from pathlib import Path

from flat_tool import compile_dfa
from pylogics.syntax.ltl import Atomic

from src.arm_fm.environments import gym_step_limit
from src.arm_fm.runtime import RewardMachineRuntime
from src.compiler import parse_paper_reward_machine, serialize_reward_machine
from src.compiler.ltlf import to_flat_syntax
from src.compiler.reward_layer import RewardSwitches, build_reward_machine
from src.engines.structured import SUPPORTED_TEMPLATES

ROOT = Path(__file__).resolve().parents[4]
TRACE = ROOT / "experiments/benchmark/base/traces/base-doorkey/solve-s1.json"
GYM_ID = "MiniGrid-DoorKey-8x8-v0"
OLD_DIR = Path(__file__).resolve().parent.parent / "graphs"
PROPS = ["at_goal", "door_open", "has_key"]
FORMS = {
    "form-a": [
        ("Existence", ("at_goal",)),
        ("Existence", ("has_key",)),
        ("Precedence", ("door_open", "at_goal")),
        ("Precedence", ("has_key", "door_open")),
    ],
    "form-b": [
        ("Existence", ("at_goal",)),
        ("Precedence", ("door_open", "at_goal")),
        ("Precedence", ("has_key", "door_open")),
    ],
}


def compile_text(clauses: list[tuple[str, tuple[str, ...]]]) -> str:
    dfas = []
    for pattern, props in clauses:
        template, _ = SUPPORTED_TEMPLATES[pattern]
        dfas.append(compile_dfa(to_flat_syntax(template(*(Atomic(p) for p in props)).to_ltlf())))
    limit = gym_step_limit(GYM_ID)
    built = build_reward_machine(dfas, [False] * len(dfas), RewardSwitches(step_limit=limit))
    return serialize_reward_machine(built.reward_machine)


def pay_per_step(text: str, labels: list[dict]) -> list[float]:
    machine = parse_paper_reward_machine(text, propositions=PROPS)
    runtime = RewardMachineRuntime(machine, warning_handler=lambda _message: None)
    ends = {*machine.final_states, *machine.rejecting_states}
    pays = []
    for step in labels:
        moved = runtime.step({name: bool(step.get(name, False)) for name in PROPS})
        pays.append(round(moved.reward, 6))
        if moved.destination in ends:
            break
    return pays


def report(name: str, text: str, labels: list[dict]) -> None:
    pays = pay_per_step(text, labels)
    nonzero = ", ".join(f"step {i + 1}: {p:g}" for i, p in enumerate(pays) if p)
    print(f"{name}: solving plan ({len(pays)} steps) pays {nonzero}; total {sum(pays):g}")


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    labels = json.loads(TRACE.read_text())["labels"]
    texts = {}
    for name, clauses in FORMS.items():
        texts[name] = compile_text(clauses)
        (out / f"{name}.rm").write_text(texts[name])
        report(name, texts[name], labels)
    print("machine texts identical:", texts["form-a"] == texts["form-b"])
    # The two machines the generator loop saw before the chain-progress fix (texts copied from the loop's
    # report), priced on the same solving trace by the runtime on PYTHONPATH.
    for name in ("old-form-a", "old-form-b"):
        report(name, (OLD_DIR / f"{name}.rm").read_text(), labels)


if __name__ == "__main__":
    main()
