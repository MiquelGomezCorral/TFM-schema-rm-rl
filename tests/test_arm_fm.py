import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import gymnasium as gym

from src.arm_fm import (
    ArtifactBundle,
    BundleManifest,
    BundleValidationError,
    EmbeddingCache,
    EmbeddingSettings,
    JudgeDecision,
    RewardMachineEnvironment,
    RewardMachineRuntime,
    adapt_compilation_result,
    aggregate_judgments,
    embed_descriptions_over_http,
    frozen_evaluate,
    generate_baseline_bundle,
    generate_compiler_bundle,
    judge_bundle,
    load_labeling_functions,
    load_task_manifest,
    resolve_embedding_settings,
)
from src.arm_fm.generation import StageAttempt, build_compiler_bundle
from src.compiler import (
    PaperRewardMachine,
    RuntimeTransition,
    RuntimeValidationError,
    parse_paper_reward_machine,
    serialize_paper_reward_machine,
)
from src.config import Configuration
from src.models import EnvironmentDescription


class _EmbeddingResponse:
    """Minimal context manager standing in for one live HTTP embedding response."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_EmbeddingResponse":
        return self

    def __exit__(self, *_args: object) -> bool:
        return False


def _embedding_response(vector: list[float], model: str) -> bytes:
    return json.dumps({"data": [{"index": 0, "embedding": vector}], "model": model}).encode("utf-8")


def _embedding_config(timeout: float = 30.0) -> Configuration:
    return Configuration(
        embedding_endpoint="http://127.0.0.1:1/v1/embeddings", embedding_timeout=timeout
    )


def machine(*transitions, propositions=("has_key", "lost_key")):
    return PaperRewardMachine(
        states=("u0", "u1", "u2"),
        initial_state="u0",
        propositions=propositions,
        transitions=tuple(transitions),
        final_states=("u2",),
    )


class ArmFMRuntimeTests(unittest.TestCase):
    def test_minigrid_labeling_uses_unwrapped_state_fields(self):
        environment = gym.make("MiniGrid-DoorKey-8x8-v0")
        environment.reset(seed=42)
        reward_machine = PaperRewardMachine(
            ("u0", "u1"),
            "u0",
            (RuntimeTransition("u0", "snapshot", "u1"),),
            ("u1",),
            ("snapshot",),
        )
        labeling = load_labeling_functions(
            "def snapshot(env):\n"
            "    return env.grid is not None and env.agent_pos is not None and env.carrying is None\n",
            ("snapshot",),
        )

        runtime = RewardMachineRuntime(reward_machine)
        runtime.step(runtime.evaluate_labeling(environment, labeling))
        self.assertEqual(runtime.state, "u1")

    def test_labeling_snapshot_is_shared_read_only_and_updated_after_success(self):
        rm = PaperRewardMachine(("u0",), "u0", (), (), ("current", "event"))
        runtime = RewardMachineRuntime(rm)
        snapshots = []
        labeling = {
            "current": lambda env: (
                snapshots.append(env.episode_memory["previous_valuation"]) or len(range(2)) == 2
            ),
            "event": lambda env: (
                snapshots.append(env.episode_memory["previous_valuation"])
                or not env.episode_memory["previous_valuation"].get("current", False)
            ),
        }
        runtime.step(runtime.evaluate_labeling(SimpleNamespace(), labeling))
        self.assertIs(snapshots[0], snapshots[1])
        self.assertEqual(
            runtime.episode_memory["previous_valuation"],
            {"current": True, "event": True},
        )
        with self.assertRaises(TypeError):
            snapshots[0]["current"] = False
        runtime.reset()
        self.assertEqual(runtime.episode_memory, {})

    def test_labeling_failure_does_not_replace_previous_valuation(self):
        rm = PaperRewardMachine(("u0",), "u0", (), (), ("value",))
        runtime = RewardMachineRuntime(rm)
        runtime.episode_memory["previous_valuation"] = {"value": True}
        with self.assertRaises(RuntimeError):
            runtime.step(
                runtime.evaluate_labeling(
                    SimpleNamespace(),
                    {"value": lambda env: (_ for _ in ()).throw(RuntimeError("bad"))},
                )
            )
        self.assertEqual(runtime.episode_memory["previous_valuation"], {"value": True})

    def test_labeling_source_is_read_only_and_non_reflective(self):
        safe = load_labeling_functions("def done(env):\n    return env.done\n", ("done",))
        self.assertTrue(safe["done"](SimpleNamespace(done=True)))
        unsafe_sources = (
            "def done(env):\n    env.done = True\n    return True\n",
            "def done(env):\n    return env._done\n",
            "def done(env):\n    return getattr(env, 'done')\n",
            "import os\ndef done(env):\n    return True\n",
            "def done(env):\n    return open('unsafe')\n",
        )
        for source in unsafe_sources:
            with self.subTest(source=source), self.assertRaises(RuntimeValidationError):
                load_labeling_functions(source, ("done",))

    def test_labeling_allows_env_derived_public_fields_only(self):
        load_labeling_functions(
            "def found(env):\n"
            "    return any(cell.type == 'door' for x in range(env.width)\n"
            "               for cell in [env.grid.get(x, 0)])\n",
            ("found",),
        )
        public = load_labeling_functions(
            "def done(env):\n    return env.public().value\n", ("done",)
        )
        self.assertTrue(public["done"](SimpleNamespace(public=lambda: SimpleNamespace(value=True))))
        for source in (
            "def done(env):\n    return (1).real\n",
            "def done(env):\n    return env.grid.get(0, 0)._type\n",
            "def done(env):\n    return env.episode_memory['previous_valuation'].get('done', False)\n",
        ):
            with self.subTest(source=source), self.assertRaises(RuntimeValidationError):
                load_labeling_functions(source, ("done",))

    def test_labeling_allows_fresh_locals_but_not_state_writes(self):
        load_labeling_functions(
            "def found(env):\n"
            "    cell = env.grid.get(0, 0)\n"
            "    x, y = env.agent_pos\n"
            "    return cell is not None and x >= 0 and y >= 0\n",
            ("found",),
        )
        unsafe_sources = (
            "def done(env):\n    env = 1\n    return True\n",
            "def done(env):\n    previous_valuation = {}\n    return True\n",
            "def done(env):\n    env.done = True\n    return True\n",
            "def done(env):\n    env.episode_memory['previous_valuation'] = {}\n    return True\n",
        )
        for source in unsafe_sources:
            with self.subTest(source=source), self.assertRaises(RuntimeValidationError):
                load_labeling_functions(source, ("done",))

    def test_complete_valuation_and_one_update(self):
        rm = machine(
            RuntimeTransition("u0", "has_key", "u1", 0.2),
            RuntimeTransition("u0", "else", "u0"),
            RuntimeTransition("u1", "lost_key", "u0", -0.2),
            RuntimeTransition("u1", "else", "u1"),
        )
        runtime = RewardMachineRuntime(rm)
        result = runtime.step({"has_key": True, "lost_key": False, "irrelevant": True})
        self.assertEqual((result.destination, result.reward), ("u1", 0.2))
        result = runtime.step({"has_key": False, "lost_key": False})
        self.assertEqual((result.destination, result.reward), ("u1", 0.0))
        runtime.reset()
        self.assertEqual(runtime.state, "u0")
        self.assertEqual(runtime.episode_memory, {})

    def test_overlap_selects_first_stored_transition_and_warns(self):
        warnings = []
        rm = machine(
            RuntimeTransition("u0", "has_key", "u1", 1),
            RuntimeTransition("u0", "has_key | lost_key", "u2", 2),
        )
        runtime = RewardMachineRuntime(rm, warning_handler=warnings.append)
        result = runtime.step({"has_key": True, "lost_key": False})
        self.assertEqual(result.destination, "u1")
        self.assertEqual(len(warnings), 1)

    def test_paper_round_trip_keeps_zero_reward_state_changes(self):
        text = """REWARD_MACHINE:
