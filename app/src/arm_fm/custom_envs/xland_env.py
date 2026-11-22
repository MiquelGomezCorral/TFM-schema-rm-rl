"""XLand-MiniGrid's four-room 13x13 world as a Gymnasium env, one ruleset per env.

The jitted ``xminigrid`` step does the physics, the rules and the goal; this wrapper adds a
symbolic observation the PPO encoder reads, the Labeling API (what the last step did: the action,
the rule products made, the tile picked up, the goal) and a scripted policy for the benchmark's
plans and walks. Importing it boots JAX, so only the gym entry point in ``xland.py`` loads it.
"""

import json
from collections import deque
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import gymnasium as gym
import jax
import jax.numpy as jnp
import numpy as np
import xminigrid
from gymnasium import spaces
from xminigrid.core.actions import take_action
from xminigrid.core.rules import check_rule
from xminigrid.rendering.rgb_render import render as rgb_render
from xminigrid.types import RuleSet

# A policy step is far too small for an accelerator; set before JAX picks a backend.
jax.config.update("jax_platforms", "cpu")

TILE_NAMES = (
    *("empty", "floor", "wall", "ball", "square", "pyramid", "goal", "key"),
    *("door_locked", "door_closed", "door_open", "hex", "star"),
)
COLOR_NAMES = (
    *("empty", "red", "green", "blue", "purple", "yellow", "grey", "black", "orange"),
    *("white", "brown", "pink"),
)
ACTION_NAMES = ("forward", "turn_right", "turn_left", "pickup", "putdown", "toggle")
FORWARD, TURN_RIGHT, TURN_LEFT, PICKUP, PUTDOWN, TOGGLE = range(len(ACTION_NAMES))
WAIT_ACTION = TURN_RIGHT  # a turn changes only the facing and fires no rule or goal
SIDES = ("up", "right", "down", "left")  # xminigrid's direction order; grid sides, not facing
DELTAS = ((-1, 0), (0, 1), (1, 0), (0, -1))  # (row, column) step of each side
FLOOR, GOAL_TILE, DOOR_CLOSED, DOOR_OPEN = 1, 6, 9, 10
PICKABLE = frozenset((3, 4, 5, 7, 11, 12))  # ball, square, pyramid, key, hex, star
PASSABLE = frozenset((FLOOR, GOAL_TILE, DOOR_OPEN, DOOR_CLOSED))  # a closed door opens on toggle
EMPTY_POCKET = (0, 0)
VIEW = 5  # xminigrid's default view for XLand
MAX_RULES = 9  # the most rules a medium-1m ruleset has

# xminigrid's rule and goal ids (``core/rules.py``, ``core/goals.py``).
RULE_HOLD, RULE_NEAR, RULE_TILE_NEAR = 1, 2, 3
RULE_TILE_NEAR_SIDE, RULE_NEAR_SIDE = range(4, 8), range(8, 12)  # up, right, down, left
GOAL_HOLD, GOAL_NEAR = 1, 3
GOAL_NEAR_SIDE = range(11, 15)  # up, right, down, left
SIDE_EVENT = ("above", "on_right", "below", "on_left")  # the goal event of each agent side

RULESETS: dict[str, dict[str, list]] = json.loads(
    Path(__file__).with_name("xland_rulesets.json").read_text(encoding="utf-8")
)
IGNORABLE = ("goal", *(f"rule-{index}" for index in range(MAX_RULES)))

_ENV, _PARAMS = xminigrid.make("XLand-MiniGrid-R4-13x13")

Tile = tuple[int, int]  # (tile id, color id)


def tile_name(tile: Tile) -> str:
    """``"blue pyramid"``: the color, then the kind."""
    return f"{COLOR_NAMES[tile[1]]} {TILE_NAMES[tile[0]]}"


def tile_id(tile: Tile) -> str:
    """``"blue_pyramid"``: a tile's name as a proposition id part."""
    return tile_name(tile).replace(" ", "_")


# ======================================================================================
#                                       RULESETS
# ======================================================================================


@dataclass(frozen=True)
class Rule:
    """One rule: its place in the ruleset (``rule-<index>``), xminigrid kind, inputs and product."""

    index: int
    kind: int
    inputs: tuple[Tile, ...]
    product: Tile

    @property
    def side(self) -> int | None:
        """The grid side a side rule names, else None."""
        if self.kind in RULE_NEAR_SIDE:
            return self.kind - RULE_NEAR_SIDE.start
        if self.kind in RULE_TILE_NEAR_SIDE:
            return self.kind - RULE_TILE_NEAR_SIDE.start
        return None


