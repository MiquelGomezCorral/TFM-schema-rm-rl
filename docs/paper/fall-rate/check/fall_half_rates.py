"""How often the very next move can pick a fallen box up, per service-room world (2026-11-22).

Run from a checkout that has ``fall_turn: "half"`` (commit 507886e or later):

    env -C <checkout> PYTHONPATH=app <RM_RL_env>/bin/python <this file> --out <dir>

Worlds: the box-carry card's world under every ``fall_turn`` the module knows; ``right (rejected)``,
the rule first asked for (only a box at the agent's right turns it to face it), played as
``fall_turn: none`` plus that turn after each fall; and the templates world of
``tpl-chain-response-1-goal`` (box on the floor, no carry). Agents: ``solve`` is the cards' solving
plan (``policy service_room``: waits in place for each fall, in the start corner on the carry
cards); ``walk`` walks the shortest route to the exit and picks the box up whenever it lies on the
floor. A fall is pickable when the box lies in the cell the agent faces right after it.

``--out`` writes ``table.md`` (rates with 95% Wilson intervals), ``falls.json`` (every fall: step,
agent cell, direction, what lies in front) and ``digests.json`` (one digest per episode, to check
that a code change kept the episodes: compare two runs with ``compare_digests.py``).
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

import gymnasium as gym
from minigrid.core.actions import Actions

from src.arm_fm import service_room as room

CARRY = {"siren": False, "box": True, "carry": True, "require": ["holding_box"], "max_steps": 200}
TEMPLATES = {"siren": False, "box": True, "require": ["holding_box"], "max_steps": 200}
SEED_SETS = {
    "event 1-3": range(1, 4),  # the plan checker's and trace bank's event seeds
    "judge 2000000-2000099": range(2_000_000, 2_000_100),  # test-rl: 100 episodes from --seed-base
    "reset 0-999": range(1000),
}
Z95 = 1.96


# ======================================================================================
#                                    WORLDS AND AGENTS
# ======================================================================================
def face_box_at_right(base) -> None:
    """The rejected rule on top of ``fall_turn: none``: a box at the agent's right turns it."""
    right = (base.agent_dir + 1) % 4
    dx, dy = room.DIRECTIONS[right]
    cell = base.grid.get(base.agent_pos[0] + dx, base.agent_pos[1] + dy)
    if cell is not None and cell.type == "box":
        base.agent_dir = right


def worlds() -> dict[str, tuple[dict, object]]:
    """World name: env kwargs, and a hook run after each fall (None for the module's own rules)."""
    found = {turn: ({**CARRY, "fall_turn": turn}, None) for turn in room.FALL_TURNS}
    found["right (rejected)"] = ({**CARRY, "fall_turn": "none"}, face_box_at_right)
    found["templates"] = (TEMPLATES, None)
    return found


def solve_action(base) -> int:
    return room.scripted_policy(base)


def walk_action(base) -> int:
    if base.carrying is None:
        for cell in room.cells_of_type(base, "box"):
            approach = room._plan(base, room._faces(cell))
            if approach is not None:
                return int(approach[0] if approach else Actions.pickup)
    return int(room._plan(base, lambda x, y, _d: (x, y) == room.EXIT_POS)[0])


AGENTS = {"solve": solve_action, "walk": walk_action}


# ======================================================================================
#                                       MEASURING
# ======================================================================================
def play(kwargs: dict, after_fall, agent, seed: int) -> tuple[list[list], str]:
    """Every fall as [step, x, y, direction, type in front], and a digest of the whole episode."""
    env = gym.make(room.ENV_ID, **kwargs)
    env.reset(seed=seed)
    base = env.unwrapped
    falls, record, done = [], [], False
    while not done:
        action = agent(base)
        _, _, terminated, truncated, info = env.step(action)
        done = terminated or truncated
        if "fall" in info["events"]:
            if after_fall is not None:
                after_fall(base)
            front = getattr(base.grid.get(*base.front_pos), "type", None)
            falls.append([base.step_count, *map(int, base.agent_pos), base.agent_dir, front])
        boxes = room.cells_of_type(base, "box")
        record.append([action, *map(int, base.agent_pos), base.agent_dir, info["events"], boxes])
    env.close()
    return falls, hashlib.sha256(json.dumps(record).encode()).hexdigest()[:16]


def wilson(successes: int, trials: int) -> tuple[float, float]:
    """95% Wilson score interval of a proportion."""
    share = successes / trials
    scale = 1 + Z95**2 / trials
    center = (share + Z95**2 / (2 * trials)) / scale
    half = Z95 / scale * math.sqrt(share * (1 - share) / trials + Z95**2 / (4 * trials**2))
    return center - half, center + half


def rate(successes: int, trials: int) -> str:
    low, high = wilson(successes, trials)
    return f"{successes}/{trials} = {successes / trials:.1%} [{low:.1%}, {high:.1%}]"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    falls_by_episode, digests = {}, {}
    rows = [
        "| world | agent | seeds | pickable falls [95% CI] | episodes where every fall was pickable [95% CI] |",
        "| --- | --- | --- | --- | --- |",
    ]
    for world, (kwargs, after_fall) in worlds().items():
        for agent_name, agent in AGENTS.items():
            for seeds_name, seeds in SEED_SETS.items():
                fall_count = pickable = episodes = perfect = 0
                for seed in seeds:
                    falls, digest = play(kwargs, after_fall, agent, seed)
                    key = f"{world}/{agent_name}/{seed}"
                    falls_by_episode[key], digests[key] = falls, digest
                    flags = [front == "box" for *_, front in falls]
                    fall_count, pickable = fall_count + len(flags), pickable + sum(flags)
                    episodes += bool(flags)
                    perfect += bool(flags) and all(flags)
                row = f"| {world} | {agent_name} | {seeds_name} | {rate(pickable, fall_count)} | {rate(perfect, episodes)} |"
                rows.append(row)
                print(row)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "table.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (args.out / "falls.json").write_text(
        json.dumps(falls_by_episode, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.out / "digests.json").write_text(
        json.dumps(digests, indent=0, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
