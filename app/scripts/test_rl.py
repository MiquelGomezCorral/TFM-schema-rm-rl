"""Test finished ``train-rl`` runs on unseen maps and render captioned GIFs.

Usage:
    python app/main.py test-rl --run w3-kc-compiler-s6r3 --episodes 100 --gifs 5

``--run`` is a run folder or an experiment name: a name tests every finished run (one with a
``summary.json``) under ``outputs/runs/<exp_name>/``. Each run is rebuilt from its saved
``config.yaml`` and final model, never retrained, and gets ``test.json`` plus, with ``--gifs``,
``gifs/<i>.gif``. Episode ``i`` resets with seed ``--seed-base + i``; training uses the run seed
and validation ``eval_seed_base``, so these maps are unseen. A fixed-layout run has one layout,
so it is tested on its layout seed instead, and ``test.json`` says so.
"""

import json
import random
import textwrap
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import gymnasium as gym
import torch
import yaml
from PIL import Image, ImageDraw, ImageFont

from src.arm_fm import make_run_environment
from src.arm_fm.dqn import (
    QNetwork,
    evaluation_resets,
    run_method,
    select_action,
)
from src.arm_fm.dqn import evaluate as evaluate_dqn
from src.arm_fm.environments import RunEnvironment
from src.arm_fm.ppo import evaluate as evaluate_ppo
from src.arm_fm.ppo import evaluation_resets as evaluation_resets_ppo
from src.arm_fm.ppo import load_ppo_agent
from src.config import Configuration

CPU = torch.device("cpu")  # training may hold the GPU
FONT = ImageFont.load_default(size=12)
LINE_HEIGHT = 15
MIN_WIDTH = 400
CAPTION_WIDTH = 58
# Why a fixed-layout run is not tested on unseen maps, by learner.
FIXED_LAYOUT_NOTES = {
    "dqn": "fixed layout: tested on the layout seed, not on unseen maps",
    "ppo": "fixed layout: the test seeds do not change the map, so this is not an unseen-map test",
}
FRAME_MS, LAST_FRAME_MS = 180, 2000
# A long episode keeps its first steps, a thinning sample of the middle, and its last steps.
HEAD_FRAMES, MIDDLE_FRAMES, TAIL_FRAMES = 40, 14, 6


# ======================================================================================
#                                      PUBLIC API
# ======================================================================================


def test_rl(CONFIG: Configuration, gifs: int) -> None:
    """Test the runs named by ``CONFIG.exp_name`` and write each run's ``test.json``.

    ``CONFIG.final_eval_episodes`` is the number of test episodes and ``CONFIG.eval_seed_base``
    the first test seed. ``gifs`` is how many of those episodes are also rendered as GIFs.

    Raises:
        ValueError: If no finished run matches ``CONFIG.exp_name``.
    """
    for directory in _run_directories(CONFIG):
        row = _test_run(CONFIG, directory, gifs)
        print(f"{directory.parent.name}/{directory.name}: test exit_rate {row['exit_rate']:.2f}")


def _run_directories(CONFIG: Configuration) -> list[Path]:
    """The run folder ``CONFIG.exp_name`` points at, else the finished runs of that name."""
    given = Path(CONFIG.exp_name)
    if (given / "config.yaml").is_file():
        return [given]
    runs = sorted((CONFIG.OUTPUT_PATH / "runs" / CONFIG.exp_name).glob("*/summary.json"))
    if not runs:
        raise ValueError(f"No finished run in {given} or under outputs/runs/{CONFIG.exp_name}/")
    return [summary.parent for summary in runs]


# ======================================================================================
#                                       ONE RUN
# ======================================================================================


@dataclass(frozen=True)
class Policy:
    """A trained policy and how its learner evaluates it.

    ``evaluate(count)`` is the learner's own evaluation row, ``resets(count)`` the ``reset``
    arguments of its test episodes, and ``act(observation)`` one action as evaluation picks it.
    """

    evaluate: Callable[[int], dict[str, object]]
    resets: Callable[[int], list[dict[str, object]]]
    act: Callable[[Any], int]


def _test_run(CONFIG: Configuration, directory: Path, gifs: int) -> dict[str, object]:
    saved = yaml.safe_load((directory / "config.yaml").read_text(encoding="utf-8"))
    config = _run_config(saved, CONFIG.eval_seed_base)
    run = make_run_environment(config)
    try:
        policy = _load_policy(config, run, directory)
        row = policy.evaluate(CONFIG.final_eval_episodes)
        recorder = GifRecorder(config, run, policy, run_method(saved))
        # A fixed layout evaluates fewer episodes than asked: GIFs replay evaluated ones only.
        records = recorder.write(directory, min(gifs, row["episodes"]))
    finally:
        run.env.close()

    test = {
        "settings": {
            "algorithm": config.algorithm,
            "layout": config.layout,
            "episodes": CONFIG.final_eval_episodes,
            "seed_base": CONFIG.eval_seed_base,
            "eval_epsilon": config.eval_epsilon,
        },
        **row,
        "gifs": records,
    }
    if config.layout == "fixed":
        test["settings"]["note"] = FIXED_LAYOUT_NOTES[config.algorithm]
    (directory / "test.json").write_text(json.dumps(test, indent=2) + "\n", encoding="utf-8")
    return row


def _run_config(saved: dict[str, Any], seed_base: int) -> Configuration:
    """The run's own settings, rebuilt from its ``config.yaml``, testing from ``seed_base``."""
    names = {item.name for item in fields(Configuration)}
    settings = {key: value for key, value in saved.items() if key in names}
    config = Configuration(**{**settings, "yaml_config_name": None})
    config.eval_seed_base = seed_base
    return config


