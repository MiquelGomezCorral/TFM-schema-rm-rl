"""Dash application factory and focused callback registration."""

import base64
import re
from collections.abc import Mapping
from pathlib import Path, PurePosixPath

import dash_cytoscape as cyto
from dash import ALL, Dash, Input, Output, State, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate

from src.compiler import CompilationResult, parse_reward_machine
from src.config import Configuration
from src.utils import (
    CYTOSCAPE_STYLESHEET,
    STEP_OUTPUT_ORDER,
    PipelineStep,
    derive_output_names,
    format_reward_label,
    load_step_trace,
    render_elements_svg,
    reward_machine_to_elements,
)

from .components import (
    CRITIC_OPTIONS,
    EMBEDDINGS_OPTIONS,
    FOCUS_OUTPUT_REGION_CLASS,
    FOCUS_WORKSPACE_CLASS,
    INPUT_REGION_CLASS,
    LABELING_OPTIONS,
    OUTPUT_REGION_CLASS,
    RUN_SIDEBAR_CLASS,
    STATUS_CLASSES,
    STEPS_REPORT_OPTIONS,
    WORKSPACE_CLASS,
    _section_icon,
    create_layout,
    render_steps,
    result_bodies,
    result_tabs,
    task_row,
)
from .runner import RunController, RunRequest, RunSnapshot, RunState

IMPORTED_RM_VALUE = "imported"

_OUTPUT_SUFFIX = ".rm"
_DEFAULT_OUTPUT_STEM = "reward-machine"
_UNSAFE_OUTPUT_NAME = re.compile(r"[^A-Za-z0-9._-]+")

_UPLOAD_STATUS_CLASS = "field-hint text-[0.76rem] leading-[1.4] text-muted"
_UPLOAD_ERROR_CLASS = "field-hint text-[0.76rem] leading-[1.4] text-[#fda4af]"

_EXPORT_CLIENT_SCRIPT = """
function (n_clicks) {
    if (!n_clicks || !window.cy) {
        return window.dash_clientside.no_update;
    }
    const positions = Object.fromEntries(
        window.cy.nodes().map((node) => {
            const point = node.position();
            return [node.id(), [point.x, point.y]];
        })
    );
    return {elements: window.cy.elements().jsons(), positions: positions};
}
"""


def create_app(controller: RunController) -> Dash:
    """Create one local Dash app driven by ``controller``."""
    cyto.load_extra_layouts()
    assets_folder = Path(__file__).resolve().parents[2] / "assets"
    app = Dash(__name__, assets_folder=str(assets_folder), title="Reward Machine compiler")
    app.layout = create_layout(CYTOSCAPE_STYLESHEET)

    _register_input_callbacks(app)
    _register_start_callback(app, controller)
    _register_poll_callback(app, controller)
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
        Input("environment-upload", "contents"),
        State("environment-upload", "filename"),
        prevent_initial_call=True,
    )(_load_environment)
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


