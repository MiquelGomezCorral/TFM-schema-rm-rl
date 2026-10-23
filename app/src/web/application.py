"""Dash application factory and focused callback registration."""

import base64
import json
import re
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath

import dash_cytoscape as cyto
from dash import ALL, Dash, Input, Output, State, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate

from src.compiler import CompilationResult, parse_reward_machine
from src.compiler.reward_machine import RewardMachineStructure
from src.config import REASONING_LEVELS, Configuration
from src.models import CODE_FILE_NAME
from src.utils import (
    CYTOSCAPE_STYLESHEET,
    STEP_OUTPUT_ORDER,
    PipelineStep,
    StepState,
    derive_output_names,
    load_step_trace,
    render_elements_html,
    render_elements_svg,
    reward_machine_to_elements,
)

from .components import (
    CRITIC_OPTIONS,
    EMBEDDINGS_OPTIONS,
    FOCUS_OUTPUT_REGION_CLASS,
    FOCUS_WORKSPACE_CLASS,
    GENERATE_BUTTON_CLASS,
    INPUT_REGION_CLASS,
    LABELING_OPTIONS,
    OUTPUT_REGION_CLASS,
    RECURRENT_SOFT_PENALTY_OPTIONS,
    RUN_SIDEBAR_CLASS,
    STATE_DESCRIPTIONS_OPTIONS,
    STATUS_CLASSES,
    STEPS_REPORT_OPTIONS,
    STOP_BUTTON_CLASS,
    TOOLBAR_ICON_SIZE_CLASS,
    WORKSPACE_CLASS,
    _icon,
    create_layout,
    render_issues,
    render_steps,
    result_bodies,
    result_tabs,
    segment_class,
    task_row,
)
from .runner import RunController, RunRequest, RunSnapshot, RunState

IMPORTED_RM_VALUE = "imported"

# Summary, tab strip, bodies, graph elements, export name, then both export buttons' disabled.
# The summary is a list of rows once an output is selected, and one plain message when it is not.
_PanelUpdate = tuple[str | list, object, list, list, str | None, bool, bool]

_OUTPUT_SUFFIX = ".rm"
_DEFAULT_OUTPUT_STEM = "reward-machine"
_DEFAULT_ENVIRONMENT_NAME = "environment.md"
_ENVIRONMENT_STEM = "environment"
_UNSAFE_OUTPUT_NAME = re.compile(r"[^A-Za-z0-9._-]+")
_ENVIRONMENT_TITLE = re.compile(r"^#\s+(\S.*)$", re.MULTILINE)
# A tasks manifest (examples/arm-fm/*/tasks.json) names the environment, points at its
# Markdown relative to the repository root, and lists the tasks to compile.
_MANIFEST_FIELDS = ("env", "env_description", "tasks")
_REPO_ROOT = Path(__file__).resolve().parents[3]

# Weights the three Tailwind font stacks use; the stacks fall back to system fonts offline.
FONTS_STYLESHEET = (
    "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600"
    "&family=JetBrains+Mono:wght@400;500&family=Sora:wght@600&display=swap"
)

_UPLOAD_STATUS_CLASS = "field-hint text-xs text-muted"
_UPLOAD_ERROR_CLASS = "field-hint text-xs text-danger-ink"

SUMMARY_ROW_CLASS = "summary-row flex gap-2.5 border-b border-border py-1.5"
SUMMARY_LABEL_CLASS = "summary-label w-[76px] shrink-0 font-mono text-xs text-muted"
SUMMARY_VALUE_CLASS = "summary-value min-w-0 font-mono text-xs text-text wrap-anywhere"

_EXPORT_CLIENT_SCRIPT = """
function (svg_clicks, html_clicks) {
    if (!(svg_clicks || html_clicks) || !window.cy) {
        return window.dash_clientside.no_update;
    }
    document.getElementById("graph-export-menu").open = false;
    const format = window.dash_clientside.callback_context.triggered_id === "graph-export-html-button"
        ? "html"
        : "svg";
    const positions = Object.fromEntries(
        window.cy.nodes().map((node) => {
            const point = node.position();
            return [node.id(), [point.x, point.y]];
        })
    );
    return {format: format, elements: window.cy.elements().jsons(), positions: positions};
}
"""

# Hover and transition panel come from assets/rm_graph.js, shared with the HTML export.
# Dash rewrites the elements on every step tab or status change, and the graph component
# writes them back with its own fields, so the panel closes only when a signature of the
# element data (ids, states, transition cases) differs from the last one stored.
_ATTACH_CLIENT_SCRIPT = """
function (elements, previous_signature) {
    const text = JSON.stringify((elements || []).map((element) => element.data));
    let hash = 0;
    for (let index = 0; index < text.length; index++) {
        hash = (hash * 31 + text.charCodeAt(index)) | 0;
    }
    const signature = text.length + ":" + hash;
    if (window.cy && window.rmGraph) {
        const graph = window.rmGraph.attach(
            window.cy, document.getElementById("rm-graph").parentElement
        );
        if (signature !== previous_signature) {
            graph.close();
        }
    }
    return signature;
}
"""

_EXPORT_FORMATS = {
    "svg": (render_elements_svg, "image/svg+xml"),
    "html": (render_elements_html, "text/html"),
}


def create_app(controller: RunController) -> Dash:
    """Create one local Dash app driven by ``controller``."""
    cyto.load_extra_layouts()
    assets_folder = Path(__file__).resolve().parents[2] / "assets"
    app = Dash(
        __name__,
        assets_folder=str(assets_folder),
        title="Reward Machine compiler",
        external_stylesheets=[FONTS_STYLESHEET],
    )
    app.layout = create_layout(CYTOSCAPE_STYLESHEET)

    _register_input_callbacks(app)
    _register_start_callback(app, controller)
    _register_stop_callback(app, controller)
    _register_poll_callback(app, controller)
    _register_issue_callback(app, controller)
    _register_result_callback(app, controller)
    _register_graph_callbacks(app)
    return app


