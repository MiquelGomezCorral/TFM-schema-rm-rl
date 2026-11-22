"""Does serving more orders pay more? Machine return of three shop plans (2026-11-22), no model call.

Root ask: the FARM shop machines charge an arriving client and refund the service steps, so an episode's
return may barely grow with orders served. Per item ``CARD@BUNDLE``, on reset seeds 1..N of the card's
own world, plays through the bundle (its labeling and machine, cut at a final or well state as training
does, the end charge included) the scripted worker (solve), a worker that serves one order and then only
answers the siren and food slips (one), and a worker that never moves (idle). Prints and writes per item
the mean served orders and machine return, plain and discounted at the learner's gamma, and the pay per
extra served order ``(solve - one) / (served_solve - served_one)``. Usage, from a checkout root:
    PYTHONPATH=app python <this file> --out <json> [--seeds N] CARD@BUNDLE [...]
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

from src.arm_fm.artifacts import ArtifactBundle
from src.arm_fm.environments import make_environment
from src.arm_fm.shop import scripted_policy
from src.benchmark.cards import load_cards
from src.benchmark.plans import DONE, PlanPlayer, Rollout, run_plan
from src.benchmark.reference_labels import labeler_for
from src.benchmark.traces import make_record, replay_in_bundle

GAMMA = 0.995  # ppo-shop.yaml, the learner of the ladder runs file
TASKS = Path("experiments/benchmark/shop/tasks.json")


def serve_one(env_spec: dict, seed: int) -> Rollout:
    """The scripted worker until its first served order, then only the siren and food slips."""
    env = make_environment(env_spec["gym_id"], **(env_spec.get("env_kwargs") or {}))
    try:
        env.reset(seed=seed)
        player = PlanPlayer(env, labeler_for(env_spec["gym_id"], env), env_spec["gym_id"], seed)
        base, served = env.unwrapped, False
        while not player.done:
            react = not served or base.siren_ringing or "fall" in base.events_this_step
            player.act(scripted_policy(base) if react else DONE)
            served = served or "serve" in base.events_this_step
        return player.rollout
    finally:
        env.close()


def machine_run(bundle: ArtifactBundle, card, name: str, rollout: Rollout) -> dict:
    """Served orders and machine return of one rollout, cut where training would stop."""
    replay = replay_in_bundle(bundle, make_record("", card, name, "plan", rollout))
    if replay.error:
        raise RuntimeError(f"{card.id} {name}: the labeling failed: {replay.error}")
    machine = bundle.reward_machine
    stops = set(machine.final_states) | set(machine.rejecting_states)
    states = replay.rm_states
    stop = next((i for i, state in enumerate(states) if state in stops), len(states) - 1)
    rewards = replay.rewards[:stop]
    served = sum(label.get("order_served", False) for label in rollout.labels[:stop])
    end = (
        "well"
        if states[stop] in machine.rejecting_states
        else "final"
        if states[stop] in machine.final_states
        else "open"
    )
    return {
        "served": served,
        "plain": sum(rewards),
        "discounted": sum(GAMMA**step * reward for step, reward in enumerate(rewards)),
        "end": end,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("items", nargs="+", help="CARD@BUNDLE folder")
    args = parser.parse_args()
    cards = {card.id: card for card in load_cards(TASKS, Path()).cards}
    report, flat = {}, []
    for item in args.items:
        card_id, _, folder = item.partition("@")
        card, bundle = cards[card_id], ArtifactBundle.load(Path(folder))
        runs: dict[str, list[dict]] = {"solve": [], "one": [], "idle": []}
        for seed in range(1, args.seeds + 1):
            runs["solve"].append(
                machine_run(
                    bundle,
                    card,
                    "solve",
                    run_plan(card.env, [{"do": "policy", "name": "shop"}], seed),
                )
            )
            runs["one"].append(machine_run(bundle, card, "one", serve_one(card.env, seed)))
            runs["idle"].append(
                machine_run(
                    bundle, card, "idle", run_plan(card.env, [{"do": "wait", "n": 10**6}], seed)
                )
            )
        summary = {
            plan: {
                key: round(statistics.fmean(run[key] for run in plan_runs), 3)
                for key in ("served", "plain", "discounted")
            }
            | {"ends": sorted({run["end"] for run in plan_runs})}
            for plan, plan_runs in runs.items()
        }
        extra = summary["solve"]["served"] - summary["one"]["served"]
        summary["pay_per_extra_order"] = {
            key: round((summary["solve"][key] - summary["one"][key]) / extra, 3) if extra else None
            for key in ("plain", "discounted")
        }
        name = Path(folder).name
        report[name] = {"card": card_id, **summary}
        flat.append(f"{name}: {json.dumps(summary)}")
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print("\n".join(flat))
    return 0


if __name__ == "__main__":
    sys.exit(main())
