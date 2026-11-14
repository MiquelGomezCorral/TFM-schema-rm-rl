"""Reproduce visibility, late-response and next-step-recovery cases without models.

The reviewer's script of card fix 2, as it ran before the change (``outputs/wave-tests/card-fix-2/before/``).
Its ``visibility`` part counts the layouts where ``key_found`` is true at the first step while
``agent_sees`` says the key is hidden: 9 of 50 with the earlier box reading. It uses the repository's
current reference labeler, which has the view reading, so on main it prints 0.

usage (repository root): PYTHONPATH=app python experiments/benchmark/envs/minigrid-key-corridor/check/card-fix-2-before-mechanics.py
(writes ``outputs/mechanics.json``)
"""

import json
from pathlib import Path

from src.arm_fm.environments import make_environment
from src.arm_fm.service_room import scripted_policy
from src.benchmark.declare_judge import as_clause, judge_trace
from src.benchmark.plans import PlanPlayer
from src.benchmark.reference_labels import labeler_for

OUT = Path("outputs")
CARDS = {
    c["id"]: c
    for s in ("base", "templates", "complex")
    for c in json.loads(Path(f"experiments/benchmark/{s}/tasks.json").read_text())["cards"]
}


def falls_in_policy(name, seed):
    card = CARDS[name]
    env = make_environment(card["env"]["gym_id"], **card["env"]["env_kwargs"])
    try:
        env.reset(seed=seed)
        player = PlanPlayer(
            env, labeler_for(card["env"]["gym_id"], env), card["env"]["gym_id"], seed
        )
        rows = []
        while not player.done:
            action = scripted_policy(env)
            player.act(action)
            front_cell = player.cell(*player.front())
            rows.append(
                {
                    "step": len(rows) + 1,
                    "action": action,
                    "position": [int(x) for x in env.unwrapped.agent_pos],
                    "direction": int(env.unwrapped.agent_dir),
                    "labels": player.rollout.labels[-1],
                    "front": None if front_cell is None else front_cell.type,
                    "events": list(env.unwrapped.events_this_step),
                }
            )
        return {
            "id": name,
            "seed": seed,
            "fall_windows": [
                rows[max(0, i - 1) : i + 3] for i, r in enumerate(rows) if r["labels"]["box_fell"]
            ],
        }
    finally:
        env.close()


def constructive_chain():
    rows = []
    for name in ("tpl-chain-response-1-goal", "tpl-chain-response-2-goal"):
        card = CARDS[name]
        for seed in range(1, 51):
            env = make_environment(card["env"]["gym_id"], **card["env"]["env_kwargs"])
            try:
                env.reset(seed=seed)
                player = PlanPlayer(
                    env, labeler_for(card["env"]["gym_id"], env), card["env"]["gym_id"], seed
                )
                player.run([{"do": "pickup", "obj": "box"}])
                while (
                    env.unwrapped.event_counts["fall"]["fired"]
                    < env.unwrapped.event_counts["fall"]["planned"]
                    or env.unwrapped.carrying is None
                ):
                    player.act(3 if env.unwrapped.carrying is None else 6)
                player.run([{"do": "goto", "obj": "exit"}])
                verdict = judge_trace([as_clause(c) for c in card["expect"]], player.rollout.labels)
                rows.append(
                    {
                        "id": name,
                        "seed": seed,
                        "success": verdict.success,
                        "steps": len(player.rollout.actions),
                        "falls": sum(s["box_fell"] for s in player.rollout.labels),
                    }
                )
            finally:
                env.close()
    return rows


def key_visibility():
    rows = []
    for seed in range(1, 51):
        env = make_environment("MiniGrid-KeyCorridorS6R3-v0")
        try:
            env.reset(seed=seed)
            labeler = labeler_for("MiniGrid-KeyCorridorS6R3-v0", env)
            env.step(6)
            base = env.unwrapped
            key = next(
                (x, y)
                for x in range(base.width)
                for y in range(base.height)
                if getattr(base.grid.get(x, y), "type", None) == "key"
            )
            values = labeler.labels(base)
            rows.append(
                {
                    "seed": seed,
                    "key_found": values["key_found"],
                    "agent_sees_key": bool(base.agent_sees(*key)),
                    "key": list(key),
                    "position": [int(x) for x in base.agent_pos],
                    "direction": int(base.agent_dir),
                }
            )
        finally:
            env.close()
    return rows


def late_siren():
    card = CARDS["cx-siren"]
    env = make_environment(card["env"]["gym_id"], **card["env"]["env_kwargs"])
    try:
        env.reset(seed=1)
        player = PlanPlayer(env, labeler_for(card["env"]["gym_id"], env), card["env"]["gym_id"], 1)
        player.run([{"do": "policy", "name": "service_room", "ignore": []}])
        return {
            "id": card["id"],
            "judgment": judge_trace(
                [as_clause(c) for c in card["expect"]], player.rollout.labels
            ).to_dict(),
        }
    finally:
        env.close()


def main():
    visibility = key_visibility()
    constructive = constructive_chain()
    falls = [
        falls_in_policy("tpl-chain-response-1-goal", 10),
        falls_in_policy("tpl-chain-response-2-goal", 6),
    ]
    result = {
        "visibility": visibility,
        "constructive_chain": constructive,
        "policy_falls": falls,
        "siren": late_siren(),
    }
    (OUT / "mechanics.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "invisible_key_found_first_step": [
                    r for r in visibility if r["key_found"] and not r["agent_sees_key"]
                ],
                "constructive_chain_runs": len(constructive),
                "constructive_chain_failures": [r for r in constructive if not r["success"]],
                "policy_falls": falls,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
