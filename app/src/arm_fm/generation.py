"""Baseline ARM-FM generation and compiler-only RM substitution."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path

from src.compiler import (
    CompilationResult,
    PaperRewardMachine,
    compiler_machine_to_paper,
    parse_paper_reward_machine,
    serialize_paper_reward_machine,
)
from src.config import Configuration
from src.models import EnvironmentDescription
from src.prompts import read_prompt, render_prompt

from .artifacts import ArtifactBundle, BundleManifest
from .runtime import load_labeling_functions

MAX_ATTEMPTS = 3
DEFAULT_API_DESCRIPTION = "The documented environment object passed as env."


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


class LabelingError(RuntimeError):
    """No labeling candidate was accepted; ``attempts`` holds every try."""

    def __init__(self, attempts: list[StageAttempt]) -> None:
        super().__init__("Labeling generation was not accepted within three attempts")
        self.attempts = attempts


# ======================================================================================
#                                   BASELINE GENERATION
# ======================================================================================


def generate_reward_machine(
    task: str,
    environment: EnvironmentDescription,
    engine: object,
    *,
    api_description: str = DEFAULT_API_DESCRIPTION,
    max_attempts: int = MAX_ATTEMPTS,
) -> tuple[PaperRewardMachine | None, str, list[StageAttempt]]:
    """Generate and refine one paper Reward Machine, keeping the last parseable candidate."""
    if not task.strip():
        raise ValueError("Task must be nonempty")
    attempts: list[StageAttempt] = []
    machine: PaperRewardMachine | None = None
    machine_text = ""
    rm_history: list[str] = []

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
                "reward_machine",
                attempt,
                "accepted" if accepted else "rejected",
                machine_text,
                feedback,
                "",
                raw_response,
            )

            attempts.append(attempt_record)

            if accepted:
                break

            rm_history.append(feedback)

        except Exception as error:
            attempts.append(
                StageAttempt("reward_machine", attempt, "failed", machine_text, error=str(error))
            )
            rm_history.append(str(error))

    return machine, machine_text, attempts


def generate_baseline_bundle(
    task: str,
    environment: EnvironmentDescription,
    engine: object,
    CONFIG: Configuration,
    *,
    api_description: str = DEFAULT_API_DESCRIPTION,
) -> GenerationResult:
    """Generate RM, labeling code, and state descriptions with bounded refinement.

    A failed run persists its inspectable bundle to ``CONFIG.bundle`` before it raises.
    """
    run = _Generation(task, environment, engine, api_description)
    run.generate_reward_machine()
    try:
        run.require_accepted_reward_machine()
        run.generate_labeling()
        run.generate_descriptions()
    except Exception:
        _persist_failure(run.bundle(), CONFIG)
        raise

    bundle = run.bundle()
    bundle.validate()
    return GenerationResult(bundle=bundle, attempts=run.attempts)


class _Generation:
    """One generation run: the accepted artifacts so far and every attempt that produced them."""

    def __init__(
        self,
        task: str,
        environment: EnvironmentDescription,
        engine: object,
        api_description: str,
    ) -> None:
        self.task = task
        self.environment = environment
        self.engine = engine
        self.api_description = api_description
        self.attempts: list[StageAttempt] = []
        self.machine: PaperRewardMachine | None = None
        self.machine_text = ""
        self.labeling_source = ""
        self.descriptions: dict[str, str] = {}

    @classmethod
    def for_compiler_result(
        cls, result: CompilationResult, engine: object, api_description: str
    ) -> _Generation:
        """Start from an accepted compiler machine whose labeling or descriptions are missing."""
        run = cls(result.proposal.task, result.environment, engine, api_description)
        run.machine = compiler_machine_to_paper(
            result.reward_machine, result.environment.proposition_ids
        )
        run.machine_text = serialize_paper_reward_machine(run.machine)
        run.labeling_source = result.labeling_source
        run.descriptions = pair_state_descriptions(result, result.state_descriptions)
        return run

    def generate_reward_machine(self) -> None:
        self.machine, self.machine_text, self.attempts = generate_reward_machine(
            self.task,
            self.environment,
            self.engine,
            api_description=self.api_description,
        )

    def require_accepted_reward_machine(self) -> None:
        accepted = self.machine is not None and any(
            item.stage == "reward_machine" and item.status == "accepted" for item in self.attempts
        )
        if not accepted:
            raise RuntimeError("Reward Machine generation was not accepted within three attempts")

    def generate_labeling(self) -> None:
        self.labeling_source = _refine_labeling(
            self.environment.proposition_ids,
            lambda history: _request_text(
                self.engine,
                "labeling_generator",
                environment=self.environment.markdown,
                task=self.task,
                candidate=self.machine_text,
                api=self.api_description,
                history=history,
            ),
            lambda source: _critic(
                self.engine,
                "labeling_critic",
                environment=self.environment.markdown,
                task=self.task,
                candidate=self.machine_text,
                labeling=source,
            ),
            self.attempts,
        )

    def generate_descriptions(self) -> None:
        candidate = ""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                candidate = _request_text(
                    self.engine,
                    "description_generator",
                    environment=self.environment.markdown,
                    task=self.task,
                    candidate=serialize_paper_reward_machine(self.machine),
                    states=", ".join(self.machine.states),
                )
                descriptions = _parse_descriptions(candidate, self.machine.states)
                self.attempts.append(StageAttempt("descriptions", attempt, "accepted", candidate))
                self.descriptions = descriptions
                return
            except Exception as error:
                self.attempts.append(
                    StageAttempt("descriptions", attempt, "failed", candidate, error=str(error))
                )
        raise RuntimeError("State-description generation was not accepted within three attempts")

    def bundle(self) -> ArtifactBundle:
        manifest = BundleManifest(
            task=self.task.strip(),
            environment=str(self.environment.source),
            proposition_semantics={
                item.identifier: item.description for item in self.environment.propositions
            },
            provenance={"status": "reconstructed", "generator": "arm-fm"},
            generation={
                "max_attempts": MAX_ATTEMPTS,
                "labeling_api": self.api_description,
                **_attempt_metadata(self.attempts, {"reward_machine", "labeling", "descriptions"}),
            },
            validation={
                "structural": self.machine is not None,
                "critic": any(item.status == "accepted" for item in self.attempts),
            },
            stage_status={
                "reward_machine": "complete" if self.machine is not None else "failed",
                "labeling": "complete" if self.labeling_source else "pending",
                "descriptions": "complete" if self.descriptions else "pending",
            },
            inputs={
                "task": self.task.strip(),
                "environment_markdown": self.environment.markdown,
            },
            api_definitions={"labeling": self.api_description},
            errors=[item.error for item in self.attempts if item.error],
            effective_settings={
                "provider": getattr(self.engine, "provider_name", None),
                "model": getattr(self.engine, "model", None),
                "max_attempts": MAX_ATTEMPTS,
            },
            rm_mode="arm-fm",
        )
        return ArtifactBundle(
            manifest=manifest,
            reward_machine=self.machine,
            labeling_source=self.labeling_source,
            state_descriptions=dict(self.descriptions),
            attempts=[item.__dict__ for item in self.attempts],
            raw_responses=[_raw_response(item) for item in self.attempts],
        )


def _persist_failure(bundle: ArtifactBundle, CONFIG: Configuration) -> None:
    if CONFIG.bundle is not None:
        with suppress(OSError):
            bundle.save(CONFIG.bundle, overwrite=CONFIG.overwrite)


def _raw_response(attempt: StageAttempt) -> dict[str, object]:
    return {
        "stage": attempt.stage,
        "attempt": attempt.attempt,
        "candidate": attempt.candidate,
        "feedback": attempt.feedback,
        "error": attempt.error,
        "raw_response": attempt.raw_response,
    }


# ======================================================================================
#                                   COMPILER SUBSTITUTION
# ======================================================================================


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
        proposition_semantics={
            item.identifier: item.description for item in result.environment.propositions
        },
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
        api_definitions={"labeling": DEFAULT_API_DESCRIPTION},
        effective_settings={"mode": "compiler"},
        stage_status={
            "reward_machine": "complete",
            "labeling": "complete" if labeling_source else "pending",
            "descriptions": "complete" if descriptions else "pending",
        },
        rm_mode="compiler",
    )
    return ArtifactBundle(manifest, machine, labeling_source, descriptions)


def pair_state_descriptions(
    result: CompilationResult,
    descriptions: Sequence[str],
) -> dict[str, str]:
    """Pair ordered compiler node descriptions with the shared u-state identities."""
    if not descriptions:
        return {}
    machine = compiler_machine_to_paper(result.reward_machine, result.environment.proposition_ids)
    return dict(zip(machine.states, descriptions, strict=True))


def build_compiler_bundle(
    result: CompilationResult,
    *,
    api_description: str,
    labeling_source: str = "",
    state_descriptions: Mapping[str, str] | None = None,
    attempts: Sequence[StageAttempt] = (),
) -> ArtifactBundle:
    """Finalize one compiler bundle with its artifacts, attempts, and API provenance."""
    bundle = adapt_compilation_result(
        result,
        labeling_source=labeling_source,
        state_descriptions=state_descriptions,
    )
    _finish_compiler_bundle(bundle, result, attempts, api_description)
    return bundle


def record_bundle_role_models(bundle: ArtifactBundle, CONFIG: Configuration) -> None:
    """Record the resolved compiler role models on one bundle manifest."""
    bundle.manifest.effective_settings.update(
        {
            "generator_model": CONFIG.generator_model,
            "critic_model": CONFIG.critic_model
            if (CONFIG.task_critic or CONFIG.rm_critic)
            else None,
        }
    )


def record_bundle_embeddings(
    bundle: ArtifactBundle,
    result: CompilationResult,
    artifact_path: str | Path | None = None,
) -> None:
    """Record accepted server embeddings and their resolved settings on one bundle.

    Only called on paths that reuse the accepted descriptions, so the vectors keep
    their node identity. The artifact path is optional because the final destination
    belongs to the writing script, not to the shared bundle builder.
    """
    if not result.embeddings:
        return
    settings = dict(result.embedding_settings)
    if artifact_path is not None:
        settings["artifact_path"] = str(artifact_path)
    bundle.embeddings = dict(result.embeddings)
    bundle.manifest.effective_settings["embedding"] = settings
    bundle.manifest.stage_status["embeddings"] = "complete"


def generate_compiler_bundle(
    results: Sequence[CompilationResult],
    engine: object | None,
    CONFIG: Configuration,
    *,
    api_description: str = DEFAULT_API_DESCRIPTION,
) -> tuple[ArtifactBundle, ...]:
    """Adapt accepted compiler results; compiler invocation belongs to scripts.

    Accepted labeling and node descriptions are reused in memory. ``engine`` is only
    needed when those fields are missing and must be regenerated; a failed regeneration
    persists its inspectable bundle to ``CONFIG.bundle`` before it raises.
    """
    if not results:
        raise RuntimeError("Compiler generation returned no accepted in-memory result")
    return tuple(_compiler_bundle(result, engine, CONFIG, api_description) for result in results)


def _compiler_bundle(
    result: CompilationResult,
    engine: object | None,
    CONFIG: Configuration,
    api_description: str,
) -> ArtifactBundle:
    descriptions = pair_state_descriptions(result, result.state_descriptions)
    if result.labeling_source and descriptions:
        bundle = build_compiler_bundle(
            result,
            api_description=api_description,
            labeling_source=result.labeling_source,
            state_descriptions=descriptions,
            attempts=[StageAttempt(**item) for item in result.labeling_attempts],
        )
        record_bundle_embeddings(bundle, result)
        return bundle

    if engine is None:
        raise RuntimeError(
            "Compiler bundle reuse requires accepted labeling and state descriptions; "
            "no engine was supplied to regenerate them"
        )
    run = _Generation.for_compiler_result(result, engine, api_description)
    try:
        run.generate_labeling()
        run.generate_descriptions()
    except Exception as error:
        bundle = _bundle_from_run(result, run, api_description)
        bundle.manifest.errors.append(str(error))
        _persist_failure(bundle, CONFIG)
        raise
    return _bundle_from_run(result, run, api_description)


def _bundle_from_run(
    result: CompilationResult, run: _Generation, api_description: str
) -> ArtifactBundle:
    return build_compiler_bundle(
        result,
        api_description=api_description,
        labeling_source=run.labeling_source,
        state_descriptions=run.descriptions,
        attempts=run.attempts,
    )


def _finish_compiler_bundle(
    bundle: ArtifactBundle,
    result: CompilationResult,
    attempts: Sequence[StageAttempt],
    api_description: str,
) -> None:
    compiler_attempt = {
        "stage": "compiler",
        "attempt": 1,
        "status": "accepted",
        "candidate": result.text,
        "feedback": "",
        "error": "",
    }
    bundle.manifest.generation["labeling_api"] = api_description
    recorded_stages = {item.stage for item in attempts} or {"labeling", "descriptions"}
    bundle.manifest.generation.update(_attempt_metadata(attempts, recorded_stages))
    bundle.manifest.api_definitions["labeling"] = api_description
    bundle.attempts = [compiler_attempt] + [item.__dict__ for item in attempts]
    bundle.raw_responses = [
        {
            "stage": "compiler",
            "attempt": 1,
            "candidate": result.text,
            "feedback": "",
            "error": "",
            "raw_response": result.text,
        }
    ] + [_raw_response(item) for item in attempts]
    bundle.manifest.stage_status.update(
        {
            "reward_machine": "complete",
            "labeling": _stage_status(attempts, "labeling", bundle.labeling_source),
            "descriptions": _stage_status(attempts, "descriptions", bundle.state_descriptions),
        }
    )
    bundle.manifest.errors = [item.error for item in attempts if item.error]


# ======================================================================================
#                                   LABELING GENERATION
# ======================================================================================


def generate_compiler_labeling(
    task: str,
    compiled: CompilationResult,
    engine: object,
    critic_engine: object | None,
    api_description: str,
) -> tuple[str, list[StageAttempt]]:
    """Generate labeling source for one accepted compiler result, with every attempt.

    Generation uses the compiler prompts on ``engine`` with the grounded artifact context;
    ``critic_engine``'s structured reviewer judges each candidate, or ``None`` skips the
    review. AST validation always runs. Raises :class:`LabelingError` when no candidate is
    accepted.
    """
    attempts: list[StageAttempt] = []
    context = {
        "clauses_json": clauses_json(compiled),
        "state_descriptions_json": descriptions_json(compiled),
        "nodes_json": json.dumps(list(state_identifiers(compiled).values())),
        "propositions_json": json.dumps(
            {item.identifier: item.description for item in compiled.environment.propositions},
            indent=2,
            sort_keys=True,
        ),
    }

    def request(history: str) -> str:
        return _compiler_request(
            engine,
            "labeling_generator",
            environment_markdown=compiled.environment.markdown,
            task=task,
            reward_machine=compiled.text,
            api=api_description,
            history=history,
            **context,
        )

    def review(source: str) -> tuple[bool, str, str]:
        if critic_engine is None:
            return True, "", ""
        verdict = critic_engine.review_labeling(
            task=task,
            candidate_rm=compiled.text,
            api=api_description,
            labeling=source,
            **context,
        )
        return verdict.accepted, verdict.feedback, ""

    propositions = tuple(compiled.environment.proposition_ids)
    return _refine_labeling(propositions, request, review, attempts), attempts


def _refine_labeling(
    propositions: Sequence[str],
    request: Callable[[str], str],
    review: Callable[[str], tuple[bool, str, str]],
    attempts: list[StageAttempt],
) -> str:
    """Run the bounded generate, validate and review loop shared by both generation modes."""
    labeling_source = ""
    history: list[str] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            candidate = request("\n\n".join(history))
            labeling_source = _extract_code(candidate)
            load_labeling_functions(labeling_source, propositions)
            accepted, feedback, raw_response = review(labeling_source)
            attempts.append(
                StageAttempt(
                    "labeling",
                    attempt,
                    "accepted" if accepted else "rejected",
                    labeling_source,
                    feedback,
                    "",
                    raw_response,
                )
            )
            if accepted:
                return labeling_source
            history.append(feedback)
        except Exception as error:
            attempts.append(
                StageAttempt("labeling", attempt, "failed", labeling_source, error=str(error))
            )
            history.append(str(error))
    raise LabelingError(attempts)


# ======================================================================================
#                                  COMPILER CONTEXT FOR PROMPTS
# ======================================================================================


def state_identifiers(compiled: CompilationResult) -> dict[int, str]:
    """Map each numeric compiler state to its shared ARM-FM identity."""
    machine = compiler_machine_to_paper(
        compiled.reward_machine, compiled.environment.proposition_ids
    )
    return dict(zip(compiled.reward_machine.states, machine.states, strict=True))


def clauses_json(compiled: CompilationResult) -> str:
    """Serialize validated clauses for the tagging and labeling prompts."""
    return json.dumps(
        [
            {
                "normalized_clause": clause.normalized_clause,
                "pattern": clause.pattern,
                "propositions": list(clause.propositions),
                "priority": clause.priority.value,
            }
            for clause in compiled.proposal.clauses
        ],
        indent=2,
        sort_keys=True,
    )


def rejecting_states_json(compiled: CompilationResult) -> str:
    """Serialize the compiler's rejecting states as shared node identities."""
    identifiers = state_identifiers(compiled)
    return json.dumps([identifiers[state] for state in compiled.reward_machine.rejecting_states])


