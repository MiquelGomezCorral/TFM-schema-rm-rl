"""Count the distinct start layouts a PPO run trains on, and how many its seeds or evaluation share.

Builds the training vector env exactly as ``train_ppo`` does for a run config, plays random
actions, and fingerprints every layout (grid, agent position and direction) right after each
training reset: the initial ``ppo_num_envs`` resets, then every autoreset. Also fingerprints the
evaluation layouts (``eval_seed_base + i`` for the ``final_eval_episodes`` episodes).

Usage (from the repo root):
    PYTHONPATH=app python experiments/benchmark/tuning/ppo-diagnostic/reset_check.py \
        experiments/benchmark/tuning/ppo-diagnostic/reset-check-config.yaml \
        [--seeds 1 2 3 4 21] [--resets 200] [--old-seeds]

Prints the distinct layouts of each run seed, the layouts each pair of seeds shares and the
layouts each seed shares with evaluation. ``--old-seeds`` resets training env ``i`` on
``run seed + i`` (the rule before the fix: run seeds closer than ``ppo_num_envs`` share
layouts); without it the check uses ``training_reset_seeds`` of ``train_ppo``.
"""

import argparse
import hashlib
from contextlib import ExitStack
from functools import partial
from itertools import combinations
from pathlib import Path

from gymnasium.vector import AutoresetMode, SyncVectorEnv

from src.arm_fm.ppo import _open_run, _training_env, training_reset_seeds
from src.config import Configuration


def fingerprint(env) -> str:
    """Hash of the MiniGrid layout an env currently holds."""
    base = env.unwrapped
    state = base.grid.encode().tobytes() + bytes(f"{base.agent_pos}{base.agent_dir}", "ascii")
    return hashlib.sha256(state).hexdigest()[:12]


def training_layouts(config_path: Path, seed: int, resets: int, old_seeds: bool) -> list[str]:
    """The fingerprints of the first ``resets`` training resets of a run with this config."""
    CONFIG = Configuration(yaml_config_name=str(config_path), seed=seed)
    first_seeds = (
        [seed + index for index in range(CONFIG.ppo_num_envs)]
        if old_seeds
        else training_reset_seeds(CONFIG)
    )
    with ExitStack() as cleanup:
        runs = [_open_run(CONFIG, cleanup) for _ in range(CONFIG.ppo_num_envs)]
        envs = SyncVectorEnv(
            [partial(_training_env, CONFIG, run) for run in runs],
            autoreset_mode=AutoresetMode.SAME_STEP,
        )
        envs.reset(seed=first_seeds)
        layouts = [fingerprint(env) for env in envs.envs]
        envs.action_space.seed(seed)
        while len(layouts) < resets:
            _, _, terminated, truncated, _ = envs.step(envs.action_space.sample())
            layouts += [fingerprint(envs.envs[i]) for i in (terminated | truncated).nonzero()[0]]
    return layouts[:resets]


def evaluation_layouts(config_path: Path) -> set[str]:
    """The fingerprints of the final evaluation's layouts (``eval_seed_base + i``)."""
    CONFIG = Configuration(yaml_config_name=str(config_path))
    layouts = set()
    with ExitStack() as cleanup:
        env = _open_run(CONFIG, cleanup).env
        for index in range(CONFIG.final_eval_episodes):
            env.reset(seed=CONFIG.eval_seed_base + index)
            layouts.add(fingerprint(env))
    return layouts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Count distinct training layouts of a run config.")
    parser.add_argument("config", type=Path)
    parser.add_argument("--seeds", type=int, nargs="+", default=[1])
    parser.add_argument("--resets", type=int, default=200)
    parser.add_argument("--old-seeds", action="store_true", help="reset env i on run seed + i")
    arguments = parser.parse_args()
    found = {
        seed: training_layouts(arguments.config, seed, arguments.resets, arguments.old_seeds)
        for seed in arguments.seeds
    }
    evaluation = evaluation_layouts(arguments.config)
    rule = "seed + i (old)" if arguments.old_seeds else "seed * ppo_num_envs + i (fix)"
    print(f"training env seeds: {rule}; {len(evaluation)} distinct evaluation layouts")
    for seed, layouts in found.items():
        print(
            f"seed {seed}: {len(set(layouts))} distinct layouts over {len(layouts)} training "
            f"resets, {len(set(layouts) & evaluation)} shared with evaluation"
        )
    for first, second in combinations(found, 2):
        shared = len(set(found[first]) & set(found[second]))
        print(f"seeds {first} and {second}: {shared} shared layouts")
