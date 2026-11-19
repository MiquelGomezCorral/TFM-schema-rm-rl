"""Shop: a MiniGrid level where things keep happening on their own, and the agent has to react.

``gym.make("MiniGrid-Shop-v0", max_steps=600)`` and ``"MiniGrid-Shop-Pot-v0"`` (the same shop plus a
pot that boils over). There is no goal: the episode ends only at the time limit. The siren rings, a
client arrives, a carried food portion slips out of the hands, and the pot boils, all at times drawn
from the reset seed, so every card of the suite sees the same world and differs only in its rules.

Eight options, all off by default (the default shop is unchanged): ``small=True`` puts the counter,
the pantry and the stove close together in a 7 x 7 room, ``easy_start_prob`` makes a share of
the episodes start at the counter with a client arriving on step 1, ``slip_chance`` lowers
(or, at 0, removes) the chance that a carried food slips, ``siren=False`` and ``clients=False``
take the siren or the clients out of the shop, ``client_patience=N`` makes a client who
waits N steps unserved leave and end the episode as a loss, and ``order_needed=False`` and
``cooking_needed=False`` let a client take food without an order or raw food without cooking.

It builds on ``ServiceRoomEnv`` and reuses its siren, switch, fall and seeded-schedule code. The
rules (layout, events, reward) are in ``environment.md`` and the code-side facts in
``environment-code.md``, both in ``experiments/benchmark/envs/shop/`` (pot: ``shop-pot/``).
"""

from collections import defaultdict, deque
from collections.abc import Callable, Iterable, Iterator
from functools import cache, partial
from typing import NamedTuple

import numpy as np
from gymnasium.envs.registration import register
from minigrid.core.actions import Actions
from minigrid.core.constants import TILE_PIXELS
from minigrid.core.grid import Grid
from minigrid.core.mission import MissionSpace
from minigrid.core.world_object import Ball, Wall

from .service_room import (
    DIRECTIONS,
    RINGING_COLOR,
    ClosedBox,
    ServiceRoomEnv,
    Switch,
    _faces,
    _plan,
    cells_of_type,
)
from .shop_visuals import render_shop

ENV_ID, POT_ENV_ID = "MiniGrid-Shop-v0", "MiniGrid-Shop-Pot-v0"
MAX_STEPS = 600
START_DIR = 0


class Layout(NamedTuple):
    """Where things stand in the room.

    The agent works from the floor cell next to each: the client spot from the east (facing west),
    the pantry from the west, the stove from the south, the switch from the north.
    """

    size: int  # the room is size x size cells with its wall
    start: tuple[int, int]
    client: tuple[int, int]  # the client spot in the counter
    pantry: tuple[int, int]  # the shelf that always holds one portion
    stove: tuple[int, int]  # in the north wall
    switch: tuple[int, int]  # in the south wall
    counter: tuple[tuple[int, int], ...]  # the other counter cells

    @property
    def floor(self) -> set[tuple[int, int]]:
        return {(x, y) for x in range(1, self.size - 1) for y in range(1, self.size - 1)}

    @property
    def blocked(self) -> set[tuple[int, int]]:
        return {self.client, self.pantry, *self.counter}

    @property
    def counter_state(self) -> tuple[int, int, int]:
        """The agent at the counter, facing the client spot."""
        return self.client[0] + 1, self.client[1], 2


NORMAL = Layout(10, (4, 4), (1, 4), (8, 4), (4, 0), (5, 9), ((1, 3), (1, 5), (8, 3), (8, 5)))
SMALL = Layout(7, (3, 3), (1, 3), (5, 3), (3, 0), (4, 6), ((1, 2), (1, 4), (5, 2), (5, 4)))
COUNTER_COLOR, STOVE_COLOR = "yellow", "purple"  # a boiling stove takes the ringing red
WAITING_COLOR, ORDERED_COLOR = "green", "blue"  # a client before and after the order is taken
RAW_COLOR, PREPARED_COLOR = "yellow", "green"  # the food portion
IGNORABLE = ("siren", "siren_late", "pot", "food_fall")
HELD = "held"

