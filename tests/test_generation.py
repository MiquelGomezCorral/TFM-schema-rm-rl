import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts.generate_rm import (
    GenerationHooks,
    PipelineStep,
    ProgressEvent,
    StepState,
    _Progress,
    generate_rm,
)
from src.config import Configuration


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.log_directory = TemporaryDirectory()
        self.addCleanup(self.log_directory.cleanup)
        self.logs_patch = patch.object(
            Configuration, "LOGS_PATH", Path(self.log_directory.name)
        )
        self.addCleanup(self.logs_patch.stop)
        self.logs_patch.start()

    def test_both_critics_cannot_be_disabled(self):
        with self.assertRaises(ValueError):
            Configuration(task_critic=False, rm_critic=False)

    def test_progress_has_total_and_step_once(self):
        messages = []
        with patch("scripts.generate_rm.time.monotonic", side_effect=[10.0, 11.234, 12.5]):
            progress = _Progress(GenerationHooks(progress=messages.append))
            self.assertEqual(progress("first"), "[total 1.234s | step 1.234s] first")
            self.assertEqual(progress("second"), "[total 2.500s | step 1.266s] second")
        self.assertEqual(messages[0].count("[total"), 1)

    def test_progress_writes_plain_text_run_log_and_events(self):
        messages = []
        events = []
        with TemporaryDirectory() as directory:
            progress = _Progress(
                GenerationHooks(progress=messages.append, event=events.append),
                Path(directory),
            )
            progress(progress.log_path.as_posix())
            started = progress.stage_start(0, 1, PipelineStep.GENERATE, "Generating")
            progress.artifact("Proposal", "{\n  \"clauses\": []\n}")
            progress.stage_end(0, 1, PipelineStep.GENERATE, started)
            log_path = progress.log_path
            progress.close()

            text = log_path.read_text(encoding="utf-8")
            self.assertEqual(text, "\n".join(messages) + "\n")
            self.assertIn('Proposal:\n{\n  "clauses": []\n}', text)
            self.assertEqual(
                [(event.step, event.state) for event in events],
                [
                    (PipelineStep.GENERATE, StepState.RUNNING),
                    (PipelineStep.GENERATE, StepState.COMPLETED),
                ],
            )
            self.assertIsNone(progress._logger)

    def test_progress_event_is_immutable(self):
        event = ProgressEvent(0, 1, PipelineStep.DFA, StepState.COMPLETED, 0.2)
        with self.assertRaises(AttributeError):
            event.state = StepState.FAILED

    def test_generate_rm_closes_handlers_if_run_started_raises(self):
        progress_instances = []

        class TrackingProgress(_Progress):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                progress_instances.append(self)

        def fail_on_start(_log_path):
            raise RuntimeError("start hook failed")

        config = Configuration(environment="demo.md", tasks=["finish"], output="out.rm")
        with patch("scripts.generate_rm._Progress", TrackingProgress):
            with self.assertRaises(RuntimeError):
                generate_rm(config, GenerationHooks(run_started=fail_on_start))

        self.assertEqual(len(progress_instances), 1)
        self.assertIsNone(progress_instances[0]._logger)


if __name__ == "__main__":
    unittest.main()
