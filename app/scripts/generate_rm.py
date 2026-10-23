"""Generate one Reward Machine per critic-validated natural-language task."""

from collections.abc import Sequence
from dataclasses import asdict, replace
from pathlib import Path

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
    clauses_json,
    generate_compiler_labeling,
    pair_state_descriptions,
    state_identifiers,
)
from src.compiler import (
    CompilationResult,
    Proposal,
    build_compilation_result,
    compile_dfas,
    materialize_proposal,
)
from src.config import Configuration
from src.engines import (
    ImmediateEngineError,
    ProposalSelection,
    ProposalValidationError,
    RetryableEngineError,
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
) -> bool:
    """Propose, review, compile, and write one RM per task.

    Returns True when every task was accepted and written, and False after an expected
    generation failure, which is also delivered through ``hooks.failure``. Unexpected errors
    raise.
    """
    hooks = attach_step_trace(CONFIG, hooks or GenerationHooks())
    progress = Progress(hooks, CONFIG.LOGS_PATH)
    try:
        if progress.log_path is not None:
            hooks.notify_run_started(progress.log_path)
            progress(f"Run log: {progress.log_path}")
        progress(f"Recurrent soft penalty: {'on' if CONFIG.recurrent_soft_penalty else 'off'}")

        _run_pipeline(CONFIG, hooks, progress, write_outputs=write_outputs)
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
) -> None:
    """Run every task through its bounded proposal attempts, then write the outputs."""
    output_paths = prepare_outputs(CONFIG, progress)
    if write_outputs:
        preflight_paths(output_paths, overwrite=CONFIG.overwrite, kind="Output file(s)")
    pipeline = _Pipeline(CONFIG, progress)
    results = tuple(pipeline.run_task(index, task) for index, task in enumerate(CONFIG.tasks))

    if write_outputs:
        progress("Writing Reward Machine outputs.")
        results = write_run_outputs(results, output_paths, CONFIG, progress)
        progress("Writing outputs complete.")
    hooks.notify_completion(results, output_paths)

    progress("Generation completed successfully.")


class _RerunError(Exception):
    """One attempt failed on a provider or content error; the same attempt runs again."""


class _Pipeline:
    """The stages of one run: settings, engines and progress shared by every task attempt."""

    def __init__(self, CONFIG: Configuration, progress: Progress) -> None:
        self.CONFIG = CONFIG
        self.progress = progress
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

        Only a critic rejection uses up an attempt; a provider or content failure reruns the
        same attempt (see ``_run_attempt``).
        """
        attempts = self.CONFIG.attempts
        history: list[dict[str, object]] = []
        for attempt in range(1, attempts + 1):
            self.progress.begin_attempt(task_index, attempt, attempts)
            compiled = self._run_attempt(task_index, task, history)
            if compiled is not None:
                self.progress(f"Task {task_index + 1}: attempt {attempt}/{attempts} accepted.")
                return compiled

        last_failure = history[-1]
        raise RetryableEngineError(
            f"Task {task_index + 1} was not accepted within {attempts} attempts. "
            f"Last {last_failure['source']} feedback: {last_failure['feedback']}"
        )

    def _run_attempt(
        self, task_index: int, task: str, history: list[dict[str, object]]
    ) -> CompilationResult | None:
        """Rerun one attempt until the critic answers; ``None`` means it rejected the candidate.

        This is the safety fuse: after ``UNCOUNTED_RETRIES`` reruns the run fails with the last
        error, the only way out besides the critic's verdict.
        """
        reruns = self.CONFIG.UNCOUNTED_RETRIES
        for _ in range(reruns + 1):
            self.progress.check_cancelled()
            try:
                return self._attempt(task, history)
            except _RerunError as failure:
                last_error = failure
        raise RetryableEngineError(
            f"Task {task_index + 1} attempt {self.progress.current_attempt}/"
            f"{self.progress.attempt_limit} failed {reruns} reruns in a row. Last error: {last_error}"
        )

    def _attempt(self, task: str, history: list[dict[str, object]]) -> CompilationResult | None:
        """Run every stage once; ``None`` means the critic rejected the candidate.

        Raises:
            _RerunError: A provider or content failure; the attempt number is kept.
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

        except (RetryableEngineError, ValueError) as error:
            record_attempt_failure(self.progress, history, proposal_text, compiled, error)
            raise _RerunError(str(error)) from error
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
            self.environment, proposal, dfas, self.CONFIG.recurrent_soft_penalty
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

        facts = _tagger_facts(compiled)
        nodes = tuple(state_identifiers(compiled).values())
        attempts = Configuration.TAGGING_ATTEMPTS

        last_error: Exception | None = None
        for tagging_attempt in range(1, attempts + 1):
            try:
                descriptions = self.generator_engine.describe_states(
                    task, facts["Clauses"], facts["Reward Machine"], nodes
                )
            except (RetryableEngineError, ProposalValidationError) as error:
                last_error = error
                self.progress.warn(
                    f"state tagging request {tagging_attempt}/{attempts} failed: {error}"
                )
                continue

            self.progress.artifact(
                "State descriptions",
                dict(zip(nodes, descriptions, strict=True)),
            )
            self.progress.complete()
            return replace(compiled, state_descriptions=descriptions)

        raise ImmediateEngineError(
            f"State-description tagging failed after {attempts} requests: {last_error}"
        )

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

        critic = self.critic_engine.review_candidate(
            task, clauses_json(compiled.proposal.clauses), compiled.text, compiled.warnings
        )

        self.progress.artifact(
            "Critic verdict",
            {"accepted": critic.accepted, "feedback": critic.feedback},
        )
        if critic.accepted:
            self.progress.complete(StepState.COMPLETED)
        else:
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
