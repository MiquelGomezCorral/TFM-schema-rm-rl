"""Dash application factory and focused callback registration."""

import base64
import re
from pathlib import Path, PurePosixPath

from dash import ALL, Dash, Input, Output, State, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate
import dash_cytoscape as cyto

from src.config import Configuration
from src.compiler.reward_machine import parse_reward_machine
from collections.abc import Mapping

from src.utils import STEP_OUTPUT_ORDER, PipelineStep, derive_output_names, load_step_trace

from .components import (
    FOCUS_OUTPUT_REGION_CLASS,
    FOCUS_WORKSPACE_CLASS,
    INPUT_REGION_CLASS,
    OUTPUT_REGION_CLASS,
    RUN_SIDEBAR_CLASS,
    STATUS_CLASSES,
    WORKSPACE_CLASS,
    _section_icon,
    create_layout,
    render_steps,
    result_bodies,
    result_tabs,
    task_row,
)
from .runner import RunController, RunState
from .svg import render_elements_svg
from .visualization import CYTOSCAPE_STYLESHEET, format_reward_label, reward_machine_to_elements


IMPORTED_RM_VALUE = "imported"

_OUTPUT_SUFFIX = ".rm"
_DEFAULT_OUTPUT_STEM = "reward-machine"
_UNSAFE_OUTPUT_NAME = re.compile(r"[^A-Za-z0-9._-]+")

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


