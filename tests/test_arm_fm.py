import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from src.arm_fm import (
    ALGORITHM_COMPONENTS,
    ArtifactBundle,
    BundleManifest,
    BundleValidationError,
    EmbeddingCache,
    EmbeddingSettings,
    JudgeDecision,
    BuiltinPolicy,
    PaperRewardMachine,
    RNDModule,
    RewardMachineEnvironment,
    RewardMachineRuntime,
    RuntimeValidationError,
    RuntimeTransition,
    TrainingCheckpoint,
    TrainingConfig,
    adapt_compilation_result,
    aggregate_judgments,
    algorithm_for_domain,
    frozen_evaluate,
    generate_baseline_bundle,
    generate_compiler_bundle,
    judge_bundle,
    load_builtin_policy,
    load_labeling_functions,
    load_task_manifest,
    paper_experiment_manifest,
    paper_training_config,
    parse_paper_reward_machine,
    resolve_embedding_settings,
    serialize_paper_reward_machine,
    train_larm,
)
from src.models import EnvironmentDescription
from src.arm_fm.training import _observation_array


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
        import gymnasium as gym
        import minigrid

        environment = gym.make("MiniGrid-DoorKey-8x8-v0")
        environment.reset(seed=42)
        reward_machine = PaperRewardMachine(
            ("u0", "u1"), "u0", (RuntimeTransition("u0", "snapshot", "u1"),), ("u1",), ("snapshot",)
        )
        labeling = load_labeling_functions(
            "def snapshot(env):\n"
            "    return env.grid is not None and env.agent_pos is not None and env.carrying is None\n",
            ("snapshot",),
        )

        runtime = RewardMachineRuntime(reward_machine)
        runtime.step_environment(environment, labeling)
        self.assertEqual(runtime.state, "u1")

    def test_labeling_snapshot_is_shared_read_only_and_updated_after_success(self):
        rm = PaperRewardMachine(
            ("u0",), "u0", (), (), ("current", "event")
        )
        runtime = RewardMachineRuntime(rm)
        snapshots = []
        labeling = {
            "current": lambda env: snapshots.append(env.episode_memory["previous_valuation"]) or len(range(2)) == 2,
            "event": lambda env: snapshots.append(env.episode_memory["previous_valuation"]) or not env.episode_memory["previous_valuation"].get("current", False),
        }
        runtime.step_environment(SimpleNamespace(), labeling)
        self.assertIs(snapshots[0], snapshots[1])
        self.assertEqual(runtime.episode_memory["previous_valuation"], {"current": True, "event": True})
        with self.assertRaises(TypeError):
            snapshots[0]["current"] = False
        runtime.reset()
        self.assertEqual(runtime.episode_memory, {})

    def test_labeling_failure_does_not_replace_previous_valuation(self):
        rm = PaperRewardMachine(("u0",), "u0", (), (), ("value",))
        runtime = RewardMachineRuntime(rm)
        runtime.episode_memory["previous_valuation"] = {"value": True}
        with self.assertRaises(RuntimeError):
            runtime.step_environment(SimpleNamespace(), {"value": lambda env: (_ for _ in ()).throw(RuntimeError("bad"))})
        self.assertEqual(runtime.episode_memory["previous_valuation"], {"value": True})

    def test_labeling_source_is_read_only_and_non_reflective(self):
        safe = load_labeling_functions(
            "def done(env):\n    return env.done\n", ("done",)
        )
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
        self.assertEqual(parse_paper_reward_machine(serialize_paper_reward_machine(machine)), machine)

    def test_compiler_paper_round_trip_declares_zero_default(self):
        machine = PaperRewardMachine(
            ("u0", "u1"), "u0", (RuntimeTransition("u0", "done", "u1"),),
            ("u1",), ("done",), 0.0,
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
            ("u0", "u1"), "u0", (RuntimeTransition("u0", "done", "u1", 1),), ("u1",), ("done",)
        )
        self.manifest = BundleManifest("finish", "demo/environment.md", {"done": "finished"}, stage_status={
            "reward_machine": "complete", "labeling": "complete", "descriptions": "complete", "embeddings": "complete", "validation": "complete"
        })

    def test_incomplete_bundle_is_visible(self):
        bundle = ArtifactBundle(self.manifest, self.rm, "def done(env):\n    return True\n", {"u0": "start", "u1": "done"})
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
                transitions=(SimpleNamespace(source=0, destination=1, condition=("done",), reward=0.0),),
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
        responses = iter([
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
        ])
        engine = SimpleNamespace(request_text=lambda system, user: next(responses))
        result = generate_baseline_bundle("finish", environment, engine)
        self.assertEqual([item.stage for item in result.attempts], ["reward_machine", "labeling", "descriptions"])
        self.assertEqual(len(result.bundle.raw_responses), 3)
        self.assertTrue(result.bundle.manifest.generation["first_attempt"])
        self.assertFalse(result.bundle.manifest.generation["refined"])

    def test_compiler_failure_persists_accepted_rm(self):
        environment = EnvironmentDescription.from_markdown(
            "# Demo\n## Propositions\n- `done`: Finished", source="demo.md"
        )
        compiled = SimpleNamespace(
            environment=SimpleNamespace(
                source=Path("demo.md"), markdown=environment.markdown,
                proposition_ids=("done",),
                propositions=(SimpleNamespace(identifier="done", description="finished"),),
            ),
            proposal=SimpleNamespace(task="finish"), text="numeric",
            reward_machine=SimpleNamespace(
                states=(0, 1), initial_state=0, final_state=1,
                transitions=(SimpleNamespace(source=0, destination=1, condition=("done",), reward=1.0),),
            ),
        )
        engine = SimpleNamespace(request_text=lambda system, user: (_ for _ in ()).throw(RuntimeError("down")))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RuntimeError):
                generate_compiler_bundle((compiled,), engine, bundle_directory=directory)
            loaded = ArtifactBundle.load(directory)
        self.assertIsNotNone(loaded.reward_machine)
        self.assertEqual(loaded.manifest.stage_status["reward_machine"], "complete")
        self.assertEqual(loaded.manifest.stage_status["labeling"], "failed")
        self.assertTrue(loaded.manifest.errors)

    def test_failed_generation_persists_inspectable_bundle(self):
        environment = EnvironmentDescription.from_markdown(
            "# Demo\n## Propositions\n- `done`: Finished", source="demo.md"
        )
        engine = SimpleNamespace(
            model="mock-model", provider_name="mock",
            request_text=lambda system, user: (_ for _ in ()).throw(RuntimeError("provider down")),
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RuntimeError):
                generate_baseline_bundle("finish", environment, engine, bundle_directory=directory)
            loaded = ArtifactBundle.load(directory)
            self.assertIsNone(loaded.reward_machine)
            self.assertTrue(loaded.attempts)
            self.assertEqual(loaded.manifest.errors, ["provider down"] * 3)

    def test_failed_generation_respects_bundle_overwrite(self):
        environment = EnvironmentDescription.from_markdown(
            "# Demo\n## Propositions\n- `done`: Finished", source="demo.md"
        )
        engine = SimpleNamespace(
            model="mock-model", provider_name="mock",
            request_text=lambda system, user: (_ for _ in ()).throw(RuntimeError("new failure")),
        )
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            (bundle / "manifest.json").write_text('{"sentinel": true}\n', encoding="utf-8")
            with self.assertRaises(RuntimeError):
                generate_baseline_bundle(
                    "finish", environment, engine,
                    bundle_directory=bundle,
                    overwrite=False,
                )
            self.assertEqual((bundle / "manifest.json").read_text(encoding="utf-8"), '{"sentinel": true}\n')
            with self.assertRaises(RuntimeError):
                generate_baseline_bundle(
                    "finish", environment, engine,
                    bundle_directory=bundle,
                    overwrite=True,
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
            ("u0", "u1"), "u0", (RuntimeTransition("u0", "done", "u1", 1),), ("u1",), ("done",)
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
            Environment(), RewardMachineRuntime(bundle.reward_machine), bundle.labeling_source,
        )
        wrapped.reset()
        _, reward, _, truncated, info = wrapped.step(0)
        self.assertEqual((reward, truncated, info["rm_state"]), (1.0, True, "u1"))
        self.assertEqual(set(info["valuation"]), {"done"})
        self.assertEqual(len(wrapped.execution_evidence), 1)

    def test_native_algorithms_and_strict_checkpoint_round_trip(self):
        import numpy as np
        cases = (("dqn", SimpleNamespace(n=2)), ("rainbow", SimpleNamespace(n=2)),
                 ("ppo", SimpleNamespace(n=2)), ("sac", SimpleNamespace(shape=(2,))))
        expected = {"dqn": "DQN", "rainbow": "RainbowDQN", "ppo": "PPO", "sac": "PeriodicSAC"}
        for algorithm, action_space in cases:
            policy = BuiltinPolicy(algorithm, action_space, seed=1, learning_rate=1e-2)
            policy._ensure({"observation": np.zeros(2), "embedding": [1.0, 0.0]})
            self.assertEqual(type(policy.algorithm_impl).__name__, expected[algorithm])
            self.assertIn("learner", ALGORITHM_COMPONENTS[algorithm])
        self.assertEqual(ALGORITHM_COMPONENTS["rainbow"]["per_alpha"], 0.5)
        self.assertEqual(ALGORITHM_COMPONENTS["rainbow"]["per_beta"], 0.4)

    def test_rnd_target_freeze_and_eval_freeze(self):
        rnd = RNDModule(2)
        rnd.train()
        self.assertFalse(rnd.target.training)
        self.assertTrue(rnd.predictor.training)
        self.assertTrue(all(not parameter.requires_grad for parameter in rnd.target.parameters()))
        rnd.eval()
        self.assertFalse(rnd.target.training)
        self.assertFalse(rnd.predictor.training)

    def test_xland_training_and_held_out_tasks_are_disjoint(self):
        manifest = paper_experiment_manifest("xland")
        self.assertTrue(set(manifest.train_tasks).isdisjoint(manifest.held_out_tasks))
        self.assertEqual(manifest.seeds, (0, 1, 2))

    def test_manifest_resolves_description_and_bundle_but_keeps_runtime_id_opaque(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "nested").mkdir()
            manifest = root / "nested" / "tasks.json"
            manifest.write_text(json.dumps({"tasks": {
                "task": {
                    "bundle": "../bundle",
                    "environment_description": "../environment.md",
                    "environment_id": "Craftium/custom/id",
                }
            }}), encoding="utf-8")
            (root / "environment.md").write_text("# Demo", encoding="utf-8")
            entry = load_task_manifest(manifest)[0]
        self.assertEqual(entry.environment_id, "Craftium/custom/id")
        self.assertEqual(entry.environment_description, (root / "environment.md").resolve())
        self.assertEqual(entry.bundle, (root / "bundle").resolve())

    def test_xland_dispatches_to_rainbow_and_rnd_is_explicit(self):
        self.assertEqual(algorithm_for_domain("xland-minigrid"), "rainbow")
        self.assertEqual(algorithm_for_domain("minigrid"), "dqn")
        self.assertFalse(paper_training_config("metaworld").rnd)
        self.assertTrue(paper_training_config("metaworld-rnd").rnd)

    def test_small_native_update_saves_and_restores_strictly(self):
        import gymnasium as gym
        import numpy as np

        class Environment:
            action_space = gym.spaces.Discrete(2)
            observation_space = gym.spaces.Box(-1, 1, shape=(2,), dtype=np.float32)

            def reset(self, **_kwargs):
                return np.zeros(2, dtype=np.float32), {}

            def step(self, _action):
                return np.zeros(2, dtype=np.float32), 0.0, False, False, {}

        config = TrainingConfig(
            "dqn", 3, 1e-3, batch_size=1, learning_starts=1,
            replay_capacity=20, train_frequency=1, target_update_frequency=2,
            epsilon_start=1.0, epsilon_end=0.1, epsilon_fraction=1.0,
        )
        bundle = ArtifactBundle(
            self.manifest, self.rm, "def done(env):\n    return True\n",
            {"u0": "start", "u1": "done"}, {"u0": [0.0], "u1": [1.0]},
        )
        with tempfile.TemporaryDirectory() as directory:
            checkpoint_path = Path(directory) / "checkpoint.pt"
            checkpoint = train_larm(bundle, Environment(), config=config, checkpoint_path=checkpoint_path)
            loaded = TrainingCheckpoint.load(checkpoint_path)
            policy = load_builtin_policy(loaded, Environment(), bundle)
        self.assertEqual(checkpoint.timestep, loaded.timestep)
        self.assertGreaterEqual(loaded.timestep, config.learning_starts)
        self.assertEqual(loaded.config["replay_capacity"], min(config.replay_capacity, config.total_timesteps))
        self.assertFalse(policy.training)

    def test_minigrid_observation_ignores_text_metadata(self):
        import gymnasium as gym
        import minigrid

        environment = gym.make("MiniGrid-DoorKey-8x8-v0")
        observation, _ = environment.reset(seed=42)
        flattened = _observation_array(observation)

        self.assertEqual(flattened.size, observation["image"].size + observation["direction"].size)

    def test_native_ppo_uses_four_lanes_and_full_rollout(self):
        import gymnasium as gym
        import numpy as np

        class Environment:
            action_space = gym.spaces.Discrete(2)
            observation_space = gym.spaces.Box(-1, 1, shape=(2,), dtype=np.float32)

            def reset(self, **_kwargs):
                return np.zeros(2, dtype=np.float32), {}

            def step(self, _action):
                return np.zeros(2, dtype=np.float32), 0.0, False, False, {}

        config = TrainingConfig("ppo", 1, 1e-3, batch_size=128)
        bundle = ArtifactBundle(
            self.manifest, self.rm, "def done(env):\n    return True\n",
            {"u0": "start", "u1": "done"}, {"u0": [0.0], "u1": [1.0]},
        )
        checkpoint = train_larm(bundle, [Environment() for _ in range(4)], config=config)
        self.assertEqual(checkpoint.timestep, 512)


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

    def test_judge_context_is_complete_method_blind_and_uses_stored_evidence(self):
        bundle = ArtifactBundle(
            BundleManifest(
                "finish", "demo.md", {"done": "finished"},
                generation={"attempt": 2, "provider": "secret", "feedback": "secret"},
                provenance={"generator": "compiler"}, rm_mode="compiler",
                inputs={"task": "finish", "environment_markdown": "# Demo"},
                api_definitions={"labeling": "env.done"},
                stage_status={"reward_machine": "complete", "labeling": "complete", "descriptions": "complete"},
            ),
            PaperRewardMachine(("u0", "u1"), "u0", (RuntimeTransition("u0", "done", "u1"),), ("u1",), ("done",)),
            "def done(env):\n    return True\n", {"u0": "start", "u1": "finish"},
            execution_evidence=[{"valuation": {"done": True}}],
        )
        prompts = []
        engine = SimpleNamespace(request_text=lambda system, user, **kwargs: prompts.append(user) or '{"rm_correct": true, "labeling_correct": true, "reason": "ok"}')
        decision = judge_bundle(bundle, engine)
        self.assertTrue(decision.scored)
        self.assertIn("environment_markdown", prompts[0])
        self.assertIn("valuation", prompts[0])
        for forbidden in ("rm_mode", "provenance", "provider", "feedback", "judge_model", "candidate_attempts"):
            self.assertNotIn(forbidden, prompts[0])

    def test_benchmark_accounting_preserves_unscored(self):
        summary = aggregate_judgments(
            [JudgeDecision(True, True, "ok"), JudgeDecision(False, False, "missing", scored=False)],
            submitted=3,
            generation_failures=1,
        )
        self.assertEqual(summary.scored, 1)
        self.assertEqual(summary.counts["both"], 1)
        self.assertEqual(summary.generation_failures, 1)

    def test_frozen_evaluation_enters_eval_mode(self):
        bundle = ArtifactBundle(
            BundleManifest("finish", "demo.md", {"done": "finished"}, stage_status={
                "reward_machine": "complete", "labeling": "complete", "descriptions": "complete", "embeddings": "complete", "validation": "complete"
            }),
            PaperRewardMachine(("u0", "u1"), "u0", (RuntimeTransition("u0", "done", "u1"),), ("u1",), ("done",)),
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
