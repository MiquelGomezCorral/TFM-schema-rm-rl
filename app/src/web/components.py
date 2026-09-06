"""Reusable Dash layout factories for the local Reward Machine UI."""

from dash import dcc, html

from .runner import STEP_ORDER, StepState, TaskSnapshot


# ======================================================================================
#                                     STATUS STYLES
# ======================================================================================

STATUS_BASE = (
    "status min-h-[2.15rem] flex-1 rounded-[0.55rem] "
    "border border-[rgb(40_59_89_/_70%)] px-[0.7rem] py-[0.48rem] "
    "text-[0.78rem] leading-[1.35]"
)
STATUS_CLASSES = {
    "idle": f"{STATUS_BASE} status-info text-muted",
    "running": f"{STATUS_BASE} status-info text-accent",
    "completed": f"{STATUS_BASE} status-success text-success",
    "failed": f"{STATUS_BASE} status-error text-[#fda4af]",
}

INPUT_REGION_CLASS = (
    "input-region grid items-start gap-3.5 [grid-area:input] "
    "grid-cols-2 max-[1200px]:grid-cols-1"
)
RUN_SIDEBAR_CLASS = (
    "run-sidebar control-card sticky top-4 self-stretch [grid-area:sidebar] "
    "flex min-w-0 flex-col gap-3 rounded-[0.85rem] border border-border "
    "bg-surface p-[0.95rem] max-[900px]:static"
)
OUTPUT_REGION_CLASS = (
    "output-region grid min-h-[34rem] gap-3.5 [grid-area:output] "
    "grid-cols-2 max-[1200px]:grid-cols-1 max-[800px]:min-h-0"
)
WORKSPACE_CLASS = (
    "workspace grid items-start gap-3.5 "
    "[grid-template-areas:'sidebar_input'_'sidebar_output'] "
    "[grid-template-columns:19rem_minmax(0,1fr)] "
    "max-[900px]:grid-cols-1 "
    "max-[900px]:[grid-template-areas:'input'_'sidebar'_'output']"
)
FOCUS_WORKSPACE_CLASS = (
    "workspace grid items-start gap-3.5 "
    "[grid-template-areas:'output'] [grid-template-columns:minmax(0,1fr)]"
)
FOCUS_OUTPUT_REGION_CLASS = (
    "output-region grid min-h-[34rem] gap-3.5 [grid-area:output] "
    "[grid-template-columns:19rem_minmax(0,1fr)] max-[800px]:min-h-0"
)
SECTION_ICON_CLASS = (
    "section-number grid h-[1.65rem] w-[1.65rem] flex-none place-items-center "
    "rounded-[0.45rem] border border-border-strong bg-[rgb(56_189_248_/_8%)] text-accent"
)
GRAPH_TOOLBAR_BUTTON_CLASS = (
    "inline-flex min-h-[2.15rem] shrink-0 cursor-pointer items-center justify-center "
    "rounded-[0.45rem] border border-border-strong bg-surface-hover px-2.5 text-[0.72rem] "
    "font-bold text-muted transition duration-150 ease-out hover:border-accent hover:text-accent "
    "focus-visible:outline-3 focus-visible:outline-offset-2 "
    "focus-visible:outline-[rgba(56,189,248,0.35)]"
)


def _icon(name: str, class_name: str) -> html.Span:
    """Render one local SVG icon using the surrounding text color."""
    source = f"url('/assets/icons/{name}.svg')"
    return html.Span(
        className=f"icon inline-block shrink-0 bg-current {class_name}",
        style={
            "WebkitMask": f"{source} center / contain no-repeat",
            "mask": f"{source} center / contain no-repeat",
        },
        **{"aria-hidden": "true"},
    )


def _section_icon(name: str) -> html.Span:
    """Render a boxed section icon with the shared panel treatment."""
    return html.Span(_icon(name, "size-[0.95rem]"), className=SECTION_ICON_CLASS)


STEP_LABELS = {
    "generate": "Generate and validate interpretation",
    "task_critic": "Task interpretation critic",
    "ltlf": "Build LTLf from DECLARE templates",
    "dfa": "Compile DFA with FL-AT / MONA",
    "reward_machine": "Build Reward Machine",
    "rm_critic": "Reward Machine critic",
}
STEP_STATUS_CLASSES = {
    StepState.PENDING: "border-border-strong text-muted",
    StepState.RUNNING: "border-accent text-accent",
    StepState.COMPLETED: "border-success text-success",
    StepState.SKIPPED: "border-border text-muted",
    StepState.FAILED: "border-[#fb7185] text-[#fda4af]",
}
STEP_STATUS_SYMBOLS = {
    StepState.PENDING: "○",
    StepState.RUNNING: "●",
    StepState.COMPLETED: "✓",
    StepState.SKIPPED: "—",
    StepState.FAILED: "!",
}


