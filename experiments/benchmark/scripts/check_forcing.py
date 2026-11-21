"""Live check of the forcing levels (``MiniGrid-Lanes-v0`` and ``MiniGrid-KeyGift-v0``).

Usage (from the repository root):
    PYTHONPATH=app python experiments/benchmark/scripts/check_forcing.py [--seeds 20] [--bundles]

For reset seeds 1..N it checks each level against its ``environment.md``: the fixed layout and
the observation, that a seed replays the same episode, the walking rhythm and the 27-step walk of
a zombie that nobody stops, the rise of the spawn rate, the plants (off the lanes, at most 3,
killed by a step), the key gift (only with empty hands and a shut door, never in the last 20
steps, not droppable, used up by the door, relocked 10 steps later), that the door is at most 10
actions away and that the labels obey the constraints. ``--bundles`` also plays an idle agent, a
random agent and a scripted guard through every card of ``experiments/benchmark/forcing`` with its
reference bundle (``reference/``, the right answer), and prints the Reward Machine return, the ending and the env result of each. Exits
non-zero when a check fails.
"""

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

import numpy as np
from minigrid.core.actions import Actions

from scripts.run_suite import RM_TIME_LIMIT_PENALTY
from src.arm_fm import forcing_envs as forcing
from src.arm_fm.artifacts import ArtifactBundle, BundleValidationError
from src.arm_fm.environments import make_environment
from src.arm_fm.forcing_envs import KEY_GIFT_ID, LANES_ID, scripted_policy
from src.arm_fm.runtime import RewardMachineEnvironment, RewardMachineRuntime
from src.arm_fm.service_room import _faces, _plan
from src.benchmark.cards import load_cards

SUITE = Path("experiments/benchmark/forcing")
REFERENCE = SUITE / "reference"  # the hand-built right-answer machines (not an arm)
CARD_LEVEL = {
    "lanes-guard": LANES_ID,
    "lanes-rules": LANES_ID,
    "keygift-hard": KEY_GIFT_ID,
    "keygift-soft": KEY_GIFT_ID,
}
DONE = int(Actions.done)
WORST_WALK = 10  # actions from the worst floor pose to a toggle of the door
# Share of seeds the scripted guard must keep the hard rule on: the Lanes guard is not perfect.
GUARD_SHARE = {LANES_ID: 0.9, KEY_GIFT_ID: 1.0}


class Checks:
    """Prints one line per check and remembers the failed ones."""

    def __init__(self) -> None:
        self.failed: list[str] = []

    def report(self, name: str, passed: int, total: int, extra: str = "") -> None:
        ok = passed == total
        print(f"{'ok  ' if ok else 'FAIL'} {name}: {passed}/{total}{' ' + extra if extra else ''}")
        if not ok:
            self.failed.append(name)


def random_actions(seed: int, length: int = forcing.MAX_STEPS) -> list[int]:
    return np.random.default_rng(seed).integers(0, 7, size=length).tolist()


def play(gym_id: str, seed: int, actions: list[int]):
    """The env after ``actions``, and each step's (events, labels)."""
    env = make_environment(gym_id)
    env.reset(seed=seed)
    log = []
    for action in actions:
        env.step(action)
        log.append((list(env.unwrapped.events_this_step), forcing.reference_labels(env)))
    return env.unwrapped, log


def idle_episode(gym_id: str, seed: int):
    """An idle episode with a log of each zombie that left the grid: (lane row, born, step)."""
    env = make_environment(gym_id)
    env.reset(seed=seed)
    base = env.unwrapped
    exits, spawned = [], []
    for step in range(1, forcing.MAX_STEPS + 1):
        before = {zombie: zombie.cur_pos for zombie in base.zombies}
        env.step(DONE)
        spawned += [
            (zombie.born, zombie.cur_pos[1]) for zombie in base.zombies if zombie not in before
        ]
        exits += [
            (pos[1], zombie.born, step)
            for zombie, pos in before.items()
            if zombie not in base.zombies
        ]
    return base, exits, spawned


