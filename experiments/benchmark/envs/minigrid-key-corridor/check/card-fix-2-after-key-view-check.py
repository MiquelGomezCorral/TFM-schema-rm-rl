"""F5 check: key_found needs a clear view, on the 50 layouts of the reviewer's mechanics.py.

No provider calls. Prints the first-step count of key_found without agent_sees (expect 0), and
whether has_matching_key ever turns true before key_found while the solving plan runs (expect 0).

usage (repository root): PYTHONPATH=app python experiments/benchmark/envs/minigrid-key-corridor/check/card-fix-2-after-key-view-check.py
(from ``outputs/wave-tests/card-fix-2/after/key_view_check.py`` of the card-fix-2 worktree)
"""

import json

from src.arm_fm.environments import make_environment
from src.benchmark.plans import PlanPlayer
from src.benchmark.reference_labels import labeler_for

GYM_ID = "MiniGrid-KeyCorridorS6R3-v0"
SOLVE = [
    {"do": "pickup", "obj": "key"},
    {"do": "toggle", "obj": "door:locked"},
    {"do": "drop"},
    {"do": "pickup", "obj": "ball"},
]


def first_step_view(seed: int) -> dict:
    env = make_environment(GYM_ID)
    try:
        env.reset(seed=seed)
        base = env.unwrapped
        labeler = labeler_for(GYM_ID, env)
        # One no-op step, like the reviewer's script: the first labels come after step 1.
        env.step(6)
        values = labeler.labels(base)
        keys = [
            (x, y)
            for x in range(base.width)
            for y in range(base.height)
            if getattr(base.grid.get(x, y), "type", None) == "key"
        ]
        sees = any(base.agent_sees(*key) for key in keys)
        return {"seed": seed, "key_found": values["key_found"], "agent_sees_key": sees}
    finally:
        env.close()


def order_check(seed: int) -> dict:
    env = make_environment(GYM_ID)
    try:
        env.reset(seed=seed)
        player = PlanPlayer(env, labeler_for(GYM_ID, env), GYM_ID, seed)
        player.run(SOLVE)
        labels = player.rollout.labels
        found_at = next((i for i, step in enumerate(labels) if step["key_found"]), None)
        held_at = next((i for i, step in enumerate(labels) if step["has_matching_key"]), None)
        return {
            "seed": seed,
            "found_at": found_at,
            "held_at": held_at,
            "success": bool(labels[-1]["target_picked_up"]),
        }
    finally:
        env.close()


def main() -> None:
    first = [first_step_view(seed) for seed in range(1, 51)]
    unseen = [row for row in first if row["key_found"] and not row["agent_sees_key"]]
    order = [order_check(seed) for seed in range(1, 51)]
    before_found = [
        row
        for row in order
        if row["held_at"] is not None
        and (row["found_at"] is None or row["found_at"] > row["held_at"])
    ]
    print(
        json.dumps(
            {
                "layouts": len(first),
                "key_found_first_step": sum(r["key_found"] for r in first),
                "key_found_without_view": len(unseen),
                "solve_runs": len(order),
                "solve_successes": sum(r["success"] for r in order),
                "held_before_found": len(before_found),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
