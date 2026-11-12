"""Generate one Reward Machine per critic-validated natural-language task."""

import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from src.arm_fm.evaluation import (
    SERVER_EMBEDDING_EXTRACTION,
    EmbeddingCache,
    EmbeddingSettings,
    effective_embedding_text,
    embed_descriptions_over_http,
)
from src.arm_fm.generation import (
    MAX_ATTEMPTS,
    LabelingError,
    call_records,
    clauses_json,
    clear_call_records,
    generate_compiler_labeling,
    pair_state_descriptions,
    state_identifiers,
)
from src.compiler import (
    CompilationResult,
    Proposal,
    RewardSwitches,
    build_compilation_result,
    compile_dfas,
    materialize_proposal,
)
from src.config import Configuration
from src.engines import (
    GenericEngine,
    ImmediateEngineError,
    ProposalSelection,
    ProposalValidationError,
    RetryableEngineError,
    retry_critic,
)
from src.models import EnvironmentDescription
from src.utils import (
    GenerationHooks,
    PipelineStep,
    Progress,
    RunCancelled,
    StepState,
    append_history,
    attach_step_trace,
    preflight_paths,
    prepare_outputs,
    record_attempt_failure,
    setup_environment_and_engines,
    structure_history_text,
    write_run_outputs,
)

EMBEDDING_INSTRUCTION = (
    "Represent the task progress that one Reward Machine state stands for, so states "
    "with the same progress toward the task embed close together."
)


def generate_rm(
    CONFIG: Configuration,
    hooks: GenerationHooks | None = None,
    *,
    write_outputs: bool = True,
    run_stats: list[dict[str, Any]] | None = None,
) -> bool:
    """Propose, review, compile, and write one RM per task.

    Returns True when every task was accepted and written, and False after an expected
    generation failure, which is also delivered through ``hooks.failure``. Unexpected errors
    raise. ``run_stats``, when given, receives one entry per task that ran, accepted or failed
    (its provider request records, attempt counts and wall time), before any output is written.
    """
    hooks = attach_step_trace(CONFIG, hooks or GenerationHooks())
    progress = Progress(hooks, CONFIG.LOGS_PATH)
    try:
        if progress.log_path is not None:
            hooks.notify_run_started(progress.log_path)
            progress(f"Run log: {progress.log_path}")
        progress(f"Recurrent soft rules: {'on' if CONFIG.recurrent_soft_penalty else 'off'}")

        _run_pipeline(CONFIG, hooks, progress, write_outputs=write_outputs, run_stats=run_stats)
        return True

    except RunCancelled:
        progress.fail("Stopped by the user")
        return False
    except (
        ProposalValidationError,
        RetryableEngineError,
        ImmediateEngineError,
    ) as error:
        progress(f"Generation failed: {error}")
        hooks.notify_failure(str(error))
        return False
    except Exception as error:
        progress(f"Generation failed unexpectedly: {error}")
        raise
    finally:
        progress.close()


def _run_pipeline(
    CONFIG: Configuration,
    hooks: GenerationHooks,
    progress: Progress,
    *,
    write_outputs: bool = True,
    run_stats: list[dict[str, Any]] | None = None,
) -> None:
    """Run every task through its bounded proposal attempts, then write the outputs."""
    output_paths = prepare_outputs(CONFIG, progress)
    if write_outputs:
        preflight_paths(output_paths, overwrite=CONFIG.overwrite, kind="Output file(s)")
    pipeline = _Pipeline(CONFIG, progress)
    try:
        results = tuple(pipeline.run_task(index, task) for index, task in enumerate(CONFIG.tasks))
    finally:
        # A failed run reports its requests too; the caller needs them for the failure bundle.
        if run_stats is not None:
            run_stats.extend(pipeline.run_stats)

    if write_outputs:
        progress("Writing Reward Machine outputs.")
        results = write_run_outputs(results, output_paths, CONFIG, progress, pipeline.run_stats)
        progress("Writing outputs complete.")
    hooks.notify_completion(results, output_paths)

    progress("Generation completed successfully.")


class _ProviderOutageError(Exception):
    """One attempt failed on a provider error; the same attempt runs again."""