def _task_status(task: TaskSnapshot) -> str:
    if task.state is StepState.RUNNING:
        return f"Task {task.index + 1} of {{total}} · Attempt {task.attempt} of 3"
    if task.state is StepState.COMPLETED:
        return f"Task {task.index + 1} of {{total}} · Accepted on attempt {task.attempt} of 3"
    if task.state is StepState.FAILED:
        return f"Task {task.index + 1} of {{total}} · Failed on attempt {task.attempt} of 3"
    return f"Task {task.index + 1} of {{total}} · Not started"


def _step_row(step) -> html.Div:
    status = step.state
    duration = f" · {step.elapsed:.3f}s" if step.elapsed is not None else ""
    return html.Div(
        [
            html.Span(
                STEP_STATUS_SYMBOLS[status],
                className=f"step-symbol grid size-6 place-items-center rounded-full border {STEP_STATUS_CLASSES[status]}",
                **{"aria-hidden": "true"},
            ),
            html.Span(
                STEP_LABELS[step.step.value],
                className="step-label min-w-0 flex-1 text-[0.8rem] font-semibold text-text",
            ),
            html.Span(
                f"{status.value.capitalize()}{duration}",
                className=f"step-state text-[0.72rem] {STEP_STATUS_CLASSES[status].split()[-1]}",
            ),
        ],
        className="run-step flex min-h-10 items-center gap-2 rounded-[0.45rem] border border-border bg-surface-raised px-2 py-1.5",
    )


def render_steps(tasks: tuple[TaskSnapshot, ...], selected_index: int = 0) -> html.Div:
    """Render the selected task's structured progress and compact navigator."""
    if not tasks:
        return html.Div("No run yet.", className="steps-empty min-h-40 text-[0.8rem] text-muted")
    selected_index = max(0, min(selected_index, len(tasks) - 1))
    task = tasks[selected_index]
    status = _task_status(task).format(total=len(tasks))
    navigation: list[object] = []
    if len(tasks) > 1:
        start = min(max(selected_index - 2, 0), max(len(tasks) - 5, 0))
        indexes = list(range(start, min(start + 5, len(tasks))))
        if start:
            navigation.append(html.Span("…", className="task-ellipsis px-1 text-muted"))
        for index in indexes:
            state = tasks[index].state
            dot_class = {
                StepState.COMPLETED: "bg-success",
                StepState.RUNNING: "bg-accent",
                StepState.FAILED: "bg-[#fb7185]",
            }.get(state, "bg-[#64748b]")
            selected_class = " ring-2 ring-accent ring-offset-2 ring-offset-surface" if index == selected_index else ""
            navigation.append(
                html.Button(
                    html.Span(className=f"task-dot size-2.5 rounded-full {dot_class}{selected_class}", **{"aria-hidden": "true"}),
                    id={"type": "task-dot", "index": index},
                    n_clicks=0,
                    className="task-dot-button grid size-8 place-items-center rounded-full border border-transparent hover:border-border-strong focus-visible:border-accent focus-visible:outline-2",
                    **{"aria-label": f"View task {index + 1} of {len(tasks)}"},
                )
            )
        if start + len(indexes) < len(tasks):
            navigation.append(html.Span("…", className="task-ellipsis px-1 text-muted"))
        navigation = [
            html.Button(
                _icon("chevron-right", "size-4 -rotate-180"),
                id="run-prev",
                n_clicks=0,
                className="task-nav-button grid size-8 place-items-center rounded-full border border-border-strong text-muted hover:border-accent hover:text-accent focus-visible:outline-2",
                **{"aria-label": "View previous task"},
            ),
            *navigation,
            html.Button(
                _icon("chevron-right", "size-4"),
                id="run-next",
                n_clicks=0,
                className="task-nav-button grid size-8 place-items-center rounded-full border border-border-strong text-muted hover:border-accent hover:text-accent focus-visible:outline-2",
                **{"aria-label": "View next task"},
            ),
        ]
    children: list[object] = [
        html.Div(
            [
                html.Div(
                    [
                        html.Div(
                            [
                                html.H3(
                                    task.task,
                                    title=task.task,
                                    className=(
                                        "run-task-title min-w-0 overflow-hidden text-ellipsis "
                                        "whitespace-nowrap text-[0.86rem] font-bold text-text"
                                    ),
                                ),
                                html.Span(
                                    task.state.value.capitalize(),
                                    className=(
                                        "run-task-state shrink-0 rounded-full border px-2 py-1 text-[0.68rem] "
                                        f"font-bold {STEP_STATUS_CLASSES[task.state]}"
                                    ),
                                ),
                            ],
                            className="run-task-title-row flex min-w-0 items-center justify-between gap-2",
                        ),
                        html.P(
                            status,
                            className=(
                                "run-task-status mt-1 w-full overflow-hidden text-ellipsis whitespace-nowrap "
                                "text-[0.74rem] text-muted"
                            ),
                        ),
                    ],
                    className="run-task-heading min-w-0 w-full",
                ),
            ],
            className="run-task-header min-w-0",
        ),
        html.Div(
            [_step_row(step) for step in task.steps],
            className="run-steps-list grid gap-1.5",
        ),
    ]
    if task.retry_note:
        children.append(
            html.P(
                f"Latest retry: {task.retry_note}",
                className="run-retry-note rounded-[0.45rem] border border-[#fb7185] bg-[rgb(251_113_133_/_8%)] px-2.5 py-2 text-[0.74rem] leading-[1.4] text-[#fda4af]",
            )
        )
    if navigation:
        children.append(html.Nav(navigation, className="run-task-navigation mt-1 flex items-center justify-center gap-1", **{"aria-label": "Task navigation"}))
    return html.Div(children, className="run-steps-content flex min-h-40 flex-col gap-2")


