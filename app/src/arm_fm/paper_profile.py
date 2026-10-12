"""The paper prompt profile: generate a bundle the way the ARM-FM authors did.

The prompt texts are read at run time from a local clone of the authors' repository, named per
environment by a ``paper-sources.json``. The repository has no licence, so no text of theirs is
stored here; this module only holds the loop around it. Per environment the profile runs:

1. a Reward Machine conversation: generator, critic, and the generator again with the critic's
   answer, at most ``MAX_ROUNDS`` times, keeping the last parseable machine;
2. the same loop for the labeling functions, with the machine in the generator prompt;
3. one request for the state descriptions with our own prompt (the authors' is unreleased).

The engines take one system and one user message, so a conversation is sent as a transcript in
the user message. The event vocabulary is whatever the generator names in its guards.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from src.compiler import (
    PaperRewardMachine,
    RuntimeValidationError,
    parse_paper_reward_machine,
    serialize_paper_reward_machine,
)
from src.engines import RetryableEngineError
from src.prompts import read_prompt, render_prompt

from .artifacts import ArtifactBundle, BundleManifest
from .generation import _extract_artifact, _extract_code, _parse_descriptions
from .probe import EpisodeProbe, probe_labeling
from .runtime import load_labeling_functions

PAPER_REFERENCE_SHA = "9a38c4a0f4e82c02052218193f033b2575bd3396"
MAX_ROUNDS = 3
SYSTEM_PROMPT = "You are a helpful assistant."
ROLES = ("rm_generator", "rm_critic", "labeling_generator", "labeling_critic")
REQUIRED_KEYS = ("environment", "description_context")
FINAL_LAG_STEPS = 3  # a final RM state may be entered this early before the env itself ends
EVENT_NOTE = "Event named by the generator; no description was declared."
_MISSION = re.compile(r'\*\*Mission:\*\*\s*"(.+?)"', re.DOTALL)
_COLORS = {"red", "green", "blue", "purple", "yellow", "grey", "gray"}
_FOLLOW_UP = "Apply the critic's requested changes and answer again in the same format."


# ======================================================================================
#                                      THE CLONE
# ======================================================================================


def clone_head(clone: Path) -> str:
    """Read the clone's HEAD commit from its ``.git`` folder, without running git."""
    git_dir = clone / ".git"
    head = (git_dir / "HEAD").read_text("utf-8").strip()
    if not head.startswith("ref: "):
        return head
    ref = head.removeprefix("ref: ")
    loose = git_dir / ref
    if loose.is_file():
        return loose.read_text("utf-8").strip()
    for line in (git_dir / "packed-refs").read_text("utf-8").splitlines():
        sha, _, name = line.partition(" ")
        if name == ref:
            return sha
    raise ValueError(f"Cannot resolve HEAD of {clone}")


def load_sources(path: Path) -> dict[str, Any]:
    """Read one ``paper-sources.json`` and check it names the prompt roles and the probe layouts."""
    try:
        sources = json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{path} is not valid JSON: {error}") from error
    if not isinstance(sources, dict) or not isinstance(sources.get("sources"), dict):
        raise ValueError(f"{path} must be an object with a 'sources' object")
    missing = [
        role
        for role in ROLES
        if not isinstance(sources["sources"].get(role), dict)
        or "file" not in sources["sources"][role]
    ]
    missing += [key for key in REQUIRED_KEYS if key not in sources]
    probe = sources.get("probe")
    if not (isinstance(probe, dict) and probe.get("gym_ids") and probe.get("gating_seeds")):
        missing.append("probe with gym_ids and gating_seeds")
    elif not isinstance(probe.get("max_final_lag", 0), int) or probe.get("max_final_lag", 0) < 0:
        raise ValueError(f"{path}: probe.max_final_lag must be a non-negative integer")
    if missing:
        raise ValueError(f"{path} lacks: {', '.join(missing)}")
    return sources


