"""Baseline ARM-FM generation and compiler-only RM substitution."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.compiler import CompilationResult
from src.models import EnvironmentDescription
from src.prompts import read_arm_fm_prompt, render_prompt

from .artifacts import ArtifactBundle, BundleManifest
from .runtime import (
    PaperRewardMachine,
    compiler_machine_to_paper,
    load_labeling_functions,
    parse_paper_reward_machine,
    serialize_paper_reward_machine,
)


MAX_ATTEMPTS = 3


@dataclass
class StageAttempt:
    stage: str
    attempt: int
    status: str
    candidate: str = ""
    feedback: str = ""
    error: str = ""
    raw_response: str = ""


@dataclass
class GenerationResult:
    """All baseline outputs, including failed and refined attempts."""

    bundle: ArtifactBundle
    attempts: list[StageAttempt] = field(default_factory=list)


def generate_reward_machine(
    task: str,
    environment: EnvironmentDescription,
    engine: object,
    *,
    api_description: str = "The documented environment object passed as env.",
    human_feedback: Mapping[str, str] | None = None,
    max_attempts: int = MAX_ATTEMPTS,
) -> tuple[PaperRewardMachine | None, str, list[StageAttempt]]:
    """Generate and refine one paper Reward Machine, keeping the last parseable candidate."""
    if not task.strip():
        raise ValueError("Task must be nonempty")
    attempts: list[StageAttempt] = []
    machine: PaperRewardMachine | None = None
    machine_text = ""
    rm_history: list[str] = []
    if human_feedback and human_feedback.get("reward_machine"):
        rm_history.append("Human feedback: " + human_feedback["reward_machine"])

    for attempt in range(1, max_attempts + 1):
        try:
            candidate = _request_text(
                engine,
                "rm_generator",
                environment=environment.markdown,
                task=task,
                api=api_description,
                history="\n\n".join(rm_history),
            )
            machine_text = _extract_artifact(candidate)
            machine = parse_paper_reward_machine(
                machine_text,
                propositions=environment.proposition_ids,
                require_final_states=True,
            )

            accepted, feedback, raw_response = _critic(
                engine,
                "rm_critic",
                environment=environment.markdown,
                task=task,
                candidate=machine_text,
            )

            attempt_record = StageAttempt(
                "reward_machine", attempt, "accepted" if accepted else "rejected",
                machine_text, feedback, "", raw_response,
            )

            attempts.append(attempt_record)

            if accepted:
                break

            rm_history.append(feedback)
            
        except Exception as error:
            attempts.append(StageAttempt("reward_machine", attempt, "failed", machine_text, error=str(error)))
            rm_history.append(str(error))

    return machine, machine_text, attempts


def generate_baseline_bundle(
    task: str,
    environment: EnvironmentDescription,
    engine: object,
    *,
    api_description: str = "The documented environment object passed as env.",
    human_feedback: Mapping[str, str] | None = None,
    max_attempts: int = MAX_ATTEMPTS,
    bundle_directory: str | Path | None = None,
    overwrite: bool = False,
) -> GenerationResult:
    """Generate RM, labeling code, and state descriptions with bounded refinement."""
    machine, machine_text, attempts = generate_reward_machine(
        task,
        environment,
        engine,
        api_description=api_description,
        human_feedback=human_feedback,
        max_attempts=max_attempts,
    )

    unaccepted = machine is None or not any(
        item.stage == "reward_machine" and item.status == "accepted" for item in attempts
    )

    if unaccepted:
        bundle = _build_bundle(
            task, environment, machine, labeling_source="", descriptions={}, attempts=attempts,
            api_description=api_description, max_attempts=max_attempts, engine=engine,
            human_feedback=human_feedback,
        )
        _persist_failure(bundle, bundle_directory, overwrite=overwrite)
        raise RuntimeError("Reward Machine generation was not accepted within three attempts")

    labeling_source = ""
    descriptions: dict[str, str] = {}

    try:
        labeling_source = _generate_labeling(
            task, environment, machine_text, engine, api_description, max_attempts, attempts
        )
        descriptions = _generate_descriptions(
            task, environment, machine, engine, max_attempts=max_attempts, attempts=attempts
        )
        
    except Exception:
        bundle = _build_bundle(
            task, environment, machine, labeling_source=labeling_source, descriptions=descriptions,
            attempts=attempts, api_description=api_description, max_attempts=max_attempts,
            engine=engine,
            human_feedback=human_feedback,
        )
        _persist_failure(bundle, bundle_directory, overwrite=overwrite)
        raise

    bundle = _build_bundle(
        task, environment, machine, labeling_source=labeling_source, descriptions=descriptions,
        attempts=attempts, api_description=api_description, max_attempts=max_attempts,
        engine=engine,
        human_feedback=human_feedback,
    )
    bundle.validate()
    return GenerationResult(bundle=bundle, attempts=attempts)


def _build_bundle(
    task: str,
    environment: EnvironmentDescription,
    machine: PaperRewardMachine | None,
    *,
    labeling_source: str,
    descriptions: Mapping[str, str],
    attempts: Sequence[StageAttempt],
    api_description: str,
    max_attempts: int,
    engine: object,
    human_feedback: Mapping[str, str] | None = None,
) -> ArtifactBundle:
    manifest = BundleManifest(
        task=task.strip(),
        environment=str(environment.source),
        proposition_semantics={item.identifier: item.description for item in environment.propositions},
        provenance={"status": "reconstructed", "generator": "arm-fm"},
        generation={
            "max_attempts": max_attempts,
            "labeling_api": api_description,
            "human_feedback": dict(human_feedback or {}),
            **_attempt_metadata(attempts, {"reward_machine", "labeling", "descriptions"}),
        },
        validation={
            "structural": machine is not None,
            "critic": any(item.status == "accepted" for item in attempts),
        },
        stage_status={
            "reward_machine": "complete" if machine is not None else "failed",
            "labeling": "complete" if labeling_source else "pending",
            "descriptions": "complete" if descriptions else "pending",
        },
        inputs={"task": task.strip(), "environment_markdown": environment.markdown},
        api_definitions={"labeling": api_description},
        errors=[item.error for item in attempts if item.error],
        effective_settings={
            "provider": getattr(engine, "provider_name", None),
            "model": getattr(engine, "model", None),
            "max_attempts": max_attempts,
        },
        rm_mode="arm-fm",
    )
    return ArtifactBundle(
        manifest=manifest,
        reward_machine=machine,
        labeling_source=labeling_source,
        state_descriptions=dict(descriptions),
        attempts=[item.__dict__ for item in attempts],
        raw_responses=[
            {"stage": item.stage, "attempt": item.attempt, "candidate": item.candidate,
             "feedback": item.feedback, "error": item.error, "raw_response": item.raw_response}
            for item in attempts
        ],
    )


def _persist_failure(
    bundle: ArtifactBundle,
    directory: str | Path | None,
    *,
    overwrite: bool = False,
) -> None:
    if directory is not None:
        try:
            bundle.save(directory, overwrite=overwrite)
        except OSError:
            pass


def adapt_compilation_result(
    result: CompilationResult,
    *,
    labeling_source: str = "",
    state_descriptions: Mapping[str, str] | None = None,
) -> ArtifactBundle:
    """Create the shared bundle from an accepted compiler result only."""
    machine = compiler_machine_to_paper(result.reward_machine, result.environment.proposition_ids)
    descriptions = dict(state_descriptions or {})
    manifest = BundleManifest(
        task=result.proposal.task,
        environment=str(result.environment.source),
        proposition_semantics={item.identifier: item.description for item in result.environment.propositions},
        provenance={"status": "reconstructed", "generator": "compiler-adaptation"},
        generation={"compiler_text": result.text},
        validation={
            "structural": True,
            "critic": True,
        },
        inputs={
            "task": result.proposal.task,
            "environment_markdown": getattr(result.environment, "markdown", ""),
        },
        api_definitions={"labeling": "The documented environment object passed as env."},
        effective_settings={"mode": "compiler"},
        stage_status={"reward_machine": "complete", "labeling": "complete" if labeling_source else "pending", "descriptions": "complete" if descriptions else "pending"},
        rm_mode="compiler",
    )
    return ArtifactBundle(manifest, machine, labeling_source, descriptions)


def generate_compiler_bundle(
    results: Sequence[CompilationResult],
    engine: object,
    *,
    api_description: str = "The documented environment object passed as env.",
    bundle_directory: str | Path | None = None,
    overwrite: bool = False,
) -> tuple[ArtifactBundle, ...]:
    """Adapt accepted compiler results; compiler invocation belongs to scripts."""
    if not results:
        raise RuntimeError("Compiler generation returned no accepted in-memory result")
    bundles = []
    for result in results:
        machine = compiler_machine_to_paper(result.reward_machine, result.environment.proposition_ids)
        machine_text = serialize_paper_reward_machine(machine)
        attempts: list[StageAttempt] = []
        labeling_source = ""
        descriptions: dict[str, str] = {}
        try:
            labeling_source = _generate_labeling(
                result.proposal.task,
                result.environment,
                machine_text,
                engine,
                api_description,
                MAX_ATTEMPTS,
                attempts,
            )
            descriptions = _generate_descriptions(
                result.proposal.task, result.environment, machine, engine,
                max_attempts=MAX_ATTEMPTS, attempts=attempts
            )
        except Exception as error:
            bundle = adapt_compilation_result(
                result, labeling_source=labeling_source, state_descriptions=descriptions
            )
            _finish_compiler_bundle(bundle, result, attempts, api_description, error)
            _persist_failure(bundle, bundle_directory, overwrite=overwrite)
            raise
        bundle = adapt_compilation_result(
            result, labeling_source=labeling_source, state_descriptions=descriptions
        )
        _finish_compiler_bundle(bundle, result, attempts, api_description)
        bundles.append(bundle)
    return tuple(bundles)


def _finish_compiler_bundle(
    bundle: ArtifactBundle,
    result: CompilationResult,
    attempts: Sequence[StageAttempt],
    api_description: str,
    error: Exception | None = None,
) -> None:
    compiler_attempt = {
        "stage": "compiler", "attempt": 1, "status": "accepted",
        "candidate": result.text, "feedback": "", "error": "",
    }
    bundle.manifest.generation["labeling_api"] = api_description
    bundle.manifest.generation.update(
        _attempt_metadata(attempts, {"labeling", "descriptions"})
    )
    bundle.manifest.api_definitions["labeling"] = api_description
    bundle.attempts = [compiler_attempt] + [item.__dict__ for item in attempts]
    bundle.raw_responses = [{
        "stage": "compiler", "attempt": 1, "candidate": result.text,
        "feedback": "", "error": "", "raw_response": result.text,
    }] + [
        {"stage": item.stage, "attempt": item.attempt, "candidate": item.candidate,
         "feedback": item.feedback, "error": item.error, "raw_response": item.raw_response}
        for item in attempts
    ]
    bundle.manifest.stage_status.update({
        "reward_machine": "complete",
        "labeling": _stage_status(attempts, "labeling", bundle.labeling_source),
        "descriptions": _stage_status(attempts, "descriptions", bundle.state_descriptions),
    })
    bundle.manifest.errors = [item.error for item in attempts if item.error]
    if error is not None:
        bundle.manifest.errors.append(str(error))


def _generate_labeling(
    task: str,
    environment: EnvironmentDescription,
    machine_text: str,
    engine: object,
    api_description: str,
    max_attempts: int,
    attempts: list[StageAttempt],
) -> str:
    labeling_source = ""
    history: list[str] = []
    propositions = tuple(environment.proposition_ids)
    for attempt in range(1, max_attempts + 1):
        try:
            candidate = _request_text(
                engine,
                "labeling_generator",
                environment=environment.markdown,
                task=task,
                candidate=machine_text,
                api=api_description,
                history="\n\n".join(history),
            )
            labeling_source = _extract_code(candidate)
            _validate_labeling_source(labeling_source, propositions)
            accepted, feedback, raw_response = _critic(
                engine,
                "labeling_critic",
                environment=environment.markdown,
                task=task,
                candidate=machine_text,
                labeling=labeling_source,
            )
            attempts.append(StageAttempt(
                "labeling", attempt, "accepted" if accepted else "rejected",
                labeling_source, feedback, "", raw_response,
            ))
            if accepted:
                return labeling_source
            history.append(feedback)
        except Exception as error:
            attempts.append(StageAttempt("labeling", attempt, "failed", labeling_source, error=str(error)))
            history.append(str(error))
    raise RuntimeError("Labeling generation was not accepted within three attempts")


def _generate_descriptions(
    task: str,
    environment: EnvironmentDescription,
    machine: PaperRewardMachine,
    engine: object,
    *,
    max_attempts: int,
    attempts: list[StageAttempt],
) -> dict[str, str]:
    candidate = ""
    for attempt in range(1, max_attempts + 1):
        try:
            candidate = _request_text(
                engine,
                "description_generator",
                environment=environment.markdown,
                task=task,
                candidate=serialize_paper_reward_machine(machine),
                states=", ".join(machine.states),
            )
            descriptions = _parse_descriptions(candidate, machine.states)
            attempts.append(StageAttempt("descriptions", attempt, "accepted", candidate))
            return descriptions
        except Exception as error:
            attempts.append(StageAttempt("descriptions", attempt, "failed", candidate, error=str(error)))
    raise RuntimeError("State-description generation was not accepted within three attempts")


def _request_text(engine: object, role: str, **values: str) -> str:
    request = getattr(engine, "request_text", None)
    if request is None:
        raise RuntimeError("ARM-FM generation requires an engine with request_text")
    return str(request(read_arm_fm_prompt(role), render_prompt(role, **values)))


def _critic(engine: object, role: str, **values: str) -> tuple[bool, str, str]:
    request = getattr(engine, "request_text", None)
    if request is None:
        raise RuntimeError("ARM-FM critic requires an engine with request_text")
    response = str(request(read_arm_fm_prompt(role), render_prompt(role, **values)))
    try:
        parsed = json.loads(_extract_artifact(response))
    except json.JSONDecodeError as error:
        raise ValueError("ARM-FM critic returned invalid JSON") from error
    if not isinstance(parsed, dict) or not isinstance(parsed.get("accepted"), bool):
        raise ValueError("ARM-FM critic must return boolean accepted")
    feedback = parsed.get("feedback")
    if not isinstance(feedback, str) or not feedback.strip():
        raise ValueError("ARM-FM critic feedback must be nonempty")
    return parsed["accepted"], feedback.strip(), response


def _extract_artifact(text: str) -> str:
    match = re.search(r"```(?:plaintext|text|json)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    return (match.group(1) if match else text).strip()


def _extract_code(text: str) -> str:
    match = re.search(r"```python\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    return (match.group(1) if match else _extract_artifact(text)).strip() + "\n"


def _validate_labeling_source(source: str, propositions: Sequence[str]) -> None:
    load_labeling_functions(source, propositions)


def _parse_descriptions(text: str, states: Sequence[str]) -> dict[str, str]:
    parsed = json.loads(_extract_artifact(text))
    if not isinstance(parsed, dict) or set(parsed) != set(states):
        raise ValueError("State descriptions must contain exactly all RM states")
    if any(not isinstance(value, str) or not value.strip() for value in parsed.values()):
        raise ValueError("State descriptions must be nonempty strings")
    return {state: parsed[state].strip() for state in states}


def _stage_status(attempts: Sequence[StageAttempt], stage: str, artifact: object) -> str:
    if any(item.stage == stage and item.status == "accepted" for item in attempts) and artifact:
        return "complete"
    if any(item.stage == stage and item.status in {"failed", "rejected"} for item in attempts):
        return "failed"
    return "pending"


def _attempt_metadata(attempts: Sequence[StageAttempt], stages: set[str]) -> dict[str, object]:
    accepted = [item for item in attempts if item.stage in stages and item.status == "accepted"]
    attempt = max((item.attempt for item in accepted), default=1)
    complete = {item.stage for item in accepted} == stages
    first_attempt = complete and all(item.attempt == 1 for item in accepted)
    refined = complete and any(item.attempt > 1 for item in accepted)
    return {
        "attempt": attempt,
        "first_attempt": first_attempt,
        "refined": refined,
        "attempt_classification": "first_attempt" if first_attempt else "refined" if refined else "incomplete",
    }