def create_app() -> Dash:
    """Create one local Dash app with an isolated run controller."""
    cyto.load_extra_layouts()
    assets_folder = Path(__file__).resolve().parents[2] / "assets"
    app = Dash(__name__, assets_folder=str(assets_folder), title="Reward Machine compiler")
    controller = RunController()
    app.layout = create_layout(CYTOSCAPE_STYLESHEET)

    @app.callback(
        Output("environment-markdown", "value"),
        Output("upload-status", "children"),
        Output("output-filename", "value"),
        Input("environment-upload", "contents"),
        State("environment-upload", "filename"),
        prevent_initial_call=True,
    )
    def load_environment(contents: str | None, filename: str | None) -> tuple[object, str, object]:
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

    @app.callback(
        Output("imported-reward-machine", "data"),
        Output("reward-machine-upload-status", "children"),
        Output("reward-machine-upload-status", "className"),
        Input("reward-machine-upload", "contents"),
        State("reward-machine-upload", "filename"),
        prevent_initial_call=True,
    )
    def load_reward_machine(
        contents: str | None,
        filename: str | None,
    ) -> tuple[object, str, str]:
        status_class = "field-hint text-[0.76rem] leading-[1.4] text-muted"
        error_class = "field-hint text-[0.76rem] leading-[1.4] text-[#fda4af]"
        if not contents:
            raise PreventUpdate
        if not filename or not filename.lower().endswith((".rm", ".json")):
            return no_update, "Could not load Reward Machine: choose a .rm or trace .json file.", error_class
        try:
            text = _decode_uploaded_markdown(contents)
            if filename.lower().endswith(".json"):
                payload = _trace_payload(filename, text)
            else:
                parse_reward_machine(text)
                payload = {"filename": filename, "text": text}
        except (ValueError, UnicodeDecodeError) as error:
            return no_update, f"Could not load Reward Machine: {error}", error_class
        tasks = payload.get("tasks")
        count = len(tasks) if isinstance(tasks, list) else 0
        note = f"Loaded {filename}: {count} task(s) with every pipeline step; select one below."
        return (
            payload,
            note if count else f"Loaded {filename}; select it below.",
            status_class,
        )

    @app.callback(
        Output("task-rows", "children"),
        Input("add-task", "n_clicks"),
        Input({"type": "remove-task", "index": ALL}, "n_clicks"),
        State({"type": "task-input", "index": ALL}, "value"),
        prevent_initial_call=True,
    )
    def update_task_rows(
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
        prevent_initial_call=True,
    )
    def start_run(
        _n_clicks: int | None,
        markdown: str | None,
        filename: str | None,
        upload_contents: str | None,
        task_values: list[str | None],
        output_filename: str | None,
        critic_options: list[str] | None,
        steps_report_options: list[str] | None,
    ) -> str:
        if not (markdown or "").strip():
            return "Enter or upload environment Markdown first."
        tasks = tuple((value or "").strip() for value in task_values or [])
        if not tasks or any(not task for task in tasks):
            return "Every task row must contain text."
        submitted_name = (output_filename or "").strip()
        output_name = _available_output_filename(submitted_name, len(tasks))
        critic_options = critic_options or []
        #if not critic_options:
        #    return "Select at least one critic."
        source_filename = _resolve_environment_filename(
            markdown,
            upload_contents,
            filename,
        )
        try:
            controller.start(
                environment_markdown=markdown,
                environment_filename=source_filename,
                tasks=tasks,
                output_filename=output_name,
                task_critic="task_critic" in critic_options,
                rm_critic="rm_critic" in critic_options,
                steps_report=bool(steps_report_options and "steps_report" in steps_report_options),
            )
        except (RuntimeError, ValueError) as error:
            return f"Could not start run: {error}"
        if output_name == submitted_name:
            return "Run started; progress will appear in the log."
        return (
            f"Run started as {output_name}; the output name was adjusted automatically "
            "to the next free file name."
        )

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
        Input("poll-interval", "n_intervals"),
        State("output-selector", "value"),
        State({"type": "remove-task", "index": ALL}, "id"),
        Input("run-prev", "n_clicks", allow_optional=True),
        Input("run-next", "n_clicks", allow_optional=True),
        Input({"type": "task-dot", "index": ALL}, "n_clicks"),
        State("task-selection", "data"),
        Input("imported-reward-machine", "data"),
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
    ) -> tuple[object, ...]:
        snapshot = controller.snapshot()
        active = snapshot.status is RunState.RUNNING
        options = [
            {"label": str(path), "value": index}
            for index, path in enumerate(snapshot.output_paths)
        ]
        imported = _imported_reward_machine(imported_data)
        if imported is not None:
            options.extend(_imported_options(imported))
        imported_selected = selected_index == IMPORTED_RM_VALUE or (
            _imported_task_index(selected_index) is not None
        )
        generated_count = len(snapshot.output_paths)
        selected_is_generated = (
            isinstance(selected_index, int)
            and not isinstance(selected_index, bool)
            and 0 <= selected_index < generated_count
        )
        status_class = STATUS_CLASSES[snapshot.status.value]
        status_text = snapshot.status.value.capitalize()
        if snapshot.error:
            status_text = f"{status_text}: {snapshot.error}"
        log_text = "\n".join(snapshot.logs) if snapshot.logs else "No run yet."
        remove_disabled = [
            active or item.get("index") == 0
            for item in remove_ids or []
        ]
        selection_data = selection_data or {}
        total_tasks = len(snapshot.tasks)
        stored_run_id = selection_data.get("run_id")
        if stored_run_id != snapshot.run_id:
            task_selected = 0
            last_active = None
        else:
            task_selected = selection_data.get("selected", 0) or 0
            last_active = selection_data.get("last_active")
        task_selected = max(0, min(task_selected, total_tasks - 1)) if total_tasks else 0
        try:
            trigger = ctx.triggered_id
        except Exception:
            trigger = None
        imported_triggered = trigger == "imported-reward-machine"
        if imported is not None and imported_triggered:
            selected = IMPORTED_RM_VALUE
        elif selected_is_generated or (imported_selected and imported is not None):
            selected = selected_index
        elif imported is not None:
            selected = IMPORTED_RM_VALUE
        else:
            selected = 0 if options else None
        navigation_triggered = False
        if total_tasks > 1 and trigger == "run-prev":
            task_selected = max(0, task_selected - 1)
            navigation_triggered = True
        elif total_tasks > 1 and trigger == "run-next":
            task_selected = min(total_tasks - 1, task_selected + 1)
            navigation_triggered = True
        elif isinstance(trigger, dict) and trigger.get("type") == "task-dot":
            index = trigger.get("index")
            if isinstance(index, int) and 0 <= index < total_tasks:
                task_selected = index
                navigation_triggered = True
        if (
            not navigation_triggered
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
        return (
            status_text,
            status_class,
            log_text,
            active,
            active,
            [active] * len(remove_ids or []),
            active,
            remove_disabled,
            active,
            active,
            [{"label": " Task interpretation critic", "value": "task_critic", "disabled": active},
             {"label": " Reward Machine critic", "value": "rm_critic", "disabled": active}],
            options,
            selected if selected != selected_index else no_update,
            not bool(options),
            render_steps(snapshot.tasks, task_selected),
            next_selection,
            [{"label": " Step report (.md)", "value": "steps_report", "disabled": active}],
        )

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
            return _panel("No completed output selected.", {}, step, [], None, True)
        task_index = _imported_task_index(selected_index)
        if selected_index == IMPORTED_RM_VALUE or task_index is not None:
            imported = _imported_reward_machine(imported_data)
            task = _imported_task(imported, task_index)
            if imported is None or task is None:
                return _panel("No imported Reward Machine selected.", {}, step, [], None, True)
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
                message = f"Could not render imported Reward Machine: {error}"
                return _panel(message, {}, step, [], None, True)
            elements = reward_machine_to_elements(reward_machine)
            name = str(task["reward_machine"]) or str(imported["filename"])
            label = str(task["task"])
            summary = f"Imported: {imported['filename']}" + (f" | {label}" if label else "")
            return _panel(summary, steps, step, elements, Path(name).stem, not elements)
        snapshot = controller.snapshot()
        if not snapshot.results:
            return _panel("No completed output selected.", {}, step, [], None, True)
        if (
            not isinstance(selected_index, int)
            or isinstance(selected_index, bool)
            or not 0 <= selected_index < len(snapshot.results)
        ):
            # Nothing selected yet, so show the newest completed output.
            selected_index = len(snapshot.results) - 1
        result = snapshot.results[selected_index]
        output_path = snapshot.output_paths[selected_index]
        steps = dict(snapshot.step_outputs[selected_index])
        steps.setdefault(PipelineStep.REWARD_MACHINE, result.text)
        elements = reward_machine_to_elements(result.reward_machine)
        return _panel(
            f"{output_path} | {result.proposal.task}",
            steps,
            step,
            elements,
            output_path.stem,
            not elements,
        )

    @app.callback(
        Output("graph-transition-pin", "data"),
        Input("rm-graph", "tapEdgeData"),
        Input("rm-graph", "tapNodeData"),
        Input("graph-transition-close", "n_clicks"),
        Input("output-selector", "value"),
        Input("imported-reward-machine", "data"),
        prevent_initial_call=True,
    )
    def update_transition_pin(
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

    @app.callback(
        Output("graph-transition-inspector", "className"),
        Output("graph-transition-content", "children"),
        Input("graph-transition-pin", "data"),
    )
    def render_transition_inspector(
        pinned_edge: dict | None,
    ) -> tuple[str, object]:
        if not isinstance(pinned_edge, dict) or not isinstance(pinned_edge.get("cases"), list):
            return _transition_inspector_class(False), []
        return (
            _transition_inspector_class(True),
            _transition_inspector_children(pinned_edge),
        )

    @app.callback(
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
    )
    def toggle_graph_focus(
        _n_clicks: int | None,
        focused: bool | None,
    ) -> tuple[bool, str, str, str, str, list, bool]:
        focused = not bool(focused)
        if focused:
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

    @app.callback(
        Output("graph-download", "data"),
        Input("graph-export-payload", "data"),
        State("graph-export-name", "data"),
        prevent_initial_call=True,
    )
    def export_graph(payload: object, name: object) -> object:
        """Render the live graph, keeping the node positions the user arranged."""
        if not isinstance(payload, dict):
            raise PreventUpdate
        elements = _export_elements(payload.get("elements"))
        positions = _export_positions(payload.get("positions"))
        if elements is None or positions is None:
            raise PreventUpdate
        svg = render_elements_svg(elements, positions or None)
        return dcc.send_string(svg, _export_filename(name), type="image/svg+xml")

    app.clientside_callback(
        _EXPORT_CLIENT_SCRIPT,
        Output("graph-export-payload", "data"),
        Input("graph-export-button", "n_clicks"),
        prevent_initial_call=True,
    )

    app._run_controller = controller
    return app


def _transition_inspector_class(visible: bool) -> str:
    """Return the fixed-position inspector classes without changing graph layout."""
    base = (
        "graph-transition-inspector absolute left-3 top-3 z-10 max-h-[calc(100%_-_1.5rem)] "
        "w-[min(28rem,calc(100%_-_1.5rem))] overflow-auto rounded-[0.65rem] border "
        "border-border-strong bg-[#101a2b] p-3 text-text shadow-[0_12px_30px_rgb(0_0_0_/_35%)]"
    )
    return f"{base} pointer-events-auto visible" if visible else f"{base} pointer-events-none invisible"


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
                    + ("bg-[#be123c] text-[#ffe4e6]" if str(literal).startswith("!") else "bg-[#eef2ff] text-[#24314d]")
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
                            html.Span(f"Case {index}", className="text-[0.68rem] font-bold text-muted"),
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
    export_disabled: bool,
) -> tuple[str, object, list, list, str | None, bool]:
    """Return one panel update: summary, tab strip, stacked bodies and the graph."""
    return (
        summary,
        result_tabs(steps, selected),
        result_bodies(steps, selected),
        elements,
        export_name,
        export_disabled,
    )


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
        isinstance(element, dict) and isinstance(element.get("data"), dict)
        for element in raw
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
        stem = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip()).strip("-")
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
    while not _is_output_name_free(
        f"{stem}-{number:03d}{_OUTPUT_SUFFIX}", task_count, existing
    ):
        number += 1
    return f"{stem}-{number:03d}{_OUTPUT_SUFFIX}"
