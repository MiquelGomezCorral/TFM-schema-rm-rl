"""Test finished ``train-rl`` runs on unseen maps and render captioned GIFs.

Usage:
    python app/main.py test-rl --run w3-kc-compiler-s6r3 --episodes 100 --gifs 5

``--run`` is a run folder or an experiment name: a name tests every finished run (one with a
``summary.json``) under ``outputs/runs/<exp_name>/``. Each run is rebuilt from its saved
``config.yaml`` and final model, never retrained, and gets ``test.json`` plus, with ``--gifs``,
``gifs/<i>.gif``. Episode ``i`` resets with seed ``--seed-base + i``; training uses the run seed
and validation ``eval_seed_base``, so these maps are unseen. A fixed-layout run has one layout,
so it is tested on its layout seed instead, and ``test.json`` says so.

With ``--judge card.json`` the test episodes are also saved as agent trace records
(``agent-traces/ep<k>.json``, reference labels included) and judged on the card's clauses into
``judge.json``. The card is checked first (its env, its propositions), before any test work. An
RM run's episode ends when the machine stops; the record then has ``rm_stopped`` set and keeps
the env's own ``terminated`` and ``truncated``. A run without ``judge.json`` is "not evaluated"
by the judge.
"""

import json
import random
import textwrap
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, fields
from pathlib import Path
from statistics import fmean
from typing import Any

import gymnasium as gym
import torch
import yaml
from PIL import Image, ImageDraw, ImageFont

from src.arm_fm import make_run_environment
from src.arm_fm.artifacts import load_bundle
from src.arm_fm.dqn import (
    QNetwork,
    evaluation_resets,
    run_method,
    select_action,
)
from src.arm_fm.dqn import evaluate as evaluate_dqn
from src.arm_fm.environments import RewardMachineObservation, RunEnvironment, make_environment
from src.arm_fm.ppo import evaluate as evaluate_ppo
from src.arm_fm.ppo import evaluation_resets as evaluation_resets_ppo
from src.arm_fm.ppo import fixed_layout, load_ppo_agent
from src.arm_fm.runtime import RewardMachineRuntime
from src.benchmark import (
    RM_RETURN_DEFINITION,
    START_SHARE_STRICT,
    CardError,
    NoReferenceLabelerError,
    Rollout,
    card_header,
    episode_cannot_start,
    expected_length,
    judge_trace,
    labeler_for,
    length_header,
    load_card,
    machine_header,
    make_record,
    write_json,
)
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
# The per-episode judge fields ``judge.json`` averages.
JUDGE_MEANS = (
    "raw_judged_success",
    "judged_success",
    "non_empty_success",
    "cannot_start",
    "cannot_start_5pct",
    "env_success",
    "hard_breaks",
    "soft_breaks",
    "hard_open",
    "soft_open",
    "env_return",
    "env_return_positive",
    "env_return_negative",
    "rm_return",
    "rm_return_positive",
    "rm_return_negative",
    "length",
)
CANNOT_START_DEFINITION = (
    "cannot_start: the machine ended the episode in a final state, the environment did not, and "
    "the episode lasted at most max(1, ceil(0.10 * expected_length)) steps; such an episode is "
    "judged failed. raw_judged_success is the judge's value before that rule; mean_cannot_start "
    "is the share of episodes affected (mean_cannot_start_5pct: the 5% threshold, not applied)."
)
RETURN_SPLIT_DEFINITION = (
    "<env|rm>_return_positive and _negative sum the positive and the negative step rewards of an "
    "episode (the negative part is <= 0); their sum is <env|rm>_return. rm_* is null without an RM."
)
# A long episode keeps its first steps, a thinning sample of the middle, and its last steps.
HEAD_FRAMES, MIDDLE_FRAMES, TAIL_FRAMES = 40, 14, 6


# ======================================================================================
#                                      PUBLIC API
# ======================================================================================


