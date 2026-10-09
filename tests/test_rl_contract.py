import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch
from minigrid.core.constants import DIR_TO_VEC
from minigrid.core.world_object import Key

from src.arm_fm import load_bundle, make_run_environment
from src.arm_fm.dqn import create_replay_buffer, store_transition
from src.config import Configuration

BUNDLE = Configuration.WORKSPACE_PATH / "outputs" / "bundles" / "UnlockPickup-1"


def _first(grid_env, kind):
    return next(cell for cell in grid_env.grid.grid if cell is not None and cell.type == kind)


def _face(grid_env, target):
    """Put the agent on a free cell next to ``target``, facing it."""
    for direction, (dx, dy) in enumerate(DIR_TO_VEC):
        position = (target[0] - dx, target[1] - dy)
        if grid_env.grid.get(*position) is None:
            grid_env.agent_pos, grid_env.agent_dir = position, direction
            return
    raise AssertionError(f"no free cell next to {target}")


@unittest.skipUnless(BUNDLE.is_dir(), "needs the local, gitignored UnlockPickup-1 bundle")
class RewardMachineTransitionContractTest(unittest.TestCase):
    def test_rm_steps_rewards_embeddings_and_replay_dones(self):
        CONFIG = Configuration(gym_id="MiniGrid-UnlockPickup-v0", bundle=BUNDLE, total_timesteps=8)
        run = make_run_environment(CONFIG)
        env, grid_env = run.env, run.env.unwrapped
        phi = {
            state: np.float32(vector) for state, vector in load_bundle(BUNDLE).embeddings.items()
        }
        buffer = create_replay_buffer(CONFIG, env, torch.device("cpu"))
        done_action, pickup_action = int(grid_env.actions.done), int(grid_env.actions.pickup)

        observation, info = env.reset(seed=1)
        np.testing.assert_array_equal(observation["rm_embedding"], phi["u0"])

        # Holding the door's key moves u0 -> u2 without reward or termination.
        door = _first(grid_env, "door")
        grid_env.carrying = Key(door.color)
        key_step = env.step(done_action)
        next_observation, reward, terminated, truncated, info = key_step
        self.assertEqual(info["rm_state"], "u2")
        self.assertEqual((reward, info["env_reward"], info["rm_reward"]), (0.0, 0.0, 0.0))
        self.assertFalse(terminated or truncated)
        np.testing.assert_array_equal(next_observation["rm_embedding"], phi["u2"])

        store_transition(buffer, observation, done_action, key_step)
        sample = buffer.sample(1)
        self.assertEqual(sample.dones.item(), 0.0)
        np.testing.assert_array_equal(sample.next_observations["rm_embedding"][0], phi["u2"])

        # Opening the door pays the RM reward on top of the zero env reward.
        door.is_locked, door.is_open = False, True
        door_observation, reward, _, _, info = env.step(done_action)
        self.assertEqual(info["rm_state"], "u3")
        self.assertEqual((reward, info["env_reward"], info["rm_reward"]), (0.1, 0.0, 0.1))

        # Picking up the box terminates: an exit, the final RM state, and a stored done of 1.
        grid_env.carrying = None
        _face(grid_env, _first(grid_env, "box").cur_pos)
        pickup = env.step(pickup_action)
        _, reward, terminated, _, info = pickup
        self.assertTrue(terminated)
        self.assertTrue(run.is_success(terminated, info["env_reward"]))
        self.assertEqual(
            (info["rm_state"], info["rm_accept"], info["rm_reward"]), ("u4", True, 1.1)
        )
        store_transition(buffer, door_observation, pickup_action, pickup)

        observation, info = env.reset(seed=1)
        self.assertEqual(info["rm_state"], "u0")
        np.testing.assert_array_equal(observation["rm_embedding"], phi["u0"])

        # A step truncated in u2 is stored as not done, and the next reset restores phi(u0).
        grid_env.carrying = Key(_first(grid_env, "door").color)
        grid_env.max_steps = grid_env.step_count + 1
        truncation = env.step(done_action)
        self.assertEqual((truncation[4]["rm_state"], *truncation[2:4]), ("u2", False, True))
        store_transition(buffer, observation, done_action, truncation)
        np.testing.assert_array_equal(buffer.dones[: buffer.pos, 0], [0.0, 1.0, 0.0])

        observation, info = env.reset(seed=1)
        self.assertEqual(info["rm_state"], "u0")
        np.testing.assert_array_equal(observation["rm_embedding"], phi["u0"])


class RunConfigLoaderTest(unittest.TestCase):
    def test_rejects_unknown_keys_and_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.yaml"
            for text, message in (
                (
                    "gym_id: MiniGrid-Empty-5x5-v0\nlearning_rat: 1.0e-4\n",
                    "Unknown keys.*learning_rat",
                ),
                ("gym_id: MiniGrid-Empty-5x5-v0\nseed: 3\n", "must not set seed"),
            ):
                path.write_text(text, encoding="utf-8")
                with self.subTest(text=text), self.assertRaisesRegex(ValueError, message):
                    Configuration(yaml_config_name=str(path))


if __name__ == "__main__":
    unittest.main()
