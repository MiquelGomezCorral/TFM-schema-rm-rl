"""Service room: a fixed MiniGrid room whose events come from a seeded schedule.

``gym.make("MiniGrid-ServiceRoom-v0", siren=..., box=..., require=[...], max_steps=200)``.
The reset seed sets only the event schedule, so one seed always plays the same events.

The rules (schedule, step order, reward) are in ``environment.md`` and the code-side facts in
``environment-code.md``, both in ``experiments/benchmark/envs/service-room/``.

Import nothing from ``src.arm_fm``: ``environments.py`` imports this module to register the id,
and the scripted policy has its own small search instead of the one in ``probe.py``.
"""

from collections import deque
from collections.abc import Callable, Iterable, Sequence

import numpy as np
from gymnasium.envs.registration import register
from minigrid.core.actions import Actions
from minigrid.core.constants import COLORS
from minigrid.core.grid import Grid
from minigrid.core.mission import MissionSpace
from minigrid.core.world_object import Box, Goal, Wall
from minigrid.minigrid_env import MiniGridEnv
from minigrid.utils.rendering import fill_coords, point_in_rect

ENV_ID = "MiniGrid-ServiceRoom-v0"
SIZE = 8
FIRST_RING_LAST = 4  # the first ring comes at a step from 1 to this
START, START_DIR = (1, 1), 0  # top-left corner, facing right
BOX_POS = (4, 2)
SWITCH_POS = (0, 5)  # in the west wall; the agent toggles it from (1, 5) facing left
EXIT_POS = (6, 6)
SILENT_COLOR, RINGING_COLOR, BOX_COLOR = "blue", "red", "purple"
REQUIREMENTS = ("siren_silent", "holding_box")
IGNORABLE = ("siren", "box_fall")
DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))  # right, down, left, up


# ======================================================================================
#                                        OBJECTS
# ======================================================================================
class Switch(Wall):
    """Wall panel that silences the siren; it encodes as a wall, red while ringing, else blue."""

    def __init__(self) -> None:
        super().__init__(SILENT_COLOR)

    def render(self, img) -> None:
        fill_coords(img, point_in_rect(0, 1, 0, 1), COLORS["grey"])
        fill_coords(img, point_in_rect(0.2, 0.8, 0.2, 0.8), COLORS[self.color])

    def toggle(self, env, _pos) -> bool:
        env.press_switch()
        return True


class ClosedBox(Box):
    """Box that stays whole when toggled (MiniGrid's box opens and disappears)."""

    def toggle(self, _env, _pos) -> bool:
        return False


