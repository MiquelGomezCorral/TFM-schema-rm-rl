"""Threaded local execution boundary for the Reward Machine pipeline."""

import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path, PurePosixPath
from threading import Lock, Thread

from src.compiler import CompilationResult
from src.config import Configuration
from src.utils import (
    GenerationHooks,
    PipelineStep,
    ProgressEvent,
    StepArtifact,
    StepState,
)

# The CLI pipeline lives in ``scripts``; the entry point hands it in so ``src`` never imports it.
GenerateRun = Callable[[Configuration, GenerationHooks], bool]


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
    PipelineStep.STATE_DESCRIPTIONS,
    PipelineStep.RM_CRITIC,
    PipelineStep.LABELING,
    PipelineStep.EMBEDDINGS,
)


@dataclass(frozen=True)
class StepSnapshot:
    """Immutable presentation state for one pipeline step."""

    step: PipelineStep
    state: StepState = StepState.PENDING
    elapsed: float | None = None
    detail: str | None = None


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
    step_outputs: tuple[dict[PipelineStep, object], ...] = ()
    error: str | None = None
    tasks: tuple[TaskSnapshot, ...] = ()
    active_task_index: int | None = None
    log_path: Path | None = None
    run_id: int = 0


@dataclass(frozen=True)
class RunRequest:
    """One submission from the UI; ``start`` copies it for the worker thread."""

    environment_markdown: str
    tasks: Sequence[str]
    output_filename: str
    environment_filename: str | None = None
    task_critic: bool = True
    rm_critic: bool = True
    labeling: bool = False
    embeddings: bool = False
    steps_report: bool = False


class RunController:
    """Own one background pipeline run."""

    def __init__(self, generate_rm: GenerateRun) -> None:
        self._generate_rm = generate_rm
        self._lock = Lock()
        self._status = RunState.IDLE
        self._logs: list[str] = []
        self._results: tuple[CompilationResult, ...] = ()
        self._output_paths: tuple[Path, ...] = ()
        self._error: str | None = None
        self._step_outputs: dict[int, dict[PipelineStep, object]] = {}
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
                step_outputs=tuple(
                    dict(self._step_outputs.get(index, {}))
                    for index in range(len(self._output_paths))
                ),
                error=self._error,
                tasks=tuple(self._tasks),
                active_task_index=self._active_task_index,
                log_path=self._log_path,
                run_id=self._run_id,
            )

    def start(self, request: RunRequest) -> None:
        """Start one run using submitted Markdown and UI values."""
        request = replace(request, tasks=tuple(request.tasks))
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
            self._step_outputs = {}
            self._tasks = tuple(
                _initial_task(index, task, request) for index, task in enumerate(request.tasks)
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

    def _run_request(self, request: RunRequest) -> None:
        try:
            with tempfile.TemporaryDirectory(prefix="schema-rm-web-") as temporary_directory:
                environment_path = Path(temporary_directory) / _safe_environment_filename(
                    request.environment_filename
                )
                environment_path.write_text(request.environment_markdown, encoding="utf-8")
                CONFIG = Configuration(
                    environment=environment_path,
                    tasks=list(request.tasks),
                    output=Path(request.output_filename),
                    task_critic=request.task_critic,
                    rm_critic=request.rm_critic,
                    labeling=request.labeling,
                    embeddings=request.embeddings,
                )
                # Keep the run's own artifacts next to its outputs.
                CONFIG.trace_dir = CONFIG.TRACE_PATH
                if request.steps_report:
                    stem = Path(request.output_filename).stem
                    CONFIG.steps_report = CONFIG.REPORT_PATH / f"{stem}-steps.md"
                hooks = GenerationHooks(
                    progress=self._record_progress,
                    event=self._record_event,
                    artifact=self._record_step_output,
                    run_started=self._record_log_path,
                    completion=self._retain_results,
                    failure=self._record_failure,
                )
                succeeded = self._generate_rm(CONFIG, hooks)
            with self._lock:
                if succeeded:
                    self._status = RunState.COMPLETED
                else:
                    self._status = RunState.FAILED
                    if self._error is None:
                        self._error = "Generation failed."
        except Exception as error:
            with self._lock:
                self._status = RunState.FAILED
                self._error = str(error)

    def _record_progress(self, message: str) -> None:
        with self._lock:
            self._logs.append(str(message))

    def _record_failure(self, message: str) -> None:
        with self._lock:
            self._error = message

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
            self._tasks = (
                *self._tasks[: event.task_index],
                TaskSnapshot(
                    index=task.index,
                    task=task.task,
                    attempt=event.attempt,
                    steps=tuple(steps),
                    retry_note=retry_note,
                ),
                *self._tasks[event.task_index + 1 :],
            )
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

    def _record_step_output(self, artifact: StepArtifact) -> None:
        """Keep the newest value per step, so retries end on the accepted attempt."""
        with self._lock:
            if not 0 <= artifact.task_index < len(self._tasks):
                return
            self._step_outputs.setdefault(artifact.task_index, {})[artifact.step] = artifact.value


def _initial_task(index: int, task: str, request: RunRequest) -> TaskSnapshot:
    skipped = {
        PipelineStep.TASK_CRITIC: not request.task_critic,
        PipelineStep.RM_CRITIC: not request.rm_critic,
        PipelineStep.LABELING: not request.labeling,
        PipelineStep.EMBEDDINGS: not request.embeddings,
    }
    return TaskSnapshot(
        index=index,
        task=task,
        steps=tuple(
            StepSnapshot(
                step,
                StepState.SKIPPED if skipped.get(step, False) else StepState.PENDING,
            )
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
