import base64
import json
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from time import sleep
from types import SimpleNamespace
from unittest.mock import patch
from xml.etree import ElementTree

from dash import no_update

from scripts import generate_rm
from src.compiler.reward_machine import RewardMachineStructure, Transition
from src.config import REASONING_LEVELS, Configuration, GraphStyle
from src.engines import GenericEngine, ImmediateEngineError
from src.models import EnvironmentDescription
from src.utils import (
    CYTOSCAPE_STYLESHEET,
    PipelineStep,
    ProgressEvent,
    StepState,
    render_elements_html,
    render_structure_svg,
    reward_machine_to_elements,
)
from src.web.application import (
    IMPORTED_RM_VALUE,
    _load_environment,
    _load_environment_code,
    _poll_panels,
    _resolve_environment_filename,
    _run_status,
    _select_reasoning,
    _step_attempts,
    create_app,
)
from src.web.components import STATUS_CLASSES, create_layout, render_steps
from src.web.runner import (
    STEP_ORDER,
    RunController,
    RunRequest,
    RunSnapshot,
    RunState,
    StepSnapshot,
    TaskSnapshot,
    _initial_task,
)


def _step_state(task: TaskSnapshot, step: PipelineStep) -> StepState | None:
    return next((item.state for item in task.steps if item.step is step), None)


