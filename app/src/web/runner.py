"""Threaded local execution boundary for the Reward Machine pipeline."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
import tempfile
from threading import Lock, Thread
from typing import Sequence

from scripts.generate_rm import (
    GenerationHooks,
    PipelineStep,
    ProgressEvent,
    StepState,
    generate_rm,
)
from src.compiler import CompilationResult
from src.config import Configuration


class RunState(StrEnum):
    """States exposed by a local generation run."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


STEP_ORDER = (
    PipelineStep.GENERATE,
    PipelineStep.TASK_CRITIC,
    PipelineStep.LTLF,
    PipelineStep.DFA,
    PipelineStep.REWARD_MACHINE,
    PipelineStep.RM_CRITIC,
)


@dataclass(frozen=True)
class StepSnapshot:
    """Immutable presentation state for one pipeline step."""

    step: PipelineStep
    state: StepState = StepState.PENDING
    elapsed: float | None = None
    detail: str | None = None

    @property
    def duration(self) -> float | None:
        return self.elapsed


@dataclass(frozen=True)
class TaskSnapshot:
    """Immutable presentation state for one submitted task."""

    index: int
    task: str
    attempt: int = 0
    steps: tuple[StepSnapshot, ...] = ()
    retry_note: str | None = None

    @property
    def state(self) -> StepState:
        states = tuple(step.state for step in self.steps)
        if StepState.FAILED in states:
            return StepState.FAILED
        if StepState.RUNNING in states:
            return StepState.RUNNING
        if states and all(state in {StepState.COMPLETED, StepState.SKIPPED} for state in states):
            return StepState.COMPLETED
        return StepState.PENDING


@dataclass(frozen=True)
class RunSnapshot:
    """Immutable view of controller state for a Dash callback."""

    status: RunState
    logs: tuple[str, ...]
    results: tuple[CompilationResult, ...]
    output_paths: tuple[Path, ...]
    error: str | None = None
    tasks: tuple[TaskSnapshot, ...] = ()
    active_task_index: int | None = None
    log_path: Path | None = None
    run_id: int = 0

    @property
    def task_progress(self) -> tuple[TaskSnapshot, ...]:
        return self.tasks

    @property
    def current_task_index(self) -> int | None:
        return self.active_task_index


@dataclass(frozen=True)
class _RunRequest:
    """Copied input required by the worker thread."""

    environment_markdown: str
    environment_filename: str | None
    tasks: tuple[str, ...]
    output_filename: str
    task_critic: bool
    rm_critic: bool