# ======================================================================================
#                                    INPUT CONTROLS
# ======================================================================================

def environment_input() -> html.Section:
    """Build the upload and editable Markdown environment controls."""
    return html.Section(
        [
            html.Div(
                [
                    _section_icon("file-text"),
                    html.Div(
                        [
                            html.H2(
                                "Environment",
                                className="section-title text-[0.98rem] font-semibold tracking-[-0.015em]",
                            ),
                            html.P(
                                "Upload UTF-8 Markdown or paste it below.",
                                className="section-description mt-[0.18rem] text-[0.76rem] leading-[1.4] text-muted",
                            ),
                        ]
                    ),
                ],
                className="section-heading flex items-start gap-[0.7rem]",
            ),
            dcc.Upload(
                id="environment-upload",
                children=html.Div(
                    [
                        _icon("upload", "upload-icon size-[1.05rem]"),
                        html.Span("Choose a Markdown file or drop it here"),
                    ],
                    className="upload-content flex items-center justify-center gap-2",
                ),
                accept=".md,text/markdown,text/plain",
                multiple=False,
                disabled=False,
                className=(
                    "upload-control grid min-h-[3.3rem] cursor-pointer place-items-center "
                    "border border-dashed border-border-strong p-3 text-center text-[0.8rem] "
                    "text-accent transition duration-150 ease-out hover:border-accent "
                    "hover:bg-surface-hover focus-visible:outline-3 focus-visible:outline-offset-2 "
                    "focus-visible:outline-[rgba(56,189,248,0.35)]"
                ),
            ),
            html.Div(
                "No file uploaded; pasted content uses environment.md.",
                id="upload-status",
                className="field-hint text-[0.76rem] leading-[1.4] text-muted",
            ),
            html.Label(
                [
                    html.Span(
                        "Markdown",
                        className="field-label text-[0.7rem] font-[750] uppercase tracking-[0.06em] text-muted",
                    ),
                    dcc.Textarea(
                        id="environment-markdown",
                        value="",
                        placeholder="# Environment\n\n## Propositions\n- `event`: Description",
                        className=(
                            "markdown-input block min-h-[11rem] w-full resize-y border "
                            "border-border-strong !border-border-strong !bg-surface-raised "
                            "px-3 py-[0.7rem] !text-text outline-0 transition duration-150 "
                            "ease-out placeholder:!text-[#8295b2] focus-visible:outline-3 "
                            "focus-visible:outline-offset-2 "
                            "focus-visible:outline-[rgba(56,189,248,0.35)]"
                        ),
                        spellCheck=True,
                        disabled=False,
                    ),
                ],
                className="field flex min-w-0 flex-col gap-[0.35rem]",
            ),
        ],
        className=(
            "environment-card control-card flex min-w-0 flex-col gap-3 rounded-[0.85rem] "
            "border border-border bg-surface p-[0.95rem]"
        ),
    )


