"""Reusable Dash layout factories for the local Reward Machine UI."""

from collections.abc import Mapping

import dash_cytoscape as cyto
from dash import dcc, html

from src.utils import STEP_OUTPUT_ORDER, PipelineStep, render_step_text

from .highlight import highlight_step
from .runner import StepState, TaskSnapshot

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
    "input-region grid items-start gap-3.5 [grid-area:input] grid-cols-2 max-[1200px]:grid-cols-1"
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
SECTION_ICON_SIZE_CLASS = "size-[0.95rem]"
TOOLBAR_ICON_SIZE_CLASS = "size-[0.9rem]"
GRAPH_TOOLBAR_BUTTON_CLASS = (
    "inline-flex min-h-[2.15rem] shrink-0 cursor-pointer items-center justify-center gap-1.5 "
    "rounded-[0.45rem] border border-border-strong bg-surface-hover px-2.5 text-[0.72rem] "
    "font-bold text-muted transition duration-150 ease-out hover:border-accent hover:text-accent "
    "focus-visible:outline-3 focus-visible:outline-offset-2 "
    "focus-visible:outline-[rgba(56,189,248,0.35)]"
)


FIELD_CLASS = "field flex min-w-0 flex-col gap-[0.35rem]"
FIELD_LABEL_CLASS = "field-label text-[0.7rem] font-[750] uppercase tracking-[0.06em] text-muted"
FIELD_HINT_CLASS = "field-hint text-[0.76rem] leading-[1.4] text-muted"
SECTION_TITLE_CLASS = "section-title text-[0.98rem] font-semibold tracking-[-0.015em]"
PANEL_TITLE_CLASS = "panel-title text-[0.98rem] font-semibold tracking-[-0.015em]"
SECTION_DESCRIPTION_CLASS = (
    "section-description mt-[0.18rem] text-[0.76rem] leading-[1.4] text-muted"
)
UPLOAD_CONTROL_CLASS = (
    "upload-control grid min-h-[3.3rem] cursor-pointer place-items-center "
    "border border-dashed border-border-strong p-3 text-center text-[0.8rem] "
    "text-accent transition duration-150 ease-out hover:border-accent "
    "hover:bg-surface-hover focus-visible:outline-3 focus-visible:outline-offset-2 "
    "focus-visible:outline-[rgba(56,189,248,0.35)]"
)
OUTPUTS_OPTIONS_CLASS = "outputs-options grid gap-[0.45rem] !text-text"
LEGEND_ROW_CLASS = "legend-row flex items-center gap-2 text-[0.72rem] text-muted"
TASK_NAV_BUTTON_CLASS = (
    "task-nav-button grid size-8 place-items-center rounded-full border border-border-strong "
    "text-muted hover:border-accent hover:text-accent focus-visible:outline-2"
)

CRITIC_OPTIONS = [
    {"label": " Task interpretation critic", "value": "task_critic"},
    {"label": " Reward Machine critic", "value": "rm_critic"},
]
STEPS_REPORT_OPTIONS = [{"label": " Step report (.md)", "value": "steps_report"}]
LABELING_OPTIONS = [{"label": " MiniGrid labeling", "value": "labeling"}]
EMBEDDINGS_OPTIONS = [{"label": " Local state embeddings", "value": "embeddings"}]

RESULT_TAB_CLASS = "result-tab border-b border-border px-2 py-2 text-[0.76rem] font-bold text-muted"
RESULT_TAB_SELECTED_CLASS = "result-tab-selected border-accent text-accent"
RUN_TAB_CLASS = "run-tab border-b border-border px-2 py-2 text-[0.76rem] font-bold text-muted"
RUN_TAB_SELECTED_CLASS = "run-tab-selected border-accent text-accent"
RESULT_TAB_STYLE = {"backgroundColor": "#101a2b", "color": "#a7b7ce", "padding": "8px"}
RESULT_TAB_SELECTED_STYLE = {
    "backgroundColor": "#17243a",
    "color": "#38bdf8",
    "padding": "8px",
}
STEP_OUTPUT_CLASS = (
    "step-output m-0 max-h-[26rem] overflow-auto whitespace-pre-wrap rounded-[0.55rem] "
    "border border-border bg-[#0c1626] p-3 font-mono text-[0.76rem] leading-[1.5] text-muted "
    "[scrollbar-color:var(--color-border-strong)_transparent]"
)

