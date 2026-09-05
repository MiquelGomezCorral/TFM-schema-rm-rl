"""Generate one Reward Machine per critic-validated natural-language task."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
import pprint
import sys
import time

from src.compiler import (
    CompilationResult,
    Proposal,
    build_compilation_result,
    compile_dfas,
    compile_proposal,
    materialize_proposal,
    propose_task,
)
from src.config import Configuration
from src.engines import (
    GenericEngine,
    ImmediateEngineError,
    OpenAIEngine,
    OpenCodeEngine,
    ProposalValidationError,
    RetryableEngineError,
)
from src.engines.structured import ProposalSelection
from src.models import EnvironmentDescription
from maikol_utils.print_utils import print_color, print_separator


class PipelineStep(StrEnum):
    """Observable stages of one task attempt."""

    GENERATE = "generate"
    TASK_CRITIC = "task_critic"
    LTLF = "ltlf"
    DFA = "dfa"
    REWARD_MACHINE = "reward_machine"
    RM_CRITIC = "rm_critic"

    PROPOSAL = "generate"
    MATERIALIZE_LTLF = "ltlf"
    COMPILE_DFA = "dfa"
    BUILD_REWARD_MACHINE = "reward_machine"


class StepState(StrEnum):
    """State of one observable pipeline stage."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class ProgressEvent:
    """Immutable stage update sent to non-text observers."""

    task_index: int
    attempt: int
    step: PipelineStep
    state: StepState
    elapsed: float | None = None
    detail: str | None = None

    @property
    def elapsed_seconds(self) -> float | None:
        return self.elapsed

    @property
    def duration_seconds(self) -> float | None:
        return self.elapsed

    @property
    def duration(self) -> float | None:
        return self.elapsed

    @property
    def stage(self) -> PipelineStep:
        return self.step

    @property
    def status(self) -> StepState:
        return self.state


@dataclass(frozen=True)
class GenerationHooks:
    """Optional observers for one generation run."""

    progress: Callable[[str], None] | None = None
    completion: Callable[[tuple[CompilationResult, ...], tuple[Path, ...]], None] | None = None
    event: Callable[[ProgressEvent], None] | None = None
    run_started: Callable[[Path], None] | None = None

    def notify_progress(self, message: str) -> None:
        if self.progress is not None:
            self.progress(message)

    def notify_event(self, event: ProgressEvent) -> None:
        if self.event is not None:
            self.event(event)

    def notify_run_started(self, log_path: Path) -> None:
        if self.run_started is not None:
            self.run_started(log_path)

    def notify_completion(
        self,
        results: tuple[CompilationResult, ...],
        output_paths: tuple[Path, ...],
    ) -> None:
        if self.completion is not None:
            self.completion(results, output_paths)


