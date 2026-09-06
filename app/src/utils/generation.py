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


def setup_environment_and_engine(
    CONFIG: Configuration,
    progress: Progress,
) -> tuple[EnvironmentDescription, GenericEngine]:
    progress("Setting up the environment and LLM engine.")
    progress(f"Loading environment from {CONFIG.environment}.")
    progress(f"Using LLM engine for provider '{CONFIG.llm_provider}'.")

    environment = EnvironmentDescription.from_file(CONFIG.environment)
    engine = _get_engine(CONFIG, environment)

    progress("Environment and engine setup complete.")
    return environment, engine


def derive_output_paths(CONFIG: Configuration) -> tuple[Path, ...]:
    if CONFIG.output is None:
        raise ValueError("An output file name is required")

    if len(CONFIG.tasks) == 1:
        output_names = (CONFIG.output,)
    else:
        output_names = tuple(
            CONFIG.output.with_name(
                f"{CONFIG.output.stem}-{index}{CONFIG.output.suffix}"
            )
            for index in range(1, len(CONFIG.tasks) + 1)
        )

    output_paths = tuple(CONFIG.OUTPUT_PATH / name for name in output_names)
    existing_paths = [path for path in output_paths if path.exists()]
    if existing_paths and not CONFIG.overwrite:
        raise ValueError(
            "Output file(s) already exist; pass --overwrite to replace them: "
            + ", ".join(str(path) for path in existing_paths)
        )
    return output_paths


def _get_engine(
    CONFIG: Configuration,
    environment: EnvironmentDescription,
) -> GenericEngine:
    engine_types = {
        "openai": OpenAIEngine,
        "opencode": OpenCodeEngine,
        "antigravity": AntigravityEngine,
    }
    return engine_types[CONFIG.llm_provider](environment, CONFIG.model)


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
