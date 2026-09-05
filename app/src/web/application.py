"""Dash application factory and focused callback registration."""

import base64
from pathlib import Path

from dash import ALL, Dash, Input, Output, State, ctx, no_update
from dash.exceptions import PreventUpdate
import dash_cytoscape as cyto

from .components import STATUS_CLASSES, create_layout, render_steps, task_row
from .runner import RunController, RunState
from .visualization import CYTOSCAPE_STYLESHEET, reward_machine_to_elements


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
        Input("environment-upload", "contents"),
        State("environment-upload", "filename"),
        prevent_initial_call=True,
    )
    def load_environment(contents: str | None, filename: str | None) -> tuple[str, str]:
        if not contents:
            raise PreventUpdate
        try:
            markdown = _decode_uploaded_markdown(contents)
        except (ValueError, UnicodeDecodeError) as error:
            return no_update, f"Could not load UTF-8 Markdown: {error}"
        return markdown, f"Loaded {filename or 'environment.md'}; edit the text before generating."

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
        if not critic_options:
            return "Select at least one critic."
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
    )
    def poll_run(
        _n_intervals: int,
        selected_index: int | None = None,
        remove_ids: list[dict[str, int]] | None = None,
        _previous_clicks: int | None = None,
        _next_clicks: int | None = None,
        _dot_clicks: list[int | None] | None = None,
        selection_data: dict[str, int | None] | None = None,
    ) -> tuple[object, ...]:
        snapshot = controller.snapshot()
        active = snapshot.status is RunState.RUNNING
        options = [
            {"label": str(path), "value": index}
            for index, path in enumerate(snapshot.output_paths)
        ]
        valid_indices = set(range(len(options)))
        selected = selected_index if selected_index in valid_indices else (0 if options else None)
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
    )
    def render_selected_result(selected_index: int | None) -> tuple[str, str, list]:
        if selected_index is None:
            return "No completed output selected.", "", []
        snapshot = controller.snapshot()
        if not isinstance(selected_index, int) or not 0 <= selected_index < len(snapshot.results):
            return "No completed output selected.", "", []
        result = snapshot.results[selected_index]
        output_path = snapshot.output_paths[selected_index]
        summary = f"{output_path} | {result.proposal.task}"
        return summary, result.text, reward_machine_to_elements(result.reward_machine)

    app._run_controller = controller
    return app


def _decode_uploaded_markdown(contents: str) -> str:
    """Decode one Dash upload payload as UTF-8 Markdown."""
    _, encoded = contents.split(",", 1)
    return base64.b64decode(encoded, validate=True).decode("utf-8")


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
