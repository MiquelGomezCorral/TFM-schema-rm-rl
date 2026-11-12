"""Baseline ARM-FM generation and compiler-only RM substitution."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.compiler import (
    ClauseProposal,
    CompilationResult,
    PaperRewardMachine,
    RewardSwitches,
    compiler_machine_to_paper,
    parse_paper_reward_machine,
    serialize_paper_reward_machine,
)
from src.config import Configuration
from src.engines import (
    CriticUnavailableError,
    CriticValidationError,
    ImmediateEngineError,
    ProposalSelection,
    RetryableEngineError,
    retry_critic,
)
from src.models import EnvironmentDescription
from src.prompts import read_prompt, render_prompt

from .artifacts import ArtifactBundle, BundleManifest
from .runtime import load_labeling_functions

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


class LabelingError(RuntimeError):
    """No labeling candidate was accepted; ``attempts`` holds every try."""

    def __init__(self, attempts: list[StageAttempt]) -> None:
        super().__init__("Labeling generation was not accepted within three attempts")
        self.attempts = attempts


# ======================================================================================
#                                   BASELINE GENERATION
# ======================================================================================


def arm_fm_role_models(CONFIG: Configuration) -> tuple[str | None, str | None]:
    """Return the generator and critic model of the ``arm-fm`` path.

    One model serves every role, as in the reproduction, unless ``arm_fm_critic`` asks for
    the provider's generator and critic models.
    """
    if not CONFIG.arm_fm_critic:
        return CONFIG.model, CONFIG.model
    if not CONFIG.critic_model:
        raise ValueError(
            "--arm-fm-critic needs a critic model; set the provider's critic model variable"
        )
    return CONFIG.generator_model, CONFIG.critic_model


def generate_baseline_bundle(
    task: str,
    environment: EnvironmentDescription,
    engine: object,
    CONFIG: Configuration,
    critic_engine: object | None = None,
) -> GenerationResult:
    """Generate RM, labeling code, and state descriptions with bounded refinement.

    ``critic_engine`` serves the critic calls; without it ``engine`` serves every role.
    Every bundle carries the stamp of its run. A failed run persists its inspectable bundle
    to ``CONFIG.bundle`` before it raises.
    """
    run = _Generation(task, environment, engine, critic_engine, rm_attempts=CONFIG.attempts)
    started = time.monotonic()
    try:
        run.generate_reward_machine()
        run.require_accepted_reward_machine()
        run.generate_labeling()
        run.generate_descriptions()
    except Exception:
        _persist_failure(_stamped_bundle(run, CONFIG, started), CONFIG)
        raise

    bundle = _stamped_bundle(run, CONFIG, started)
    bundle.validate()
    return GenerationResult(bundle=bundle, attempts=run.attempts)


def _stamped_bundle(run: _Generation, CONFIG: Configuration, started: float) -> ArtifactBundle:
    """Return the run's bundle with its stamp, counted from the attempts made so far."""
    bundle = run.bundle()
    stats = {
        **rm_stage_counts(bundle.attempts),
        "wall_time_s": round(time.monotonic() - started, 1),
    }
    record_bundle_stamp(bundle, CONFIG, arm_fm_role_models(CONFIG), stats)
    return bundle


