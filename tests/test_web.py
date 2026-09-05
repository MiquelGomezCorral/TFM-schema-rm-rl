import re
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.web.components import create_layout, render_steps
from src.web.runner import RunController, RunState, StepSnapshot, TaskSnapshot
from scripts.generate_rm import PipelineStep, ProgressEvent, StepState
from src.compiler.reward_machine import RewardMachineStructure


class WebTests(unittest.TestCase):
    def test_component_and_css_classes_stay_in_sync(self):
        root = Path(__file__).parents[1]
        tailwind_source = (root / "app/src/web/tailwind.css").read_text()
        custom_stylesheet = (root / "app/assets/app.css").read_text()
        compiled_stylesheet = (root / "app/assets/00-tailwind.css").read_text()

        self.assertNotIn("@apply", tailwind_source)
        self.assertNotIn("@layer components", tailwind_source)
        self.assertIn(".flex{", compiled_stylesheet)
        self.assertLess(len(custom_stylesheet), 6_000)

        custom_classes = set(
            re.findall(r"(?<![\w-])\.([a-zA-Z_][\w-]*)", custom_stylesheet)
        )
        self.assertEqual(
            {name for name in custom_classes if not name.startswith("dash-")},
            {"critic-options", "graph-canvas"},
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
        self.assertNotIn("approve-button", layout)
        self.assertNotIn("decline-button", layout)
        self.assertEqual({state.value for state in RunState}, {"idle", "running", "completed", "failed"})

    def test_poll_locks_inputs_and_critics_while_running_and_keeps_results(self):
        from src.web.application import create_app
        app = create_app()
        controller = app._run_controller
        key = next(key for key in app.callback_map if "critic-options.options" in key)
        poll = app.callback_map[key]["callback"].__wrapped__
        idle = poll(0, None, [{"index": 0}])
        self.assertFalse(idle[10][0]["disabled"])
        controller._status = RunState.RUNNING
        active = poll(0, None, [{"index": 0}])
        self.assertTrue(active[3])
        self.assertTrue(all(item["disabled"] for item in active[10]))
        controller._status = RunState.COMPLETED
        controller._results = (SimpleNamespace(
            proposal=SimpleNamespace(task="finish"), text="rm",
            reward_machine=RewardMachineStructure((0,), 0, 0, (), ()),
        ),)
        controller._output_paths = (Path("out.rm"),)
        result_key = next(key for key in app.callback_map if "result-summary.children" in key)
        render = app.callback_map[result_key]["callback"].__wrapped__
        summary, text, elements = render(0)
        self.assertIn("out.rm", summary)
        self.assertEqual(text, "rm")
        self.assertTrue(elements)

    def test_optional_navigation_inputs_and_dark_tab_styles(self):
        from src.web.application import create_app

        app = create_app()
        key = next(key for key in app.callback_map if "critic-options.options" in key)
        optional_inputs = {
            item.component_id: item.allow_optional
            for item in app.callback_map[key]["raw_inputs"]
            if isinstance(item.component_id, str)
            and item.component_id in {"run-prev", "run-next"}
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
        controller = RunController()
        controller._tasks = (
            TaskSnapshot(
                0,
                "finish",
                steps=tuple(StepSnapshot(step) for step in controller_steps()),
            ),
        )
        controller._record_event(ProgressEvent(0, 1, PipelineStep.GENERATE, StepState.RUNNING))
        controller._record_event(ProgressEvent(0, 1, PipelineStep.GENERATE, StepState.FAILED, 0.2, "bad proposal"))
        controller._record_event(ProgressEvent(0, 2, PipelineStep.GENERATE, StepState.RUNNING))
        snapshot = controller.snapshot()
        self.assertEqual(snapshot.tasks[0].attempt, 2)
        self.assertEqual(snapshot.tasks[0].retry_note, "bad proposal")
        self.assertEqual(snapshot.tasks[0].state, StepState.RUNNING)
        self.assertIn("Task 1 of 1", str(render_steps(snapshot.tasks)))


def controller_steps():
    return (
        PipelineStep.GENERATE,
        PipelineStep.TASK_CRITIC,
        PipelineStep.LTLF,
        PipelineStep.DFA,
        PipelineStep.REWARD_MACHINE,
        PipelineStep.RM_CRITIC,
    )


if __name__ == "__main__":
    unittest.main()