class _Pipeline:
    """The stages of one run: settings, engines and progress shared by every task attempt."""

    def __init__(self, CONFIG: Configuration, progress: Progress) -> None:
        self.CONFIG = CONFIG
        self.progress = progress
        self.reruns = 0  # provider outages rerun inside the current task
        self.rejections = 0  # critic rejections inside the current task
        self.generated = False  # the generator returned a candidate for the current attempt
        # One entry per task that ran: its request records, stage counts and wall time.
        self.run_stats: list[dict[str, Any]] = []
        self.environment, self.generator_engine, self.critic_engine = setup_environment_and_engines(
            CONFIG, progress
        )
        if CONFIG.labeling:
            # Only the labeling generator reads the code file; the clause generator and the
            # critic keep the facts alone.
            self.labeling_environment = EnvironmentDescription.from_file(
                CONFIG.environment, code=True
            )
            self.labeling_environment.require_labeling_api()

    def run_task(self, task_index: int, task: str) -> CompilationResult:
        """Return the accepted result for one task, or raise after the last critic rejection.

        Every new candidate uses up an attempt: a critic rejection and an invalid candidate
        (content failure) both do. A provider outage reruns the same attempt without using it up
        (see ``_run_attempt``). The task's run record joins ``run_stats`` whether it is accepted
        or fails, so a failed task's requests are still counted; its ``attempts`` are the ones
        whose candidate the generator returned, whatever a later stage did to it, so a provider
        that never answers leaves 0.
        """
        attempts = self.CONFIG.attempts
        history: list[dict[str, object]] = []
        engines = (self.generator_engine, self.critic_engine)
        clear_call_records(*engines)
        started = time.monotonic()
        self.reruns = self.rejections = 0
        counted = 0
        try:
            for attempt in range(1, attempts + 1):
                self.progress.begin_attempt(task_index, attempt, attempts)
                self.generated = False
                try:
                    compiled = self._run_attempt(task_index, task, history)
                finally:
                    counted += self.generated
                if compiled is not None:
                    self.progress(f"Task {task_index + 1}: attempt {attempt}/{attempts} accepted.")
                    return compiled

            last_failure = history[-1]
            raise RetryableEngineError(
                f"Task {task_index + 1} was not accepted within {attempts} attempts. "
                f"Last {last_failure['source']} feedback: {last_failure['feedback']}"
            )
        finally:
            self.run_stats.append(
                {
                    "calls": call_records(*engines),
                    "attempts": counted,
                    "critic_interventions": self.rejections,
                    "retries": self.reruns,
                    "wall_time_s": round(time.monotonic() - started, 1),
                }
            )

    def _run_attempt(
        self, task_index: int, task: str, history: list[dict[str, object]]
    ) -> CompilationResult | None:
        """Rerun one attempt through provider outages; ``None`` means the candidate was refused.

        A refused candidate is a critic rejection or an invalid candidate. After
        ``OUTAGE_RETRIES`` reruns in a row the run fails with the last provider error.
        """
        reruns = self.CONFIG.OUTAGE_RETRIES
        for tries in range(reruns + 1):
            self.progress.check_cancelled()
            try:
                return self._attempt(task, history)
            except _ProviderOutageError as failure:
                if tries < reruns:  # the last failure is followed by no rerun
                    self.reruns += 1
                last_error = failure
        raise RetryableEngineError(
            f"Task {task_index + 1} attempt {self.progress.current_attempt}/"
            f"{self.progress.attempt_limit} failed {reruns} reruns in a row. Last error: {last_error}"
        )

    def _attempt(self, task: str, history: list[dict[str, object]]) -> CompilationResult | None:
        """Run every stage once; ``None`` means the candidate was rejected or invalid.

        Raises:
            _ProviderOutageError: A provider error; the attempt number is kept.
        """
        proposal_text: str | None = None
        compiled: CompilationResult | None = None
        try:
            selections, proposal_text = self._generate_proposal(task, history)
            proposal = self._materialize_ltlf(task, selections)
            dfas = self._compile_dfa(proposal)
            compiled = self._build_reward_machine(proposal, dfas)
            if not self._review_candidate(task, proposal_text, compiled, history):
                return None

            compiled = self._describe_states(task, compiled)
            compiled = self._generate_labeling(task, compiled)
            return self._embed_states(compiled)

        except RetryableEngineError as error:
            record_attempt_failure(self.progress, history, proposal_text, compiled, error)
            raise _ProviderOutageError(str(error)) from error
        except ValueError as error:  # an invalid candidate uses up the attempt
            self.generated = True  # also a proposal the generator returned but could not use
            record_attempt_failure(self.progress, history, proposal_text, compiled, error)
            return None
        except ImmediateEngineError as error:
            self.progress.fail(str(error))
            raise
        except (FileNotFoundError, RuntimeError) as error:
            self.progress.fail(str(error))
            raise ImmediateEngineError(str(error)) from error

    # ==================================================================================
    #                                      STAGES
    # ==================================================================================

    def _generate_proposal(
        self, task: str, history: list[dict[str, object]]
    ) -> tuple[tuple[ProposalSelection, ...], str]:
        """Generate and log validated proposal selections."""
        self.progress.start(PipelineStep.GENERATE)

        history_text = structure_history_text(history)
        selections = self.generator_engine.propose_task(task, history=history_text)
        self.generated = True
        proposal_text = clauses_json(selections)

        self.progress.artifact("Validated proposal", proposal_text)
        self.progress.complete()

        return selections, proposal_text

    def _materialize_ltlf(self, task: str, selections: Sequence[ProposalSelection]) -> Proposal:
        self.progress.start(PipelineStep.LTLF)

        proposal = materialize_proposal(task, selections)

        self.progress.artifact(
            "LTLf clauses",
            [
                {
                    "normalized_clause": clause.normalized_clause,
                    "formula": clause.ltlf_formula,
                }
                for clause in proposal.clauses
            ],
        )
        self.progress.complete()
        return proposal

    def _compile_dfa(self, proposal: Proposal) -> tuple[dict, ...]:
        self.progress.start(PipelineStep.DFA)

        dfas = compile_dfas(proposal, self.CONFIG)

        self.progress.artifact("DFA data", dfas)
        self.progress.complete()
        return dfas

    def _build_reward_machine(self, proposal: Proposal, dfas: Sequence[dict]) -> CompilationResult:
        self.progress.start(PipelineStep.REWARD_MACHINE)

        compiled = build_compilation_result(
            self.environment, proposal, dfas, RewardSwitches.from_config(self.CONFIG)
        )

        self.progress.artifact("Serialized Reward Machine", compiled.text)
        for warning in compiled.warnings:
            self.progress.warn(warning)
        self.progress.complete()
        return compiled

    def _describe_states(self, task: str, compiled: CompilationResult) -> CompilationResult:
        """Tag every machine state, retrying malformed or transient responses locally."""
        if not self.CONFIG.state_descriptions:
            self.progress.stage_skip(PipelineStep.STATE_DESCRIPTIONS)
            return compiled
        self.progress.start(PipelineStep.STATE_DESCRIPTIONS)

        def count_failed_request(message: str) -> None:
            # `tag_states` warns once per failed request. The last one raises and a failed
            # run's retries are not stamped, so only the requests before a success matter.
            self.reruns += 1
            self.progress.warn(message)

        descriptions = tag_states(self.generator_engine, task, compiled, count_failed_request)
        nodes = tuple(state_identifiers(compiled).values())

        self.progress.artifact("State descriptions", dict(zip(nodes, descriptions, strict=True)))
        self.progress.complete()
        return replace(compiled, state_descriptions=descriptions)

    def _review_candidate(
        self,
        task: str,
        proposal_text: str,
        compiled: CompilationResult,
        history: list[dict[str, object]],
    ) -> bool:
        """Have the critic judge the clauses and the machine they compiled to."""
        if not self.CONFIG.critic:
            self.progress.stage_skip(PipelineStep.CRITIC)
            return True
        self.progress.start(PipelineStep.CRITIC)

        def request_verdict():
            self.progress.check_cancelled()
            return self.critic_engine.review_candidate(
                task, clauses_json(compiled.proposal.clauses), compiled.text, compiled.warnings
            )

        # A failed critic request is repeated on this candidate; it never restarts generation.
        critic = retry_critic(
            request_verdict, lambda message: self.progress.warn(f"Critic {message}")
        )

        self.progress.artifact(
            "Critic verdict",
            {"accepted": critic.accepted, "feedback": critic.feedback},
        )
        if critic.accepted:
            self.progress.complete(StepState.COMPLETED)
        else:
            self.rejections += 1
            self.progress.complete(StepState.FAILED, critic.feedback)
            append_history(history, proposal_text, compiled, PipelineStep.CRITIC, critic.feedback)

        return critic.accepted

    def _generate_labeling(self, task: str, compiled: CompilationResult) -> CompilationResult:
        """Generate labeling predicates for one accepted RM, retrying locally."""
        if not self.CONFIG.labeling:
            self.progress.stage_skip(PipelineStep.LABELING)
            return compiled
        self.progress.start(PipelineStep.LABELING)

        # The result keeps the text the labeling generator reads, so every bundle stores it.
        compiled = replace(compiled, environment=self.labeling_environment)
        try:
            source, attempts = generate_compiler_labeling(
                task, compiled, self.generator_engine, self.critic_engine
            )
        except LabelingError as error:
            last = error.attempts[-1] if error.attempts else None
            detail = (last.feedback or last.error) if last is not None else str(error)
            raise ImmediateEngineError(
                f"Labeling generation failed after {MAX_ATTEMPTS} requests: {detail or error}"
            ) from error

        self.progress.artifact("Labeling source", source)
        self.progress.complete()
        return replace(
            compiled,
            labeling_source=source,
            labeling_attempts=tuple(item.__dict__ for item in attempts),
        )

    def _embed_states(self, compiled: CompilationResult) -> CompilationResult:
        """Embed the accepted state descriptions through the configured local server."""
        CONFIG = self.CONFIG
        if not CONFIG.embeddings:
            self.progress.stage_skip(PipelineStep.EMBEDDINGS)
            return compiled
        self.progress.start(PipelineStep.EMBEDDINGS)

        descriptions = pair_state_descriptions(compiled, compiled.state_descriptions)
        if not descriptions:
            raise ImmediateEngineError("Embedding stage requires accepted state descriptions")
        # The vectors keep the facts the state tagger read, not the code file.
        context = (
            state_embedding_context(replace(compiled, environment=self.environment))
            if CONFIG.embedding_context
            else ""
        )
        settings = EmbeddingSettings(
            model=CONFIG.embedding_model,
            model_revision=CONFIG.embedding_revision,
            tokenizer_revision=CONFIG.embedding_revision,
            extraction=SERVER_EMBEDDING_EXTRACTION,
            normalize=True,
            device="remote",
        )
        cache = EmbeddingCache(Path(CONFIG.EMBEDDINGS_PATH) / "cache.json")
        try:
            vectors = embed_descriptions_over_http(
                descriptions, CONFIG, settings=settings, context=context, cache=cache
            )
        except (RuntimeError, ValueError, OSError) as error:
            raise ImmediateEngineError(f"Embedding stage failed: {error}") from error

        dimension = len(next(iter(vectors.values())))
        self.progress.artifact(
            "State embeddings",
            {
                "model": settings.model,
                "revision": settings.model_revision,
                "extraction": settings.extraction,
                "dimension": dimension,
                "context": context,
                "nodes": list(vectors),
            },
        )
        self.progress.complete()
        return replace(
            compiled,
            embeddings=vectors,
            embedding_settings={
                **asdict(settings),
                "dimension": dimension,
                "context": context,
                "endpoint": CONFIG.embedding_endpoint,
            },
            embedding_texts={
                node: effective_embedding_text(text, context) for node, text in descriptions.items()
            },
        )


