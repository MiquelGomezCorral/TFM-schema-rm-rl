"""Reset-state check: how many distinct layouts do 32 training resets give, and are the eval layouts fixed?

Run from the worktree root:  PYTHONPATH=app python <this file> <run-config.yaml>
Takes a run's own run-config.yaml (card, bundle, machine), sets the layout to `fixed` (layout seed 1) and
to `procedural` (layout_seed null), and drives 8 training environments through dqn.py's own reset seeds
(`_training_reset_seeds`, as `_train` does): 4 resets each = 32 training resets. A layout is the encoded
grid plus the agent's position and direction. It also counts the layouts that pairs of run seeds (1/2, 1/11, 1/21, 11/21) share in their first 32 resets.
Then it lists the evaluation resets (`evaluation_resets`)
for run seeds 1, 2 and 3 and checks they are the same layouts.
"""

import hashlib
import sys

from src.arm_fm import make_run_environment
from src.arm_fm.dqn import _training_reset_seeds, evaluation_resets
from src.config import Configuration

ENVS = 8
RESETS_PER_ENV = 4


def layout_id(env) -> str:
    base = env.unwrapped
    grid = base.grid.encode().tobytes() + bytes([*base.agent_pos, base.agent_dir])
    return hashlib.sha1(grid, usedforsecurity=False).hexdigest()[:10]


def make(config_file: str, layout: str, seed: int) -> Configuration:
    CONFIG = Configuration(yaml_config_name=config_file, seed=seed)
    CONFIG.layout = layout
    CONFIG.layout_seed = 1 if layout == "fixed" else None
    CONFIG.dqn_num_envs = ENVS
    return CONFIG


def training_layouts(config_file: str, layout: str, seed: int = 1) -> list[str]:
    CONFIG = make(config_file, layout, seed)
    envs = [make_run_environment(CONFIG).env for _ in range(ENVS)]
    seeds = [_training_reset_seeds(CONFIG, index) for index in range(ENVS)]
    found = []
    for _ in range(RESETS_PER_ENV):
        for env, env_seeds in zip(envs, seeds, strict=True):
            env.reset(seed=next(env_seeds))
            found.append(layout_id(env))
    return found


def eval_layouts(config_file: str, layout: str, seed: int) -> list[str]:
    CONFIG = make(config_file, layout, seed)
    run = make_run_environment(CONFIG)
    found = []
    for reset in evaluation_resets(CONFIG, run, CONFIG.eval_episodes):
        run.env.reset(**reset)
        found.append(layout_id(run.env))
    return found


def main(config_file: str) -> None:
    for layout in ("fixed", "procedural"):
        found = training_layouts(config_file, layout)
        print(f"{layout}: {len(found)} training resets -> {len(set(found))} distinct layouts")
        evals = [eval_layouts(config_file, layout, seed) for seed in (1, 2, 3)]
        same = all(layouts == evals[0] for layouts in evals)
        print(
            f"{layout}: eval episodes {len(evals[0])}, distinct eval layouts {len(set(evals[0]))}, "
            f"same for run seeds 1, 2, 3: {same}"
        )
        train_eval_overlap = len(set(found) & set(evals[0]))
        print(
            f"{layout}: layouts shared by the 32 training resets and the eval set: {train_eval_overlap}"
        )
    # 8 envs seed sub-env i with run seed + i (dqn.py `_training_reset_seeds`): neighbouring run seeds overlap.
    sets = {seed: set(training_layouts(config_file, "procedural", seed)) for seed in (1, 2, 11, 21)}
    for first, second in ((1, 2), (1, 11), (1, 21), (11, 21)):
        print(
            f"procedural: run seeds {first} and {second} share {len(sets[first] & sets[second])} of "
            f"{len(sets[first])} distinct layouts in their first 32 training resets"
        )


if __name__ == "__main__":
    main(sys.argv[1])