class WebTests(unittest.TestCase):
    def test_failed_run_exposes_generator_critic_and_provider_reasons(self):
        environment_markdown = (
            "# Demo\n## Propositions\n- `done`: Completion event\n- `next`: Next event"
        )
        environment = EnvironmentDescription.from_markdown(environment_markdown)
        dfa = {
            "states": ("0", "1"),
            "initial_state": "0",
            "accepting_states": ("1",),
            "alphabet": ("done",),
            "transitions": {
                ("0", "!done"): "0",
                ("0", "done"): "1",
                ("1", "true"): "1",
            },
        }
        for failure, expected, calls in (
            ("generator", "Last error: Unsupported priority: 'none'", 11),
            ("critic", "Last critic feedback: Rejected candidate", 6),
            ("provider", "Experiment provider is unavailable", 0),
        ):
            with self.subTest(failure=failure), TemporaryDirectory() as directory:
                requests = []

                def request(
                    _model,
                    _system,
                    _user,
                    _schema,
                    name,
                    failure=failure,
                    requests=requests,
                ):
                    requests.append(name)
                    if name == "declare_proposal":
                        return json.dumps(
                            {
                                "clauses": [
                                    {
                                        "normalized_clause": "Finish",
                                        "pattern": "Existence",
                                        "propositions": ["done"],
                                        "priority": "none" if failure == "generator" else "hard",
                                    }
                                ]
                            }
                        )
                    return json.dumps(
                        {
                            "accepted": name != failure,
                            "feedback": "Rejected candidate",
                        }
                    )

                def request_text(_model, _system, _user):
                    return '["state one", "state two"]'

                generator_engine = GenericEngine(
                    environment,
                    "test-generator-model",
                    "test-provider",
                    request,
                    request_text,
                )
                critic_engine = GenericEngine(
                    environment,
                    "test-critic-model",
                    "test-provider",
                    request,
                    request_text,
                )
                controller = RunController(generate_rm)
                with (
                    patch.object(Configuration, "LOGS_PATH", Path(directory) / "logs"),
                    patch.object(Configuration, "OUTPUT_PATH", Path(directory) / "outputs"),
                    patch(
                        "scripts.generate_rm.setup_environment_and_engines",
                        return_value=(environment, generator_engine, critic_engine),
                        side_effect=ImmediateEngineError(expected)
                        if failure == "provider"
                        else None,
                    ),
                    patch(
                        "scripts.generate_rm.compile_dfas",
                        return_value=(dfa,),
                    ),
                ):
                    controller.start(RunRequest(environment_markdown, ["Finish"], "failed.rm"))
                    controller._worker.join(timeout=5)
                    self.assertFalse(controller._worker.is_alive())
                snapshot = controller.snapshot()
                self.assertEqual(snapshot.status, RunState.FAILED)
                self.assertIn(expected, snapshot.error)
                word, _status_class, reason = _run_status(snapshot)
                self.assertEqual(word, "Failed")
                self.assertIn(expected, reason)
                self.assertEqual(len(requests), calls)
                self.assertIn(expected, snapshot.log_path.read_text(encoding="utf-8"))
                self.assertEqual(list((Path(directory) / "outputs" / "RMs").glob("*.rm")), [])

    def test_component_and_css_classes_stay_in_sync(self):
        root = Path(__file__).parents[1]
        tailwind_source = (root / "app/src/web/tailwind.css").read_text()
        custom_stylesheet = (root / "app/assets/app.css").read_text()
        compiled_stylesheet = (root / "app/assets/00-tailwind.css").read_text()

        self.assertNotIn("@apply", tailwind_source)
        self.assertNotIn("@layer components", tailwind_source)
        self.assertIn(".flex{", compiled_stylesheet)
        self.assertLess(len(custom_stylesheet), 6_000)

        custom_classes = set(re.findall(r"(?<![\w-])\.([a-zA-Z_][\w-]*)", custom_stylesheet))
        self.assertEqual(
            {name for name in custom_classes if not name.startswith("dash-")},
            {
                "critic-options",
                "graph-canvas",
                "outputs-options",
                "run-log",
                "run-tab",
                "status-reason",
                "step-output",
            },
        )

        pending = [create_layout()]
        component_classes = []
        while pending:
            component = pending.pop()
            class_name = getattr(component, "className", None)
            if class_name:
                component_classes.append(class_name)
            children = getattr(component, "children", None)
            if isinstance(children, (list, tuple)):
                pending.extend(children)
            elif hasattr(children, "children"):
                pending.append(children)
        self.assertTrue(component_classes)
        self.assertTrue(all(len(class_name.split()) > 1 for class_name in component_classes))

    def test_environment_upload_names_the_output_after_its_title(self):
        cases = (
            (
                "# MultiTaxi with Two Passengers\n\n## Environment",
                "environment.md",
                "multitaxi-with-two-passengers.rm",
            ),
            ("No heading here.", "ENVIRONMENT.md", "environment.rm"),
            ("# Door Key\n", "doorkey.md", "doorkey.rm"),
        )
        for text, filename, expected in cases:
            payload = "data:text/markdown;base64," + base64.b64encode(text.encode()).decode()
            with self.subTest(filename=filename, text=text.splitlines()[0]):
                with patch("src.web.application._existing_output_names", return_value=set()):
                    markdown, status, output_name, rows = _load_environment(payload, filename)
                self.assertEqual(markdown, text)
                self.assertEqual(status, f"Loaded {filename}; edit the text before generating.")
                self.assertEqual(output_name, expected)
                self.assertIs(rows, no_update)

    def test_tasks_manifest_upload_fills_environment_name_and_tasks(self):
        with TemporaryDirectory() as root:
            Path(root, "env.md").write_text("# Door Key\n", encoding="utf-8")
            manifest = {
                "env": "MiniGrid DoorKey",
                "env_description": "env.md",
                "tasks": ["Eventually acquire the key.", "Reach the goal."],
            }
            payload = (
                "data:application/json;base64,"
                + base64.b64encode(json.dumps(manifest).encode()).decode()
            )
            with (
                patch("src.web.application._REPO_ROOT", Path(root)),
                patch("src.web.application._existing_output_names", return_value=set()),
            ):
                markdown, status, output_name, rows = _load_environment(payload, "tasks.json")
                incomplete = _load_environment(
                    "data:application/json;base64," + base64.b64encode(b'{"env": "x"}').decode(),
                    "tasks.json",
                )
                resolved = _resolve_environment_filename(markdown, payload, "tasks.json")
        self.assertEqual(markdown, "# Door Key\n")
        self.assertEqual(output_name, "minigrid-doorkey.rm")
        self.assertIn("2 tasks and env.md from tasks.json", status)
        self.assertEqual([row.children[1].children[1].value for row in rows], manifest["tasks"])
        self.assertEqual(resolved, "env.md")
        self.assertIs(incomplete[0], no_update)
        self.assertIn("env, env_description, tasks", incomplete[1])

    def test_labeling_run_gets_the_code_file_beside_the_facts(self):
        facts = "# Demo\n## Propositions\n- `done`: Finished\n"
        code = "# Demo: code notes\n\n## Labeling API\n\n- `env.grid.get(x, y)`: a cell\n"
        seen = {}

        def generate(CONFIG, hooks):
            seen["facts"] = EnvironmentDescription.from_file(CONFIG.environment)
            seen["labeling"] = EnvironmentDescription.from_file(CONFIG.environment, code=True)
            return True

        controller = RunController(generate)
        with self.assertRaisesRegex(ValueError, "environment-code.md"):
            controller.start(RunRequest(facts, ["finish"], "out.rm", labeling=True))
        controller.start(
            RunRequest(
                facts,
                ["finish"],
                "out.rm",
                environment_filename="doorkey.md",
                environment_code=code,
                labeling=True,
            )
        )
        controller._worker.join(timeout=5)
        self.assertEqual(controller.snapshot().status, RunState.COMPLETED)
        self.assertIsNone(seen["facts"].labeling_api)
        self.assertEqual(seen["labeling"].require_labeling_api(), "- `env.grid.get(x, y)`: a cell")
        payload = "data:text/markdown;base64," + base64.b64encode(code.encode()).decode()
        self.assertEqual(_load_environment_code(payload, "environment-code.md")[0], code)

    def test_state_descriptions_skip_follows_the_request_flag(self):
        enabled = _initial_task(0, "finish", RunRequest("# Demo", ["finish"], "out.rm"))
        disabled = _initial_task(
            0,
            "finish",
            RunRequest("# Demo", ["finish"], "out.rm", state_descriptions=False),
        )
        self.assertIs(_step_state(enabled, PipelineStep.STATE_DESCRIPTIONS), StepState.PENDING)
        self.assertIs(_step_state(disabled, PipelineStep.STATE_DESCRIPTIONS), StepState.SKIPPED)
        self.assertIs(_step_state(disabled, PipelineStep.LABELING), StepState.SKIPPED)

    def test_layout_uses_critic_options_and_no_approval_controls(self):
        layout = str(create_layout())
        self.assertIn("critic-options", layout)
        self.assertIn("descriptions-toggle", layout)
        self.assertIn("labeling-toggle", layout)
        self.assertIn("embeddings-toggle", layout)
        self.assertNotIn("approve-button", layout)
        self.assertNotIn("decline-button", layout)
        self.assertEqual(
            {state.value for state in RunState},
            {"idle", "running", "completed", "failed", "stopped"},
        )
        self.assertIn("stop-run", layout)
        self.assertIn("Stop generation", layout)

    def test_graph_starts_with_the_standalone_renderer_layout(self):
        layout = create_layout(CYTOSCAPE_STYLESHEET)
        pending = [layout]
        graph = None
        while pending:
            component = pending.pop()
            if getattr(component, "id", None) == "rm-graph":
                graph = component
                break
            children = getattr(component, "children", None)
            if isinstance(children, (list, tuple)):
                pending.extend(children)
            elif hasattr(children, "children"):
                pending.append(children)
        self.assertIsNotNone(graph)
        self.assertEqual(graph.layout["name"], "preset")
        self.assertTrue(graph.layout["fit"])
        self.assertTrue(graph.userPanningEnabled)
        self.assertTrue(graph.userZoomingEnabled)

        machine = RewardMachineStructure(
            states=(0, 1, 2, 3),
            initial_state=0,
            final_state=3,
            rejecting_states=(1,),
            transitions=(
                Transition(0, 1, ("!a", "b"), 0),
                Transition(0, 2, ("a", "!b"), 0),
                Transition(2, 3, ("b",), 1.1),
            ),
        )
        graph.elements = reward_machine_to_elements(machine)
        points = {
            element["data"]["label"]: (
                element["position"]["x"],
                element["position"]["y"],
            )
            for element in graph.elements
            if "source" not in element["data"]
        }
        self.assertLess(points["u0"][1], points["u2"][1])
        self.assertLess(points["u2"][1], points["u3"][1])
        self.assertTrue(all(points["u1"][0] < points[state][0] for state in ("u0", "u2", "u3")))

        svg = ElementTree.fromstring(render_structure_svg(machine))
        rendered = {
            text.text: (float(text.attrib["x"]), float(text.attrib["y"]))
            for text in svg.findall(
                "{http://www.w3.org/2000/svg}g/{http://www.w3.org/2000/svg}text"
            )
        }
        for state, (x, y) in points.items():
            self.assertEqual(
                (x - points["u0"][0], y - points["u0"][1]),
                (
                    rendered[state][0] - rendered["u0"][0],
                    rendered[state][1] - rendered["u0"][1],
                ),
            )

    def test_layout_puts_the_final_last_the_well_aside_and_states_off_foreign_edges(self):
        # Every earlier state points at every later one, and all but the final also at the well.
        machine = RewardMachineStructure(
            states=tuple(range(7)),
            initial_state=0,
            final_state=5,
            rejecting_states=(6,),
            transitions=tuple(
                Transition(source, target, (f"p{source}{target}",), 0.1)
                for source in range(6)
                for target in range(source + 1, 7)
            ),
        )

        def positions(machine):
            return {
                int(element["data"]["id"].removeprefix("state-")): (
                    element["position"]["x"],
                    element["position"]["y"],
                )
                for element in reward_machine_to_elements(machine)
                if "source" not in element["data"]
            }

        def assert_states_off_edges(machine, points):
            limit = GraphStyle().node_diameter / 2 + 6
            for transition in machine.transitions:
                (ax, ay), (bx, by) = points[transition.source], points[transition.destination]
                length = (bx - ax) ** 2 + (by - ay) ** 2
                for state in set(machine.states) - {transition.source, transition.destination}:
                    x, y = points[state]
                    along = max(
                        0.0, min(1.0, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / length)
                    )
                    gap = (
                        (x - ax - along * (bx - ax)) ** 2 + (y - ay - along * (by - ay)) ** 2
                    ) ** 0.5
                    self.assertGreater(
                        gap, limit, f"u{state} on u{transition.source} -> u{transition.destination}"
                    )

        points = positions(machine)
        self.assertEqual(points[5][1], max(y for state, (_, y) in points.items() if state != 6))
        self.assertTrue(all(points[6][0] < points[state][0] for state in range(6)))
        self.assertTrue(all(points[a][1] < points[b][1] for a in range(5) for b in range(a + 1, 6)))
        assert_states_off_edges(machine, points)

        # A back edge is drawn straight too, so it must not run through the state between.
        cycle = RewardMachineStructure(
            states=(0, 1, 2, 3),
            initial_state=0,
            final_state=3,
            rejecting_states=(),
            transitions=(
                Transition(0, 1, ("a",), 0),
                Transition(1, 2, ("b",), 0),
                Transition(2, 0, ("c",), 0),
                Transition(2, 3, ("d",), 0),
            ),
        )
        assert_states_off_edges(cycle, positions(cycle))
        self.assertNotIn(" Q ", render_structure_svg(cycle))

    def test_html_export_embeds_every_state_the_stylesheet_and_the_shared_script(self):
        machine = RewardMachineStructure(
            states=(0, 1, 2),
            initial_state=0,
            final_state=2,
            rejecting_states=(),
            transitions=(
                Transition(0, 1, ("a", "!b"), 0),
                Transition(1, 2, ("</script>",), 1.0),
            ),
        )
        elements = reward_machine_to_elements(machine)
        elements[-1]["classes"] += " rm-hover"
        page = render_elements_html(elements)

        payload = re.search(
            r'<script id="rm-graph-data" type="application/json">(.*?)</script>', page
        )
        data = json.loads(payload.group(1))
        state_ids = {element["data"]["id"] for element in data["elements"] if "position" in element}
        self.assertEqual(state_ids, {"state-0", "state-1", "state-2"})
        self.assertEqual(data["theme"], "auto")
        self.assertEqual(data["styles"]["dark"], CYTOSCAPE_STYLESHEET)
        self.assertEqual(len(data["styles"]["light"]), len(CYTOSCAPE_STYLESHEET))
        self.assertNotIn("rm-hover", json.dumps(data["elements"]))

        assets = Path(__file__).parents[1] / "app" / "assets"
        self.assertIn((assets / "rm_graph.js").read_text(encoding="utf-8"), page)
        self.assertIn((assets / "rm_graph.css").read_text(encoding="utf-8"), page)
        self.assertIn("rm-graph-literal-positive", page)

        light = render_elements_html(elements, theme="light")
        self.assertIn('"theme": "light"', light)
        with self.assertRaises(ValueError):
            render_elements_html(elements, theme="sepia")

    def test_poll_locks_inputs_and_critics_while_running_and_keeps_results(self):
        controller = RunController(generate_rm)
        app = create_app(controller)
        key = next(key for key in app.callback_map if "critic-options.options" in key)
        poll = app.callback_map[key]["callback"].__wrapped__
        idle = poll(0, None, [{"index": 0}])
        self.assertFalse(idle[16][0]["disabled"])
        controller._status, controller._error = RunState.RUNNING, None
        active = poll(0, None, [{"index": 0}])
        self.assertTrue(active[4])
        self.assertTrue(active[5] and active[6] and active[7])  # markdown, code upload, code text
        self.assertTrue(all(item["disabled"] for item in active[16]))
        self.assertTrue(all(active[17]))  # reasoning segments
        self.assertTrue(active[18])  # attempts input
        self.assertTrue(all(item["disabled"] for item in active[-1]))
        controller._status = RunState.COMPLETED
        controller._results = (
            SimpleNamespace(
                proposal=SimpleNamespace(task="finish"),
                text="rm",
                reward_machine=RewardMachineStructure((0,), 0, 0, (), ()),
                bundle_path=Path("out-bundle"),
                embedding_path=Path("out-embeddings") / "embeddings.json",
                embedding_settings={"model": "nomic-embed-text", "dimension": 2},
                warnings=("Rule-only task: no hard goal clause",),
            ),
        )
        controller._output_paths = (Path("out.rm"),)
        controller._step_outputs = {
            0: {
                PipelineStep.REWARD_MACHINE: "rm",
                PipelineStep.STATE_DESCRIPTIONS: {"u0": "start", "u1": "done"},
            }
        }
        result_key = next(key for key in app.callback_map if "result-summary.children" in key)
        render = app.callback_map[result_key]["callback"].__wrapped__
        summary, tabs, bodies, elements, export_name, *export_disabled = render(0)
        self.assertIn("out.rm", str(summary))
        self.assertIn("Rule-only task", str(summary))
        self.assertIn("out-bundle", str(summary))
        self.assertIn("nomic-embed-text dim=2", str(summary))
        self.assertIn("out-embeddings", str(summary))
        self.assertEqual([tab.value for tab in tabs], ["reward_machine", "state_descriptions"])
        self.assertIn("State descriptions", str(tabs))
        self.assertIn('"u0"', str(bodies))
        self.assertIn('"start"', str(bodies))
        self.assertTrue(elements)
        self.assertEqual(export_name, "out")
        self.assertEqual(export_disabled, [False, False])

    def test_optional_navigation_inputs_and_dark_tab_styles(self):
        app = create_app(RunController(generate_rm))
        key = next(key for key in app.callback_map if "critic-options.options" in key)
        optional_inputs = {
            item.component_id: item.allow_optional
            for item in app.callback_map[key]["raw_inputs"]
            if isinstance(item.component_id, str) and item.component_id in {"run-prev", "run-next"}
        }
        self.assertEqual(optional_inputs, {"run-prev": True, "run-next": True})

        layout = create_layout()
        pending = [layout]
        tabs = None
        while pending:
            component = pending.pop()
            if getattr(component, "id", None) == "run-tabs":
                tabs = component
                break
            children = getattr(component, "children", None)
            if isinstance(children, (list, tuple)):
                pending.extend(children)
            elif hasattr(children, "children"):
                pending.append(children)
        self.assertIsNotNone(tabs)
        for tab in tabs.children:
            self.assertEqual(tab.style["backgroundColor"], "transparent")
            self.assertEqual(tab.selected_style["backgroundColor"], "transparent")

    def test_rerun_of_the_same_attempt_restarts_the_stages(self):
        controller = RunController(generate_rm)
        controller._tasks = (
            TaskSnapshot(0, "finish", steps=tuple(StepSnapshot(step) for step in STEP_ORDER)),
        )
        for step, state in (
            (PipelineStep.GENERATE, StepState.RUNNING),
            (PipelineStep.CRITIC, StepState.FAILED),
            (PipelineStep.GENERATE, StepState.RUNNING),
        ):
            controller._record_event(ProgressEvent(0, 1, step, state, detail="timeout"))
        task = controller.snapshot().tasks[0]
        self.assertEqual(task.state, StepState.RUNNING)
        self.assertEqual(task.failures, ("Attempt 1: timeout",))
        self.assertIn("Attempt 1 of 3", str(render_steps((task,))))

    def test_issue_tabs_follow_the_run_and_split_warnings_from_errors(self):
        controller = RunController(generate_rm)
        app = create_app(controller)
        key = next(key for key in app.callback_map if "run-warnings-tab.label" in key)
        poll = app.callback_map[key]["callback"].__wrapped__
        controller._warnings = ["Task 1: second run"]
        controller._tasks = (
            TaskSnapshot(
                0,
                "finish",
                steps=(StepSnapshot(PipelineStep.GENERATE, StepState.FAILED),),
                failures=("Attempt 1: unclear", "Attempt 2: still unclear"),
            ),
        )
        controller._error = "Generation failed."
        update = poll(0, [], "errors")
        self.assertEqual(update[0], "Warnings · 2")
        self.assertFalse(update[1])
        self.assertEqual(update[3], "Errors · 2")
        self.assertIs(update[6], no_update)
        self.assertEqual(
            update[7],
            [
                ["Task 1: second run", "Task 1 · Attempt 1: unclear"],
                ["Task 1 · Attempt 2: still unclear", "Generation failed."],
            ],
        )
        self.assertIs(poll(0, update[7], "steps")[0], no_update)
        controller._status, controller._error = RunState.STOPPED, "Stopped by the user"
        self.assertEqual(poll(0, [], "steps")[7][1], [])
        controller._status, controller._error = RunState.RUNNING, None
        self.assertEqual(poll(0, [], "steps")[7][1], [])
        controller._status = RunState.IDLE
        controller._warnings, controller._tasks, controller._error = [], (), None
        empty = poll(0, update[7], "warnings")
        self.assertEqual((empty[0], empty[1], empty[6]), ("Warnings", True, "steps"))

    def test_output_selector_and_task_chevrons_follow_each_other(self):
        tasks = tuple(TaskSnapshot(index, f"t{index}") for index in range(3))
        paths = tuple(Path(f"out-{index}.rm") for index in range(3))
        snapshot = RunSnapshot(RunState.COMPLETED, (), (), paths, tasks=tasks, run_id=7)
        selection = {"selected": 0, "last_active": None, "run_id": 7}
        imported = {"filename": "x.rm", "text": "0 0 0\n"}

        def poll(trigger, selected, imported_data=None):
            with patch("src.web.application._triggered_id", return_value=trigger):
                panels = _poll_panels(snapshot, selected, [], selection, imported_data)
            return panels[17], panels[19]

        selector, _ = poll("run-next", 0)
        self.assertEqual(selector, 1)
        selector, steps = poll("output-selector", 2)
        self.assertIs(selector, no_update)
        self.assertIn("Task 3 of 3", str(steps))
        selector, steps = poll("output-selector", IMPORTED_RM_VALUE, imported)
        self.assertIs(selector, no_update)
        self.assertIn("Task 1 of 3", str(steps))
        selector, _ = poll("run-next", IMPORTED_RM_VALUE, imported)
        self.assertEqual(selector, 1)

    def test_task_arrows_disable_at_the_edges(self):
        tasks = tuple(TaskSnapshot(index, f"t{index}") for index in range(3))
        for selected, expected in ((0, (True, False)), (1, (False, False)), (2, (False, True))):
            nav = render_steps(tasks, selected).children[-1]
            self.assertEqual((nav.children[0].disabled, nav.children[-1].disabled), expected)

    def test_structured_steps_and_retry_reset(self):
        controller = RunController(generate_rm)
        controller._tasks = (
            TaskSnapshot(
                0,
                "finish",
                steps=tuple(StepSnapshot(step) for step in STEP_ORDER),
            ),
        )
        controller._record_event(ProgressEvent(0, 1, PipelineStep.GENERATE, StepState.RUNNING))
        controller._record_event(
            ProgressEvent(0, 1, PipelineStep.GENERATE, StepState.FAILED, 0.2, "bad proposal")
        )
        controller._record_event(ProgressEvent(0, 2, PipelineStep.GENERATE, StepState.RUNNING))
        snapshot = controller.snapshot()
        self.assertEqual(snapshot.tasks[0].attempt, 2)
        self.assertEqual(snapshot.tasks[0].failures, ("Attempt 1: bad proposal",))
        self.assertEqual(snapshot.tasks[0].state, StepState.RUNNING)
        self.assertIn("Task 1 of 1", str(render_steps(snapshot.tasks)))

    def test_reasoning_segments_keep_one_selected_level(self):
        ids = [{"type": "reasoning-option", "index": level} for level in REASONING_LEVELS]

        def select(trigger: object, current: str):
            with patch("src.web.application.ctx", SimpleNamespace(triggered_id=trigger)):
                return _select_reasoning([0, 0, 0, 1, 0], current, ids)

        level, classes, checked = select({"type": "reasoning-option", "index": "high"}, "none")
        selected = REASONING_LEVELS.index("high")
        self.assertEqual(level, "high")
        self.assertIn("bg-hover text-text", classes[selected])
        self.assertTrue(
            all(
                "bg-hover text-text" not in name
                for index, name in enumerate(classes)
                if index != selected
            )
        )
        self.assertEqual(checked, [False, False, False, True, False])
        self.assertIs(select({"type": "reasoning-option", "index": "high"}, "high")[0], no_update)
        self.assertIs(select("generate-button", "low")[0], no_update)
        self.assertEqual(select("generate-button", "low")[2], [False, True, False, False, False])

    def test_stepper_clamps_the_attempt_limit_and_locks_both_buttons(self):
        limits = Configuration.ATTEMPT_LIMITS
        last = limits.stop - 1

        def step(trigger: str, value: object, locked: bool = False):
            with patch("src.web.application.ctx", SimpleNamespace(triggered_id=trigger)):
                return _step_attempts(1, 1, value, locked)

        self.assertEqual(step("attempts-decrement", limits.start), (limits.start, True, False))
        self.assertEqual(step("attempts-decrement", 5), (4, False, False))
        self.assertEqual(step("attempts-increment", last), (last, False, True))
        self.assertEqual(step("attempts-increment", 5), (6, False, False))
        self.assertEqual(step("attempts", 5), (no_update, False, False))
        self.assertEqual(step("attempts", True), (no_update, True, True))
        self.assertEqual(step("attempts-decrement", None), (no_update, True, True))
        self.assertEqual(step("attempts-decrement", 5, locked=True), (no_update, True, True))
        self.assertEqual(step("attempts-increment", last, locked=True), (no_update, True, True))

    def test_stop_ends_the_run_neutral(self):
        def looping_generate(_CONFIG, hooks):
            while not hooks.is_cancelled():
                sleep(0.01)
            return False

        controller = RunController(looping_generate)
        self.assertFalse(controller.stop())
        controller.start(RunRequest("# Demo", ["finish"], "stopped.rm"))
        self.assertTrue(controller.stop())
        controller._worker.join(timeout=5)
        self.assertFalse(controller._worker.is_alive())
        snapshot = controller.snapshot()
        self.assertEqual(snapshot.status, RunState.STOPPED)
        self.assertEqual(snapshot.error, "Stopped by the user")
        self.assertTrue(snapshot.stopping)
        self.assertEqual(_run_status(snapshot), ("Stopped", STATUS_CLASSES["stopped"], ""))

    def test_a_stopping_run_keeps_the_running_pill(self):
        controller = RunController(generate_rm)
        controller._status, controller._error = RunState.RUNNING, None
        controller._stopping = True
        self.assertEqual(
            _run_status(controller.snapshot()),
            ("Stopping…", STATUS_CLASSES["running"], ""),
        )

    def test_poll_swaps_the_generate_and_stop_slot(self):
        controller = RunController(generate_rm)
        app = create_app(controller)
        key = next(key for key in app.callback_map if "critic-options.options" in key)
        poll = app.callback_map[key]["callback"].__wrapped__
        idle_generate, idle_stop, idle_stop_disabled = poll(0, None, [{"index": 0}])[13:16]
        self.assertNotIn("!hidden", idle_generate.split())
        self.assertIn("!hidden", idle_stop.split())
        self.assertFalse(idle_stop_disabled)
        controller._status, controller._error = RunState.RUNNING, None
        running_generate, running_stop, running_stop_disabled = poll(0, None, [{"index": 0}])[13:16]
        self.assertIn("!hidden", running_generate.split())
        self.assertNotIn("!hidden", running_stop.split())
        self.assertFalse(running_stop_disabled)
        controller._stopping = True
        self.assertTrue(poll(0, None, [{"index": 0}])[15])

    def test_stop_control_reports_whether_a_run_was_active(self):
        controller = RunController(generate_rm)
        app = create_app(controller)
        key = next(key for key in app.callback_map if key.startswith("run-feedback.children@"))
        stop = app.callback_map[key]["callback"].__wrapped__
        self.assertEqual(stop(1), "No run is active.")
        controller._status, controller._error = RunState.RUNNING, None
        self.assertEqual(stop(1), "Stopping after the current request…")


if __name__ == "__main__":
    unittest.main()