# ======================================================================================
#                                  CALLBACK REGISTRATION
# ======================================================================================


def _register_input_callbacks(app: Dash) -> None:
    app.callback(
        Output("environment-markdown", "value"),
        Output("upload-status", "children"),
        Output("output-filename", "value"),
        Output("task-rows", "children", allow_duplicate=True),
        Input("environment-upload", "contents"),
        State("environment-upload", "filename"),
        prevent_initial_call=True,
    )(_load_environment)
    app.callback(
        Output("environment-code-markdown", "value"),
        Output("code-upload-status", "children"),
        Input("environment-code-upload", "contents"),
        State("environment-code-upload", "filename"),
        prevent_initial_call=True,
    )(_load_environment_code)
    app.callback(
        Output("imported-reward-machine", "data"),
        Output("reward-machine-upload-status", "children"),
        Output("reward-machine-upload-status", "className"),
        Input("reward-machine-upload", "contents"),
        State("reward-machine-upload", "filename"),
        prevent_initial_call=True,
    )(_load_reward_machine)
    app.callback(
        Output("task-rows", "children"),
        Input("add-task", "n_clicks"),
        Input({"type": "remove-task", "index": ALL}, "n_clicks"),
        State({"type": "task-input", "index": ALL}, "value"),
        prevent_initial_call=True,
    )(_update_task_rows)
    app.callback(
        Output("attempts", "value"),
        Output("attempts-decrement", "disabled"),
        Output("attempts-increment", "disabled"),
        Input("attempts-decrement", "n_clicks"),
        Input("attempts-increment", "n_clicks"),
        Input("attempts", "value"),
        Input("attempts", "disabled"),
        prevent_initial_call=True,
    )(_step_attempts)
    app.callback(
        Output("reasoning-level", "data"),
        Output({"type": "reasoning-option", "index": ALL}, "className"),
        Output({"type": "reasoning-option", "index": ALL}, "aria-checked"),
        Input({"type": "reasoning-option", "index": ALL}, "n_clicks"),
        State("reasoning-level", "data"),
        State({"type": "reasoning-option", "index": ALL}, "id"),
        prevent_initial_call=True,
    )(_select_reasoning)


def _register_start_callback(app: Dash, controller: RunController) -> None:
    @app.callback(
        Output("run-feedback", "children"),
        Input("generate-button", "n_clicks"),
        State("environment-markdown", "value"),
        State("environment-upload", "filename"),
        State("environment-upload", "contents"),
        State({"type": "task-input", "index": ALL}, "value"),
        State("output-filename", "value"),
        State("environment-code-markdown", "value"),
        State("reasoning-level", "data"),
        State("attempts", "value"),
        State("critic-options", "value"),
        State("recurrent-soft-penalty-toggle", "value"),
        State("steps-report-toggle", "value"),
        State("descriptions-toggle", "value"),
        State("labeling-toggle", "value"),
        State("embeddings-toggle", "value"),
        prevent_initial_call=True,
    )
    def start_run(
        _n_clicks: int | None,
        markdown: str | None,
        filename: str | None,
        upload_contents: str | None,
        task_values: list[str | None],
        output_filename: str | None,
        *options: object,
    ) -> str:
        """Start a run from the form.

        ``options`` are the code file text, the reasoning level, the attempt limit, then the six
        checklist values in layout order.
        """
        (
            code,
            reasoning,
            attempts,
            critic,
            recurrent_soft_penalty,
            steps_report,
            state_descriptions,
            labeling,
            embeddings,
        ) = options
        if not (markdown or "").strip():
            return "Enter or upload environment Markdown first."
        tasks = tuple((value or "").strip() for value in task_values or [])
        if not tasks or any(not task for task in tasks):
            return "Every task row must contain text."
        if attempts not in Configuration.ATTEMPT_LIMITS:
            limits = Configuration.ATTEMPT_LIMITS
            return (
                f"Enter a whole number from {limits.start} to {limits.stop - 1} critic rejections."
            )
        if reasoning not in REASONING_LEVELS:
            return "Choose a reasoning level."
        submitted_name = (output_filename or "").strip()
        output_name = _available_output_filename(submitted_name, len(tasks))
        request = RunRequest(
            environment_markdown=markdown,
            tasks=tasks,
            output_filename=output_name,
            environment_filename=_resolve_environment_filename(markdown, upload_contents, filename),
            environment_code=code or "",
            reasoning=reasoning,
            attempts=int(attempts),
            critic=_is_checked(critic, "critic"),
            recurrent_soft_penalty=_is_checked(recurrent_soft_penalty, "recurrent_soft_penalty"),
            labeling=_is_checked(labeling, "labeling"),
            state_descriptions=_is_checked(state_descriptions, "state_descriptions"),
            embeddings=_is_checked(embeddings, "embeddings"),
            steps_report=_is_checked(steps_report, "steps_report"),
        )
        try:
            controller.start(request)
        except (RuntimeError, ValueError) as error:
            return f"Could not start run: {error}"
        if output_name == submitted_name:
            return "Run started; progress will appear in the log."
        return (
            f"Run started as {output_name}; the output name was adjusted automatically "
            "to the next free file name."
        )


def _register_stop_callback(app: Dash, controller: RunController) -> None:
    @app.callback(
        Output("run-feedback", "children", allow_duplicate=True),
        Input("stop-run", "submit_n_clicks"),
        prevent_initial_call=True,
    )
    def stop_run(_submit_n_clicks: int | None) -> str:
        """Stop the running generation after its current provider request."""
        if controller.stop():
            return "Stopping after the current request…"
        return "No run is active."