def task_row(
    index: int,
    task: str = "",
) -> html.Div:
    """Build one ordinary-language task row."""
    return html.Div(
        [
            html.Div(
                [
                    html.Span(
                        f"Task {index + 1}",
                        className=(
                            "task-title min-w-0 overflow-hidden text-ellipsis whitespace-nowrap "
                            "text-[0.82rem] font-extrabold text-text"
                        ),
                    ),
                    html.Button(
                        _icon("trash", "remove-task-icon size-[1.05rem]"),
                        id={"type": "remove-task", "index": index},
                        n_clicks=0,
                        disabled=index == 0,
                        className=(
                            "remove-task button button-quiet ml-auto min-h-[2.75rem] "
                            "w-[2.75rem] min-w-[2.75rem] cursor-pointer rounded-[0.55rem] "
                            "border border-border-strong bg-transparent p-0 text-muted "
                            "transition duration-150 ease-out enabled:hover:-translate-y-px "
                            "enabled:hover:border-[#fb7185] enabled:hover:text-[#fda4af] "
                            "enabled:active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-40"
                        ),
                        **{"aria-label": f"Remove task {index + 1}"},
                    ),
                ],
                className="task-header flex min-w-0 flex-nowrap items-center gap-2",
            ),
            html.Label(
                [
                    html.Span(
                        f"Task {index + 1} text",
                        className="task-input-label sr-only",
                    ),
                    dcc.Textarea(
                        id={"type": "task-input", "index": index},
                        value=task,
                        placeholder="e.g. Collect the key, open the door, then reach the goal",
                        className=(
                            "task-input block min-h-[4.2rem] w-full resize-y border "
                            "border-border-strong !border-border-strong !bg-surface-raised "
                            "px-3 py-[0.7rem] !text-text outline-0 transition duration-150 "
                            "ease-out placeholder:!text-[#8295b2] focus-visible:outline-3 "
                            "focus-visible:outline-offset-2 "
                            "focus-visible:outline-[rgba(56,189,248,0.35)]"
                        ),
                        rows=2,
                        disabled=False,
                    ),
                ],
                className="field flex min-w-0 flex-col gap-[0.35rem]",
            ),
        ],
        id={"type": "task-row", "index": index},
        className="task-row flex min-w-0 flex-col gap-[0.45rem]",
    )


def task_input() -> html.Section:
    """Build the dynamic task section."""
    return html.Section(
        [
            html.Div(
                [
                    _section_icon("list-todo"),
                    html.Div(
                        [
                            html.H2(
                                "Tasks",
                                className="section-title text-[0.98rem] font-semibold tracking-[-0.015em]",
                            ),
                            html.P(
                                "Each task produces one independently compiled Reward Machine.",
                                className="section-description mt-[0.18rem] text-[0.76rem] leading-[1.4] text-muted",
                            ),
                        ]
                    ),
                ],
                className="section-heading flex items-start gap-[0.7rem]",
            ),
            html.Div(
                [task_row(0)],
                id="task-rows",
                className="task-rows flex min-w-0 flex-col gap-[0.65rem]",
            ),
            html.Button(
                [_icon("plus", "add-task-icon size-4"), html.Span("Add task")],
                id="add-task",
                n_clicks=0,
                className=(
                    "add-task button button-secondary inline-flex min-h-[2.55rem] cursor-pointer "
                    "items-center justify-center gap-2 "
                    "rounded-[0.55rem] border border-border-strong bg-surface-hover "
                    "px-[0.85rem] py-[0.62rem] text-[0.84rem] font-[750] text-text "
                    "transition duration-150 ease-out enabled:hover:-translate-y-px "
                    "enabled:hover:border-accent enabled:active:translate-y-0 "
                    "disabled:cursor-not-allowed disabled:opacity-40"
                ),
            ),
        ],
        className=(
            "tasks-card control-card flex min-w-0 flex-col gap-3 rounded-[0.85rem] "
            "border border-border bg-surface p-[0.95rem]"
        ),
    )


# ======================================================================================
#                                   OUTPUT CONTROLS
# ======================================================================================