# Seeded schedule. A first start is drawn from the range; every next start comes a gap after the
# previous event ended (the siren was switched off, the client served, the stove turned down).
FIRST_START = {"ring": (3, 30), "client": (3, 25), "pot": (30, 90)}
GAP = {"ring": (25, 70), "client": (10, 40), "pot": (40, 100)}
SLIP_DELAY = (2, 8)  # steps from a pickup to the slip planned for it
SLIP_CHANCE = 0.5  # default slip_chance: every pickup but the first; the first always slips
GAP_DRAWS, PICKUP_DRAWS = 60, 60
QUIET_FACTOR = 3  # an event does not start in the last QUIET_FACTOR x N_x steps
MISS_PENALTY = -0.5


# ======================================================================================
#                                     LAYOUT SEARCH
# ======================================================================================
def _front(x: int, y: int, direction: int) -> tuple[int, int]:
    dx, dy = DIRECTIONS[direction]
    return x + dx, y + dy


def _walk(
    layout: Layout, x: int, y: int, direction: int, blocked: set
) -> Iterator[tuple[int, int, int]]:
    """The turns and the step forward the agent can take from a state."""
    yield x, y, (direction - 1) % 4
    yield x, y, (direction + 1) % 4
    ahead = _front(x, y, direction)
    if ahead in layout.floor and ahead not in blocked:
        yield (*ahead, direction)


def _fewest_actions(starts: list, successors: Callable, is_goal: Callable) -> int:
    """The most actions, over ``starts``, of the shortest way to a goal state (reverse BFS)."""
    graph, queue = {}, deque(starts)
    while queue:
        state = queue.popleft()
        if state not in graph:
            graph[state] = list(successors(state))
            queue.extend(graph[state])
    before = defaultdict(list)
    for state, followers in graph.items():
        for follower in followers:
            before[follower].append(state)
    distance = {state: 0 for state in graph if is_goal(state)}
    queue = deque(distance)
    while queue:
        state = queue.popleft()
        for earlier in before[state]:
            if earlier not in distance:
                distance[earlier] = distance[state] + 1
                queue.append(earlier)
    return max(distance[start] for start in starts)


def _walks(layout: Layout, state: tuple) -> Iterator[tuple]:
    return _walk(layout, *state, layout.blocked)


def _client_moves(layout: Layout, state: tuple) -> Iterator[tuple]:
    """Serving a client: the order, the food (none, raw, prepared, handed over: 0 to 3) in either order.

    The food can be fetched before the order, but the stove prepares it only after the order.
    """
    *pose, ordered, food = state
    for walked in _walk(layout, *pose, layout.blocked):
        yield (*walked, ordered, food)
    ahead = _front(*pose)
    if ahead == layout.client and not ordered:
        yield (*pose, True, food)
    elif ahead == layout.client and food == 2:
        yield (*pose, ordered, 3)
    elif ahead == layout.pantry and food == 0:
        yield (*pose, ordered, 1)
    elif ahead == layout.stove and food == 1 and ordered:
        yield (*pose, ordered, 2)


def _pot_moves(layout: Layout, state: tuple) -> Iterator[tuple]:
    """Turning the stove down while carrying: put the food down, turn it down, pick the food up."""
    *pose, item, fixed = state
    blocked = layout.blocked | ({item} if item != HELD else set())
    for walked in _walk(layout, *pose, blocked):
        yield (*walked, item, fixed)
    ahead = _front(*pose)
    if item == HELD and ahead in layout.floor and ahead not in blocked:
        yield (*pose, ahead, fixed)
    if item == ahead:
        yield (*pose, HELD, fixed)
    if ahead == layout.stove and item != HELD:
        yield (*pose, item, True)


def poses(layout: Layout = NORMAL) -> list[tuple[int, int, int]]:
    return [(*cell, d) for cell in sorted(layout.floor - layout.blocked) for d in range(4)]