class _Generation:
    """One generation run: the accepted artifacts so far and every attempt that produced them.

    ``rm_attempts`` bounds the reward-machine stage only; labeling and descriptions keep
    ``MAX_ATTEMPTS``.
    """

    def __init__(
        self,
        task: str,
        environment: EnvironmentDescription,
        engine: object,
        critic_engine: object | None = None,
        rm_attempts: int = MAX_ATTEMPTS,
    ) -> None:
        self.task = task
        self.environment = environment
        self.engine = engine
        self.critic_engine = engine if critic_engine is None else critic_engine
        self.rm_attempts = rm_attempts
        self.labeling_api = environment.require_labeling_api()
        self.attempts: list[StageAttempt] = []
        self.machine: PaperRewardMachine | None = None
        self.machine_text = ""
        self.labeling_source = ""
        self.descriptions: dict[str, str] = {}

    @classmethod
    def for_compiler_result(cls, result: CompilationResult, engine: object) -> _Generation:
        """Start from an accepted compiler machine whose labeling or descriptions are missing."""
        run = cls(result.proposal.task, result.environment, engine)
        run.machine = compiler_machine_to_paper(
            result.reward_machine, result.environment.proposition_ids
        )
        run.machine_text = serialize_paper_reward_machine(run.machine)
        run.labeling_source = result.labeling_source
        run.descriptions = pair_state_descriptions(result, result.state_descriptions)
        return run

    def generate_reward_machine(self) -> None:
        """Generate and refine one paper Reward Machine, keeping the last parseable candidate.

        Every round is an attempt: accepted, rejected by the critic or failed on its content, as
        in the compiler path. A provider outage (``RetryableEngineError``) runs the round again
        without using one; after ``Configuration.OUTAGE_RETRIES`` reruns in a row the run ends
        with that error. An ``ImmediateEngineError`` (authentication, bad request, or an exhausted
        critic, ``CriticUnavailableError``) ends the run at once, as in the compiler path; when the
        generator had already returned the round's candidate, it keeps its attempt as a failed
        round, and when the generator itself failed it uses none. ``self.attempts`` holds every
        round, also when an error leaves.
        """
        if not self.task.strip():
            raise ValueError("Task must be nonempty")
        rm_history: list[str] = []

        attempt, outages = 1, 0
        while attempt <= self.rm_attempts:
            generated = False  # the generator returned a candidate in this round
            try:
                candidate = _request_text(
                    self.engine,
                    "rm_generator",
                    environment=self.environment.markdown,
                    task=self.task,
                    api=self.labeling_api,
                    history="\n\n".join(rm_history),
                )
                generated = True
                self.machine_text = _extract_artifact(candidate)
                self.machine = parse_paper_reward_machine(
                    self.machine_text,
                    propositions=self.environment.proposition_ids,
                    require_final_states=True,
                )

                accepted, feedback, raw_response = _critic(
                    self.critic_engine,
                    "rm_critic",
                    environment=self.environment.markdown,
                    task=self.task,
                    candidate=self.machine_text,
                )

                self.attempts.append(
                    StageAttempt(
                        "reward_machine",
                        attempt,
                        "accepted" if accepted else "rejected",
                        self.machine_text,
                        feedback,
                        "",
                        raw_response,
                    )
                )

                if accepted:
                    break

                rm_history.append(feedback)

            except RetryableEngineError as error:
                outages += 1
                if outages > Configuration.OUTAGE_RETRIES:
                    raise RetryableEngineError(
                        f"Reward Machine attempt {attempt}/{self.rm_attempts} failed "
                        f"{Configuration.OUTAGE_RETRIES} reruns in a row. Last error: {error}"
                    ) from error
                continue
            except ImmediateEngineError as error:
                # A candidate that exists keeps its attempt, also when the critic fails for good
                # (exhausted repeats, authentication); the generator's own failure uses none.
                if generated:
                    self._record_failed_round(attempt, error)
                raise
            except Exception as error:
                self._record_failed_round(attempt, error)
                rm_history.append(str(error))
            attempt, outages = attempt + 1, 0

    def _record_failed_round(self, attempt: int, error: Exception) -> None:
        """Record the current candidate's round as failed with ``error``."""
        self.attempts.append(
            StageAttempt("reward_machine", attempt, "failed", self.machine_text, error=str(error))
        )

    def require_accepted_reward_machine(self) -> None:
        accepted = self.machine is not None and any(
            item.stage == "reward_machine" and item.status == "accepted" for item in self.attempts
        )
        if not accepted:
            raise RuntimeError(
                f"Reward Machine generation was not accepted within {self.rm_attempts} attempts"
            )

    def generate_labeling(self) -> None:
        self.labeling_source = _refine_labeling(
            self.environment.proposition_ids,
            lambda history: _request_text(
                self.engine,
                "labeling_generator",
                environment=self.environment.markdown,
                task=self.task,
                candidate=self.machine_text,
                api=self.labeling_api,
                history=history,
            ),
            lambda source: _critic(
                self.critic_engine,
                "labeling_critic",
                environment=self.environment.markdown,
                task=self.task,
                candidate=self.machine_text,
                labeling=source,
            ),
            self.attempts,
        )

    def generate_descriptions(self) -> None:
        self.descriptions = request_state_descriptions(
            self.engine, self.environment.markdown, self.task, self.machine, self.attempts
        )

    def bundle(self) -> ArtifactBundle:
        manifest = BundleManifest(
            task=self.task.strip(),
            environment=str(self.environment.source),
            proposition_semantics={
                item.identifier: item.description for item in self.environment.propositions
            },
            provenance={"status": "reconstructed", "generator": "arm-fm"},
            generation={
                "max_attempts": self.rm_attempts,
                "labeling_api": self.labeling_api,
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
            api_definitions={"labeling": self.labeling_api},
            errors=[item.error for item in self.attempts if item.error],
            effective_settings={
                "provider": getattr(self.engine, "provider_name", None),
                "model": getattr(self.engine, "model", None),
                "max_attempts": self.rm_attempts,
            },
            rm_mode="arm-fm",
        )
        return ArtifactBundle(
            manifest=manifest,
            reward_machine=self.machine,
            labeling_source=self.labeling_source,
            state_descriptions=dict(self.descriptions),
            attempts=[item.__dict__ for item in self.attempts],
            raw_responses=[_raw_response(item) for item in self.attempts]
            + call_records(self.engine, self.critic_engine),
        )


def request_state_descriptions(
    engine: object,
    environment_markdown: str,
    task: str,
    machine: PaperRewardMachine,
    attempts: list[StageAttempt],
) -> dict[str, str]:
    """Ask for one description per state of ``machine``; every try is appended to ``attempts``.

    Raises:
        RuntimeError: When no reply is accepted within ``MAX_ATTEMPTS`` tries.
    """
    candidate = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            candidate = _request_text(
                engine,
                "description_generator",
                environment=environment_markdown,
                task=task,
                candidate=serialize_paper_reward_machine(machine),
                states=", ".join(machine.states),
            )
            descriptions = _parse_descriptions(candidate, machine.states)
            attempts.append(StageAttempt("descriptions", attempt, "accepted", candidate))
            return descriptions
        except Exception as error:
            attempts.append(
                StageAttempt("descriptions", attempt, "failed", candidate, error=str(error))
            )
    raise RuntimeError("State-description generation was not accepted within three attempts")


def call_records(*engines: object) -> list[dict[str, str | None]]:
    """Return the request records of ``engines``; an engine that serves two roles counts once."""
    return [dict(call) for log in _call_logs(engines) for call in log]


def clear_call_records(*engines: object) -> None:
    """Forget the request records of ``engines`` so the next task counts its own requests."""
    for log in _call_logs(engines):
        log.clear()


def _call_logs(engines: Sequence[object]) -> list[list[dict[str, str | None]]]:
    distinct = {id(engine): engine for engine in engines if engine is not None}.values()
    return [getattr(engine, "calls", []) for engine in distinct]


def _persist_failure(bundle: ArtifactBundle, CONFIG: Configuration) -> None:
    if CONFIG.bundle is not None:
        try:
            bundle.save(CONFIG.bundle, overwrite=CONFIG.overwrite)
        except OSError as error:
            # The failure that got us here is re-raised by the caller; this one must not hide it.
            # Plain stderr print: importing ``print_warning`` here is a circular import.
            print(f"warning: could not save the failed bundle: {error}", file=sys.stderr)


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
        validation={"structural": True},
        inputs={
            "task": result.proposal.task,
            "environment_markdown": getattr(result.environment, "markdown", ""),
        },
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
    _finish_compiler_bundle(bundle, result, attempts)
    return bundle


def record_bundle_role_models(
    bundle: ArtifactBundle,
    CONFIG: Configuration,
    run_stats: Mapping[str, Any] | None = None,
) -> None:
    """Record the compiler role models, the attempt limit, the critic verdict and the switches.

    ``max_attempts`` is the candidates the run allowed (``CONFIG.attempts``), the
    reward-machine limit that ``arm-fm`` bundles record under the same key.
    The critic verdict is whether a critic accepted the machine. A run without the critic
    records no critic validation: a recorded ``False`` would make
    ``validate(require_complete=True)`` reject the bundle for training. The switches are
    flat keys (``recurrent_soft_penalty`` and the five ``reward_*``), so ``ablate-rm`` can
    rebuild the machine with the settings it was made with.

    ``run_stats`` is the accepted run's record: its request records join ``raw_responses``
    and its counts go to the stamp. Without it the stamp counts are null.
    """
    run_stats = run_stats or {}
    if CONFIG.critic:
        bundle.manifest.validation["critic"] = True
    generator_model, critic_model = _compiler_role_models(CONFIG)
    bundle.manifest.effective_settings.update(
        {
            "generator_model": generator_model,
            "critic_model": critic_model,
            "max_attempts": CONFIG.attempts,
            **asdict(RewardSwitches.from_config(CONFIG)),
        }
    )
    bundle.raw_responses.extend(run_stats.get("calls", ()))
    record_bundle_stamp(bundle, CONFIG, (generator_model, critic_model), run_stats)


def record_compiler_failure(
    bundle: ArtifactBundle, CONFIG: Configuration, run_stats: Mapping[str, Any]
) -> None:
    """Give a failed compiler run's bundle the request records and the stamp of that run.

    ``run_stats`` is empty when the run failed before it made a request; the counts are null.
    The interventions and retries are null in any case: its labeling and description attempts
    are not in the failure bundle, so a number would be short.
    """
    bundle.raw_responses.extend(run_stats.get("calls", ()))
    bundle.manifest.effective_settings["max_attempts"] = CONFIG.attempts
    stats = {**run_stats, "critic_interventions": None, "retries": None}
    record_bundle_stamp(bundle, CONFIG, _compiler_role_models(CONFIG), stats)


def _compiler_role_models(CONFIG: Configuration) -> tuple[str | None, str | None]:
    """Return the compiler path's generator model and critic model (none without a critic)."""
    return CONFIG.generator_model, CONFIG.critic_model if CONFIG.critic else None


def rm_stage_counts(attempts: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """Count the ``arm-fm`` path's reward-machine attempts, critic rejections and failures.

    Every loop round is an attempt there, so a failed round counts as an attempt and a retry
    (the ``farm`` path counts provider reruns as retries; see ``record_bundle_stamp``). A
    provider outage reruns its round and leaves no record.
    """
    rm_attempts = [item for item in attempts if item["stage"] == "reward_machine"]
    return {
        "attempts": len(rm_attempts),
        "critic_interventions": sum(item["status"] == "rejected" for item in rm_attempts),
        "retries": sum(item["status"] == "failed" for item in rm_attempts),
    }


def record_bundle_stamp(
    bundle: ArtifactBundle,
    CONFIG: Configuration,
    models: tuple[str | None, str | None],
    run_stats: Mapping[str, Any],
) -> None:
    """Write ``provenance["stamp"]``: the code, models and effort behind one bundle.

    ``run_stats`` holds the reward-machine stage's ``attempts``, ``critic_interventions`` and
    ``retries`` and the run's ``wall_time_s``. The labeling and description attempts in
    ``bundle.attempts`` add to the last two. A count the run did not report is null, never
    estimated. Both arms count an attempt for every new candidate (accepted, rejected by the
    critic or invalid); their retries differ: ``farm`` retries are reruns after provider
    outages and failed tagging requests, ``arm-fm`` retries the rounds that failed on their
    content.

    ``dirty`` is whether any file under ``app/`` differs from the commit, untracked files
    included, so bundles written under ``outputs/`` or ``experiments/`` do not taint it. A git
    command that fails leaves ``commit`` or ``dirty`` null, and ``provisional`` true.

    shortcut: the frozen commit is not recorded anywhere yet, so ``provisional`` is false for
    a clean ``main``; compare the commit once the user freezes one.
    """
    commit = _git("rev-parse", "HEAD")
    changes = _git("status", "--porcelain", "--", "app")
    dirty = None if changes is None else bool(changes)
    on_main = _git("rev-parse", "--abbrev-ref", "HEAD") == "main"
    counts = {key: run_stats.get(key) for key in ("attempts", "critic_interventions", "retries")}
    if None not in counts.values():
        later = [item for item in bundle.attempts if item["stage"] in {"labeling", "descriptions"}]
        counts["critic_interventions"] += sum(item["status"] == "rejected" for item in later)
        counts["retries"] += sum(item["status"] == "failed" for item in later)
    bundle.manifest.provenance["stamp"] = {
        "commit": commit,
        "dirty": dirty,
        "generator_model": models[0],
        "critic_model": models[1],
        "reasoning": CONFIG.reasoning,
        **counts,
        "wall_time_s": run_stats.get("wall_time_s"),
        "provisional": not (commit and dirty is False and on_main),
    }


def _git(*arguments: str) -> str | None:
    """Return the output of one git command in this repository, or None when it fails."""
    git = shutil.which("git")
    if git is None:
        return None
    completed = subprocess.run(  # noqa: S603  approved: fixed git argv, no shell
        [git, *arguments],
        capture_output=True,
        text=True,
        check=False,
        cwd=Configuration.WORKSPACE_PATH,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


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
) -> tuple[ArtifactBundle, ...]:
    """Adapt accepted compiler results; compiler invocation belongs to scripts.

    Accepted labeling and node descriptions are reused in memory. ``engine`` is only
    needed when those fields are missing and must be regenerated; a failed regeneration
    persists its inspectable bundle to ``CONFIG.bundle`` before it raises.
    """
    if not results:
        raise RuntimeError("Compiler generation returned no accepted in-memory result")
    return tuple(_compiler_bundle(result, engine, CONFIG) for result in results)


def _compiler_bundle(
    result: CompilationResult, engine: object | None, CONFIG: Configuration
) -> ArtifactBundle:
    descriptions = pair_state_descriptions(result, result.state_descriptions)
    if result.labeling_source and descriptions:
        bundle = build_compiler_bundle(
            result,
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
    run = _Generation.for_compiler_result(result, engine)
    try:
        run.generate_labeling()
        run.generate_descriptions()
    except Exception as error:
        bundle = _bundle_from_run(result, run)
        bundle.manifest.errors.append(str(error))
        _persist_failure(bundle, CONFIG)
        raise
    return _bundle_from_run(result, run)


def _bundle_from_run(result: CompilationResult, run: _Generation) -> ArtifactBundle:
    return build_compiler_bundle(
        result,
        labeling_source=run.labeling_source,
        state_descriptions=run.descriptions,
        attempts=run.attempts,
    )


def _finish_compiler_bundle(
    bundle: ArtifactBundle, result: CompilationResult, attempts: Sequence[StageAttempt]
) -> None:
    labeling_api = result.environment.require_labeling_api()
    compiler_attempt = {
        "stage": "compiler",
        "attempt": 1,
        "status": "accepted",
        "candidate": result.text,
        "feedback": "",
        "error": "",
    }
    bundle.manifest.generation["labeling_api"] = labeling_api
    # The compiled clause list, so `ablate-rm` can rebuild the machine without a model call;
    # `clause_texts` holds each clause's sentence, in the same order, for the description prompt.
    bundle.manifest.generation["clauses"] = [
        [clause.pattern, list(clause.propositions), clause.priority.value]
        for clause in result.proposal.clauses
    ]
    bundle.manifest.generation["clause_texts"] = [
        clause.normalized_clause for clause in result.proposal.clauses
    ]
    recorded_stages = {item.stage for item in attempts} or {"labeling", "descriptions"}
    bundle.manifest.generation.update(_attempt_metadata(attempts, recorded_stages))
    bundle.manifest.api_definitions["labeling"] = labeling_api
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
) -> tuple[str, list[StageAttempt]]:
    """Generate labeling source for one accepted compiler result, with every attempt.

    Generation uses the compiler prompts on ``engine`` with the grounded artifact context;
    ``critic_engine``'s structured reviewer judges each candidate, or ``None`` skips the
    review. AST validation always runs. Raises :class:`LabelingError` when no candidate is
    accepted.
    """
    labeling_api = compiled.environment.require_labeling_api()
    attempts: list[StageAttempt] = []
    context = {
        "clauses_json": clauses_json(compiled.proposal.clauses),
        "state_descriptions_json": descriptions_json(compiled),
        "nodes_json": json.dumps(list(state_identifiers(compiled).values())),
        "propositions_json": json.dumps(
            {item.identifier: item.description for item in compiled.environment.propositions},
            indent=2,
            sort_keys=True,
        ),
    }

    def request(history: str) -> str:
        return _request_text(
            engine,
            "labeling_generator",
            family="compiler",
            environment_markdown=compiled.environment.markdown,
            task=task,
            reward_machine=compiled.text,
            api=labeling_api,
            history=history,
            **context,
        )

    def review(source: str) -> tuple[bool, str, str]:
        if critic_engine is None:
            return True, "", ""
        verdict = retry_critic(
            lambda: critic_engine.review_labeling(
                task=task,
                candidate_rm=compiled.text,
                api=labeling_api,
                labeling=source,
                **context,
            ),
            getattr(critic_engine, "warn", None),
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
            labeling_source = extract_labeling_code(candidate)
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
        except CriticUnavailableError:
            raise  # the critic never answered about this candidate: no new candidate
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


def clauses_json(clauses: Iterable[ClauseProposal | ProposalSelection]) -> str:
    """Serialize clauses, as proposed or as compiled, for logs, history and prompts."""
    return json.dumps(
        [
            {
                "normalized_clause": clause.normalized_clause,
                "pattern": clause.pattern,
                "propositions": list(clause.propositions),
                "priority": clause.priority.value,
            }
            for clause in clauses
        ],
        indent=2,
        sort_keys=True,
    )


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


def _request_text(engine: object, role: str, family: str = "arm_fm", **values: str) -> str:
    """Render one prompt of ``family`` and send it through the engine's text request path."""
    request = getattr(engine, "request_text", None)
    if request is None:
        raise RuntimeError("Prompted generation requires an engine with request_text")
    return str(
        request(read_prompt(family, role), render_prompt(family, role, **values), stage=role)
    )


def review_reward_machine(
    engine: object, environment: str, task: str, candidate: str
) -> tuple[bool, str]:
    """Ask the ARM-FM reward-machine critic about one machine: accepted and feedback."""
    accepted, feedback, _reply = _critic(
        engine, "rm_critic", environment=environment, task=task, candidate=candidate
    )
    return accepted, feedback


def _critic(engine: object, role: str, **values: str) -> tuple[bool, str, str]:
    """Ask the critic about one candidate, repeating the request while it fails or is malformed."""
    return retry_critic(lambda: _ask_critic(engine, role, **values), getattr(engine, "warn", None))


def _ask_critic(engine: object, role: str, **values: str) -> tuple[bool, str, str]:
    response = _request_text(engine, role, **values)
    try:
        parsed = json.loads(_extract_artifact(response))
    except json.JSONDecodeError as error:
        raise CriticValidationError("ARM-FM critic returned invalid JSON") from error
    if not isinstance(parsed, dict) or not isinstance(parsed.get("accepted"), bool):
        raise CriticValidationError("ARM-FM critic must return boolean accepted")
    feedback = parsed.get("feedback")
    if not isinstance(feedback, str) or not feedback.strip():
        raise CriticValidationError("ARM-FM critic feedback must be nonempty")
    return parsed["accepted"], feedback.strip(), response


def _extract_artifact(text: str) -> str:
    match = re.search(
        r"```(?:plaintext|text|json)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL
    )
    return (match.group(1) if match else text).strip()


def extract_labeling_code(text: str) -> str:
    """The Python source in a model reply: its first ```python block, else the whole reply."""
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