def render_source(clone: Path, spec: dict[str, Any], mission: str = "") -> str:
    """Read one prompt template from the clone: a file or a trace section, then our substitutions.

    ``spec`` holds ``file``, optionally ``section`` (a ``=== <section> ===`` block of a trace
    file), ``until`` (a regular expression where the section's prompt ends) and ``replace``, a
    list of ``{"pattern", "with"}`` regular-expression substitutions (``{MISSION}`` in ``with``
    stands for the mission).
    """
    text = (clone / spec["file"]).read_text("utf-8")
    if "section" in spec:
        text = _section(text, spec["section"], spec["file"])
    if "until" in spec:  # a trace section runs on into the recorded rounds
        end = re.search(spec["until"], text)
        if end is None:
            raise ValueError(f"The end marker {spec['until']!r} matched nothing in {spec['file']}")
        text = text[: end.start()]
    for item in spec.get("replace", []):
        text, count = re.subn(
            item["pattern"], item["with"].replace("{MISSION}", mission), text, flags=re.DOTALL
        )
        if count == 0:
            raise ValueError(f"A replacement matched nothing in {spec['file']}: {item['pattern']}")
    return text.strip()


def _section(text: str, name: str, file: str) -> str:
    match = re.search(rf"^=== {re.escape(name)} ===\n(.*?)(?=^=== |\Z)", text, re.DOTALL | re.M)
    if match is None:
        raise ValueError(f"{file} has no '=== {name} ===' section")
    return match.group(1)


@dataclass(frozen=True)
class PaperPrompts:
    """The four prompt templates of one environment, as read from the clone."""

    templates: dict[str, str]
    mission: str

    @classmethod
    def read(cls, clone: Path, sources: dict[str, Any]) -> PaperPrompts:
        mission = sources.get("mission", "")
        templates = {
            role: render_source(clone, sources["sources"][role], mission) for role in ROLES
        }
        if not mission:
            match = _MISSION.search(templates["rm_generator"])
            if match is None:
                raise ValueError("The RM generator template has no quoted mission")
            mission = " ".join(match.group(1).split())
        return cls(templates, mission)

    def hashes(self) -> dict[str, str]:
        return {role: _sha(text) for role, text in self.templates.items()}


# ======================================================================================
#                                   THE CONVERSATIONS
# ======================================================================================


@dataclass(frozen=True)
class Engines:
    """The role engines: the generator model and the critic model."""

    generator: Any
    critic: Any


@dataclass
class Round:
    """One generator answer and, when it parsed, the critic's answer to it."""

    stage: str
    number: int
    prompt: str
    reply: str
    candidate: str = ""
    critic_prompt: str = ""
    critic_reply: str = ""
    verdict: str = ""  # accepted | changes | unclear | invalid
    error: str = ""


@dataclass
class StageResult:
    """The rounds of one loop and whether the critic accepted the last candidate."""

    rounds: list[Round] = field(default_factory=list)
    accepted: bool = False


@dataclass(frozen=True)
class _Loop:
    """What one generator-critic loop needs besides its engines."""

    stage: str
    first_prompt: str
    extract: Callable[[str], str]
    check: Callable[[str], Any]  # raises when the candidate is unusable, else the parsed value
    critic_prompt: Callable[[str], str]


def critic_verdict(reply: str) -> str:
    """``accepted`` when the critic's last verdict phrase is NO CHANGES NEEDED."""
    text = reply.upper()
    accepted, required = text.rfind("NO CHANGES NEEDED"), text.rfind("CHANGES REQUIRED")
    if accepted == -1 and required == -1:
        return "unclear"
    return "accepted" if accepted > required else "changes"


def refine_reward_machine(
    prompts: PaperPrompts, engines: Engines
) -> tuple[PaperRewardMachine | None, StageResult]:
    """Run the RM conversation and return the last parseable machine."""
    critic_template = prompts.templates["rm_critic"]
    loop = _Loop(
        "reward_machine",
        prompts.templates["rm_generator"],
        _extract_artifact,
        parse_paper_reward_machine,
        lambda candidate: (
            f"{critic_template}\n\n---\n\n## Reward machine to evaluate\n\n"
            f"```plaintext\n{candidate}\n```"
        ),
    )
    return _refine(loop, engines)


def refine_labeling(
    prompts: PaperPrompts, machine: PaperRewardMachine, engines: Engines
) -> tuple[str | None, StageResult]:
    """Run the labeling conversation and return the last source that loads for the RM events."""
    rm_text = serialize_paper_reward_machine(machine)
    template = prompts.templates["labeling_generator"]
    if "{REWARD_MACHINE}" not in template:
        raise ValueError("The labeling generator template has no {REWARD_MACHINE} slot")
    critic_template = prompts.templates["labeling_critic"]

    def load(candidate: str) -> str:
        load_labeling_functions(candidate, machine.propositions)
        return candidate

    loop = _Loop(
        "labeling",
        template.replace("{REWARD_MACHINE}", rm_text),
        _extract_code,
        load,
        lambda candidate: (
            f"{critic_template}\n\n---\n\n## Reward machine\n\n```plaintext\n{rm_text}\n```\n\n"
            f"## Python functions to evaluate\n\n```python\n{candidate}```"
        ),
    )
    return _refine(loop, engines)