@cache
def handling_steps(layout: Layout = NORMAL) -> dict[str, int]:
    """``N_x``: the fewest actions that fully handle event x from the worst start state.

    The worst start state is the worst floor cell with the worst facing, found by breadth-first
    search over the layout. The siren is handled by facing the switch and toggling; a client by
    the four steps of the order; the pot by turning the stove down with the hands full (put the
    food down, turn the stove down, pick the food up). A food slip is handled by the next pickup:
    the fall turns the agent to face the food.
    """
    starts = poses(layout)
    ring = _fewest_actions(starts, partial(_walks, layout), lambda s: _front(*s) == layout.switch)
    client = _fewest_actions(
        [(*pose, False, 0) for pose in starts], partial(_client_moves, layout), lambda s: s[4] == 3
    )
    pot = _fewest_actions(
        [(*pose, HELD, False) for pose in starts],
        partial(_pot_moves, layout),
        lambda s: s[4] and s[3] == HELD,
    )
    return {"ring": ring + 1, "client": client, "pot": pot, "fall": 1}


@cache
def walk_limits(layout: Layout = NORMAL) -> dict[str, int]:
    """Steps a waiting client may hear the siren, or the pot may boil, before the shop reward fines it.

    Three times the shortest walk from the counter to the switch (or to the stove).
    """
    walks, start = partial(_walks, layout), [layout.counter_state]
    to_switch = _fewest_actions(start, walks, lambda s: _front(*s) == layout.switch)
    to_stove = _fewest_actions(start, walks, lambda s: _front(*s) == layout.stove)
    return {"ring": 3 * to_switch, "pot": 3 * to_stove}


def last_start_steps(max_steps: int, layout: Layout = NORMAL) -> dict[str, int]:
    """The last step an event may start at: it never starts in the last ``3 x N_x`` steps."""
    return {kind: max_steps - QUIET_FACTOR * n for kind, n in handling_steps(layout).items()}


def _late_penalty(count: int, limit: int) -> float:
    """The penalty for a count that just went up by one: at ``limit + 1``, ``2 * limit + 1``, ..."""
    return MISS_PENALTY if count > limit and (count - 1) % limit == 0 else 0.0


# ======================================================================================
#                                        OBJECTS
# ======================================================================================
class Counter(Wall):
    def __init__(self) -> None:
        super().__init__(COUNTER_COLOR)


CALM_COLORS = {Wall: "grey", Counter: COUNTER_COLOR}  # these turn red while the siren rings


class Stove(Wall):
    """Wall panel: it prepares carried food, and with empty hands turns a boiling pot down."""

    def __init__(self) -> None:
        super().__init__(STOVE_COLOR)

    def toggle(self, env, _pos) -> bool:
        env.use_stove()
        return True


class Client(Ball):
    """The client at the counter: toggling takes the order, then hands over prepared food."""

    def __init__(self) -> None:
        super().__init__(WAITING_COLOR)

    def can_pickup(self) -> bool:
        return False

    def toggle(self, env, _pos) -> bool:
        env.talk_to_client()
        return True


class Food(ClosedBox):
    """One portion: raw from the pantry, prepared at the stove."""

    def __init__(self) -> None:
        super().__init__(RAW_COLOR)


