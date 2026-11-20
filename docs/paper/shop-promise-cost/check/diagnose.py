"""Why today's shop-serve never reaches food_prepared: food handling counts and plan pay. No training.

Every episode runs through the bundle's own labeling and machine (``RewardMachineEnvironment``),
cut at a well or final state as in training unless the level says ``nocut``. The counts come from
the env itself (``events_this_step``, ``carrying``), so the two levels count alike although the
round 7 machine has no food_fell or food_prepared. A pickup is a step that starts with empty hands
and ends holding the food; a fall is saved when the very next step ends holding it again (the
ChainResponse(food_fell, holding_food) rule). The time-limit penalty is 0 (pay comparable across
levels; round 7 trained with -5 on every episode that ends out of the well).

Usage (tp-shop-well on PYTHONPATH, run from its checkout):
  python diagnose.py random LEVEL N OUT.json      # uniform random actions, N episodes
  python diagnose.py agent LEVEL TRACES OUT.json  # replay a judged run's agent-traces/ep*.json
  python diagnose.py plans LEVEL OUT.json         # scripted plans on the card's event seeds

Copied from the plan folder's shop-well/diagnose.py; the one change: the bundles and the round 7 card
are the entry's copies in evidence/ (lint fixes the repository's hooks asked for aside). The agent mode
needs a run's agent-traces/, not copied here.
"""

import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from src.arm_fm.artifacts import load_bundle
from src.arm_fm.environments import make_environment
from src.arm_fm.runtime import RewardMachineEnvironment, RewardMachineRuntime
from src.arm_fm.shop import scripted_policy
from src.benchmark.cards import Card

GAMMA = 0.995
PICKUP, DONE = 3, 6
EVIDENCE = Path(__file__).resolve().parent.parent / "evidence"
BUNDLES = EVIDENCE / "bundles"
TODAY = {
    "kwargs": {"max_steps": 600},
    "bundle": BUNDLES / "shop-serve-promise-after",
    "card": ("experiments/benchmark/shop/tasks.json", "shop-serve"),
    "cut": True,
}
LEVELS = {
    "today": TODAY,
    "today-nocut": TODAY
    | {"cut": False},  # the well does not end the episode: what play could reach
    "today-noslip": TODAY | {"kwargs": {"max_steps": 600, "slip_chance": 0}},  # no fall, so no well
    # the proposed fix, priced only: + hard Response(order_taken, holding_food) (fetch_variant.py)
    "today-fetch": TODAY | {"bundle": BUNDLES / "shop-serve-fetch-promise"},
    "r7": {
        "kwargs": {
            "max_steps": 600,
            "agent_view_size": 9,
            "slip_chance": 0,
            "siren": False,
            "order_needed": True,
            "cooking_needed": False,
        },
        "bundle": BUNDLES / "r7-b8b-rebuilt",
        "card": (str(EVIDENCE / "cards/r7-shop-order-deliver.json"), "shop-order-deliver"),
        "cut": True,
    },
}
_BUNDLES = {}


def bundle_of(level: str):
    if level not in _BUNDLES:
        _BUNDLES[level] = load_bundle(LEVELS[level]["bundle"])
    return _BUNDLES[level]


def card_of(level: str) -> Card:
    path, card_id = LEVELS[level]["card"]
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data["cards"] if "cards" in data else data if isinstance(data, list) else [data]
    return next(Card.from_dict(item) for item in items if item["id"] == card_id)


def episode(level: str, seed: int, choose, kwargs: dict | None = None) -> dict:
    """Play one episode; ``choose(base, memo)`` gives each action, ``memo`` holds the counts so far."""
    spec, bundle = LEVELS[level], bundle_of(level)
    machine = bundle.reward_machine
    env = make_environment("MiniGrid-Shop-v0", **(kwargs if kwargs is not None else spec["kwargs"]))
    wrapped = RewardMachineEnvironment(
        env,
        RewardMachineRuntime(machine, propositions=bundle.labeling_propositions),
        bundle.labeling_source,
        reward_source="rm",
        terminate_on_rm=spec["cut"],
    )
    wrapped.time_limit_penalty = 0.0
    wrapped.reset(seed=seed)
    base = env.unwrapped
    memo, rewards, well_at, fell_last = Counter(), [], None, False
    try:
        while True:
            action = choose(base, memo)
            if action is None:
                break
            held_before = base.carrying is not None
            _, reward, terminated, truncated, info = wrapped.step(action)
            events, held = base.events_this_step, base.carrying is not None
            if fell_last:
                memo["falls_with_next"] += 1
                memo["falls_saved"] += held
            memo["pickups"] += not held_before and held
            memo["falls"] += events.count("fall")
            memo["orders"] += "order" in events
            memo["prepares"] += "prepare" in events
            memo["serves"] += events.count("serve")
            fell_last = "fall" in events
            rewards.append(reward)
            if well_at is None and info["rm_state"] in machine.rejecting_states:
                well_at = len(rewards)
            if terminated or truncated:
                break
    finally:
        env.close()
    return {
        "seed": seed,
        **memo,
        "well_at": well_at,
        "length": len(rewards),
        "plain": round(sum(rewards), 3),
        "discounted": round(sum(GAMMA**i * r for i, r in enumerate(rewards)), 3),
    }