class _Progress:
    """Run-scoped plain-text logging and stage event fan-out."""

    def __init__(
        self,
        hooks: GenerationHooks,
        logs_path: Path | None = None,
    ) -> None:
        self.hooks = hooks
        self.started = time.monotonic()
        self.previous = self.started
        self._logger: logging.Logger | None = None
        self.log_path: Path | None = None
        if logs_path is not None:
            logs_path = Path(logs_path).resolve()
            logs_path.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
            self.log_path = logs_path / f"run-{stamp}.log"
            suffix = 1
            while self.log_path.exists():
                self.log_path = logs_path / f"run-{stamp}-{suffix}.log"
                suffix += 1
            logger = logging.getLogger(f"schema-rm.run.{id(self)}")
            logger.setLevel(logging.INFO)
            logger.propagate = False
            formatter = logging.Formatter("%(message)s")
            file_handler = logging.FileHandler(self.log_path, encoding="utf-8")
            stream_handler = logging.StreamHandler(sys.stdout)
            file_handler.setFormatter(formatter)
            stream_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            logger.addHandler(stream_handler)
            self._logger = logger

    def __call__(self, message: str) -> str:
        """Log one timed plain-text record and send the same record to the UI."""
        now = time.monotonic()
        rendered = f"[total {now - self.started:.3f}s | step {now - self.previous:.3f}s] {message}"
        self.previous = now
        self._write(rendered)
        return rendered

    def artifact(self, label: str, value: object) -> str:
        """Log a complete readable artifact without truncating its contents."""
        body = value if isinstance(value, str) else pprint.pformat(value, sort_dicts=True, width=120)
        return self(f"{label}:\n{body}")

    def stage_start(
        self,
        task_index: int,
        attempt: int,
        step: PipelineStep,
        label: str,
    ) -> float:
        self.hooks.notify_event(
            ProgressEvent(task_index, attempt, step, StepState.RUNNING)
        )
        self(f"Task {task_index + 1}: attempt {attempt}/3 — {label}.")
        return time.monotonic()

    def stage_end(
        self,
        task_index: int,
        attempt: int,
        step: PipelineStep,
        started: float,
        state: StepState = StepState.COMPLETED,
        detail: str | None = None,
    ) -> float:
        elapsed = max(0.0, time.monotonic() - started)
        self.hooks.notify_event(
            ProgressEvent(task_index, attempt, step, state, elapsed, detail)
        )
        suffix = f" — {detail}" if detail else ""
        self(f"Task {task_index + 1}: {step_label(step)} {state.value}{suffix}.")
        return elapsed

    def stage_skip(self, task_index: int, attempt: int, step: PipelineStep) -> None:
        self.hooks.notify_event(
            ProgressEvent(task_index, attempt, step, StepState.SKIPPED)
        )
        self(f"Task {task_index + 1}: {step_label(step)} skipped.")

    def close(self) -> None:
        """Flush and detach this run's handlers."""
        if self._logger is None:
            return
        for handler in tuple(self._logger.handlers):
            handler.flush()
            handler.close()
            self._logger.removeHandler(handler)
        self._logger = None

    def _write(self, message: str) -> None:
        if self._logger is not None:
            self._logger.info(message)
        self.hooks.notify_progress(message)


def step_label(step: PipelineStep) -> str:
    """Return the user-facing label for a typed stage."""
    return {
        PipelineStep.GENERATE: "Generating proposal",
        PipelineStep.TASK_CRITIC: "Task critic",
        PipelineStep.LTLF: "Building LTLf",
        PipelineStep.DFA: "Compiling DFA",
        PipelineStep.REWARD_MACHINE: "Building Reward Machine",
        PipelineStep.RM_CRITIC: "Reward Machine critic",
    }[step]


def generate_rm(config: Configuration, hooks: GenerationHooks | None = None) -> int:
    """Propose, review, compile, and write one RM per task."""
    hooks = hooks or GenerationHooks()
    progress = _Progress(hooks, config.LOGS_PATH)
    try:
        if progress.log_path is not None:
            hooks.notify_run_started(progress.log_path)
            progress(f"Run log: {progress.log_path}")
        return _run_pipeline(config, hooks, progress)
    except (ProposalValidationError, RetryableEngineError, ImmediateEngineError) as error:
        progress(f"Generation failed: {error}")
        return 1
    except Exception as error:
        progress(f"Generation failed unexpectedly: {error}")
        raise
    finally:
        progress.close()