STATES: u0, u1
INITIAL_STATE: u0
FINAL_STATES: u1
TRANSITION_FUNCTION:
(u0, event) -> u1
(u0, else) -> u0
REWARD_FUNCTION:
"""
        machine = parse_paper_reward_machine(text)
        self.assertEqual(machine.transitions[0].reward, 0)
        self.assertEqual(
            parse_paper_reward_machine(serialize_paper_reward_machine(machine)), machine
        )

    def test_compiler_paper_round_trip_declares_zero_default(self):
        machine = PaperRewardMachine(
            ("u0", "u1"),
            "u0",
            (RuntimeTransition("u0", "done", "u1"),),
            ("u1",),
            ("done",),
            0.0,
        )
        text = serialize_paper_reward_machine(machine)
        self.assertIn("DEFAULT_REWARD: 0", text)
        self.assertEqual(parse_paper_reward_machine(text), machine)

    def test_baseline_parser_requires_explicit_finals_when_requested(self):
        text = """REWARD_MACHINE:
STATES: u0, u1
INITIAL_STATE: u0
TRANSITION_FUNCTION:
(u0, done) -> u1
REWARD_FUNCTION:
"""
        with self.assertRaises(RuntimeValidationError):
            parse_paper_reward_machine(text, require_final_states=True)

    def test_reward_referencing_missing_transition_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_paper_reward_machine(
                """REWARD_MACHINE:
STATES: u0, u1
INITIAL_STATE: u0
TRANSITION_FUNCTION:
(u0, else) -> u0
REWARD_FUNCTION:
(u0, event, u1) -> 1
"""
            )


class ArmFMArtifactTests(unittest.TestCase):
    def setUp(self):
        self.rm = PaperRewardMachine(
            ("u0", "u1"),
            "u0",
            (RuntimeTransition("u0", "done", "u1", 1),),
            ("u1",),
            ("done",),
        )
        self.manifest = BundleManifest(
            "finish",
            "demo/environment.md",
            {"done": "finished"},
            stage_status={
                "reward_machine": "complete",
                "labeling": "complete",
                "descriptions": "complete",
                "embeddings": "complete",
                "validation": "complete",
            },
        )

    def test_incomplete_bundle_is_visible(self):
        bundle = ArtifactBundle(
            self.manifest,
            self.rm,
            "def done(env):\n    return True\n",
            {"u0": "start", "u1": "done"},
        )
        self.assertFalse(bundle.complete)
        with self.assertRaises(BundleValidationError):
            bundle.validate(require_complete=True)

    def test_bundle_round_trip(self):
        bundle = ArtifactBundle(
            self.manifest,
            self.rm,
            "def done(env):\n    return True\n",
            {"u0": "start", "u1": "done"},
            {"u0": [0.0, 1.0], "u1": [1.0, 0.0]},
        )
        with tempfile.TemporaryDirectory() as directory:
            bundle.save(directory)
            loaded = ArtifactBundle.load(directory)
        self.assertEqual(loaded.reward_machine, self.rm)
        self.assertEqual(loaded.embeddings["u1"], [1.0, 0.0])

    def test_compiler_adaptation_keeps_zero_reward_edge(self):
        compiled = SimpleNamespace(
            environment=SimpleNamespace(
                source=Path("demo.md"),
                proposition_ids=("done",),
                propositions=(SimpleNamespace(identifier="done", description="finished"),),
            ),
            proposal=SimpleNamespace(task="finish"),
            text="numeric",
            reward_machine=SimpleNamespace(
                states=(0, 1),
                initial_state=0,
                final_state=1,
                transitions=(
                    SimpleNamespace(source=0, destination=1, condition=("done",), reward=0.0),
                ),
            ),
        )
        bundle = adapt_compilation_result(compiled)
        self.assertEqual(bundle.reward_machine.states, ("u0", "u1"))
        self.assertEqual(bundle.reward_machine.initial_state, "u0")
        self.assertEqual(bundle.reward_machine.final_states, ("u1",))
        self.assertEqual(bundle.reward_machine.default_reward, 0.0)
        self.assertEqual(bundle.reward_machine.transitions[0].reward, 0.0)

    def test_baseline_refinement_records_each_stage(self):
        environment = EnvironmentDescription.from_markdown(
            "# Demo\n## Propositions\n- `done`: Finished", source="demo.md"
        )
        responses = iter(
            [
                """```plaintext
REWARD_MACHINE:
STATES: u0, u1
INITIAL_STATE: u0
FINAL_STATES: u1
TRANSITION_FUNCTION:
(u0, done) -> u1
(u0, else) -> u0
(u1, else) -> u1
REWARD_FUNCTION:
(u0, done, u1) -> 1
```""",
                '{"accepted":true,"feedback":"ok"}',
                "```python\ndef done(env):\n    return True\n```",
                '{"accepted":true,"feedback":"ok"}',
                '{"u0":"start","u1":"finished"}',
            ]
        )
        engine = SimpleNamespace(request_text=lambda system, user: next(responses))
        result = generate_baseline_bundle("finish", environment, engine, Configuration())
        self.assertEqual(
            [item.stage for item in result.attempts],
            ["reward_machine", "labeling", "descriptions"],
        )
        self.assertEqual(len(result.bundle.raw_responses), 3)
        self.assertTrue(result.bundle.manifest.generation["first_attempt"])
        self.assertFalse(result.bundle.manifest.generation["refined"])

    def test_compiler_failure_persists_accepted_rm(self):
        environment = EnvironmentDescription.from_markdown(
            "# Demo\n## Propositions\n- `done`: Finished", source="demo.md"
        )
        compiled = SimpleNamespace(
            environment=SimpleNamespace(
                source=Path("demo.md"),
                markdown=environment.markdown,
                proposition_ids=("done",),
                propositions=(SimpleNamespace(identifier="done", description="finished"),),
            ),
            proposal=SimpleNamespace(task="finish"),
            text="numeric",
            state_descriptions=(),
            labeling_source="",
            labeling_attempts=(),
            reward_machine=SimpleNamespace(
                states=(0, 1),
                initial_state=0,
                final_state=1,
                transitions=(
                    SimpleNamespace(source=0, destination=1, condition=("done",), reward=1.0),
                ),
            ),
        )
        engine = SimpleNamespace(
            request_text=lambda system, user: (_ for _ in ()).throw(RuntimeError("down"))
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RuntimeError):
                generate_compiler_bundle((compiled,), engine, Configuration(bundle=directory))
            loaded = ArtifactBundle.load(directory)
        self.assertIsNotNone(loaded.reward_machine)
        self.assertEqual(loaded.manifest.stage_status["reward_machine"], "complete")
        self.assertEqual(loaded.manifest.stage_status["labeling"], "failed")
        self.assertTrue(loaded.manifest.errors)

    @staticmethod
    def _compiler_result(**overrides):
        """Minimal accepted compiler result shared by compiler-bundle checks."""
        values = {
            "environment": SimpleNamespace(
                source=Path("demo.md"),
                markdown="# Demo\n## Propositions\n- `done`: Finished",
                proposition_ids=("done",),
                propositions=(SimpleNamespace(identifier="done", description="finished"),),
            ),
            "proposal": SimpleNamespace(task="finish"),
            "text": "numeric",
            "state_descriptions": ("start", "finished"),
            "labeling_source": "def done(env):\n    return True\n",
            "labeling_attempts": (
                {
                    "stage": "labeling",
                    "attempt": 1,
                    "status": "accepted",
                    "candidate": "def done(env):\n    return True\n",
                    "feedback": "",
                    "error": "",
                    "raw_response": "",
                },
            ),
            "reward_machine": SimpleNamespace(
                states=(0, 1),
                initial_state=0,
                final_state=1,
                transitions=(
                    SimpleNamespace(source=0, destination=1, condition=("done",), reward=1.0),
                ),
            ),
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_compiler_bundle_reuses_accepted_labeling_and_descriptions(self):
        compiled = self._compiler_result(
            embeddings={"u0": [1.0, 0.0], "u1": [0.0, 1.0]},
            embedding_settings={"model": "nomic-embed-text", "dimension": 2},
        )
        api_description = "env.grid.get(x, y), env.agent_pos"
        bundle = generate_compiler_bundle(
            (compiled,), None, Configuration(), api_description=api_description
        )[0]
        self.assertEqual(bundle.labeling_source, compiled.labeling_source)
        self.assertEqual(bundle.state_descriptions, {"u0": "start", "u1": "finished"})
        self.assertEqual(bundle.manifest.stage_status["labeling"], "complete")
        self.assertEqual(bundle.manifest.stage_status["descriptions"], "complete")
        self.assertEqual(bundle.embeddings, compiled.embeddings)
        self.assertEqual(bundle.manifest.stage_status["embeddings"], "complete")
        self.assertEqual(
            bundle.manifest.effective_settings["embedding"], compiled.embedding_settings
        )
        self.assertEqual(bundle.validate(require_complete=True), [])
        self.assertEqual([item["stage"] for item in bundle.attempts], ["compiler", "labeling"])
        self.assertEqual(bundle.manifest.api_definitions["labeling"], api_description)
        self.assertEqual(bundle.manifest.generation["labeling_api"], api_description)
        self.assertTrue(bundle.manifest.generation["first_attempt"])
        self.assertEqual(bundle.manifest.generation["attempt_classification"], "first_attempt")

    def test_compiler_bundle_requires_engine_for_missing_fields(self):
        compiled = self._compiler_result(
            state_descriptions=(),
            labeling_source="",
            labeling_attempts=(),
        )
        with self.assertRaisesRegex(RuntimeError, "no engine was supplied"):
            generate_compiler_bundle((compiled,), None, Configuration())

    def test_stage_status_rejects_complete_for_rejected_attempts(self):
        compiled = self._compiler_result()
        bundle = build_compiler_bundle(
            compiled,
            api_description="env.grid.get(x, y)",
            labeling_source=compiled.labeling_source,
            state_descriptions={"u0": "start", "u1": "finished"},
            attempts=(StageAttempt("labeling", 1, "rejected", compiled.labeling_source),),
        )
        self.assertEqual(bundle.manifest.stage_status["labeling"], "failed")

    def test_failed_generation_persists_inspectable_bundle(self):
        environment = EnvironmentDescription.from_markdown(
            "# Demo\n## Propositions\n- `done`: Finished", source="demo.md"
        )
        engine = SimpleNamespace(
            model="mock-model",
            provider_name="mock",
            request_text=lambda system, user: (_ for _ in ()).throw(RuntimeError("provider down")),
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RuntimeError):
                generate_baseline_bundle(
                    "finish", environment, engine, Configuration(bundle=directory)
                )
            loaded = ArtifactBundle.load(directory)
            self.assertIsNone(loaded.reward_machine)
            self.assertTrue(loaded.attempts)
            self.assertEqual(loaded.manifest.errors, ["provider down"] * 3)

    def test_failed_generation_respects_bundle_overwrite(self):
        environment = EnvironmentDescription.from_markdown(
            "# Demo\n## Propositions\n- `done`: Finished", source="demo.md"
        )
        engine = SimpleNamespace(
            model="mock-model",
            provider_name="mock",
            request_text=lambda system, user: (_ for _ in ()).throw(RuntimeError("new failure")),
        )
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            (bundle / "manifest.json").write_text('{"sentinel": true}\n', encoding="utf-8")
            with self.assertRaises(RuntimeError):
                generate_baseline_bundle(
                    "finish",
                    environment,
                    engine,
                    Configuration(bundle=bundle, overwrite=False),
                )
            self.assertEqual(
                (bundle / "manifest.json").read_text(encoding="utf-8"),
                '{"sentinel": true}\n',
            )
            with self.assertRaises(RuntimeError):
                generate_baseline_bundle(
                    "finish",
                    environment,
                    engine,
                    Configuration(bundle=bundle, overwrite=True),
                )
            self.assertIn("new failure", (bundle / "manifest.json").read_text(encoding="utf-8"))

    def test_direct_labeling_full_valuation_and_environment_step(self):
        bundle = ArtifactBundle(
            self.manifest,
            self.rm,
            "def done(env):\n    return True\n",
            {"u0": "start", "u1": "done"},
            {"u0": [0.0], "u1": [1.0], "u2": [2.0]},
        )
        bundle.reward_machine = PaperRewardMachine(
            ("u0", "u1"),
            "u0",
            (RuntimeTransition("u0", "done", "u1", 1),),
            ("u1",),
            ("done",),
        )
        bundle.state_descriptions = {"u0": "start", "u1": "done"}
        bundle.embeddings = {"u0": [0.0], "u1": [1.0]}

        class Environment:
            action_space = SimpleNamespace(n=2)

            def reset(self):
                self.done = False
                return {}, {}

            def step(self, action):
                self.done = True
                return {}, 0.0, False, True, {}

        wrapped = RewardMachineEnvironment(
            Environment(),
            RewardMachineRuntime(bundle.reward_machine),
            bundle.labeling_source,
        )
        wrapped.reset()
        _, reward, _, truncated, info = wrapped.step(0)
        self.assertEqual((reward, truncated, info["rm_state"]), (1.0, True, "u1"))
        self.assertEqual(set(info["valuation"]), {"done"})
        self.assertEqual(len(wrapped.execution_evidence), 1)

    def test_manifest_resolves_description_and_bundle_but_keeps_runtime_id_opaque(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "nested").mkdir()
            manifest = root / "nested" / "tasks.json"
            manifest.write_text(
                json.dumps(
                    {
                        "tasks": {
                            "task": {
                                "bundle": "../bundle",
                                "environment_description": "../environment.md",
                                "environment_id": "Craftium/custom/id",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            (root / "environment.md").write_text("# Demo", encoding="utf-8")
            entry = load_task_manifest(manifest)[0]
        self.assertEqual(entry.environment_id, "Craftium/custom/id")
        self.assertEqual(entry.environment_description, (root / "environment.md").resolve())
        self.assertEqual(entry.bundle, (root / "bundle").resolve())


class ArmFMEvaluationTests(unittest.TestCase):
    def test_embedding_provenance_requires_and_keeps_loaded_revisions(self):
        resolved = resolve_embedding_settings(
            SimpleNamespace(_commit_hash="model-revision"),
            SimpleNamespace(_commit_hash="tokenizer-revision"),
            EmbeddingSettings(),
        )
        self.assertEqual(resolved.model_revision, "model-revision")
        self.assertEqual(resolved.tokenizer_revision, "tokenizer-revision")
        with self.assertRaises(RuntimeError):
            resolve_embedding_settings(
                SimpleNamespace(name_or_path="org/model"),
                SimpleNamespace(name_or_path="org/tokenizer"),
                EmbeddingSettings(),
            )

    def test_cache_identity_includes_settings(self):
        cache = EmbeddingCache()
        first = EmbeddingSettings(model_revision="a")
        second = EmbeddingSettings(model_revision="b")
        cache.put("state", first, [1, 2])
        self.assertEqual(cache.get("state", first), [1, 2])
        self.assertIsNone(cache.get("state", second))

    def test_http_embedding_is_single_text_and_cached(self):
        settings = EmbeddingSettings(
            model="nomic-embed-text",
            model_revision="sha256:abc",
            tokenizer_revision="sha256:abc",
            extraction="server-mean-pooling-last-layer",
            device="remote",
        )
        requests: list[dict] = []

        def fake_urlopen(request, timeout=None):
            requests.append({"body": json.loads(request.data.decode()), "timeout": timeout})
            return _EmbeddingResponse(_embedding_response([3.0, 4.0], "nomic-embed-text"))

        cache = EmbeddingCache()
        with patch("src.arm_fm.evaluation.urlopen", side_effect=fake_urlopen):
            first = embed_descriptions_over_http(
                {"u0": "start"},
                _embedding_config(timeout=5.0),
                settings=settings,
                cache=cache,
            )
            second = embed_descriptions_over_http(
                {"u0": "start"},
                _embedding_config(timeout=5.0),
                settings=settings,
                cache=cache,
            )
        self.assertEqual(requests[0]["body"], {"input": "start", "model": "nomic-embed-text"})
        self.assertEqual(requests[0]["timeout"], 5.0)
        self.assertEqual(len(requests), 1)
        self.assertEqual(first, {"u0": [0.6, 0.8]})
        self.assertEqual(second, first)

    def test_http_embedding_rejects_bad_cached_per_served_vectors(self):
        settings = EmbeddingSettings(
            model="m",
            model_revision="r",
            tokenizer_revision="r",
            extraction="server-mean-pooling-last-layer",
            device="remote",
        )
        for bad, pattern in (
            ([0.0, 0.0], "zero vector"),
            ([True, 0.5], "only numbers"),
        ):
            cache = EmbeddingCache()
            cache.values[cache.key("text", settings)] = bad
            with (
                patch(
                    "src.arm_fm.evaluation.urlopen",
                    side_effect=AssertionError("no request"),
                ),
                self.assertRaisesRegex(RuntimeError, pattern),
            ):
                embed_descriptions_over_http(
                    {"u0": "text"}, _embedding_config(), settings=settings, cache=cache
                )

    def test_http_embedding_rejects_substituted_model_and_missing_index(self):
        settings = EmbeddingSettings(
            model="nomic-embed-text",
            model_revision="r",
            tokenizer_revision="r",
            extraction="server-mean-pooling-last-layer",
            device="remote",
        )
        served = (
            (
                {"data": [{"embedding": [1.0, 0.0]}], "model": "nomic-embed-text"},
                "index 0",
            ),
            (
                {"data": [{"index": 0, "embedding": [1.0, 0.0]}], "model": "other"},
                "does not match",
            ),
        )
        for payload, pattern in served:
            with (
                patch(
                    "src.arm_fm.evaluation.urlopen",
                    return_value=_EmbeddingResponse(json.dumps(payload).encode()),
                ),
                self.assertRaisesRegex(RuntimeError, pattern),
            ):
                embed_descriptions_over_http(
                    {"u0": "text"},
                    _embedding_config(),
                    settings=settings,
                    cache=EmbeddingCache(),
                )

    def test_judge_context_is_complete_method_blind_and_uses_stored_evidence(self):
        bundle = ArtifactBundle(
            BundleManifest(
                "finish",
                "demo.md",
                {"done": "finished"},
                generation={"attempt": 2, "provider": "secret", "feedback": "secret"},
                provenance={"generator": "compiler"},
                rm_mode="compiler",
                inputs={"task": "finish", "environment_markdown": "# Demo"},
                api_definitions={"labeling": "env.done"},
                stage_status={
                    "reward_machine": "complete",
                    "labeling": "complete",
                    "descriptions": "complete",
                },
            ),
            PaperRewardMachine(
                ("u0", "u1"),
                "u0",
                (RuntimeTransition("u0", "done", "u1"),),
                ("u1",),
                ("done",),
            ),
            "def done(env):\n    return True\n",
            {"u0": "start", "u1": "finish"},
            execution_evidence=[{"valuation": {"done": True}}],
        )
        prompts = []
        engine = SimpleNamespace(
            request_text=lambda system, user, **kwargs: (
                prompts.append(user)
                or '{"rm_correct": true, "labeling_correct": true, "reason": "ok"}'
            )
        )
        decision = judge_bundle(bundle, engine)
        self.assertTrue(decision.scored)
        self.assertIn("environment_markdown", prompts[0])
        self.assertIn("valuation", prompts[0])
        for forbidden in (
            "rm_mode",
            "provenance",
            "provider",
            "feedback",
            "judge_model",
            "candidate_attempts",
        ):
            self.assertNotIn(forbidden, prompts[0])

    def test_benchmark_accounting_preserves_unscored(self):
        summary = aggregate_judgments(
            [
                JudgeDecision(True, True, "ok"),
                JudgeDecision(False, False, "missing", scored=False),
            ],
            submitted=3,
            generation_failures=1,
        )
        self.assertEqual(summary.scored, 1)
        self.assertEqual(summary.counts["both"], 1)
        self.assertEqual(summary.generation_failures, 1)

    def test_frozen_evaluation_enters_eval_mode(self):
        bundle = ArtifactBundle(
            BundleManifest(
                "finish",
                "demo.md",
                {"done": "finished"},
                stage_status={
                    "reward_machine": "complete",
                    "labeling": "complete",
                    "descriptions": "complete",
                    "embeddings": "complete",
                    "validation": "complete",
                },
            ),
            PaperRewardMachine(
                ("u0", "u1"),
                "u0",
                (RuntimeTransition("u0", "done", "u1"),),
                ("u1",),
                ("done",),
            ),
            "def done(env):\n    return True\n",
            {"u0": "start", "u1": "finish"},
            {"u0": [0.0], "u1": [1.0]},
        )
        policy = SimpleNamespace(training=False, eval=Mock())
        result = frozen_evaluate(policy, [bundle], runner=lambda p, b: {"success": 1.0})
        policy.eval.assert_called_once_with()
        self.assertEqual(result[0]["success"], 1.0)


if __name__ == "__main__":
    unittest.main()