@dataclass(frozen=True)
class Ruleset:
    """A decoded ruleset: the goal, the rules in the order they run, the initial objects."""

    goal_kind: int
    goal_tiles: tuple[Tile, ...]
    rules: tuple[Rule, ...]
    init_tiles: tuple[Tile, ...]

    @classmethod
    def decode(cls, raw: dict[str, list]) -> "Ruleset":
        """Read xminigrid's encodings, dropping the empty padding rows.

        Raises:
            ValueError: If the goal is not one of the kinds this module names.
        """
        goal = raw["goal"]
        if goal[0] not in (GOAL_HOLD, GOAL_NEAR, *GOAL_NEAR_SIDE):
            # shortcut: only the goal kinds of the eight benchmark rulesets, add others with a card
            raise ValueError(f"goal kind {goal[0]} is not supported")
        rules = tuple(
            _decode_rule(index, row) for index, row in enumerate(raw["rules"]) if row[0] != 0
        )
        tiles = tuple((row[0], row[1]) for row in raw["init_tiles"] if row[0] != 0)
        return cls(goal[0], ((goal[1], goal[2]),), rules, tiles)

    @property
    def goal_tile(self) -> Tile:
        return self.goal_tiles[0]

    @property
    def goal_side(self) -> int | None:
        return self.goal_kind - GOAL_NEAR_SIDE.start if self.goal_kind in GOAL_NEAR_SIDE else None

    def goal_event(self) -> str:
        """The proposition true on the step the goal fires."""
        if self.goal_kind == GOAL_HOLD:
            return f"{tile_id(self.goal_tile)}_held"
        if self.goal_kind == GOAL_NEAR:
            return f"{tile_id(self.goal_tile)}_reached"
        return f"{tile_id(self.goal_tile)}_{SIDE_EVENT[self.goal_side]}"

    def products(self) -> list[Tile]:
        """Every distinct rule product, in rule order."""
        return list(dict.fromkeys(rule.product for rule in self.rules))

    def pickup_inputs(self) -> list[Tile]:
        """The tiles a rule needs picked up: holding inputs and both inputs of a tile-pair rule."""
        carried = (
            rule.inputs
            for rule in self.rules
            if rule.kind in (RULE_HOLD, RULE_TILE_NEAR, *RULE_TILE_NEAR_SIDE)
        )
        return list(dict.fromkeys(tile for inputs in carried for tile in inputs))

    def propositions(self) -> list[str]:
        """The env page's propositions: one per product, one per pickup input, the goal event."""
        return [
            *(f"{tile_id(tile)}_made" for tile in self.products()),
            *(f"{tile_id(tile)}_picked_up" for tile in self.pickup_inputs()),
            self.goal_event(),
        ]


def _decode_rule(index: int, row: list[int]) -> Rule:
    pairs = [(row[1], row[2]), (row[3], row[4]), (row[5], row[6])]
    if row[0] == RULE_TILE_NEAR or row[0] in RULE_TILE_NEAR_SIDE:
        return Rule(index, row[0], (pairs[0], pairs[1]), pairs[2])
    return Rule(index, row[0], (pairs[0],), pairs[1])


# ======================================================================================
#                                     ENVIRONMENT
# ======================================================================================


@jax.jit
def _reset(params: Any, key: jax.Array) -> Any:
    return _ENV.reset(params, key)


@jax.jit
def _step(params: Any, timestep: Any, action: jax.Array) -> tuple[Any, jax.Array]:
    """The library's own step, plus whether each rule changed the world on it.

    The flags replay xminigrid's order (the action, then each rule on the grid the one before
    left), one rule at a time.
    """
    state = timestep.state
    grid, agent, position = take_action(state.grid, state.agent, action)

    def apply(carry: tuple, encoding: jax.Array) -> tuple[tuple, jax.Array]:
        before_grid, before_agent = carry
        after_grid, after_agent = check_rule(
            encoding[None], before_grid, before_agent, action, position
        )
        changed = jnp.any(after_grid != before_grid) | jnp.any(
            after_agent.pocket != before_agent.pocket
        )
        return (after_grid, after_agent), changed

    _, fired = jax.lax.scan(apply, (grid, agent), state.rule_encoding)
    return _ENV.step(params, timestep, action), fired


