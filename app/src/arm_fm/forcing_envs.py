"""Forcing levels: two MiniGrid rooms where something happens by itself and the agent must answer.

A rule such as "never let a zombie through" or "whenever you hold the key, open the door" passes
untested when its trigger never happens, so an agent that does nothing passes it. In both levels
the world makes the trigger happen at times drawn from the reset seed, so doing nothing fails the
rule:

- ``MiniGrid-Lanes-v0``: zombies walk down three lanes of a 9 x 9 field and the agent must stop
  them. The top lane is the protected one. The agent sees the whole grid.
- ``MiniGrid-KeyGift-v0``: a key sometimes lands in the agent's empty hands. It cannot drop it, and
  the only use of the key is to open the locked door. The agent sees the standard 7 x 7 view.

Every draw is made at reset from the seed, so one seed with one action list is one episode. The env
reward follows the shop: it pays the work done (a zombie killed, a gift answered), never the rules
of a card. ``success`` is read at the end of an episode and is not a MiniGrid termination. Facts and
labeling API: ``experiments/benchmark/envs/minigrid-lanes/`` and
``experiments/benchmark/envs/minigrid-key-gift/``.

Import nothing from ``src.arm_fm`` but the service room's grid helpers (``DIRECTIONS``, ``_faces``)
and the drawing of the Lanes picture (``lanes_visuals``): ``environments.py`` imports this module to
register the ids.
"""

from collections import deque
from collections.abc import Callable, Iterable

import numpy as np
from gymnasium import spaces
from gymnasium.envs.registration import register
from minigrid.core.actions import Actions
from minigrid.core.constants import COLOR_TO_IDX, OBJECT_TO_IDX, TILE_PIXELS
from minigrid.core.grid import Grid
from minigrid.core.mission import MissionSpace
from minigrid.core.world_object import Ball, Door, Key
from minigrid.minigrid_env import MiniGridEnv

from .lanes_visuals import render_lanes
from .service_room import DIRECTIONS, _faces

LANES_ID, KEY_GIFT_ID = "MiniGrid-Lanes-v0", "MiniGrid-KeyGift-v0"
MAX_STEPS = 300

# Lanes: the field is 9 x 9 inside the outer wall, so the grid is 11 x 11 and field row r is grid row r + 1.
LANES_SIZE = 11
LANE_ROWS = (1, 5, 9)  # field rows 0, 4, 8; the first is the top lane, the protected one
FIELD = range(1, 10)  # grid columns and rows of the field
RIGHT_END, LEFT_END = 9, 1
LANES_START, LANES_START_DIR = (5, 5), 2  # the middle of the field, facing left
ZOMBIE_PERIOD = 3  # a zombie steps one cell left every 3 env steps, counted from its spawn
SPAWN_CHANCE = (0.04, 0.17)  # chance per step of a spawn, rising linearly over the episode
PLANT_GAP = (20, 60)  # steps between two sprout attempts
MAX_PLANTS = 3
LANES_EVENTS = ("top_breach", "side_breach", "plant_trampled", "zombie_killed")
IGNORABLE = ("top", "plants")

# Key gift
KEY_GIFT_SIZE = 7
DOOR_POS = (3, 0)  # in the top wall; the agent works it from (3, 1), facing up
KEY_GIFT_START, KEY_GIFT_START_DIR = (3, 3), 3
KEY_COLOR = "yellow"
GIFT_CHANCE = 1 / 30
RELOCK_AFTER = 10  # steps from the opening to the door shutting and locking again
GIFT_QUIET_END = 20  # no gift in the last steps: the door is up to 7 actions away


