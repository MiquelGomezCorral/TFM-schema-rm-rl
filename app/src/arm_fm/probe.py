"""Scripted solver that probes a Reward Machine and its labeling in the real MiniGrid env.

The player reads the full grid, plans with a breadth-first search over (x, y, direction) and
acts only through ``env.step``, so every step goes through the labeling and the RM exactly as
training does. It solves key-and-door tasks on any layout: it opens the locked doors with the
key of their colour, moves objects that block a door, and then takes the mission's target.
"""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from src.compiler import PaperRewardMachine

from .environments import make_environment
from .runtime import RewardMachineEnvironment, RewardMachineRuntime

LEFT, RIGHT, FORWARD, PICKUP, DROP, TOGGLE = 0, 1, 2, 3, 4, 5
DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))
MAX_STAGES = 12
_PICKUP_MISSION = re.compile(r"pick up (?:the |a )?(?:(\w+) )?(ball|box|key)")


class ProbeError(RuntimeError):
    """The scripted player cannot solve the layout."""


@dataclass
class EpisodeProbe:
    """What one scripted episode did to the RM."""

    gym_id: str
    seed: int
    steps: int = 0
    solved: bool = False
    rm_path: list[str] = field(default_factory=list)
    final_entered: int | None = None  # the step that first entered a final RM state
    reached_final: bool = False
    events_fired: set[str] = field(default_factory=set)
    error: str = ""


def probe_labeling(
    machine: PaperRewardMachine,
    labeling_source: str,
    gym_ids: Sequence[str],
    seeds: Sequence[int],
    final_states: Sequence[str],
) -> list[EpisodeProbe]:
    """Solve every ``gym_id`` x ``seed`` layout and report the RM path of each episode."""
    results = []
    for gym_id in gym_ids:
        for seed in seeds:
            results.append(_probe_episode(machine, labeling_source, gym_id, seed, final_states))
    return results


def _probe_episode(
    machine: PaperRewardMachine,
    labeling_source: str,
    gym_id: str,
    seed: int,
    final_states: Sequence[str],
) -> EpisodeProbe:
    env = make_environment(gym_id)
    episode = EpisodeProbe(gym_id, seed)
    try:
        wrapped = RewardMachineEnvironment(env, RewardMachineRuntime(machine), labeling_source)
        wrapped.reset(seed=seed)
        episode.rm_path = [wrapped.runtime.state]
        player = _Player(wrapped, episode, final_states)
        player.solve()
    except Exception as error:  # a labeling crash or an unsolvable layout is a probe result
        episode.error = f"{type(error).__name__}: {error}"
    finally:
        env.close()
    episode.reached_final = bool(episode.rm_path) and episode.rm_path[-1] in set(final_states)
    return episode