STEP_TAB_LABELS = {
    PipelineStep.GENERATE: "Clauses",
    PipelineStep.LTLF: "LTLf",
    PipelineStep.DFA: "DFA",
    PipelineStep.REWARD_MACHINE: "Reward Machine",
    PipelineStep.STATE_DESCRIPTIONS: "State descriptions",
    PipelineStep.LABELING: "Labeling",
    PipelineStep.EMBEDDINGS: "Embeddings",
    PipelineStep.TASK_CRITIC: "Task critic",
    PipelineStep.RM_CRITIC: "RM critic",
}


def _step_tab(step: PipelineStep) -> dcc.Tab:
    """Build one label-only tab; the bodies live in their own container."""
    return dcc.Tab(
        label=STEP_TAB_LABELS[step],
        value=step.value,
        className=RESULT_TAB_CLASS,
        selected_className=RESULT_TAB_SELECTED_CLASS,
        style=RESULT_TAB_STYLE,
        selected_style=RESULT_TAB_SELECTED_STYLE,
    )


def _step_body(step: PipelineStep, body: str, *, visible: bool) -> html.Pre:
    """Build one step body, hidden but still measured when it is not selected."""
    return html.Pre(
        highlight_step(step, body),
        className=(f"{STEP_OUTPUT_CLASS} [grid-area:1/1]" + ("" if visible else " invisible")),
    )


def _step_bodies(bodies: Mapping[PipelineStep, str], visible: PipelineStep) -> list[html.Pre]:
    """Stack every step body in one grid cell so the panel keeps the tallest height.

    Only the selected body is painted; the others stay in the layout, which is what
    stops the panel from resizing when the reader switches tabs.
    """
    return [_step_body(step, body, visible=step is visible) for step, body in bodies.items()]


def result_tabs(step_outputs: Mapping[PipelineStep, object]) -> list[dcc.Tab]:
    """Build the label-only tabs of one output, in report order.

    Dash's Tabs resolves its own children from the client layout, so the bodies are
    rendered beside it by :func:`result_bodies` and stay fresh on every update.
    """
    return [_step_tab(step) for step in _output_steps(step_outputs)]


def result_bodies(
    step_outputs: Mapping[PipelineStep, object],
    selected: PipelineStep,
) -> list[html.Pre]:
    """Build the stacked bodies of every step, with the selected one painted."""
    bodies = {
        step: render_step_text(step, value) for step, value in _output_steps(step_outputs).items()
    }
    return _step_bodies(bodies, selected)


def _output_steps(
    step_outputs: Mapping[PipelineStep, object],
) -> dict[PipelineStep, object]:
    """Keep the captured steps in report order, defaulting to a placeholder body."""
    steps = {step: step_outputs[step] for step in STEP_OUTPUT_ORDER if step in step_outputs}
    return steps or {PipelineStep.REWARD_MACHINE: "No output selected."}


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


def _section_heading(
    icon_name: str, title: str, description: str, title_class: str = SECTION_TITLE_CLASS
) -> html.Div:
    """Build the icon, title and one-line description that open a panel."""
    return html.Div(
        [
            _section_icon(icon_name),
            html.Div(
                [
                    html.H2(title, className=title_class),
                    html.P(description, className=SECTION_DESCRIPTION_CLASS),
                ]
            ),
        ],
        className="section-heading flex items-start gap-[0.7rem]",
    )


def _field(label: str, *controls: object) -> html.Label:
    """Wrap controls under a small uppercase label."""
    return html.Label(
        [html.Span(label, className=FIELD_LABEL_CLASS), *controls],
        className=FIELD_CLASS,
    )


