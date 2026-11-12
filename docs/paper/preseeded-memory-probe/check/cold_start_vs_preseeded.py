"""One labeling expression, two ways to run it: with a hand-seeded previous valuation, and through a fresh runtime.

The expression is the KeyCorridor documentation's table example for `key_found` before it was guarded: it reads
`prev["key_found"]` first. A probe that hands the function `{"key_found": False}` itself never meets an empty
valuation; the production runtime, which a real labeling function runs under, does at step 1.

Run from the root of a repository tree, inside RM_RL_env:

    PYTHONPATH=app python cold_start_vs_preseeded.py [out.json]

Plays the solving plan of the `cx-sequence` card on seeds 1 to 50 and compares the expression with the reference
labeler at every step. No provider call.
"""

import json
import sys
from pathlib import Path

from src.arm_fm.environments import make_environment
from src.arm_fm.runtime import RewardMachineRuntime, load_labeling_functions
from src.benchmark.cards import load_cards
from src.benchmark.plans import run_plan
from src.benchmark.reference_labels import labeler_for
from src.compiler import parse_paper_reward_machine

CARD = {c.id: c for c in load_cards(Path("experiments/benchmark/complex/tasks.json")).cards}[
    "cx-sequence"
]
VIEW = 'any(cell[0] == 5 for col in env.gen_obs()["image"] for cell in col)'
UNGUARDED = f'prev["key_found"] or {VIEW}'
GUARDED = f'("key_found" in prev and prev["key_found"]) or {VIEW}'
MACHINE = parse_paper_reward_machine(
    "REWARD_MACHINE:\nSTATES: u0, u1\nINITIAL_STATE: u0\nFINAL_STATES: u1\nTRANSITION_FUNCTION:\n"
    "(u0, key_found) -> u1\n(u0, else) -> u0\n(u1, else) -> u1\nREWARD_FUNCTION:\n(u0, key_found, u1) -> 1\n",
    propositions=("key_found",),
    require_final_states=True,
)


class SeededContext:
    """What a probe hands the function: the previous valuation is supplied by hand."""

    def __init__(self, env, previous):
        self.gen_obs = env.gen_obs
        self.episode_memory = {"previous_valuation": previous}


def run(expression, seeded):
    source = f'def key_found(env):\n    prev = env.episode_memory["previous_valuation"]\n    return {expression}\n'
    functions = load_labeling_functions(source, ("key_found",))
    error_runs, mismatch_runs, steps, first_error = 0, 0, 0, None
    for seed in range(1, 51):
        rollout = run_plan(CARD.env, CARD.solve, seed)
        env = make_environment(CARD.env["gym_id"])
        try:
            env.reset(seed=seed)
            reference = labeler_for(CARD.env["gym_id"], env)
            runtime = RewardMachineRuntime(MACHINE)
            runtime.reset()
            previous, failed, wrong = {"key_found": False}, False, False
            for step, action in enumerate(rollout.actions, 1):
                env.step(action)
                try:
                    if seeded:
                        actual = bool(
                            functions["key_found"](SeededContext(env.unwrapped, previous))
                        )
                        previous = {"key_found": actual}
                    else:
                        actual = runtime.evaluate_labeling(env, functions)["key_found"]
                except Exception as error:
                    failed = True
                    first_error = (
                        first_error or f"seed {seed} step {step}: {type(error).__name__}: {error}"
                    )
                    break
                steps += 1
                wrong = wrong or actual != reference.labels(env.unwrapped)["key_found"]
            error_runs += failed
            mismatch_runs += wrong
        finally:
            env.close()
    return {
        "runs": 50,
        "error_runs": error_runs,
        "mismatch_runs": mismatch_runs,
        "steps_checked": steps,
        "first_error": first_error,
    }


def main():
    rows = {
        "unguarded expression, previous valuation seeded by hand (the probe)": run(UNGUARDED, True),
        "unguarded expression, fresh runtime": run(UNGUARDED, False),
        "guarded expression, fresh runtime": run(GUARDED, False),
    }
    text = json.dumps(rows, indent=2)
    print(text)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
