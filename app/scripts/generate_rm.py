"""Generate one Reward Machine per critic-validated natural-language task."""

from collections.abc import Sequence
from pathlib import Path

from src.compiler import (
    CompilationResult,
    Proposal,
    build_compilation_result,
    compile_dfas,
    materialize_proposal,
)
from src.config import Configuration
from src.engines import (
    GenericEngine,
    ImmediateEngineError,
    ProposalValidationError,
    RetryableEngineError,
    ProposalSelection
)
from src.models import EnvironmentDescription
from src.utils import (
    GenerationHooks,
    PipelineStep,
    Progress,
    StepState,
    record_attempt_failure,
    append_history,
    validate_configuration,
    proposal_json,
    structure_history_text,
    setup_environment_and_engine,
    derive_output_paths,
    save_results,
)

# ============================================================================
#
#                                   PIPELINE
#
# ============================================================================

def generate_rm(CONFIG: Configuration, hooks: GenerationHooks | None = None) -> int:
    """Propose, review, compile, and write one RM per task."""
    hooks = hooks or GenerationHooks()
    progress = Progress(hooks, CONFIG.LOGS_PATH)
    try:
        if progress.log_path is not None:
            hooks.notify_run_started(progress.log_path)
            progress(f"Run log: {progress.log_path}")

        return _run_pipeline(CONFIG, hooks, progress)

    except (ProposalValidationError, RetryableEngineError, ImmediateEngineError) as error:
        progress(f"Generation failed: {error}")
        return 1
    except Exception as error:
        progress(f"Generation failed unexpectedly: {error}")
        raise
    finally:
        progress.close()


def _run_pipeline(
    CONFIG: Configuration,
    hooks: GenerationHooks,
    progress: Progress,
) -> int:
    """Run every task through at most three proposal attempts."""
    output_paths = _prepare_outputs(CONFIG, progress)
    environment, engine = setup_environment_and_engine(CONFIG, progress)
    accepted: list[CompilationResult] = []

    for task_index, task in enumerate(CONFIG.tasks):
        history: list[dict[str, object]] = []
        result: CompilationResult | None = None

        for attempt in range(1, 4):
            proposal_text: str | None = None
            compiled: CompilationResult | None = None
            try:
                # ====== pipeline =======

                selections, proposal_text = _step_generate_proposal(
                    task, engine, history, progress, task_index, attempt
                )
                if not _step_task_critic(
                    CONFIG.task_critic, engine, task, proposal_text, history,
                    progress, task_index, attempt,
                ):
                    continue

                proposal = _step_materialize_ltlf(
                    environment, task, selections, progress, task_index, attempt
                )
                dfas = _step_compile_dfa(
                    CONFIG, proposal, progress, task_index, attempt
                )
                compiled = _step_build_reward_machine(
                    environment, proposal, dfas, progress, task_index, attempt
                )
                if not _step_rm_critic(
                    CONFIG.rm_critic, engine, task, proposal_text, compiled, history,
                    progress, task_index, attempt,
                ):
                    continue

            # ====== Exception handling =======
            except (RetryableEngineError, ValueError) as error:
                record_attempt_failure(
                    progress, history, proposal_text, compiled, task_index, attempt,
                    error,
                    "retryable failure" if isinstance(error, RetryableEngineError)
                    else "rejected",
                )
                continue
            except ImmediateEngineError:
                progress.fail(task_index, attempt)
                raise
            except (FileNotFoundError, RuntimeError) as error:
                progress.fail(task_index, attempt, str(error))
                raise ImmediateEngineError(str(error)) from error

            # ====== Results handling =======

            result = compiled
            progress(f"Task {task_index + 1}: attempt {attempt}/3 accepted.")
            break

        if result is None:
            raise RetryableEngineError(
                f"Task {task_index + 1} was not accepted within 3 attempts"
            )
        accepted.append(result)

    # ====== Results handling =======

    progress("Writing Reward Machine outputs.")
    results = tuple(accepted)
    save_results(results, output_paths, overwrite=CONFIG.overwrite)

    progress("Writing outputs complete.")
    hooks.notify_completion(results, output_paths)

    progress("Generation completed successfully.")
    return 0

