import gymnasium as gym
from minigrid.core.actions import Actions

from src.arm_fm import service_room as room

CARRY = {"siren": False, "box": True, "carry": True, "require": ["holding_box"], "max_steps": 200}


def first_landing(turn: str, seed: int):
    env = gym.make(room.ENV_ID, **CARRY, fall_turn=turn)
    env.reset(seed=seed)
    base = env.unwrapped
    for _ in range(12):
        _, _, _, _, info = env.step(int(Actions.done))
        if "fall" in info["events"]:
            return base._fall_draws, room.cells_of_type(base, "box"), base.step_count
    return None


same = sum(
    first_landing("none", s) == first_landing("half", s) == first_landing("side", s)
    for s in range(1000)
)
coins = [first_landing("half", s)[0][0][1] for s in range(1000)]
print(
    f"same draws, first landing cell and step for none/side/half: {same}/1000; coin 0 share {coins.count(0) / 1000:.1%}"
)