def _refine(loop: _Loop, engines: Engines) -> tuple[Any, StageResult]:
    result = StageResult()
    transcript: list[tuple[str, str]] = []
    kept = None
    for number in range(1, MAX_ROUNDS + 1):
        prompt = _with_transcript(loop.first_prompt, transcript)
        reply = _ask(engines.generator, prompt)
        item = Round(loop.stage, number, prompt, reply, candidate=loop.extract(reply))
        result.rounds.append(item)
        try:
            kept = loop.check(item.candidate)
        except (RuntimeValidationError, ValueError) as error:
            item.verdict, item.error = "invalid", str(error)
            transcript.append((reply, f"Your answer was rejected by the parser: {error}"))
            continue
        item.critic_prompt = loop.critic_prompt(item.candidate)
        item.critic_reply = _ask(engines.critic, item.critic_prompt)
        item.verdict = critic_verdict(item.critic_reply)
        result.accepted = item.verdict == "accepted"
        if result.accepted:
            break
        transcript.append((reply, item.critic_reply))
    return kept, result


def _with_transcript(first_prompt: str, transcript: Sequence[tuple[str, str]]) -> str:
    if not transcript:
        return first_prompt
    parts = [first_prompt]
    for answer, critique in transcript:
        parts.append(
            f"---\n\nYour previous answer:\n\n{answer}\n\nThe critic replied:\n\n{critique}"
        )
    parts.append(f"---\n\n{_FOLLOW_UP}")
    return "\n\n".join(parts)


def _ask(engine: Any, user: str, system: str = SYSTEM_PROMPT) -> str:
    """One request; a timeout or server error is retried once."""
    try:
        return str(engine.request_text(system, user))
    except RetryableEngineError:
        return str(engine.request_text(system, user))


# ======================================================================================
#                                  FINAL STATES AND GATES
# ======================================================================================


def infer_final_states(machine: PaperRewardMachine) -> tuple[str, ...]:
    """States that can never be left: they have no transition except an ``else`` self-loop."""
    return tuple(
        state
        for state in machine.states
        if all(
            item.source != state or (item.is_else and item.destination == state)
            for item in machine.transitions
        )
    )


def literal_warnings(labeling_source: str) -> list[str]:
    """Warn about colour names and integer coordinates, which tie a labeling to one layout."""
    warnings: set[str] = set()
    for node in ast.walk(ast.parse(labeling_source)):
        if not isinstance(node, ast.Constant):
            continue
        if isinstance(node.value, str) and node.value.lower() in _COLORS:
            warnings.add(f"colour literal {node.value!r}")
        elif isinstance(node.value, int) and not isinstance(node.value, bool) and node.value >= 2:
            warnings.add(f"integer literal {node.value}")
    return sorted(warnings)


@dataclass
class GateResult:
    """The static gates of one draw.

    ``probes`` gate the draw: the layouts the runs use. ``held_out`` layouts are only reported.
    ``max_final_lag`` is the most steps a final RM state may be entered before the env ends the
    episode; without it the lag only warns.
    """

    events: tuple[str, ...] = ()
    initial_final: bool = False
    probes: list[EpisodeProbe] = field(default_factory=list)
    held_out: list[EpisodeProbe] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    max_final_lag: int | None = None

    @property
    def events_never_fired(self) -> list[str]:
        fired = set().union(*(item.events_fired for item in self.probes))
        return sorted(set(self.events) - fired)

    @property
    def failures(self) -> list[str]:
        """Why the draw fails the gates; empty when it passes."""
        reasons = []
        if not self.events:
            reasons.append("the RM has no event")
        if self.initial_final:
            reasons.append("the initial RM state is final")
        if not self.probes:
            reasons.append("no probe episode ran")
        if any(not item.solved for item in self.probes):
            reasons.append("the scripted player did not solve every probe layout")
        if any(not item.reached_final for item in self.probes):
            reasons.append("the RM did not end in a final state on every probe layout")
        if self.events_never_fired:
            reasons.append("events never fired: " + ", ".join(self.events_never_fired))
        if self.max_final_lag is not None:
            early = _early_finals(self.probes, self.max_final_lag)
            if early:
                reasons.append(
                    f"the final RM state is entered more than {self.max_final_lag} steps before "
                    f"the env ends in {len(early)} of {len(self.probes)} probes "
                    f"(up to {max(early)} steps)"
                )
        return reasons

    @property
    def passed(self) -> bool:
        return not self.failures

    def summary(self) -> dict[str, Any]:
        return {
            "probe_passed": self.passed,
            "failures": self.failures,
            "probe_episodes": [_episode_summary(item) for item in self.probes],
            "held_out_episodes": [_episode_summary(item) for item in self.held_out],
            "events_never_fired": self.events_never_fired,
            "warnings": self.warnings,
        }