def _register_start_callback(app: Dash, controller: RunController) -> None:
    @app.callback(
        Output("run-feedback", "children"),
        Input("generate-button", "n_clicks"),
        State("environment-markdown", "value"),
        State("environment-upload", "filename"),
        State("environment-upload", "contents"),
        State({"type": "task-input", "index": ALL}, "value"),
        State("output-filename", "value"),
        State("critic-options", "value"),
        State("steps-report-toggle", "value"),
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
        *toggles: list[str] | None,
    ) -> str:
        """Start a run from the form; ``toggles`` are the four checklist values in layout order."""
        if not (markdown or "").strip():
            return "Enter or upload environment Markdown first."
        tasks = tuple((value or "").strip() for value in task_values or [])
        if not tasks or any(not task for task in tasks):
            return "Every task row must contain text."
        submitted_name = (output_filename or "").strip()
        output_name = _available_output_filename(submitted_name, len(tasks))
        request = RunRequest(
            environment_markdown=markdown,
            tasks=tasks,
            output_filename=output_name,
            environment_filename=_resolve_environment_filename(markdown, upload_contents, filename),
            **_run_flags(*toggles),
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


def _register_poll_callback(app: Dash, controller: RunController) -> None:
    @app.callback(
        Output("run-status", "children"),
        Output("run-status", "className"),
        Output("run-log", "children"),
        Output("environment-upload", "disabled"),
        Output("environment-markdown", "disabled"),
        Output({"type": "task-input", "index": ALL}, "disabled"),
        Output("add-task", "disabled"),
        Output({"type": "remove-task", "index": ALL}, "disabled"),
        Output("output-filename", "disabled"),
        Output("generate-button", "disabled"),
        Output("critic-options", "options"),
        Output("output-selector", "options"),
        Output("output-selector", "value"),
        Output("output-selector", "disabled"),
        Output("run-steps", "children"),
        Output("task-selection", "data"),
        Output("steps-report-toggle", "options"),
        Output("labeling-toggle", "options"),
        Output("embeddings-toggle", "options"),
        Input("poll-interval", "n_intervals"),
        State("output-selector", "value"),
        State({"type": "remove-task", "index": ALL}, "id"),
        Input("run-prev", "n_clicks", allow_optional=True),
        Input("run-next", "n_clicks", allow_optional=True),
        Input({"type": "task-dot", "index": ALL}, "n_clicks"),
        State("task-selection", "data"),
        Input("imported-reward-machine", "data"),
        State("run-status", "children"),
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
        previous_status: str | None = None,
    ) -> tuple[object, ...]:
        snapshot = controller.snapshot()
        status_text, status_class = _run_status(snapshot)
        if status_text == previous_status:
            # Only a real status change may wake dependents, or every poll would re-render them.
            status_text = status_class = no_update
        panels = _poll_panels(snapshot, selected_index, remove_ids, selection_data, imported_data)
        return status_text, status_class, *panels


def _register_result_callback(app: Dash, controller: RunController) -> None:
    @app.callback(
        Output("result-summary", "children"),
        Output("result-tabs", "children"),
        Output("result-bodies", "children"),
        Output("rm-graph", "elements"),
        Output("graph-export-name", "data"),
        Output("graph-export-button", "disabled"),
        Input("output-selector", "value"),
        Input("imported-reward-machine", "data"),
        Input("run-status", "children"),
        Input("result-tabs", "value"),
    )
    def render_selected_result(
        selected_index: int | str | None,
        imported_data: dict[str, str] | None = None,
        _run_status: str | None = None,
        selected_step: str | None = None,
    ) -> tuple[str, object, list, list, str | None, bool]:
        step = _selected_step(selected_step)
        if selected_index is None:
            return _empty_panel("No completed output selected.", step)
        if _is_imported_value(selected_index):
            return _render_imported(imported_data, _imported_task_index(selected_index), step)
        return _render_generated(controller.snapshot(), selected_index, step)


def _register_graph_callbacks(app: Dash) -> None:
    app.callback(
        Output("graph-transition-pin", "data"),
        Input("rm-graph", "tapEdgeData"),
        Input("rm-graph", "tapNodeData"),
        Input("graph-transition-close", "n_clicks"),
        Input("output-selector", "value"),
        Input("imported-reward-machine", "data"),
        prevent_initial_call=True,
    )(_update_transition_pin)
    app.callback(
        Output("graph-transition-inspector", "className"),
        Output("graph-transition-content", "children"),
        Input("graph-transition-pin", "data"),
    )(_render_transition_inspector)
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
        prevent_initial_call=True,
    )


# ======================================================================================
#                                  INPUT CALLBACK BODIES
# ======================================================================================


def _load_environment(contents: str | None, filename: str | None) -> tuple[object, str, object]:
    if not contents:
        raise PreventUpdate
    try:
        markdown = _decode_uploaded_markdown(contents)
    except (ValueError, UnicodeDecodeError) as error:
        return no_update, f"Could not load UTF-8 Markdown: {error}", no_update
    environment_name = filename or "environment.md"
    return (
        markdown,
        f"Loaded {environment_name}; edit the text before generating.",
        _available_output_filename(environment_name),
    )


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


def _run_flags(
    critic_options: list[str] | None,
    steps_report_options: list[str] | None,
    labeling_options: list[str] | None,
    embeddings_options: list[str] | None,
) -> dict[str, bool]:
    """Turn the four checklist values into the run request's boolean flags."""
    return {
        "task_critic": _is_checked(critic_options, "task_critic"),
        "rm_critic": _is_checked(critic_options, "rm_critic"),
        "labeling": _is_checked(labeling_options, "labeling"),
        "embeddings": _is_checked(embeddings_options, "embeddings"),
        "steps_report": _is_checked(steps_report_options, "steps_report"),
    }