def test_rl(CONFIG: Configuration, gifs: int, judge: Path | None = None) -> None:
    """Test the runs named by ``CONFIG.exp_name`` and write each run's ``test.json``.

    ``CONFIG.final_eval_episodes`` is the number of test episodes and ``CONFIG.eval_seed_base``
    the first test seed. ``gifs`` is how many of those episodes are also rendered as GIFs. With
    ``judge`` (a card file) the episodes are also saved as agent traces and judged.

    Raises:
        ValueError: If no finished run matches ``CONFIG.exp_name``.
        SystemExit: If ``judge`` is not one card that fits the run's env and labels; the check
            runs before any test work, so nothing is written.
    """
    for directory in _run_directories(CONFIG):
        try:
            row = _test_run(CONFIG, directory, gifs, judge)
        except (CardError, NoReferenceLabelerError) as error:
            raise SystemExit(f"error: {error}") from error
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

    ``evaluate(count)`` is the learner's own evaluation row and ``resets(count)`` the ``reset``
    arguments of its test episodes. ``new_act()`` starts a fresh action stream, seeded with the
    run seed as the learner's evaluation seeds its own, and returns ``act(observation)``, one
    action as evaluation picks it. Each recorder takes its own stream, so one cannot change the
    other's actions.
    """

    evaluate: Callable[[int], dict[str, object]]
    resets: Callable[[int], list[dict[str, object]]]
    new_act: Callable[[], Callable[[Any], int]]


def _test_run(
    CONFIG: Configuration, directory: Path, gifs: int, judge: Path | None
) -> dict[str, object]:
    saved = yaml.safe_load((directory / "config.yaml").read_text(encoding="utf-8"))
    config = _run_config(saved, CONFIG.eval_seed_base)
    run = make_run_environment(config)
    try:
        policy = _load_policy(config, run, directory)
        # Built first: a card that does not fit the run fails before any test work.
        judge_recorder = JudgeRecorder(config, run, policy, judge) if judge is not None else None
        row = policy.evaluate(CONFIG.final_eval_episodes)
        recorder = GifRecorder(config, run, policy, run_method(saved))
        # A fixed layout evaluates fewer episodes than asked: GIFs replay evaluated ones only.
        records = recorder.write(directory, min(gifs, row["episodes"]))
        if judge_recorder is not None:
            judge_recorder.write(directory, CONFIG.final_eval_episodes)
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
    fixed = fixed_layout(config) if config.algorithm == "ppo" else config.layout == "fixed"
    if fixed:
        test["settings"]["note"] = FIXED_LAYOUT_NOTES[config.algorithm]
    (directory / "test.json").write_text(json.dumps(test, indent=2) + "\n", encoding="utf-8")
    return row


def _run_config(saved: dict[str, Any], seed_base: int) -> Configuration:
    """The run's own settings, rebuilt from its ``config.yaml``, testing from ``seed_base``."""
    if "use_rm" in saved:
        raise ValueError("This run predates reward_source (its config.yaml has use_rm); retrain it")
    names = {item.name for item in fields(Configuration)}
    settings = {key: value for key, value in saved.items() if key in names}
    config = Configuration(**{**settings, "yaml_config_name": None})
    config.eval_seed_base = seed_base
    return config


