"""Shop pricing: does a FARM shop machine pay more for serving more orders?

Plays four plans on the judge's test seeds (2000000-2000099, the seeds of
``no-train/plan_vs_agent.json``) and replays each through the stored FARM bundle and through its
promise-cost copy (``shop-pricing/bundles/<name>-pc``, made by ``rebuild-rewards --promise-cost``):

- idle: ``done`` for the whole episode;
- order-stop: the scripted shop worker until the first order is taken, then ``done``;
- serve-stop: the scripted worker until the first order is served, then ``done``;
- solve: the scripted worker all episode (the card's solving plan).

Episodes are cut where training cuts them (the first well state; shop machines have no final).
Per plan: machine return plain and discounted at 0.995 (shop runs) and 0.99 (shop-reward runs),
the world's own reward (what ``reward_source: both`` adds), and orders served. Per served order of
the solve: the machine pay from the step after the previous serve to this serve.

Usage (repository root, RM_RL_env, PYTHONPATH=app, ``python -P``):
    python -P <FP>/tools/shop_pricing.py play <bundle-name>   # one bundle -> shop-pricing/<name>.json
    python -P <FP>/tools/shop_pricing.py table               # every JSON -> shop-pricing/table.md
"""

import json
import sys
from pathlib import Path
from statistics import fmean

from src.arm_fm.artifacts import load_bundle
from src.arm_fm.environments import make_environment
from src.arm_fm.shop import scripted_policy
from src.benchmark import labeler_for, load_cards, make_record
from src.benchmark.plans import DONE, PlanPlayer, Rollout
from src.benchmark.traces import replay_in_bundle
from src.config import Configuration

FP = Path(__file__).resolve().parents[1]  # this entry's folder (the plan folder in the original)
OUT = FP / "evidence" / "shop-pricing"
CARDS = Configuration.WORKSPACE_PATH / "experiments/benchmark/shop/tasks.json"
FARM = Configuration.WORKSPACE_PATH / "experiments/benchmark/shop/bundles/farm"
SEEDS = list(range(2_000_000, 2_000_100))
GAMMAS = {"shop": 0.995, "shop-reward": 0.99}  # the PPO gamma of each suite's FARM runs
PLANS = ("idle", "order-stop", "serve-stop", "solve")
STOP_AT = {"idle": "start", "order-stop": "order_taken", "serve-stop": "order_served"}


# ======================================================================================
#                                      PLAY
# ======================================================================================


def rollout(card, plan: str, seed: int) -> Rollout:
    """One plan on one layout; the worker stops after ``STOP_AT[plan]`` first comes true."""
    gym_id, kwargs = card.env["gym_id"], card.env.get("env_kwargs") or {}
    env = make_environment(gym_id, **kwargs)
    try:
        env.reset(seed=seed)
        player = PlanPlayer(env, labeler_for(gym_id, env), gym_id, seed)
        stop = STOP_AT.get(plan)
        while not player.done and stop != "start":
            if stop and player.rollout.labels and player.rollout.labels[-1].get(stop):
                break
            player.act(scripted_policy(player.base))
        while not player.done:
            player.act(DONE)
        return player.rollout
    finally:
        env.close()


def discounted(rewards: list[float], gamma: float) -> float:
    return sum(gamma**step * reward for step, reward in enumerate(rewards))


def order_pays(rewards: list[float], labels: list[dict]) -> list[float]:
    """Machine pay of each served order: from the step after the previous serve to this one."""
    pays, start = [], 0
    for step, label in enumerate(labels):
        if label.get("order_served"):
            pays.append(sum(rewards[start : step + 1]))
            start = step + 1
    return pays


def measure(bundle, card, record_rollout: Rollout) -> dict:
    replay = replay_in_bundle(bundle, make_record("", card, "plan", "plan", record_rollout))
    assert not replay.error, replay.error
    well = set(bundle.reward_machine.rejecting_states)
    states = replay.rm_states
    stop = next((i for i, state in enumerate(states) if state in well), len(states) - 1)
    rewards, labels = replay.rewards[:stop], record_rollout.labels[:stop]
    return {
        "steps": stop,
        "well": states[stop] in well,
        "plain": round(sum(rewards), 4),
        **{f"disc_{suite}": round(discounted(rewards, g), 4) for suite, g in GAMMAS.items()},
        "env": round(sum(record_rollout.env_rewards[:stop]), 4),
        "env_disc_shop-reward": round(
            discounted(record_rollout.env_rewards[:stop], GAMMAS["shop-reward"]), 4
        ),
        "served": sum(bool(label.get("order_served")) for label in labels),
        "order_pays": order_pays(rewards, labels),
    }