# ============================================================================
#
#                                   HELPERS
#
# ============================================================================


def tag_states(
    engine: GenericEngine, task: str, compiled: CompilationResult, warn: Callable[[str], None]
) -> tuple[str, ...]:
    """Have the generator describe every state of one compiled machine, in node order.

    A malformed answer or a transient provider failure is asked again, at most
    ``Configuration.TAGGING_ATTEMPTS`` requests in all.

    Raises:
        ImmediateEngineError: Every request failed.
    """
    facts = _tagger_facts(compiled)
    nodes = tuple(state_identifiers(compiled).values())
    attempts = Configuration.TAGGING_ATTEMPTS

    last_error: Exception | None = None
    for tagging_attempt in range(1, attempts + 1):
        try:
            return engine.describe_states(task, facts["Clauses"], facts["Reward Machine"], nodes)
        except (RetryableEngineError, ProposalValidationError) as error:
            last_error = error
            warn(f"state tagging request {tagging_attempt}/{attempts} failed: {error}")

    raise ImmediateEngineError(
        f"State-description tagging failed after {attempts} requests: {last_error}"
    )


def state_embedding_context(compiled: CompilationResult) -> str:
    """Build the opt-in embedding context from the facts the state tagger read.

    The instruction line states what the vectors are for, so the model projects each node
    toward task progress instead of surface wording.
    """
    sections = [f"### {title}\n{text}" for title, text in _tagger_facts(compiled).items()]
    return "\n\n".join((EMBEDDING_INSTRUCTION, *sections, "### State"))


def _tagger_facts(compiled: CompilationResult) -> dict[str, str]:
    """The run facts the state tagger reads beside the node list."""
    return {
        "Environment": compiled.environment.markdown,
        "Task": compiled.proposal.task,
        "Clauses": clauses_json(compiled.proposal.clauses),
        "Reward Machine": compiled.text,
    }