def _upload(component_id: str, prompt: str, accept: str) -> dcc.Upload:
    """Build one drop-or-choose upload control."""
    return dcc.Upload(
        id=component_id,
        children=html.Div(
            [_icon("upload", "upload-icon size-[1.05rem]"), html.Span(prompt)],
            className="upload-content flex items-center justify-center gap-2",
        ),
        accept=accept,
        multiple=False,
        disabled=False,
        className=UPLOAD_CONTROL_CLASS,
    )


def _legend_row(swatch_class: str, text: str) -> html.Li:
    """Build one graph legend entry: a swatch and its meaning."""
    return html.Li(
        [html.Span(className=swatch_class, **{"aria-hidden": "true"}), html.Span(text)],
        className=LEGEND_ROW_CLASS,
    )


def _section_icon(name: str, *, boxed: bool = True) -> html.Span:
    """Render a section icon.

    Boxed icons keep the shared panel treatment used next to section headings.
    Pass ``boxed=False`` for the bare icon when the container already draws its
    own border or background, such as the graph toolbar buttons.
    """
    if not boxed:
        return _icon(name, TOOLBAR_ICON_SIZE_CLASS)
    return html.Span(_icon(name, SECTION_ICON_SIZE_CLASS), className=SECTION_ICON_CLASS)