def _register_poll_callback(app: Dash, controller: RunController) -> None:
    @app.callback(
        Output("run-status", "children"),
        Output("run-status", "className"),
        Output("run-status-reason", "children"),
        Output("run-log", "children"),
        Output("environment-upload", "disabled"),
        Output("environment-markdown", "disabled"),
        Output("environment-code-upload", "disabled"),
        Output("environment-code-markdown", "disabled"),
        Output({"type": "task-input", "index": ALL}, "disabled"),
        Output("add-task", "disabled"),
        Output({"type": "remove-task", "index": ALL}, "disabled"),
        Output("output-filename", "disabled"),
        Output("generate-button", "disabled"),
        Output("generate-button", "className"),
        Output("stop-run-button", "className"),
        Output("stop-run-button", "disabled"),
        Output("critic-options", "options"),
        Output({"type": "reasoning-option", "index": ALL}, "disabled"),
        Output("attempts", "disabled"),
        Output("output-selector", "options"),
        Output("output-selector", "value"),
        Output("output-selector", "disabled"),
        Output("run-steps", "children"),
        Output("task-selection", "data"),
        Output("recurrent-soft-penalty-toggle", "options"),
        Output("steps-report-toggle", "options"),
        Output("descriptions-toggle", "options"),
        Output("labeling-toggle", "options"),
        Output("embeddings-toggle", "options"),
        Input("poll-interval", "n_intervals"),
        Input("output-selector", "value"),
        State({"type": "remove-task", "index": ALL}, "id"),
        Input("run-prev", "n_clicks", allow_optional=True),
        Input("run-next", "n_clicks", allow_optional=True),
        Input({"type": "task-dot", "index": ALL}, "n_clicks"),
        State("task-selection", "data"),
        Input("imported-reward-machine", "data"),
        State("run-status", "children"),
        State("run-status-reason", "children"),
    )
    def poll_run(
        _n_intervals: int,
        selected_index: int | str | None = None,
        remove_ids: list[dict[str, int]] | None = None,
        _previous_clicks: int | None = None,
        _next_clicks: int | None = None,
        _dot_clicks: list[int | None] | None = None,
        selection_data: dict[str, int | None] | None = None,
        imported_data: dict[str, str] | None = None,
        *previous_states: str | None,
    ) -> tuple[object, ...]:
        previous_status = previous_states[0] if previous_states else None
        previous_reason = previous_states[1] if len(previous_states) > 1 else None
        snapshot = controller.snapshot()
        word, class_name, reason = _run_status(snapshot)
        if (word, reason) == (previous_status, previous_reason):
            # Only a real status change may wake dependents, or every poll would re-render them.
            status: tuple[object, object, object] = (no_update, no_update, no_update)
        else:
            status = (word, class_name, reason)
        panels = _poll_panels(snapshot, selected_index, remove_ids, selection_data, imported_data)
        return *status, *panels


def _register_issue_callback(app: Dash, controller: RunController) -> None:
    @app.callback(
        Output("run-warnings-tab", "label"),
        Output("run-warnings-tab", "disabled"),
        Output("run-warnings", "children"),
        Output("run-errors-tab", "label"),
        Output("run-errors-tab", "disabled"),
        Output("run-errors", "children"),
        Output("run-tabs", "value"),
        Output("issues-shown", "data"),
        Input("poll-interval", "n_intervals"),
        State("issues-shown", "data"),
        State("run-tabs", "value"),
    )
    def poll_issues(_n_intervals: int, shown: list | None, open_tab: str | None) -> tuple:
        """Fill the Warnings and Errors tabs, or change nothing while they match what is shown.

        Skipping the update keeps a list still while the user reads it. A tab that
        empties while open falls back to Steps, so no disabled tab stays selected.
        """
        warnings, errors = _run_issues(controller.snapshot())
        if [warnings, errors] == (shown or []):
            return (no_update,) * 8
        open_entries = {"warnings": warnings, "errors": errors}.get(open_tab or "", (True,))
        tab = no_update if open_entries else "steps"
        return (
            _issue_label("Warnings", warnings),
            not warnings,
            render_issues(warnings, "warning"),
            _issue_label("Errors", errors),
            not errors,
            render_issues(errors, "error"),
            tab,
            [warnings, errors],
        )


def _issue_label(name: str, entries: list[str]) -> str:
    return f"{name} · {len(entries)}" if entries else name


def _run_issues(snapshot: RunSnapshot) -> tuple[list[str], list[str]]:
    """Split what the run reported into warnings (the run went on) and errors (it stopped).

    A task's failed attempts count as warnings while it keeps retrying; the last
    failure of a task that ended failed is an error, as is the run's own error.
    """
    warnings = list(snapshot.warnings)
    errors: list[str] = []
    # While running, a failed task is between attempts: its failure is still a warning.
    ended = snapshot.status not in {RunState.RUNNING, RunState.STOPPED}
    for task in snapshot.tasks:
        notes = [f"Task {task.index + 1} · {note}" for note in task.failures]
        if ended and task.state is StepState.FAILED and notes:
            errors.append(notes.pop())
        warnings.extend(notes)
    if snapshot.error and snapshot.status is not RunState.STOPPED:
        errors.append(snapshot.error)
    return warnings, errors


def _register_result_callback(app: Dash, controller: RunController) -> None:
    @app.callback(
        Output("result-summary", "children"),
        Output("result-tabs", "children"),
        Output("result-bodies", "children"),
        Output("rm-graph", "elements"),
        Output("graph-export-name", "data"),
        Output("graph-export-button", "disabled"),
        Output("graph-export-html-button", "disabled"),
        Input("output-selector", "value"),
        Input("imported-reward-machine", "data"),
        Input("run-status", "children"),
        Input("result-tabs", "value"),
        State("rm-graph", "elements"),
    )
    def render_selected_result(
        selected_index: int | str | None,
        imported_data: dict[str, str] | None = None,
        _run_status: str | None = None,
        selected_step: str | None = None,
        drawn_elements: list | None = None,
    ) -> _PanelUpdate:
        step = _selected_step(selected_step)
        if selected_index is None:
            panel = _empty_panel("No completed output selected.", step)
        elif _is_imported_value(selected_index):
            panel = _render_imported(imported_data, _imported_task_index(selected_index), step)
        else:
            panel = _render_generated(controller.snapshot(), selected_index, step)
        return _keep_drawn_graph(panel, drawn_elements)