# ======================================================================================
#                                      ENVIRONMENT
# ======================================================================================
class ServiceRoomEnv(MiniGridEnv):
    """The fixed room with a seeded siren and falling box.

    The state that labeling reads is listed under ``## Labeling API`` in ``environment-code.md``.
    A plain room (no siren, no box, nothing required) is the default.

    Raises:
        ValueError: If ``require`` names an unknown condition, or asks for the box without it.
    """

    def __init__(
        self,
        siren: bool = False,
        box: bool = False,
        require: Sequence[str] = (),
        max_steps: int = 200,
        **kwargs,
    ) -> None:
        unknown = set(require) - set(REQUIREMENTS)
        if unknown:
            raise ValueError(f"unknown require {sorted(unknown)}; choose from {REQUIREMENTS}")
        if "holding_box" in require and not box:
            raise ValueError("require 'holding_box' needs box=True")
        super().__init__(
            mission_space=MissionSpace(mission_func=self._gen_mission),
            width=SIZE,
            height=SIZE,
            max_steps=max_steps,
            **kwargs,
        )
        self.siren, self.box, self.require = siren, box, tuple(require)
        self.siren_ringing = False
        self.events_this_step: list[str] = []
        self.event_counts: dict[str, dict[str, int]] = {}
        self._ring_steps: list[int] = []
        self._fall_delays: list[int] = []
        self._fall_steps: list[int] = []  # absolute steps, set by pickups

    @staticmethod
    def _gen_mission() -> str:
        return "reach the exit"

    def _gen_grid(self, width: int, height: int) -> None:
        self.grid = Grid(width, height)
        self.grid.wall_rect(0, 0, width, height)
        self.grid.set(*EXIT_POS, Goal())
        if self.siren:
            self.grid.set(*SWITCH_POS, Switch())
        if self.box:
            self.grid.set(*BOX_POS, ClosedBox(BOX_COLOR))
        self.agent_pos, self.agent_dir = START, START_DIR

    def _reward(self) -> float:
        siren_ok = not (self.siren_ringing and "siren_silent" in self.require)
        box_ok = self.carrying is not None or "holding_box" not in self.require
        return super()._reward() if siren_ok and box_ok else 0.0

    # ============================== episode ==============================

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        obs, _ = super().reset(seed=seed, options=options)
        # Without a seed the schedule comes from the env's own stream, so autoresets still vary;
        # the info reports the seed used, so any episode can be replayed from it.
        event_seed = int(self.np_random.integers(2**31)) if seed is None else seed
        self._plan_events(np.random.default_rng(event_seed))
        return obs, {"events": [], "event_seed": event_seed}

    def _plan_events(self, rng: np.random.Generator) -> None:
        """Draw the whole schedule; every draw happens whatever the flags."""
        first_ring = int(rng.integers(1, FIRST_RING_LAST + 1))
        second_ring = first_ring + int(rng.integers(8, 31))
        has_second_ring = rng.random() < 0.5
        fall_delays = [int(rng.integers(2, 7)), int(rng.integers(2, 7))]
        has_second_fall = rng.random() < 0.5

        rings = [first_ring, second_ring] if has_second_ring else [first_ring]
        falls = fall_delays[: 2 if has_second_fall else 1]
        self._ring_steps = rings if self.siren else []
        self._fall_delays = falls if self.box else []
        self._fall_steps = []
        self.siren_ringing = False
        self.events_this_step = []
        self.event_counts = {
            "ring": {"planned": len(self._ring_steps), "fired": 0, "skipped": 0},
            "fall": {"planned": len(self._fall_delays), "fired": 0, "skipped": 0},
        }

    def step(self, action):
        self.events_this_step = []
        carried = self.carrying
        obs, reward, terminated, truncated, _ = super().step(action)
        if carried is None and self.carrying is not None:  # the box is the only pickable object
            self._schedule_fall()
        if not (terminated or truncated):
            self._fire_due_events()
            obs = self.gen_obs()
        return obs, reward, terminated, truncated, {"events": list(self.events_this_step)}

    # ============================== events ==============================

    def press_switch(self) -> None:
        """Record a toggle of the switch and silence the siren (called by ``Switch.toggle``)."""
        self.events_this_step.append("toggle")
        self._set_siren(False)

    def _set_siren(self, ringing: bool) -> None:
        self.siren_ringing = ringing
        self.grid.get(*SWITCH_POS).color = RINGING_COLOR if ringing else SILENT_COLOR

    def _schedule_fall(self) -> None:
        """The n-th pickup of the box schedules the n-th planned fall."""
        scheduled = len(self._fall_steps)
        if scheduled < len(self._fall_delays):
            self._fall_steps.append(self.step_count + self._fall_delays[scheduled])

    def _fire_due_events(self) -> None:
        if self.step_count in self._ring_steps:
            self._ring()
        for _ in range(self._fall_steps.count(self.step_count)):
            self._fall()

    def _ring(self) -> None:
        counts = self.event_counts["ring"]
        if self.siren_ringing:
            counts["skipped"] += 1
            return
        self._set_siren(True)
        counts["fired"] += 1
        self.events_this_step.append("ring")

    def _fall(self) -> None:
        counts = self.event_counts["fall"]
        landing = self._landing_cell() if self.carrying is not None else None
        if landing is None:
            counts["skipped"] += 1
            return
        self.grid.set(*landing, self.carrying)
        self.carrying.cur_pos = np.array(landing)
        self.carrying = None
        counts["fired"] += 1
        self.events_this_step.append("fall")

    def _landing_cell(self) -> tuple[int, int] | None:
        """First free cell among front, right, back, left of the agent."""
        for turn in range(4):
            dx, dy = DIRECTIONS[(self.agent_dir + turn) % 4]
            cell = (self.agent_pos[0] + dx, self.agent_pos[1] + dy)
            if self.grid.get(*cell) is None:
                return cell
        return None