def output_controls() -> html.Aside:
    """Build output filename, critic controls, and run status."""
    return html.Aside(
        [
            html.Div(
                [
                    _section_icon("wand-sparkles"),
                    html.Div(
                        [
                            html.H2(
                                "Generate",
                                className="section-title text-[0.98rem] font-semibold tracking-[-0.015em]",
                            ),
                            html.P(
                                "Critics validate each task automatically.",
                                className="section-description mt-[0.18rem] text-[0.76rem] leading-[1.4] text-muted",
                            ),
                        ]
                    ),
                ],
                className="section-heading flex items-start gap-[0.7rem]",
            ),
            html.Label(
                [
                    html.Span(
                        "Base output filename",
                        className="field-label text-[0.7rem] font-[750] uppercase tracking-[0.06em] text-muted",
                    ),
                    dcc.Input(
                        id="output-filename",
                        type="text",
                        value="reward-machine.rm",
                        placeholder="reward-machine.rm",
                        className=(
                            "text-input min-h-[2.55rem] w-full border border-border-strong "
                            "!border-border-strong !bg-surface-raised px-[0.72rem] py-[0.65rem] "
                            "!text-text outline-0 transition duration-150 ease-out "
                            "placeholder:!text-[#8295b2] focus-visible:outline-3 "
                            "focus-visible:outline-offset-2 "
                            "focus-visible:outline-[rgba(56,189,248,0.35)]"
                        ),
                        disabled=False,
                    ),
                ],
                className="field flex min-w-0 flex-col gap-[0.35rem]",
            ),
            html.Button(
                [
                    _icon("play", "generate-button-icon size-4"),
                    html.Span("Generate Reward Machines"),
                ],
                id="generate-button",
                n_clicks=0,
                className=(
                    "generate-button button button-primary inline-flex min-h-[2.55rem] cursor-pointer "
                    "items-center justify-center gap-2 "
                    "rounded-[0.55rem] border border-accent bg-accent px-[0.85rem] "
                    "py-[0.62rem] text-[0.84rem] font-[750] text-[#04131e] transition "
                    "duration-150 ease-out enabled:hover:-translate-y-px "
                    "enabled:hover:border-accent enabled:active:translate-y-0 "
                    "disabled:cursor-not-allowed disabled:opacity-40"
                ),
            ),
            html.Fieldset(
                [
                    html.Legend(
                        "Automatic critics",
                        className=(
                            "critic-legend px-[0.35rem] text-[0.7rem] font-[750] "
                            "uppercase tracking-[0.06em] text-muted"
                        ),
                    ),
                    dcc.Checklist(
                        id="critic-options",
                        options=[
                            {"label": " Task interpretation critic", "value": "task_critic"},
                            {"label": " Reward Machine critic", "value": "rm_critic"},
                        ],
                        value=["task_critic", "rm_critic"],
                        className="critic-options grid gap-[0.45rem] !text-text",
                    ),
                ],
                className=(
                    "critic-controls m-0 min-w-0 rounded-[0.55rem] border "
                    "border-border-strong bg-surface-raised px-3 pb-3 pt-[0.65rem] text-text"
                ),
            ),
            html.Div(
                id="run-feedback",
                className="field-hint text-[0.76rem] leading-[1.4] text-muted",
            ),
            html.Div(
                [
                    html.H2(
                        "Run status",
                        className="status-title text-[0.98rem] font-semibold tracking-[-0.015em]",
                    ),
                    html.Div(
                        "Idle",
                        id="run-status",
                        className=STATUS_CLASSES["idle"],
                        role="status",
                        **{"aria-live": "polite"},
                    ),
                ],
                className=(
                    "status-heading flex items-center gap-[0.9rem] "
                    "max-[560px]:flex-col max-[560px]:items-stretch"
                ),
            ),
            dcc.Tabs(
                id="run-tabs",
                value="steps",
                className="run-tabs flex-1",
                children=[
                    dcc.Tab(
                        label="Steps",
                        value="steps",
                        className="run-tab border-b border-border px-2 py-2 text-[0.76rem] font-bold text-muted",
                        selected_className="run-tab-selected border-accent text-accent",
                        style={"backgroundColor": "#101a2b", "color": "#a7b7ce", "padding": "8px"},
                        selected_style={"backgroundColor": "#17243a", "color": "#38bdf8", "padding": "8px"},
                        children=html.Div(
                            [
                                "No run yet.",
                                html.Button(id="run-prev", n_clicks=0, className="hidden placeholder-button"),
                                html.Button(id="run-next", n_clicks=0, className="hidden placeholder-button"),
                                html.Button(id={"type": "task-dot", "index": 0}, n_clicks=0, className="hidden placeholder-button"),
                            ],
                            id="run-steps",
                            className="steps-empty text-[0.8rem] text-muted",
                        ),
                    ),
                    dcc.Tab(
                        label="Log",
                        value="log",
                        className="run-tab border-b border-border px-2 py-2 text-[0.76rem] font-bold text-muted",
                        selected_className="run-tab-selected border-accent text-accent",
                        style={"backgroundColor": "#101a2b", "color": "#a7b7ce", "padding": "8px"},
                        selected_style={"backgroundColor": "#17243a", "color": "#38bdf8", "padding": "8px"},
                        children=html.Pre(
                            "No run yet.",
                            id="run-log",
                            className=(
                                "run-log m-0 h-full max-h-[34rem] overflow-auto whitespace-pre-wrap "
                                "rounded-[0.55rem] border border-border bg-[#0c1626] p-3 font-mono "
                                "text-[0.76rem] leading-[1.5] text-muted "
                                "[scrollbar-color:var(--color-border-strong)_transparent]"
                            ),
                        ),
                    ),
                ],
            ),
        ],
        id="run-sidebar",
        className=RUN_SIDEBAR_CLASS,
    )


# ======================================================================================
#                                     RESULT PANELS
# ======================================================================================

