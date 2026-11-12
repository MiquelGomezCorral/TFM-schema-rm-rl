"""Count the distinct start layouts a PPO run trains on, over its first training resets.

Builds the training vector env exactly as ``train_ppo`` does for a suite's ``run-config.yaml``, plays
random actions, and fingerprints every layout (grid, agent position and direction) right after
each training reset: the initial ``ppo_num_envs`` resets, then every autoreset.

Usage (from the repo root):
    PYTHONPATH=app python experiments/benchmark/tuning/ppo/reset_check.py <run-config.yaml> \
        [--seeds 1 11 21] [--resets 32]

Prints the distinct layouts of each run seed and the layouts each pair of seeds shares. Training
env ``i`` of a run resets on seed ``run seed + i`` and then draws its own layouts, so run seeds
closer than ``ppo_num_envs`` share envs and layouts.
"""

import argparse
import hashlib
from contextlib import ExitStack
from functools import partial
from itertools import combinations
from pathlib import Path

from gymnasium.vector import AutoresetMode, SyncVectorEnv

from src.arm_fm.ppo import _open_run, _training_env
from src.config import Configuration


def fingerprint(env) -> str:
    """Hash of the MiniGrid layout an env currently holds."""
    base = env.unwrapped
    state = base.grid.encode().tobytes() + bytes(f"{base.agent_pos}{base.agent_dir}", "ascii")
    return hashlib.sha256(state).hexdigest()[:12]


def training_layouts(config_path: Path, seed: int, resets: int) -> list[str]:
    """The fingerprints of the first ``resets`` training resets of a run with this config."""
    CONFIG = Configuration(yaml_config_name=str(config_path), seed=seed)
    with ExitStack() as cleanup:
        runs = [_open_run(CONFIG, cleanup) for _ in range(CONFIG.ppo_num_envs)]
        envs = SyncVectorEnv(
            [partial(_training_env, CONFIG, run) for run in runs],
            autoreset_mode=AutoresetMode.SAME_STEP,
        )
        envs.reset(seed=CONFIG.seed)
        layouts = [fingerprint(env) for env in envs.envs]
        envs.action_space.seed(seed)
        while len(layouts) < resets:
            _, _, terminated, truncated, _ = envs.step(envs.action_space.sample())
            layouts += [fingerprint(envs.envs[i]) for i in (terminated | truncated).nonzero()[0]]
    return layouts[:resets]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Count distinct training layouts of a run config.")
    parser.add_argument("config", type=Path)
    parser.add_argument("--seeds", type=int, nargs="+", default=[1])
    parser.add_argument("--resets", type=int, default=32)
    arguments = parser.parse_args()
    found = {
        seed: training_layouts(arguments.config, seed, arguments.resets) for seed in arguments.seeds
    }
    for seed, layouts in found.items():
        print(
            f"seed {seed}: {len(set(layouts))} distinct layouts over {len(layouts)} training resets"
        )
    for first, second in combinations(found, 2):
        shared = len(set(found[first]) & set(found[second]))
        print(f"seeds {first} and {second}: {shared} shared layouts")