register(id=ENV_ID, entry_point=ServiceRoomEnv)


# ======================================================================================
#                                    REFERENCE LABELS
# ======================================================================================
def reference_labels(env) -> dict[str, bool]:
    """The five propositions of ``environment.md`` after the last step, read from the env."""
    base = env.unwrapped
    under_agent = base.grid.get(*base.agent_pos)
    return {
        "siren_ringing": base.siren_ringing,
        "switch_toggled": "toggle" in base.events_this_step,
        "holding_box": base.carrying is not None and base.carrying.type == "box",
        "box_fell": "fall" in base.events_this_step,
        "at_exit": under_agent is not None and under_agent.type == "goal",
    }


# ======================================================================================
#                                    SCRIPTED POLICY
# ======================================================================================
def scripted_policy(env, ignore: Iterable[str] = ()) -> int:
    """Next action of a player that reacts to the events and then walks to the exit.

    It replans on the live grid each call. In order: when the siren rings go toggle the switch;
    when the box is required and lies on the floor pick it up; then go to the exit. A step is
    skipped when its target cannot be faced (a fallen box may block the cell in front of the
    switch, the access cell (1, 5): picking the box up clears it).

    Args:
        env: The service room, wrapped or not.
        ignore (Iterable[str]): ``"siren"`` skips the switch, ``"box_fall"`` skips picking the
            box up again once it has fallen. They make the wrong traces.

    Returns:
        int: A MiniGrid action index.
    """
    ignore = set(ignore)
    if ignore - set(IGNORABLE):
        raise ValueError(
            f"cannot ignore {sorted(ignore - set(IGNORABLE))}; choose from {IGNORABLE}"
        )
    base = env.unwrapped
    for target, interaction in _reactions(base, ignore):
        approach = _plan(base, _faces(target))
        if approach is not None:
            return int(approach[0] if approach else interaction)
    approach = _plan(base, lambda x, y, _d: (x, y) == EXIT_POS)
    if not approach:
        raise RuntimeError("the exit cannot be reached")
    return int(approach[0])


def _reactions(base: ServiceRoomEnv, ignore: set[str]) -> list[tuple[tuple[int, int], Actions]]:
    """Cells to face before the exit, with the action to take there."""
    reactions = []
    if base.siren_ringing and "siren" not in ignore:
        reactions.append((SWITCH_POS, Actions.toggle))
    fallen = base.event_counts["fall"]["fired"] > 0
    if (
        "holding_box" in base.require
        and base.carrying is None
        and not (fallen and "box_fall" in ignore)
    ):
        reactions += [(cell, Actions.pickup) for cell in cells_of_type(base, "box")]
    return reactions


def cells_of_type(base: ServiceRoomEnv, kind: str) -> list[tuple[int, int]]:
    """Grid cells holding an object of the given MiniGrid type name."""
    cells = ((x, y) for x in range(base.width) for y in range(base.height))
    return [cell for cell in cells if getattr(base.grid.get(*cell), "type", None) == kind]


def _faces(target: tuple[int, int]) -> Callable[[int, int, int], bool]:
    def reached(x: int, y: int, direction: int) -> bool:
        dx, dy = DIRECTIONS[direction]
        return (x + dx, y + dy) == target

    return reached


def _plan(base: ServiceRoomEnv, reached: Callable[[int, int, int], bool]) -> list[int] | None:
    """Shortest action list to a (x, y, direction) state satisfying ``reached``, or None."""
    start = (*base.agent_pos, base.agent_dir)
    queue = deque([(start, [])])
    seen = {start}
    while queue:
        (x, y, direction), actions = queue.popleft()
        if reached(x, y, direction):
            return actions
        if (x, y) == EXIT_POS:  # stepping onto the exit ends the episode, so no path goes through
            continue
        dx, dy = DIRECTIONS[direction]
        moves = [
            ((x, y, (direction - 1) % 4), Actions.left),
            ((x, y, (direction + 1) % 4), Actions.right),
        ]
        ahead = base.grid.get(x + dx, y + dy)
        if ahead is None or ahead.type == "goal":
            moves.append(((x + dx, y + dy, direction), Actions.forward))
        for state, action in moves:
            if state not in seen:
                seen.add(state)
                queue.append((state, [*actions, action]))
    return None
