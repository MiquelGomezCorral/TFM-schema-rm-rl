import json

from collections.abc import Sequence
from pathlib import Path

from src.engines import (
    AntigravityEngine,
    GenericEngine,
    OpenAIEngine,
    OpenCodeEngine,
    ProposalSelection,
)
from src.compiler import CompilationResult
from src.models import EnvironmentDescription
from src.config import Configuration

from .generation_logging import PipelineStep, Progress

def record_attempt_failure(
    progress: Progress,
    history: list[dict[str, object]],
    proposal_text: str | None,
    compiled: CompilationResult | None,
    task_index: int,
    attempt: int,
    error: Exception,
    outcome: str,
) -> None:
    progress.fail(task_index, attempt, str(error))
    append_history(history, proposal_text, compiled, progress.current_step, error)
    progress(f"Task {task_index + 1}: attempt {attempt}/3 {outcome} — {error}")


def append_history(
    history: list[dict[str, object]],
    proposal_text: str | None,
    compiled: CompilationResult | None,
    step: PipelineStep,
    feedback: object,
) -> None:
    """Keep bounded retry context for the next proposal attempt."""
    entry: dict[str, object] = {
        "source": (
            "generator" if step is PipelineStep.GENERATE else
            "task critic" if step is PipelineStep.TASK_CRITIC else
            "RM critic" if step is PipelineStep.RM_CRITIC else
            "compiler" if step in {
                PipelineStep.LTLF, PipelineStep.DFA, PipelineStep.REWARD_MACHINE
            } else step.value
        ),
        "pipeline_step": step.value,
        "feedback": str(feedback),
    }
    if proposal_text is not None:
        entry["proposal"] = proposal_text
    if compiled is not None:
        entry["compiled_rm"] = compiled.text
    history.append(entry)


def validate_configuration(CONFIG: Configuration) -> None:
    if CONFIG.environment is None:
        raise ValueError("An environment file is required")
    if CONFIG.output is None:
        raise ValueError("An output file is required")
    if not CONFIG.tasks:
        raise ValueError("At least one task is required")
    if any(not isinstance(task, str) or not task.strip() for task in CONFIG.tasks):
        raise ValueError("Tasks must be nonempty")


def proposal_json(
    selections: Sequence[ProposalSelection], task: str
) -> str:
    """Serialize only validated proposal fields safe for logs and critic prompts."""
    return json.dumps({
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
    }, indent=2, sort_keys=True)


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
            "The generator and critic models must differ, both resolved to "
            f"'{CONFIG.critic_model}'"
        )

    critic_engine = get_engine(CONFIG, environment, CONFIG.critic_model)
    progress(f"Critic engine ready: role=critic model={CONFIG.critic_model}.")

    progress("Environment and engine setup complete.")
    return environment, generator_engine, critic_engine


def derive_output_names(output: Path, task_count: int) -> tuple[Path, ...]:
    """Return the file names one run writes for ``output`` and ``task_count``."""
    if task_count <= 1:
        return (output,)
    return tuple(
        output.with_name(f"{output.stem}-{index}{output.suffix}")
        for index in range(1, task_count + 1)
    )


def derive_output_paths(CONFIG: Configuration) -> tuple[Path, ...]:
    if CONFIG.output is None:
        raise ValueError("An output file name is required")

    output_paths = tuple(
        CONFIG.RM_PATH / name
        for name in derive_output_names(CONFIG.output, len(CONFIG.tasks))
    )
    existing_paths = [path for path in output_paths if path.exists()]
    if existing_paths and not CONFIG.overwrite:
        raise ValueError(
            "Output file(s) already exist; pass --overwrite to replace them: "
            + ", ".join(str(path) for path in existing_paths)
        )
    return output_paths


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


def save_results(
    results: tuple[CompilationResult, ...],
    output_paths: tuple[Path, ...],
    overwrite: bool,
) -> None:
    mode = "w" if overwrite else "x"
    for output_path, result in zip(output_paths, results, strict=True):
        try:
            with output_path.open(mode, encoding="utf-8") as output_file:
                output_file.write(result.text)
        except FileExistsError as error:
            raise ValueError(
                f"Output file '{output_path}' already exists; pass --overwrite to replace it"
            ) from error
        except OSError as error:
            raise ValueError(f"Could not write output file '{output_path}': {error}") from error