def _is_checked(options: list[str] | None, name: str) -> bool:
    return bool(options and name in options)


# ======================================================================================
#                                  RUN CALLBACK BODIES
# ======================================================================================


def _run_status(snapshot: RunSnapshot) -> tuple[str, str]:
    """Return the status label and its CSS classes."""
    text = snapshot.status.value.capitalize()
    if snapshot.error:
        text = f"{text}: {snapshot.error}"
    return text, STATUS_CLASSES[snapshot.status.value]


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
    task_selected, next_selection = _task_selection(snapshot, selection_data, trigger)
    remove_ids = remove_ids or []
    return (
        "\n".join(snapshot.logs) if snapshot.logs else "No run yet.",
        active,
        active,
        [active] * len(remove_ids),
        active,
        [active or item.get("index") == 0 for item in remove_ids],
        active,
        active,
        _locked(CRITIC_OPTIONS, active),
        options,
        selected if selected != selected_index else no_update,
        not bool(options),
        render_steps(snapshot.tasks, task_selected),
        next_selection,
        _locked(STEPS_REPORT_OPTIONS, active),
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
    if trigger == "imported-reward-machine":
        return IMPORTED_RM_VALUE
    if generated or _is_imported_value(selected_index):
        return selected_index
    return IMPORTED_RM_VALUE


def _task_selection(
    snapshot: RunSnapshot,
    selection_data: dict[str, int | None] | None,
    trigger: str | dict | None,
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
) -> tuple[str, object, list, list, str | None, bool]:
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
    summary = f"Imported: {imported['filename']}" + (f" | {label}" if label else "")
    return _panel(
        summary,
        steps,
        step,
        reward_machine_to_elements(reward_machine),
        Path(name).stem,
    )


def _render_generated(
    snapshot: RunSnapshot, selected_index: int | str, step: PipelineStep
) -> tuple[str, object, list, list, str | None, bool]:
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
        reward_machine_to_elements(result.reward_machine),
        output_path.stem,
    )


def _result_summary(result: CompilationResult, output_path: Path) -> str:
    """Describe one completed output, with its bundle and embedding artifacts when present."""
    summary = f"{output_path} | {result.proposal.task}"
    if result.bundle_path:
        summary += f" | Bundle: {result.bundle_path}"
    if result.embedding_settings:
        model = result.embedding_settings.get("model")
        dimension = result.embedding_settings.get("dimension")
        summary += f" | Embedding: {model} dim={dimension}"
    if result.embedding_path:
        summary += f" | Embeddings: {result.embedding_path}"
    return summary


def _is_generated_index(value: object, generated_count: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value < generated_count


def _is_imported_value(value: object) -> bool:
    return value == IMPORTED_RM_VALUE or _imported_task_index(value) is not None


# ======================================================================================
#                                 GRAPH CALLBACK BODIES
# ======================================================================================


def _update_transition_pin(
    tapped_edge: dict | None,
    _tapped_node: dict | None,
    _close_clicks: int | None,
    _selected_output: int | str | None,
    _imported_reward_machine: dict[str, str] | None,
) -> dict | None:
    triggered_props = ctx.triggered_prop_ids
    if "rm-graph.tapEdgeData" in triggered_props:
        return tapped_edge
    if {
        "output-selector.value",
        "imported-reward-machine.data",
        "rm-graph.tapNodeData",
        "graph-transition-close.n_clicks",
    } & triggered_props.keys():
        return None
    raise PreventUpdate


def _render_transition_inspector(pinned_edge: dict | None) -> tuple[str, object]:
    if not isinstance(pinned_edge, dict) or not isinstance(pinned_edge.get("cases"), list):
        return _transition_inspector_class(False), []
    return _transition_inspector_class(True), _transition_inspector_children(pinned_edge)


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
            [_section_icon("minimize", boxed=False), "Exit focus"],
            True,
        )
    return (
        False,
        WORKSPACE_CLASS,
        INPUT_REGION_CLASS,
        RUN_SIDEBAR_CLASS,
        OUTPUT_REGION_CLASS,
        [_section_icon("focus", boxed=False), "Focus graph"],
        False,
    )


