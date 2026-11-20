"""Plan pay of shop machines: each plan's plain and discounted machine pay per event seed. No model call.

The plans (the card's solve and wrong plans, plus an idle plan) run in the card's real env and replay
through the bundle's own labeling and machine (``replay_in_bundle``, as the plan check does). The pay
is the machine reward summed up to the first final or well state, where training ends the episode;
a machine with an end judgment pays its end charge at the cut (the replay adds it). Discounted at
gamma 0.995, the shop runs' gamma. The time-limit penalty is left out: the probes and run-suite set
it to 0 (rounds 6 and 7 trained with -5, the same constant on every plan that ends out of the well).

Usage (the app under test on PYTHONPATH; run from its checkout, card env paths are relative):
  python plan_pay.py rounds OUT.json           # Part 1: stored round 6/7 and probe bundles
  python plan_pay.py levels BUNDLES OUT.json   # Part 2: build the four shop levels, promise on/off

Copied from the plan folder's shop-well/plan_pay.py; the one change: the round 6/7 and probe bundles
and cards are the entry's copies in evidence/ (the same files the runs used; lint fixes the
repository's hooks asked for aside).
"""

import importlib.util
import json
import sys
from dataclasses import asdict
from multiprocessing import Pool
from pathlib import Path

from flat_tool import compile_dfa

from src.arm_fm.artifacts import load_bundle
from src.arm_fm.environments import gym_step_limit
from src.arm_fm.generation import build_compiler_bundle
from src.arm_fm.pay_order import record_pay_order
from src.benchmark.cards import Card
from src.benchmark.plans import PlanError, run_plan
from src.benchmark.traces import make_record, replay_in_bundle
from src.compiler import RewardSwitches
from src.compiler.pipeline import build_compilation_result
from src.models import EnvironmentDescription

GAMMA = 0.995
IDLE = [{"do": "wait", "n": 1000}]
EVIDENCE = Path(__file__).resolve().parent.parent / "evidence"
BUNDLES, CARDS = EVIDENCE / "bundles", EVIDENCE / "cards"
SHOP = Path("experiments/benchmark/shop/bundles")

# (label, bundle, card): the shop runs that learned, the ones that did not, and today's probes.
ROUNDS = [
    ("r6-A both off (0/0/0 served)", BUNDLES / "r6-both-off", CARDS / "r6-shop-order-deliver.json"),
    (
        "r6-D promise on (12.2/11.2/12.2)",
        BUNDLES / "r6-promise",
        CARDS / "r6-shop-order-deliver.json",
    ),
    ("r6-E end on (18.2/12.4/12.4)", BUNDLES / "r6-end", CARDS / "r6-shop-order-deliver.json"),
    (
        "r7-B4 promise on (9.6/8.8/9.6)",
        BUNDLES / "r7-b4-promise",
        CARDS / "r7-shop-serve-only.json",
    ),
    (
        "r7-B8b promise on (12.2/12.1/12.2)",
        BUNDLES / "r7-b8b-promise",
        CARDS / "r7-shop-order-deliver.json",
    ),
    (
        "probe shop-serve both off (0/0/0)",
        BUNDLES / "shop-serve-both-off",
        CARDS / "probes-shop-serve.json",
    ),
    (
        "probe shop-serve promise on (gated)",
        BUNDLES / "shop-serve-promise-before",
        CARDS / "probes-shop-serve.json",
    ),
]
LEVEL_LABELINGS = {
    "shop-serve": SHOP / "farm/shop-serve/labeling.py",
    "shop-full": SHOP / "farm/shop-full/labeling.py",
    "shop-quiet-first": SHOP
    / "arm-fm/shop-boil/labeling.py",  # the shop labeling that has served_while_ringing
    "shop-boil": SHOP / "arm-fm/shop-boil/labeling.py",
}


