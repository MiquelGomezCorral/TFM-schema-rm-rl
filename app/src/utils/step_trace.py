"""Step traces of one Reward Machine generation run.

Attach :func:`attach_step_trace` to the pipeline's generation hooks and every sub-step
output (clauses, LTLf, DFA, Reward Machine, state descriptions, critic verdicts) is
captured per task and written once, in submission order, as ``<output>.json`` under
``Configuration.TRACE_PATH``.
A trace reopens in the web panel with all of its steps, so it is the portable form of a
run; the optional Markdown report is the same data rendered for reading.

One public entry point: :func:`attach_step_trace` writes the trace when
``CONFIG.trace_dir`` names a folder and adds the Markdown report when
``CONFIG.steps_report`` names a file.
"""

from __future__ import annotations

import html
import json
from collections.abc import Sequence
from pathlib import Path

from src.compiler import CompilationResult
from src.config import Configuration

from .generation_logging import GenerationHooks, PipelineStep, StepArtifact
from .svg import render_structure_svg

# ======================================================================================
#                                     TRACE CONTENT
# ======================================================================================

TRACE_FORMAT = "schema-rm-trace/1"

# Report order, which is not the pipeline order: both critic verdicts come after the
# artifact stages.
STEP_OUTPUT_ORDER = (
    PipelineStep.GENERATE,
    PipelineStep.LTLF,
    PipelineStep.DFA,
    PipelineStep.REWARD_MACHINE,
    PipelineStep.STATE_DESCRIPTIONS,
    PipelineStep.LABELING,
    PipelineStep.EMBEDDINGS,
    PipelineStep.TASK_CRITIC,
    PipelineStep.RM_CRITIC,
)
_STEP_TITLES = {
    PipelineStep.GENERATE: "Validated proposal (clauses)",
    PipelineStep.LTLF: "LTLf formulas",
    PipelineStep.DFA: "MONA DFA",
    PipelineStep.REWARD_MACHINE: "Compiled Reward Machine",
    PipelineStep.STATE_DESCRIPTIONS: "State descriptions",
    PipelineStep.LABELING: "MiniGrid labeling source",
    PipelineStep.EMBEDDINGS: "State embeddings",
    PipelineStep.TASK_CRITIC: "Task critic verdict",
    PipelineStep.RM_CRITIC: "Reward Machine critic verdict",
}
_SVG_WIDTH = 420
_SKIP_NOTE = "skipped (disabled for this run)"


# ======================================================================================
#                                     PUBLIC API
# ======================================================================================


def attach_step_trace(CONFIG: Configuration, hooks: GenerationHooks) -> GenerationHooks:
    """Return hooks that write this run's step trace, and its report when asked.

    Both files are written before the original ``completion`` hook runs, so they are
    already on disk when clients learn the run finished.
    """
    if CONFIG.trace_dir is None and CONFIG.steps_report is None:
        return hooks
    writer = _StepTraceWriter(CONFIG, hooks)
    return GenerationHooks(
        progress=hooks.progress,
        completion=writer.finish,
        event=hooks.event,
        artifact=writer.receive_artifact,
        run_started=hooks.run_started,
        failure=hooks.failure,
    )