def _episode_summary(item: EpisodeProbe) -> dict[str, Any]:
    return {
        "gym_id": item.gym_id,
        "seed": item.seed,
        "steps": item.steps,
        "env_solved": item.solved,
        "rm_path": item.rm_path,
        "final_entered": item.final_entered,
        "reached_final": item.reached_final,
        "error": item.error,
    }


def _early_finals(probes: Sequence[EpisodeProbe], limit: int) -> list[int]:
    """Steps by which a probe entered a final RM state before the env ended, when above ``limit``."""
    lags = [item.steps - item.final_entered for item in probes if item.final_entered is not None]
    return [lag for lag in lags if lag > limit]


def early_final_warning(probes: Sequence[EpisodeProbe]) -> list[str]:
    """Warn when the final RM state is entered well before the env ends the episode.

    Used when the environment sets no ``max_final_lag``: the authors' own KeyCorridor RM
    legitimately ends before the ball is taken.
    """
    lags = _early_finals(probes, FINAL_LAG_STEPS)
    if not lags:
        return []
    return [
        f"the final RM state is entered more than {FINAL_LAG_STEPS} steps before the env ends in "
        f"{len(lags)} of {len(probes)} probes (up to {max(lags)} steps)"
    ]


def run_gates(
    machine: PaperRewardMachine, labeling_source: str, probe: dict[str, Any]
) -> GateResult:
    """Probe a generated RM and labeling with the scripted player on the layouts of ``probe``.

    ``probe`` names ``gym_ids``, the ``gating_seeds`` that decide the gate, optional
    ``held_out_seeds`` that are only reported and an optional ``max_final_lag``: an environment
    whose last RM stage is the env's own success sets it, so an early final state fails the gate.
    """
    gym_ids, finals = probe["gym_ids"], machine.final_states
    probes = probe_labeling(machine, labeling_source, gym_ids, probe["gating_seeds"], finals)
    held_out = probe_labeling(
        machine, labeling_source, gym_ids, probe.get("held_out_seeds", []), finals
    )
    max_lag = probe.get("max_final_lag")
    warnings = literal_warnings(labeling_source)
    if max_lag is None:
        warnings += early_final_warning(probes)
    return GateResult(
        machine.propositions,
        machine.initial_state in finals,
        probes,
        held_out,
        warnings,
        max_lag,
    )


# ======================================================================================
#                                      ONE DRAW
# ======================================================================================


@dataclass(frozen=True)
class PaperRun:
    """Everything the draws of one environment share."""

    prompts: PaperPrompts
    sources: dict[str, Any]
    models: dict[str, str]
    engines: Engines


@dataclass
class PaperDraw:
    """One complete generation attempt: its artifacts, rounds, gate results and bundle."""

    number: int
    machine: PaperRewardMachine | None = None
    labeling_source: str | None = None
    descriptions: dict[str, str] = field(default_factory=dict)
    rm_stage: StageResult = field(default_factory=StageResult)
    labeling_stage: StageResult = field(default_factory=StageResult)
    gates: GateResult | None = None
    error: str = ""
    bundle: ArtifactBundle | None = None

    @property
    def passed(self) -> bool:
        return self.gates is not None and self.gates.passed and not self.error