# ======================================================================================
#                                        LANES
# ======================================================================================
def check_lanes_layout(checks: Checks, seeds: range) -> None:
    ring_only = 0
    for seed in seeds:
        env = make_environment(LANES_ID)
        obs, info = env.reset(seed=seed)
        base = env.unwrapped
        cells = [base.grid.get(x, y) for x in range(base.width) for y in range(base.height)]
        walls = sum(cell is not None and cell.type == "wall" for cell in cells)
        ring_only += (
            walls == 4 * 10
            and sum(cell is not None for cell in cells) == walls
            and obs["image"].shape == (11, 11, 3)
            and info["event_seed"] == seed
            and (*base.agent_pos, base.agent_dir) == (5, 5, 2)
        )
    checks.report(
        "lanes: reset is the empty 11x11 field, agent at (5, 5) facing left", ring_only, len(seeds)
    )


def check_lanes_observation(checks: Checks, seeds: range) -> None:
    agent_ok, zombie_ok = 0, 0
    for seed in seeds:
        env = make_environment(LANES_ID)
        env.reset(seed=seed)
        base = env.unwrapped
        for _ in range(40):
            obs, *_ = env.step(DONE)
        image = obs["image"]
        x, y = base.agent_pos
        agent_ok += tuple(image[x][y]) == (10, 0, base.agent_dir)  # agent, red, facing
        # a zombie on the agent's own cell is hidden by the agent
        zombie_ok += all(
            tuple(image[z.cur_pos[0]][z.cur_pos[1]]) == (6, 0, 0)
            for z in base.zombies
            if tuple(z.cur_pos) != tuple(base.agent_pos)
        )
    checks.report(
        "lanes: the observation shows the agent, its facing and every zombie", agent_ok, len(seeds)
    )
    checks.report("lanes: a zombie is a red ball in the observation", zombie_ok, len(seeds))


def check_lanes_idle(checks: Checks, seeds: range) -> None:
    rhythm, lanes_ok, entry_ok, sprout_ok, success, first_breach = 0, 0, 0, 0, 0, []
    early, late, accounted = [], [], 0
    for seed in seeds:
        base, exits, spawned = idle_episode(LANES_ID, seed)
        counts = base.event_counts
        rhythm += all(step - born == 27 for _, born, step in exits)
        lanes_ok += all(row in forcing.LANE_ROWS for _, row in spawned)
        entry_ok += len({(born, row) for born, row in spawned}) == len(spawned)
        sprout_ok += (
            counts["plant_sprouted"] <= forcing.MAX_PLANTS
            and len(base.plants) == counts["plant_sprouted"]
        )
        accounted += (
            counts["top_breach"] + counts["side_breach"] + len(base.zombies)
            == counts["zombie_spawned"]
        )
        success += base.success
        early.append(sum(born <= 100 for born, _ in spawned))
        late.append(sum(born > 200 for born, _ in spawned))
        first_breach += [step for _, _, step in exits][:1]
    n = len(seeds)
    checks.report(
        "lanes idle: a zombie nobody stops gets through 27 steps after it entered", rhythm, n
    )
    checks.report("lanes idle: zombies enter only on the three lane rows", lanes_ok, n)
    checks.report("lanes idle: no zombie enters twice on one step", entry_ok, n)
    checks.report("lanes idle: breaches + zombies on the grid = zombies entered", accounted, n)
    checks.report("lanes idle: plants sprout up to 3 and none dies", sprout_ok, n)
    checks.report(
        "lanes idle: spawns rise (steps 1-100 against 201-300)",
        int(np.mean(early) < np.mean(late)),
        1,
        f"mean {np.mean(early):.1f} then {np.mean(late):.1f}",
    )
    checks.report(
        "lanes idle: no breach before step 28",
        int(min(first_breach) >= 28),
        1,
        f"first at step {min(first_breach)}",
    )
    checks.report(
        "lanes idle: the env marks the episode failed (top lane breached)",
        n - success,
        n,
        f"{n - success} failed",
    )


