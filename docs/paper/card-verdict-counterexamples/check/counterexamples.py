"""Independent physical counterexamples for card semantics; no provider calls.

Run from the root of a repository tree: PYTHONPATH=app python counterexamples.py <output dir>
"""

import json
import sys
from pathlib import Path

from src.arm_fm.environments import make_environment
from src.benchmark.declare_judge import as_clause, judge_trace
from src.benchmark.plans import PlanPlayer, run_plan
from src.benchmark.reference_labels import labeler_for

OUT = Path(sys.argv[1])  # output folder; the full run is large, the printed summary is the evidence
CARDS = {
    c["id"]: c
    for s in ("base", "templates", "complex")
    for c in json.loads(Path(f"experiments/benchmark/{s}/tasks.json").read_text())["cards"]
}


def record(card, rollout):
    judged = judge_trace([as_clause(c) for c in card["expect"]], rollout.labels)
    return {
        "id": card["id"],
        "judgment": judged.to_dict(),
        "steps": len(rollout.actions),
        "env_reward": sum(rollout.env_rewards),
        "labels": rollout.labels,
        "actions": rollout.actions,
    }


def response_door_close(card):
    env = make_environment(card["env"]["gym_id"], **card["env"].get("env_kwargs", {}))
    try:
        env.reset(seed=1)
        player = PlanPlayer(env, labeler_for(card["env"]["gym_id"], env), card["env"]["gym_id"], 1)
        steps = []
        if "Blocked" in card["env"]["gym_id"]:
            steps += [{"do": "pickup", "obj": "ball"}, {"do": "drop"}]
        steps += [{"do": "pickup", "obj": "key"}, {"do": "toggle", "obj": "door:locked"}]
        player.run(steps)
        target = (
            player.labeler.locked_door[:2]
            if hasattr(player.labeler, "locked_door")
            else player.objects("door")[0]
        )
        player.execute(player.plan(lambda x, y, _d: (x, y) == (target[0] + 1, target[1])))
        player.go_facing(target)
        player.act(5)
        if card["goal"]:
            if "DoorKey" in card["env"]["gym_id"]:
                player.run([{"do": "goto", "obj": "goal"}])
            else:
                player.run(
                    [
                        {"do": "drop"},
                        {
                            "do": "pickup",
                            "obj": "ball" if "KeyCorridor" in card["env"]["gym_id"] else "box",
                        },
                    ]
                )
        else:
            player.run([{"do": "wait", "n": 2000}])
        return record(card, player.rollout)
    finally:
        env.close()


def event_sweep():
    rows = []
    for card in CARDS.values():
        if card["env"]["gym_id"] != "MiniGrid-ServiceRoom-v0":
            continue
        for seed in range(1, 51):
            rollout = run_plan(card["env"], card["plans"]["solve"], seed)
            row = record(card, rollout)
            rows.append(
                {
                    "id": card["id"],
                    "seed": seed,
                    "steps": row["steps"],
                    "judgment": row["judgment"],
                    "falls": sum(s["box_fell"] for s in rollout.labels),
                }
            )
    return rows


def main():
    cases = []
    for name in (
        "tpl-response-1-goal",
        "tpl-response-2-goal",
        "tpl-response-2-nogoal",
        "tpl-response-3-goal",
        "tpl-response-3-nogoal",
        "cx-goal-many-rules",
    ):
        cases.append({"case": "open-door-then-close-it", **response_door_close(CARDS[name])})
    card = CARDS["tpl-response-1-nogoal"]
    rollout = run_plan(
        card["env"],
        [
            {"do": "pickup", "obj": "ball"},
            {"do": "drop"},
            {"do": "pickup", "obj": "key"},
            {"do": "drop"},
            {"do": "wait", "n": 2000},
        ],
        1,
    )
    cases.append({"case": "ball-moved-key-picked-up-then-put-down", **record(card, rollout)})
    card = CARDS["base-blocked-unlock-pickup"]
    rollout = run_plan(
        card["env"],
        [
            {"do": "pickup", "obj": "key"},
            {"do": "drop"},
            {"do": "pickup", "obj": "ball"},
            {"do": "drop"},
            {"do": "pickup", "obj": "key"},
            {"do": "toggle", "obj": "door"},
            {"do": "drop"},
            {"do": "pickup", "obj": "box"},
        ],
        1,
    )
    cases.append({"case": "key-before-ball-accepted-by-ball-first-task", **record(card, rollout)})
    card = CARDS["cx-goal-one-rule"]
    rollout = run_plan(
        card["env"],
        [
            {"do": "pickup", "obj": "ball"},
            {"do": "drop"},
            {"do": "pickup", "obj": "key"},
            {"do": "toggle", "obj": "door"},
            {"do": "toggle", "obj": "door"},
            {"do": "drop"},
            {"do": "wait", "n": 2000},
        ],
        1,
    )
    # Check only the two claimed goal formulations; the soft rule is identical in both.
    primary = judge_trace([as_clause(c) for c in card["expect"]], rollout.labels).to_dict()
    alternative = judge_trace([as_clause(c) for c in card["also_ok"][0]], rollout.labels).to_dict()
    cases.append(
        {
            "case": "also-ok-closed-door-without-box",
            "primary": primary,
            "alternative": alternative,
            "labels": rollout.labels,
        }
    )
    sweep = event_sweep()
    result = {"cases": cases, "event_sweep": sweep}
    (OUT / "counterexamples.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "cases": [
                    {k: v for k, v in row.items() if k not in ("labels", "actions")}
                    for row in cases
                ],
                "event_runs": len(sweep),
                "event_solve_failures": [row for row in sweep if not row["judgment"]["success"]],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