def result_panel() -> html.Section:
    """Build the synchronized output selector and exact raw text view."""
    return html.Section(
        [
            html.Div(
                [
                    _section_icon("file-code"),
                    html.Div(
                        [
                            html.H2(
                                "Compiled Reward Machine",
                                className="panel-title text-[0.98rem] font-semibold tracking-[-0.015em]",
                            ),
                            html.P(
                                "Import a processed Reward Machine or select a completed output.",
                                className="section-description mt-[0.18rem] text-[0.76rem] leading-[1.4] text-muted",
                            ),
                        ]
                    ),
                ],
                className="section-heading flex items-start gap-[0.7rem]",
            ),
            html.Label(
                [
                    html.Span(
                        "Import processed Reward Machine",
                        className="field-label text-[0.7rem] font-[750] uppercase tracking-[0.06em] text-muted",
                    ),
                    dcc.Upload(
                        id="reward-machine-upload",
                        children=html.Div(
                            [
                                _icon("upload", "upload-icon size-[1.05rem]"),
                                html.Span("Choose an .rm file or drop it here"),
                            ],
                            className="upload-content flex items-center justify-center gap-2",
                        ),
                        accept=".rm,text/plain",
                        multiple=False,
                        disabled=False,
                        className=(
                            "upload-control grid min-h-[3.3rem] cursor-pointer place-items-center "
                            "border border-dashed border-border-strong p-3 text-center text-[0.8rem] "
                            "text-accent transition duration-150 ease-out hover:border-accent "
                            "hover:bg-surface-hover focus-visible:outline-3 focus-visible:outline-offset-2 "
                            "focus-visible:outline-[rgba(56,189,248,0.35)]"
                        ),
                    ),
                ],
                className="field flex min-w-0 flex-col gap-[0.35rem]",
            ),
            html.Div(
                "No imported Reward Machine.",
                id="reward-machine-upload-status",
                className="field-hint text-[0.76rem] leading-[1.4] text-muted",
            ),
            html.Label(
                [
                    html.Span(
                        "Completed output",
                        className="field-label text-[0.7rem] font-[750] uppercase tracking-[0.06em] text-muted",
                    ),
                    dcc.Dropdown(
                        id="output-selector",
                        options=[],
                        value=None,
                        placeholder="Select a completed output",
                        clearable=False,
                        searchable=False,
                        disabled=True,
                        className=(
                            "output-selector min-h-[2.75rem] w-full rounded-[0.55rem] "
                            "border !border-border-strong !bg-surface-raised p-0 text-left "
                            "!text-text transition duration-150 ease-out "
                            "focus:!border-accent focus:outline-3 "
                            "focus:outline-offset-2 focus:outline-[rgb(56_189_248_/_35%)] "
                            "focus-visible:!border-accent focus-visible:outline-3 "
                            "focus-visible:outline-offset-2 "
                            "focus-visible:outline-[rgb(56_189_248_/_35%)] "
                            "disabled:cursor-not-allowed disabled:!border-border "
                            "disabled:!bg-[#0d1625] disabled:!text-muted disabled:opacity-50"
                        ),
                    ),
                ],
                className="field flex min-w-0 flex-col gap-[0.35rem]",
            ),
            html.Div(
                id="result-summary",
                className="result-summary text-[0.76rem] leading-[1.4] text-muted",
            ),
            html.Label(
                [
                    html.Span(
                        "Serialized Reward Machine",
                        className="field-label text-[0.7rem] font-[750] uppercase tracking-[0.06em] text-muted",
                    ),
                    dcc.Textarea(
                        id="result-text",
                        value="",
                        readOnly=True,
                        className=(
                            "result-text block min-h-[24rem] w-full flex-1 resize-y "
                            "whitespace-pre border border-border-strong !border-border-strong "
                            "!bg-surface-raised px-3 py-[0.7rem] font-mono text-[0.8rem] "
                            "leading-[1.5] !text-text outline-0 transition duration-150 "
                            "ease-out focus-visible:outline-3 focus-visible:outline-offset-2 "
                            "focus-visible:outline-[rgba(56,189,248,0.35)]"
                        ),
                    ),
                ],
                className="field flex min-w-0 flex-col gap-[0.35rem]",
            ),
        ],
        className=(
            "output-panel flex min-h-0 min-w-0 flex-col gap-3 rounded-[0.85rem] "
            "border border-border bg-surface p-[0.95rem] max-[800px]:min-h-[30rem]"
        ),
    )


