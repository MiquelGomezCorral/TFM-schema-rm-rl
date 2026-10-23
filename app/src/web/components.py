"""Reusable Dash layout factories for the local Reward Machine UI."""

from collections.abc import Mapping

import dash_cytoscape as cyto
from dash import dcc, html

from src.config import REASONING_LEVELS, Configuration
from src.utils import STEP_OUTPUT_ORDER, PipelineStep, render_step_text

from .highlight import highlight_step
from .runner import StepState, TaskSnapshot

# ======================================================================================
#                                     STATUS STYLES
# ======================================================================================

# The poll callback replaces the pill's text, so its state mark rides in ::before and every
# word carries the mask of its own step icon instead of an inline svg.
STATUS_BASE = (
    "status inline-flex min-h-[22px] shrink-0 items-center gap-1.5 rounded-sm border "
    "px-2 text-sm font-medium before:inline-block before:size-3.5 before:shrink-0 "
    "before:bg-current before:content-['']"
)
STATUS_MASK_PENDING = (
    "before:[mask:url('/assets/icons/step-pending.svg')_center/contain_no-repeat] "
    "before:[-webkit-mask:url('/assets/icons/step-pending.svg')_center/contain_no-repeat]"
)
STATUS_MASK_RUNNING = (
    "before:[mask:url('/assets/icons/step-running.svg')_center/contain_no-repeat] "
    "before:[-webkit-mask:url('/assets/icons/step-running.svg')_center/contain_no-repeat]"
)
STATUS_MASK_DONE = (
    "before:[mask:url('/assets/icons/step-done.svg')_center/contain_no-repeat] "
    "before:[-webkit-mask:url('/assets/icons/step-done.svg')_center/contain_no-repeat]"
)
STATUS_MASK_FAILED = (
    "before:[mask:url('/assets/icons/step-failed.svg')_center/contain_no-repeat] "
    "before:[-webkit-mask:url('/assets/icons/step-failed.svg')_center/contain_no-repeat]"
)
STATUS_MASK_SKIPPED = (
    "before:[mask:url('/assets/icons/step-skipped.svg')_center/contain_no-repeat] "
    "before:[-webkit-mask:url('/assets/icons/step-skipped.svg')_center/contain_no-repeat]"
)
STATUS_CLASSES = {
    "idle": f"{STATUS_BASE} border-border-strong text-muted {STATUS_MASK_PENDING}",
    "running": f"{STATUS_BASE} border-border-strong bg-accent-tint text-info-ink {STATUS_MASK_RUNNING}",
    "completed": f"{STATUS_BASE} border-success bg-success-tint text-success-ink {STATUS_MASK_DONE}",
    "failed": f"{STATUS_BASE} border-danger bg-danger-tint text-danger-ink {STATUS_MASK_FAILED}",
    # A stop is a neutral outcome, not a failure, so it never borrows the danger colour.
    "stopped": f"{STATUS_BASE} border-border bg-raised text-muted {STATUS_MASK_SKIPPED}",
}
# The pill keeps one word, so the failure reason lives in this hover/focus popover.
# The wide layout keeps it left-anchored; the single-column sidebar puts the pill on the right,
# so there it anchors right and a wider inset keeps both edges inside the viewport.
STATUS_REASON_CLASS = (
    "status-reason hidden group-hover:block group-focus-within:block absolute left-0 top-full "
    "z-20 mt-1 w-[min(32rem,calc(100vw-2rem))] max-h-64 overflow-auto rounded-sm "
    "border border-border-strong bg-surface p-3 text-xs leading-[1.5] text-text "
    "whitespace-pre-wrap wrap-anywhere shadow-none [scrollbar-gutter:stable] "
    "[scrollbar-width:thin] empty:hidden "
    "max-[900px]:left-auto max-[900px]:right-0 max-[900px]:w-[min(32rem,calc(100vw-3.5rem))]"
)
# The task title's popover lives inside the tab panel, which clips overflow, so it spans the
# panel instead of the status popover's fixed width.
TASK_TITLE_POPOVER_CLASS = (
    STATUS_REASON_CLASS.replace("w-[min(32rem,calc(100vw-2rem))]", "w-full")
    .replace("max-[900px]:w-[min(32rem,calc(100vw-3.5rem))]", "")
    .replace("max-[900px]:left-auto max-[900px]:right-0", "")
)