STEP_LABELS = {
    "generate": "Generate and validate interpretation",
    "task_critic": "Task interpretation critic",
    "ltlf": "Build LTLf from DECLARE templates",
    "dfa": "Compile DFA with FL-AT / MONA",
    "reward_machine": "Build Reward Machine",
    "state_descriptions": "Describe each Reward Machine state",
    "rm_critic": "Reward Machine critic",
    "labeling": "Generate MiniGrid labeling functions",
    "embeddings": "Embed each Reward Machine state description",
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
            selected_class = (
                " ring-2 ring-accent ring-offset-2 ring-offset-surface"
                if index == selected_index
                else ""
            )
            navigation.append(
                html.Button(
                    html.Span(
                        className=f"task-dot size-2.5 rounded-full {dot_class}{selected_class}",
                        **{"aria-hidden": "true"},
                    ),
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
                className=TASK_NAV_BUTTON_CLASS,
                **{"aria-label": "View previous task"},
            ),
            *navigation,
            html.Button(
                _icon("chevron-right", "size-4"),
                id="run-next",
                n_clicks=0,
                className=TASK_NAV_BUTTON_CLASS,
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
        children.append(
            html.Nav(
                navigation,
                className="run-task-navigation mt-1 flex items-center justify-center gap-1",
                **{"aria-label": "Task navigation"},
            )
        )
    return html.Div(children, className="run-steps-content flex min-h-40 flex-col gap-2")


# ======================================================================================
#                                    INPUT CONTROLS
# ======================================================================================


def environment_input() -> html.Section:
    """Build the upload and editable Markdown environment controls."""
    return html.Section(
        [
            _section_heading(
                "file-text", "Environment", "Upload UTF-8 Markdown or paste it below."
            ),
            _upload(
                "environment-upload",
                "Choose a Markdown file or drop it here",
                ".md,text/markdown,text/plain",
            ),
            html.Div(
                "No file uploaded; pasted content uses environment.md.",
                id="upload-status",
                className=FIELD_HINT_CLASS,
            ),
            _field(
                "Markdown",
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
                className=FIELD_CLASS,
            ),
        ],
        id={"type": "task-row", "index": index},
        className="task-row flex min-w-0 flex-col gap-[0.45rem]",
    )


def task_input() -> html.Section:
    """Build the dynamic task section."""
    return html.Section(
        [
            _section_heading(
                "list-todo",
                "Tasks",
                "Each task produces one independently compiled Reward Machine.",
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
            _section_heading(
                "wand-sparkles", "Generate", "Critics validate each task automatically."
            ),
            _field(
                "Base output filename",
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
                        options=CRITIC_OPTIONS,
                        value=["task_critic", "rm_critic"],
                        className="critic-options grid gap-[0.45rem] !text-text",
                    ),
                ],
                className=(
                    "critic-controls m-0 min-w-0 rounded-[0.55rem] border "
                    "border-border-strong bg-surface-raised px-3 pb-3 pt-[0.65rem] text-text"
                ),
            ),
            html.Fieldset(
                [
                    html.Legend(
                        "Outputs",
                        className=(
                            "outputs-legend px-[0.35rem] text-[0.7rem] font-[750] "
                            "uppercase tracking-[0.06em] text-muted"
                        ),
                    ),
                    dcc.Checklist(
                        id="steps-report-toggle",
                        options=STEPS_REPORT_OPTIONS,
                        value=["steps_report"],
                        className=OUTPUTS_OPTIONS_CLASS,
                    ),
                    dcc.Checklist(
                        id="labeling-toggle",
                        options=LABELING_OPTIONS,
                        value=[],
                        className=OUTPUTS_OPTIONS_CLASS,
                    ),
                    dcc.Checklist(
                        id="embeddings-toggle",
                        options=EMBEDDINGS_OPTIONS,
                        value=[],
                        className=OUTPUTS_OPTIONS_CLASS,
                    ),
                ],
                className=(
                    "outputs-controls m-0 min-w-0 rounded-[0.55rem] border "
                    "border-border-strong bg-surface-raised px-3 pb-3 pt-[0.65rem] text-text"
                ),
            ),
            html.Div(
                id="run-feedback",
                className=FIELD_HINT_CLASS,
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
                        className=RUN_TAB_CLASS,
                        selected_className=RUN_TAB_SELECTED_CLASS,
                        style=RESULT_TAB_STYLE,
                        selected_style=RESULT_TAB_SELECTED_STYLE,
                        children=html.Div(
                            [
                                "No run yet.",
                                html.Button(
                                    id="run-prev",
                                    n_clicks=0,
                                    className="hidden placeholder-button",
                                ),
                                html.Button(
                                    id="run-next",
                                    n_clicks=0,
                                    className="hidden placeholder-button",
                                ),
                                html.Button(
                                    id={"type": "task-dot", "index": 0},
                                    n_clicks=0,
                                    className="hidden placeholder-button",
                                ),
                            ],
                            id="run-steps",
                            className="steps-empty text-[0.8rem] text-muted",
                        ),
                    ),
                    dcc.Tab(
                        label="Log",
                        value="log",
                        className=RUN_TAB_CLASS,
                        selected_className=RUN_TAB_SELECTED_CLASS,
                        style=RESULT_TAB_STYLE,
                        selected_style=RESULT_TAB_SELECTED_STYLE,
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
            _section_heading(
                "file-code",
                "Compiled Reward Machine",
                "Import a processed Reward Machine or select a completed output.",
                title_class=PANEL_TITLE_CLASS,
            ),
            _field(
                "Import processed Reward Machine",
                _upload(
                    "reward-machine-upload",
                    "Choose an .rm or trace .json file",
                    ".rm,.json,text/plain",
                ),
            ),
            html.Div(
                "No imported Reward Machine.",
                id="reward-machine-upload-status",
                className=FIELD_HINT_CLASS,
            ),
            _field(
                "Completed output",
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
            ),
            html.Div(
                id="result-summary",
                className="result-summary text-[0.76rem] leading-[1.4] text-muted",
            ),
            _field(
                "Pipeline outputs",
                dcc.Tabs(
                    id="result-tabs",
                    value=PipelineStep.REWARD_MACHINE.value,
                    className="result-tabs flex-1",
                    content_style={"display": "none"},
                    children=[_step_tab(PipelineStep.REWARD_MACHINE)],
                ),
                html.Div(
                    id="result-bodies",
                    children=result_bodies(
                        {PipelineStep.REWARD_MACHINE: "No output selected."},
                        PipelineStep.REWARD_MACHINE,
                    ),
                    className="step-bodies grid min-w-0",
                ),
            ),
        ],
        className=(
            "output-panel flex min-h-0 min-w-0 flex-col gap-3 rounded-[0.85rem] "
            "border border-border bg-surface p-[0.95rem] max-[800px]:min-h-[30rem]"
        ),
    )


def graph_panel(stylesheet: list[dict] | None = None) -> html.Section:
    """Build the interactive Cytoscape graph panel."""
    return html.Section(
        [
            html.Div(
                [
                    html.Div(
                        [
                            _section_icon("network"),
                            html.H2(
                                "State graph",
                                className=PANEL_TITLE_CLASS,
                            ),
                        ],
                        className="panel-heading flex min-w-0 items-center gap-2 justify-self-start",
                    ),
                    html.Div(
                        [
                            html.Button(
                                [_section_icon("focus", boxed=False), "Focus graph"],
                                id="graph-focus-toggle",
                                n_clicks=0,
                                className=f"graph-focus-toggle {GRAPH_TOOLBAR_BUTTON_CLASS}",
                                **{"aria-label": "Focus graph", "aria-pressed": False},
                            ),
                            html.Button(
                                [_section_icon("download", boxed=False), "Export SVG"],
                                id="graph-export-button",
                                n_clicks=0,
                                disabled=True,
                                className=f"graph-export-button {GRAPH_TOOLBAR_BUTTON_CLASS}",
                                **{"aria-label": "Export the graph as an SVG file"},
                            ),
                        ],
                        className=(
                            "graph-toolbar-actions flex items-center gap-2 "
                            "justify-self-center max-[800px]:hidden"
                        ),
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
                                            _legend_row(
                                                (
                                                    "legend-swatch inline-block h-4 w-4 flex-none "
                                                    "rounded-[0.25rem] border-2 border-[#5878a8] "
                                                    "bg-[#18263d]"
                                                ),
                                                "Default state",
                                            ),
                                            _legend_row(
                                                (
                                                    "legend-swatch-initial legend-swatch inline-block h-4 w-4 "
                                                    "flex-none rounded-[0.25rem] border-[3px] border-accent "
                                                    "bg-[#18263d]"
                                                ),
                                                "Initial state",
                                            ),
                                            _legend_row(
                                                (
                                                    "legend-swatch-accepting legend-swatch inline-block h-4 w-4 "
                                                    "flex-none rounded-[0.25rem] border-2 border-success "
                                                    "bg-[#14532d]"
                                                ),
                                                "Accepting state",
                                            ),
                                            _legend_row(
                                                (
                                                    "legend-swatch-rejecting legend-swatch inline-block h-4 w-4 "
                                                    "flex-none rounded-[0.25rem] border-2 border-[#fb7185] "
                                                    "bg-[#572033]"
                                                ),
                                                "Rejecting state",
                                            ),
                                            _legend_row(
                                                (
                                                    "legend-swatch-transition legend-swatch inline-block h-0 "
                                                    "w-4 flex-none rounded-none border-0 border-t-2 "
                                                    "border-[#7189ad] bg-transparent"
                                                ),
                                                "Explicit transition",
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
                            "name": "preset",
                            "fit": True,
                            "padding": 60,
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
            dcc.Store(
                id="task-selection",
                data={"selected": 0, "last_active": None, "run_id": 0},
            ),
            dcc.Store(id="imported-reward-machine", data=None),
            dcc.Store(id="graph-transition-pin", data=None),
            dcc.Store(id="graph-focus-state", data=False),
            dcc.Store(id="graph-export-name", data=None),
            dcc.Store(id="graph-export-payload", data=None),
            dcc.Download(id="graph-download"),
        ],
        className=(
            "app-shell flex min-h-dvh w-full flex-col gap-4 "
            "px-[clamp(1rem,2.5vw,2.5rem)] pb-6 pt-5 "
            "max-[560px]:gap-3 max-[560px]:px-[0.8rem] "
            "max-[560px]:pb-5 max-[560px]:pt-[0.9rem]"
        ),
    )
