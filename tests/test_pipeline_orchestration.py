import json
import os, subprocess, sys, unittest
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, call, patch
import importlib

from src.compiler import CompilationResult, Proposal
from src.compiler.reward_machine import RewardMachineStructure
from src.config import Configuration
from src.engines import CriticResult, ImmediateEngineError, ProposalValidationError, RetryableEngineError
from src.engines.structured import ProposalSelection, parse_critic
from src.models import EnvironmentDescription, PriorityLevel
from src.utils import GenerationHooks, PipelineStep, Progress, StepState, load_step_trace
from nl2ltl.declare.declare import Existence
from pylogics.syntax.ltl import Atomic

g = importlib.import_module("scripts.generate_rm")
ENV = EnvironmentDescription.from_markdown("# Demo\n## Propositions\n- `done`: Finished", source="demo.md")
SELECTION = ProposalSelection(
    "finish done", "Existence", ("done",), PriorityLevel.NONE,
    Existence(Atomic("done")),
)

def prop(task="finish"): return Proposal(task=task, clauses=())
def result(text="serialized-rm"):
    return CompilationResult(
        ENV, prop(), (), RewardMachineStructure((0, 1), 0, 1, (), ()), text
    )

class EmbeddingResponse:
    """Minimal context manager standing in for one live HTTP embedding response."""
    def __init__(self, body): self._body=body
    def read(self): return self._body
    def __enter__(self): return self
    def __exit__(self,*_args): return False

class Engine:
    def __init__(self):
        self.environment=ENV; self.tasks=[]; self.rms=[]; self.histories=[]; self.proposals=[]
        self.tag_nodes=[]; self.descriptions=[]; self.tag_results=[]
        self.labeling_requests=[]; self.labeling_reviews=[]
        self.labeling_results=[]; self.labeling_verdicts=[]
    def propose_task(self, task, history=""):
        self.histories.append(history)
        value = self.proposals.pop(0) if self.proposals else (SELECTION,)
        if isinstance(value, BaseException): raise value
        return value
    def review_task(self, task, candidate):
        self.tasks.append(candidate); value=self.task_results.pop(0)
        if isinstance(value, BaseException): raise value
        return value
    def describe_states(self, task, clauses, candidate, rejecting, nodes):
        self.tag_nodes.append(tuple(nodes))
        value = self.tag_results.pop(0) if self.tag_results else None
        if isinstance(value, BaseException): raise value
        if value is None: return tuple(f"description {node}" for node in nodes)
        return value
    def review_reward_machine(self, task, candidate, state_descriptions=""):
        self.rms.append(candidate); self.descriptions.append(state_descriptions)
        value=self.rm_results.pop(0)
        if isinstance(value, BaseException): raise value
        return value
    def request_text(self, system, user):
        self.labeling_requests.append(user)
        value = self.labeling_results.pop(0) if self.labeling_results else (
            "```python\ndef done(env):\n    return True\n```"
        )
        if isinstance(value, BaseException): raise value
        return value
    def review_labeling(self, **values):
        self.labeling_reviews.append(values)
        value = self.labeling_verdicts.pop(0) if self.labeling_verdicts else CriticResult(True, "NO CHANGES NEEDED")
        if isinstance(value, BaseException): raise value
        return value