INPUT_REGION_CLASS = (
    "input-region grid items-stretch gap-3 [grid-area:input] grid-cols-2 max-[1200px]:grid-cols-1"
)
RUN_SIDEBAR_CLASS = (
    "run-sidebar control-card self-stretch [grid-area:sidebar] "
    "flex min-w-0 flex-col gap-3 rounded-sm border border-border "
    "bg-surface p-3.5"
)
# The output row is the page leftover, but the panels must never cross their card borders when
# that leftover is short: 38rem is the Compiled Reward Machine panel's own minimum (fixed
# controls, the summary rows, and the 12rem code floor).
# The output row never drops below a readable height: on short viewports the page scrolls
# instead of squeezing the Reward Machine text and the graph.
OUTPUT_REGION_CLASS = (
    "output-region grid min-h-[36rem] items-stretch gap-3 [grid-area:output] grid-cols-2 "
    "max-[1200px]:grid-cols-1 max-[1200px]:min-h-0"
)
# Two rows: the input cards take what their content needs, the output row fills the rest, so
# the four cards end at the bottom of the viewport instead of leaving a blank band. Below the
# desktop breakpoint both rows keep their natural height and the page scrolls.
WORKSPACE_CLASS = (
    "workspace grid flex-1 items-stretch gap-3 "
    "[grid-template-rows:auto_1fr] "
    "[grid-template-areas:'sidebar_input'_'sidebar_output'] "
    "[grid-template-columns:19rem_minmax(0,1fr)] "
    "max-[1200px]:[grid-template-rows:auto_auto] "
    "max-[900px]:grid-cols-1 "
    "max-[900px]:[grid-template-areas:'input'_'sidebar'_'output']"
)
FOCUS_WORKSPACE_CLASS = (
    "workspace grid flex-1 items-stretch gap-3 "
    "[grid-template-rows:1fr] "
    "[grid-template-areas:'output'] [grid-template-columns:minmax(0,1fr)] "
    "max-[1200px]:[grid-template-rows:auto]"
)
FOCUS_OUTPUT_REGION_CLASS = (
    "output-region grid min-h-0 items-stretch gap-3 [grid-area:output] "
    "min-[1200px]:min-h-[38rem] "
    "[grid-template-columns:19rem_minmax(0,1fr)] max-[800px]:min-h-0"
)
TOOLBAR_ICON_SIZE_CLASS = "size-[0.9rem]"
# One shape for the Generate slot: the two states of the same control differ only in colour.
PRIMARY_ACTION_CLASS = (
    "button button-primary inline-flex min-h-9 cursor-pointer items-center justify-center "
    "gap-2 rounded-sm border px-[0.85rem] text-base font-normal transition duration-150 "
    "ease-out focus-visible:outline-2 focus-visible:outline-offset-2 "
    "disabled:cursor-not-allowed disabled:opacity-60"
)
GENERATE_BUTTON_CLASS = (
    f"generate-button {PRIMARY_ACTION_CLASS} border-accent bg-accent text-page "
    "enabled:hover:border-accent enabled:hover:brightness-110 "
    "focus-visible:outline-accent"
)
# A standalone stop is always visible, labelled and outlined in red; its confirmation is the modal.
STOP_BUTTON_CLASS = (
    f"stop-run-button {PRIMARY_ACTION_CLASS} border-danger bg-transparent text-danger "
    "enabled:hover:border-danger enabled:hover:bg-danger-tint "
    "focus-visible:outline-danger"
)
GRAPH_TOOLBAR_BUTTON_CLASS = (
    "inline-flex min-h-[26px] shrink-0 cursor-pointer items-center justify-center gap-1.5 "
    "rounded-sm border border-border bg-page px-2 text-xs font-medium whitespace-nowrap "
    "text-muted transition duration-150 ease-out hover:border-border-strong hover:text-text "
    "focus-visible:outline-3 focus-visible:outline-offset-2 "
    "focus-visible:outline-accent/35 disabled:cursor-not-allowed disabled:opacity-60 "
    "disabled:hover:border-border disabled:hover:text-muted"
)


FIELD_CLASS = "field flex min-w-0 flex-col gap-[0.35rem]"
FIELD_LABEL_CLASS = "field-label text-sm font-medium text-muted"
FIELD_LABEL_MUTED_CLASS = "field-label text-sm font-normal text-muted tracking-[0.32px]"
FIELD_HINT_CLASS = "field-hint text-xs text-muted"
FIELD_TEXTAREA_CLASS = (
    "block w-full resize-y !rounded-sm border !border-border !bg-page !px-2.5 !py-2 "
    "text-base !text-text outline-0 transition duration-150 ease-out "
    "placeholder:!text-muted focus-visible:!border-accent focus-visible:!outline-2 "
    "focus-visible:outline-offset-2 focus-visible:!outline-accent/35 "
    "enabled:hover:!border-border-strong disabled:!cursor-not-allowed "
    "disabled:!border-border disabled:!bg-surface disabled:!text-muted disabled:!opacity-60"
)
SECTION_TITLE_CLASS = "section-title text-md font-semibold"
PANEL_TITLE_CLASS = "panel-title text-lg font-semibold tracking-[-0.015em]"
SECTION_DESCRIPTION_CLASS = "section-description mt-[0.18rem] text-sm text-muted"
UPLOAD_CONTROL_CLASS = (
    "upload-control grid min-h-8 cursor-pointer place-items-center rounded-sm "
    "border border-border bg-page p-2 text-center text-muted "
    "transition duration-150 ease-out hover:border-border-strong "
    "has-[:disabled]:cursor-not-allowed has-[:disabled]:border-border "
    "has-[:disabled]:bg-surface has-[:disabled]:opacity-60 "
    "has-[:disabled]:hover:border-border "
    "has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 "
    "has-[:focus-visible]:outline-accent/35"
)
UPLOAD_TEXT_CLASS = "text-base"
COMPACT_UPLOAD_TEXT_CLASS = "text-sm"
CHECKLIST_CLASS = "grid gap-[0.45rem] !text-text [&>label]:min-h-6 [&>label]:text-base"
OUTPUTS_OPTIONS_CLASS = f"outputs-options {CHECKLIST_CLASS}"
LEGEND_ROW_CLASS = "legend-row flex items-center gap-2 text-xs text-muted"
TASK_NAV_BUTTON_CLASS = (
    "task-nav-button grid size-6 place-items-center rounded-sm border border-border-strong "
    "text-muted transition duration-150 ease-out hover:border-accent hover:text-accent "
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent "
    "disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:border-border-strong "
    "disabled:hover:text-muted"
)
SEGMENTED_TRACK_CLASS = (
    "segmented grid grid-cols-5 gap-0 rounded-sm border border-border-strong bg-transparent p-0"
)
SEGMENT_BASE = (
    "segment min-h-8 cursor-pointer rounded-none border-0 px-0 text-sm font-normal capitalize "
    "transition duration-150 ease-out focus-visible:outline-2 focus-visible:outline-offset-2 "
    "focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-60 "
    "[&:not(:first-child)]:border-l [&:not(:first-child)]:border-border"
)
SEGMENT_SELECTED = " bg-hover text-text shadow-[inset_0_-2px_0_var(--color-accent)]"
SEGMENT_IDLE = " bg-transparent text-muted hover:bg-hover hover:text-text"

