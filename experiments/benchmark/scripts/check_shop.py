"""Live check of the shop levels (``MiniGrid-Shop-v0`` and ``MiniGrid-Shop-Pot-v0``).

Usage (from the repository root):
    PYTHONPATH=app python experiments/benchmark/scripts/check_shop.py --out <dir> [--seeds 300]

For reset seeds 1..N on each level it checks that the recorded schedule is the one the events
follow, that no event starts in the quiet end (the last ``3 x N_x`` steps) and that ``N_x`` is what
the scripted worker needs from the worst start pose, that the solving plan of every card of the
level passes the independent judge, that doing nothing fails every card, that each wrong plan breaks
exactly the clauses its card promises, that the labels obey the constraints of ``environment.md``,
that the shop reward matches a recount from the labels, that one portion at most lies outside the
pantry, and that a seed replays the same episode. Prints one line per check, writes
``summary.json`` to ``--out`` and exits non-zero when a check fails.
"""

import argparse
import json
import statistics
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from minigrid.core.actions import Actions

from src.arm_fm import shop
from src.arm_fm.environments import make_environment
from src.arm_fm.service_room import _faces, _plan, cells_of_type
from src.benchmark.cards import Card, load_cards
from src.benchmark.declare_judge import judge_trace
from src.benchmark.plans import Rollout, run_plan

CARDS = Path("experiments/benchmark/shop/tasks.json")
LEVELS = {"shop": "MiniGrid-Shop-v0", "shop-pot": "MiniGrid-Shop-Pot-v0"}
FULL_CARD = {"shop": "shop-full", "shop-pot": "shop-boil"}
SOLVE = [{"do": "policy", "name": "shop", "ignore": []}]
NOTHING = [{"do": "wait", "n": shop.MAX_STEPS}]
PICKUP = int(Actions.pickup)
TOGGLES = ("switch_toggled", "order_taken", "food_prepared", "order_served", "stove_fixed")


class Checks:
    """Prints one line per check and remembers the failed ones."""

    def __init__(self) -> None:
        self.failed: list[str] = []

    def report(self, name: str, passed: int, total: int, extra: str = "") -> None:
        ok = passed == total
        print(f"{'ok  ' if ok else 'FAIL'} {name}: {passed}/{total}{' ' + extra if extra else ''}")
        if not ok:
            self.failed.append(name)


class Plays:
    """Runs plans on one level and keeps every rollout, so a plan shared by cards runs once."""

    def __init__(self, env_spec: dict[str, Any]) -> None:
        self.env_spec = env_spec
        self.cache: dict[tuple[str, int], Rollout] = {}

    def __call__(self, steps: Sequence[dict], seed: int) -> Rollout:
        key = (json.dumps(steps, sort_keys=True), seed)
        if key not in self.cache:
            self.cache[key] = run_plan(self.env_spec, steps, seed)
        return self.cache[key]


# ======================================================================================
#                                    TRACE READING
# ======================================================================================
def rise(values: list[bool]) -> list[int]:
    """1-based steps at which a condition turns true."""
    return [i + 1 for i, v in enumerate(values) if v and (i == 0 or not values[i - 1])]


def starts(rollout: Rollout, pot: bool) -> dict[str, list[int]]:
    """Steps at which each kind of event started, read from the labels."""
    found = {
        "ring": rise([x["siren_ringing"] for x in rollout.labels]),
        "client": [i + 1 for i, x in enumerate(rollout.labels) if x["client_arrived"]],
        "fall": [i + 1 for i, x in enumerate(rollout.labels) if x["food_fell"]],
    }
    if pot:
        found["pot"] = rise([x["pot_boiling"] for x in rollout.labels])
    return found


def broken_constraints(rollout: Rollout, pot: bool) -> list[str]:
    """The constraints of ``environment.md`` the trace breaks (an empty list when none)."""
    labels, broken, arrived, served, ordered = rollout.labels, set(), 0, 0, False
    for i, now in enumerate(labels):
        before = labels[i - 1] if i else dict.fromkeys(now, False)
        arrived, served = arrived + now["client_arrived"], served + now["order_served"]
        checks = {
            "fell leaves the hands empty": not now["food_fell"] or not now["holding_food"],
            "only carried food falls": not now["food_fell"]
            or before["holding_food"]
            or rollout.actions[i] == PICKUP,
            "serving empties the hands": not now["order_served"]
            or (before["holding_food"] and not now["holding_food"]),
            "served_while_ringing is serving on a ringing siren": now["served_while_ringing"]
            == (now["order_served"] and before["siren_ringing"]),
            "preparing needs food, which stays unless it slips": not now["food_prepared"]
            or (before["holding_food"] and (now["holding_food"] or now["food_fell"])),
            "preparing needs an order taken and not yet served": not now["food_prepared"]
            or ordered,
            "arrival is not an order or a serve": not now["client_arrived"]
            or not (now["order_taken"] or now["order_served"]),
            "one client at a time": 0 <= arrived - served <= 1,
            "one toggle has one target": sum(now.get(name, False) for name in TOGGLES) <= 1,
            "the siren stops only at a toggle": not before["siren_ringing"]
            or now["siren_ringing"]
            or now["switch_toggled"],
        }
        if pot:
            checks["fixing needs a boil and empty hands"] = not now["stove_fixed"] or (
                before["pot_boiling"] and not now["pot_boiling"] and not now["holding_food"]
            )
            checks["the pot stops only when fixed"] = (
                not before["pot_boiling"] or now["pot_boiling"] or now["stove_fixed"]
            )
        broken |= {name for name, holds in checks.items() if not holds}
        ordered = (ordered or now["order_taken"]) and not now["order_served"]
    return sorted(broken)