def _register_graph_callbacks(app: Dash) -> None:
    app.callback(
        Output("graph-focus-state", "data"),
        Output("workspace", "className"),
        Output("input-region", "className"),
        Output("run-sidebar", "className"),
        Output("output-region", "className"),
        Output("graph-focus-toggle", "children"),
        Output("graph-focus-toggle", "aria-pressed"),
        Input("graph-focus-toggle", "n_clicks"),
        State("graph-focus-state", "data"),
        prevent_initial_call=True,
    )(_toggle_graph_focus)
    app.callback(
        Output("graph-download", "data"),
        Input("graph-export-payload", "data"),
        State("graph-export-name", "data"),
        prevent_initial_call=True,
    )(_export_graph)
    app.clientside_callback(
        _EXPORT_CLIENT_SCRIPT,
        Output("graph-export-payload", "data"),
        Input("graph-export-button", "n_clicks"),
        Input("graph-export-html-button", "n_clicks"),
        prevent_initial_call=True,
    )
    app.clientside_callback(
        _ATTACH_CLIENT_SCRIPT,
        Output("graph-attached", "data"),
        Input("rm-graph", "elements"),
        State("graph-attached", "data"),
    )


# ======================================================================================
#                                  INPUT CALLBACK BODIES
# ======================================================================================


def _load_environment(
    contents: str | None, filename: str | None
) -> tuple[object, str, object, object]:
    if not contents:
        raise PreventUpdate
    try:
        upload = _uploaded_environment(contents, filename)
    except (ValueError, UnicodeDecodeError, OSError, RecursionError) as error:
        return no_update, f"Could not load {filename or 'the file'}: {error}", no_update, no_update
    if upload.tasks is None:
        rows: object = no_update
        status = f"Loaded {filename or _DEFAULT_ENVIRONMENT_NAME}; edit the text before generating."
    else:
        rows = [task_row(index, task) for index, task in enumerate(upload.tasks)]
        status = (
            f"Loaded {len(upload.tasks)} tasks and {upload.environment_filename} from {filename}; "
            "edit before generating."
        )
    return (
        upload.markdown,
        status,
        _available_output_filename(upload.output_stem, len(upload.tasks or ())),
        rows,
    )


def _load_environment_code(contents: str | None, filename: str | None) -> tuple[object, str]:
    if not contents:
        raise PreventUpdate
    try:
        text = _decode_uploaded_markdown(contents)
    except (ValueError, UnicodeDecodeError) as error:
        return no_update, f"Could not load {filename or 'the file'}: {error}"
    return text, f"Loaded {filename or CODE_FILE_NAME}; edit the text before generating."


def _load_reward_machine(contents: str | None, filename: str | None) -> tuple[object, str, str]:
    if not contents:
        raise PreventUpdate
    if not filename or not filename.lower().endswith((".rm", ".json")):
        return (
            no_update,
            "Could not load Reward Machine: choose a .rm or trace .json file.",
            _UPLOAD_ERROR_CLASS,
        )
    try:
        text = _decode_uploaded_markdown(contents)
        if filename.lower().endswith(".json"):
            payload = _trace_payload(filename, text)
        else:
            parse_reward_machine(text)
            payload = {"filename": filename, "text": text}
    except (ValueError, UnicodeDecodeError) as error:
        return no_update, f"Could not load Reward Machine: {error}", _UPLOAD_ERROR_CLASS
    tasks = payload.get("tasks")
    count = len(tasks) if isinstance(tasks, list) else 0
    note = f"Loaded {filename}: {count} task(s) with every pipeline step; select one below."
    return (
        payload,
        note if count else f"Loaded {filename}; select it below.",
        _UPLOAD_STATUS_CLASS,
    )


def _update_task_rows(
    _add_clicks: int | None,
    _remove_clicks: list[int | None],
    values: list[str | None],
) -> list:
    # Rows another callback adds (a tasks manifest) re-fire this one with n_clicks=0.
    if not ctx.triggered or not ctx.triggered[0].get("value"):
        raise PreventUpdate
    rows = [value or "" for value in values or []]
    triggered = ctx.triggered_id
    if triggered == "add-task":
        rows.append("")
    elif isinstance(triggered, dict) and len(rows) > 1:
        index = triggered.get("index")
        if isinstance(index, int) and 0 <= index < len(rows):
            rows.pop(index)
    if not rows:
        rows = [""]
    return [task_row(index, value) for index, value in enumerate(rows)]


def _step_attempts(
    _decrement_clicks: int | None,
    _increment_clicks: int | None,
    value: object,
    locked: bool | None,
) -> tuple[object, bool, bool]:
    """Move the rejection limit one step and keep both buttons inside its bounds.

    A click on a button moves the value; a typed or pasted value is kept untouched, so only
    the two ``disabled`` flags are recomputed and the pair never freezes.
    """
    limits = Configuration.ATTEMPT_LIMITS
    if locked:
        return no_update, True, True
    current = value if isinstance(value, int) and not isinstance(value, bool) else None
    stepped = no_update
    if current is not None and limits.start <= current <= limits.stop - 1:
        if ctx.triggered_id == "attempts-decrement":
            stepped = max(current - 1, limits.start)
        elif ctx.triggered_id == "attempts-increment":
            stepped = min(current + 1, limits.stop - 1)
    unknown = current is None
    return (
        stepped,
        unknown or current <= limits.start,
        unknown or current >= limits.stop - 1,
    )