class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.log_directory = TemporaryDirectory()
        self.addCleanup(self.log_directory.cleanup)
        self.logs_patch = patch.object(
            Configuration, "LOGS_PATH", Path(self.log_directory.name)
        )
        self.addCleanup(self.logs_patch.stop)
        self.logs_patch.start()
        self.engine=Engine(); self.engine.task_results=[]; self.engine.rm_results=[]; self.critic=Engine(); self.critic.task_results=[]; self.critic.rm_results=[]; self.saved=Mock()
    def execute(self, tasks=("finish",), **flags):
        CONFIG=Configuration(environment="demo.md", tasks=list(tasks), output="out.rm", **flags)
        with patch.object(g,"setup_environment_and_engines",return_value=(ENV,self.engine,self.critic)), patch.object(g,"derive_output_paths",return_value=tuple(Path(f"out-{i}.rm") for i in range(len(tasks)))), patch.object(g,"save_results",self.saved), patch.object(g,"compile_dfas",return_value=()), patch.object(g,"build_compilation_result",return_value=result()): return g.generate_rm(CONFIG)
    def test_first_attempt_acceptance(self):
        self.critic.task_results=[CriticResult(True,"task ok")]; self.critic.rm_results=[CriticResult(True,"rm ok")]
        self.assertEqual(self.execute(),0); self.saved.assert_called_once()
    def test_task_rejection_skips_compile_and_history(self):
        self.critic.task_results=[CriticResult(False,"fix task"),CriticResult(True,"ok")]; self.critic.rm_results=[CriticResult(True,"ok")]
        with patch.object(g,"setup_environment_and_engines",return_value=(ENV,self.engine,self.critic)), patch.object(g,"derive_output_paths",return_value=(Path("out.rm"),)), patch.object(g,"save_results",self.saved), patch.object(g,"compile_dfas",return_value=()) as compile_mock, patch.object(g,"build_compilation_result",return_value=result()): self.assertEqual(g.generate_rm(Configuration(environment="demo.md",tasks=["finish"],output="out.rm")),0)
        self.assertEqual(compile_mock.call_count,1); self.assertIn("fix task",self.engine.histories[1]); self.assertIn("task critic",self.engine.histories[1]); self.assertIn('"source": "task critic"',self.engine.histories[1])
    def test_rm_critic_failure_keeps_compiled_rm_in_history(self):
        self.critic.task_results=[CriticResult(True,"ok")]*2; self.critic.rm_results=[RetryableEngineError("critic unavailable"),CriticResult(True,"ok")]
        compiled=[result("rm-before-retry"),result()]
        with patch.object(g,"setup_environment_and_engines",return_value=(ENV,self.engine,self.critic)), patch.object(g,"derive_output_paths",return_value=(Path("out.rm"),)), patch.object(g,"save_results",self.saved), patch.object(g,"compile_dfas",return_value=()), patch.object(g,"build_compilation_result",side_effect=compiled):
            self.assertEqual(g.generate_rm(Configuration(environment="demo.md",tasks=["finish"],output="out.rm")),0)
        self.assertIn("rm-before-retry",self.engine.histories[1]); self.assertIn("critic unavailable",self.engine.histories[1]); self.assertIn('"source": "RM critic"',self.engine.histories[1])
    def test_rm_rejection_recompiles_and_history(self):
        self.critic.task_results=[CriticResult(True,"ok")]*2; self.critic.rm_results=[CriticResult(False,"fix rm"),CriticResult(True,"ok")]; compiled=[result("rm-1"),result()]
        with patch.object(g,"setup_environment_and_engines",return_value=(ENV,self.engine,self.critic)), patch.object(g,"derive_output_paths",return_value=(Path("out.rm"),)), patch.object(g,"save_results",self.saved), patch.object(g,"compile_dfas",return_value=()), patch.object(g,"build_compilation_result",side_effect=compiled): self.assertEqual(g.generate_rm(Configuration(environment="demo.md",tasks=["finish"],output="out.rm")),0)
        self.assertIn("rm-1",self.engine.histories[1]); self.assertIn("fix rm",self.engine.histories[1]); self.assertIn('"source": "RM critic"',self.engine.histories[1])
    def test_exhaustion_and_later_task_failure_write_nothing(self):
        self.critic.task_results=[CriticResult(False,"no")]*3; self.assertEqual(self.execute(),1); self.saved.assert_not_called()
        self.critic.task_results=[]; self.critic.rm_results=[CriticResult(False,"no")]*3; self.saved.reset_mock()
        self.assertEqual(self.execute(("one","two"),task_critic=False),1); self.saved.assert_not_called()
    def test_each_critic_toggle(self):
        self.critic.rm_results=[CriticResult(True,"ok")]; self.assertEqual(self.execute(task_critic=False),0); self.assertFalse(self.critic.tasks)
        self.assertTrue(self.engine.tag_nodes)
        self.critic.rms.clear(); self.engine.tag_nodes.clear(); self.critic.task_results=[CriticResult(True,"ok")]
        self.assertEqual(self.execute(rm_critic=False),0); self.assertFalse(self.critic.rms)
        self.assertTrue(self.engine.tag_nodes)
    def test_multiple_task_output_names_are_numbered(self):
        CONFIG=Configuration(environment="demo.md",tasks=["one","two"],output="batch.rm")
        self.assertEqual([path.name for path in g.derive_output_paths(CONFIG)],["batch-1.rm","batch-2.rm"])
    def test_blank_task_fails_before_setup_or_generation(self):
        CONFIG=Configuration(environment="demo.md",tasks=["  "],output="out.rm")
        with patch.object(g,"setup_environment_and_engines") as setup, patch.object(g,"_step_generate_proposal") as propose:
            with self.assertRaises(ValueError): g.generate_rm(CONFIG)
        setup.assert_not_called(); propose.assert_not_called()
    def test_retryable_immediate_and_mona_failures(self):
        self.critic.rm_results=[CriticResult(True,"ok")]
        self.engine.proposals=[RetryableEngineError("rate"),(SELECTION,)]
        with patch.object(g,"setup_environment_and_engines",return_value=(ENV,self.engine,self.critic)), patch.object(g,"derive_output_paths",return_value=(Path("out.rm"),)), patch.object(g,"save_results",self.saved), patch.object(g,"compile_dfas",return_value=()), patch.object(g,"build_compilation_result",return_value=result()): self.assertEqual(g.generate_rm(Configuration(environment="demo.md",tasks=["finish"],output="out.rm",task_critic=False)),0)
        with patch.object(g,"setup_environment_and_engines",side_effect=ImmediateEngineError("denied")): self.assertEqual(g.generate_rm(Configuration(environment="demo.md",tasks=["finish"],output="out.rm")),1)
        self.critic.task_results=[CriticResult(True,"ok")]
        with patch.object(g,"setup_environment_and_engines",return_value=(ENV,self.engine,self.critic)), patch.object(g,"derive_output_paths",return_value=(Path("out.rm"),)), patch.object(g,"compile_dfas",side_effect=RuntimeError("MONA failed")): self.assertEqual(g.generate_rm(Configuration(environment="demo.md",tasks=["finish"],output="out.rm")),1)
    def test_compiler_failure_is_recorded_as_compiler_source(self):
        self.critic.rm_results=[CriticResult(True,"ok")]
        with patch.object(g,"setup_environment_and_engines",return_value=(ENV,self.engine,self.critic)), patch.object(g,"derive_output_paths",return_value=(Path("out.rm"),)), patch.object(g,"save_results",self.saved), patch.object(g,"compile_dfas",side_effect=[ValueError("bad candidate"),()]), patch.object(g,"build_compilation_result",return_value=result()):
            self.assertEqual(g.generate_rm(Configuration(environment="demo.md",tasks=["finish"],output="out.rm",task_critic=False)),0)
        self.assertIn('"source": "compiler"',self.engine.histories[1])
    def test_malformed_proposal_is_recorded_as_generator_source(self):
        self.critic.rm_results=[CriticResult(True,"ok")]
        self.engine.proposals=[ProposalValidationError("malformed"),(SELECTION,)]
        with patch.object(g,"setup_environment_and_engines",return_value=(ENV,self.engine,self.critic)), patch.object(g,"derive_output_paths",return_value=(Path("out.rm"),)), patch.object(g,"save_results",self.saved), patch.object(g,"compile_dfas",return_value=()), patch.object(g,"build_compilation_result",return_value=result()):
            self.assertEqual(g.generate_rm(Configuration(environment="demo.md",tasks=["finish"],output="out.rm",task_critic=False)),0)
        self.assertIn('"source": "generator"',self.engine.histories[1])
    def test_strict_critic_and_cli_flags(self):
        self.assertEqual(parse_critic('{"accepted":true,"feedback":"ok"}'),CriticResult(True,"ok"))
        for value in ('{}','{"accepted":true,"feedback":""}','{"accepted":"yes","feedback":"ok"}'):
            with self.assertRaises(ValueError): parse_critic(value)
        env=os.environ|{"PYTHONPATH":"app"}; command=[sys.executable,"app/main.py","generate-rm","--help"]; help_text=subprocess.run(command,capture_output=True,text=True,env=env,check=True).stdout
        self.assertIn("--no-task-critic",help_text); self.assertIn("--no-rm-critic",help_text)

    def test_structured_pipeline_critic_precedes_ltlf_materialization(self):
        order = []
        engine = SimpleNamespace(
            environment=ENV,
            propose_task=lambda task, history="": order.append("generator") or (SELECTION,),
            review_task=lambda task, candidate: order.append("task critic") or CriticResult(True, "ok"),
            describe_states=lambda *args: order.append("tagger") or ("first", "second"),
            review_reward_machine=lambda task, candidate, state_descriptions="": order.append("RM critic") or CriticResult(True, "ok"),
        )
        CONFIG = Configuration(environment="demo.md", tasks=["finish"], output="out.rm")
        with patch.object(g, "setup_environment_and_engines", return_value=(ENV, engine, engine)), \
            patch.object(g, "derive_output_paths", return_value=(Path("out.rm"),)), \
            patch.object(g, "save_results"), \
            patch.object(g, "materialize_proposal", side_effect=lambda *args: order.append("LTLf") or prop()), \
            patch.object(g, "compile_dfas", side_effect=lambda *args, **kwargs: order.append("DFA") or ()), \
            patch.object(g, "build_compilation_result", side_effect=lambda *args: order.append("RM") or result()):
            self.assertEqual(g.generate_rm(CONFIG), 0)
        self.assertEqual(order, ["generator", "task critic", "LTLf", "DFA", "RM", "tagger", "RM critic"])

    def test_tagging_retries_exhaust_without_restarting_proposals(self):
        self.critic.task_results=[CriticResult(True,"ok")]; self.engine.tag_results=[RetryableEngineError("malformed descriptions")]*3
        failures=[]; events=[]
        with patch.object(g,"setup_environment_and_engines",return_value=(ENV,self.engine,self.critic)), patch.object(g,"derive_output_paths",return_value=(Path("out.rm"),)), patch.object(g,"save_results",self.saved), patch.object(g,"compile_dfas",return_value=()), patch.object(g,"build_compilation_result",return_value=result()):
            status=g.generate_rm(
                Configuration(environment="demo.md",tasks=["finish"],output="out.rm"),
                hooks=GenerationHooks(failure=failures.append,event=events.append),
            )
        self.assertEqual(status,1); self.assertEqual(len(self.engine.histories),1); self.assertEqual(len(self.engine.tag_nodes),3)
        self.assertFalse(self.critic.rms); self.saved.assert_not_called()
        self.assertIn("State-description tagging failed",failures[-1]); self.assertIn("malformed descriptions",failures[-1])
        failed=[event for event in events if event.state is StepState.FAILED]
        self.assertEqual(failed[-1].step,PipelineStep.STATE_DESCRIPTIONS); self.assertIn("State-description tagging failed",failed[-1].detail)

    def test_labeling_runs_after_rm_acceptance_with_role_engines(self):
        self.critic.task_results=[CriticResult(True,"ok")]; self.critic.rm_results=[CriticResult(True,"ok")]
        CONFIG=Configuration(environment="demo.md",tasks=["finish"],output="out.rm",labeling=True)
        with patch.object(g,"setup_environment_and_engines",return_value=(ENV,self.engine,self.critic)), patch.object(g,"derive_output_paths",return_value=(Path("out.rm"),)), patch.object(g,"save_results",self.saved), patch.object(g,"compile_dfas",return_value=()), patch.object(g,"build_compilation_result",return_value=result()), patch.object(g,"_preflight_labeling_bundles"), patch.object(g,"_write_labeling_bundles",return_value=(Path("out-bundle"),)):
            self.assertEqual(g.generate_rm(CONFIG),0)
        self.assertEqual(len(self.engine.labeling_requests),1)
        self.assertEqual(self.engine.labeling_reviews,[])
        self.assertEqual(self.critic.labeling_requests,[])
        self.assertEqual(len(self.critic.labeling_reviews),1)
        review=self.critic.labeling_reviews[0]
        self.assertIn("def done(env)",review["labeling"])
        self.assertIn('"u0": "description u0"',review["state_descriptions_json"])
        self.assertIn('"done"',review["propositions_json"])

    def test_labeling_disabled_skips_stage_and_provider(self):
        self.critic.task_results=[CriticResult(True,"ok")]; self.critic.rm_results=[CriticResult(True,"ok")]
        events=[]
        with patch.object(g,"setup_environment_and_engines",return_value=(ENV,self.engine,self.critic)), patch.object(g,"derive_output_paths",return_value=(Path("out.rm"),)), patch.object(g,"save_results",self.saved), patch.object(g,"compile_dfas",return_value=()), patch.object(g,"build_compilation_result",return_value=result()):
            self.assertEqual(g.generate_rm(Configuration(environment="demo.md",tasks=["finish"],output="out.rm"),hooks=GenerationHooks(event=events.append)),0)
        labeling=[event for event in events if event.step is PipelineStep.LABELING]
        self.assertTrue(labeling); self.assertTrue(all(event.state is StepState.SKIPPED for event in labeling))
        embeddings=[event for event in events if event.step is PipelineStep.EMBEDDINGS]
        self.assertTrue(embeddings); self.assertTrue(all(event.state is StepState.SKIPPED for event in embeddings))
        self.assertEqual(self.engine.labeling_requests,[]); self.assertEqual(self.critic.labeling_reviews,[])

    def test_labeling_retries_exhaust_without_restarting_proposals(self):
        self.critic.task_results=[CriticResult(True,"ok")]; self.critic.rm_results=[CriticResult(True,"ok")]
        self.engine.labeling_results=[RuntimeError("provider down")]*3
        failures=[]; events=[]
        with patch.object(g,"setup_environment_and_engines",return_value=(ENV,self.engine,self.critic)), patch.object(g,"derive_output_paths",return_value=(Path("out.rm"),)), patch.object(g,"save_results",self.saved), patch.object(g,"compile_dfas",return_value=()), patch.object(g,"build_compilation_result",return_value=result()), patch.object(g,"_preflight_labeling_bundles"), patch.object(g,"_write_labeling_bundles"):
            status=g.generate_rm(Configuration(environment="demo.md",tasks=["finish"],output="out.rm",labeling=True),hooks=GenerationHooks(failure=failures.append,event=events.append))
        self.assertEqual(status,1)
        self.assertEqual(len(self.engine.labeling_requests),3)
        self.assertEqual(len(self.critic.rms),1)
        self.assertEqual(len(self.engine.histories),1)
        self.assertIn("Labeling generation failed after 3 requests",failures[-1])
        failed=[event for event in events if event.state is StepState.FAILED]
        self.assertEqual(failed[-1].step,PipelineStep.LABELING)

    def test_labeling_bundles_are_written_and_preflighted(self):
        self.critic.task_results=[CriticResult(True,"ok")]; self.critic.rm_results=[CriticResult(True,"ok")]
        with TemporaryDirectory() as directory:
            root=Path(directory); output_path=root/"RMs"/"out.rm"
            CONFIG=Configuration(environment="demo.md",tasks=["finish"],output="out.rm",labeling=True,rm_critic=False,generator_model="generator-model",critic_model="critic-model")
            CONFIG.OUTPUT_PATH=root
            patches=(patch.object(g,"setup_environment_and_engines",return_value=(ENV,self.engine,self.critic)), patch.object(g,"derive_output_paths",return_value=(output_path,)), patch.object(g,"save_results",self.saved), patch.object(g,"compile_dfas",return_value=()), patch.object(g,"build_compilation_result",return_value=result()))
            completion=[]
            with patches[0],patches[1],patches[2],patches[3],patches[4]:
                self.assertEqual(g.generate_rm(CONFIG,hooks=GenerationHooks(completion=lambda results,paths: completion.append(results))),0)
            bundle_path=root/"bundles"/"out"
            self.assertTrue((bundle_path/"labeling.py").exists())
            self.assertEqual(completion[-1][0].bundle_path,bundle_path)
            self.saved.assert_called_once()
            manifest=json.loads((bundle_path/"manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["stage_status"]["labeling"],"complete")
            self.assertEqual(manifest["stage_status"]["descriptions"],"complete")
            self.assertIn("env.grid.get",manifest["api_definitions"]["labeling"])
            self.assertEqual(manifest["api_definitions"]["labeling"],manifest["generation"]["labeling_api"])
            self.assertEqual(manifest["generation"]["attempt_classification"],"first_attempt")
            attempts=json.loads((bundle_path/"attempts.json").read_text(encoding="utf-8"))
            self.assertEqual([item["stage"] for item in attempts],["compiler","labeling"])
            self.assertEqual(manifest["effective_settings"],{"mode":"compiler","generator_model":"generator-model","critic_model":"critic-model"})
            self.critic.task_results=[CriticResult(True,"ok")]; self.critic.rm_results=[CriticResult(True,"ok")]
            self.saved.reset_mock()
            with patches[0],patches[1],patches[2],patches[3],patches[4]:
                with self.assertRaisesRegex(ValueError,"already exist"):
                    g.generate_rm(CONFIG)
            self.saved.assert_not_called()

    def test_embeddings_stage_is_single_text_cached_and_persisted(self):
        from src.arm_fm import evaluation

        requests=[]
        def fake_urlopen(request,timeout=None):
            requests.append(json.loads(request.data.decode()))
            body=json.dumps({"data":[{"index":0,"embedding":[5.0,0.0]}],"model":"nomic-embed-text"}).encode()
            return EmbeddingResponse(body)
        with TemporaryDirectory() as directory:
            root=Path(directory); output_path=root/"RMs"/"out.rm"; completion=[]
            def config(**overrides):
                value=Configuration(environment="demo.md",tasks=["finish"],output="out.rm",embeddings=True,**overrides)
                value.OUTPUT_PATH=root; value.EMBEDDINGS_PATH=root/"embeddings"
                return value
            def run(value):
                self.critic.task_results=[CriticResult(True,"ok")]; self.critic.rm_results=[CriticResult(True,"ok")]
                patches=(
                    patch.object(g,"setup_environment_and_engines",return_value=(ENV,self.engine,self.critic)),
                    patch.object(g,"derive_output_paths",return_value=(output_path,)),
                    patch.object(g,"save_results",self.saved),
                    patch.object(g,"compile_dfas",return_value=()),
                    patch.object(g,"build_compilation_result",return_value=result()),
                )
                with ExitStack() as stack:
                    stack.enter_context(patch.object(evaluation,"urlopen",side_effect=fake_urlopen))
                    for item in patches: stack.enter_context(item)
                    return g.generate_rm(value,hooks=GenerationHooks(completion=lambda results,paths: completion.append(results)))
            self.assertEqual(run(config()),0)
            artifact=json.loads((root/"embeddings"/"out"/"embeddings.json").read_text(encoding="utf-8"))
            self.assertEqual(len(requests),2)
            self.assertEqual({item["input"] for item in requests},{"description u0","description u1"})
            self.assertEqual(artifact["nodes"],["u0","u1"])
            self.assertEqual(artifact["effective_texts"],{"u0":"description u0","u1":"description u1"})
            self.assertEqual(artifact["settings"]["extraction"],"server-mean-pooling-last-layer")
            self.assertEqual(artifact["settings"]["model_revision"],config().embedding_revision)
            self.assertEqual(artifact["settings"]["dimension"],2)
            self.assertEqual(completion[-1][0].embeddings["u0"],[1.0,0.0])
            self.assertEqual(completion[-1][0].embedding_path,root/"embeddings"/"out"/"embeddings.json")
            self.assertTrue((root/"embeddings"/"cache.json").exists())
            self.saved.reset_mock()
            with self.assertRaisesRegex(ValueError,"already exist"):
                run(config())
            self.saved.assert_not_called()
            requests.clear()
            self.assertEqual(run(config(overwrite=True)),0)
            self.assertEqual(requests,[])
            requests.clear()
            self.assertEqual(run(config(overwrite=True,embedding_context="Episode context")),0)
            self.assertEqual({item["input"] for item in requests},{"Episode context\ndescription u0","Episode context\ndescription u1"})
            contextual=json.loads((root/"embeddings"/"out"/"embeddings.json").read_text(encoding="utf-8"))
            self.assertEqual(contextual["effective_texts"]["u0"],"Episode context\ndescription u0")
            self.assertEqual(contextual["context"],"Episode context")

    def test_labeling_domain_gate_recognizes_exact_families(self):
        baseline=g._labeling_api(Configuration(environment="demo.md",tasks=["finish"],output="out.rm",domain="minigrid"))
        for domain in (None,"minigrid","MiniGrid-DoorKey-8x8-v0","minigrid-unlock-pickup","babyai","BabyAI-UnlockToUnlock-v0"):
            CONFIG=Configuration(environment="demo.md",tasks=["finish"],output="out.rm",domain=domain)
            self.assertEqual(g._labeling_api(CONFIG),baseline)
        for domain in ("xminigrid-medium-1m","minigridish","craftium","not-minigrid","metaworld"):
            CONFIG=Configuration(environment="demo.md",tasks=["finish"],output="out.rm",domain=domain)
            with self.assertRaises(ValueError):
                g._labeling_api(CONFIG)

    def test_rm_rejection_tags_the_next_candidate_afresh(self):
        self.critic.task_results=[CriticResult(True,"ok")]*2; self.critic.rm_results=[CriticResult(False,"fix rm"),CriticResult(True,"ok")]
        self.engine.tag_results=[("a0","a1"),("b0","b1")]; compiled=[result("rm-1"),result("rm-2")]
        with patch.object(g,"setup_environment_and_engines",return_value=(ENV,self.engine,self.critic)), patch.object(g,"derive_output_paths",return_value=(Path("out.rm"),)), patch.object(g,"save_results",self.saved), patch.object(g,"compile_dfas",return_value=()), patch.object(g,"build_compilation_result",side_effect=compiled):
            self.assertEqual(g.generate_rm(Configuration(environment="demo.md",tasks=["finish"],output="out.rm")),0)
        self.assertEqual(self.engine.tag_nodes,[("u0","u1"),("u0","u1")])
        self.assertEqual(len(self.critic.descriptions),2)
        self.assertIn('"u0": "a0"',self.critic.descriptions[0]); self.assertNotIn("b0",self.critic.descriptions[0])
        self.assertIn('"u0": "b0"',self.critic.descriptions[1]); self.assertNotIn("a0",self.critic.descriptions[1])

    def test_critic_context_keeps_node_order_beyond_ten_states(self):
        self.critic.task_results=[CriticResult(True,"ok")]; self.critic.rm_results=[CriticResult(True,"ok")]
        self.engine.tag_results=[tuple(f"description {index}" for index in range(11))]
        compiled=[CompilationResult(ENV,prop(),(),RewardMachineStructure(tuple(range(11)),0,10,(),()),"rm-11")]
        with patch.object(g,"setup_environment_and_engines",return_value=(ENV,self.engine,self.critic)), patch.object(g,"derive_output_paths",return_value=(Path("out.rm"),)), patch.object(g,"save_results",self.saved), patch.object(g,"compile_dfas",return_value=()), patch.object(g,"build_compilation_result",side_effect=compiled):
            self.assertEqual(g.generate_rm(Configuration(environment="demo.md",tasks=["finish"],output="out.rm")),0)
        context=self.critic.descriptions[0]
        self.assertLess(context.index('"u2"'),context.index('"u10"'))

    def test_trace_keeps_identified_state_descriptions(self):
        self.critic.task_results=[CriticResult(True,"ok")]
        self.critic.rm_results=[CriticResult(True,"ok")]
        self.engine.tag_results=[("first stage","task satisfied")]
        artifacts=[]; trace_dir=Path(self.log_directory.name)/"traces"; trace_dir.mkdir()
        CONFIG=Configuration(environment="demo.md",tasks=["finish"],output="out.rm"); CONFIG.trace_dir=trace_dir
        with patch.object(g,"setup_environment_and_engines",return_value=(ENV,self.engine,self.critic)), patch.object(g,"derive_output_paths",return_value=(Path("out.rm"),)), patch.object(g,"save_results",self.saved), patch.object(g,"compile_dfas",return_value=()), patch.object(g,"build_compilation_result",return_value=result()):
            self.assertEqual(g.generate_rm(CONFIG,hooks=GenerationHooks(artifact=artifacts.append)),0)
        published=[item.value for item in artifacts if item.step is PipelineStep.STATE_DESCRIPTIONS]
        self.assertEqual(published,[{"u0":"first stage","u1":"task satisfied"}])
        tasks=load_step_trace((trace_dir/"out.json").read_text(encoding="utf-8"))
        self.assertIn('"u0": "first stage"',tasks[0]["steps"]["state_descriptions"])
        self.assertIn('"u1": "task satisfied"',tasks[0]["steps"]["state_descriptions"])

    def test_role_engines_are_created_once_and_reused(self):
        self.critic.task_results=[CriticResult(False,"task"),CriticResult(True,"ok"),CriticResult(False,"task"),CriticResult(True,"ok")]
        self.critic.rm_results=[CriticResult(True,"ok"),CriticResult(True,"ok")]
        CONFIG=Configuration(environment="demo.md",tasks=["one","two"],output="batch.rm")
        with patch.object(g,"setup_environment_and_engines",return_value=(ENV,self.engine,self.critic)) as setup, patch.object(g,"derive_output_paths",return_value=(Path("one.rm"),Path("two.rm"))), patch.object(g,"save_results",self.saved), patch.object(g,"compile_dfas",return_value=()), patch.object(g,"build_compilation_result",return_value=result()):
            self.assertEqual(g.generate_rm(CONFIG),0)
        setup.assert_called_once()
        self.assertEqual(len(self.engine.histories),4)
        self.assertEqual(len(self.engine.tag_nodes),2)
        self.assertEqual(len(self.critic.tasks),4)
        self.assertEqual(len(self.critic.rms),2)

    def test_compiler_setup_requires_and_separates_role_models(self):
        with TemporaryDirectory() as directory:
            environment_path=Path(directory)/"environment.md"
            environment_path.write_text("# Demo\n## Propositions\n- `done`: Finished",encoding="utf-8")
            CONFIG=Configuration(environment=environment_path,generator_model="generator")
            with patch("src.utils.generation.get_engine",return_value=object()):
                with self.assertRaisesRegex(ValueError,"critic model"):
                    g.setup_environment_and_engines(CONFIG,Progress(GenerationHooks()))
            CONFIG=Configuration(environment=environment_path,generator_model="generator",critic_model="generator")
            with patch("src.utils.generation.get_engine",return_value=object()):
                with self.assertRaisesRegex(ValueError,"must differ"):
                    g.setup_environment_and_engines(CONFIG,Progress(GenerationHooks()))
            generator_engine,critic_engine=object(),object()
            CONFIG=Configuration(environment=environment_path,generator_model="generator",critic_model="critic")
            with patch("src.utils.generation.get_engine",side_effect=[generator_engine,critic_engine]) as get_engine:
                loaded,setup_generator,setup_critic=g.setup_environment_and_engines(CONFIG,Progress(GenerationHooks()))
            self.assertIs(setup_generator,generator_engine); self.assertIs(setup_critic,critic_engine)
            self.assertEqual([item.args[2] for item in get_engine.call_args_list],["generator","critic"])
            CONFIG=Configuration(environment=environment_path,generator_model="generator",task_critic=False,rm_critic=False)
            with patch("src.utils.generation.get_engine",return_value=generator_engine) as get_engine:
                loaded,setup_generator,setup_critic=g.setup_environment_and_engines(CONFIG,Progress(GenerationHooks()))
            self.assertIs(setup_generator,generator_engine); self.assertIsNone(setup_critic); self.assertEqual(get_engine.call_count,1)

if __name__ == "__main__": unittest.main()