TEXT_INPUT_CLASS = (
    "text-input w-full !h-auto !rounded-none !border-0 !border-b !border-border-strong "
    "!bg-raised px-2 py-1.5 text-base text-text outline-0 transition duration-150 ease-out "
    "hover:!bg-hover hover:[&>input]:!bg-hover "
    "has-[:disabled]:cursor-not-allowed has-[:disabled]:!border-border "
    "has-[:disabled]:!bg-surface has-[:disabled]:!opacity-60 "
    "has-[:focus-visible]:!outline-2 has-[:focus-visible]:!outline-accent "
    "has-[:focus-visible]:!outline-offset-0 "
    "[&>input]:!p-0 [&>input]:w-full [&>input]:text-base [&>input]:text-text "
    "[&>input]:outline-0 [&>input]:placeholder:text-muted "
    "[&>input]:disabled:!text-muted"
)
FIELDSET_CLASS = (
    "m-0 min-w-0 rounded-none border-0 border-t border-border bg-transparent "
    "px-0 pb-0 pt-3 text-text"
)
FIELD_BODY_CLASS = "clear-both flex flex-col gap-2"
FIELD_LEGEND_CLASS = "float-left mb-2 w-full px-0 text-sm font-normal text-muted"
STEPPER_CLASS = (
    "stepper flex min-h-9 w-full items-stretch overflow-hidden rounded-sm "
    "border border-border-strong bg-raised transition duration-150 ease-out "
    "hover:border-accent has-[:disabled]:cursor-not-allowed "
    "has-[:disabled]:border-border has-[:disabled]:opacity-60 "
    "has-[:disabled]:hover:border-border focus-within:outline-3 "
    "focus-within:outline-offset-2 focus-within:outline-accent/35"
)
STEPPER_BUTTON_CLASS = (
    "stepper-button grid w-9 shrink-0 cursor-pointer place-items-center border-0 "
    "bg-transparent text-text transition duration-150 ease-out enabled:hover:bg-hover "
    "enabled:hover:text-accent focus-visible:outline-2 focus-visible:-outline-offset-2 "
    "focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-60"
)
STEPPER_INPUT_CLASS = (
    "stepper-input min-w-0 flex-1 !h-auto !border-0 !bg-transparent text-center !text-text "
    "[&>input]:font-sans [&>input]:text-base [&>input]:outline-0 [&>input]:text-center "
    "[&>input]:tabular-nums [&>input]:[appearance:textfield] "
    "[&>input::-webkit-inner-spin-button]:!appearance-none "
    "[&>input::-webkit-outer-spin-button]:!appearance-none "
    "[&>.dash-input-stepper]:!hidden"
)
ISSUE_LIST_CLASS = (
    "issue-list m-0 grid list-none gap-1.5 overflow-auto p-0 text-sm leading-[1.4] text-text "
    "[scrollbar-color:var(--color-border-strong)_transparent] [scrollbar-width:thin]"
)
ISSUE_ITEM_CLASSES = {
    "warning": "border-warning bg-warning-tint",
    "error": "border-danger bg-danger-tint",
}

CRITIC_OPTIONS = [{"label": " Critic", "value": "critic"}]
STEPS_REPORT_OPTIONS = [{"label": " Step report (.md)", "value": "steps_report"}]
LABELING_OPTIONS = [{"label": " MiniGrid labeling", "value": "labeling"}]
STATE_DESCRIPTIONS_OPTIONS = [{"label": " State descriptions", "value": "state_descriptions"}]
EMBEDDINGS_OPTIONS = [{"label": " Local state embeddings", "value": "embeddings"}]

RUN_TAB_CLASS = (
    "run-tab !flex-none !border-x-0 !border-t-0 !px-2.5 !py-1.5 text-sm font-medium text-muted"
)
RUN_TAB_SELECTED_CLASS = "run-tab-selected !border-b-2 !border-accent !text-text font-semibold"
RUN_TAB_WARNING_SELECTED_CLASS = (
    "run-tab-selected !border-b-2 !border-warning !text-warning-ink font-semibold"
)
RUN_TAB_ERROR_SELECTED_CLASS = (
    "run-tab-selected !border-b-2 !border-danger !text-danger-ink font-semibold"
)
RUN_TAB_DISABLED_CLASS = "run-tab-disabled cursor-not-allowed opacity-50"
RUN_TAB_STYLE = {"backgroundColor": "transparent"}
RUN_TAB_SELECTED_STYLE = {"backgroundColor": "transparent"}
STEP_OUTPUT_CLASS = (
    "step-output m-0 h-full overflow-y-auto overflow-x-hidden whitespace-pre-wrap "
    "rounded-sm border border-border bg-page p-3 font-mono text-xs leading-[1.7] text-muted "
    "[scrollbar-color:var(--color-border-strong)_transparent] [scrollbar-gutter:stable] "
    "[scrollbar-width:thin]"
)

STEP_TAB_LABELS = {
    PipelineStep.GENERATE: "Clauses",
    PipelineStep.LTLF: "LTLf",
    PipelineStep.DFA: "DFA",
    PipelineStep.REWARD_MACHINE: "Reward Machine",
    PipelineStep.STATE_DESCRIPTIONS: "State descriptions",
    PipelineStep.LABELING: "Labeling",
    PipelineStep.EMBEDDINGS: "Embeddings",
    PipelineStep.CRITIC: "Critic",
}