# ======================================================================================
#                                        SHARED SHELL
# ======================================================================================
class ForcingEnv(MiniGridEnv):
    """The seeded schedule and the per-step events both levels share.

    ``reset`` draws the whole schedule from the seed (the env's own stream when none is given; the
    info reports the seed used) through ``_plan_events``. ``events_this_step`` lists the events of
    the step just taken and ``event_counts`` counts them over the episode.
    """

    def __init__(self, size: int, max_steps: int, **kwargs) -> None:
        super().__init__(
            mission_space=MissionSpace(mission_func=self._gen_mission),
            width=size,
            height=size,
            max_steps=max_steps,
            **kwargs,
        )
        self.events_this_step: list[str] = []
        self.event_counts: dict[str, int] = {}

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed, options=options)
        event_seed = int(self.np_random.integers(2**31)) if seed is None else seed
        self.events_this_step = []
        self._plan_events(np.random.default_rng(event_seed))
        return self.gen_obs(), {"events": [], "event_seed": event_seed}

    def _put(self, item: Ball, x: int, y: int) -> None:
        self.grid.set(x, y, item)
        item.cur_pos = (x, y)

    def _emit(self, event: str) -> None:
        self.events_this_step.append(event)
        self.event_counts[event] += 1


# ======================================================================================
#                                          LANES
# ======================================================================================
class Creature(Ball):
    """A ball the agent walks onto (it is not picked up): the ``Lanes`` zombies and plants."""

    def can_overlap(self) -> bool:
        return True

    def can_pickup(self) -> bool:
        return False


class Zombie(Creature):
    """A red creature; ``born`` is the step it entered, which sets its walking rhythm."""

    def __init__(self, born: int) -> None:
        super().__init__("red")
        self.born = born


class Plant(Creature):
    def __init__(self) -> None:
        super().__init__("green")