def check_lanes_walks(checks: Checks, seeds: range) -> None:
    off_lane, trample_ok, kill_ok, apart, accounted, plants_max = 0, 0, 0, 0, 0, 0
    kills = tramples = 0
    for seed in seeds:
        env = make_environment(LANES_ID)
        env.reset(seed=seed)
        base = env.unwrapped
        for action in random_actions(seed):
            plants, pos = len(base.plants), tuple(base.agent_pos)
            env.step(action)
            events = base.events_this_step
            kill, trample = "zombie_killed" in events, "plant_trampled" in events
            kills, tramples = kills + kill, tramples + trample
            kill_ok += not kill or tuple(base.agent_pos) != pos
            trample_ok += not trample or len(base.plants) == plants - 1
            apart += not (kill and trample)
            plants_max = max(plants_max, len(base.plants))
            off_lane += all(p.cur_pos[1] not in forcing.LANE_ROWS for p in base.plants)
        counts = base.event_counts
        gone = counts["top_breach"] + counts["side_breach"] + counts["zombie_killed"]
        accounted += gone + len(base.zombies) == counts["zombie_spawned"]
    steps = len(seeds) * forcing.MAX_STEPS
    checks.report("lanes random: a plant is always off the lanes", off_lane, steps)
    checks.report(
        "lanes random: a trample removes exactly one plant",
        trample_ok,
        steps,
        f"{tramples} tramples",
    )
    checks.report(
        "lanes random: a kill comes with a move of the agent", kill_ok, steps, f"{kills} kills"
    )
    checks.report("lanes random: kill and trample never on one step", apart, steps)
    checks.report(
        "lanes random: at most 3 plants alive",
        int(plants_max <= forcing.MAX_PLANTS),
        1,
        f"max {plants_max}",
    )
    checks.report(
        "lanes random: kills + breaches + zombies on the grid = zombies entered",
        accounted,
        len(seeds),
    )


def check_lanes_guard(checks: Checks, seeds: range) -> None:
    top_held, kills, side, success, replay_ok = 0, [], [], 0, 0
    for seed in seeds:
        env = make_environment(LANES_ID)
        env.reset(seed=seed)
        base = env.unwrapped
        actions = []
        for _ in range(forcing.MAX_STEPS):
            actions.append(scripted_policy(env))
            env.step(actions[-1])
        held = base.event_counts["top_breach"] == 0
        top_held += held
        success += base.success == held
        kills.append(base.event_counts["zombie_killed"])
        side.append(base.event_counts["side_breach"])
        again, _ = play(LANES_ID, seed, actions)
        replay_ok += again.event_counts == base.event_counts
    n = len(seeds)
    checks.report(
        "lanes guard: holds the top lane on at least 9 seeds in 10",
        int(top_held >= 0.9 * n),
        1,
        f"{top_held}/{n}, mean {np.mean(kills):.1f} kills, {np.mean(side):.1f} side breaches",
    )
    checks.report("lanes guard: env success is true exactly when the top lane held", success, n)
    checks.report("lanes: one seed with one action list replays the same episode", replay_ok, n)