def _load_policy(config: Configuration, run: RunEnvironment, directory: Path) -> Policy:
    if config.algorithm == "ppo":
        agent = load_ppo_agent(directory / "agent.pt", run, CPU)

        def new_ppo_act() -> Callable[[Any], int]:
            generator = torch.Generator().manual_seed(config.seed)
            return lambda observation: agent.act(
                observation, generator, deterministic=config.eval_greedy
            )

        return Policy(
            evaluate=lambda count: evaluate_ppo(config, run, agent, count),
            resets=lambda count: evaluation_resets_ppo(config, run, count),
            new_act=new_ppo_act,
        )

    q_network = QNetwork(run.make_encoder(), run.env.observation_space, int(run.env.action_space.n))
    q_network.load_state_dict(torch.load(directory / "q_network.pt", map_location=CPU))

    def new_dqn_act() -> Callable[[Any], int]:
        rng = random.Random(config.seed)
        return lambda observation: select_action(
            q_network, observation, config.eval_epsilon, run.env.action_space, rng
        )

    return Policy(
        evaluate=lambda count: evaluate_dqn(config, run, q_network, count),
        resets=lambda count: evaluation_resets(config, run, count),
        new_act=new_dqn_act,
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
        self.act = policy.new_act()

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
            observation, reward, terminated, truncated, info = env.step(self.act(observation))
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


# ======================================================================================
#                                        JUDGE
# ======================================================================================


@dataclass(frozen=True)
class Played:
    """A judged test episode: its rollout and RM rewards, whether the machine ended it in a final
    state, and the labeling's valuation at reset (None without an RM)."""

    rollout: Rollout
    rm_rewards: list[float]
    machine_final: bool
    start_labels: dict[str, bool] | None


class JudgeRecorder:
    """Replay a run's test episodes, save each as an agent trace record and judge it on a card.

    An episode is the test episode as the run plays it: with an RM it ends when the machine
    stops. The record keeps the env's own flags and sets ``rm_stopped`` for a machine stop.

    Raises:
        CardError: If the card is unreadable or breaks the card contract, is for another env or
            other env kwargs than the run, judges a proposition the reference labeler does not
            emit (the judge would read it as always false), or the run sets ``task_bundles``.
        NoReferenceLabelerError: If the card's env has no reference labeler.
    """

    def __init__(
        self, config: Configuration, run: RunEnvironment, policy: Policy, card_path: Path
    ) -> None:
        self.config = config
        self.run = run
        self.policy = policy
        self.suite, self.card = load_card(card_path)
        self.machine = load_bundle(config.bundle).reward_machine if config.bundle else None
        self.expected = expected_length(self.card)
        if config.task_bundles:
            raise CardError(
                f"{card_path}: the judge does not take a task_bundles run: one card judges one task"
            )
        gym_id = self.card.env.get("gym_id")
        if gym_id != config.gym_id:
            raise CardError(
                f"{card_path}: the card is for {gym_id!r}, the run plays {config.gym_id!r}"
            )
        card_kwargs = self.card.env.get("env_kwargs") or {}
        if card_kwargs != config.env_kwargs:  # layout seeds are not compared: tests use their own
            raise CardError(
                f"{card_path}: the card's env_kwargs {card_kwargs} differ from the run's "
                f"{config.env_kwargs}"
            )
        # A throwaway env: resetting the run's env here would shift the draws of its evaluation.
        probe = make_environment(gym_id, **card_kwargs)
        try:
            probe.reset(seed=config.eval_seed_base)
            self.labeler = labeler_for(gym_id, probe)
            emitted = set(self.labeler.labels(probe.unwrapped))
        finally:
            probe.close()
        unknown = {name for clause in self.card.expect for name in clause[1]} - emitted
        if unknown:
            raise CardError(f"{card_path}: the reference labeler emits no {sorted(unknown)}")

    def write(self, directory: Path, count: int) -> None:
        """Save the episodes to ``<directory>/agent-traces/ep<k>.json``, verdicts to ``judge.json``."""
        episodes, start_labels = [], {}
        act = self.policy.new_act()
        # Epsilon-random actions draw from the action space, which evaluation leaves unseeded.
        self.run.env.action_space.seed(self.config.seed)
        for index, reset in enumerate(self.policy.resets(count)[:count]):
            played = self._rollout(act, reset)
            rollout, rm_rewards = played.rollout, played.rm_rewards
            if played.start_labels is not None:
                start_labels[rollout.reset_seed] = played.start_labels
            record = make_record(self.suite, self.card, "agent", "agent", rollout)
            name = f"agent-traces/ep{index}.json"
            write_json(directory / name, record.to_dict())
            verdict = judge_trace(self.card.expect, rollout.labels).to_dict()
            # The machine ended the episode in a final state before the agent could act on the
            # task: the clauses are not tested, so the episode fails whatever they say.
            length = len(rollout.actions)
            ended = rollout.rm_stopped and played.machine_final
            expected = self.expected
            cannot_start = episode_cannot_start(length, ended, expected)
            raw_success, raw_non_empty = verdict.pop("success"), verdict.pop("non_empty_success")
            episodes.append(
                {
                    "file": name,
                    "reset_seed": rollout.reset_seed,
                    "raw_judged_success": raw_success,
                    "judged_success": raw_success and not cannot_start,
                    "non_empty_success": raw_non_empty and not cannot_start,
                    "cannot_start": cannot_start,
                    "cannot_start_5pct": episode_cannot_start(
                        length, ended, expected, START_SHARE_STRICT
                    ),
                    **verdict,
                    "env_success": record.env_success,
                    **_return_split("env", rollout.env_rewards),
                    **_return_split("rm", rm_rewards),
                    "length": len(rollout.actions),
                }
            )
        summary = {
            **card_header(self.card),
            "suite": self.suite,
            "rm_bundle": str(self.config.bundle) if self.config.bundle else None,
            "episodes": len(episodes),
            "rm_return_definition": RM_RETURN_DEFINITION,
            "return_split_definition": RETURN_SPLIT_DEFINITION,
            "cannot_start_definition": CANNOT_START_DEFINITION,
            **length_header(self.expected),
            **machine_header(self.machine, start_labels or None),
            **judge_means(episodes),
            "activated_share": activated_share(episodes),
            "per_episode": episodes,
        }
        write_json(directory / "judge.json", summary, indent=2)

    def _rollout(self, act: Callable[[Any], int], reset: dict[str, object]) -> Played:
        """One test episode: the reference labels after every step, the RM rewards, whether the
        machine ended in a final state (``rm_accept`` of the last step), and the labeling's
        valuation at reset (None without an RM)."""
        env = self.run.env
        base = env.unwrapped
        self.labeler.reset()
        observation, reset_info = env.reset(**reset)
        # An env that draws its own episode seed (the service room) reports it as ``event_seed``.
        rollout = Rollout(reset_seed=int((reset_info or {}).get("event_seed", reset["seed"])))
        start_labels = _start_labels(env)
        rm_rewards, done, machine_final = [], False, False
        while not done:
            action = act(observation)
            observation, reward, terminated, truncated, info = env.step(action)
            machine_final = bool(info.get("rm_accept"))
            env_reward = float(info.get("env_reward", reward))
            rollout.actions.append(int(action))
            rollout.labels.append(self.labeler.labels(base))
            rollout.env_rewards.append(env_reward)
            if "rm_reward" in info:
                rm_rewards.append(float(info["rm_reward"]))
            # The RM wrapper folds the machine's stop into ``terminated`` and reports the env's own
            # flag as ``env_terminated``; without a wrapper the two are the same.
            rollout.terminated = bool(info.get("env_terminated", terminated))
            rollout.truncated = bool(truncated)
            rollout.rm_stopped = bool(terminated) and not rollout.terminated
            done = bool(terminated) or bool(truncated)
        return Played(rollout, rm_rewards, machine_final, start_labels)


def _start_labels(env: gym.Env) -> dict[str, bool] | None:
    """The RM labeling's valuation of the just-reset env, read on a fresh runtime so the live
    episode's labeling memory is untouched; None when the env has no RM wrapper."""
    while env is not None and not isinstance(env, RewardMachineObservation):
        env = getattr(env, "env", None)
    if env is None:
        return None
    adapter = env.reward_machine
    runtime = RewardMachineRuntime(adapter.runtime.machine)
    return runtime.evaluate_labeling(adapter.environment, adapter.labeling)


def _return_split(prefix: str, rewards: list[float]) -> dict[str, float | None]:
    """``<prefix>_return`` and its positive and negative parts; null without rewards (no RM)."""
    if not rewards:
        return dict.fromkeys(
            (f"{prefix}_return", f"{prefix}_return_positive", f"{prefix}_return_negative")
        )
    return {
        f"{prefix}_return": sum(rewards),
        f"{prefix}_return_positive": sum(reward for reward in rewards if reward > 0),
        f"{prefix}_return_negative": sum(reward for reward in rewards if reward < 0),
    }


def activated_share(episodes: list[dict[str, Any]]) -> list[float | None]:
    """Per clause, the share of episodes that activated it; null for a clause with no trigger."""
    return [
        None if None in flags else fmean(flags)
        for flags in zip(*(episode["activated"] for episode in episodes), strict=True)
    ]


def judge_means(episodes: list[dict[str, Any]]) -> dict[str, float | None]:
    """The ``mean_<name>`` entries of ``judge.json``, one per ``JUDGE_MEANS`` name."""
    return {f"mean_{name}": _mean(episodes, name) for name in JUDGE_MEANS}


def _mean(episodes: list[dict[str, Any]], name: str) -> float | None:
    """The mean of ``name`` over the episodes that have it (``rm_return`` is null without an RM)."""
    values = [float(episode[name]) for episode in episodes if episode[name] is not None]
    return fmean(values) if values else None


def _status(step: int, info: dict[str, Any]) -> str:
    return f"step {step}" + (f"  rm {info['rm_state']}" if "rm_state" in info else "")