def random_job(job):
    level, seed = job
    rng = np.random.default_rng(seed)
    return episode(level, seed, lambda _base, _memo: int(rng.integers(7)))


def agent_job(job):
    level, path = job
    trace = json.loads(Path(path).read_text(encoding="utf-8"))
    actions = iter(trace["actions"])
    return episode(
        level, trace["reset_seed"], lambda _base, _memo: next(actions, None), trace["env_kwargs"]
    )


def summary(rows: list[dict]) -> dict:
    total = lambda key: sum(row.get(key, 0) for row in rows)  # noqa: E731
    n = len(rows)
    return {
        "episodes": n,
        "with_pickup": sum(row.get("pickups", 0) > 0 for row in rows),
        "pickups": total("pickups"),
        "falls": total("falls"),
        "falls_per_carry": round(total("falls") / total("pickups"), 3)
        if total("pickups")
        else None,
        "falls_with_next": total("falls_with_next"),
        "falls_saved_next_move": total("falls_saved"),
        "well": sum(row["well_at"] is not None for row in rows),
        "with_order": sum(row.get("orders", 0) > 0 for row in rows),
        "with_prepared": sum(row.get("prepares", 0) > 0 for row in rows),
        "with_served": sum(row.get("serves", 0) > 0 for row in rows),
        "served_mean": round(total("serves") / n, 3),
        "length_mean": round(total("length") / n, 1),
        "plain_mean": round(total("plain") / n, 3),
        "discounted_mean": round(total("discounted") / n, 3),
    }


# The plans: the scripted worker until a point, then the ``done`` no-op to the end. "drop it" is the
# forced slip: the env turns a deliberate drop into a no-op until the first fall (service_room.py:182).
PLANS = {
    "idle": lambda _memo: False,
    "order, stop": lambda memo: memo["orders"] == 0,
    "pick up food, stop": lambda memo: memo["pickups"] == 0,
    "pick up, slip, pick up again, stop": lambda memo: memo["falls"] == 0 or memo["pickups"] < 2,
    "pick up, slip, pick up again, serve one, stop": lambda memo: memo["serves"] == 0,
    "solve (worker all episode)": lambda _memo: True,
}


def plan_job(job):
    level, name, seed = job
    keep_going = PLANS[name]
    return name, episode(
        level, seed, lambda base, memo: scripted_policy(base) if keep_going(memo) else DONE
    )


def main() -> None:
    mode, level, out = sys.argv[1], sys.argv[2], Path(sys.argv[-1])
    with Pool(6) as pool:
        if mode == "random":
            rows = pool.map(random_job, [(level, 10_000 + i) for i in range(int(sys.argv[3]))])
            result = {"level": level, "policy": "random", **summary(rows)}
        elif mode == "agent":
            paths = sorted(Path(sys.argv[3]).glob("ep*.json"))
            rows = pool.map(agent_job, [(level, str(path)) for path in paths])
            result = {"level": level, "policy": f"agent {sys.argv[3]}", **summary(rows)}
        else:
            seeds = card_of(level).reset_seeds(42)
            jobs = [(level, name, seed) for name in PLANS for seed in seeds]
            rows = pool.map(plan_job, jobs)
            result = {"level": level, "seeds": seeds, "plans": {}}
            for name, row in rows:
                result["plans"].setdefault(name, []).append(row)
    out.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    if mode == "plans":
        for name, items in result["plans"].items():
            cells = [
                f"s{r['seed']} {r['plain']:g}/{r['discounted']:g} "
                f"{'well@' + str(r['well_at']) if r['well_at'] else 'len' + str(r['length'])} srv{r.get('serves', 0)}"
                for r in items
            ]
            print(f"{name:46} " + " | ".join(cells))
    else:
        print(json.dumps(result))


if __name__ == "__main__":
    main()