def _run_pipeline(
    config: Configuration,
    hooks: GenerationHooks,
    progress: _Progress | None = None,
) -> int:
    """Run the generation phases inside the command separator boundary."""
    progress = progress or _Progress(hooks, config.LOGS_PATH)

    progress("Validating output configuration.")
    _validate_configuration(config)
    output_paths = _derive_output_paths(config)
    progress(f"Output setup complete for {len(config.tasks)} task(s).")
    for output_path in output_paths:
        progress(f"Output path: {output_path}")

    progress("Setting up the environment and LLM engine.")
    environment, engine = _setup_environment_and_engine(config, progress)
    progress("Environment and engine setup complete.")

    accepted: list[CompilationResult] = []
    for task_index, task in enumerate(config.tasks):
        history: list[dict[str, object]] = []
        result: CompilationResult | None = None
        for attempt in range(1, 4):
            proposal: Proposal | None = None
            proposal_text: str | None = None
            compiled: CompilationResult | None = None
            legacy_proposal = False
            stage_failed = False
            current_step = PipelineStep.GENERATE
            started = progress.stage_start(
                task_index, attempt, current_step, step_label(current_step)
            )
            try:
                generated = _generate_candidate(
                    environment, task, engine, _history_text(history)
                )
                legacy_proposal = isinstance(generated, Proposal)
                proposal_text = _proposal_json(generated, task)
                progress.artifact("Validated proposal", proposal_text)
                progress.stage_end(task_index, attempt, current_step, started)

                if config.task_critic:
                    current_step = PipelineStep.TASK_CRITIC
                    started = progress.stage_start(
                        task_index, attempt, current_step, step_label(current_step)
                    )
                    critic = engine.review_task(task, proposal_text)
                    progress.artifact(
                        "Task critic verdict",
                        {"accepted": critic.accepted, "feedback": critic.feedback},
                    )
                    if not critic.accepted:
                        progress.stage_end(
                            task_index, attempt, current_step, started,
                            StepState.FAILED, critic.feedback,
                        )
                        history.append({
                            "proposal": proposal_text,
                            "source": "task critic",
                            "pipeline_step": current_step.value,
                            "feedback": critic.feedback,
                        })
                        continue
                    progress.stage_end(task_index, attempt, current_step, started)
                else:
                    progress.stage_skip(task_index, attempt, PipelineStep.TASK_CRITIC)

                if legacy_proposal:
                    proposal = generated
                else:
                    current_step = PipelineStep.LTLF
                    started = progress.stage_start(
                        task_index, attempt, current_step, step_label(current_step)
                    )
                    proposal = materialize_proposal(environment, task, generated)
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
                    progress.stage_end(task_index, attempt, current_step, started)

                current_step = PipelineStep.DFA
                started = progress.stage_start(
                    task_index, attempt, current_step, step_label(current_step)
                )
                if legacy_proposal:
                    compiled = compile_proposal(
                        environment,
                        proposal,
                        mona_executable=config.mona_executable or "mona",
                    )
                    dfas = getattr(compiled, "dfas", ())
                else:
                    dfas = compile_dfas(
                        proposal, mona_executable=config.mona_executable or "mona"
                    )
                progress.artifact("DFA data", dfas)
                progress.stage_end(task_index, attempt, current_step, started)

                current_step = PipelineStep.REWARD_MACHINE
                started = progress.stage_start(
                    task_index, attempt, current_step, step_label(current_step)
                )
                if compiled is None:
                    compiled = build_compilation_result(environment, proposal, dfas)
                progress.artifact("Serialized Reward Machine", compiled.text)
                progress.stage_end(task_index, attempt, current_step, started)

                if config.rm_critic:
                    current_step = PipelineStep.RM_CRITIC
                    started = progress.stage_start(
                        task_index, attempt, current_step, step_label(current_step)
                    )
                    critic = engine.review_reward_machine(task, compiled.text)
                    progress.artifact(
                        "Reward Machine critic verdict",
                        {"accepted": critic.accepted, "feedback": critic.feedback},
                    )
                    if not critic.accepted:
                        progress.stage_end(
                            task_index, attempt, current_step, started,
                            StepState.FAILED, critic.feedback,
                        )
                        history.append({
                            "proposal": proposal_text,
                            "compiled_rm": compiled.text,
                            "source": "RM critic",
                            "pipeline_step": current_step.value,
                            "feedback": critic.feedback,
                        })
                        continue
                    progress.stage_end(task_index, attempt, current_step, started)
                else:
                    progress.stage_skip(task_index, attempt, PipelineStep.RM_CRITIC)

                result = compiled
                progress(f"Task {task_index + 1}: attempt {attempt}/3 accepted.")
                break
            except RetryableEngineError as error:
                stage_failed = True
                progress.stage_end(
                    task_index, attempt, current_step, started,
                    StepState.FAILED, str(error),
                )
                _append_history(history, proposal_text, compiled, current_step, error)
                progress(f"Task {task_index + 1}: attempt {attempt}/3 retryable failure — {error}")
            except ImmediateEngineError:
                if not stage_failed:
                    progress.stage_end(
                        task_index, attempt, current_step, started,
                        StepState.FAILED,
                    )
                raise
            except (FileNotFoundError, RuntimeError) as error:
                stage_failed = True
                progress.stage_end(
                    task_index, attempt, current_step, started,
                    StepState.FAILED, str(error),
                )
                raise ImmediateEngineError(str(error)) from error
            except ValueError as error:
                stage_failed = True
                progress.stage_end(
                    task_index, attempt, current_step, started,
                    StepState.FAILED, str(error),
                )
                _append_history(history, proposal_text, compiled, current_step, error)
                progress(f"Task {task_index + 1}: attempt {attempt}/3 rejected — {error}")
        if result is None:
            raise RetryableEngineError(
                f"Task {task_index + 1} was not accepted within 3 attempts"
            )
        accepted.append(result)

    results = tuple(accepted)
    progress("Writing Reward Machine outputs.")
    _save_results(results, output_paths, overwrite=config.overwrite)
    progress("Writing outputs complete.")
    hooks.notify_completion(results, output_paths)
    progress("Generation completed successfully.")
    return 0


