"""Progress events and hooks shared by Reward Machine generation clients."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import logging
from pathlib import Path
import pprint
import sys
import time

from src.compiler import CompilationResult


class PipelineStep(StrEnum):
    """Observable stages of one task attempt."""

    GENERATE = "generate"
    TASK_CRITIC = "task_critic"
    LTLF = "ltlf"
    DFA = "dfa"
    REWARD_MACHINE = "reward_machine"
    RM_CRITIC = "rm_critic"


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
        self.stage_started = self.started
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
        """Log one timed record and send it to the UI."""
        now = time.monotonic()
        rendered = f"[total {now - self.started:.3f}s | step {now - self.previous:.3f}s] {message}"
        self.previous = now
        self._write(rendered)
        return rendered

    def artifact(self, label: str, value: object) -> str:
        """Log a complete readable artifact."""
        body = value if isinstance(value, str) else pprint.pformat(value, sort_dicts=True, width=120)
        return self(f"{label}:\n{body}")

    def stage_start(
        self,
        task_index: int,
        attempt: int,
        step: PipelineStep,
        label: str,
    ) -> float:
        self.current_step = step
        self.stage_started = time.monotonic()
        self.hooks.notify_event(ProgressEvent(task_index, attempt, step, StepState.RUNNING))
        self(f"Task {task_index + 1}: attempt {attempt}/3 — {label}.")
        return self.stage_started

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
        self.hooks.notify_event(ProgressEvent(task_index, attempt, step, state, elapsed, detail))
        suffix = f" — {detail}" if detail else ""
        self(f"Task {task_index + 1}: {step_label(step)} {state.value}{suffix}.")
        return elapsed

    def stage_skip(self, task_index: int, attempt: int, step: PipelineStep) -> None:
        self.current_step = step
        self.hooks.notify_event(ProgressEvent(task_index, attempt, step, StepState.SKIPPED))
        self(f"Task {task_index + 1}: {step_label(step)} skipped.")

    def start(self, task_index: int, attempt: int, step: PipelineStep) -> None:
        """Start a stage using its standard label."""
        self.stage_start(task_index, attempt, step, step_label(step))

    def complete(
        self,
        task_index: int,
        attempt: int,
        state: StepState = StepState.COMPLETED,
        detail: str | None = None,
    ) -> None:
        """Finish the current stage."""
        self.stage_end(
            task_index,
            attempt,
            self.current_step,
            self.stage_started,
            state,
            detail,
        )

    def fail(self, task_index: int, attempt: int, detail: str | None = None) -> None:
        """Mark the current stage as failed."""
        self.complete(task_index, attempt, StepState.FAILED, detail)

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
