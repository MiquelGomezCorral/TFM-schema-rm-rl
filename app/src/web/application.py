"""Dash application factory and focused callback registration."""

import base64
import re
from pathlib import Path

from dash import ALL, Dash, Input, Output, State, ctx, html, no_update
from dash.exceptions import PreventUpdate
import dash_cytoscape as cyto

from src.config import Configuration
from src.compiler.reward_machine import parse_reward_machine

from .components import (
    FOCUS_OUTPUT_REGION_CLASS,
    FOCUS_WORKSPACE_CLASS,
    INPUT_REGION_CLASS,
    OUTPUT_REGION_CLASS,
    RUN_SIDEBAR_CLASS,
    STATUS_CLASSES,
    WORKSPACE_CLASS,
    create_layout,
    render_steps,
    task_row,
)
from .runner import RunController, RunState
from .visualization import CYTOSCAPE_STYLESHEET, format_reward_label, reward_machine_to_elements


IMPORTED_RM_VALUE = "imported"


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
            _next_output_filename(environment_name),
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
        if not filename or not filename.lower().endswith(".rm"):
            return no_update, "Could not load Reward Machine: choose a .rm file.", error_class
        try:
            text = _decode_uploaded_markdown(contents)
            parse_reward_machine(text)
        except (ValueError, UnicodeDecodeError) as error:
            return no_update, f"Could not load Reward Machine: {error}", error_class
        return (
            {"filename": filename, "text": text},
            f"Loaded {filename}; select it below.",
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
    ) -> str:
        if not (markdown or "").strip():
            return "Enter or upload environment Markdown first."
        tasks = tuple((value or "").strip() for value in task_values or [])
        if not tasks or any(not task for task in tasks):
            return "Every task row must contain text."
        output_name = (output_filename or "").strip()
        if not output_name:
            return "Enter a base output filename."
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
            )
        except (RuntimeError, ValueError) as error:
            return f"Could not start run: {error}"
        return "Run started; progress will appear in the log."

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
            options.append({"label": f"Imported: {imported['filename']}", "value": IMPORTED_RM_VALUE})
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
        elif selected_is_generated or (selected_index == IMPORTED_RM_VALUE and imported is not None):
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
            selected,
            not bool(options),
            render_steps(snapshot.tasks, task_selected),
            next_selection,
        )

    @app.callback(
        Output("result-summary", "children"),
        Output("result-text", "value"),
        Output("rm-graph", "elements"),
        Input("output-selector", "value"),
        Input("imported-reward-machine", "data"),
    )
    def render_selected_result(
        selected_index: int | str | None,
        imported_data: dict[str, str] | None = None,
    ) -> tuple[str, str, list]:
        if selected_index is None:
            return "No completed output selected.", "", []
        if selected_index == IMPORTED_RM_VALUE:
            imported = _imported_reward_machine(imported_data)
            if imported is None:
                return "No imported Reward Machine selected.", "", []
            try:
                reward_machine = parse_reward_machine(imported["text"])
            except ValueError as error:
                return f"Could not render imported Reward Machine: {error}", "", []
            return (
                f"Imported: {imported['filename']}",
                imported["text"],
                reward_machine_to_elements(reward_machine),
            )
        snapshot = controller.snapshot()
        if (
            not isinstance(selected_index, int)
            or isinstance(selected_index, bool)
            or not 0 <= selected_index < len(snapshot.results)
        ):
            return "No completed output selected.", "", []
        result = snapshot.results[selected_index]
        output_path = snapshot.output_paths[selected_index]
        summary = f"{output_path} | {result.proposal.task}"
        return summary, result.text, reward_machine_to_elements(result.reward_machine)

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
        Input("rm-graph", "mouseoverEdgeData"),
        Input("graph-transition-pin", "data"),
        Input("output-selector", "value"),
        Input("imported-reward-machine", "data"),
    )
    def render_transition_inspector(
        hovered_edge: dict | None,
        pinned_edge: dict | None,
        _selected_output: int | str | None,
        _imported_reward_machine: dict[str, str] | None,
    ) -> tuple[str, object]:
        if {
            "output-selector.value",
            "imported-reward-machine.data",
        } & ctx.triggered_prop_ids.keys():
            return _transition_inspector_class(False), []

        selected_edge = pinned_edge or hovered_edge

        if not isinstance(selected_edge, dict) or not isinstance(selected_edge.get("cases"), list):
            return _transition_inspector_class(False), []
        return (
            _transition_inspector_class(True),
            _transition_inspector_children(selected_edge),
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
    ) -> tuple[bool, str, str, str, str, str, bool]:
        focused = not bool(focused)
        if focused:
            return (
                True,
                FOCUS_WORKSPACE_CLASS,
                "hidden",
                "hidden",
                FOCUS_OUTPUT_REGION_CLASS,
                "Exit focus",
                True,
            )
        return (
            False,
            WORKSPACE_CLASS,
            INPUT_REGION_CLASS,
            RUN_SIDEBAR_CLASS,
            OUTPUT_REGION_CLASS,
            "Focus graph",
            False,
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
    return f"{base} pointer-events-none visible" if visible else f"{base} pointer-events-none invisible"


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


def _imported_reward_machine(data: object) -> dict[str, str] | None:
    """Return a well-shaped imported Reward Machine payload, if present."""
    if not isinstance(data, dict):
        return None
    filename = data.get("filename")
    text = data.get("text")
    if not isinstance(filename, str) or not isinstance(text, str):
        return None
    return {"filename": filename, "text": text}


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


def _next_output_filename(environment_filename: str) -> str:
    """Return the first available RM name based on an uploaded environment file."""
    stem = Path(environment_filename).stem or "reward-machine"
    base_name = f"{stem}.rm"
    output_dir = Configuration.OUTPUT_PATH
    if not (output_dir / base_name).exists():
        return base_name

    suffix_pattern = re.compile(rf"^{re.escape(stem)}-(\d+)\.rm$")
    suffixes = (
        int(match.group(1))
        for path in output_dir.iterdir()
        if (match := suffix_pattern.fullmatch(path.name))
    )
    return f"{stem}-{max(suffixes, default=0) + 1:03d}.rm"
