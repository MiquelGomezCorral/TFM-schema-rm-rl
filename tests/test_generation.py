import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock, patch

from httpx import Request, Response
from openai import BadRequestError

from scripts import generate_rm
from src.arm_fm import record_bundle_role_models
from src.config import Configuration
from src.engines import AntigravityEngine, GenericEngine, RunCancelled
from src.models import EnvironmentDescription
from src.utils import (
    GenerationHooks,
    PipelineStep,
    Progress,
    ProgressEvent,
    StepState,
    get_engine,
    setup_environment_and_engines,
)


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.log_directory = TemporaryDirectory()
        self.addCleanup(self.log_directory.cleanup)
        self.logs_patch = patch.object(Configuration, "LOGS_PATH", Path(self.log_directory.name))
        self.addCleanup(self.logs_patch.stop)
        self.logs_patch.start()

    def test_bundle_records_critic_validation_only_when_a_critic_ran(self):
        for critic in (True, False):
            manifest = SimpleNamespace(validation={"structural": True}, effective_settings={})
            record_bundle_role_models(
                SimpleNamespace(manifest=manifest), Configuration(critic=critic)
            )
            self.assertEqual(manifest.validation.get("critic"), True if critic else None)

    def test_only_code_writing_steps_load_the_code_file(self):
        facts = "# Demo\n## Propositions\n- `done`: Finished\n"
        code = "# Demo: code notes\n\n## Labeling API\n\n- `env.grid.get(x, y)`: a cell\n"
        with TemporaryDirectory() as directory:
            path = Path(directory) / "environment.md"
            path.write_text(facts, encoding="utf-8")
            alone = EnvironmentDescription.from_file(path, code=True)
            self.assertEqual(alone.markdown, facts)
            self.assertIsNone(alone.labeling_api)
            Path(directory, "environment-code.md").write_text(code, encoding="utf-8")
            joined = EnvironmentDescription.from_file(path, code=True)
            self.assertEqual(joined.markdown, f"{facts}\n\n{code}")
            self.assertEqual(joined.require_labeling_api(), "- `env.grid.get(x, y)`: a cell")
            self.assertEqual(joined.proposition_ids, ("done",))
            self.assertEqual(EnvironmentDescription.from_file(path).markdown, facts)

            CONFIG = Configuration(
                environment=path, generator_model="generator", critic_model="critic"
            )
            with patch("src.utils.generation.get_engine", return_value=object()) as engines:
                loaded, _generator, _critic = setup_environment_and_engines(
                    CONFIG, Progress(GenerationHooks())
                )
            self.assertEqual(loaded.markdown, facts)
            self.assertEqual([call.args[1] for call in engines.call_args_list], [loaded, loaded])

    def test_embeddings_configuration_defaults_and_validation(self):
        CONFIG = Configuration(embeddings=True)
        self.assertEqual(CONFIG.EMBEDDINGS_PATH, Path(CONFIG.MODELS_PATH) / "state_embeddings")
        self.assertEqual(CONFIG.embedding_endpoint, "http://127.0.0.1:8934/v1/embeddings")
        self.assertFalse(CONFIG.embedding_context)
        with self.assertRaisesRegex(ValueError, "http"):
            Configuration(embeddings=True, embedding_endpoint="127.0.0.1:8934")
        with self.assertRaisesRegex(ValueError, "timeout"):
            Configuration(embeddings=True, embedding_timeout=0)
        self.assertEqual(Configuration().embedding_timeout, 30.0)

    def test_antigravity_configuration_selects_antigravity_engine(self):
        environment = EnvironmentDescription.from_markdown(
            "# Demo\n## Propositions\n- `done`: Finished",
            source="demo.md",
        )
        with patch.dict(
            os.environ,
            {"LLM_PROVIDER": "antigravity", "ANTIGRAVITY_MODEL": "gemini-model"},
            clear=True,
        ):
            CONFIG = Configuration()
        self.assertEqual(CONFIG.llm_provider, "antigravity")
        self.assertEqual(CONFIG.model, "gemini-model")
        self.assertIsInstance(get_engine(CONFIG, environment), AntigravityEngine)

    def test_role_model_precedence_and_baseline_isolation(self):
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "opencode",
                "OPENCODE_MODEL": "provider-model",
                "OPENCODE_MODEL_GENERATOR": "role-generator",
                "OPENCODE_MODEL_CRITIC": "role-critic",
            },
            clear=True,
        ):
            CONFIG = Configuration()
        self.assertEqual(CONFIG.model, "provider-model")
        self.assertEqual(CONFIG.generator_model, "role-generator")
        self.assertEqual(CONFIG.critic_model, "role-critic")

        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "opencode",
                "OPENCODE_MODEL": "provider-model",
                "OPENCODE_MODEL_GENERATOR": "role-generator",
            },
            clear=True,
        ):
            CONFIG = Configuration(model="explicit-model")
        self.assertEqual(CONFIG.model, "explicit-model")
        self.assertEqual(CONFIG.generator_model, "explicit-model")
        self.assertIsNone(CONFIG.critic_model)

        with patch.dict(
            os.environ,
            {"LLM_PROVIDER": "opencode", "OPENCODE_MODEL": "provider-model"},
            clear=True,
        ):
            CONFIG = Configuration(model="explicit-model", generator_model="explicit-generator")
        self.assertEqual(CONFIG.model, "explicit-model")
        self.assertEqual(CONFIG.generator_model, "explicit-generator")

        with patch.dict(
            os.environ,
            {"LLM_PROVIDER": "opencode", "OPENCODE_MODEL": "provider-model"},
            clear=True,
        ):
            CONFIG = Configuration()
        self.assertEqual(CONFIG.model, "provider-model")
        self.assertEqual(CONFIG.generator_model, "provider-model")
        self.assertIsNone(CONFIG.critic_model)

    def test_engine_factory_model_override_keeps_baseline_default(self):
        environment = EnvironmentDescription.from_markdown(
            "# Demo\n## Propositions\n- `done`: Finished",
            source="demo.md",
        )
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "opencode",
                "OPENCODE_MODEL": "baseline-model",
                "OPENCODE_API_KEY": "test",
            },
            clear=True,
        ):
            CONFIG = Configuration()
            baseline_engine = get_engine(CONFIG, environment)
            override_engine = get_engine(CONFIG, environment, "override-model")
        self.assertEqual(baseline_engine.model, "baseline-model")
        self.assertEqual(override_engine.model, "override-model")

    def test_progress_has_total_and_step_once(self):
        messages = []
        with patch(
            "src.utils.generation_logging.time.monotonic",
            side_effect=[10.0, 11.234, 12.5],
        ):
            progress = Progress(GenerationHooks(progress=messages.append))
            self.assertEqual(progress("first"), "[total 1.234s | step 1.234s] first")
            self.assertEqual(progress("second"), "[total 2.500s | step 1.266s] second")
        self.assertEqual(messages[0].count("[total"), 1)

    def test_progress_writes_plain_text_run_log_and_events(self):
        messages = []
        events = []
        with TemporaryDirectory() as directory:
            progress = Progress(
                GenerationHooks(progress=messages.append, event=events.append),
                Path(directory),
            )
            progress(progress.log_path.as_posix())
            progress.begin_attempt(0, 1, 3)
            progress.start(PipelineStep.GENERATE)
            progress.artifact("Proposal", '{\n  "clauses": []\n}')
            progress.complete()
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

    def test_progress_start_raises_once_the_client_stopped_the_run(self):
        stopped = Event()
        progress = Progress(GenerationHooks(cancelled=stopped.is_set))
        progress.begin_attempt(0, 1, 3)
        stopped.set()
        with self.assertRaises(RunCancelled):
            progress.start(PipelineStep.GENERATE)
        with self.assertRaises(RunCancelled):
            progress.begin_attempt(0, 1, 3)

    def test_provider_retry_loop_stops_when_the_run_is_stopped(self):
        response = Response(400, request=Request("POST", "https://provider.test/v1"))
        failure = BadRequestError("Error code: 400", response=response, body=None)
        engine = GenericEngine(
            EnvironmentDescription.from_markdown(
                "# Demo\n## Propositions\n- `done`: Finished", source="demo.md"
            ),
            "test-model",
            "Test",
            lambda *args: "",
            Mock(side_effect=failure),
        )
        engine.should_stop = lambda: True
        with (
            patch("src.engines.generic_engine.sleep") as sleep,
            self.assertRaises(RunCancelled),
        ):
            engine.request_text("system", "user")
        self.assertEqual(sleep.call_count, 0)

    def test_generate_rm_closes_handlers_if_run_started_raises(self):
        progress_instances = []

        class TrackingProgress(Progress):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                progress_instances.append(self)

        def fail_on_start(_log_path):
            raise RuntimeError("start hook failed")

        CONFIG = Configuration(environment="demo.md", tasks=["finish"], output="out.rm")
        with (
            patch("scripts.generate_rm.Progress", TrackingProgress),
            self.assertRaises(RuntimeError),
        ):
            generate_rm(CONFIG, GenerationHooks(run_started=fail_on_start))

        self.assertEqual(len(progress_instances), 1)
        self.assertIsNone(progress_instances[0]._logger)


if __name__ == "__main__":
    unittest.main()
