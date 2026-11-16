"""Seeded random walks in a card's env, recorded with the reference labels.

A card's plans visit only the states their author thought of, so a labeling that is wrong on any
other state still passes the plan check. ``Walks`` records walks on layouts the plans never use and
the labeling check replays them like plan traces. Two walks per layout seed: ``uniform`` takes
uniformly random actions; ``task`` mixes bursts of random actions with random task moves (go to,
pick up, toggle or drop a random object), because uniform actions almost never unlock the door or
take the target, so those propositions would never turn true.
"""

import random
from contextlib import suppress
from dataclasses import dataclass, field, replace

from src.arm_fm.environments import make_environment
from src.arm_fm.probe import ProbeError

from .plans import PlanError, PlanPlayer
from .reference_labels import labeler_for
from .traces import TraceRecord

UNIFORM, TASK = "uniform", "task"
FIRST_SEED = 1000  # above every layout seed a card, a bank or an earlier review used
MOVE_LIMIT = 300  # task moves per walk; failed moves cost no env step, so this bounds the loop
OBJECT_KINDS = ("key", "door", "ball", "box", "goal")  # what a task move can name
BURST_SHARE, DROP_SHARE = 0.4, 0.1  # of the task moves; the rest act on an object
GOAL_SHARE = 0.2  # of the moves that name the goal: stepping on it ends the walk
LOCKED_SHARE = 0.5  # of the moves that name a door: aim at a locked one


@dataclass
class Walks:
    """The walks of one card, in blocks: a block's layout seeds are never another block's.

    ``template`` is any plan record of the card; the walks copy its env. A block is built on first
    use and kept, so every bundle of the card replays the same walks.
    """

    template: TraceRecord
    layouts: int
    blocks: dict[int, list[TraceRecord]] = field(default_factory=dict)

    def block(self, number: int) -> list[TraceRecord]:
        """The walks of block ``number``: ``uniform`` and ``task`` on each of its layout seeds."""
        if number not in self.blocks:
            first = FIRST_SEED + number * self.layouts
            self.blocks[number] = [
                self._walk(kind, seed)
                for seed in range(first, first + self.layouts)
                for kind in (UNIFORM, TASK)
            ]
        return self.blocks[number]

    def _walk(self, kind: str, seed: int) -> TraceRecord:
        env = make_environment(self.template.gym_id, **self.template.env_kwargs)
        try:
            env.reset(seed=seed)
            player = PlanPlayer(
                env, labeler_for(self.template.gym_id, env), self.template.gym_id, seed
            )
            rng = random.Random(f"{kind}:{seed}")  # a str seed is stable across runs
            walk = _uniform_walk if kind == UNIFORM else _task_walk
            walk(player, rng, env.action_space.n)
        finally:
            env.close()
        rollout = player.rollout
        return replace(
            self.template,
            plan=f"walk-{kind}",
            source="walk",
            reset_seed=seed,
            actions=rollout.actions,
            labels=rollout.labels,
            env_rewards=rollout.env_rewards,
            terminated=rollout.terminated,
            truncated=rollout.truncated,
        )


def _uniform_walk(player: PlanPlayer, rng: random.Random, actions: int) -> None:
    while not player.done:
        player.act(rng.randrange(actions))


def _task_walk(player: PlanPlayer, rng: random.Random, actions: int) -> None:
    for _ in range(MOVE_LIMIT):
        if player.done:
            return
        with suppress(ProbeError, PlanError):  # a move that cannot run: the walk tries another
            _task_move(player, rng, actions)


def _task_move(player: PlanPlayer, rng: random.Random, actions: int) -> None:
    roll = rng.random()
    if roll < BURST_SHARE:
        for _ in range(rng.randint(1, 6)):
            if not player.done:
                player.act(rng.randrange(actions))
    elif roll < BURST_SHARE + DROP_SHARE:
        player.run_step({"do": "drop"})
    else:
        present = [kind for kind in OBJECT_KINDS if player.objects(kind)]
        if not present:
            return
        kind = rng.choice(present)
        if kind == "goal":
            if rng.random() < GOAL_SHARE:
                player.run_step({"do": "goto", "obj": "goal"})
            return
        spec = "door:locked" if kind == "door" and rng.random() < LOCKED_SHARE else kind
        player.run_step({"do": rng.choice(("goto", "pickup", "toggle")), "obj": spec})