def _step_tab(step: PipelineStep) -> dcc.Tab:
    """Build one label-only tab; the bodies live in their own container.

    Result and run tabs share one underline treatment, so they share its constants.
    """
    return dcc.Tab(
        label=STEP_TAB_LABELS[step],
        value=step.value,
        className=RUN_TAB_CLASS,
        selected_className=RUN_TAB_SELECTED_CLASS,
        style=RUN_TAB_STYLE,
        selected_style=RUN_TAB_SELECTED_STYLE,
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
        className="section-heading flex items-start gap-2.5",
    )


def _field(
    label: str,
    *controls: object,
    label_class: str = FIELD_LABEL_CLASS,
    class_name: str = FIELD_CLASS,
) -> html.Label:
    """Wrap controls under a small label."""
    return html.Label(
        [html.Span(label, className=label_class), *controls],
        className=class_name,
    )


def _upload(
    component_id: str,
    prompt: str,
    accept: str,
    text_class: str = UPLOAD_TEXT_CLASS,
) -> dcc.Upload:
    """Build one drop-or-choose upload control at the call site's type size."""
    return dcc.Upload(
        id=component_id,
        children=html.Div(
            [
                _icon("upload", "upload-icon size-4 text-accent"),
                html.Span(prompt, className="font-medium text-text"),
            ],
            className="upload-content flex items-center justify-center gap-2",
        ),
        accept=accept,
        multiple=False,
        disabled=False,
        className=f"{UPLOAD_CONTROL_CLASS} {text_class}",
    )


def _legend_row(swatch_class: str, text: str) -> html.Li:
    """Build one graph legend entry: a swatch and its meaning."""
    return html.Li(
        [html.Span(className=swatch_class, **{"aria-hidden": "true"}), html.Span(text)],
        className=LEGEND_ROW_CLASS,
    )


def _section_icon(name: str) -> html.Span:
    """Render the bare section icon shared by every panel heading."""
    return _icon(name, "size-5 text-muted")


STEP_LABELS = {
    "generate": "Generate and validate interpretation",
    "ltlf": "Build LTLf from DECLARE templates",
    "dfa": "Compile DFA with FL-AT / MONA",
    "reward_machine": "Build Reward Machine",
    "critic": "Critic review of clauses and Reward Machine",
    "state_descriptions": "Describe each Reward Machine state",
    "labeling": "Generate MiniGrid labeling functions",
    "embeddings": "Embed each Reward Machine state description",
}
STEP_MARK_CLASSES = {
    StepState.PENDING: "text-muted",
    StepState.RUNNING: "text-accent",
    StepState.COMPLETED: "text-success-ink",
    StepState.SKIPPED: "text-muted",
    StepState.FAILED: "text-danger-ink",
}
STEP_MARK_ICONS = {
    StepState.PENDING: "step-pending",
    StepState.RUNNING: "step-running",
    StepState.COMPLETED: "step-done",
    StepState.SKIPPED: "step-skipped",
    StepState.FAILED: "step-failed",
}


def _task_status(task: TaskSnapshot) -> str:
    limit = task.attempts
    if task.state is StepState.RUNNING:
        return f"Task {task.index + 1} of {{total}} · Attempt {task.attempt} of {limit}"
    if task.state is StepState.COMPLETED:
        return f"Task {task.index + 1} of {{total}} · Accepted on attempt {task.attempt} of {limit}"
    if task.state is StepState.FAILED:
        return f"Task {task.index + 1} of {{total}} · Failed on attempt {task.attempt} of {limit}"
    return f"Task {task.index + 1} of {{total}} · Not started"


def _step_row(step) -> html.Div:
    status = step.state
    duration = f" · {step.elapsed:.3f}s" if step.elapsed is not None else ""
    return html.Div(
        [
            html.Span(
                _icon(STEP_MARK_ICONS[status], f"size-4 {STEP_MARK_CLASSES[status]}"),
                className="step-mark grid size-4 flex-none place-items-center",
                **{"aria-hidden": "true"},
            ),
            html.Span(
                STEP_LABELS[step.step.value],
                className="step-label min-w-0 flex-1 text-sm font-medium text-text",
            ),
            html.Span(
                f"{status.value.capitalize()}{duration}",
                className="step-state font-mono text-xs text-muted",
            ),
        ],
        className=(
            "run-step flex min-h-[30px] items-center gap-2 rounded-sm border border-border "
            "bg-page px-1.5 py-[3px]"
        ),
    )


def render_steps(tasks: tuple[TaskSnapshot, ...], selected_index: int = 0) -> html.Div:
    """Render the selected task's structured progress and compact navigator."""
    if not tasks:
        return html.Div("No run yet.", className="steps-empty min-h-40 text-sm text-muted")
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
                StepState.FAILED: "bg-danger",
            }.get(state, "bg-border-strong")
            selected_class = (
                " border-accent bg-accent-tint"
                if index == selected_index
                else " border-transparent"
            )
            dot_size = "size-2" if index == selected_index else "size-1.5"
            navigation.append(
                html.Button(
                    html.Span(
                        className=f"task-dot {dot_size} rounded-full {dot_class}",
                        **{"aria-hidden": "true"},
                    ),
                    id={"type": "task-dot", "index": index},
                    n_clicks=0,
                    className=(
                        "task-dot-button grid size-6 place-items-center rounded-sm border"
                        f"{selected_class} transition duration-150 ease-out "
                        "hover:border-border-strong focus-visible:border-accent "
                        "focus-visible:outline-2 focus-visible:outline-offset-2 "
                        "focus-visible:outline-accent"
                    ),
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
                disabled=selected_index == 0,
                className=TASK_NAV_BUTTON_CLASS,
                **{"aria-label": "View previous task"},
            ),
            *navigation,
            html.Button(
                _icon("chevron-right", "size-4"),
                id="run-next",
                n_clicks=0,
                disabled=selected_index == len(tasks) - 1,
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
                                    className=(
                                        "run-task-title min-w-0 truncate text-sm font-semibold "
                                        "leading-[1.35] text-text"
                                    ),
                                    tabIndex="0",
                                ),
                                # The full text; the title above keeps one line.
                                html.Div(task.task, className=TASK_TITLE_POPOVER_CLASS),
                            ],
                            className="run-task-title-row group relative min-w-0",
                        ),
                        html.P(
                            status,
                            className="run-task-status mt-1 font-mono text-xs text-muted",
                        ),
                    ],
                    className="run-task-heading min-w-0 w-full",
                ),
            ],
            className="run-task-header min-w-0 pt-3",
        ),
        html.Div(
            [_step_row(step) for step in task.steps],
            className="run-steps-list grid gap-2",
        ),
    ]
    if navigation:
        children.append(
            html.Nav(
                navigation,
                className="run-task-navigation mt-1 flex items-center justify-center gap-1",
                **{"aria-label": "Task navigation"},
            )
        )
    return html.Div(children, className="run-steps-content flex min-h-40 flex-col gap-2")