# ======================================================================================
#                                      ENVIRONMENT
# ======================================================================================
class ShopEnv(ServiceRoomEnv):
    """The shop: siren, clients, food slips and, with ``pot``, a pot that boils over.

    The state that labeling reads is listed under ``## Labeling API`` in ``environment-code.md``.
    The reward is the shop's own: +1 per served order, ``-0.5`` for every further
    ``walk_limits()["ring"]`` steps a waiting client keeps hearing a ring, and with ``pot``
    ``-0.5`` for every further ``walk_limits()["pot"]`` steps of a boil.

    Args:
        pot: Add the pot that boils over.
        small: Use the ``SMALL`` layout (a 7 x 7 room, the counter, the pantry and the stove close
            together) instead of ``NORMAL``. The events, schedule and rules are the same.
        easy_start_prob: Chance, per episode, of the easy start: the agent stands at the counter
            facing the client spot and a client arrives on step 1. The chance is drawn from the
            reset seed, after every other draw, so the schedule is the same whatever the value.
        slip_chance: Chance that a pickup is followed by a slip. The first pickup of an episode
            always slips while this is above 0 (the fall rule is never idle); at 0 no food ever
            slips. The slip draws are made whatever the value, so every other event keeps its time.
        max_steps: Episode length.
        siren (via kwargs, default True): False means the siren never rings (the switch stays on
            the wall). The ring draws are still made, so every other event keeps its time.
        clients (via kwargs, default True): False means no client ever comes in (the client spot
            stays a counter). The client draws are still made. With no clients every ring is fined
            after the usual walk limit (with clients, only a ring a waiting client hears).
        client_patience (via kwargs, default None = the client waits for ever): a client not served
            this many steps after coming in leaves, the episode ends there as a loss (``terminated``,
            event ``leave``), and the shop reward gets no extra penalty.
        order_needed (via kwargs, default True): False means a client needs no order: it takes food
            the moment it is held at the counter, and the ``order`` event never fires.
        cooking_needed (via kwargs, default True): False means raw food from the pantry counts as
            served; the stove still cooks. Neither option moves a draw or ``N_x``, so every card
            sees the same schedule.
    """

    def __init__(
        self,
        pot: bool = False,
        small: bool = False,
        easy_start_prob: float = 0.0,
        slip_chance: float = SLIP_CHANCE,
        max_steps: int = MAX_STEPS,
        **kwargs,
    ) -> None:
        # the n-th gap is used only after n events, each at least the shortest gap long
        covered = GAP_DRAWS * min(low for low, _ in GAP.values())
        if max_steps > covered:
            raise ValueError(
                f"max_steps {max_steps} is over {covered}: the {GAP_DRAWS} drawn gaps run out"
            )
        if not 0.0 <= easy_start_prob <= 1.0:
            raise ValueError(f"easy_start_prob {easy_start_prob} is not between 0 and 1")
        if not 0.0 <= slip_chance <= 1.0:
            raise ValueError(f"slip_chance {slip_chance} is not between 0 and 1")
        self.layout = SMALL if small else NORMAL
        self.size, self.switch_pos = self.layout.size, self.layout.switch  # read by the base class
        # siren and clients ride in kwargs (the signature is at the argument limit); the base class
        # takes siren itself and Shop builds its own grid, so for the Shop it only records the flag
        self.clients = kwargs.pop("clients", True)
        self.client_patience = kwargs.pop("client_patience", None)
        if self.client_patience is not None and self.client_patience < 1:
            raise ValueError(
                f"client_patience {self.client_patience} is not a step count of 1 or more"
            )
        self.order_needed = kwargs.pop("order_needed", True)
        self.cooking_needed = kwargs.pop("cooking_needed", True)
        kwargs.setdefault("siren", True)
        super().__init__(max_steps=max_steps, **kwargs)
        self.pot, self.face_fallen = pot, True
        self.easy_start_prob, self.easy_start = easy_start_prob, False
        self.slip_chance = slip_chance
        self.pot_boiling = False
        self.client_present = self.order_taken = False
        self._ringing_before = False
        self._last_start = last_start_steps(max_steps, self.layout)
        self._first: dict[str, int] = {}
        self._due: dict[str, int | None] = {}
        self._gaps: dict[str, deque[int]] = {}
        self._slips: list[int | None] = []
        self._pickups = 0
        self._heard = self._boiled = 0
        self._arrived_at = 0

    @staticmethod
    def _gen_mission() -> str:
        return "run the shop"

    def _gen_grid(self, width: int, height: int) -> None:
        self.grid = Grid(width, height)
        self.grid.wall_rect(0, 0, width, height)
        layout = self.layout
        for cell in (layout.client, *layout.counter):
            self.grid.set(*cell, Counter())
        self.grid.set(*layout.pantry, Food())
        self.grid.set(*layout.stove, Stove())
        self.grid.set(*layout.switch, Switch())
        self.agent_pos, self.agent_dir = layout.start, START_DIR

    def picture(self, tile_size: int = TILE_PIXELS) -> np.ndarray:
        """The drawn shop (``shop_visuals``), for pictures made for people.

        Not ``get_frame``: the RGB pixel observation reads that, and it stays MiniGrid's.
        """
        return render_shop(self, tile_size, PREPARED_COLOR)

    # ============================== episode ==============================

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        obs, info = super().reset(seed=seed, options=options)
        # the event seed, hence the easy-start choice, is known only after the grid is built
        if self.easy_start:
            x, y, direction = self.layout.counter_state
            self.agent_pos, self.agent_dir = (x, y), direction  # a tuple, as MiniGrid keeps it
            obs = self.gen_obs()
        return obs, {**info, "schedule": self._schedule_info()}

    def _plan_events(self, rng: np.random.Generator) -> None:
        """Draw the whole schedule; every draw happens whatever the flags."""
        first, gaps = {}, {}
        for kind in ("ring", "client", "pot"):
            first[kind] = int(rng.integers(FIRST_START[kind][0], FIRST_START[kind][1] + 1))
            gaps[kind] = [int(g) for g in rng.integers(*GAP[kind], size=GAP_DRAWS)]
        delays = [int(d) for d in rng.integers(*SLIP_DELAY, size=PICKUP_DRAWS)]
        slips = rng.random(PICKUP_DRAWS) < self.slip_chance
        # the first food of the episode always slips (the rule is never idle), unless slips are off
        slips[0] = self.slip_chance > 0
        # last: no other draw moves; no easy start without clients (it needs a client on step 1)
        self.easy_start = bool(rng.random() < self.easy_start_prob) and self.clients
        if self.easy_start:
            first["client"] = 1  # arrives on the first step, as the normal "arrive" event

        self._gaps = {kind: deque(values) for kind, values in gaps.items()}
        self._first = first
        enabled = {"ring": self.siren, "client": self.clients, "pot": self.pot}
        self._due = {kind: first[kind] if enabled[kind] else None for kind in first}
        self._slips = [delay if slip else None for delay, slip in zip(delays, slips, strict=True)]
        self._pickups = 0
        self._fall_steps = []
        self._heard = self._boiled = 0
        self.siren_ringing = self.pot_boiling = False
        self.client_present = self.order_taken = False
        self.events_this_step = []
        self.event_counts = {
            kind: {"planned": 0, "fired": 0, "skipped": 0}
            for kind in ("ring", "client", "pot", "fall")
        }

    def _schedule_info(self) -> dict:
        return {
            "first_start": dict(self._first),
            "last_start": dict(self._last_start),
            "gaps": {kind: list(gaps)[:5] for kind, gaps in self._gaps.items()},
            "slip_delays": self._slips[:5],
        }

    def step(self, action):
        self._ringing_before = self.siren_ringing
        obs, _, terminated, truncated, info = super().step(action)
        reward = self._shop_reward()
        if self._leave_if_impatient():
            # a loss, not a time-out: the learner does not bootstrap past it
            terminated = True
            info["events"] = list(self.events_this_step)
        return obs, reward, terminated, truncated, info

    def _leave_if_impatient(self) -> bool:
        """With ``client_patience``, a client not served that many steps after coming in leaves.

        Changes state (the client spot, the ``leave`` event); returns whether the client left.
        """
        waited = self.step_count - self._arrived_at
        if self.client_patience is None or not self.client_present or waited < self.client_patience:
            return False
        self.client_present = False
        self.grid.set(*self.layout.client, Counter())
        self._set_siren(self.siren_ringing)  # the new counter cell takes the current colour
        self.events_this_step.append("leave")
        return True

    def _shop_reward(self) -> float:
        reward = 1.0 if "serve" in self.events_this_step else 0.0
        if "ring" in self.events_this_step:
            self._heard = 0
        if "boil" in self.events_this_step:
            self._boiled = 0
        limits = walk_limits(self.layout)
        # with no clients any ring is fined, not only one a waiting client hears
        if self.siren_ringing and (self.client_present or not self.clients):
            self._heard += 1
            reward += _late_penalty(self._heard, limits["ring"])
        if self.pot_boiling:
            self._boiled += 1
            reward += _late_penalty(self._boiled, limits["pot"])
        return reward

    # ============================== events ==============================

    def _start_after(self, kind: str) -> None:
        """Plan the next start of ``kind`` a drawn gap after now, unless it falls in the quiet end."""
        due = self.step_count + self._gaps[kind].popleft()
        self._due[kind] = due if due <= self._last_start[kind] else None

    def press_switch(self) -> None:
        was_ringing = self.siren_ringing
        super().press_switch()
        if was_ringing:
            self._start_after("ring")

    def talk_to_client(self) -> None:
        """Toggling the client takes the order, or hands over prepared food and serves it."""
        client = self.grid.get(*self.layout.client)
        if not self.order_taken:
            self.order_taken, client.color = True, ORDERED_COLOR
            self.events_this_step.append("order")
        elif self._food_ready():
            self.carrying, self.client_present = None, False
            self.grid.set(*self.layout.client, Counter())
            self._set_siren(self.siren_ringing)  # the new counter cell takes the current colour
            self.events_this_step.append("serve")
            if self._ringing_before:
                self.events_this_step.append("serve_ringing")
            self._start_after("client")

    def _food_ready(self) -> bool:
        """Whether the held food may be handed over: prepared, or any food when cooking is not needed."""
        held = self.carrying
        return held is not None and (not self.cooking_needed or held.color == PREPARED_COLOR)

    def use_stove(self) -> None:
        """Toggling the stove cooks raw food for an order taken; with empty hands it turns a boil down."""
        held = self.carrying
        if held is not None and held.color == RAW_COLOR:
            if self.client_present and self.order_taken:  # cook to order: no stocking up
                held.color = PREPARED_COLOR
                self.events_this_step.append("prepare")
        elif held is None and self.pot_boiling:
            self._set_boiling(False)
            self.events_this_step.append("fix")
            self._start_after("pot")

    def _set_siren(self, ringing: bool) -> None:
        """Besides the switch, every wall and counter turns red while the siren rings: it is heard everywhere."""
        super()._set_siren(ringing)
        for cell in self.grid.grid:
            if type(cell) in CALM_COLORS:
                cell.color = RINGING_COLOR if ringing else CALM_COLORS[type(cell)]

    def _set_boiling(self, boiling: bool) -> None:
        self.pot_boiling = boiling
        self.grid.get(*self.layout.stove).color = RINGING_COLOR if boiling else STOVE_COLOR

    def _schedule_fall(self) -> None:
        """Called after every pickup: keep the pantry full, one portion in the shop, plan a slip.

        One slip is pending, owned by the food in hand: a new pickup replaces it, so a slip
        planned for an earlier holding never drops the food of a later one.
        """
        if self.grid.get(*self.layout.pantry) is None:  # the portion came from the pantry
            self.grid.set(*self.layout.pantry, Food())
            for cell in cells_of_type(self, "box"):
                if cell != self.layout.pantry:
                    self.grid.set(*cell, None)
        delay = self._slips[self._pickups] if self._pickups < PICKUP_DRAWS else None
        self._pickups += 1
        self._fall_steps = []
        if delay is not None and self.step_count + delay <= self._last_start["fall"]:
            self._fall_steps.append(self.step_count + delay)
            self.event_counts["fall"]["planned"] += 1

    def _fire_due_events(self) -> None:
        step = self.step_count
        if self._due["ring"] == step:
            self._due["ring"] = None
            self._ring()
        if self._due["client"] == step:
            self._due["client"] = None
            self.grid.set(*self.layout.client, Client())
            self.client_present, self.order_taken = True, not self.order_needed
            self._arrived_at = step
            self.event_counts["client"]["fired"] += 1
            self.events_this_step.append("arrive")
        if self._due["pot"] == step:
            self._due["pot"] = None
            self._set_boiling(True)
            self.event_counts["pot"]["fired"] += 1
            self.events_this_step.append("boil")
        for _ in range(self._fall_steps.count(step)):
            self._fall()