def play(name: str) -> None:
    card = next(card for card in load_cards(CARDS).cards if card.id == name)
    bundles = {"off": load_bundle(FARM / name), "pc": load_bundle(OUT / "bundles" / f"{name}-pc")}
    rows = {variant: {plan: [] for plan in PLANS} for variant in bundles}
    for seed in SEEDS:
        for plan in PLANS:
            played = rollout(card, plan, seed)
            for variant, bundle in bundles.items():
                rows[variant][plan].append({"seed": seed, **measure(bundle, card, played)})
        print(f"{name} {seed}: solve {rows['off']['solve'][-1]['plain']}", flush=True)
    self_check(name, rows["off"]["solve"])
    (OUT / f"{name}.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")


def self_check(name: str, solve: list[dict]) -> None:
    """The off machine's solve must pay what ``plan_vs_agent`` measured on the same seeds."""
    stored = json.loads((FP / "evidence" / "plan_vs_agent.json").read_text(encoding="utf-8"))
    row = stored.get(f"shop/{name}/ppo")
    if row is None:
        return
    assert row["seeds"] == SEEDS, "the judge's seeds moved"
    for mine, theirs in zip(solve, row["solve"], strict=True):
        assert mine["plain"] == theirs["pay"], (name, mine["seed"], mine["plain"], theirs["pay"])
        assert mine["served"] == theirs["served_count"], (name, mine["seed"])


# ======================================================================================
#                                      TABLE
# ======================================================================================


def mean_of(episodes: list[dict], key: str) -> str:
    return f"{fmean(episode[key] for episode in episodes):.2f}"


def plan_cell(episodes: list[dict], suite: str, with_env: bool = False) -> str:
    """Plain / discounted machine return; with ``with_env`` the world's reward added (both)."""
    if with_env:
        plain = fmean(e["plain"] + e["env"] for e in episodes)
        disc = fmean(e["disc_shop-reward"] + e["env_disc_shop-reward"] for e in episodes)
        return f"{plain:.2f} / {disc:.2f}"
    return f"{mean_of(episodes, 'plain')} / {mean_of(episodes, f'disc_{suite}')}"


def agent_rows() -> list[str]:
    """FARM and no-RM judged runs on the shop suites: served per episode, RM return, judged."""
    lines = []
    for folder in sorted((FP / "evidence" / "judge").glob("bench__shop*__*__*__ppo")):
        _, suite, card, arm, _ = folder.name.split("__")
        judges = sorted(
            run / "judge.json"
            for run in folder.glob("seed*-*")
            if "." not in run.name and (run / "judge.json").is_file()
        )
        if arm not in ("farm", "no-rm") or not judges:
            continue
        rows = [json.loads(path.read_text(encoding="utf-8")) for path in judges]
        cells = [
            ", ".join(number(row.get(key)) for row in rows)
            for key in ("mean_served_count", "mean_rm_return", "mean_judged_success")
        ]
        lines.append(f"| {suite} | {card} | {arm} | {' | '.join(cells)} |")
    return lines


def number(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"  # no-RM runs have no RM return


def table() -> None:
    names = sorted(path.stem for path in OUT.glob("shop-*.json"))
    lines = [
        "# Shop pricing replay (judge seeds 2000000-2000099)",
        "",
        "Machine return per episode, plain / discounted (0.995 for the shop runs). Cut at the well.",
        "Per order: mean machine pay per served order of the solve (min, max).",
        "",
        "| bundle | pricing | idle | order-stop | serve-stop | solve | solve served | per order | "
        "both (shop-reward, gamma 0.99): order-stop / serve-stop / solve |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name in names:
        rows = json.loads((OUT / f"{name}.json").read_text(encoding="utf-8"))
        for variant, plans in rows.items():
            pays = [pay for episode in plans["solve"] for pay in episode["order_pays"]]
            per_order = f"{fmean(pays):.2f} ({min(pays):.2f}, {max(pays):.2f})" if pays else "-"
            both = " ; ".join(
                plan_cell(plans[plan], "shop-reward", with_env=True)
                for plan in ("order-stop", "serve-stop", "solve")
            )
            wells = sum(episode["well"] for plan in PLANS for episode in plans[plan])
            lines.append(
                f"| {name} | {variant}{f' ({wells} in the well)' if wells else ''} | "
                + " | ".join(plan_cell(plans[plan], "shop") for plan in PLANS)
                + f" | {mean_of(plans['solve'], 'served')} | {per_order} | {both} |"
            )
    lines += [
        "",
        "## Agents (judge.json, greedy, per seed)",
        "",
        "| suite | card | arm | served per episode | RM return | judged |",
        "|---|---|---|---|---|---|",
        *agent_rows(),
    ]
    (OUT / "table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1] == "play":
        play(sys.argv[2])
    else:
        table()
