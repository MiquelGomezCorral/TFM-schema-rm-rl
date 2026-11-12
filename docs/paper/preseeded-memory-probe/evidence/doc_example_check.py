"""Fix 3: the labeling examples of the KeyCorridor environment-code.md load in the sandbox and match.

Reads the two documented expressions out of the file itself (the table row of ``key_found`` and
the ``gen_obs`` bullet of the Labeling API), loads them with ``load_labeling_functions`` and
compares them with the reference labeler step by step on the solving plan of ``cx-sequence``
(seeds 1 to 50). Also shows that the earlier NumPy ``.any()`` example is refused by the sandbox.

usage (repository root): PYTHONPATH=app python outputs/wave-tests/card-fix-2/after/doc_example_check.py
"""

import json
import re
from pathlib import Path

from src.arm_fm.environments import make_environment
from src.arm_fm.runtime import load_labeling_functions
from src.benchmark.cards import load_cards
from src.benchmark.plans import run_plan
from src.benchmark.reference_labels import labeler_for

OUT = Path(__file__).parent
DOC = Path("experiments/benchmark/envs/minigrid-key-corridor/environment-code.md").read_text()
CARD = {c.id: c for c in load_cards(Path("experiments/benchmark/complex/tasks.json")).cards}[
    "cx-sequence"
]
OLD_EXAMPLE = '(env.gen_obs()["image"][:, :, 0] == 5).any()'


class ReadContext:
    """The only names the labeling code reads: ``gen_obs`` and ``episode_memory``."""

    def __init__(self, env, previous):
        self.gen_obs = env.gen_obs
        self.episode_memory = {"previous_valuation": previous}


def documented_expressions():
    table = re.search(r"\| `key_found` \| `(.+?)`:", DOC)
    bullet = re.search(r"`(any\(cell\[0\] == 5 [^`]+)` is true while a key is in\s+view", DOC)
    assert table and bullet, "the documented examples were not found"
    return table.group(1), bullet.group(1)


def run(source, name, latch):
    """Compare the loaded function with the reference ``key_found`` on seeds 1 to 50."""
    predicate = load_labeling_functions(source, (name,))[name]
    rows = []
    for seed in range(1, 51):
        rollout = run_plan(CARD.env, CARD.solve, seed)
        env = make_environment(CARD.env["gym_id"])
        try:
            env.reset(seed=seed)
            labeler = labeler_for(CARD.env["gym_id"], env)
            previous, mismatches, seen = {"key_found": False}, [], False
            for step, action in enumerate(rollout.actions, 1):
                env.step(action)
                value = bool(predicate(ReadContext(env.unwrapped, previous)))
                seen = seen or value
                generated = value if not latch else seen
                reference = labeler.labels(env.unwrapped)["key_found"]
                previous = {"key_found": generated}
                if generated != reference:
                    mismatches.append(step)
            rows.append(
                {
                    "seed": seed,
                    "steps": len(rollout.actions),
                    "mismatches": mismatches,
                    "found": seen,
                }
            )
        finally:
            env.close()
    return rows


def main():
    full, view = documented_expressions()
    table_source = f'def key_found(env):\n    prev = env.episode_memory["previous_valuation"]\n    return {full}\n'
    bullet_source = f"def key_in_view(env):\n    return {view}\n"
    try:
        load_labeling_functions(
            f"def key_in_view(env):\n    return {OLD_EXAMPLE}\n", ("key_in_view",)
        )
        old = "loaded"
    except Exception as error:  # the sandbox's own refusal is the evidence
        old = f"{type(error).__name__}: {error}"
    table_rows = run(table_source, "key_found", latch=False)
    bullet_rows = run(bullet_source, "key_in_view", latch=True)
    result = {
        "table_expression": full,
        "bullet_expression": view,
        "old_example_in_sandbox": old,
        "table_runs": len(table_rows),
        "table_steps": sum(r["steps"] for r in table_rows),
        "table_mismatch_runs": sum(bool(r["mismatches"]) for r in table_rows),
        "table_found_runs": sum(r["found"] for r in table_rows),
        "bullet_runs": len(bullet_rows),
        "bullet_mismatch_runs": sum(bool(r["mismatches"]) for r in bullet_rows),
        "bullet_found_runs": sum(r["found"] for r in bullet_rows),
    }
    (OUT / "doc-example-check.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
