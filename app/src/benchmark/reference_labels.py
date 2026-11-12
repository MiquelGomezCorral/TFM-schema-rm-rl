"""Reference labelers: the truth of every proposition, computed straight from the environment.

They are the yardstick of the judge and belong to neither pipeline. The four MiniGrid labelers
follow the truth conditions in each env's ``environment-code.md`` (``examples/arm-fm/
minigrid-*/``). Any other env, such as the event room, supplies ``reference_labels(env)`` beside
its own class and is found through that class's module.

A labeler exposes ``reset()`` (forget the episode) and ``labels(env)`` (the labels after the
step just taken). The four MiniGrid labelers remember the previous labels, so event propositions
such as ``key_lost`` and latched ones such as ``key_found`` work. A ``reference_labels(env)``
function sees only the env: it must compute every proposition from the env state alone.
"""

import inspect
from collections.abc import Callable, Iterator
from typing import Any


class NoReferenceLabelerError(LookupError):
    """No reference labeler exists for an environment."""


class ReferenceLabeler:
    """Base labeler: subclasses fill ``compute`` and may extend ``reset``."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.previous: dict[str, bool] = {}

    def labels(self, env: Any) -> dict[str, bool]:
        """The labels of the live (unwrapped) env, remembered as the previous step's."""
        values = {name: bool(value) for name, value in self.compute(env).items()}  # not numpy
        self.previous = values
        return values

    def compute(self, env: Any) -> dict[str, bool]:
        raise NotImplementedError


class FunctionLabeler(ReferenceLabeler):
    """Wrap a stateless ``reference_labels(env)`` function of an env module."""

    def __init__(self, function: Callable[[Any], dict[str, bool]]) -> None:
        super().__init__()
        self.function = function

    def compute(self, env: Any) -> dict[str, bool]:
        return self.function(env)


# ======================================================================================
#                                   GRID READING HELPERS
# ======================================================================================


def _cells(env: Any) -> Iterator[tuple[int, int, Any]]:
    """Every non-empty grid cell as ``(x, y, object)``."""
    for x in range(env.width):
        for y in range(env.height):
            cell = env.grid.get(x, y)
            if cell is not None:
                yield x, y, cell


def _doors(env: Any) -> list[tuple[int, int, Any]]:
    return [(x, y, cell) for x, y, cell in _cells(env) if cell.type == "door"]


def _carrying(env: Any, kind: str) -> Any | None:
    held = env.carrying
    return held if held is not None and held.type == kind else None


def _at_goal(env: Any) -> bool:
    cell = env.grid.get(*env.agent_pos)
    return cell is not None and cell.type == "goal"


def _mission_target(env: Any, kind: str) -> bool:
    held = _carrying(env, kind)
    return held is not None and env.mission == f"pick up the {held.color} {kind}"


# ======================================================================================
#                                      MINIGRID ENVS
# ======================================================================================


class DoorKey(ReferenceLabeler):
    def compute(self, env: Any) -> dict[str, bool]:
        key = _carrying(env, "key")
        has_key = key is not None and key.color == "yellow"
        door_open = any(door.is_open for _, _, door in _doors(env))
        key_lost = self.previous.get("has_key", False) and not has_key and not door_open
        return {
            "has_key": has_key,
            "door_open": door_open,
            "at_goal": _at_goal(env),
            "key_lost": key_lost,
        }


class UnlockPickup(ReferenceLabeler):
    def compute(self, env: Any) -> dict[str, bool]:
        key = _carrying(env, "key")
        doors = _doors(env)
        has_door_key = key is not None and any(door.color == key.color for _, _, door in doors)
        door_open = any(door.is_open for _, _, door in doors)
        key_lost = self.previous.get("has_door_key", False) and not has_door_key and not door_open
        return {
            "has_door_key": has_door_key,
            "door_open": door_open,
            "target_picked_up": _mission_target(env, "box"),
            "key_lost": key_lost,
        }


class BlockedUnlockPickup(UnlockPickup):
    def compute(self, env: Any) -> dict[str, bool]:
        values = super().compute(env)
        # The ball starts on the cell in front of the door; a ball in hand is off the grid.
        door_x, door_y, _ = _doors(env)[0]
        blocker = env.grid.get(door_x - 1, door_y)
        values["blocker_moved"] = not (blocker is not None and blocker.type == "ball")
        return values


class KeyCorridor(ReferenceLabeler):
    """KeyCorridorS6R3: unlocking clears ``is_locked``, so the locked door is noted once."""

    def reset(self) -> None:
        super().reset()
        self.locked_door: tuple[int, int, str] | None = None

    def compute(self, env: Any) -> dict[str, bool]:
        # The first labels come after step 1, and no step can unlock a door before the key is held.
        if self.locked_door is None:
            self.locked_door = next(
                ((x, y, door.color) for x, y, door in _doors(env) if door.is_locked), None
            )
        door_x, door_y, color = self.locked_door or (None, None, None)
        key = _carrying(env, "key")
        agent_x, agent_y = env.agent_pos

        # == Seen from the agent's 7x7 view box (MiniGrid's get_view_exts) ==
        box_x = agent_x + (0, -3, -6, -3)[env.agent_dir]
        box_y = agent_y + (-3, 0, -3, -6)[env.agent_dir]
        key_seen = any(
            cell.type == "key" and cell.color == color
            for x, y, cell in _cells(env)
            if box_x <= x <= box_x + 6 and box_y <= y <= box_y + 6
        )

        # == The locked door's room is the 6x6 block to the right of its cell ==
        in_room = (
            door_x is not None
            and door_x <= agent_x <= door_x + 5
            and 5 * (door_y // 5) <= agent_y <= 5 * (door_y // 5) + 5
        )
        door = env.grid.get(door_x, door_y) if door_x is not None else None
        return {
            "key_found": self.previous.get("key_found", False) or key_seen,
            "has_matching_key": key is not None and key.color == color,
            "target_door_open": door is not None and door.is_open,
            "target_room_entered": self.previous.get("target_room_entered", False) or in_room,
            "target_picked_up": _mission_target(env, "ball"),
        }


MINIGRID_LABELERS: dict[str, type[ReferenceLabeler]] = {
    "MiniGrid-DoorKey-": DoorKey,
    "MiniGrid-UnlockPickup-": UnlockPickup,
    "MiniGrid-BlockedUnlockPickup-": BlockedUnlockPickup,
    "MiniGrid-KeyCorridorS6R3-": KeyCorridor,
}


# ======================================================================================
#                                        LOOKUP
# ======================================================================================


def env_module(env: Any) -> Any:
    """The module that defines the env's class (None for a class built without a module)."""
    return inspect.getmodule(type(env.unwrapped))


def labeler_for(gym_id: str, env: Any) -> ReferenceLabeler:
    """The reference labeler of ``gym_id``; ``env`` is the live env, for envs that bring their own.

    Raises:
        NoReferenceLabelerError: If the env is not one of the four MiniGrid envs and its module has
            no ``reference_labels`` (the event room before it is in the codebase, Craftium, ...).
    """
    for prefix, labeler in MINIGRID_LABELERS.items():
        if gym_id.startswith(prefix):
            return labeler()
    function = getattr(env_module(env), "reference_labels", None)
    if function is None:
        raise NoReferenceLabelerError(f"no reference labeler for {gym_id}: not available")
    return FunctionLabeler(function)