def _select_reasoning(
    _clicks: list[int | None], current: str | None, ids: list[dict[str, str]]
) -> tuple[object, list[str], list[bool]]:
    """Return the level one segment click selects and the whole track's visible state.

    One handler serves the group, so the clicked level comes from the trigger id; a trigger
    that is not a known segment keeps the stored level. The store only changes on a new level,
    while class names and aria-checked are returned for every segment in ``ids`` order.
    """
    triggered = _triggered_id()
    clicked = triggered.get("index") if isinstance(triggered, Mapping) else None
    level = clicked if clicked in REASONING_LEVELS else current
    return (
        level if level != current else no_update,
        [segment_class(item["index"] == level) for item in ids],
        [item["index"] == level for item in ids],
    )


def _is_checked(options: list[str] | None, name: str) -> bool:
    return bool(options and name in options)


# ======================================================================================
#                                  RUN CALLBACK BODIES
# ======================================================================================


def _run_status(snapshot: RunSnapshot) -> tuple[str, str, str]:
    """Return the status word, its CSS classes and the failure reason.

    The pill stays one word wide; a failure puts its reason in the status popover instead.
    A stop is a neutral outcome, so it keeps no reason: the log holds the error text.
    """
    if snapshot.status is RunState.STOPPED:
        return "Stopped", STATUS_CLASSES["stopped"], ""
    stopping = snapshot.stopping and snapshot.status is RunState.RUNNING
    word = "Stopping…" if stopping else snapshot.status.value.capitalize()
    return word, STATUS_CLASSES[snapshot.status.value], snapshot.error or ""


def _slot_class(base: str, hidden: bool) -> str:
    """Return a button's class list, hidden while the other state of the slot owns it.

    ``!hidden`` beats the button's own ``inline-flex``, which the plain ``hidden`` utility
    does not: both are unlayered display utilities and ``inline-flex`` comes later.
    """
    return f"{base} !hidden" if hidden else base


def _poll_panels(
    snapshot: RunSnapshot,
    selected_index: int | str | None,
    remove_ids: list[dict[str, int]] | None,
    selection_data: dict[str, int | None] | None,
    imported_data: dict[str, str] | None,
) -> tuple[object, ...]:
    """Return every poll output after the status pair."""
    active = snapshot.status is RunState.RUNNING
    imported = _imported_reward_machine(imported_data)
    options = [
        {"label": str(path), "value": index} for index, path in enumerate(snapshot.output_paths)
    ]
    if imported is not None:
        options.extend(_imported_options(imported))
    trigger = _triggered_id()
    selected = _selected_output(snapshot, imported, selected_index, trigger)
    task_selected, next_selection = _task_selection(
        snapshot, selection_data, trigger, selected_index
    )
    # The chevrons and dots lead the selector; an imported selection leaves them where they are.
    if _is_task_navigation(trigger) and _is_generated_index(
        task_selected, len(snapshot.output_paths)
    ):
        selected = task_selected
    remove_ids = remove_ids or []
    return (
        "\n".join(snapshot.logs) if snapshot.logs else "No run yet.",
        active,
        active,
        active,
        active,
        [active] * len(remove_ids),
        active,
        [active or item.get("index") == 0 for item in remove_ids],
        active,
        active,
        _slot_class(GENERATE_BUTTON_CLASS, active),
        _slot_class(STOP_BUTTON_CLASS, not active),
        active and snapshot.stopping,
        _locked(CRITIC_OPTIONS, active),
        [active] * len(REASONING_LEVELS),
        active,
        options,
        selected if selected != selected_index else no_update,
        not bool(options),
        render_steps(snapshot.tasks, task_selected),
        next_selection,
        _locked(RECURRENT_SOFT_PENALTY_OPTIONS, active),
        _locked(STEPS_REPORT_OPTIONS, active),
        _locked(STATE_DESCRIPTIONS_OPTIONS, active),
        _locked(LABELING_OPTIONS, active),
        _locked(EMBEDDINGS_OPTIONS, active),
    )


def _locked(options: list[dict[str, str]], disabled: bool) -> list[dict[str, object]]:
    return [{**option, "disabled": disabled} for option in options]


def _triggered_id() -> str | dict | None:
    try:
        return ctx.triggered_id
    except Exception:
        return None


def _selected_output(
    snapshot: RunSnapshot,
    imported: dict[str, object] | None,
    selected_index: int | str | None,
    trigger: str | dict | None,
) -> int | str | None:
    """Keep a valid selection, otherwise prefer the imported machine, then the first output."""
    generated = _is_generated_index(selected_index, len(snapshot.output_paths))
    if imported is None:
        return selected_index if generated else (0 if snapshot.output_paths else None)
    # The options list owns which value names a task of a multi-task trace; selecting the entry it
    # lists first keeps the selector showing a label instead of an empty box.
    if trigger == "imported-reward-machine" or not (
        generated or _is_imported_value(selected_index)
    ):
        return str(_imported_options(imported)[0]["value"])
    return selected_index


def _is_task_navigation(trigger: str | dict | None) -> bool:
    return trigger in {"run-prev", "run-next"} or (
        isinstance(trigger, dict) and trigger.get("type") == "task-dot"
    )