class LanesEnv(ForcingEnv):
    """Zombies walk left down three lanes; one lane is protected and the agent must hold it.

    Zombies enter at the right end of a random lane at random times and step one cell left every 3
    env steps (the agent is faster). A zombie that steps past the left end gets through and
    disappears. The agent kills a zombie by moving onto its cell; a zombie that steps onto the
    agent's cell keeps walking, so standing in a lane stops nothing. A zombie does not enter
    while another one stands on the entry cell of its lane. Spawns speed up during the episode
    (``SPAWN_CHANCE``), so late in the episode the agent cannot guard every lane.

    Plants sprout on random free cells off the lanes, at most 3 alive; a plant the agent steps on
    dies. The state that labeling reads is listed under ``## Labeling API`` in
    ``environment-code.md``. The env reward is +1 per zombie killed. ``success`` is true while no
    zombie has got through the top lane. The observation is the whole grid, as MiniGrid's
    ``FullyObsWrapper`` gives it (the agent's cell and facing included).

    Args:
        max_steps: Episode length.
    """

    def __init__(self, max_steps: int = MAX_STEPS, **kwargs) -> None:
        super().__init__(LANES_SIZE, max_steps, **kwargs)
        self.observation_space = spaces.Dict(
            {
                **self.observation_space.spaces,
                "image": spaces.Box(0, 255, (LANES_SIZE, LANES_SIZE, 3), np.uint8),
            }
        )
        self.zombies: list[Zombie] = []
        self.plants: list[Plant] = []
        # What the grid forgets, kept only for ``picture``: the (lane row, step) of every breach
        # and the cell of every trampled plant. No rule reads them.
        self.breaches: list[tuple[int, int]] = []
        self.trampled: list[tuple[int, int]] = []

    @staticmethod
    def _gen_mission() -> str:
        return "keep the zombies out of the top lane"

    def picture(self, tile_size: int = TILE_PIXELS) -> np.ndarray:
        """The drawn garden (``lanes_visuals``), for pictures made for people.

        Not ``get_frame``: the RGB pixel observation reads that, and it stays MiniGrid's.
        """
        return render_lanes(self, tile_size, LANE_ROWS, ZOMBIE_PERIOD)

    @property
    def success(self) -> bool:
        return self.event_counts["top_breach"] == 0

    def _gen_grid(self, width: int, height: int) -> None:
        self.grid = Grid(width, height)
        self.grid.wall_rect(0, 0, width, height)
        self.agent_pos, self.agent_dir = LANES_START, LANES_START_DIR

    def gen_obs(self):
        image = self.grid.encode()
        agent = (OBJECT_TO_IDX["agent"], COLOR_TO_IDX["red"], self.agent_dir)
        image[self.agent_pos[0]][self.agent_pos[1]] = agent
        return {"image": image, "direction": self.agent_dir, "mission": self.mission}

    def _plan_events(self, rng: np.random.Generator) -> None:
        steps = self.max_steps
        chance = np.linspace(*SPAWN_CHANCE, steps)
        self._spawns = rng.random(steps) < chance  # entry i happens at step i + 1
        self._spawn_lanes = rng.integers(0, len(LANE_ROWS), size=steps)
        gaps = rng.integers(PLANT_GAP[0], PLANT_GAP[1] + 1, size=steps // PLANT_GAP[0])
        # sprout step -> a draw in [0, 1) that picks the cell among the free ones at that step
        self._sprouts = dict(
            zip(np.cumsum(gaps).tolist(), rng.random(len(gaps)).tolist(), strict=True)
        )
        self.zombies, self.plants = [], []
        self.breaches, self.trampled = [], []
        self.event_counts = dict.fromkeys((*LANES_EVENTS, "zombie_spawned", "plant_sprouted"), 0)

    def step(self, action):
        self.events_this_step = []
        before = tuple(self.agent_pos)
        _, _, terminated, truncated, _ = super().step(action)
        if tuple(self.agent_pos) != before:
            self._land()
        self._advance_zombies()
        self._spawn_zombie()
        self._sprout_plant()
        reward = float(self.events_this_step.count("zombie_killed"))
        return (
            self.gen_obs(),
            reward,
            terminated,
            truncated,
            {"events": list(self.events_this_step)},
        )

    def _land(self) -> None:
        """The agent just moved: a zombie on its new cell is killed, a plant is trampled."""
        cell = self.grid.get(*self.agent_pos)
        if isinstance(cell, Zombie):
            self.zombies.remove(cell)
            self._emit("zombie_killed")
        elif isinstance(cell, Plant):
            self.plants.remove(cell)
            self.trampled.append(tuple(self.agent_pos))
            self._emit("plant_trampled")
        else:
            return
        self.grid.set(*self.agent_pos, None)

    def _advance_zombies(self) -> None:
        for zombie in list(self.zombies):
            if (self.step_count - zombie.born) % ZOMBIE_PERIOD:
                continue
            x, y = zombie.cur_pos
            self.grid.set(x, y, None)
            if x > LEFT_END:
                self._put(zombie, x - 1, y)
                continue
            self.zombies.remove(zombie)
            self.breaches.append((y, self.step_count))
            self._emit("top_breach" if y == LANE_ROWS[0] else "side_breach")

    def _spawn_zombie(self) -> None:
        index = self.step_count - 1
        y = LANE_ROWS[self._spawn_lanes[index]]
        if self._spawns[index] and self.grid.get(RIGHT_END, y) is None:
            zombie = Zombie(self.step_count)
            self._put(zombie, RIGHT_END, y)
            self.zombies.append(zombie)
            self.event_counts["zombie_spawned"] += 1

    def _sprout_plant(self) -> None:
        draw = self._sprouts.get(self.step_count)
        if draw is None or len(self.plants) >= MAX_PLANTS:
            return
        free = [
            (x, y)
            for x in FIELD
            for y in FIELD
            if y not in LANE_ROWS and self.grid.get(x, y) is None and (x, y) != self.agent_pos
        ]
        plant = Plant()
        self._put(plant, *free[int(draw * len(free))])
        self.plants.append(plant)
        self.event_counts["plant_sprouted"] += 1


# ======================================================================================
#                                        KEY GIFT
# ======================================================================================
class GiftDoor(Door):
    """The locked door: it opens for the gifted key, which it uses up; it never closes by hand."""

    def __init__(self) -> None:
        super().__init__(KEY_COLOR, is_locked=True)

    def can_overlap(self) -> bool:
        return False  # the doorway is in the outer wall: nothing lies behind it

    def toggle(self, env, _pos) -> bool:
        if self.is_open or env.carrying is None:
            return False
        env.answer_gift()
        return True


class KeyGiftEnv(ForcingEnv):
    """One small room with a locked door; a key sometimes lands in the agent's empty hands.

    While the agent's hands are empty and the door is shut, a key lands in its hands at any step
    with chance 1/30, except in the last 20 steps. The agent cannot drop it (``drop`` does
    nothing). Opening the door with the key uses the key up; the door shuts and locks again 10
    steps later. There are no other objects. The state that labeling reads is listed under
    ``## Labeling API`` in ``environment-code.md``. The env reward is +1 per gift answered by
    opening the door. ``success`` is true while every gift so far was answered.

    Args:
        max_steps: Episode length.
    """

    def __init__(self, max_steps: int = MAX_STEPS, **kwargs) -> None:
        super().__init__(KEY_GIFT_SIZE, max_steps, **kwargs)
        self.door = GiftDoor()
        self._relock_at: int | None = None

    @staticmethod
    def _gen_mission() -> str:
        return "open the door whenever you hold the key"

    @property
    def success(self) -> bool:
        return self.event_counts["gift"] == self.event_counts["answer"]

    def _gen_grid(self, width: int, height: int) -> None:
        self.grid = Grid(width, height)
        self.grid.wall_rect(0, 0, width, height)
        self.door = GiftDoor()
        self.grid.set(*DOOR_POS, self.door)
        self.agent_pos, self.agent_dir = KEY_GIFT_START, KEY_GIFT_START_DIR

    def _plan_events(self, rng: np.random.Generator) -> None:
        self._gift_draws = rng.random(self.max_steps) < GIFT_CHANCE  # entry i is step i + 1
        self._relock_at = None
        self.event_counts = dict.fromkeys(("gift", "answer"), 0)

    def answer_gift(self) -> None:
        """Open the door with the held key and use the key up (called by ``GiftDoor.toggle``)."""
        self.door.is_locked, self.door.is_open = False, True
        self.carrying = None
        self._relock_at = self.step_count + RELOCK_AFTER
        self._emit("answer")

    def step(self, action):
        self.events_this_step = []
        action = Actions.done if action == Actions.drop else action
        _, _, terminated, truncated, _ = super().step(action)
        if self.step_count == self._relock_at:
            self.door.is_open, self.door.is_locked = False, True
            self._relock_at = None
        if (
            self._gift_draws[self.step_count - 1]
            and self.carrying is None
            and not self.door.is_open
            and self.step_count <= self.max_steps - GIFT_QUIET_END
        ):
            self.carrying = Key(KEY_COLOR)
            self.carrying.cur_pos = np.array([-1, -1])
            self._emit("gift")
        reward = float("answer" in self.events_this_step)
        return (
            self.gen_obs(),
            reward,
            terminated,
            truncated,
            {"events": list(self.events_this_step)},
        )


register(id=LANES_ID, entry_point=LanesEnv)
register(id=KEY_GIFT_ID, entry_point=KeyGiftEnv)


# ======================================================================================
#                                    REFERENCE LABELS
# ======================================================================================
def reference_labels(env) -> dict[str, bool]:
    """The propositions of the level's ``environment.md`` after the last step, read from the env."""
    base = env.unwrapped
    if isinstance(base, KeyGiftEnv):
        return {"has_door_key": base.carrying is not None, "door_open": base.door.is_open}
    return {name: name in base.events_this_step for name in LANES_EVENTS}


# ======================================================================================
#                                    SCRIPTED POLICY
# ======================================================================================
def scripted_policy(env, ignore: Iterable[str] = ()) -> int:
    """Next action of a guard that answers what the world does and keeps every rule it can.

    Lanes: it walks up to a top-lane zombie (the one nearest the left end first) and else up to the
    nearest zombie of the other lanes, and steps onto it; plants and other zombies in the way are
    walked around. With no zombie it stands still. It keeps the top lane on about nine seeds in
    ten: it is not a perfect guard, a pack of zombies that comes while it is far away gets through.
    ``ignore=("top",)`` leaves the top lane alone, which makes the wrong trace of a hard top-lane
    rule; ``ignore=("plants",)`` also walks onto every plant after the top lane, which makes the
    wrong trace of the plant rule. Key gift: with the key it walks to the door and opens it;
    without it, it waits.

    Args:
        env: The level, wrapped or not.
        ignore (Iterable[str]): Lanes only. ``"top"`` never goes for a top-lane zombie; ``"plants"``
            goes for plants, after the top lane and before the side lanes.

    Returns:
        int: A MiniGrid action index.
    """
    ignore = set(ignore)
    if ignore - set(IGNORABLE):
        raise ValueError(
            f"cannot ignore {sorted(ignore - set(IGNORABLE))}; choose from {IGNORABLE}"
        )
    base = env.unwrapped
    if isinstance(base, KeyGiftEnv):
        return _answer_gift(base)
    return _hold_lanes(base, ignore)


def _route(base, reached: Callable[[int, int, int], bool]) -> list[int] | None:
    """Shortest action list to an ``(x, y, direction)`` pose that ``reached`` accepts, or None.

    Only empty cells can be walked on. Among equal routes the one that goes forward first wins,
    so a target that moves one cell does not flip the agent between two routes (it would turn
    back and forth and never catch up).
    """
    start = (*base.agent_pos, base.agent_dir)
    queue, seen = deque([(start, [])]), {start}
    while queue:
        (x, y, direction), actions = queue.popleft()
        if reached(x, y, direction):
            return actions
        dx, dy = DIRECTIONS[direction]
        moves = [
            ((x, y, (direction + 3) % 4), Actions.left),
            ((x, y, (direction + 1) % 4), Actions.right),
        ]
        if base.grid.get(x + dx, y + dy) is None:
            moves.insert(0, ((x + dx, y + dy, direction), Actions.forward))
        for pose, action in moves:
            if pose not in seen:
                seen.add(pose)
                queue.append((pose, [*actions, action]))
    return None


def _first_action(route: list[int], interaction: Actions) -> int:
    """The first action of a route to a facing pose; an empty route means act at once."""
    return int(route[0] if route else interaction)


def _answer_gift(base: KeyGiftEnv) -> int:
    route = _route(base, _faces(DOOR_POS)) if base.carrying is not None else None
    return int(Actions.done) if route is None else _first_action(route, Actions.toggle)


def _step_toward(base, cells: list[tuple[int, int]], *, in_order: bool) -> int | None:
    """The first action toward the first reachable cell in list order, or the nearest one."""
    routes = [route for cell in cells if (route := _route(base, _faces(cell))) is not None]
    if not routes:
        return None
    return _first_action(routes[0] if in_order else min(routes, key=len), Actions.forward)


def _hold_lanes(base: LanesEnv, ignore: set[str]) -> int:
    zombies = sorted((tuple(zombie.cur_pos) for zombie in base.zombies), key=lambda cell: cell[0])
    top = [cell for cell in zombies if cell[1] == LANE_ROWS[0] and "top" not in ignore]
    side = [cell for cell in zombies if cell[1] != LANE_ROWS[0]]
    plants = [tuple(plant.cur_pos) for plant in base.plants] if "plants" in ignore else []
    # the top-lane zombie nearest the left end first, then the nearest plant (if told to), then
    # the nearest side-lane zombie
    for cells, in_order in ((top, True), (plants, False), (side, False)):
        action = _step_toward(base, cells, in_order=in_order)
        if action is not None:
            return action
    return int(Actions.done)
