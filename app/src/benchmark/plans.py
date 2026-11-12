"""Run a card plan in the real, seeded env and record what happened.

A plan is a list of steps (``pickup``, ``toggle``, ``goto``, ``drop``, ``wait``, ``policy``).
Navigation is the breadth-first search of ``arm_fm.probe``; every move goes through
``env.step``, so the recorded actions replay exactly. A plan may break rules, never physics.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import gymnasium as gym

from src.arm_fm.environments import make_environment
from src.arm_fm.probe import PICKUP, TOGGLE, EpisodeProbe, ProbeError, _Player

from .reference_labels import ReferenceLabeler, env_module, labeler_for

DONE = 6  # MiniGrid's ``done`` action: a no-op that still takes a step
OBJECT_ALIASES = {"exit": "goal"}  # the event room's exit is a MiniGrid Goal


class PlanError(RuntimeError):
    """A plan step cannot run in this env."""


@dataclass
class Rollout:
    """One recorded episode: the action taken, the reference labels and the env reward per step.

    ``terminated`` and ``truncated`` are the env's own; ``rm_stopped`` says a Reward Machine ended
    the episode before the env did (an agent episode of an RM run).
    """

    reset_seed: int = 0
    actions: list[int] = field(default_factory=list)
    labels: list[dict[str, bool]] = field(default_factory=list)
    env_rewards: list[float] = field(default_factory=list)
    terminated: bool = False
    truncated: bool = False
    rm_stopped: bool = False


class PlanPlayer(_Player):
    """The probe's grid planner, recording a rollout instead of an RM path."""

    def __init__(self, env: Any, labeler: ReferenceLabeler, gym_id: str, reset_seed: int) -> None:
        super().__init__(env, EpisodeProbe(gym_id, reset_seed), ())
        self.labeler = labeler
        self.rollout = Rollout(reset_seed)

    # ============================== acting ==============================

    def act(self, action: int) -> None:
        if self.done:
            raise ProbeError("the episode already ended")
        _, reward, terminated, truncated, _ = self.env.step(action)
        self.rollout.actions.append(int(action))
        self.rollout.labels.append(self.labeler.labels(self.base))
        self.rollout.env_rewards.append(float(reward))
        self.rollout.terminated, self.rollout.truncated = bool(terminated), bool(truncated)
        self.done = bool(terminated or truncated)

    def run(self, steps: Sequence[Mapping[str, Any]]) -> Rollout:
        """Play every step in order; raises ``PlanError`` naming the step that cannot run."""
        for number, step in enumerate(steps):
            try:
                self.run_step(step)
            except (ProbeError, PlanError) as error:
                raise PlanError(f"step {number} {step}: {error}") from error
        return self.rollout

    def run_step(self, step: Mapping[str, Any]) -> None:
        kind = _field(step, "do")
        if kind == "wait":
            for _ in range(_field(step, "n")):
                if self.done:
                    return
                self.act(DONE)
        elif self.done:
            raise PlanError("the episode already ended")
        elif kind == "drop":
            self.drop()
        elif kind == "policy":
            self.run_policy(step)
        elif kind in ("pickup", "toggle", "goto"):
            self.interact(kind, _field(step, "obj"))
        else:
            raise PlanError(f"unknown step kind {kind!r}")

    # ============================== the steps ==============================

    def interact(self, kind: str, spec: str) -> None:
        """Walk to the nearest reachable object named by ``spec`` and act on it."""
        walk, position = self.nearest(spec, walk_onto=kind == "goto" and _kind_of(spec) == "goal")
        self.execute(walk)
        if kind == "pickup":
            if self.base.carrying is not None:
                raise PlanError("the hands are full; the plan needs a drop first")
            self.act(PICKUP)
            if self.base.carrying is None:
                raise PlanError(f"{spec} at {position} cannot be picked up")
        elif kind == "toggle":
            target = self.cell(*position)
            was_open = target.is_open if target.type == "door" else None
            self.act(TOGGLE)
            if was_open is not None and target.is_open == was_open:
                raise PlanError(f"the {spec} did not change (a locked door needs its key)")

    def nearest(self, spec: str, *, walk_onto: bool) -> tuple[list[int], tuple[int, int]]:
        """The shortest action list to the object ``spec`` names, and the object's cell.

        ``spec`` is ``<type>``, ``<type>:<color>`` or ``door:locked``; the agent ends on the
        cell for ``walk_onto``, else on a cell that faces it.
        """
        kind, qualifier = _kind_of(spec), spec.partition(":")[2]
        color = None if qualifier in ("", "locked") else qualifier
        routes = []
        for position in self.objects(kind, color):
            if qualifier == "locked" and not self.cell(*position).is_locked:
                continue
            route = (
                self.plan(lambda x, y, _d, p=position: (x, y) == p)
                if walk_onto
                else self.plan_facing(position)
            )
            if route is not None:
                routes.append((route, position))
        if not routes:
            raise PlanError(f"no reachable {spec}")
        return min(routes, key=lambda item: len(item[0]))

    def drop(self) -> None:
        if self.base.carrying is None:
            raise PlanError("nothing is carried")
        self.empty_hands()  # the probe's rule: a free cell that cuts off no reachable cell

    def run_policy(self, step: Mapping[str, Any]) -> None:
        """Let the env's scripted policy play to the end of the episode."""
        policy = getattr(env_module(self.base), "scripted_policy", None)
        if policy is None:
            raise PlanError(f"{_field(step, 'name')}: the env has no scripted_policy")
        ignore = tuple(step.get("ignore", ()))
        while not self.done:
            self.act(policy(self.base, ignore=ignore))


def _field(step: Mapping[str, Any], name: str) -> Any:
    """A field of a plan step; a step that lacks it, or is no object, is a bad step."""
    try:
        return step[name]
    except (KeyError, TypeError) as error:
        raise PlanError(f"bad step ({error!r})") from error


def _kind_of(spec: str) -> str:
    """The object type a spec names: ``goal:green`` and ``exit`` are goals."""
    kind = spec.partition(":")[0]
    return OBJECT_ALIASES.get(kind, kind)


def run_plan(env_spec: Mapping[str, Any], steps: Sequence[Mapping[str, Any]], seed: int) -> Rollout:
    """Run ``steps`` in a fresh env of the card's ``env_spec`` reset with ``seed``.

    Raises:
        PlanError: If the env cannot be built, a step cannot run, or the env has no reference
            labeler.
    """
    try:
        env = make_environment(env_spec["gym_id"], **(env_spec.get("env_kwargs") or {}))
    except (gym.error.Error, KeyError, TypeError) as error:
        raise PlanError(f"cannot build the env: {error!r}") from error
    try:
        env.reset(seed=seed)
        labeler = labeler_for(env_spec["gym_id"], env)
        return PlanPlayer(env, labeler, env_spec["gym_id"], seed).run(steps)
    finally:
        env.close()