def _task_selection(
    snapshot: RunSnapshot,
    selection_data: dict[str, int | None] | None,
    trigger: str | dict | None,
    selected_output: int | str | None,
) -> tuple[int, dict[str, int | None]]:
    """Return the task to show and the selection state to store for the next poll."""
    selection_data = selection_data or {}
    total_tasks = len(snapshot.tasks)
    if selection_data.get("run_id") != snapshot.run_id:
        task_selected = 0
        last_active = None
    else:
        task_selected = selection_data.get("selected", 0) or 0
        last_active = selection_data.get("last_active")
    task_selected = max(0, min(task_selected, total_tasks - 1)) if total_tasks else 0

    task_selected, navigated = _navigate(task_selected, total_tasks, trigger)
    if trigger == "output-selector" and _is_generated_index(
        selected_output, min(total_tasks, len(snapshot.output_paths))
    ):
        task_selected, navigated = selected_output, True
    if (
        not navigated
        and snapshot.active_task_index is not None
        and snapshot.active_task_index != last_active
        and task_selected == last_active
    ):
        task_selected = snapshot.active_task_index
    next_selection = {
        "selected": task_selected,
        "last_active": snapshot.active_task_index,
        "run_id": snapshot.run_id,
    }
    return task_selected, next_selection


def _navigate(task_selected: int, total_tasks: int, trigger: str | dict | None) -> tuple[int, bool]:
    """Apply a previous, next or dot click; the flag says whether one was applied."""
    if total_tasks > 1 and trigger == "run-prev":
        return max(0, task_selected - 1), True
    if total_tasks > 1 and trigger == "run-next":
        return min(total_tasks - 1, task_selected + 1), True
    if isinstance(trigger, dict) and trigger.get("type") == "task-dot":
        index = trigger.get("index")
        if isinstance(index, int) and 0 <= index < total_tasks:
            return index, True
    return task_selected, False


def _render_imported(
    imported_data: dict[str, str] | None, task_index: int | None, step: PipelineStep
) -> _PanelUpdate:
    imported = _imported_reward_machine(imported_data)
    task = _imported_task(imported, task_index)
    if imported is None or task is None:
        return _empty_panel("No imported Reward Machine selected.", step)
    raw_steps = dict(task["steps"])
    steps = {
        step_key: raw_steps[step_key.value]
        for step_key in STEP_OUTPUT_ORDER
        if isinstance(raw_steps.get(step_key.value), str)
    }
    machine_text = str(steps.get(PipelineStep.REWARD_MACHINE) or imported["text"])
    try:
        reward_machine = parse_reward_machine(machine_text)
    except ValueError as error:
        return _empty_panel(f"Could not render imported Reward Machine: {error}", step)
    name = str(task["reward_machine"]) or str(imported["filename"])
    label = str(task["task"])
    summary = [_summary_row("Imported", imported["filename"])]
    if label:
        summary.append(_summary_row("Task", label))
    return _panel(
        summary,
        steps,
        step,
        _graph_elements(reward_machine),
        Path(name).stem,
    )


def _render_generated(
    snapshot: RunSnapshot, selected_index: int | str, step: PipelineStep
) -> _PanelUpdate:
    if not snapshot.results:
        return _empty_panel("No completed output selected.", step)
    if not _is_generated_index(selected_index, len(snapshot.results)):
        # Nothing selected yet, so show the newest completed output.
        selected_index = len(snapshot.results) - 1
    result = snapshot.results[selected_index]
    output_path = snapshot.output_paths[selected_index]
    steps = dict(snapshot.step_outputs[selected_index])
    steps.setdefault(PipelineStep.REWARD_MACHINE, result.text)
    return _panel(
        _result_summary(result, output_path),
        steps,
        step,
        _graph_elements(result.reward_machine),
        output_path.stem,
    )


def _keep_drawn_graph(panel: _PanelUpdate, drawn_elements: list | None) -> _PanelUpdate:
    """Leave the graph alone when it already shows this machine.

    A step tab click or a status poll renders the same machine again; rewriting its elements
    would redraw the graph and drop the positions the user dragged. Positions live outside
    ``data``, so equal ``data`` means the same machine.
    """
    summary, tabs, bodies, elements, *rest = panel
    drawn = [element["data"] for element in drawn_elements or []]
    if drawn == [element["data"] for element in elements]:
        elements = no_update
    return summary, tabs, bodies, elements, *rest


@lru_cache(maxsize=16)
def _laid_out_elements(machine: RewardMachineStructure) -> list:
    return reward_machine_to_elements(machine)


def _graph_elements(machine: RewardMachineStructure) -> list:
    """Return the graph elements of a machine, laid out once.

    A step tab click or a status poll renders the same machine again, and the structure
    is frozen, so the layout is cached per machine; the caller gets its own copy.
    """
    return deepcopy(_laid_out_elements(machine))


def _result_summary(result: CompilationResult, output_path: Path) -> list:
    """Describe one completed output: its path, task, compile warnings and artifacts."""
    rows = [_summary_row("Output", output_path), _summary_row("Task", result.proposal.task)]
    rows.extend(_summary_row("Warning", warning) for warning in result.warnings)
    if result.bundle_path:
        rows.append(_summary_row("Bundle", result.bundle_path))
    if result.embedding_settings:
        model = result.embedding_settings.get("model")
        dimension = result.embedding_settings.get("dimension")
        rows.append(_summary_row("Embedding", f"{model} dim={dimension}"))
    if result.embedding_path:
        rows.append(_summary_row("Embeddings", result.embedding_path))
    return rows


def _summary_row(label: str, value: object) -> html.Div:
    """Build one summary row; the fixed label width keeps every value aligned."""
    return html.Div(
        [
            html.Dt(label, className=SUMMARY_LABEL_CLASS),
            html.Dd(str(value), className=SUMMARY_VALUE_CLASS),
        ],
        className=SUMMARY_ROW_CLASS,
    )