class XLandEnv(gym.Env):
    """One XLand-MiniGrid ruleset on the four-room 13x13 grid (``ruleset`` names it).

    The observation is the 5x5 view ahead of the agent (tile and color ids per cell) with the
    pocket's tile, the pocket's color and the facing broadcast as three more channels, so a
    policy sees what it carries and where it looks: ``(5, 5, 5)`` uint8. After each step the
    Labeling API attributes say what the step did (``environment-code.md`` lists them).
    """

    metadata: ClassVar[dict[str, Any]] = {"render_modes": ["rgb_array"], "render_fps": 4}

    def __init__(self, ruleset: str, render_mode: str | None = None) -> None:
        raw = RULESETS[ruleset]
        self.ruleset_name = ruleset
        self.ruleset = Ruleset.decode(raw)
        encodings = RuleSet(
            goal=jnp.asarray(raw["goal"], jnp.uint8),
            rules=jnp.asarray(raw["rules"], jnp.uint8),
            init_tiles=jnp.asarray(raw["init_tiles"], jnp.uint8),
        )
        self.params = _PARAMS.replace(ruleset=encodings)
        self.max_steps = int(self.params.max_steps)
        self.render_mode = render_mode
        self.action_space = spaces.Discrete(len(ACTION_NAMES))
        self.observation_space = spaces.Box(0, 255, (VIEW, VIEW, 5), np.uint8)
        self._timestep: Any = None
        self._clear_step()

    def _clear_step(self) -> None:
        self.last_action: str | None = None
        self.products_made: tuple[str, ...] = ()
        self.picked_up: str | None = None
        self.goal_reached = False

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed, options=options)
        key_seed = int(self.np_random.integers(2**31)) if seed is None else seed
        self._timestep = _reset(self.params, jax.random.key(key_seed))
        self._read_state(self._timestep)
        self._clear_step()
        return self._observation(), {}

    def step(self, action):
        action = int(action)
        front = self.front_tile()
        empty_handed = self.pocket_tile == EMPTY_POCKET
        self._timestep, fired = _step(self.params, self._timestep, action)
        reward, discount, step_type = self._read_state(self._timestep)
        terminated = discount == 0  # xminigrid zeroes the discount only on the goal
        truncated = step_type == 2 and not terminated  # StepType.LAST
        flags = np.asarray(fired)
        self.last_action = ACTION_NAMES[action]
        self.products_made = tuple(
            tile_name(rule.product) for rule in self.ruleset.rules if flags[rule.index]
        )
        took = action == PICKUP and empty_handed and front[0] in PICKABLE
        self.picked_up = tile_name(front) if took else None
        self.goal_reached = terminated
        return self._observation(), reward, terminated, truncated, {}

    def peek(self, action: int) -> tuple[bool, tuple[bool, ...]]:
        """Whether ``action`` would fire the goal, and each rule row, without taking it."""
        timestep, fired = _step(self.params, self._timestep, int(action))
        return bool(timestep.discount == 0), tuple(bool(flag) for flag in np.asarray(fired))

    def _read_state(self, timestep: Any) -> tuple[float, float, int]:
        state = timestep.state
        grid, position, direction, pocket, view, reward, discount, step_type = jax.device_get(
            (
                state.grid,
                state.agent.position,
                state.agent.direction,
                state.agent.pocket,
                timestep.observation,
                timestep.reward,
                timestep.discount,
                timestep.step_type,
            )
        )
        self.grid = np.asarray(grid)
        self.agent_pos = (int(position[0]), int(position[1]))
        self.agent_dir = int(direction)
        self.pocket_tile: Tile = (int(pocket[0]), int(pocket[1]))
        self._view = np.asarray(view, np.uint8)
        return float(reward), float(discount), int(step_type)

    def _observation(self) -> np.ndarray:
        extra = np.array([*self.pocket_tile, self.agent_dir], np.uint8)
        return np.concatenate([self._view, np.broadcast_to(extra, (VIEW, VIEW, 3))], axis=-1)

    # ============================== Labeling API ==============================

    @property
    def pocket(self) -> str | None:
        """The carried tile's name, or None with an empty pocket."""
        return None if self.pocket_tile == EMPTY_POCKET else tile_name(self.pocket_tile)

    @property
    def tiles(self) -> tuple[tuple[str, ...], ...]:
        """Every cell's tile name, by row then column."""
        return tuple(tuple(tile_name((int(t), int(c))) for t, c in row) for row in self.grid)

    def front_tile(self) -> Tile:
        """The tile of the cell the agent faces."""
        dy, dx = DELTAS[self.agent_dir]
        cell = self.grid[self.agent_pos[0] + dy, self.agent_pos[1] + dx]
        return int(cell[0]), int(cell[1])

    def render(self) -> np.ndarray:
        """An RGB picture of the whole grid with the agent's view highlighted."""
        return rgb_render(self.grid, self._timestep.state.agent, VIEW)


