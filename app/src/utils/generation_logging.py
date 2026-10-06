"""Progress events and hooks shared by Reward Machine generation clients."""

import logging
import pprint
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from src.compiler import CompilationResult


class PipelineStep(StrEnum):
    """Observable stages of one task attempt."""

    GENERATE = "generate"
    TASK_CRITIC = "task_critic"
    LTLF = "ltlf"
    DFA = "dfa"
    REWARD_MACHINE = "reward_machine"
    STATE_DESCRIPTIONS = "state_descriptions"
    RM_CRITIC = "rm_critic"
    LABELING = "labeling"
    EMBEDDINGS = "embeddings"


class StepState(StrEnum):
    """State of one observable pipeline stage."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


_STEP_LABELS = {
    PipelineStep.GENERATE: "Generating proposal",
    PipelineStep.TASK_CRITIC: "Task critic",
    PipelineStep.LTLF: "Building LTLf",
    PipelineStep.DFA: "Compiling DFA",
    PipelineStep.REWARD_MACHINE: "Building Reward Machine",
    PipelineStep.STATE_DESCRIPTIONS: "Generating state descriptions",
    PipelineStep.RM_CRITIC: "Reward Machine critic",
    PipelineStep.LABELING: "Generating MiniGrid labeling",
    PipelineStep.EMBEDDINGS: "Embedding state descriptions",
}


@dataclass(frozen=True)
class ProgressEvent:
    """Immutable stage update sent to non-text observers."""

    task_index: int
    attempt: int
    step: PipelineStep
    state: StepState
    elapsed: float | None = None
    detail: str | None = None


@dataclass(frozen=True)
class StepArtifact:
    """Structured value one pipeline stage published for one task attempt."""

    task_index: int
    attempt: int
    step: PipelineStep
    value: object


@dataclass(frozen=True)
class GenerationHooks:
    """Optional observers for one generation run."""

    progress: Callable[[str], None] | None = None
    completion: Callable[[tuple[CompilationResult, ...], tuple[Path, ...]], None] | None = None
    event: Callable[[ProgressEvent], None] | None = None
    artifact: Callable[[StepArtifact], None] | None = None
    run_started: Callable[[Path], None] | None = None
    failure: Callable[[str], None] | None = None

    def notify_progress(self, message: str) -> None:
        if self.progress is not None:
            self.progress(message)

    def notify_event(self, event: ProgressEvent) -> None:
        if self.event is not None:
            self.event(event)

    def notify_artifact(self, artifact: StepArtifact) -> None:
        if self.artifact is not None:
            self.artifact(artifact)

    def notify_run_started(self, log_path: Path) -> None:
        if self.run_started is not None:
            self.run_started(log_path)

    def notify_failure(self, message: str) -> None:
        if self.failure is not None:
            self.failure(message)

    def notify_completion(
        self,
        results: tuple[CompilationResult, ...],
        output_paths: tuple[Path, ...],
    ) -> None:
        if self.completion is not None:
            self.completion(results, output_paths)


class Progress:
    """Run-scoped plain-text logging and stage event fan-out."""

    def __init__(
        self,
        hooks: GenerationHooks,
        logs_path: Path | None = None,
    ) -> None:
        self.hooks = hooks
        self.started = time.monotonic()
        self.previous = self.started
        self.current_step = PipelineStep.GENERATE
        self.current_task = -1  # Replaced by begin_attempt before any artifact publishes.
        self.current_attempt = 0
        self.stage_started = self.started
        self._logger: logging.Logger | None = None
        self.log_path: Path | None = None

        if logs_path is not None:
            logs_path = Path(logs_path).resolve()
            logs_path.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
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
        """Log one timed record and send it to the UI."""
        now = time.monotonic()
        rendered = f"[total {now - self.started:.3f}s | step {now - self.previous:.3f}s] {message}"
        self.previous = now
        self._write(rendered)
        return rendered

    def artifact(self, label: str, value: object) -> str:
        """Log a complete readable artifact and publish it to structured observers."""
        body = (
            value if isinstance(value, str) else pprint.pformat(value, sort_dicts=True, width=120)
        )
        self.hooks.notify_artifact(
            StepArtifact(
                task_index=self.current_task,
                attempt=self.current_attempt,
                step=self.current_step,
                value=value,
            )
        )
        return self(f"{label}:\n{body}")

    def begin_attempt(self, task_index: int, attempt: int) -> None:
        """Name the task attempt that the following stages belong to."""
        self.current_task = task_index
        self.current_attempt = attempt

    def start(self, step: PipelineStep) -> None:
        """Start a stage of the current attempt using its standard label."""
        self.current_step = step
        self.stage_started = time.monotonic()
        self.hooks.notify_event(
            ProgressEvent(self.current_task, self.current_attempt, step, StepState.RUNNING)
        )
        self(
            f"Task {self.current_task + 1}: attempt {self.current_attempt}/3 — {_STEP_LABELS[step]}."
        )

    def stage_skip(self, step: PipelineStep) -> None:
        self.current_step = step
        self.hooks.notify_event(
            ProgressEvent(self.current_task, self.current_attempt, step, StepState.SKIPPED)
        )
        self(f"Task {self.current_task + 1}: {_STEP_LABELS[step]} skipped.")

    def complete(
        self,
        state: StepState = StepState.COMPLETED,
        detail: str | None = None,
    ) -> None:
        """Finish the current stage."""
        elapsed = max(0.0, time.monotonic() - self.stage_started)
        self.hooks.notify_event(
            ProgressEvent(
                self.current_task,
                self.current_attempt,
                self.current_step,
                state,
                elapsed,
                detail,
            )
        )
        suffix = f" — {detail}" if detail else ""
        self(
            f"Task {self.current_task + 1}: {_STEP_LABELS[self.current_step]} {state.value}{suffix}."
        )

    def fail(self, detail: str | None = None) -> None:
        """Mark the current stage as failed."""
        self.complete(StepState.FAILED, detail)

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