def expected_reward(rollout: Rollout, pot: bool) -> float:
    """The shop reward recounted from the labels alone."""
    limits, total = shop.walk_limits(), 0.0
    rings = rise([x["siren_ringing"] for x in rollout.labels])
    boils = rise([x["pot_boiling"] for x in rollout.labels]) if pot else []
    present, heard, boiled = False, [0], [0]  # steps heard per ring, steps boiling per boil
    for i, now in enumerate(rollout.labels, start=1):
        total += now["order_served"]
        present = (present or now["client_arrived"]) and not now["order_served"]
        if i in rings:
            heard.append(0)
        if i in boils:
            boiled.append(0)
        heard[-1] += now["siren_ringing"] and present
        boiled[-1] += pot and now["pot_boiling"]
    # n steps cost -0.5 for each full K steps after the first K: (n - 1) // K, and nothing at n = 0
    for steps, limit in ((heard, limits["ring"]), (boiled, limits["pot"])):
        total -= 0.5 * sum(max(0, n - 1) // limit for n in steps)
    return total


# ======================================================================================
#                                 N_x AND THE ONE-PORTION RULE
# ======================================================================================
def portions_outside_pantry(gym_id: str, seed: int) -> int:
    """The most portions (carried or on the floor) outside the pantry in a solving episode."""
    env = make_environment(gym_id, max_steps=shop.MAX_STEPS)
    env.reset(seed=seed)
    base, most = env.unwrapped, 0
    for _ in range(shop.MAX_STEPS):
        env.step(shop.scripted_policy(env))
        floor = [cell for cell in cells_of_type(base, "box") if cell != shop.PANTRY_POS]
        most = max(most, len(floor) + (base.carrying is not None))
    return most


def handling_time(gym_id: str, kind: str, pose: tuple[int, int, int]) -> int:
    """Steps the scripted worker needs to handle one event from ``pose``, nothing else happening."""
    env = make_environment(gym_id, max_steps=shop.MAX_STEPS)
    env.reset(seed=1)
    base = env.unwrapped
    base._slips = [None] * shop.PICKUP_DRAWS  # N_x counts the event alone, so no slip
    base._due = {"ring": None, "client": None, "pot": None}
    base.agent_pos, base.agent_dir = pose[:2], pose[2]
    if kind == "pot":
        base.carrying = shop.Food()
        env.step(int(Actions.done))
        base._set_boiling(True)
    else:
        base._due[kind] = 1
    event = {"ring": "toggle", "client": "serve", "pot": "fix"}[kind]
    handled = False
    for step in range(1, 200):
        env.step(shop.scripted_policy(env))
        handled = handled or event in base.events_this_step
        if handled and (kind != "pot" or base.carrying is not None):
            return step - (kind != "pot")  # ring and client: step 1 is before the event
    raise AssertionError(f"{kind} from {pose} never handled")


def check_handling_steps(checks: Checks, summary: dict) -> None:
    env = make_environment(LEVELS["shop"], max_steps=shop.MAX_STEPS)
    env.reset(seed=1)
    poses, base, walks = shop.poses(), env.unwrapped, []
    for x, y, direction in poses:
        base.agent_pos, base.agent_dir = (x, y), direction
        walks.append(len(_plan(base, _faces(shop.SWITCH_POS))) + 1)
    bound = shop.handling_steps()
    checks.report(
        "N_ring: the env's own planner needs as many actions as the search from the worst pose",
        int(max(walks) == bound["ring"]),
        1,
        f"({max(walks)})",
    )
    for kind, level in (("ring", "shop"), ("client", "shop"), ("pot", "shop-pot")):
        worst = max(handling_time(LEVELS[level], kind, pose) for pose in poses)
        summary[f"worker_worst_{kind}"] = worst
        # the worker always takes the order first, so for a client it may need more than the search
        # value (which also allows fetching food first), but it must fit the quiet end
        room = shop.QUIET_FACTOR * bound[kind] if kind == "client" else bound[kind]
        checks.report(
            f"N_{kind}: the scripted worker needs {worst} steps from the worst pose, "
            f"search says {bound[kind]}",
            int(bound[kind] <= worst <= room),
            1,
        )


# ======================================================================================
#                                     PER-LEVEL CHECKS
# ======================================================================================
def check_schedule(checks: Checks, level: str, plays: Plays, seeds: list[int]) -> dict:
    """Schedule in ``info``, replay, quiet end and the one-portion rule on the solving worker."""
    gym_id, pot = LEVELS[level], level == "shop-pot"
    recorded = replay = one_portion = 0
    first: dict[str, list[int]] = {}
    latest = dict.fromkeys(("ring", "client", "pot", "fall"), 0)
    counts: dict[str, list[int]] = {}
    for seed in seeds:
        _, info = make_environment(gym_id, max_steps=shop.MAX_STEPS).reset(seed=seed)
        idle = starts(plays(NOTHING, seed), pot)
        schedule = info["schedule"]["first_start"]
        recorded += all(idle[kind][0] == schedule[kind] for kind in schedule if kind in idle)
        for kind, steps in idle.items():
            if steps:
                first.setdefault(kind, []).append(steps[0])
        solved = plays(SOLVE, seed)
        for kind, steps in starts(solved, pot).items():
            latest[kind] = max(latest[kind], *steps)
            counts.setdefault(kind, []).append(len(steps))
        again = run_plan(plays.env_spec, SOLVE, seed)
        replay += again.labels == solved.labels and again.env_rewards == solved.env_rewards
        one_portion += portions_outside_pantry(gym_id, seed) <= 1
    n = len(seeds)
    checks.report(f"{level}: the schedule of `info` is what the events follow", recorded, n)
    checks.report(f"{level}: the same seed replays the same episode", replay, n)
    checks.report(f"{level}: at most one portion lies outside the pantry", one_portion, n)
    limit = shop.last_start_steps(shop.MAX_STEPS)
    for kind in counts:
        checks.report(
            f"{level}: latest {kind} start {latest[kind]} is within the quiet end "
            f"(last {limit[kind]})",
            int(latest[kind] <= limit[kind]),
            1,
        )
    return {
        "first_start_range": {kind: [min(v), max(v)] for kind, v in first.items()},
        "latest_start": latest,
        "per_episode": {kind: [min(v), statistics.mean(v), max(v)] for kind, v in counts.items()},
    }


def check_card(checks: Checks, card: Card, plays: Plays, seeds: list[int]) -> dict:
    """The solving plan passes, doing nothing fails, each wrong plan breaks what it promises."""
    passed = nonempty = 0
    for seed in seeds:
        judgment = judge_trace(card.expect, plays(list(card.solve), seed).labels)
        passed += judgment.success
        nonempty += judgment.non_empty_success
    n = len(seeds)
    checks.report(f"{card.id}: the solving plan is judged success", passed, n)
    checks.report(f"{card.id}: ... with every clause triggered (non-empty success)", nonempty, n)
    wrong_plans = {}
    for index, plan in enumerate(card.wrong):
        exact = failing = 0
        for seed in seeds:
            judgment = judge_trace(card.expect, plays(list(plan["steps"]), seed).labels)
            exact += sorted(judgment.failed()) == sorted(plan["breaks"])
            failing += not judgment.success
        wrong_plans[f"wrong-{index}"] = [exact, failing, n]
        name = f"{card.id}: wrong-{index} breaks exactly {plan['breaks']} ({plan['why'][:40]})"
        checks.report(name, exact, n)
        if list(plan["steps"]) == NOTHING:
            checks.report(f"{card.id}: doing nothing fails the card", failing, n)
    return wrong_plans


def check_traces(checks: Checks, level: str, plays: Plays) -> dict:
    """Constraints and reward recount over every trace the level's plans made."""
    pot, constraints, mismatched = level == "shop-pot", {}, 0
    per_plan: dict[str, list[float]] = {}
    for (plan, _seed), rollout in plays.cache.items():
        for problem in broken_constraints(rollout, pot):
            constraints[problem] = constraints.get(problem, 0) + 1
        total = sum(rollout.env_rewards)
        mismatched += abs(total - expected_reward(rollout, pot)) > 1e-9
        per_plan.setdefault(plan, []).append(total)
    traces = len(plays.cache)
    checks.report(
        f"{level}: the labels obey every constraint ({traces} traces)",
        int(not constraints),
        1,
        str(constraints) if constraints else "",
    )
    checks.report(
        f"{level}: the shop reward equals the recount from the labels",
        traces - mismatched,
        traces,
    )
    rewards = {plan: [min(v), round(statistics.mean(v), 2), max(v)] for plan, v in per_plan.items()}
    for plan, (low, mean, high) in rewards.items():
        print(f"     {level}: shop reward min {low} mean {mean} max {high}: {plan[:80]}")
    return rewards


def check_reward_order(checks: Checks, level: str, rewards: dict) -> None:
    """The solving worker must out-earn every plan that breaks the level's full card."""

    def mean(steps: list[dict]) -> float:
        return rewards[json.dumps(steps, sort_keys=True)][1]

    ignored = ("siren", "food_fall", "pot") if level == "shop-pot" else ("siren", "food_fall")
    rivals = [NOTHING] + [[{**SOLVE[0], "ignore": [name]}] for name in ignored]
    beaten = sum(mean(SOLVE) > mean(rival) for rival in rivals)
    checks.report(
        f"{level}: the solving worker's mean reward beats every plan that breaks the full card",
        beaten,
        len(rivals),
    )


def stock_policy(env) -> int:
    """The solving worker that, when idle, holds raw food at the stove so the next order starts cooking.

    The stove cooks only to an order taken, so this is the nearest thing to prestocking: it
    keeps every rule and is no wrong plan, but it saves the pantry trip.
    """
    action = shop.scripted_policy(env)
    if action != int(Actions.done):
        return action
    base = env.unwrapped
    target, act = (
        (shop.PANTRY_POS, Actions.pickup)
        if base.carrying is None
        else (shop.STOVE_POS, Actions.done)
    )
    path = _plan(base, _faces(target))
    return int(path[0] if path else act)


def play_stock_worker(env_spec: dict, seed: int) -> Rollout:
    env = make_environment(env_spec["gym_id"])
    env.reset(seed=seed)
    rollout = Rollout(seed)
    for _ in range(shop.MAX_STEPS):
        _, reward, terminated, truncated, _ = env.step(stock_policy(env))
        rollout.labels.append(shop.reference_labels(env))
        rollout.env_rewards.append(float(reward))
        if terminated or truncated:
            break
    return rollout


def check_stock_worker(
    checks: Checks, level: str, card: Card, seeds: list[int], solver: float
) -> dict:
    """The stock worker passes the full card and its reward recount holds; its mean is reported."""
    rollouts = [play_stock_worker(card.env, seed) for seed in seeds]
    passed = sum(judge_trace(card.expect, r.labels).success for r in rollouts)
    recount = sum(
        abs(sum(r.env_rewards) - expected_reward(r, level == "shop-pot")) < 1e-9 for r in rollouts
    )
    checks.report(f"{level}: the stock worker passes {card.id}", passed, len(seeds))
    checks.report(f"{level}: the stock worker's reward equals the recount", recount, len(seeds))
    totals = [sum(r.env_rewards) for r in rollouts]
    mean = round(statistics.mean(totals), 2)
    print(
        f"     {level}: stock worker reward min {min(totals)} mean {mean} max {max(totals)}, "
        f"solving worker {solver}"
    )
    return {"min": min(totals), "mean": mean, "max": max(totals)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True, help="folder for summary.json")
    parser.add_argument("--seeds", type=int, default=300, help="reset seeds 1..N per level")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    seeds = list(range(1, args.seeds + 1))
    card_file = load_cards(CARDS)
    if card_file.problems:
        print(f"FAIL the cards break the card contract: {card_file.problems}")
        return 1

    checks = Checks()
    summary: dict = {"seeds": args.seeds, "N_x": shop.handling_steps(), "K": shop.walk_limits()}
    check_handling_steps(checks, summary)
    for level, gym_id in LEVELS.items():
        cards = [card for card in card_file.cards if card.env["gym_id"] == gym_id]
        plays = Plays(cards[0].env)
        summary[level] = {"cards": [card.id for card in cards]}
        summary[level] |= check_schedule(checks, level, plays, seeds)
        summary[level]["wrong_plans"] = {
            card.id: check_card(checks, card, plays, seeds) for card in cards
        }
        summary[level]["reward_per_plan"] = check_traces(checks, level, plays)
        check_reward_order(checks, level, summary[level]["reward_per_plan"])
        solver = summary[level]["reward_per_plan"][json.dumps(SOLVE, sort_keys=True)][1]
        full = next(card for card in cards if card.id == FULL_CARD[level])
        summary[level]["stock_worker"] = check_stock_worker(checks, level, full, seeds, solver)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("all checks passed" if not checks.failed else f"{len(checks.failed)} checks failed")
    return 1 if checks.failed else 0


if __name__ == "__main__":
    sys.exit(main())