def render_issues(entries: tuple[str, ...] | list[str], kind: str) -> object:
    """Render one Warnings or Errors tab body: a tinted list, or a short empty note."""
    if not entries:
        return html.P(f"No {kind}s.", className="issues-empty m-0 text-sm text-muted")
    return html.Ul(
        [
            html.Li(
                entry,
                className=(
                    f"issue-item rounded-sm border-l-2 px-2 py-1.5 {ISSUE_ITEM_CLASSES[kind]}"
                ),
            )
            for entry in entries
        ],
        className=ISSUE_LIST_CLASS,
    )


# ======================================================================================
#                                    INPUT CONTROLS
# ======================================================================================


def environment_input() -> html.Section:
    """Build the upload and editable Markdown environment controls."""
    return html.Section(
        [
            _section_heading(
                "file-text",
                "Environment",
                "Upload UTF-8 Markdown, a tasks.json manifest, or paste it below.",
            ),
            _upload(
                "environment-upload",
                "Choose a Markdown or tasks.json file or drop it here",
                ".md,.json,text/markdown,text/plain,application/json",
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
                        "markdown-input flex-1 min-h-[11rem] !resize-none "
                        f"max-[1200px]:!resize-y {FIELD_TEXTAREA_CLASS}"
                    ),
                    spellCheck=True,
                    disabled=False,
                ),
                class_name=f"{FIELD_CLASS} flex-1 min-h-0",
            ),
            _upload(
                "environment-code-upload",
                "Optional: choose environment-code.md or drop it here",
                ".md,text/markdown,text/plain",
            ),
            html.Div(
                "Labeling reads this code file; the generator and critic never do.",
                id="code-upload-status",
                className=FIELD_HINT_CLASS,
            ),
            _field(
                "Code file",
                dcc.Textarea(
                    id="environment-code-markdown",
                    value="",
                    placeholder="# Environment: code notes\n\n## Labeling API",
                    className=f"markdown-input min-h-[4rem] {FIELD_TEXTAREA_CLASS}",
                    spellCheck=False,
                    disabled=False,
                ),
            ),
        ],
        className=(
            "environment-card control-card flex min-w-0 flex-col gap-3 rounded-sm "
            "border border-border bg-surface p-4"
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
                        className="task-title min-w-0 text-sm font-normal text-muted",
                    ),
                    html.Button(
                        _icon("trash", "remove-task-icon size-3.5"),
                        id={"type": "remove-task", "index": index},
                        n_clicks=0,
                        disabled=index == 0,
                        title="The first task can't be removed" if index == 0 else None,
                        className=(
                            "remove-task button button-quiet ml-auto grid size-7 shrink-0 "
                            "cursor-pointer place-items-center rounded-sm border "
                            "border-border-strong bg-transparent p-0 text-muted transition "
                            "duration-150 ease-out enabled:hover:border-danger "
                            "enabled:hover:text-danger focus-visible:outline-2 "
                            "focus-visible:outline-offset-2 focus-visible:outline-danger "
                            "disabled:cursor-not-allowed disabled:opacity-60"
                        ),
                        **{"aria-label": f"Remove task {index + 1}"},
                    ),
                ],
                className="task-header flex min-h-5 min-w-0 flex-nowrap items-center gap-2",
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
                        className=f"task-input min-h-[4rem] {FIELD_TEXTAREA_CLASS}",
                        rows=2,
                        disabled=False,
                    ),
                ],
                className=FIELD_CLASS,
            ),
        ],
        id={"type": "task-row", "index": index},
        className=(
            "task-row flex min-w-0 flex-col gap-1.5 rounded-none border-l-2 "
            "border-border-strong pl-2.5"
        ),
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
                className="task-rows flex min-w-0 flex-1 flex-col gap-3",
            ),
            html.Button(
                [_icon("plus", "add-task-icon size-4"), html.Span("Add task")],
                id="add-task",
                n_clicks=0,
                className=(
                    "add-task button button-secondary inline-flex min-h-9 w-full cursor-pointer "
                    "items-center justify-start gap-2 rounded-sm border border-border-strong "
                    "bg-transparent px-[0.85rem] py-[0.62rem] text-base font-normal text-text "
                    "transition duration-150 ease-out enabled:hover:bg-hover "
                    "focus-visible:outline-2 focus-visible:outline-offset-2 "
                    "focus-visible:outline-accent/35 disabled:cursor-not-allowed "
                    "disabled:opacity-60"
                ),
            ),
        ],
        className=(
            "tasks-card control-card flex min-w-0 flex-col gap-3 rounded-sm "
            "border border-border bg-surface p-4"
        ),
    )


# ======================================================================================
#                                   OUTPUT CONTROLS
# ======================================================================================


