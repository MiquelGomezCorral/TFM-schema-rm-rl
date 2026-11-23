"""World stages: one training run whose world changes under the same agent.

``CONFIG.env_stages`` lists the worlds a run plays before its final one, which is the card's own
``env_kwargs`` (evaluation and the judge always play that one). A stage is ``env_kwargs`` (shop
attributes set on every training env at each reset, over the card's values) and ``until`` (when the
run moves on). The machine, policy, optimizer and step count carry on; only the world changes.
Stages only move forward.

``until`` is measured over the last ``episodes`` (default 100) finished training episodes of the
stage, across all envs: ``served`` is the least mean number of served orders per episode, and
``caught`` the least share of food falls whose very next move picked the food up.
"""

import csv
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import gymnasium as gym

from src.config import Configuration

STAGE_LOG = "stages.csv"
STAGE_COLUMNS = ("global_step", "stage", "episodes", "mean_served", "caught_share")
WINDOW_EPISODES = 100


@dataclass(frozen=True)
class EpisodeWorld:
    """What one finished training episode did: its stage, orders served, food falls and catches."""

    stage: int
    served: int
    falls: int
    caught: int


class WorldCurriculum:
    """The stage the training envs play and the rule for moving to the next one.

    The ``WorldStage`` wrappers report finished episodes here and the rollout collector calls
    ``update`` once per vector step. Stage ``len(env_stages)`` is the final world: no overrides.
    """

    def __init__(self, CONFIG: Configuration) -> None:
        self.stages = CONFIG.env_stages
        self.stage = 0
        self.finished: list[EpisodeWorld] = []  # reported since the last update
        self.window = self._new_window()

    @property
    def is_final(self) -> bool:
        return self.stage == len(self.stages)

    @property
    def world(self) -> dict:
        """The ``env_kwargs`` the current stage sets over the card's own; none at the final stage."""
        return {} if self.is_final else self.stages[self.stage]["env_kwargs"]

    def update(self, global_step: int, directory: Path) -> None:
        """Take in the episodes that finished and, if this stage's goal is met, move on and log it."""
        episodes, self.finished = self.finished, []
        if self.is_final:
            return
        # an episode begun under an earlier stage says nothing about this one
        self.window.extend(episode for episode in episodes if episode.stage == self.stage)
        if len(self.window) < self.window.maxlen:
            return

        until = self.stages[self.stage]["until"]
        served = sum(episode.served for episode in self.window) / len(self.window)
        falls = sum(episode.falls for episode in self.window)
        caught = sum(episode.caught for episode in self.window) / falls if falls else None
        if served < until["served"]:
            return
        if "caught" in until and (caught is None or caught < until["caught"]):
            return
        measured = (len(self.window), served, caught)
        self.stage += 1
        self.window = self._new_window()
        self._log(directory, global_step, measured)

    def _new_window(self) -> deque[EpisodeWorld]:
        if self.is_final:
            return deque()
        return deque(maxlen=self.stages[self.stage]["until"].get("episodes", WINDOW_EPISODES))

    def _log(self, directory: Path, global_step: int, measured: tuple) -> None:
        """Append the switch to ``stages.csv``: the stage entered and the numbers that decided it."""
        path = directory / STAGE_LOG
        new_file = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            if new_file:
                writer.writerow(STAGE_COLUMNS)
            writer.writerow((global_step, self.stage, *measured))
        print(
            f"step {global_step}: world stage {self.stage - 1} -> {self.stage} "
            f"({measured[0]} episodes, mean served {measured[1]:.2f}, caught share {measured[2]})",
            flush=True,
        )


class WorldStage(gym.Wrapper):
    """A training env that plays the curriculum's current world and reports each finished episode.

    At every reset it sets the current stage's ``env_kwargs`` as attributes of the shop env (the
    shop reads them when it plans the episode), and the values the card built the env with for
    every other key a stage touches. It counts served orders, food falls and falls caught on the
    very next move from the shop's own events, before the vector env resets a finished episode.
    """

    def __init__(self, env: gym.Env, curriculum: WorldCurriculum) -> None:
        super().__init__(env)
        self.curriculum = curriculum
        base = env.unwrapped
        keys = {key for stage in curriculum.stages for key in stage["env_kwargs"]}
        unknown = sorted(key for key in keys if not hasattr(base, key))
        if unknown:
            raise ValueError(f"env_stages set {unknown}, which the env does not have")
        self.card_world = {key: getattr(base, key) for key in keys}
        self.stage = curriculum.stage
        self.served = self.falls = self.caught = 0
        self.fell = False  # food fell on the last step: this step is its catch

    def reset(self, **kwargs):
        self.stage = self.curriculum.stage
        base = self.env.unwrapped
        for key, value in {**self.card_world, **self.curriculum.world}.items():
            setattr(base, key, value)
        self.served = self.falls = self.caught = 0
        self.fell = False
        return super().reset(**kwargs)

    def step(self, action):
        observation, reward, terminated, truncated, info = super().step(action)
        base = self.env.unwrapped
        events = base.events_this_step
        holding = base.carrying is not None and base.carrying.type == "box"
        self.served += events.count("serve")
        self.caught += int(self.fell and holding)
        self.fell = "fall" in events
        self.falls += int(self.fell)
        if terminated or truncated:
            episode = EpisodeWorld(self.stage, self.served, self.falls, self.caught)
            self.curriculum.finished.append(episode)
        return observation, reward, terminated, truncated, info