register(id=ENV_ID, entry_point=ShopEnv)
register(id=POT_ENV_ID, entry_point=ShopEnv, kwargs={"pot": True})


# ======================================================================================
#                                    REFERENCE LABELS
# ======================================================================================
def reference_labels(env) -> dict[str, bool]:
    """The propositions of ``environment.md`` after the last step, read from the env."""
    base = env.unwrapped
    events = base.events_this_step
    labels = {
        "siren_ringing": base.siren_ringing,
        "holding_food": base.carrying is not None and base.carrying.type == "box",
        "switch_toggled": "toggle" in events,
        "client_arrived": "arrive" in events,
        "order_taken": "order" in events,
        "food_prepared": "prepare" in events,
        "order_served": "serve" in events,
        "food_fell": "fall" in events,
        "served_while_ringing": "serve_ringing" in events,
    }
    if base.pot:
        labels |= {"pot_boiling": base.pot_boiling, "stove_fixed": "fix" in events}
    return labels


# ======================================================================================
#                                    SCRIPTED POLICY
# ======================================================================================
def scripted_policy(env, ignore: Iterable[str] = ()) -> int:
    """Next action of a shop worker that reacts to the events and keeps every rule.

    It replans on the live grid each call. In order: the step after a food slip it picks the food
    up; a ringing siren it switches off; a boiling pot it turns down (with full hands it puts the
    food down next to the stove first); food lying on the floor it picks up; then it serves the
    client: take the order, fetch food from the pantry, prepare it at the stove, hand it over.

    Args:
        env: The shop, wrapped or not.
        ignore (Iterable[str]): ``"siren"`` never switches the siren off, ``"siren_late"`` serves
            the client at the counter before it switches the siren off, ``"pot"`` never turns the
            pot down, ``"food_fall"`` leaves fallen food lying one step. They make the wrong
            traces.

    Returns:
        int: A MiniGrid action index.
    """
    ignore = set(ignore)
    if ignore - set(IGNORABLE):
        raise ValueError(
            f"cannot ignore {sorted(ignore - set(IGNORABLE))}; choose from {IGNORABLE}"
        )
    base = env.unwrapped
    if "fall" in base.events_this_step and "food_fall" in ignore:
        return int(Actions.done)
    if "fall" in base.events_this_step:  # the fall turned the agent to the food
        return int(Actions.pickup)
    if base.pot_boiling and "pot" not in ignore and base.carrying is not None:
        action = _put_food_down_by_stove(base)
        if action is not None:
            return action
    for target, interaction in _reactions(base, ignore):
        approach = _plan(base, _faces(target))
        if approach is not None:
            return int(approach[0] if approach else interaction)
    return int(Actions.done)