def _export_graph(payload: object, name: object) -> object:
    """Render the live graph, keeping the node positions the user arranged."""
    if not isinstance(payload, dict):
        raise PreventUpdate
    elements = _export_elements(payload.get("elements"))
    positions = _export_positions(payload.get("positions"))
    if elements is None or positions is None:
        raise PreventUpdate
    svg = render_elements_svg(elements, positions or None)
    return dcc.send_string(svg, _export_filename(name), type="image/svg+xml")


# ======================================================================================
#                                      HELPERS
# ======================================================================================


def _transition_inspector_class(visible: bool) -> str:
    """Return the fixed-position inspector classes without changing graph layout."""
    base = (
        "graph-transition-inspector absolute left-3 top-3 z-10 max-h-[calc(100%_-_1.5rem)] "
        "w-[min(28rem,calc(100%_-_1.5rem))] overflow-auto rounded-[0.65rem] border "
        "border-border-strong bg-[#101a2b] p-3 text-text shadow-[0_12px_30px_rgb(0_0_0_/_35%)]"
    )
    return (
        f"{base} pointer-events-auto visible"
        if visible
        else f"{base} pointer-events-none invisible"
    )


def _transition_inspector_children(edge: dict) -> list[object]:
    """Render all formal grouped transition cases as readable chips."""
    source = str(edge.get("source", "")).removeprefix("state-")
    target = str(edge.get("target", "")).removeprefix("state-")
    cases = edge.get("cases", [])
    children: list[object] = [
        html.Div(
            [
                html.Span(f"u{source} → u{target}", className="font-bold text-text"),
                html.Span(
                    f"{len(cases)} formal case{'s' if len(cases) != 1 else ''}",
                    className="text-[0.7rem] text-muted",
                ),
            ],
            className="flex items-baseline justify-between gap-3",
        )
    ]
    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            continue
        condition = case.get("condition", [])
        if isinstance(condition, str):
            condition = [condition]
        if not isinstance(condition, list):
            condition = []
        literals = [
            html.Span(
                str(literal),
                className=(
                    "rounded-[0.3rem] px-1.5 py-0.5 font-mono text-[0.68rem] "
                    + (
                        "bg-[#be123c] text-[#ffe4e6]"
                        if str(literal).startswith("!")
                        else "bg-[#eef2ff] text-[#24314d]"
                    )
                ),
            )
            for literal in condition
        ] or [
            html.Span(
                "true",
                className="rounded-[0.3rem] bg-[#eef2ff] px-1.5 py-0.5 font-mono text-[0.68rem] text-[#24314d]",
            )
        ]
        reward = case.get("reward", 0)
        try:
            numeric_reward = float(reward)
        except (TypeError, ValueError):
            numeric_reward = 0.0
        reward_class = (
            "text-[#86efac]"
            if numeric_reward > 0
            else "text-[#be123c]"
            if numeric_reward < 0
            else "text-[#dce7f7]"
        )
        children.append(
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(
                                f"Case {index}",
                                className="text-[0.68rem] font-bold text-muted",
                            ),
                            html.Span(
                                f"· r={format_reward_label(numeric_reward)}",
                                className=f"text-[0.68rem] font-bold {reward_class}",
                            ),
                        ],
                        className="flex items-center gap-1",
                    ),
                    html.Div(literals, className="flex flex-wrap gap-1"),
                ],
                className="grid gap-1 rounded-[0.45rem] border border-border bg-surface-raised p-2",
            )
        )
    return children


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
    summary: str,
    steps: Mapping[PipelineStep, object],
    selected: PipelineStep,
    elements: list,
    export_name: str | None,
) -> tuple[str, object, list, list, str | None, bool]:
    """Return one panel update: summary, tab strip, stacked bodies and the graph."""
    return (
        summary,
        result_tabs(steps),
        result_bodies(steps, selected),
        elements,
        export_name,
        not elements,
    )


def _empty_panel(
    summary: str, selected: PipelineStep
) -> tuple[str, object, list, list, str | None, bool]:
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
        uploaded_markdown = _decode_uploaded_markdown(upload_contents)
    except (ValueError, UnicodeDecodeError):
        return None
    if _normalize_line_endings(current_markdown) != _normalize_line_endings(uploaded_markdown):
        return None
    return upload_filename


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


def _export_filename(name: object) -> str:
    """Name the export after the selected output, sanitized for filesystems."""
    if isinstance(name, str):
        stem = _UNSAFE_OUTPUT_NAME.sub("-", name.strip()).strip("-")
        if stem:
            return f"{stem}.svg"
    return "reward-machine.svg"


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
