"""Forced starts: two MiniGrid levels that begin with the trigger of a rule already true.

A conditional rule such as ``Response(blocker_moved, has_door_key)`` passes untested when its
trigger never happens, so an agent that does nothing passes it. These levels are the original
ones with a different start, so doing nothing fails the rule instead:

- ``MiniGrid-BlockedUnlockPickup-Cleared-v0``: the ball starts off the cell in front of the door,
  so ``blocker_moved`` is true at the first step. Hands empty, key reachable, door locked.
- ``MiniGrid-UnlockPickup-KeyHeld-v0``: the agent starts holding the matching key, so
  ``has_door_key`` is true at the first step. ``drop`` does nothing on the first step, so the
  first recorded step always shows the key in hand; later steps are the plain level's.

The plain ids (``MiniGrid-BlockedUnlockPickup-v0``, ``MiniGrid-UnlockPickup-v0``) are not
touched: every existing card and run builds the same env as before. Facts and labeling API:
``experiments/benchmark/envs/minigrid-blocked-unlock-pickup-cleared/`` and
``experiments/benchmark/envs/minigrid-unlock-pickup-key-held/``.

Import nothing from ``src.arm_fm``: ``environments.py`` imports this module to register the ids.
"""

import numpy as np
from gymnasium.envs.registration import register
from minigrid.core.actions import Actions
from minigrid.envs import BlockedUnlockPickupEnv, UnlockPickupEnv

CLEARED_ID = "MiniGrid-BlockedUnlockPickup-Cleared-v0"
KEY_HELD_ID = "MiniGrid-UnlockPickup-KeyHeld-v0"


def _cell_of_type(env, kind: str) -> tuple[int, int]:
    """The first grid cell holding an object of ``kind`` (each level has one door and one key)."""
    for x in range(env.width):
        for y in range(env.height):
            item = env.grid.get(x, y)
            if item is not None and item.type == kind:
                return x, y
    raise ValueError(f"no {kind} in the grid")


# ======================================================================================
#                                BLOCKED UNLOCK PICKUP, CLEARED
# ======================================================================================
class BlockedUnlockPickupClearedEnv(BlockedUnlockPickupEnv):
    """BlockedUnlockPickup with the ball already away from the door.

    The ball moves to a free floor cell of the start room, drawn uniformly from the reset seed
    after every draw of the plain level, so the same seed gives the plain level's door, key, box
    and agent. The cell in front of the door and its neighbours are excluded (the ball is at
    least 2 steps from that cell), so the door stays easy to approach; the agent's and the key's
    cells are taken. One extra obstacle cannot wall off any cell of the 4 x 4 floor, so the key
    and the door stay reachable without touching the ball.
    """

    def _gen_grid(self, width: int, height: int) -> None:
        super()._gen_grid(width, height)
        door_x, door_y = _cell_of_type(self, "door")
        in_front = (door_x - 1, door_y)
        ball = self.grid.get(*in_front)
        self.grid.set(*in_front, None)
        self.place_obj(
            ball,
            top=(0, 0),
            size=(door_x, height),
            reject_fn=lambda _env, pos: abs(pos[0] - in_front[0]) + abs(pos[1] - in_front[1]) < 2,
        )


# ======================================================================================
#                                  UNLOCK PICKUP, KEY HELD
# ======================================================================================
class UnlockPickupKeyHeldEnv(UnlockPickupEnv):
    """UnlockPickup with the agent already holding the key that matches the door.

    The key leaves the floor at reset and goes into the hands; the rest of the layout is the plain
    level's for the same seed. ``drop`` becomes ``done`` on the first step so the first recorded
    step cannot lose the key; from the second step every action is the plain level's.
    """

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        _, info = super().reset(seed=seed, options=options)
        x, y = _cell_of_type(self, "key")
        self.carrying = self.grid.get(x, y)
        self.carrying.cur_pos = np.array([-1, -1])
        self.grid.set(x, y, None)
        return self.gen_obs(), info

    def step(self, action):
        if action == Actions.drop and self.step_count == 0:
            action = Actions.done  # no losing the key before the first labels are read
        return super().step(action)


register(id=CLEARED_ID, entry_point=BlockedUnlockPickupClearedEnv)
register(id=KEY_HELD_ID, entry_point=UnlockPickupKeyHeldEnv)