def graph_panel(stylesheet: list[dict] | None = None) -> html.Section:
    """Build the interactive Cytoscape graph panel."""
    import dash_cytoscape as cyto

    return html.Section(
        [
            html.Div(
                [
                    html.Div(
                        [
                            _section_icon("network"),
                            html.H2(
                                "State graph",
                                className="panel-title text-[0.98rem] font-semibold tracking-[-0.015em]",
                            ),
                        ],
                        className="panel-heading flex min-w-0 items-center gap-2 justify-self-start",
                    ),
                    html.Button(
                        "Focus graph",
                        id="graph-focus-toggle",
                        n_clicks=0,
                        className=f"graph-focus-toggle {GRAPH_TOOLBAR_BUTTON_CLASS} justify-self-center max-[800px]:hidden",
                        **{"aria-label": "Focus graph", "aria-pressed": False},
                    ),
                    html.Details(
                        [
                            html.Summary(
                                "Graph legend",
                                className=f"graph-legend-summary {GRAPH_TOOLBAR_BUTTON_CLASS} list-none",
                            ),
                            html.Div(
                                [
                                    html.Ul(
                                        [
                                            html.Li(
                                        [
                                            html.Span(
                                                className=(
                                                    "legend-swatch inline-block h-4 w-4 flex-none "
                                                    "rounded-[0.25rem] border-2 border-[#5878a8] "
                                                    "bg-[#18263d]"
                                                ),
                                                **{"aria-hidden": "true"},
                                            ),
                                            html.Span("Default state"),
                                        ],
                                        className="legend-row flex items-center gap-2 text-[0.72rem] text-muted",
                                            ),
                                            html.Li(
                                        [
                                            html.Span(
                                                className=(
                                                    "legend-swatch-initial legend-swatch inline-block h-4 w-4 "
                                                    "flex-none rounded-[0.25rem] border-[3px] border-accent "
                                                    "bg-[#18263d]"
                                                ),
                                                **{"aria-hidden": "true"},
                                            ),
                                            html.Span("Initial state"),
                                        ],
                                        className="legend-row flex items-center gap-2 text-[0.72rem] text-muted",
                                            ),
                                            html.Li(
                                        [
                                            html.Span(
                                                className=(
                                                    "legend-swatch-accepting legend-swatch inline-block h-4 w-4 "
                                                    "flex-none rounded-[0.25rem] border-2 border-success "
                                                    "bg-[#14532d]"
                                                ),
                                                **{"aria-hidden": "true"},
                                            ),
                                            html.Span("Accepting state"),
                                        ],
                                        className="legend-row flex items-center gap-2 text-[0.72rem] text-muted",
                                            ),
                                            html.Li(
                                        [
                                            html.Span(
                                                className=(
                                                    "legend-swatch-rejecting legend-swatch inline-block h-4 w-4 "
                                                    "flex-none rounded-[0.25rem] border-2 border-[#fb7185] "
                                                    "bg-[#572033]"
                                                ),
                                                **{"aria-hidden": "true"},
                                            ),
                                            html.Span("Rejecting state"),
                                        ],
                                        className="legend-row flex items-center gap-2 text-[0.72rem] text-muted",
                                            ),
                                            html.Li(
                                        [
                                            html.Span(
                                                className=(
                                                    "legend-swatch-transition legend-swatch inline-block h-0 "
                                                    "w-4 flex-none rounded-none border-0 border-t-2 "
                                                    "border-[#7189ad] bg-transparent"
                                                ),
                                                **{"aria-hidden": "true"},
                                            ),
                                            html.Span("Explicit transition"),
                                        ],
                                        className="legend-row flex items-center gap-2 text-[0.72rem] text-muted",
                                            ),
                                        ],
                                        className=(
                                            "legend-list m-[0.55rem_0_0] grid list-none "
                                            "gap-[0.35rem] p-0"
                                        ),
                                    ),
                                    html.P(
                                        "Only explicit transitions are shown. Omitted transitions are zero-reward self-loops.",
                                        className=(
                                            "graph-explanation mt-[0.55rem] max-w-[25rem] whitespace-normal break-words "
                                            "text-[0.76rem] leading-[1.4] text-muted max-[560px]:m-0 max-[560px]:text-left"
                                        ),
                                    ),
                                ],
                                className=(
                                    "graph-legend-panel absolute right-0 top-full z-20 mt-1 max-h-[calc(100dvh_-_7rem)] "
                                    "w-[18rem] max-w-[calc(100vw_-_2rem)] overflow-auto whitespace-normal rounded-[0.6rem] "
                                    "border border-border-strong bg-[#101a2b] p-2 text-text shadow-[0_12px_30px_rgb(0_0_0_/_35%)]"
                                ),
                            ),
                        ],
                        className="graph-legend relative justify-self-end",
                    ),
                ],
                className=(
                    "graph-toolbar relative grid flex-none grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] "
                    "items-center gap-4 pb-1"
                ),
            ),
            html.Div(
                [
                    cyto.Cytoscape(
                        id="rm-graph",
                        elements=[],
                        layout={
                            "name": "cola",
                            "fit": False,
                            "infinite": False,
                            "nodeSpacing": 16,
                            "edgeLength": 130,
                            "avoidOverlap": True,
                        },
                        stylesheet=stylesheet or [],
                        responsive=True,
                        boxSelectionEnabled=False,
                        userPanningEnabled=True,
                        userZoomingEnabled=True,
                        wheelSensitivity=0.15,
                        style={"width": "100%", "height": "100%"},
                        className="graph-canvas min-h-[27rem] h-full w-full flex-1",
                    ),
                    html.Div(
                        [
                            html.Div(id="graph-transition-content", className="grid gap-2"),
                            html.Button(
                                "Close",
                                id="graph-transition-close",
                                n_clicks=0,
                                className=(
                                    "graph-transition-close mt-2 min-h-[2rem] rounded-[0.4rem] border "
                                    "border-border-strong px-2.5 text-[0.7rem] font-bold text-muted cursor-pointer "
                                    "hover:border-accent hover:text-accent focus-visible:outline-2"
                                ),
                                **{"aria-label": "Close transition details"},
                            ),
                        ],
                        id="graph-transition-inspector",
                        className=(
                            "graph-transition-inspector pointer-events-none invisible absolute left-3 top-3 "
                            "z-10 max-h-[calc(100%_-_1.5rem)] w-[min(28rem,calc(100%_-_1.5rem))] "
                            "overflow-auto rounded-[0.65rem] border border-border-strong bg-[#101a2b] "
                            "p-3 text-text shadow-[0_12px_30px_rgb(0_0_0_/_35%)]"
                        ),
                    ),
                ],
                className="graph-stage relative min-h-0 flex-1",
            ),
        ],
        className=(
            "graph-panel relative flex min-h-0 min-w-0 flex-col gap-3 overflow-hidden "
            "rounded-[0.85rem] border border-border bg-[#0c1626] p-[0.95rem] "
            "max-[800px]:min-h-[30rem]"
        ),
    )