def _generate_candidate(
    environment: EnvironmentDescription,
    task: str,
    engine: GenericEngine,
    history: str,
) -> tuple[ProposalSelection, ...] | Proposal:
    """Request validated selections, with a compatibility path for old test engines."""
    engine_propose = getattr(engine, "propose_task", None)
    if callable(engine_propose):
        return engine_propose(task, history=history)
    return propose_task(environment, task, engine, history=history)


def _append_history(
    history: list[dict[str, object]],
    proposal_text: str | None,
    compiled: CompilationResult | None,
    step: PipelineStep,
    error: Exception,
) -> None:
    """Keep retry context while preserving the legacy compiler source label."""
    entry: dict[str, object] = {
        "source": (
            "generator" if step is PipelineStep.GENERATE else
            "RM critic" if step is PipelineStep.RM_CRITIC else
            "compiler" if step in {
                PipelineStep.LTLF, PipelineStep.DFA, PipelineStep.REWARD_MACHINE
            } else step.value
        ),
        "pipeline_step": step.value,
        "feedback": str(error),
    }
    if proposal_text is not None:
        entry["proposal"] = proposal_text
    if compiled is not None:
        entry["compiled_rm"] = compiled.text
    history.append(entry)


def _validate_configuration(config: Configuration) -> None:
    if config.environment is None:
        raise ValueError("An environment file is required")
    if config.output is None:
        raise ValueError("An output file is required")
    if not config.tasks:
        raise ValueError("At least one task is required")
    if any(not isinstance(task, str) or not task.strip() for task in config.tasks):
        raise ValueError("Tasks must be nonempty")
    if not config.task_critic and not config.rm_critic:
        raise ValueError("At least one critic must be enabled")


def _proposal_json(
    proposal: Proposal | Sequence[ProposalSelection],
    task: str | None = None,
) -> str:
    """Serialize only validated proposal fields safe for logs and critic prompts."""
    if isinstance(proposal, Proposal):
        task = proposal.task
        clauses = proposal.clauses
    else:
        task = task or ""
        clauses = proposal
    return json.dumps({
        "task": task,
        "clauses": [
            {
                "normalized_clause": c.normalized_clause,
                "pattern": c.pattern,
                "propositions": list(c.propositions),
                "priority": c.priority.value,
            }
            for c in clauses
        ],
    }, indent=2, sort_keys=True)


def _history_text(history: list[dict[str, object]]) -> str:
    return json.dumps(history, sort_keys=True) if history else "None."


def _setup_environment_and_engine(
    config: Configuration,
    progress: _Progress | None = None,
) -> tuple[EnvironmentDescription, GenericEngine]:
    if progress is not None:
        progress(f"Loading environment from {config.environment}.")
    environment = EnvironmentDescription.from_file(config.environment)
    if progress is not None:
        progress(f"Using LLM engine for provider '{config.llm_provider}'.")
    engine = _get_engine(config, environment)
    return environment, engine


def _derive_output_paths(config: Configuration) -> tuple[Path, ...]:
    if config.output is None:
        raise ValueError("An output file name is required")

    if len(config.tasks) == 1:
        output_names = (config.output,)
    else:
        output_names = tuple(
            config.output.with_name(
                f"{config.output.stem}-{index}{config.output.suffix}"
            )
            for index in range(1, len(config.tasks) + 1)
        )

    output_paths = tuple(config.OUTPUT_PATH / name for name in output_names)
    existing_paths = [path for path in output_paths if path.exists()]
    if existing_paths and not config.overwrite:
        raise ValueError(
            "Output file(s) already exist; pass --overwrite to replace them: "
            + ", ".join(str(path) for path in existing_paths)
        )
    return output_paths


def _get_engine(
    config: Configuration,
    environment: EnvironmentDescription,
) -> GenericEngine:
    if config.llm_provider == "opencode":
        return OpenCodeEngine(environment, config.model)
    return OpenAIEngine(environment, config.model)


def _save_results(
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