def descriptions_json(compiled: CompilationResult) -> str:
    """Pair one candidate's descriptions with the shared node identities."""
    # Keep the adapter's node order (u0, u1, ... u10), which the reviewer prompt
    # promises as a node-ordered mapping; sorting keys would put u10 before u2.
    return json.dumps(
        pair_state_descriptions(compiled, compiled.state_descriptions),
        indent=2,
    )


# ======================================================================================
#                                      PROMPT PLUMBING
# ======================================================================================


def _request_text(engine: object, role: str, **values: str) -> str:
    request = getattr(engine, "request_text", None)
    if request is None:
        raise RuntimeError("ARM-FM generation requires an engine with request_text")
    return str(request(read_prompt("arm_fm", role), render_prompt("arm_fm", role, **values)))


def _compiler_request(engine: object, role: str, **values: str) -> str:
    """Render one compiler labeling prompt through the engine's text request path."""
    request = getattr(engine, "request_text", None)
    if request is None:
        raise RuntimeError("Compiler labeling generation requires an engine with request_text")
    return str(request(read_prompt("compiler", role), render_prompt("compiler", role, **values)))


def _critic(engine: object, role: str, **values: str) -> tuple[bool, str, str]:
    request = getattr(engine, "request_text", None)
    if request is None:
        raise RuntimeError("ARM-FM critic requires an engine with request_text")
    response = str(request(read_prompt("arm_fm", role), render_prompt("arm_fm", role, **values)))
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
    match = re.search(
        r"```(?:plaintext|text|json)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL
    )
    return (match.group(1) if match else text).strip()


def _extract_code(text: str) -> str:
    match = re.search(r"```python\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    return (match.group(1) if match else _extract_artifact(text)).strip() + "\n"


def _parse_descriptions(text: str, states: Sequence[str]) -> dict[str, str]:
    parsed = json.loads(_extract_artifact(text))
    if not isinstance(parsed, dict) or set(parsed) != set(states):
        raise ValueError("State descriptions must contain exactly all RM states")
    if any(not isinstance(value, str) or not value.strip() for value in parsed.values()):
        raise ValueError("State descriptions must be nonempty strings")
    return {state: parsed[state].strip() for state in states}


def _stage_status(attempts: Sequence[StageAttempt], stage: str, artifact: object) -> str:
    """Return one stage's status; failures never report complete."""
    stage_attempts = [item for item in attempts if item.stage == stage]
    if artifact and (
        not stage_attempts or any(item.status == "accepted" for item in stage_attempts)
    ):
        return "complete"
    if any(item.status in {"failed", "rejected"} for item in stage_attempts):
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
        "attempt_classification": "first_attempt"
        if first_attempt
        else "refined"
        if refined
        else "incomplete",
    }
