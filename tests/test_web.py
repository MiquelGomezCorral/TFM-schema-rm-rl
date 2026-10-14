import json
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from xml.etree import ElementTree

from scripts import generate_rm
from src.compiler.reward_machine import RewardMachineStructure, Transition
from src.config import Configuration, GraphStyle
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
from src.web.application import create_app
from src.web.components import create_layout, render_steps
from src.web.runner import (
    STEP_ORDER,
    RunController,
    RunRequest,
    RunState,
    StepSnapshot,
    TaskSnapshot,
)


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
            ("generator", "Last generator feedback: Unsupported priority: 'none'", 3),
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
            {"critic-options", "graph-canvas", "outputs-options", "run-tab"},
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

    def test_layout_uses_critic_options_and_no_approval_controls(self):
        layout = str(create_layout())
        self.assertIn("critic-options", layout)
        self.assertIn("labeling-toggle", layout)
        self.assertIn("embeddings-toggle", layout)
        self.assertNotIn("approve-button", layout)
        self.assertNotIn("decline-button", layout)
        self.assertEqual(
            {state.value for state in RunState},
            {"idle", "running", "completed", "failed"},
        )

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
        self.assertEqual(data["style"], CYTOSCAPE_STYLESHEET)
        self.assertNotIn("rm-hover", json.dumps(data["elements"]))

        assets = Path(__file__).parents[1] / "app" / "assets"
        self.assertIn((assets / "rm_graph.js").read_text(encoding="utf-8"), page)
        self.assertIn((assets / "rm_graph.css").read_text(encoding="utf-8"), page)

    def test_poll_locks_inputs_and_critics_while_running_and_keeps_results(self):
        controller = RunController(generate_rm)
        app = create_app(controller)
        key = next(key for key in app.callback_map if "critic-options.options" in key)
        poll = app.callback_map[key]["callback"].__wrapped__
        idle = poll(0, None, [{"index": 0}])
        self.assertFalse(idle[10][0]["disabled"])
        controller._status = RunState.RUNNING
        active = poll(0, None, [{"index": 0}])
        self.assertTrue(active[3])
        self.assertTrue(all(item["disabled"] for item in active[10]))
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
        self.assertIn("out.rm", summary)
        self.assertIn("Warning: Rule-only task", summary)
        self.assertIn("Bundle: out-bundle", summary)
        self.assertIn("Embedding: nomic-embed-text dim=2", summary)
        self.assertIn("Embeddings: out-embeddings", summary)
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
            self.assertEqual(tab.style["backgroundColor"], "#101a2b")
            self.assertEqual(tab.selected_style["backgroundColor"], "#17243a")

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
        self.assertEqual(snapshot.tasks[0].retry_note, "bad proposal")
        self.assertEqual(snapshot.tasks[0].state, StepState.RUNNING)
        self.assertIn("Task 1 of 1", str(render_steps(snapshot.tasks)))


if __name__ == "__main__":
    unittest.main()