def load_script(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_card(path: Path) -> Card:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Card.from_dict(data["cards"][0] if "cards" in data else data)


def plans_of(card: Card) -> list[tuple[str, list]]:
    return (
        [("solve", list(card.solve))]
        + [(f"wrong-{i}", w["steps"]) for i, w in enumerate(card.wrong)]
        + [("idle", IDLE)]
    )


def rollout_job(job):
    card, name, steps, seed = job
    try:
        return name, seed, run_plan(card.env, steps, seed)
    except PlanError as error:
        return name, seed, str(error)[:200]


def rollouts(card: Card) -> list:
    jobs = [
        (card, name, steps, seed) for name, steps in plans_of(card) for seed in card.event_seeds
    ]
    with Pool(6) as pool:
        return pool.map(rollout_job, jobs)


def pay(bundle, card: Card, name: str, rollout) -> dict:
    replay = replay_in_bundle(bundle, make_record("", card, name, "plan", rollout))
    machine = bundle.reward_machine
    finals, well = set(machine.final_states), set(machine.rejecting_states)
    states = replay.rm_states
    stop = next((i for i, s in enumerate(states) if s in finals | well), len(states) - 1)
    rewards = replay.rewards[:stop]
    end = "final" if states[stop] in finals else "well" if states[stop] in well else "open"
    served = sum(bool(label.get("order_served")) for label in rollout.labels[:stop])
    return {
        "plain": round(sum(rewards), 3),
        "discounted": round(sum(GAMMA**i * r for i, r in enumerate(rewards)), 3),
        "end": f"{end}@{stop}",
        "served": served,
        "error": replay.error or None,
    }


def table(label: str, bundle_path: Path, card: Card, rows: list) -> dict:
    bundle = load_bundle(bundle_path)
    settings = bundle.manifest.effective_settings
    plans = {}
    for name, seed, rollout in rows:
        plans.setdefault(name, {})[seed] = (
            pay(bundle, card, name, rollout) if not isinstance(rollout, str) else rollout
        )
    problems = []
    for name, seeds in plans.items():
        for seed, item in seeds.items():
            solve = plans["solve"].get(seed)
            if name == "solve" or isinstance(item, str) or isinstance(solve, str):
                continue
            for key in ("plain", "discounted"):
                if item[key] >= solve[key]:
                    problems.append(f"{name}-s{seed} {key} {item[key]} >= solve {solve[key]}")
    return {
        "label": label,
        "bundle": str(bundle_path),
        "card": card.id,
        "task": card.task,
        "states": len(bundle.reward_machine.states),
        "switches": {
            key: settings.get(key)
            for key in (
                "reward_end_judgment",
                "reward_promise_cost",
                "step_limit",
                "gamma",
                "hard_ceiling",
            )
        },
        "pay_order": (settings.get("pay_order") or {}).get("summary"),
        "plans": plans,
        "solve_best": not problems,
        "problems": problems,
    }


def build(card: Card, promise: bool, folder: Path) -> Path:
    """The card's expect at the default pricing over the level's step limit, gamma 0.995 (as the probes)."""
    proposal_of = load_script(
        Path("experiments/benchmark/scripts/build_forcing_bundles.py")
    ).proposal_of
    environment = EnvironmentDescription.from_file(card.env["description"], code=True)
    proposal = proposal_of(card.task, card.expect)
    dfas = tuple(compile_dfa(clause.ltlf_formula) for clause in proposal.clauses)
    switches = RewardSwitches(
        step_limit=gym_step_limit(card.env["gym_id"], **(card.env.get("env_kwargs") or {})),
        reward_promise_cost=promise,
        gamma=GAMMA,
    )
    result = build_compilation_result(environment, proposal, dfas, switches)
    labeling = LEVEL_LABELINGS[card.id].read_text(encoding="utf-8")
    bundle = build_compiler_bundle(result, labeling_source=labeling, state_descriptions=None)
    bundle.manifest.effective_settings.update(asdict(switches))
    record_pay_order(bundle)
    return bundle.save(folder / f"{card.id}-pc-{'on' if promise else 'off'}", overwrite=True)


def main() -> None:
    mode = sys.argv[1]
    out = Path(sys.argv[-1])
    results = []
    if mode == "one":  # python plan_pay.py one BUNDLE CARD.json OUT.json
        card = read_card(Path(sys.argv[3]))
        results.append(table(sys.argv[2], Path(sys.argv[2]), card, rollouts(card)))
    elif mode == "rounds":
        for label, bundle_path, card_path in ROUNDS:
            card = read_card(card_path)
            results.append(table(label, bundle_path, card, rollouts(card)))
    else:
        folder = Path(sys.argv[2])
        shop = json.loads(Path("experiments/benchmark/shop/tasks.json").read_text(encoding="utf-8"))
        cards = {item["id"]: Card.from_dict(item) for item in shop.get("cards", shop)}
        for card_id in LEVEL_LABELINGS:
            card = cards[card_id]
            rows = rollouts(card)
            for promise in (True, False):
                path = build(card, promise, folder)
                results.append(
                    table(f"{card_id} promise {'on' if promise else 'off'}", path, card, rows)
                )
    out.write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    for item in results:
        print(f"== {item['label']} | {item['card']} | states {item['states']} | {item['switches']}")
        print(f"   pay order: {item['pay_order']}")
        for name, seeds in item["plans"].items():
            cells = [
                f"s{s} {v['plain']:g}/{v['discounted']:g} {v['end']} srv{v['served']}"
                if isinstance(v, dict)
                else f"s{s} {v}"
                for s, v in seeds.items()
            ]
            print(f"   {name:8} " + " | ".join(cells))
        print(f"   solve pays most: {item['solve_best']} {item['problems'][:4]}")


if __name__ == "__main__":
    main()