# ======================================================================================
#                                      KEY GIFT
# ======================================================================================
def check_gift_layout(checks: Checks, seeds: range) -> None:
    ok = 0
    for seed in seeds:
        env = make_environment(KEY_GIFT_ID)
        obs, info = env.reset(seed=seed)
        base = env.unwrapped
        door = base.grid.get(*forcing.DOOR_POS)
        others = [
            base.grid.get(x, y)
            for x in range(base.width)
            for y in range(base.height)
            if (x, y) != forcing.DOOR_POS
        ]
        ok += (
            door.type == "door"
            and door.is_locked
            and not door.is_open
            and door.color == "yellow"
            and all(cell is None or cell.type == "wall" for cell in others)
            and base.carrying is None
            and obs["image"].shape == (7, 7, 3)
            and (*base.agent_pos, base.agent_dir) == (3, 3, 3)
            and info["event_seed"] == seed
        )
    checks.report(
        "keygift: reset is the empty room, yellow locked door at (3, 0), hands empty",
        ok,
        len(seeds),
    )


def check_gift_idle(checks: Checks, seeds: range) -> None:
    gifts, first, holds, opened, failed = [], [], 0, 0, 0
    for seed in seeds:
        base, log = play(KEY_GIFT_ID, seed, [DONE] * forcing.MAX_STEPS)
        gifts.append(base.event_counts["gift"])
        first.append(next((i + 1 for i, (events, _) in enumerate(log) if "gift" in events), 0))
        holds += base.carrying is not None or base.event_counts["gift"] == 0
        opened += base.door.is_open
        failed += not base.success
    n = len(seeds)
    checks.report(
        "keygift idle: at most one gift, and it stays in the hands",
        int(max(gifts) <= 1),
        1,
        f"{sum(gifts)} gifts in {n} episodes, first at steps {sorted(first)[:5]}...",
    )
    checks.report("keygift idle: the door never opens", n - opened, n)
    checks.report(
        "keygift idle: the env marks the episode failed (a gift unanswered)",
        failed,
        n - gifts.count(0),
    )
    checks.report("keygift idle: the key is still held at the end", holds, n)


def answered_gifts(seed: int) -> tuple[bool, list[int], list[int]]:
    """A guard episode: its success flag, the steps of each gift and of each answer."""
    env = make_environment(KEY_GIFT_ID)
    env.reset(seed=seed)
    base = env.unwrapped
    gifts, answers, opened_at, relock_ok = [], [], 0, True
    for step in range(1, forcing.MAX_STEPS + 1):
        env.step(scripted_policy(env))
        if "gift" in base.events_this_step:
            gifts.append(step)
        if "answer" in base.events_this_step:
            answers.append(step)
            opened_at = step
        if opened_at and step == opened_at + forcing.RELOCK_AFTER:
            relock_ok &= not base.door.is_open and base.door.is_locked
        if opened_at and step == opened_at + forcing.RELOCK_AFTER - 1:
            relock_ok &= base.door.is_open
    return base.success and relock_ok, gifts, answers


def check_gift_guard(checks: Checks, seeds: range) -> None:
    ok, quick, last_gift = 0, 0, 0
    for seed in seeds:
        success, gifts, answers = answered_gifts(seed)
        ok += success
        quick += len(gifts) == len(answers) and all(
            a - g <= WORST_WALK for g, a in zip(gifts, answers, strict=True)
        )
        last_gift = max([last_gift, *gifts])
    n = len(seeds)
    checks.report(
        "keygift guard: every gift answered, door open 10 steps then shut and locked", ok, n
    )
    checks.report(f"keygift guard: each answer within {WORST_WALK} steps of its gift", quick, n)
    checks.report(
        "keygift guard: no gift after step 280",
        int(last_gift <= forcing.MAX_STEPS - forcing.GIFT_QUIET_END),
        1,
        f"last gift at step {last_gift}",
    )


