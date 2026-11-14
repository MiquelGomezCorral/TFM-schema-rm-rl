"""Read documentation expressions and evaluate them through fresh labeling runtime state."""

import json
import runpy
from pathlib import Path

from src.arm_fm.environments import make_environment
from src.arm_fm.runtime import RewardMachineRuntime, load_labeling_functions
from src.benchmark.plans import run_plan
from src.benchmark.reference_labels import labeler_for
from src.compiler import parse_paper_reward_machine

OUT = Path(__file__).parent
MACHINE = parse_paper_reward_machine(
    """REWARD_MACHINE:
STATES: u0, u1
INITIAL_STATE: u0
FINAL_STATES: u1
TRANSITION_FUNCTION:
(u0, key_found) -> u1
(u0, else) -> u0
(u1, else) -> u1
REWARD_FUNCTION:
(u0, key_found, u1) -> 1
""",
    propositions=("key_found",),
    require_final_states=True,
)


def main():
    doc = runpy.run_path(str(OUT / "doc_example_check.py"))
    table, view = doc["documented_expressions"]()
    # The "before" run (doc_cold_start-before.log) read the unguarded `prev["key_found"] or ...`.
    cases = (
        ("documented-table", table),
        (
            "documented-view-with-guarded-latch",
            f'("key_found" in prev and prev["key_found"]) or {view}',
        ),
    )
    result = []
    card = doc["CARD"]
    for name, expression in cases:
        source = f'def key_found(env):\n    prev = env.episode_memory["previous_valuation"]\n    return {expression}\n'
        functions = load_labeling_functions(source, ("key_found",))
        errors, mismatches, total_steps = [], [], 0
        for seed in range(1, 51):
            rollout = run_plan(card.env, card.solve, seed)
            env = make_environment(card.env["gym_id"])
            try:
                env.reset(seed=seed)
                runtime = RewardMachineRuntime(MACHINE)
                runtime.reset()
                reference = labeler_for(card.env["gym_id"], env)
                for step, action in enumerate(rollout.actions, 1):
                    env.step(action)
                    expected = reference.labels(env.unwrapped)["key_found"]
                    try:
                        actual = runtime.evaluate_labeling(env, functions)["key_found"]
                    except Exception as error:
                        errors.append(
                            {
                                "seed": seed,
                                "step": step,
                                "error": f"{type(error).__name__}: {error}",
                            }
                        )
                        break
                    total_steps += 1
                    if actual != expected:
                        mismatches.append({"seed": seed, "step": step})
            finally:
                env.close()
        result.append(
            {
                "case": name,
                "expression": expression,
                "runs": 50,
                "successful_steps": total_steps,
                "errors": errors,
                "mismatches": mismatches,
            }
        )
    (OUT / "doc-cold-start.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            [{**r, "errors": r["errors"][:2], "error_runs": len(r["errors"])} for r in result],
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