# ======================================================================================
#                                  APPLICATION LAYOUT
# ======================================================================================

def create_layout(stylesheet: list[dict] | None = None) -> html.Main:
    """Build the complete UI layout without registering callbacks."""
    return html.Main(
        [
            html.Header(
                [
                    html.Div(
                        [
                            html.P(
                                "Reward Machine compiler",
                                className=(
                                    "eyebrow text-[0.7rem] font-extrabold uppercase "
                                    "tracking-[0.14em] text-accent"
                                ),
                            ),
                            html.H1(
                                "Review and visualize",
                                className=(
                                    "app-title mt-[0.1rem] text-[clamp(1.55rem,2.4vw,2.2rem)] "
                                    "font-bold tracking-[-0.035em] max-[560px]:text-[1.65rem]"
                                ),
                            ),
                        ]
                    ),
                    html.P(
                        "A local path from environment Markdown to critic-validated Reward Machines.",
                        className=(
                            "usage-guide max-w-[43rem] text-right text-[0.88rem] "
                            "leading-[1.45] text-muted max-[800px]:text-left"
                        ),
                    ),
                ],
                className=(
                    "app-header flex flex-none items-end justify-between gap-x-8 gap-y-4 "
                    "max-[800px]:flex-col max-[800px]:items-start max-[800px]:gap-[0.55rem]"
                ),
            ),
            html.Div(
                [
                    html.Div(
                        [environment_input(), task_input()],
                        id="input-region",
                        className=INPUT_REGION_CLASS,
                    ),
                    output_controls(),
                    html.Div(
                        [result_panel(), graph_panel(stylesheet)],
                        id="output-region",
                        className=OUTPUT_REGION_CLASS,
                    ),
                ],
                id="workspace",
                className=WORKSPACE_CLASS,
            ),
            dcc.Interval(id="poll-interval", interval=500, n_intervals=0),
            dcc.Store(id="task-selection", data={"selected": 0, "last_active": None, "run_id": 0}),
            dcc.Store(id="imported-reward-machine", data=None),
            dcc.Store(id="graph-transition-pin", data=None),
            dcc.Store(id="graph-focus-state", data=False),
        ],
        className=(
            "app-shell flex min-h-dvh w-full flex-col gap-4 "
            "px-[clamp(1rem,2.5vw,2.5rem)] pb-6 pt-5 "
            "max-[560px]:gap-3 max-[560px]:px-[0.8rem] "
            "max-[560px]:pb-5 max-[560px]:pt-[0.9rem]"
        ),
    )
