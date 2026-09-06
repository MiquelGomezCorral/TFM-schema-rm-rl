import os, subprocess, sys, unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch
import importlib

from src.compiler import Proposal
from src.config import Configuration
from src.engines import CriticResult, ImmediateEngineError, ProposalValidationError, RetryableEngineError
from src.engines.structured import ProposalSelection, parse_critic
from src.models import EnvironmentDescription, PriorityLevel
from nl2ltl.declare.declare import Existence
from pylogics.syntax.ltl import Atomic

g = importlib.import_module("scripts.generate_rm")
ENV = EnvironmentDescription.from_markdown("# Demo\n## Propositions\n- `done`: Finished", source="demo.md")
SELECTION = ProposalSelection(
    "finish done", "Existence", ("done",), PriorityLevel.NONE,
    Existence(Atomic("done")),
)

def prop(task="finish"): return Proposal(task=task, clauses=())
def result(): return SimpleNamespace(text="serialized-rm", proposal=prop())

class Engine:
    def __init__(self):
        self.environment=ENV; self.tasks=[]; self.rms=[]; self.histories=[]; self.proposals=[]
    def propose_task(self, task, history=""):
        self.histories.append(history)
        value = self.proposals.pop(0) if self.proposals else (SELECTION,)
        if isinstance(value, BaseException): raise value
        return value
    def review_task(self, task, candidate):
        self.tasks.append(candidate); value=self.task_results.pop(0)
        if isinstance(value, BaseException): raise value
        return value
    def review_reward_machine(self, task, candidate):
        self.rms.append(candidate); value=self.rm_results.pop(0)
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
        self.engine=Engine(); self.engine.task_results=[]; self.engine.rm_results=[]; self.saved=Mock()
    def execute(self, tasks=("finish",), **flags):
        config=Configuration(environment="demo.md", tasks=list(tasks), output="out.rm", **flags)
        with patch.object(g,"setup_environment_and_engine",return_value=(ENV,self.engine)), patch.object(g,"derive_output_paths",return_value=tuple(Path(f"out-{i}.rm") for i in range(len(tasks)))), patch.object(g,"save_results",self.saved), patch.object(g,"compile_dfas",return_value=()), patch.object(g,"build_compilation_result",return_value=result()): return g.generate_rm(config)
    def test_first_attempt_acceptance(self):
        self.engine.task_results=[CriticResult(True,"task ok")]; self.engine.rm_results=[CriticResult(True,"rm ok")]
        self.assertEqual(self.execute(),0); self.saved.assert_called_once()
    def test_task_rejection_skips_compile_and_history(self):
        self.engine.task_results=[CriticResult(False,"fix task"),CriticResult(True,"ok")]; self.engine.rm_results=[CriticResult(True,"ok")]
        with patch.object(g,"setup_environment_and_engine",return_value=(ENV,self.engine)), patch.object(g,"derive_output_paths",return_value=(Path("out.rm"),)), patch.object(g,"save_results",self.saved), patch.object(g,"compile_dfas",return_value=()) as compile_mock, patch.object(g,"build_compilation_result",return_value=result()): self.assertEqual(g.generate_rm(Configuration(environment="demo.md",tasks=["finish"],output="out.rm")),0)
        self.assertEqual(compile_mock.call_count,1); self.assertIn("fix task",self.engine.histories[1]); self.assertIn("task critic",self.engine.histories[1]); self.assertIn('"source": "task critic"',self.engine.histories[1])
    def test_rm_critic_failure_keeps_compiled_rm_in_history(self):
        self.engine.task_results=[CriticResult(True,"ok")]*2; self.engine.rm_results=[RetryableEngineError("critic unavailable"),CriticResult(True,"ok")]
        compiled=[SimpleNamespace(text="rm-before-retry",proposal=prop()),result()]
        with patch.object(g,"setup_environment_and_engine",return_value=(ENV,self.engine)), patch.object(g,"derive_output_paths",return_value=(Path("out.rm"),)), patch.object(g,"save_results",self.saved), patch.object(g,"compile_dfas",return_value=()), patch.object(g,"build_compilation_result",side_effect=compiled):
            self.assertEqual(g.generate_rm(Configuration(environment="demo.md",tasks=["finish"],output="out.rm")),0)
        self.assertIn("rm-before-retry",self.engine.histories[1]); self.assertIn("critic unavailable",self.engine.histories[1]); self.assertIn('"source": "RM critic"',self.engine.histories[1])
    def test_rm_rejection_recompiles_and_history(self):
        self.engine.task_results=[CriticResult(True,"ok")]*2; self.engine.rm_results=[CriticResult(False,"fix rm"),CriticResult(True,"ok")]; compiled=[SimpleNamespace(text="rm-1",proposal=prop()),result()]
        with patch.object(g,"setup_environment_and_engine",return_value=(ENV,self.engine)), patch.object(g,"derive_output_paths",return_value=(Path("out.rm"),)), patch.object(g,"save_results",self.saved), patch.object(g,"compile_dfas",return_value=()), patch.object(g,"build_compilation_result",side_effect=compiled): self.assertEqual(g.generate_rm(Configuration(environment="demo.md",tasks=["finish"],output="out.rm")),0)
        self.assertIn("rm-1",self.engine.histories[1]); self.assertIn("fix rm",self.engine.histories[1]); self.assertIn('"source": "RM critic"',self.engine.histories[1])
    def test_exhaustion_and_later_task_failure_write_nothing(self):
        self.engine.task_results=[CriticResult(False,"no")]*3; self.assertEqual(self.execute(),1); self.saved.assert_not_called()
        self.engine.task_results=[]; self.engine.rm_results=[CriticResult(False,"no")]*3; self.saved.reset_mock()
        self.assertEqual(self.execute(("one","two"),task_critic=False),1); self.saved.assert_not_called()
    def test_each_critic_toggle(self):
        self.engine.rm_results=[CriticResult(True,"ok")]; self.assertEqual(self.execute(task_critic=False),0); self.assertFalse(self.engine.tasks)
        self.engine.rms.clear(); self.engine.task_results=[CriticResult(True,"ok")]; self.assertEqual(self.execute(rm_critic=False),0); self.assertFalse(self.engine.rms)
    def test_multiple_task_output_names_are_numbered(self):
        config=Configuration(environment="demo.md",tasks=["one","two"],output="batch.rm")
        self.assertEqual([path.name for path in g.derive_output_paths(config)],["batch-1.rm","batch-2.rm"])
    def test_blank_task_fails_before_setup_or_generation(self):
        config=Configuration(environment="demo.md",tasks=["  "],output="out.rm")
        with patch.object(g,"setup_environment_and_engine") as setup, patch.object(g,"_step_generate_proposal") as propose:
            with self.assertRaises(ValueError): g.generate_rm(config)
        setup.assert_not_called(); propose.assert_not_called()
    def test_retryable_immediate_and_mona_failures(self):
        self.engine.rm_results=[CriticResult(True,"ok")]
        self.engine.proposals=[RetryableEngineError("rate"),(SELECTION,)]
        with patch.object(g,"setup_environment_and_engine",return_value=(ENV,self.engine)), patch.object(g,"derive_output_paths",return_value=(Path("out.rm"),)), patch.object(g,"save_results",self.saved), patch.object(g,"compile_dfas",return_value=()), patch.object(g,"build_compilation_result",return_value=result()): self.assertEqual(g.generate_rm(Configuration(environment="demo.md",tasks=["finish"],output="out.rm",task_critic=False)),0)
        with patch.object(g,"setup_environment_and_engine",side_effect=ImmediateEngineError("denied")): self.assertEqual(g.generate_rm(Configuration(environment="demo.md",tasks=["finish"],output="out.rm")),1)
        self.engine.task_results=[CriticResult(True,"ok")]
        with patch.object(g,"setup_environment_and_engine",return_value=(ENV,self.engine)), patch.object(g,"derive_output_paths",return_value=(Path("out.rm"),)), patch.object(g,"compile_dfas",side_effect=RuntimeError("MONA failed")): self.assertEqual(g.generate_rm(Configuration(environment="demo.md",tasks=["finish"],output="out.rm")),1)
    def test_compiler_failure_is_recorded_as_compiler_source(self):
        self.engine.rm_results=[CriticResult(True,"ok")]
        with patch.object(g,"setup_environment_and_engine",return_value=(ENV,self.engine)), patch.object(g,"derive_output_paths",return_value=(Path("out.rm"),)), patch.object(g,"save_results",self.saved), patch.object(g,"compile_dfas",side_effect=[ValueError("bad candidate"),()]), patch.object(g,"build_compilation_result",return_value=result()):
            self.assertEqual(g.generate_rm(Configuration(environment="demo.md",tasks=["finish"],output="out.rm",task_critic=False)),0)
        self.assertIn('"source": "compiler"',self.engine.histories[1])
    def test_malformed_proposal_is_recorded_as_generator_source(self):
        self.engine.rm_results=[CriticResult(True,"ok")]
        self.engine.proposals=[ProposalValidationError("malformed"),(SELECTION,)]
        with patch.object(g,"setup_environment_and_engine",return_value=(ENV,self.engine)), patch.object(g,"derive_output_paths",return_value=(Path("out.rm"),)), patch.object(g,"save_results",self.saved), patch.object(g,"compile_dfas",return_value=()), patch.object(g,"build_compilation_result",return_value=result()):
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
            review_reward_machine=lambda task, candidate: order.append("RM critic") or CriticResult(True, "ok"),
        )
        fake_result = SimpleNamespace(text="rm")
        config = Configuration(environment="demo.md", tasks=["finish"], output="out.rm")
        with patch.object(g, "setup_environment_and_engine", return_value=(ENV, engine)), \
            patch.object(g, "derive_output_paths", return_value=(Path("out.rm"),)), \
            patch.object(g, "save_results"), \
            patch.object(g, "materialize_proposal", side_effect=lambda *args: order.append("LTLf") or prop()), \
            patch.object(g, "compile_dfas", side_effect=lambda *args, **kwargs: order.append("DFA") or ()), \
            patch.object(g, "build_compilation_result", side_effect=lambda *args: order.append("RM") or fake_result):
            self.assertEqual(g.generate_rm(config), 0)
        self.assertEqual(order, ["generator", "task critic", "LTLf", "DFA", "RM", "RM critic"])

if __name__ == "__main__": unittest.main()