# ======================================================================================
#                                REFERENCE LABELS
# ======================================================================================


def reference_labels(env: Any) -> dict[str, bool]:
    """The true value of every proposition of the env's ruleset after the last step."""
    base = env.unwrapped
    ruleset = base.ruleset
    labels = {
        f"{tile_id(tile)}_made": tile_name(tile) in base.products_made
        for tile in ruleset.products()
    }
    labels |= {
        f"{tile_id(tile)}_picked_up": base.picked_up == tile_name(tile)
        for tile in ruleset.pickup_inputs()
    }
    labels[ruleset.goal_event()] = base.goal_reached
    return labels


# ======================================================================================
#                                  SCRIPTED POLICY
# ======================================================================================
# Goal regression on the live grid, planned again every step: reach the goal; a tile the goal
# or a rule needs and the grid lacks is made by the first rule that makes it. Navigation is a
# breadth-first search over (row, column, facing); a closed door on the route gets a toggle.

MAKE_DEPTH = 6  # the longest chain of rules the policy plans through


@dataclass(frozen=True)
class _World:
    grid: np.ndarray
    pos: tuple[int, int]
    facing: int
    pocket: Tile
    ruleset: Ruleset
    ignored: frozenset[str]

    def tile(self, row: int, column: int) -> Tile:
        return int(self.grid[row, column, 0]), int(self.grid[row, column, 1])

    def cells_of(self, tile: Tile) -> list[tuple[int, int]]:
        rows, columns = np.nonzero((self.grid[..., 0] == tile[0]) & (self.grid[..., 1] == tile[1]))
        return [(int(row), int(column)) for row, column in zip(rows, columns, strict=True)]

    def front(self, row: int, column: int, facing: int) -> tuple[int, int]:
        return row + DELTAS[facing][0], column + DELTAS[facing][1]

    def can_pick(self, tile: Tile) -> bool:
        return tile[0] in PICKABLE and f"pickup-{tile_id(tile)}" not in self.ignored


def scripted_policy(env: Any, ignore: Iterable[str] = ()) -> int:
    """The next action toward the goal; ``ignore`` names what never to fire.

    ``"goal"`` keeps the goal from firing, ``"rule-<i>"`` keeps rule ``i`` from firing (it is
    never planned, and an action that would fire it by the way waits instead) and
    ``"pickup-<tile id>"`` never picks that tile up (a tile-pair rule carries its other input).
    A goal or tile out of reach waits.
    """
    base = env.unwrapped
    world = _World(
        base.grid, base.agent_pos, base.agent_dir, base.pocket_tile, base.ruleset, frozenset(ignore)
    )
    action = _goal_action(world)
    if action is None:
        return WAIT_ACTION
    goal, fired = base.peek(action)
    blocked = {f"rule-{index}" for index, flag in enumerate(fired) if flag}
    if goal:
        blocked.add("goal")
    if action == PICKUP:
        blocked.add(f"pickup-{tile_id(base.front_tile())}")
    return WAIT_ACTION if blocked & world.ignored else action


def _goal_action(world: _World) -> int | None:
    target = world.ruleset.goal_tile
    if world.ruleset.goal_kind == GOAL_HOLD:
        return PICKUP if world.pocket == target else _obtain(world, target, 0)
    if world.ruleset.goal_kind == GOAL_NEAR:
        return _bump(world, target, None, 0)
    return _bump(world, target, world.ruleset.goal_side, 0)


def _obtain(world: _World, target: Tile, depth: int) -> int | None:
    """The next action toward holding ``target`` (picked up, or made and then picked up)."""
    cells = world.cells_of(target)
    if not cells:
        return _make(world, target, depth)  # making it may need what the pocket holds
    if not world.can_pick(target):
        return None
    if world.pocket != EMPTY_POCKET:
        return _put_down(world, lambda _cell: True)
    return _face(world, set(cells), PICKUP)


def _bump(world: _World, target: Tile, side: int | None, depth: int) -> int | None:
    """The next action toward a ``forward`` or ``putdown`` with ``target`` beside the agent.

    ``side`` None: any neighbour (face it and press forward against it). A grid side: stand with
    the tile on that side, facing it, or put the carried tile down on that side.
    """
    if world.pocket == target:
        if side is None:
            return _put_down(world, lambda _cell: True)
        return _put_down(world, lambda _cell: True, facing=side)
    cells = world.cells_of(target)
    if not cells:
        return _make(world, target, depth)
    if side is None:
        return _face(world, set(cells), FORWARD)
    poses = {(row - DELTAS[side][0], column - DELTAS[side][1], side) for row, column in cells}
    action = _go(world, lambda *pose: pose in poses, FORWARD)
    if action is None and world.can_pick(target):
        return _obtain(world, target, depth)  # no free cell beside it: carry it instead
    return action