class RunController:
    """Own one background pipeline run."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._status = RunState.IDLE
        self._logs: list[str] = []
        self._results: tuple[CompilationResult, ...] = ()
        self._output_paths: tuple[Path, ...] = ()
        self._error: str | None = None
        self._tasks: tuple[TaskSnapshot, ...] = ()
        self._active_task_index: int | None = None
        self._log_path: Path | None = None
        self._run_id = 0
        self._worker: Thread | None = None

    def snapshot(self) -> RunSnapshot:
        """Return a lock-consistent, immutable snapshot of the current run."""
        with self._lock:
            return RunSnapshot(
                status=self._status,
                logs=tuple(self._logs),
                results=tuple(self._results),
                output_paths=tuple(self._output_paths),
                error=self._error,
                tasks=tuple(self._tasks),
                active_task_index=self._active_task_index,
                log_path=self._log_path,
                run_id=self._run_id,
            )

    def start(
        self,
        environment_markdown: str,
        tasks: Sequence[str],
        output_filename: str,
        environment_filename: str | None = None,
        task_critic: bool = True,
        rm_critic: bool = True,
    ) -> None:
        """Start one run using submitted Markdown and UI values."""
        # if not task_critic and not rm_critic:
        #     raise ValueError("At least one critic must be enabled")
        request = _RunRequest(
            environment_markdown=environment_markdown,
            environment_filename=environment_filename,
            tasks=tuple(tasks),
            output_filename=output_filename,
            task_critic=task_critic,
            rm_critic=rm_critic,
        )
        with self._lock:
            if self._status is RunState.RUNNING or (
                self._worker is not None and self._worker.is_alive()
            ):
                raise RuntimeError("A Reward Machine run is already active")
            self._run_id += 1
            self._status = RunState.RUNNING
            self._logs = []
            self._results = ()
            self._output_paths = ()
            self._error = None
            self._tasks = tuple(
                _initial_task(index, task, task_critic, rm_critic)
                for index, task in enumerate(request.tasks)
            )
            self._active_task_index = None
            self._log_path = None
            self._worker = Thread(
                target=self._run_request,
                args=(request,),
                name="reward-machine-web-worker",
                daemon=True,
            )
            self._worker.start()

    def _run_request(self, request: _RunRequest) -> None:
        try:
            with tempfile.TemporaryDirectory(prefix="schema-rm-web-") as temporary_directory:
                environment_path = Path(temporary_directory) / _safe_environment_filename(
                    request.environment_filename
                )
                environment_path.write_text(request.environment_markdown, encoding="utf-8")
                config = Configuration(
                    environment=environment_path,
                    tasks=list(request.tasks),
                    output=Path(request.output_filename),
                    task_critic=request.task_critic,
                    rm_critic=request.rm_critic,
                )
                hooks = GenerationHooks(
                    progress=self._record_progress,
                    event=self._record_event,
                    run_started=self._record_log_path,
                    completion=self._retain_results,
                )
                return_code = generate_rm(config, hooks=hooks)
            with self._lock:
                if return_code == 0:
                    self._status = RunState.COMPLETED
                else:
                    self._status = RunState.FAILED
                    self._error = f"Generation exited with code {return_code}."
        except Exception as error:
            with self._lock:
                self._status = RunState.FAILED
                self._error = str(error)

    def _record_progress(self, message: str) -> None:
        with self._lock:
            self._append_log(message)

    def _record_event(self, event: ProgressEvent) -> None:
        with self._lock:
            if not 0 <= event.task_index < len(self._tasks):
                return
            task = self._tasks[event.task_index]
            if event.attempt > task.attempt:
                task = _reset_task(task, event.attempt)
            elif event.attempt < task.attempt:
                return
            steps = list(task.steps)
            step_index = next(
                (index for index, item in enumerate(steps) if item.step is event.step),
                None,
            )
            if step_index is None:
                return
            steps[step_index] = StepSnapshot(
                step=event.step,
                state=event.state,
                elapsed=event.elapsed,
                detail=event.detail,
            )
            retry_note = task.retry_note
            if event.state is StepState.FAILED and event.detail:
                retry_note = event.detail
            self._tasks = self._tasks[:event.task_index] + (
                TaskSnapshot(
                    index=task.index,
                    task=task.task,
                    attempt=event.attempt,
                    steps=tuple(steps),
                    retry_note=retry_note,
                ),
            ) + self._tasks[event.task_index + 1:]
            if event.state is StepState.RUNNING:
                self._active_task_index = event.task_index

    def _record_log_path(self, path: Path) -> None:
        with self._lock:
            self._log_path = path

    def _retain_results(
        self,
        results: tuple[CompilationResult, ...],
        output_paths: tuple[Path, ...],
    ) -> None:
        with self._lock:
            self._results = tuple(results)
            self._output_paths = tuple(output_paths)

    def _append_log(self, message: str) -> None:
        self._logs.append(str(message))


def _initial_task(index: int, task: str, task_critic: bool, rm_critic: bool) -> TaskSnapshot:
    skipped = {
        PipelineStep.TASK_CRITIC: not task_critic,
        PipelineStep.RM_CRITIC: not rm_critic,
    }
    return TaskSnapshot(
        index=index,
        task=task,
        steps=tuple(
            StepSnapshot(step, StepState.SKIPPED if skipped.get(step, False) else StepState.PENDING)
            for step in STEP_ORDER
        ),
    )


def _reset_task(task: TaskSnapshot, attempt: int) -> TaskSnapshot:
    return TaskSnapshot(
        index=task.index,
        task=task.task,
        attempt=attempt,
        steps=tuple(
            StepSnapshot(
                step.step,
                StepState.SKIPPED if step.state is StepState.SKIPPED else StepState.PENDING,
            )
            for step in task.steps
        ),
        retry_note=task.retry_note,
    )


def _safe_environment_filename(filename: str | None) -> str:
    """Keep an uploaded basename while preventing path traversal."""
    if not filename:
        return "environment.md"
    basename = PurePosixPath(str(filename).replace("\\", "/")).name
    if not basename or basename in {".", ".."} or "\x00" in basename:
        return "environment.md"
    return basename