def load_step_trace(text: str) -> list[dict[str, object]]:
    """Read one trace file into per-task steps, rejecting anything malformed.

    Each task keeps its own text, the Reward Machine text, the accepted attempt and
    the captured step outputs, which is what the web panel renders on import.
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"Trace is not valid JSON: {error}") from error
    if not isinstance(payload, dict) or payload.get("format") != TRACE_FORMAT:
        raise ValueError(f"Trace must declare format {TRACE_FORMAT!r}")

    raw_tasks = payload.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise ValueError("Trace must list at least one task")

    tasks: list[dict[str, object]] = []
    for index, raw_task in enumerate(raw_tasks, start=1):
        tasks.append(_trace_task(raw_task, index))
    return tasks


# ======================================================================================
#                                     COLLECTION
# ======================================================================================


class _StepTraceWriter:
    """Collect one run's artifacts and write its trace and report when it completes."""

    def __init__(self, CONFIG: Configuration, hooks: GenerationHooks) -> None:
        self._CONFIG = CONFIG
        self._hooks = hooks
        self._artifacts: list[StepArtifact] = []

    def receive_artifact(self, artifact: StepArtifact) -> None:
        """Keep the artifact and pass it on, so other observers keep seeing it."""
        self._artifacts.append(artifact)
        if self._hooks.artifact is not None:
            self._hooks.artifact(artifact)

    def finish(
        self,
        results: tuple[CompilationResult, ...],
        output_paths: tuple[Path, ...],
    ) -> None:
        """Write this run's trace, its report when requested, then forward completion."""
        if self._CONFIG.trace_dir is not None:
            self._write_trace(results, output_paths)
        if self._CONFIG.steps_report is not None:
            self._write_report(results, output_paths)
        if self._hooks.completion is not None:
            self._hooks.completion(results, output_paths)

    # ==================================================================================
    #                                      TRACE
    # ==================================================================================

    def _write_trace(
        self,
        results: tuple[CompilationResult, ...],
        output_paths: tuple[Path, ...],
    ) -> None:
        """Write the portable trace the web panel can reopen with every step."""
        payload = {
            "format": TRACE_FORMAT,
            "environment": Path(self._CONFIG.environment).name if self._CONFIG.environment else "",
            "tasks": [
                self._trace_task(index, result, output_path)
                for index, (result, output_path) in enumerate(
                    zip(results, output_paths, strict=True)
                )
            ],
        }
        path = Path(self._CONFIG.trace_dir) / f"{_trace_stem(self._CONFIG, output_paths)}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _trace_task(
        self,
        task_index: int,
        result: CompilationResult,
        output_path: Path,
    ) -> dict[str, object]:
        """Collect one accepted task's step texts for the trace."""
        attempt = self._accepted_attempt(task_index)
        steps = {
            step.value: render_step_text(step, value)
            for step in STEP_OUTPUT_ORDER
            if (value := self._artifact(task_index, attempt, step)) is not None
        }
        steps.setdefault(PipelineStep.REWARD_MACHINE.value, str(result.text))
        return {
            "task": str(result.proposal.task),
            "attempt": attempt,
            "reward_machine": Path(output_path).name,
            "steps": steps,
        }

    # ==================================================================================
    #                                     REPORT
    # ==================================================================================

    def _write_report(
        self,
        results: tuple[CompilationResult, ...],
        output_paths: tuple[Path, ...],
    ) -> None:
        report_path = Path(self._CONFIG.steps_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        svg_directory = report_path.parent / f"{report_path.stem}-svgs"
        svg_directory.mkdir(parents=True, exist_ok=True)

        lines = [
            "# Reward Machine pipeline report",
            "",
            "One accepted attempt per task; each sub-step is the pipeline's own artifact",
            "output, rendered deterministically in fixed order.",
            "",
        ]
        for index, (result, output_path) in enumerate(zip(results, output_paths, strict=True)):
            lines.extend(self._task_section(index, result, output_path, svg_directory))

        report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _task_section(
        self,
        task_index: int,
        result: CompilationResult,
        output_path: Path,
        svg_directory: Path,
    ) -> list[str]:
        """Render one task heading followed by its sub-steps."""
        attempt = self._accepted_attempt(task_index)
        lines = [
            f"## Task {task_index + 1} — `{html.escape(str(result.proposal.task))}`",
            "",
            f"Accepted on attempt {attempt}; output `{Path(output_path).name}`.",
            "",
        ]

        for number, step in enumerate(STEP_OUTPUT_ORDER, start=1):
            if step is PipelineStep.REWARD_MACHINE:
                lines.extend(self._machine_section(task_index, result, svg_directory, number))
            else:
                lines.extend(self._text_section(task_index, attempt, step, number))
            lines.append("")

        return lines

    def _text_section(
        self,
        task_index: int,
        attempt: int,
        step: PipelineStep,
        number: int,
    ) -> list[str]:
        """Render one fenced-block sub-step, or a skip note when it never ran."""
        value = self._artifact(task_index, attempt, step)
        heading = f"#### {number}. {_STEP_TITLES[step]}"
        if value is None:
            return [heading, "", _SKIP_NOTE]

        language = "text" if step in {PipelineStep.DFA, PipelineStep.LABELING} else "json"
        body = render_step_text(step, value)
        return [heading, "", f"```{language}\n{body}\n```"]

    def _machine_section(
        self,
        task_index: int,
        result: CompilationResult,
        svg_directory: Path,
        number: int,
    ) -> list[str]:
        """Render the compiled text and its graph side by side."""
        svg_path = svg_directory / f"task-{task_index + 1}.svg"
        svg_path.write_text(render_structure_svg(result.reward_machine), encoding="utf-8")
        link = f"{svg_directory.name}/{svg_path.name}"
        heading = f"#### {number}. {_STEP_TITLES[PipelineStep.REWARD_MACHINE]}"

        table = "".join(
            (
                "<table><tbody><tr>",
                f"<td><pre>{html.escape(str(result.text))}</pre></td>",
                f'<td><a href="{link}"><img src="{link}" width="{_SVG_WIDTH}"',
                f' alt="Task {task_index + 1} Reward Machine graph"></a></td>',
                "</tr></tbody></table>",
            )
        )
        return [heading, "", table]

    def _artifact(self, task_index: int, attempt: int, step: PipelineStep) -> object | None:
        for artifact in self._artifacts:
            if (
                artifact.task_index == task_index
                and artifact.attempt == attempt
                and artifact.step is step
            ):
                return artifact.value
        return None

    def _accepted_attempt(self, task_index: int) -> int:
        """Return the last attempt that produced a Reward Machine for this task."""
        return max(
            artifact.attempt
            for artifact in self._artifacts
            if artifact.task_index == task_index and artifact.step is PipelineStep.REWARD_MACHINE
        )


# ======================================================================================
#                                   VALUE RENDERING
# ======================================================================================


def render_step_text(step: PipelineStep, value: object) -> str:
    """Return one captured step value as plain text, shared by trace, report and web UI.

    Values read back from a trace are already text and stay verbatim; live DFA
    dictionaries become a sorted listing and every structured value is JSON, so equal
    runs read identically.
    """
    if isinstance(value, str):
        return value
    if step is PipelineStep.DFA:
        return _render_dfas(value)
    return json.dumps(value, indent=2, sort_keys=True)


def _trace_stem(CONFIG: Configuration, output_paths: Sequence[Path]) -> str:
    """Name the trace after the requested output, or the first written one."""
    if CONFIG.output is not None:
        return Path(CONFIG.output).stem
    return Path(output_paths[0]).stem


def _trace_task(raw_task: object, index: int) -> dict[str, object]:
    """Validate one trace task, keeping the steps this build understands."""
    if not isinstance(raw_task, dict):
        raise ValueError(f"Trace task {index} must be an object")
    raw_steps = raw_task.get("steps")
    if not isinstance(raw_steps, dict):
        raise ValueError(f"Trace task {index} must list its steps")

    steps = {
        step.value: raw_steps[step.value]
        for step in STEP_OUTPUT_ORDER
        if isinstance(raw_steps.get(step.value), str)
    }
    machine = raw_task.get("reward_machine")
    if PipelineStep.REWARD_MACHINE.value not in steps and not isinstance(machine, str):
        raise ValueError(f"Trace task {index} has no Reward Machine text")

    attempt = raw_task.get("attempt")
    return {
        "task": str(raw_task.get("task") or f"Task {index}"),
        "attempt": attempt if isinstance(attempt, int) and not isinstance(attempt, bool) else 1,
        "reward_machine": machine if isinstance(machine, str) else "",
        "steps": steps,
    }


def _render_dfas(dfas: Sequence[dict]) -> str:
    """Render one DFA block per clause, sorted so equal runs read identically."""
    return "\n\n".join(_render_dfa(dfa) for dfa in dfas)


def _render_dfa(dfa: dict) -> str:
    transitions = sorted(
        (str(source), str(guard), str(destination))
        for (source, guard), destination in dfa["transitions"].items()
    )
    lines = [
        "accepting_states: " + ", ".join(sorted(str(state) for state in dfa["accepting_states"])),
        "alphabet: " + ", ".join(sorted(str(symbol) for symbol in dfa["alphabet"])),
        f"initial_state: {dfa['initial_state']}",
        "states: " + ", ".join(sorted(str(state) for state in dfa["states"])),
        "transitions:",
    ]
    lines.extend(
        f"  ({source}, {guard}) -> {destination}" for source, guard, destination in transitions
    )
    return "\n".join(lines)
