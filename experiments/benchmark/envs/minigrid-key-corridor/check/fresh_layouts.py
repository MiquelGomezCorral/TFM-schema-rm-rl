"""Run a KeyCorridor labeling through the runtime on fresh layouts against the reference labeler.

For each of 50 layouts (reset seeds 1 to 50) and each plan below, the plan's actions are replayed
step by step; the labeling is evaluated through `RewardMachineRuntime.evaluate_labeling` (the
sandbox of `load_labeling_functions`, with episode memory) and compared, for all five
propositions, with `labeler_for(...)`, the reference labeler. Errors and differences are counted.

Plans (card `cx-sequence` of experiments/benchmark/complex/tasks.json, plus one of ours):
  solve   key, unlock, drop the key, pick up the ball (ends at the pickup)
  open    key, unlock, then wait 1000 steps (door open, key in hand, never entered)
  nokey   key, then wait 1000 steps (door never opens)
  enter   key, unlock, drop, stand in the room facing the ball, wait 20 (room entered, no pickup)

Also, informational: 30 random actions after the solve plan's last step. The environment ended the
episode there, so these steps belong to no episode.

usage (repository root):
  PYTHONPATH=app python experiments/benchmark/envs/minigrid-key-corridor/check/fresh_layouts.py [LABELING_PY [OUT_JSON]]

Defaults, both beside this script: LABELING_PY = ``kc-page-after-labeling.py`` (the labeling of the
KeyCorridor page after its change, taken from the git-ignored ``outputs/wave-tests/kc-page/after/``
of the kc-page worktree) and the machine ``kc-page-reward-machine.txt`` (the reward machine of
``templates/kc-page-bug/arm-fm/tpl-response-1-goal``; it only supplies the five propositions and the
runtime). OUT_JSON defaults to ``outputs/fresh_layouts.json``.
"""

import json
import random
import sys
from pathlib import Path

from src.arm_fm.environments import make_environment
from src.arm_fm.runtime import RewardMachineRuntime, load_labeling_functions
from src.benchmark.cards import load_cards
from src.benchmark.plans import run_plan
from src.benchmark.reference_labels import labeler_for
from src.compiler import parse_paper_reward_machine

PROPOSITIONS = (
    "key_found",
    "has_matching_key",
    "target_door_open",
    "target_room_entered",
    "target_picked_up",
)
HERE = Path(__file__).resolve().parent
RM_TEXT = HERE / "kc-page-reward-machine.txt"
CARD = {c.id: c for c in load_cards(Path("experiments/benchmark/complex/tasks.json")).cards}[
    "cx-sequence"
]
PLANS = {
    "solve": CARD.solve,
    "open": CARD.wrong[0]["steps"],
    "nokey": CARD.wrong[1]["steps"],
    "enter": [
        {"do": "pickup", "obj": "key"},
        {"do": "toggle", "obj": "door:locked"},
        {"do": "drop"},
        {"do": "goto", "obj": "ball"},
        {"do": "wait", "n": 20},
    ],
}
SEEDS = range(1, 51)
TAIL_STEPS = 30


def compare(functions, machine, seed, actions, tail):
    """Replay ``actions`` (then ``tail`` random ones) on the layout of ``seed``; return a record."""
    env = make_environment(CARD.env["gym_id"])
    record = {
        "steps": 0,
        "errors": [],
        "differences": [],
        "after_unlock": 0,
        "pickup_steps": 0,
        "tail": [],
    }
    try:
        env.reset(seed=seed)
        runtime = RewardMachineRuntime(machine)
        runtime.reset()
        reference = labeler_for(CARD.env["gym_id"], env)
        unlocked = False
        extra = [random.Random(seed).randrange(7) for _ in range(tail)]
        for step, action in enumerate([*actions, *extra], 1):
            env.step(action)
            expected = reference.labels(env.unwrapped)
            try:
                actual = runtime.evaluate_labeling(env, functions)
            except Exception as error:  # a labeling that crashes is a result
                record["errors"].append({"step": step, "error": f"{type(error).__name__}: {error}"})
                break
            wrong = [name for name in PROPOSITIONS if actual[name] != expected[name]]
            if step <= len(actions):
                record["steps"] += 1
                record["after_unlock"] += unlocked
                record["pickup_steps"] += expected["target_picked_up"]
                for name in wrong:
                    record["differences"].append(
                        {"step": step, "proposition": name, "reference": expected[name]}
                    )
            elif wrong:
                record["tail"].append({"step": step, "propositions": wrong})
            unlocked = unlocked or expected["target_door_open"]
    finally:
        env.close()
    return record


def main(labeling_path: str, out_path: str) -> None:
    functions = load_labeling_functions(
        Path(labeling_path).read_text(encoding="utf-8"), PROPOSITIONS
    )
    machine = parse_paper_reward_machine(
        RM_TEXT.read_text(encoding="utf-8"), propositions=PROPOSITIONS, require_final_states=True
    )
    result = {}
    for plan, steps in PLANS.items():
        runs = []
        for seed in SEEDS:
            actions = run_plan(CARD.env, steps, seed).actions
            runs.append(
                (
                    seed,
                    compare(
                        functions, machine, seed, actions, TAIL_STEPS if plan == "solve" else 0
                    ),
                )
            )
        errors = [(seed, r["errors"][0]) for seed, r in runs if r["errors"]]
        differences = [(seed, r["differences"]) for seed, r in runs if r["differences"]]
        tail = [(seed, r["tail"]) for seed, r in runs if r["tail"]]
        result[plan] = {
            "layouts": len(runs),
            "steps": sum(r["steps"] for _, r in runs),
            "steps_after_unlock": sum(r["after_unlock"] for _, r in runs),
            "pickup_steps": sum(r["pickup_steps"] for _, r in runs),
            "error_layouts": len(errors),
            "difference_layouts": len(differences),
            "differing_steps": sum(len(items) for _, items in differences),
            "first_errors": errors[:2],
            "first_differences": [(seed, items[:2]) for seed, items in differences[:3]],
            "tail_layouts_with_differences": len(tail),
            "tail_first": tail[:2],
        }
    Path(out_path).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for plan, item in result.items():
        print(plan, {k: v for k, v in item.items() if not k.startswith(("first", "tail_first"))})
        if item["first_errors"] or item["first_differences"]:
            print(
                "   first errors:",
                item["first_errors"],
                "\n   first differences:",
                item["first_differences"],
            )
        if item["tail_first"]:
            print("   tail:", item["tail_first"])


if __name__ == "__main__":
    main(
        sys.argv[1] if len(sys.argv) > 1 else str(HERE / "kc-page-after-labeling.py"),
        sys.argv[2] if len(sys.argv) > 2 else "outputs/fresh_layouts.json",
    )