def generate_draw(number: int, run: PaperRun) -> PaperDraw:
    """Run the three stages once; descriptions are only requested after the gates pass."""
    draw = PaperDraw(number)
    machine, draw.rm_stage = refine_reward_machine(run.prompts, run.engines)
    if machine is None:
        draw.error = f"no parseable Reward Machine in {MAX_ROUNDS} rounds"
    else:
        draw.machine = replace(machine, final_states=infer_final_states(machine))
        draw.labeling_source, draw.labeling_stage = refine_labeling(
            run.prompts, draw.machine, run.engines
        )
        if draw.labeling_source is None:
            draw.error = f"no labeling that loads for the RM events in {MAX_ROUNDS} rounds"
    if draw.machine is not None and draw.labeling_source is not None:
        draw.gates = run_gates(draw.machine, draw.labeling_source, run.sources["probe"])
        if draw.gates.passed:
            draw.descriptions = _describe_states(draw.machine, run)
            if not draw.descriptions:
                draw.error = f"no valid state descriptions in {MAX_ROUNDS} attempts"
    draw.bundle = _bundle(draw, run)
    return draw


def _describe_states(machine: PaperRewardMachine, run: PaperRun) -> dict[str, str]:
    for _ in range(MAX_ROUNDS):
        try:
            reply = _ask(
                run.engines.generator,
                render_prompt(
                    "arm_fm",
                    "description_generator",
                    environment=run.sources["description_context"],
                    task=run.prompts.mission,
                    candidate=serialize_paper_reward_machine(machine),
                    states=", ".join(machine.states),
                ),
                read_prompt("arm_fm", "description_generator"),
            )
            return _parse_descriptions(reply, machine.states)
        except ValueError:  # includes json.JSONDecodeError
            continue
    return {}


def _bundle(draw: PaperDraw, run: PaperRun) -> ArtifactBundle:
    rounds = [*draw.rm_stage.rounds, *draw.labeling_stage.rounds]
    machine = draw.machine
    models = run.models
    reconstruction = [
        "description_generator",
        "critic candidate framing",
        "conversation transcript",
    ]
    if run.sources.get("reconstruction"):
        reconstruction.append("prompts of this environment (no authentic prompt was released)")
    manifest = BundleManifest(
        task=run.prompts.mission,
        environment=run.sources["environment"],
        proposition_semantics=dict.fromkeys(machine.propositions if machine else (), EVENT_NOTE),
        provenance={
            "generator": (
                f"paper profile: {models['generator']} (generator), {models['critic']} (critic)"
            ),
            "status": "reconstructed",
            "prompt_profile": "paper",
            "reconstruction": reconstruction,
        },
        generation={
            "prompt_profile": "paper",
            "reference_sha": PAPER_REFERENCE_SHA,
            "sources": run.sources,
            "generator_model": models["generator"],
            "critic_model": models["critic"],
            "prompt_template_sha256": run.prompts.hashes(),
            "draw": draw.number,
            "rounds": {
                "reward_machine": len(draw.rm_stage.rounds),
                "labeling": len(draw.labeling_stage.rounds),
            },
            "critic_accepted": {
                "reward_machine": draw.rm_stage.accepted,
                "labeling": draw.labeling_stage.accepted,
            },
            "verdicts": [(item.stage, item.number, item.verdict) for item in rounds],
            "final_states_inferred": list(machine.final_states) if machine else [],
            "gates": draw.gates.summary() if draw.gates is not None else {},
            "error": draw.error,
        },
        validation={"structural": machine is not None and draw.labeling_source is not None},
        stage_status={
            "reward_machine": "complete" if machine else "failed",
            "labeling": "complete" if draw.labeling_source else "failed" if machine else "pending",
            "descriptions": "complete" if draw.descriptions else "pending",
        },
        inputs={"task": run.prompts.mission, "prompt_profile": "paper"},
        errors=[item.error for item in rounds if item.error] + ([draw.error] if draw.error else []),
        effective_settings={
            "mode": "paper",
            "max_rounds": MAX_ROUNDS,
            "generator_model": models["generator"],
            "critic_model": models["critic"],
            "system_prompt": SYSTEM_PROMPT,
        },
        rm_mode="arm-fm",
    )
    attempts = [
        {
            "stage": item.stage,
            "attempt": item.number,
            "status": item.verdict,
            "candidate": item.candidate,
            "feedback": item.critic_reply,
            "error": item.error,
            "prompt_sha256": _sha(item.prompt),
        }
        for item in rounds
    ]
    return ArtifactBundle(
        manifest,
        machine,
        draw.labeling_source or "",
        draw.descriptions,
        attempts=attempts,
        raw_responses=[item.__dict__ for item in rounds],
    )


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