def _make(world: _World, product: Tile, depth: int) -> int | None:
    """The next action of the first rule that makes ``product`` and can be planned."""
    if depth >= MAKE_DEPTH:
        return None
    for rule in world.ruleset.rules:
        if rule.product != product or f"rule-{rule.index}" in world.ignored:
            continue
        action = _rule_action(world, rule, depth + 1)
        if action is not None:
            return action
    return None


def _rule_action(world: _World, rule: Rule, depth: int) -> int | None:
    if rule.kind == RULE_HOLD:
        return PICKUP if world.pocket == rule.inputs[0] else _obtain(world, rule.inputs[0], depth)
    if rule.kind == RULE_NEAR:
        return _bump(world, rule.inputs[0], None, depth)
    if rule.kind in RULE_NEAR_SIDE:
        return _bump(world, rule.inputs[0], rule.side, depth)
    if rule.kind == RULE_TILE_NEAR:
        return _pair_action(world, rule, depth)
    return None  # shortcut: side tile-pair rules are not planned; add them when a card needs one


def _pair_action(world: _World, rule: Rule, depth: int) -> int | None:
    """Carry one input and put it down beside the other."""
    first, second = rule.inputs
    if world.pocket in rule.inputs:
        other = second if world.pocket == first else first
        cells = world.cells_of(other)
        if not cells:
            return _make(world, other, depth)
        return _put_down(world, lambda cell: _touches(cell, cells))
    missing = [tile for tile in rule.inputs if not world.cells_of(tile)]
    if missing:
        return _make(world, missing[0], depth)
    return _obtain(world, first if world.can_pick(first) else second, depth)


def _touches(cell: tuple[int, int], cells: list[tuple[int, int]]) -> bool:
    return any(abs(cell[0] - row) + abs(cell[1] - column) == 1 for row, column in cells)


def _face(world: _World, cells: set[tuple[int, int]], action: int) -> int | None:
    """Turn to face one of ``cells`` (walking as needed), then ``action``."""
    return _go(world, lambda row, column, facing: world.front(row, column, facing) in cells, action)


def _put_down(
    world: _World, wanted: Callable[[tuple[int, int]], bool], facing: int | None = None
) -> int | None:
    """Put the carried tile on a floor cell ``wanted`` accepts, facing ``facing`` if given."""

    def spot(row: int, column: int, direction: int) -> bool:
        cell = world.front(row, column, direction)
        free = world.tile(*cell)[0] == FLOOR
        return free and (facing is None or direction == facing) and wanted(cell)

    return _go(world, spot, PUTDOWN)


def _go(world: _World, reached: Callable[[int, int, int], bool], action: int) -> int | None:
    """The first action of the shortest route to a pose ``reached`` accepts, then ``action``."""
    route = _route(world, reached)
    if route is None:
        return None
    if not route:
        return action
    if route[0] == FORWARD and world.tile(*world.front(*world.pos, world.facing))[0] == DOOR_CLOSED:
        return TOGGLE
    return route[0]


def _route(world: _World, reached: Callable[[int, int, int], bool]) -> list[int] | None:
    start = (*world.pos, world.facing)
    if reached(*start):
        return []
    parents: dict[tuple[int, int, int], tuple[tuple[int, int, int], int] | None] = {start: None}
    queue = deque([start])
    while queue:
        pose = queue.popleft()
        for action, after in _moves(world, pose):
            if after in parents:
                continue
            parents[after] = (pose, action)
            if reached(*after):
                return _unwind(parents, after)
            queue.append(after)
    return None


def _moves(world: _World, pose: tuple[int, int, int]) -> Iterator[tuple[int, tuple]]:
    row, column, facing = pose
    yield TURN_RIGHT, (row, column, (facing + 1) % 4)
    yield TURN_LEFT, (row, column, (facing - 1) % 4)
    ahead = world.front(row, column, facing)
    if world.tile(*ahead)[0] in PASSABLE:
        yield FORWARD, (*ahead, facing)


def _unwind(parents: dict, pose: tuple[int, int, int]) -> list[int]:
    actions = []
    while parents[pose] is not None:
        pose, action = parents[pose]
        actions.append(action)
    return actions[::-1]
