"""Generate one Reward Machine per critic-validated natural-language task."""

from collections.abc import Sequence
from dataclasses import asdict, replace
from pathlib import Path

from src.arm_fm.environments import minigrid_labeling_api
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
    descriptions_json,
    generate_compiler_labeling,
    pair_state_descriptions,
    rejecting_states_json,
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
from src.utils import (
    GenerationHooks,
    PipelineStep,
    Progress,
    StepState,
    append_history,
    attach_step_trace,
    preflight_paths,
    prepare_outputs,
    proposal_json,
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

        _run_pipeline(CONFIG, hooks, progress, write_outputs=write_outputs)
        return True

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
        results = write_run_outputs(results, output_paths, CONFIG, pipeline.labeling_api, progress)
        progress("Writing outputs complete.")
    hooks.notify_completion(results, output_paths)

    progress("Generation completed successfully.")


class _Pipeline:
    """The stages of one run: settings, engines and progress shared by every task attempt."""

    def __init__(self, CONFIG: Configuration, progress: Progress) -> None:
        self.CONFIG = CONFIG
        self.progress = progress
        self.environment, self.generator_engine, self.critic_engine = setup_environment_and_engines(
            CONFIG, progress
        )
        self.labeling_api = resolve_labeling_api(CONFIG) if CONFIG.labeling else ""

    def run_task(self, task_index: int, task: str) -> CompilationResult:
        """Return the accepted result for one task, or raise after its last failed attempt."""
        attempts = Configuration.PROPOSAL_ATTEMPTS
        history: list[dict[str, object]] = []
        for attempt in range(1, attempts + 1):
            self.progress.begin_attempt(task_index, attempt)
            compiled = self._attempt(task, history)
            if compiled is not None:
                self.progress(f"Task {task_index + 1}: attempt {attempt}/{attempts} accepted.")
                return compiled

        last_failure = history[-1]
        raise RetryableEngineError(
            f"Task {task_index + 1} was not accepted within {attempts} attempts. "
            f"Last {last_failure['source']} feedback: {last_failure['feedback']}"
        )

    def _attempt(self, task: str, history: list[dict[str, object]]) -> CompilationResult | None:
        """Run every stage once; ``None`` means a critic or a retryable failure rejected it."""
        proposal_text: str | None = None
        compiled: CompilationResult | None = None
        try:
            selections, proposal_text = self._generate_proposal(task, history)
            if not self._review_task(task, proposal_text, history):
                return None

            proposal = self._materialize_ltlf(task, selections)
            dfas = self._compile_dfa(proposal)
            compiled = self._build_reward_machine(proposal, dfas)
            compiled = self._describe_states(task, compiled)
            if not self._review_reward_machine(task, proposal_text, compiled, history):
                return None

            compiled = self._generate_labeling(task, compiled)
            return self._embed_states(compiled)

        except (RetryableEngineError, ValueError) as error:
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
        proposal_text = proposal_json(selections, task)

        self.progress.artifact("Validated proposal", proposal_text)
        self.progress.complete()

        return selections, proposal_text

    def _review_task(self, task: str, proposal_text: str, history: list[dict[str, object]]) -> bool:
        if not self.CONFIG.task_critic:
            self.progress.stage_skip(PipelineStep.TASK_CRITIC)
            return True
        self.progress.start(PipelineStep.TASK_CRITIC)

        critic = self.critic_engine.review_task(task, proposal_text)

        self.progress.artifact(
            "Task critic verdict",
            {"accepted": critic.accepted, "feedback": critic.feedback},
        )
        if critic.accepted:
            self.progress.complete(StepState.COMPLETED)
        else:
            self.progress.complete(StepState.FAILED, critic.feedback)
            append_history(history, proposal_text, None, PipelineStep.TASK_CRITIC, critic.feedback)

        return critic.accepted

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

        compiled = build_compilation_result(self.environment, proposal, dfas)

        self.progress.artifact("Serialized Reward Machine", compiled.text)
        self.progress.complete()
        return compiled

    def _describe_states(self, task: str, compiled: CompilationResult) -> CompilationResult:
        """Tag every machine state, retrying malformed or transient responses locally."""
        self.progress.start(PipelineStep.STATE_DESCRIPTIONS)

        facts = _tagger_facts(compiled)
        nodes = tuple(state_identifiers(compiled).values())
        attempts = Configuration.TAGGING_ATTEMPTS

        last_error: Exception | None = None
        for tagging_attempt in range(1, attempts + 1):
            try:
                descriptions = self.generator_engine.describe_states(
                    task,
                    facts["Clauses"],
                    facts["Reward Machine"],
                    facts["Rejecting states"],
                    nodes,
                )
            except RetryableEngineError as error:
                last_error = error
                self.progress(
                    f"Task {self.progress.current_task + 1}: state tagging attempt "
                    f"{tagging_attempt}/{attempts} failed — {error}"
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

    def _review_reward_machine(
        self,
        task: str,
        proposal_text: str,
        compiled: CompilationResult,
        history: list[dict[str, object]],
    ) -> bool:
        if not self.CONFIG.rm_critic:
            self.progress.stage_skip(PipelineStep.RM_CRITIC)
            return True
        self.progress.start(PipelineStep.RM_CRITIC)

        critic = self.critic_engine.review_reward_machine(
            task, compiled.text, descriptions_json(compiled)
        )

        self.progress.artifact(
            "Reward Machine critic verdict",
            {"accepted": critic.accepted, "feedback": critic.feedback},
        )
        if critic.accepted:
            self.progress.complete(StepState.COMPLETED)
        else:
            self.progress.complete(StepState.FAILED, critic.feedback)
            append_history(
                history,
                proposal_text,
                compiled,
                PipelineStep.RM_CRITIC,
                critic.feedback,
            )

        return critic.accepted

    def _generate_labeling(self, task: str, compiled: CompilationResult) -> CompilationResult:
        """Generate MiniGrid predicates for one accepted RM, retrying locally."""
        if not self.CONFIG.labeling:
            self.progress.stage_skip(PipelineStep.LABELING)
            return compiled
        self.progress.start(PipelineStep.LABELING)

        critic_engine = self.critic_engine if self.CONFIG.rm_critic else None
        try:
            source, attempts = generate_compiler_labeling(
                task, compiled, self.generator_engine, critic_engine, self.labeling_api
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
        context = state_embedding_context(compiled) if CONFIG.embedding_context else ""
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


def resolve_labeling_api(CONFIG: Configuration) -> str:
    """Resolve the MiniGrid labeling API, rejecting unrecognized explicit domains."""
    domain = (CONFIG.domain or "minigrid").strip().lower()
    families = ("minigrid", "babyai")
    recognized = any(
        domain == family or domain.startswith((f"{family}-", f"{family}_")) for family in families
    )
    if not recognized:
        raise ValueError(
            "Compiler labeling supports the MiniGrid and BabyAI domain families only, "
            f"got {CONFIG.domain!r}"
        )
    return minigrid_labeling_api()


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
        "Clauses": clauses_json(compiled),
        "Reward Machine": compiled.text,
        "Rejecting states": rejecting_states_json(compiled),
    }