def check_gift_rules(checks: Checks, seeds: range) -> None:
    gift_ok, hands_ok, drop_ok, walls_ok, labels_ok, steps = 0, 0, 0, 0, 0, 0
    for seed in seeds:
        env = make_environment(KEY_GIFT_ID)
        env.reset(seed=seed)
        base = env.unwrapped
        for action in random_actions(seed):
            before = (base.carrying is not None, base.door.is_open, tuple(base.agent_pos))
            env.step(action)
            steps += 1
            gifted = "gift" in base.events_this_step
            gift_ok += not gifted or not (before[0] or before[1])
            drop_ok += action != int(Actions.drop) or not before[0] or base.carrying is not None
            walls_ok += tuple(base.agent_pos) != forcing.DOOR_POS and base.agent_pos[1] >= 1
            hands_ok += not (base.carrying is not None and base.door.is_open)
            labels = forcing.reference_labels(env)
            labels_ok += not (labels["has_door_key"] and labels["door_open"])
    checks.report(
        "keygift random: a gift lands only with empty hands and a shut door", gift_ok, steps
    )
    checks.report("keygift random: drop never empties the hands", drop_ok, steps)
    checks.report("keygift random: the agent never stands in the doorway", walls_ok, steps)
    checks.report("keygift random: key and open door never together", hands_ok, steps)
    checks.report("keygift random: has_door_key and door_open never both true", labels_ok, steps)


def check_gift_distance(checks: Checks) -> None:
    env = make_environment(KEY_GIFT_ID)
    env.reset(seed=1)
    base = env.unwrapped
    worst = 0
    for x in range(1, 6):
        for y in range(1, 6):
            for direction in range(4):
                base.agent_pos, base.agent_dir = (x, y), direction
                worst = max(worst, len(_plan(base, _faces(forcing.DOOR_POS))) + 1)
    checks.report(
        f"keygift: the door is at most {WORST_WALK} actions away from any pose, inside the quiet end",
        int(worst <= WORST_WALK < forcing.GIFT_QUIET_END),
        1,
        f"worst {worst}",
    )


# ======================================================================================
#                                  CARDS AND BUNDLES
# ======================================================================================
AGENTS = ("idle", "random", "guard", "side-only")
COLUMNS = ("return", "steps", "success", "side_breach", "plant_trampled", "zombie_killed")


def policy_of(agent: str, seed: int) -> Callable[[object], int]:
    """The action function of a scripted agent: it reads the live env and returns an action."""
    rng = np.random.default_rng(seed)
    policies = {
        "idle": lambda _base: DONE,
        "random": lambda _base: int(rng.integers(0, 7)),
        "guard": scripted_policy,
        "side-only": lambda base: scripted_policy(base, ignore=("top",)),
    }
    return policies[agent]


def machine_env(card: str) -> tuple[RewardMachineEnvironment, ArtifactBundle]:
    bundle = ArtifactBundle.load(REFERENCE / card)
    runtime = RewardMachineRuntime(bundle.reward_machine, propositions=bundle.labeling_propositions)
    env = RewardMachineEnvironment(
        make_environment(CARD_LEVEL[card]), runtime, bundle.labeling_source
    )
    env.time_limit_penalty = RM_TIME_LIMIT_PENALTY  # as the suite's runs train
    return env, bundle


def play_card(card: str, agent: str, seed: int) -> dict[str, float | str]:
    """One episode of an agent under a card's machine: RM return, ending, steps and env result."""
    env, bundle = machine_env(card)
    env.reset(seed=seed)
    policy = policy_of(agent, seed)
    base = env.unwrapped
    total, steps = 0.0, 0
    while True:
        _, _, terminated, truncated, info = env.step(policy(base))
        total, steps = total + info["rm_reward"], steps + 1
        if terminated or truncated:
            break
    ending = "well" if info["rm_state"] in bundle.reward_machine.rejecting_states else "cut"
    return {
        "return": total,
        "ending": ending,
        "steps": steps,
        "success": float(base.success),
        **base.event_counts,
    }