def _load_policy(config: Configuration, run: RunEnvironment, directory: Path) -> Policy:
    if config.algorithm == "ppo":
        agent = load_ppo_agent(directory / "agent.pt", run, CPU)
        generator = torch.Generator().manual_seed(config.seed)
        return Policy(
            evaluate=lambda count: evaluate_ppo(config, run, agent, count),
            resets=lambda count: evaluation_resets_ppo(config, count),
            act=lambda observation: agent.act(observation, generator),
        )

    q_network = QNetwork(run.make_encoder(), run.env.observation_space, int(run.env.action_space.n))
    q_network.load_state_dict(torch.load(directory / "q_network.pt", map_location=CPU))
    rng = random.Random(config.seed)
    return Policy(
        evaluate=lambda count: evaluate_dqn(config, run, q_network, count),
        resets=lambda count: evaluation_resets(config, run, count),
        act=lambda observation: select_action(
            q_network, observation, config.eval_epsilon, run.env.action_space, rng
        ),
    )


# ======================================================================================
#                                         GIFS
# ======================================================================================

# Each family's picture of an env's current state, taken from the task env under the wrappers.
RENDERERS: dict[str, Callable[[gym.Env], Image.Image]] = {
    "minigrid": lambda env: Image.fromarray(env.get_frame(highlight=True, tile_size=24)),
    "craftium": lambda env: Image.fromarray(env.last_observation).convert("RGB"),
}


class FrameSampler:
    """Keep the first and last frames of an episode of unknown length, and a thinning middle."""

    def __init__(self) -> None:
        self.head: dict[int, Image.Image] = {}
        self.middle: dict[int, Image.Image] = {}
        self.tail: deque[tuple[int, Image.Image]] = deque(maxlen=TAIL_FRAMES)
        self.stride = 1

    def add(self, step: int, frame: Image.Image) -> None:
        self.tail.append((step, frame))
        if len(self.head) < HEAD_FRAMES:
            self.head[step] = frame
        elif step % self.stride == 0:
            self.middle[step] = frame
            if len(self.middle) > MIDDLE_FRAMES:
                self.stride *= 2
                self.middle = {s: f for s, f in self.middle.items() if s % self.stride == 0}

    def frames(self) -> list[Image.Image]:
        """The kept frames in step order."""
        kept = {**self.head, **self.middle, **dict(self.tail)}
        return [kept[step] for step in sorted(kept)]


class GifRecorder:
    """Replay a run's test episodes with its policy and save each one as a captioned GIF."""

    def __init__(
        self, config: Configuration, run: RunEnvironment, policy: Policy, method: str
    ) -> None:
        self.config = config
        self.run = run
        self.policy = policy
        self.method = method

    def write(self, directory: Path, count: int) -> list[dict[str, object]]:
        """Save test episodes 0..count-1 to ``<directory>/gifs/<i>.gif`` and describe each one."""
        resets = self.policy.resets(count)[:count]
        if resets:
            (directory / "gifs").mkdir(exist_ok=True)
        records = []
        for index, reset in enumerate(resets):
            name = f"gifs/{index}.gif"
            records.append({"file": name, **self._rollout(reset, directory / name)})
        return records

    def _rollout(self, reset: dict[str, object], path: Path) -> dict[str, object]:
        env = self.run.env
        observation, info = env.reset(**reset)
        task = info.get("task")
        header = self._header(task, reset["seed"])
        sampler = FrameSampler()
        sampler.add(0, self._frame([*header, _status(0, info)]))

        steps, solved, done = 0, False, False
        while not done:
            observation, reward, terminated, truncated, info = env.step(
                self.policy.act(observation)
            )
            steps += 1
            solved = self.run.is_success(terminated, info.get("env_reward", reward))
            done = terminated or truncated
            verdict = ("  SOLVED" if solved else "  failed") if done else ""
            sampler.add(steps, self._frame([*header, _status(steps, info) + verdict]))

        frames = sampler.frames()
        durations = [FRAME_MS] * (len(frames) - 1) + [LAST_FRAME_MS]
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=durations, loop=0)
        return {"seed": reset["seed"], "task": task, "solved": solved, "steps": steps}

    def _header(self, task: str | None, seed: int) -> list[str]:
        """Caption lines: environment, method and task, the map seed, and the mission if any."""
        title = f"{self.config.gym_id} · {self.method}" + (f" · {task}" if task else "")
        mission = getattr(self.run.env.unwrapped, "mission", None)
        mission_lines = textwrap.wrap(f"mission: {mission}", CAPTION_WIDTH) if mission else []
        return [title, f"map seed {seed}", *mission_lines]

    def _frame(self, lines: list[str]) -> Image.Image:
        """The env's current picture under the caption ``lines``."""
        picture = RENDERERS[self.config.env_family](self.run.env.unwrapped)
        height = picture.height + LINE_HEIGHT * len(lines) + 8
        canvas = Image.new("RGB", (max(MIN_WIDTH, picture.width), height), "white")
        canvas.paste(picture, ((canvas.width - picture.width) // 2, canvas.height - picture.height))
        draw = ImageDraw.Draw(canvas)
        for number, text in enumerate(lines):
            draw.text((6, 4 + LINE_HEIGHT * number), text, fill="black", font=FONT)
        return canvas


def _status(step: int, info: dict[str, Any]) -> str:
    return f"step {step}" + (f"  rm {info['rm_state']}" if "rm_state" in info else "")