def _reactions(base: ShopEnv, ignore: set[str]) -> list[tuple[tuple[int, int], Actions]]:
    """Cells to face, with the action to take there, in the order the worker tries them."""
    held, serving = base.carrying, []
    floor_food = [] if held is not None else _floor_food(base)
    if base.client_present and not base.order_taken:
        serving.append((base.layout.client, Actions.toggle))
    elif base.client_present and held is None:
        serving.append((base.layout.pantry, Actions.pickup))
    elif base.client_present and held.color == RAW_COLOR and base.cooking_needed:
        serving.append((base.layout.stove, Actions.toggle))
    elif base.client_present:
        serving.append((base.layout.client, Actions.toggle))
    siren = (
        [(base.layout.switch, Actions.toggle)]
        if base.siren_ringing and "siren" not in ignore
        else []
    )
    pot = [(base.layout.stove, Actions.toggle)] if base.pot_boiling and "pot" not in ignore else []
    if "siren_late" in ignore and base.client_present:  # the client first, whatever rings
        return serving + siren + pot
    return siren + pot + floor_food + serving


def _floor_food(base: ShopEnv) -> list[tuple[tuple[int, int], Actions]]:
    boxes = cells_of_type(base, "box")
    return [(cell, Actions.pickup) for cell in boxes if cell != base.layout.pantry]


def _put_food_down_by_stove(base: ShopEnv) -> int | None:
    """Walk to the stove access cell, face a free neighbor and drop the carried food there."""
    x, y, direction = *base.agent_pos, base.agent_dir
    stove_x, stove_y = base.layout.stove
    if (x, y) != (stove_x, stove_y + 1):
        approach = _plan(base, lambda px, py, _d: (px, py) == (stove_x, stove_y + 1))
        return int(approach[0]) if approach else None
    free = [base.grid.get(*_front(x, y, turned)) is None for turned in range(4)]
    if free[direction]:
        return int(Actions.drop)
    return int(Actions.left if free[(direction - 1) % 4] else Actions.right)