def check_bundles(checks: Checks, seeds: range) -> None:
    loaded = load_cards(SUITE / "tasks.json")
    cards = {card.id: card for card in loaded.cards}
    checks.report(
        "tasks.json: no card breaks the card contract",
        int(not loaded.problems),
        1,
        str(loaded.problems),
    )
    playable = []
    for card in CARD_LEVEL:
        try:
            bundle = ArtifactBundle.load(REFERENCE / card)
            playable.append(card)
            problems = bundle.validate(require_complete=True)
        except BundleValidationError as error:  # a failed load or an incomplete bundle
            problems = [str(error)]
        checks.report(
            f"{card}: bundle validates complete", int(not problems), 1, "; ".join(problems)
        )
        checks.report(f"{card}: the card is in tasks.json", int(card in cards), 1)
    if missing := [card for card in CARD_LEVEL if card not in playable]:
        print(
            f"\nnot played (the agents play every card's machine): {', '.join(missing)} do not load"
        )
        return
    print()
    print(
        f"{'card':13} {'agent':10} {'RM return':>10} {'well':>5} {'steps':>6} {'env ok':>7} {'side':>5} {'plants':>7} {'kills':>6}"
    )
    results: dict[tuple[str, str], list[dict]] = {}
    for card in CARD_LEVEL:
        for agent in AGENTS:
            if agent == "side-only" and card != "lanes-rules":
                continue
            runs = [play_card(card, agent, seed) for seed in seeds]
            results[card, agent] = runs
            wells = sum(run["ending"] == "well" for run in runs)
            mean = {key: np.mean([run.get(key, 0) for run in runs]) for key in COLUMNS}
            print(
                f"{card:13} {agent:10} {mean['return']:10.2f} {wells:3d}/{len(runs)} {mean['steps']:6.0f} "
                f"{mean['success']:7.2f} {mean['side_breach']:5.1f} {mean['plant_trampled']:7.1f} "
                f"{mean['zombie_killed']:6.1f}"
            )
    n = len(seeds)
    for card in CARD_LEVEL:
        idle, guard = results[card, "idle"], results[card, "guard"]
        if any(clause[2] == "hard" for clause in cards[card].expect):
            checks.report(
                f"{card}: an idle agent breaks the hard rule",
                sum(run["return"] <= -1 for run in idle),
                n,
            )
        else:
            below = sum(a["return"] < b["return"] for a, b in zip(idle, guard, strict=True))
            checks.report(f"{card}: an idle agent scores below the guard", below, n)
        held = sum(run["ending"] == "cut" and run["success"] == 1.0 for run in guard)
        needed = int(np.ceil(GUARD_SHARE[CARD_LEVEL[card]] * n))
        checks.report(
            f"{card}: the guard keeps the rule to the end (at least {needed}/{n})",
            n if held >= needed else held,
            n,
            f"held {held}/{n}",
        )
    print(
        "\nlanes-rules, ending early against guarding (a top breach ends the episode in the well):"
    )
    guard = results["lanes-rules", "guard"]
    for agent in ("idle", "side-only"):
        runs = results["lanes-rules", agent]
        better = sum(a["return"] > b["return"] for a, b in zip(runs, guard, strict=True))
        print(
            f"  {agent} scores more than the guard in {better}/{n} seeds "
            f"({agent} {np.mean([r['return'] for r in runs]):.2f}, "
            f"guard {np.mean([r['return'] for r in guard]):.2f})"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument(
        "--bundles", action="store_true", help="also play every card with its bundle"
    )
    args = parser.parse_args()
    seeds, checks = range(1, args.seeds + 1), Checks()
    for check in (
        check_lanes_layout,
        check_lanes_observation,
        check_lanes_idle,
        check_lanes_walks,
        check_lanes_guard,
        check_gift_layout,
        check_gift_idle,
        check_gift_guard,
        check_gift_rules,
    ):
        check(checks, seeds)
    check_gift_distance(checks)
    if args.bundles:
        check_bundles(checks, seeds)
    print(f"\n{'FAILED: ' + ', '.join(checks.failed) if checks.failed else 'all checks passed'}")
    return 1 if checks.failed else 0


if __name__ == "__main__":
    sys.exit(main())