def _is_generated_index(value: object, generated_count: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value < generated_count


def _is_imported_value(value: object) -> bool:
    return value == IMPORTED_RM_VALUE or _imported_task_index(value) is not None


# ======================================================================================
#                                 GRAPH CALLBACK BODIES
# ======================================================================================


def _toggle_graph_focus(
    _n_clicks: int | None,
    focused: bool | None,
) -> tuple[bool, str, str, str, str, list, bool]:
    if not focused:
        return (
            True,
            FOCUS_WORKSPACE_CLASS,
            "hidden",
            "hidden",
            FOCUS_OUTPUT_REGION_CLASS,
            [_icon("minimize", TOOLBAR_ICON_SIZE_CLASS), "Exit focus"],
            True,
        )
    return (
        False,
        WORKSPACE_CLASS,
        INPUT_REGION_CLASS,
        RUN_SIDEBAR_CLASS,
        OUTPUT_REGION_CLASS,
        [_icon("focus", TOOLBAR_ICON_SIZE_CLASS), "Focus graph"],
        False,
    )


def _export_graph(payload: object, name: object) -> object:
    """Render the live graph as SVG or HTML, keeping the node positions the user arranged."""
    if not isinstance(payload, dict) or payload.get("format") not in _EXPORT_FORMATS:
        raise PreventUpdate
    elements = _export_elements(payload.get("elements"))
    positions = _export_positions(payload.get("positions"))
    if elements is None or positions is None:
        raise PreventUpdate
    export_format = payload["format"]
    render, mime_type = _EXPORT_FORMATS[export_format]
    document = render(elements, positions or None)
    return dcc.send_string(document, _export_filename(name, export_format), type=mime_type)


# ======================================================================================
#                                      HELPERS
# ======================================================================================


def _decode_uploaded_markdown(contents: str) -> str:
    """Decode one Dash upload payload as UTF-8 text."""
    _, encoded = contents.split(",", 1)
    return base64.b64decode(encoded, validate=True).decode("utf-8")


def _selected_step(value: object) -> PipelineStep:
    """Return the step a tab selection points at, defaulting to the Reward Machine."""
    try:
        return PipelineStep(value)
    except ValueError:
        return PipelineStep.REWARD_MACHINE


def _panel(
    summary: str | list,
    steps: Mapping[PipelineStep, object],
    selected: PipelineStep,
    elements: list,
    export_name: str | None,
) -> _PanelUpdate:
    """Return one panel update: summary, tab strip, stacked bodies and the graph."""
    return (
        summary,
        result_tabs(steps),
        result_bodies(steps, selected),
        elements,
        export_name,
        not elements,
        not elements,
    )


def _empty_panel(summary: str | list, selected: PipelineStep) -> _PanelUpdate:
    """Return a panel update that shows only a message."""
    return _panel(summary, {}, selected, [], None)


def _trace_payload(filename: str, text: str) -> dict[str, object]:
    """Read one uploaded trace file into the payload the output selector lists."""
    tasks = load_step_trace(text)
    machine = str(tasks[0]["steps"].get(PipelineStep.REWARD_MACHINE.value, ""))
    parse_reward_machine(machine)
    return {"filename": filename, "text": machine, "tasks": tasks}


def _imported_task_index(value: object) -> int | None:
    """Return the trace task index of an imported selection, or None for a plain RM."""
    if not isinstance(value, str) or not value.startswith(f"{IMPORTED_RM_VALUE}:"):
        return None
    try:
        return int(value.split(":", 1)[1])
    except ValueError:
        return None


def _imported_options(imported: dict[str, object]) -> list[dict[str, object]]:
    """List one selector entry per trace task, or one entry for a bare Reward Machine."""
    filename = str(imported["filename"])
    tasks = imported.get("tasks")
    if not isinstance(tasks, list) or len(tasks) < 2:
        return [{"label": f"Imported: {filename}", "value": IMPORTED_RM_VALUE}]
    return [
        {
            "label": f"Imported: {filename} · task {index + 1}/{len(tasks)}",
            "value": f"{IMPORTED_RM_VALUE}:{index}",
        }
        for index in range(len(tasks))
    ]


def _imported_task(
    imported: dict[str, object] | None,
    index: int | None,
) -> dict[str, object] | None:
    """Return the selected trace task, or a bare Reward Machine as a one-step task."""
    if imported is None:
        return None
    tasks = imported.get("tasks")
    if isinstance(tasks, list) and tasks:
        position = 0 if index is None else index
        if 0 <= position < len(tasks) and isinstance(tasks[position], dict):
            return tasks[position]
        return None
    if index is not None:
        return None
    return {
        "task": "",
        "attempt": 1,
        "reward_machine": "",
        "steps": {PipelineStep.REWARD_MACHINE.value: imported["text"]},
    }


def _imported_reward_machine(data: object) -> dict[str, object] | None:
    """Return a well-shaped imported payload, if present."""
    if not isinstance(data, dict):
        return None
    filename = data.get("filename")
    text = data.get("text")
    if not isinstance(filename, str) or not isinstance(text, str):
        return None
    return {"filename": filename, "text": text, "tasks": data.get("tasks")}


def _resolve_environment_filename(
    current_markdown: str | None,
    upload_contents: str | None,
    upload_filename: str | None,
) -> str | None:
    """Return the upload basename only while its content is still current."""
    if not current_markdown or not upload_contents or not upload_filename:
        return None
    try:
        upload = _uploaded_environment(upload_contents, upload_filename)
    except (ValueError, UnicodeDecodeError, OSError, RecursionError):
        return None
    if _normalize_line_endings(current_markdown) != _normalize_line_endings(upload.markdown):
        return None
    return upload.environment_filename


def _normalize_line_endings(markdown: str) -> str:
    """Normalize browser and platform line endings for provenance comparison."""
    return markdown.replace("\r\n", "\n").replace("\r", "\n")


def _export_elements(raw: object) -> list | None:
    """Validate the browser-supplied Cytoscape elements, or None when unusable."""
    if not isinstance(raw, list) or not raw:
        return None
    shaped = all(
        isinstance(element, dict) and isinstance(element.get("data"), dict) for element in raw
    )
    return raw if shaped else None


def _export_positions(raw: object) -> dict | None:
    """Validate the browser-supplied node positions, or None when unusable."""
    if not isinstance(raw, dict):
        return None
    positions: dict[str, tuple[float, float]] = {}
    for node, value in raw.items():
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            return None
        try:
            positions[str(node)] = (float(value[0]), float(value[1]))
        except (TypeError, ValueError):
            return None
    return positions


def _export_filename(name: object, extension: str) -> str:
    """Name the export after the selected output, sanitized for filesystems."""
    if isinstance(name, str):
        stem = _UNSAFE_OUTPUT_NAME.sub("-", name.strip()).strip("-")
        if stem:
            return f"{stem}.{extension}"
    return f"reward-machine.{extension}"


@dataclass(frozen=True)
class _UploadedEnvironment:
    markdown: str
    environment_filename: str
    output_stem: str
    tasks: tuple[str, ...] | None = None


def _uploaded_environment(contents: str, filename: str | None) -> _UploadedEnvironment:
    """Read an Environment upload: Markdown, or a tasks manifest that points at it.

    A manifest must carry ``env``, ``env_description`` and a non-empty ``tasks``
    list. Its Markdown is read from ``env_description`` resolved against the
    repository root and kept inside it; the output is named after ``env``.
    Raises ``ValueError`` for a manifest missing fields, ``OSError`` when the
    referenced file cannot be read.
    """
    text = _decode_uploaded_markdown(contents)
    if not (filename or "").lower().endswith(".json"):
        return _UploadedEnvironment(
            text,
            filename or _DEFAULT_ENVIRONMENT_NAME,
            _environment_output_stem(filename, text),
        )
    manifest = json.loads(text.lstrip("\ufeff"))
    if not isinstance(manifest, dict) or any(not manifest.get(field) for field in _MANIFEST_FIELDS):
        raise ValueError(f"a tasks manifest needs {', '.join(_MANIFEST_FIELDS)}")
    tasks = manifest["tasks"]
    if not isinstance(tasks, list) or any(
        not isinstance(task, str) or not task.strip() for task in tasks
    ):
        raise ValueError("tasks must be a list of non-empty strings")
    description = (_REPO_ROOT / str(manifest["env_description"])).resolve()
    if not description.is_relative_to(_REPO_ROOT):
        raise ValueError("env_description must stay inside the repository")
    slug = re.sub(r"[^a-z0-9]+", "-", str(manifest["env"]).lower()).strip("-")
    return _UploadedEnvironment(
        description.read_text(encoding="utf-8"),
        description.name,
        slug or _DEFAULT_ENVIRONMENT_NAME,
        tuple(task.strip() for task in tasks),
    )


def _environment_output_stem(filename: str | None, markdown: str) -> str:
    """Name the output after the environment title for a generic ``environment.md`` upload.

    Every example environment file shares the name ``environment.md``, so an
    output numbered after that name says nothing about the task. A generic
    upload is slugged from its first level-1 heading instead, falling back to
    the generic name when it has none. Any other file name is kept unchanged.
    """
    if filename is not None and PurePosixPath(filename).stem.lower() != _ENVIRONMENT_STEM:
        return filename
    match = _ENVIRONMENT_TITLE.search(markdown)
    if match is None:
        return _DEFAULT_ENVIRONMENT_NAME
    slug = re.sub(r"[^a-z0-9]+", "-", match.group(1).lower()).strip("-")
    return slug or _DEFAULT_ENVIRONMENT_NAME


def _output_stem(name: str | None) -> str:
    """Reduce a submitted output name to a filesystem-safe stem.

    Directories, repeated ``.rm`` fragments, and unsupported characters are
    removed so a name the user typed can be repaired instead of rejected.
    """
    candidate = PurePosixPath(str(name or "").replace("\\", "/")).name.strip()
    while candidate.lower().endswith(_OUTPUT_SUFFIX):
        candidate = candidate[: -len(_OUTPUT_SUFFIX)]
    path = Path(candidate)
    stem = path.stem if path.suffix else candidate
    stem = _UNSAFE_OUTPUT_NAME.sub("-", stem).strip("-._")
    return stem or _DEFAULT_OUTPUT_STEM


def _existing_output_names() -> set[str]:
    """Return the file names already written to the shared output folder."""
    output_dir = Configuration.RM_PATH
    if not output_dir.exists():
        return set()
    return {path.name for path in output_dir.iterdir()}


def _is_output_name_free(candidate: str, task_count: int, existing: set[str]) -> bool:
    """Return whether the name and every file this run writes are unused."""
    derived = derive_output_names(Path(candidate), task_count)
    return candidate not in existing and all(name.name not in existing for name in derived)


def _available_output_filename(name: str | None, task_count: int = 1) -> str:
    """Return an unused RM name derived from a submitted or uploaded name.

    A name that is already valid is returned unchanged. Anything else is
    repaired: unsupported characters are replaced, then the shared ``-NNN``
    counter continues from the highest number already on disk, so a run can
    start without the user editing the field by hand.
    """
    stem = _output_stem(name)
    existing = _existing_output_names()
    if _is_output_name_free(f"{stem}{_OUTPUT_SUFFIX}", task_count, existing):
        return f"{stem}{_OUTPUT_SUFFIX}"

    numbered = re.compile(rf"^{re.escape(stem)}-(\d+){re.escape(_OUTPUT_SUFFIX)}$")
    highest = max(
        (
            int(match.group(1))
            for existing_name in existing
            if (match := numbered.fullmatch(existing_name))
        ),
        default=0,
    )
    number = highest + 1
    while not _is_output_name_free(f"{stem}-{number:03d}{_OUTPUT_SUFFIX}", task_count, existing):
        number += 1
    return f"{stem}-{number:03d}{_OUTPUT_SUFFIX}"
