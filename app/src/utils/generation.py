"""Retry history and engine setup shared by the generation pipeline."""

import json
from collections.abc import Sequence

from src.compiler import CompilationResult
from src.config import Configuration
from src.engines import (
    AntigravityEngine,
    GenericEngine,
    OpenAIEngine,
    OpenCodeEngine,
    ProposalSelection,
    RetryableEngineError,
)
from src.models import EnvironmentDescription

from .generation_logging import PipelineStep, Progress

_HISTORY_SOURCES = {
    PipelineStep.GENERATE: "generator",
    PipelineStep.TASK_CRITIC: "task critic",
    PipelineStep.RM_CRITIC: "RM critic",
    PipelineStep.LTLF: "compiler",
    PipelineStep.DFA: "compiler",
    PipelineStep.REWARD_MACHINE: "compiler",
}


def record_attempt_failure(
    progress: Progress,
    history: list[dict[str, object]],
    proposal_text: str | None,
    compiled: CompilationResult | None,
    error: Exception,
) -> None:
    """Fail the current stage and keep the error as retry context for the next attempt."""
    outcome = "retryable failure" if isinstance(error, RetryableEngineError) else "rejected"
    progress.fail(str(error))
    append_history(history, proposal_text, compiled, progress.current_step, error)
    progress(
        f"Task {progress.current_task + 1}: attempt {progress.current_attempt}/{Configuration.PROPOSAL_ATTEMPTS} {outcome} — {error}"
    )


def append_history(
    history: list[dict[str, object]],
    proposal_text: str | None,
    compiled: CompilationResult | None,
    step: PipelineStep,
    feedback: object,
) -> None:
    """Keep bounded retry context for the next proposal attempt."""
    entry: dict[str, object] = {
        "source": _HISTORY_SOURCES.get(step, step.value),
        "pipeline_step": step.value,
        "feedback": str(feedback),
    }
    if proposal_text is not None:
        entry["proposal"] = proposal_text
    if compiled is not None:
        entry["compiled_rm"] = compiled.text
    history.append(entry)


def proposal_json(selections: Sequence[ProposalSelection], task: str) -> str:
    """Serialize only validated proposal fields safe for logs and critic prompts."""
    return json.dumps(
        {
            "task": task,
            "clauses": [
                {
                    "normalized_clause": c.normalized_clause,
                    "pattern": c.pattern,
                    "propositions": list(c.propositions),
                    "priority": c.priority.value,
                }
                for c in selections
            ],
        },
        indent=2,
        sort_keys=True,
    )


def structure_history_text(history: list[dict[str, object]]) -> str:
    return json.dumps(history, sort_keys=True) if history else "None."


def setup_environment_and_engines(
    CONFIG: Configuration,
    progress: Progress,
) -> tuple[EnvironmentDescription, GenericEngine, GenericEngine | None]:
    """Load the environment and create the compiler's role engines for one run.

    The generator engine proposes clauses and state descriptions. The critic
    engine reviews both artifacts and is None only when both critics are disabled.

    Raises:
        ValueError: An enabled critic has no critic model, or the resolved
            generator and critic models are identical.
    """
    progress("Setting up the environment and LLM engines.")
    progress(f"Loading environment from {CONFIG.environment}.")
    progress(f"Using LLM provider '{CONFIG.llm_provider}'.")

    environment = EnvironmentDescription.from_file(CONFIG.environment)
    generator_engine = get_engine(CONFIG, environment, CONFIG.generator_model)
    progress(f"Generator engine ready: role=generator model={CONFIG.generator_model}.")

    if not CONFIG.task_critic and not CONFIG.rm_critic:
        progress("Both critics are disabled; no critic engine created.")
        return environment, generator_engine, None

    if not CONFIG.critic_model:
        raise ValueError(
            "An enabled critic requires a configured critic model; set the "
            f"{CONFIG.llm_provider} critic model variable or Configuration.critic_model"
        )
    if CONFIG.critic_model == CONFIG.generator_model:
        raise ValueError(
            f"The generator and critic models must differ, both resolved to '{CONFIG.critic_model}'"
        )

    critic_engine = get_engine(CONFIG, environment, CONFIG.critic_model)
    progress(f"Critic engine ready: role=critic model={CONFIG.critic_model}.")

    progress("Environment and engine setup complete.")
    return environment, generator_engine, critic_engine


def get_engine(
    CONFIG: Configuration,
    environment: EnvironmentDescription,
    model: str | None = None,
) -> GenericEngine:
    """Create the selected provider's engine, defaulting to the baseline model."""
    engine_types = {
        "openai": OpenAIEngine,
        "opencode": OpenCodeEngine,
        "antigravity": AntigravityEngine,
    }
    return engine_types[CONFIG.llm_provider](
        environment, model if model is not None else CONFIG.model
    )