# ============================================================================
#
#                                   STEPS
#
# ============================================================================
def _prepare_outputs(CONFIG: Configuration, progress: Progress) -> tuple[Path, ...]:
    progress("Validating output configuration.")

    validate_configuration(CONFIG)
    output_paths = derive_output_paths(CONFIG)

    for output_path in output_paths:
        progress(f"Output path: {output_path}")
    progress(f"Output setup complete for {len(CONFIG.tasks)} task(s).")

    return output_paths


def _step_generate_proposal(
    task: str,
    engine: GenericEngine,
    history: list[dict[str, object]],
    progress: Progress,
    task_index: int,
    attempt: int,
) -> tuple[tuple[ProposalSelection, ...], str]:
    """Generate and log validated proposal selections."""
    progress.start(task_index, attempt, PipelineStep.GENERATE)

    history_text = structure_history_text(history)
    selections = engine.propose_task(task, history=history_text)
    proposal_text = proposal_json(selections, task)

    progress.artifact("Validated proposal", proposal_text)
    progress.complete(task_index, attempt)

    return selections, proposal_text


def _step_task_critic(
    enabled: bool,
    engine: GenericEngine,
    task: str,
    proposal_text: str,
    history: list[dict[str, object]],
    progress: Progress,
    task_index: int,
    attempt: int,
) -> bool:
    if not enabled:
        progress.stage_skip(task_index, attempt, PipelineStep.TASK_CRITIC)
        return True
    progress.start(task_index, attempt, PipelineStep.TASK_CRITIC)


    critic = engine.review_task(task, proposal_text)


    progress.artifact(
        "Task critic verdict",
        {"accepted": critic.accepted, "feedback": critic.feedback},
    )
    if critic.accepted:
        progress.complete(task_index, attempt, StepState.COMPLETED)
    else:
        progress.complete(task_index, attempt, StepState.FAILED, critic.feedback)
        append_history(history, proposal_text, None, PipelineStep.TASK_CRITIC, critic.feedback)
        
    return critic.accepted
    

def _step_materialize_ltlf(
    environment: EnvironmentDescription,
    task: str,
    selections: Sequence[ProposalSelection],
    progress: Progress,
    task_index: int,
    attempt: int,
) -> Proposal:
    progress.start(task_index, attempt, PipelineStep.LTLF)

    proposal = materialize_proposal(environment, task, selections)

    progress.artifact(
        "LTLf clauses",
        [
            {
                "normalized_clause": clause.normalized_clause,
                "formula": clause.ltlf_formula,
            }
            for clause in proposal.clauses
        ],
    )
    progress.complete(task_index, attempt)
    return proposal


def _step_compile_dfa(
    CONFIG: Configuration,
    proposal: Proposal,
    progress: Progress,
    task_index: int,
    attempt: int,
) -> tuple[dict, ...]:
    progress.start(task_index, attempt, PipelineStep.DFA)

    dfas = compile_dfas(
        proposal, mona_executable=CONFIG.mona_executable or "mona"
    )

    progress.artifact("DFA data", dfas)
    progress.complete(task_index, attempt)
    return dfas


def _step_build_reward_machine(
    environment: EnvironmentDescription,
    proposal: Proposal,
    dfas: Sequence[dict],
    progress: Progress,
    task_index: int,
    attempt: int,
) -> CompilationResult:
    progress.start(task_index, attempt, PipelineStep.REWARD_MACHINE)
    
    compiled = build_compilation_result(environment, proposal, dfas)

    progress.artifact("Serialized Reward Machine", compiled.text)
    progress.complete(task_index, attempt)
    return compiled


def _step_rm_critic(
    enabled: bool,
    engine: GenericEngine,
    task: str,
    proposal_text: str,
    compiled: CompilationResult,
    history: list[dict[str, object]],
    progress: Progress,
    task_index: int,
    attempt: int,
) -> bool:
    if not enabled:
        progress.stage_skip(task_index, attempt, PipelineStep.RM_CRITIC)
        return True
    progress.start(task_index, attempt, PipelineStep.RM_CRITIC)


    critic = engine.review_reward_machine(task, compiled.text)

    
    progress.artifact(
        "Reward Machine critic verdict",
        {"accepted": critic.accepted, "feedback": critic.feedback},
    )
    if critic.accepted:
        progress.complete(task_index, attempt, StepState.COMPLETED)
    else:
        progress.complete(task_index, attempt, StepState.FAILED, critic.feedback)
        append_history(history, proposal_text, None, PipelineStep.TASK_CRITIC, critic.feedback)
        
    return critic.accepted