class _Player:
    """Plans on the live grid and acts through the RM-wrapped env."""

    def __init__(
        self, env: RewardMachineEnvironment, episode: EpisodeProbe, final_states: Sequence[str]
    ) -> None:
        self.env = env
        self.final_states = frozenset(final_states)
        self.base = env.unwrapped
        self.episode = episode
        self.done = False

    # ============================== acting ==============================

    def act(self, action: int) -> None:
        if self.done:
            raise ProbeError("the episode already ended")
        _, reward, terminated, truncated, info = self.env.step(action)
        self.episode.steps += 1
        self.episode.events_fired |= {name for name, value in info["valuation"].items() if value}
        if info["rm_state"] != self.episode.rm_path[-1]:
            self.episode.rm_path.append(info["rm_state"])
            if info["rm_state"] in self.final_states and self.episode.final_entered is None:
                self.episode.final_entered = self.episode.steps
        if terminated or truncated:
            self.done = True
            self.episode.solved = terminated and reward - info["rm_reward"] > 0

    def execute(self, actions: Sequence[int]) -> None:
        for action in actions:
            if action == FORWARD:
                front = self.cell(*self.front())
                if front is not None and front.type == "door" and not front.is_open:
                    self.act(TOGGLE)
            self.act(action)

    # ============================== the grid ==============================

    @property
    def position(self) -> tuple[int, int]:
        return tuple(self.base.agent_pos)

    def cell(self, x: int, y: int):
        return self.base.grid.get(x, y)

    def front(self) -> tuple[int, int]:
        dx, dy = DIRECTIONS[self.base.agent_dir]
        return self.position[0] + dx, self.position[1] + dy

    def objects(self, kind: str, color: str | None = None) -> list[tuple[int, int]]:
        found = []
        for x in range(self.base.width):
            for y in range(self.base.height):
                item = self.cell(x, y)
                if item is not None and item.type == kind and color in (None, item.color):
                    found.append((x, y))
        return found

    def is_free(self, x: int, y: int) -> bool:
        item = self.cell(x, y)
        return item is None or item.type == "goal" or (item.type == "door" and not item.is_locked)

    def plan(self, reached: Callable[[int, int, int], bool]) -> list[int] | None:
        """Shortest action list to a (x, y, direction) state satisfying ``reached``, or None."""
        start = (*self.position, self.base.agent_dir)
        queue = deque([(start, [])])
        seen = {start}
        while queue:
            (x, y, direction), actions = queue.popleft()
            if reached(x, y, direction):
                return actions
            dx, dy = DIRECTIONS[direction]
            moves = [((x, y, (direction - 1) % 4), LEFT), ((x, y, (direction + 1) % 4), RIGHT)]
            if self.is_free(x + dx, y + dy):
                moves.append(((x + dx, y + dy, direction), FORWARD))
            for state, action in moves:
                if state not in seen:
                    seen.add(state)
                    queue.append((state, [*actions, action]))
        return None

    def go_facing(self, target: tuple[int, int]) -> None:
        """Walk to a cell that faces ``target``; the player must have checked it can."""
        path = self.plan_facing(target)
        if path is None:
            raise ProbeError(f"no cell can face {target}")
        self.execute(path)

    def reachable(self, blocked: tuple[int, int] | None = None) -> set[tuple[int, int]]:
        """Cells the agent can walk to, optionally with one more cell occupied."""
        start = self.position
        seen = {start}
        queue = deque([start])
        while queue:
            x, y = queue.popleft()
            for dx, dy in DIRECTIONS:
                cell = (x + dx, y + dy)
                if cell != blocked and cell not in seen and self.is_free(*cell):
                    seen.add(cell)
                    queue.append(cell)
        return seen

    def plan_facing(self, target: tuple[int, int]) -> list[int] | None:
        tx, ty = target
        return self.plan(
            lambda x, y, d: (
                (x + DIRECTIONS[d][0], y + DIRECTIONS[d][1]) == (tx, ty) and (x, y) != (tx, ty)
            )
        )

    # ============================== the task ==============================

    def target(self) -> tuple[str, str | None]:
        mission = str(getattr(self.base, "mission", "")).lower()
        if "goal" in mission:
            return "goal", None
        match = _PICKUP_MISSION.search(mission)
        if match is None:
            raise ProbeError(f"cannot read a target from the mission {mission!r}")
        return match.group(2), match.group(1)

    def solve(self) -> None:
        kind, color = self.target()
        for _ in range(MAX_STAGES):
            if self.done:
                return
            if self.take_target(kind, color):
                return
            if not self.open_next_door(kind):
                raise ProbeError("no door can be opened and the target is unreachable")
        raise ProbeError("the layout needs more stages than the player allows")

    def take_target(self, kind: str, color: str | None) -> bool:
        for position in self.objects(kind, color):
            if kind == "goal":
                path = self.plan(lambda x, y, _d, p=position: (x, y) == p)
                if path is not None:
                    self.execute(path)
                    return True
                continue
            if self.pick_up(position):
                return True
        return False

    def pick_up(self, position: tuple[int, int]) -> bool:
        """Take the object at ``position``; False when no reachable cell faces it."""
        if self.plan_facing(position) is None:
            return False
        self.empty_hands()
        self.go_facing(position)
        self.act(PICKUP)
        return True

    def open_next_door(self, target_kind: str) -> bool:
        for door in self.objects("door"):
            if not self.cell(*door).is_locked:
                continue
            color = self.cell(*door).color
            if self.plan_facing(door) is None:
                if self.clear_blocker(door, target_kind):
                    return True
                continue
            if not self.hold_key(color):
                continue
            self.go_facing(door)
            self.act(TOGGLE)
            return True
        return False

    def hold_key(self, color: str) -> bool:
        carrying = self.base.carrying
        if carrying is not None and carrying.type == "key" and carrying.color == color:
            return True
        return any(self.pick_up(key) for key in self.objects("key", color))

    def clear_blocker(self, door: tuple[int, int], target_kind: str) -> bool:
        """Move a ball, box or key that stands in front of ``door`` out of the way."""
        for dx, dy in DIRECTIONS:
            spot = (door[0] + dx, door[1] + dy)
            item = self.cell(*spot)
            if item is None or item.type in {"wall", "door", "goal"} or item.type == target_kind:
                continue
            if self.pick_up(spot):
                return True
        return False

    def empty_hands(self) -> None:
        """Drop the carried object where it blocks nothing.

        The cell must be empty, at least 2 steps from every door, and must not cut off any cell the
        agent can reach now.
        """
        if self.base.carrying is None:
            return
        doors = self.objects("door")
        for _ in range(8):
            for _ in range(4):
                if self.is_safe_drop(self.front(), doors):
                    self.act(DROP)
                    return
                self.act(RIGHT)
            self.execute([FORWARD])
        raise ProbeError("no safe cell to drop the carried object")

    def is_safe_drop(self, cell: tuple[int, int], doors: Sequence[tuple[int, int]]) -> bool:
        x, y = cell
        if self.cell(x, y) is not None or any(abs(x - dx) + abs(y - dy) < 2 for dx, dy in doors):
            return False
        return len(self.reachable(blocked=cell)) == len(self.reachable()) - 1