def segment_class(selected: bool) -> str:
    """Return the tracked-cell style of a selected or an idle reasoning level."""
    return SEGMENT_BASE + (SEGMENT_SELECTED if selected else SEGMENT_IDLE)


def reasoning_option(level: str, selected: bool) -> html.Button:
    """Build one mutually exclusive segment of the reasoning control."""
    return html.Button(
        level,
        id={"type": "reasoning-option", "index": level},
        n_clicks=0,
        role="radio",
        className=segment_class(selected),
        **{"aria-checked": selected},
    )


def output_controls() -> html.Aside:
    """Build output filename, critic controls, and run status."""
    return html.Aside(
        [
            html.Div(
                [
                    _section_icon("wand-sparkles"),
                    html.Div(
                        [
                            html.H2("Generate", className="section-title text-lg font-semibold"),
                            html.P(
                                "The critic validates each task automatically.",
                                className="section-description mt-1 text-sm text-muted",
                            ),
                        ]
                    ),
                ],
                className="section-heading flex items-start gap-3",
            ),
            _field(
                "Base output filename",
                dcc.Input(
                    id="output-filename",
                    type="text",
                    value="reward-machine.rm",
                    placeholder="reward-machine.rm",
                    className=TEXT_INPUT_CLASS,
                    disabled=False,
                ),
                label_class=FIELD_LABEL_MUTED_CLASS,
            ),
            html.Button(
                [
                    _icon("play", "generate-button-icon size-4"),
                    html.Span("Generate Reward Machines"),
                ],
                id="generate-button",
                n_clicks=0,
                className=GENERATE_BUTTON_CLASS,
            ),
            dcc.ConfirmDialogProvider(
                id="stop-run",
                message=(
                    "Stop the running generation? The current task is discarded; "
                    "finished tasks are kept in the log only."
                ),
                children=html.Button(
                    [_icon("square", "stop-run-icon size-4"), html.Span("Stop generation")],
                    id="stop-run-button",
                    n_clicks=0,
                    className=f"{STOP_BUTTON_CLASS} !hidden",
                ),
            ),
            html.Fieldset(
                [
                    html.Legend(
                        "Automatic critic",
                        className=f"critic-legend {FIELD_LEGEND_CLASS}",
                    ),
                    html.Div(
                        [
                            dcc.Checklist(
                                id="critic-options",
                                options=CRITIC_OPTIONS,
                                value=["critic"],
                                className=f"critic-options {CHECKLIST_CLASS}",
                            ),
                            _field(
                                "Critic rejections allowed",
                                html.Div(
                                    [
                                        html.Button(
                                            _icon("minus", "size-4"),
                                            id="attempts-decrement",
                                            n_clicks=0,
                                            className=(
                                                f"{STEPPER_BUTTON_CLASS} border-r border-border-strong"
                                            ),
                                            title="Allow one fewer rejection",
                                            **{"aria-label": "Allow one fewer rejection"},
                                        ),
                                        dcc.Input(
                                            id="attempts",
                                            type="number",
                                            min=Configuration.ATTEMPT_LIMITS.start,
                                            max=Configuration.ATTEMPT_LIMITS.stop - 1,
                                            step=1,
                                            value=Configuration.attempts,
                                            inputMode="numeric",
                                            debounce=False,
                                            className=STEPPER_INPUT_CLASS,
                                            disabled=False,
                                        ),
                                        html.Button(
                                            _icon("plus", "size-4"),
                                            id="attempts-increment",
                                            n_clicks=0,
                                            className=(
                                                f"{STEPPER_BUTTON_CLASS} border-l border-border-strong"
                                            ),
                                            title="Allow one more rejection",
                                            **{"aria-label": "Allow one more rejection"},
                                        ),
                                    ],
                                    className=STEPPER_CLASS,
                                    role="group",
                                    **{"aria-label": "Critic rejections allowed"},
                                ),
                                label_class=FIELD_LABEL_MUTED_CLASS,
                            ),
                        ],
                        className=FIELD_BODY_CLASS,
                    ),
                ],
                className=f"critic-controls {FIELDSET_CLASS}",
            ),
            html.Fieldset(
                [
                    html.Legend(
                        "Reasoning",
                        className=f"reasoning-legend {FIELD_LEGEND_CLASS}",
                    ),
                    html.Div(
                        [
                            dcc.Store(id="reasoning-level", data=Configuration.reasoning),
                            html.Div(
                                [
                                    reasoning_option(
                                        level, selected=level == Configuration.reasoning
                                    )
                                    for level in REASONING_LEVELS
                                ],
                                id="reasoning-options",
                                role="radiogroup",
                                className=SEGMENTED_TRACK_CLASS,
                                **{"aria-label": "Reasoning level"},
                            ),
                            html.Span(
                                [
                                    "Shared by the generator and the critic; ",
                                    html.Span("none", className="font-medium text-text"),
                                    " is fastest, ",
                                    html.Span("max", className="font-medium text-text"),
                                    " thinks longest",
                                ],
                                className=f"{FIELD_HINT_CLASS} mt-2",
                            ),
                        ],
                        className=FIELD_BODY_CLASS,
                    ),
                ],
                className=f"reasoning-controls {FIELDSET_CLASS}",
            ),
            html.Fieldset(
                [
                    html.Legend(
                        "Outputs",
                        className=f"outputs-legend {FIELD_LEGEND_CLASS}",
                    ),
                    html.Div(
                        [
                            dcc.Checklist(
                                id="steps-report-toggle",
                                options=STEPS_REPORT_OPTIONS,
                                value=["steps_report"],
                                className=OUTPUTS_OPTIONS_CLASS,
                            ),
                            dcc.Checklist(
                                id="descriptions-toggle",
                                options=STATE_DESCRIPTIONS_OPTIONS,
                                value=["state_descriptions"],
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
                        className=FIELD_BODY_CLASS,
                    ),
                ],
                className=f"outputs-controls {FIELDSET_CLASS}",
            ),
            html.Div(
                id="run-feedback",
                className=FIELD_HINT_CLASS,
            ),
            html.Div(
                [
                    html.H2(
                        "Run status",
                        className="status-title text-md font-semibold",
                    ),
                    html.Div(
                        [
                            html.Div(
                                "Idle",
                                id="run-status",
                                className=f"{STATUS_CLASSES['idle']} max-w-full truncate",
                                role="status",
                                tabIndex="0",
                                **{"aria-live": "polite"},
                            ),
                            html.Div(id="run-status-reason", className=STATUS_REASON_CLASS),
                        ],
                        className="status-wrap group relative min-w-0",
                    ),
                ],
                className="status-heading flex flex-wrap items-center justify-between gap-3",
            ),
            dcc.Tabs(
                id="run-tabs",
                value="steps",
                className="run-tabs flex-1 border-b border-border",
                children=[
                    dcc.Tab(
                        label="Steps",
                        value="steps",
                        className=RUN_TAB_CLASS,
                        selected_className=RUN_TAB_SELECTED_CLASS,
                        style=RUN_TAB_STYLE,
                        selected_style=RUN_TAB_SELECTED_STYLE,
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
                            className="steps-empty text-sm text-muted",
                        ),
                    ),
                    _issue_tab("warning", RUN_TAB_WARNING_SELECTED_CLASS),
                    _issue_tab("error", RUN_TAB_ERROR_SELECTED_CLASS),
                    dcc.Tab(
                        label="Log",
                        value="log",
                        className=RUN_TAB_CLASS,
                        selected_className=RUN_TAB_SELECTED_CLASS,
                        style=RUN_TAB_STYLE,
                        selected_style=RUN_TAB_SELECTED_STYLE,
                        children=html.Pre(
                            "No run yet.",
                            id="run-log",
                            className=(
                                "run-log m-0 h-full max-h-[34rem] overflow-auto whitespace-pre-wrap "
                                "rounded-sm border border-border bg-page p-3 font-mono "
                                "text-sm leading-[1.5] text-muted "
                                "[scrollbar-color:var(--color-border-strong)_transparent] "
                                "[scrollbar-gutter:stable] [scrollbar-width:thin]"
                            ),
                        ),
                    ),
                ],
            ),
        ],
        id="run-sidebar",
        className=RUN_SIDEBAR_CLASS,
    )


def _issue_tab(kind: str, selected_class: str) -> dcc.Tab:
    """Build a Warnings or Errors tab; it starts disabled until the run reports one."""
    return dcc.Tab(
        label=f"{kind.title()}s",
        value=f"{kind}s",
        id=f"run-{kind}s-tab",
        disabled=True,
        className=RUN_TAB_CLASS,
        selected_className=selected_class,
        disabled_className=RUN_TAB_DISABLED_CLASS,
        style=RUN_TAB_STYLE,
        selected_style=RUN_TAB_SELECTED_STYLE,
        disabled_style=RUN_TAB_STYLE,
        children=html.Div(
            render_issues((), kind),
            id=f"run-{kind}s",
            className="issues-body max-h-[34rem] overflow-auto",
        ),
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
                    COMPACT_UPLOAD_TEXT_CLASS,
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
                        "output-selector min-h-8 w-full rounded-sm "
                        "border !border-border !bg-page p-0 text-left "
                        "!font-mono !text-sm !text-text transition duration-150 ease-out "
                        "hover:!border-border-strong "
                        "[&_.dash-dropdown-trigger]:!min-h-8 "
                        "[&_.dash-dropdown-trigger]:!gap-2 "
                        "[&_.dash-dropdown-trigger]:!px-2.5 "
                        "focus:!border-accent focus:!outline-3 "
                        "focus:outline-offset-2 focus:!outline-accent/35 "
                        "focus-visible:!border-accent focus-visible:!outline-3 "
                        "focus-visible:outline-offset-2 "
                        "focus-visible:!outline-accent/35 "
                        "disabled:cursor-not-allowed disabled:!border-border "
                        "disabled:!bg-page disabled:!text-muted disabled:opacity-50"
                    ),
                ),
            ),
            html.Dl(
                id="result-summary",
                className="result-summary text-sm leading-[1.4] text-muted",
            ),
            _field(
                "Pipeline outputs",
                dcc.Tabs(
                    id="result-tabs",
                    value=PipelineStep.REWARD_MACHINE.value,
                    className="result-tabs flex-none border-b border-border",
                    content_style={"display": "none"},
                    children=[_step_tab(PipelineStep.REWARD_MACHINE)],
                ),
                html.Div(
                    id="result-bodies",
                    children=result_bodies(
                        {PipelineStep.REWARD_MACHINE: "No output selected."},
                        PipelineStep.REWARD_MACHINE,
                    ),
                    className=(
                        "step-bodies grid min-w-0 flex-1 min-h-[16rem] [contain:size] [grid-template-rows:minmax(0,1fr)]"
                    ),
                ),
                class_name=f"{FIELD_CLASS} flex-1 min-h-0",
            ),
        ],
        className=(
            "output-panel flex min-h-0 min-w-0 flex-col gap-3 rounded-sm "
            "border border-border bg-surface p-4 max-[800px]:min-h-[30rem]"
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
                        className="panel-heading flex min-w-0 shrink-0 items-center gap-2",
                    ),
                    html.Div(
                        [
                            html.Button(
                                [_icon("focus", TOOLBAR_ICON_SIZE_CLASS), "Focus graph"],
                                id="graph-focus-toggle",
                                n_clicks=0,
                                className=f"graph-focus-toggle {GRAPH_TOOLBAR_BUTTON_CLASS}",
                                **{"aria-label": "Focus graph", "aria-pressed": False},
                            ),
                            html.Details(
                                [
                                    html.Summary(
                                        [_icon("download", TOOLBAR_ICON_SIZE_CLASS), "Export"],
                                        className=(
                                            f"graph-export-summary {GRAPH_TOOLBAR_BUTTON_CLASS} list-none"
                                        ),
                                    ),
                                    html.Div(
                                        [
                                            html.Button(
                                                "Export SVG",
                                                id="graph-export-button",
                                                n_clicks=0,
                                                disabled=True,
                                                className=f"graph-export-button {GRAPH_TOOLBAR_BUTTON_CLASS}",
                                                **{"aria-label": "Export the graph as an SVG file"},
                                            ),
                                            html.Button(
                                                "Export HTML",
                                                id="graph-export-html-button",
                                                n_clicks=0,
                                                disabled=True,
                                                className=f"graph-export-html-button {GRAPH_TOOLBAR_BUTTON_CLASS}",
                                                **{
                                                    "aria-label": (
                                                        "Export the graph as an interactive HTML file"
                                                    )
                                                },
                                            ),
                                        ],
                                        className=(
                                            "graph-export-panel absolute right-0 top-full z-20 mt-1 grid gap-1 "
                                            "rounded-sm border border-border-strong bg-surface p-2.5 "
                                            "text-text shadow-none"
                                        ),
                                    ),
                                ],
                                id="graph-export-menu",
                                className="graph-export relative",
                            ),
                        ],
                        className=(
                            "graph-toolbar-actions flex items-center gap-2 max-[800px]:hidden"
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
                                    html.H3(
                                        "Graph legend",
                                        className="legend-title text-xs font-semibold",
                                    ),
                                    html.Ul(
                                        [
                                            _legend_row(
                                                (
                                                    "legend-swatch inline-block size-[13px] flex-none "
                                                    "rounded-full border-2 border-border-strong "
                                                    "bg-raised"
                                                ),
                                                "Default state",
                                            ),
                                            _legend_row(
                                                (
                                                    "legend-swatch-initial legend-swatch inline-block "
                                                    "size-[13px] flex-none rounded-full "
                                                    "border-[3px] border-accent bg-raised"
                                                ),
                                                "Initial state",
                                            ),
                                            _legend_row(
                                                (
                                                    "legend-swatch-accepting legend-swatch inline-block "
                                                    "size-[13px] flex-none rounded-full "
                                                    "border-2 border-success bg-success-tint"
                                                ),
                                                "Accepting state",
                                            ),
                                            _legend_row(
                                                (
                                                    "legend-swatch-rejecting legend-swatch inline-block "
                                                    "size-[13px] flex-none rounded-full "
                                                    "border-2 border-danger bg-danger-tint"
                                                ),
                                                "Rejecting state",
                                            ),
                                            _legend_row(
                                                (
                                                    "legend-swatch-transition legend-swatch inline-block "
                                                    "h-0 w-[13px] flex-none rounded-none border-0 "
                                                    "border-t-2 border-border-strong bg-transparent"
                                                ),
                                                "Explicit transition",
                                            ),
                                        ],
                                        className=("legend-list mt-1.5 grid list-none gap-1.5 p-0"),
                                    ),
                                    html.P(
                                        "Only explicit transitions are shown. Omitted transitions are zero-reward self-loops.",
                                        className=(
                                            "graph-explanation mt-1.5 max-w-[25rem] whitespace-normal break-words "
                                            "text-xs leading-[1.4] text-muted max-[560px]:m-0 max-[560px]:text-left"
                                        ),
                                    ),
                                ],
                                className=(
                                    "graph-legend-panel absolute right-0 top-full z-20 mt-1 max-h-[calc(100dvh_-_7rem)] "
                                    "w-[18rem] max-w-[calc(100vw_-_2rem)] overflow-auto whitespace-normal rounded-sm "
                                    "border border-border-strong bg-surface p-2.5 text-text shadow-none"
                                ),
                            ),
                        ],
                        className="graph-legend relative ml-auto shrink-0",
                    ),
                ],
                className=(
                    "graph-toolbar relative flex flex-none flex-wrap items-center justify-between "
                    "gap-4 pb-1"
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
                        className="graph-canvas min-h-[22rem] h-full w-full flex-1",
                    ),
                ],
                className=(
                    "graph-stage relative min-h-0 flex-1 rounded-sm border border-border bg-page"
                ),
            ),
        ],
        className=(
            "graph-panel relative flex min-h-0 min-w-0 flex-col gap-3 overflow-hidden "
            "rounded-sm border border-border bg-surface p-4 "
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
                                    "eyebrow font-sans text-sm font-medium text-muted "
                                    "tracking-[0.02em]"
                                ),
                            ),
                            html.H1(
                                "Review and visualize",
                                className=(
                                    "app-title mt-2.5 font-display text-display font-semibold "
                                    "leading-[1.02] tracking-[-0.035em]"
                                ),
                            ),
                        ]
                    ),
                    html.P(
                        "A local path from environment Markdown to critic-validated Reward Machines.",
                        className=(
                            "usage-guide max-w-[30rem] pt-1.5 text-right text-base leading-[1.6] "
                            "text-muted max-[800px]:text-left"
                        ),
                    ),
                ],
                className=(
                    "app-header flex flex-none items-start justify-between gap-x-8 gap-y-4 "
                    "pt-2 pb-4 max-[800px]:flex-col max-[800px]:gap-[0.55rem]"
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
            dcc.Store(id="graph-attached", data=None),
            dcc.Store(id="issues-shown", data=[]),
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
