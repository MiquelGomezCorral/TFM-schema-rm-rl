"""F7: counted RM candidates and provider-outage reruns in both arms, scripted (no provider call).

usage: PYTHONPATH=<tree>/app python f7_limits.py <tree> [<rows.json>]

Modeled on the wave probe ``c31_limits.py``. Every row reports the requests the scripted
engines received, the attempt records the run left, and how the run ended. ``attempts`` is the
benchmark's limit (``RM_ATTEMPTS`` in ``generate_suite``); ``Configuration.OUTAGE_RETRIES`` is
the bounded rerun count for a provider outage, the same in both arms.
"""

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from nl2ltl.declare.declare import Existence
from pylogics.syntax.ltl import Atomic

from scripts.generate_larm import generate_compiler
from scripts.generate_suite import ARM_FLAGS, PROVIDER_ERROR
from src.arm_fm import generate_baseline_bundle
from src.compiler import CompilationResult, Proposal
from src.compiler.reward_machine import RewardMachineStructure
from src.config import Configuration, PriorityLevel
from src.engines import (
    CriticResult,
    CriticValidationError,
    ImmediateEngineError,
    ProposalValidationError,
    RetryableEngineError,
)
from src.engines.structured import ProposalSelection
from src.models import EnvironmentDescription

FACTS = "# Demo\n## Propositions\n- `done`: Finished\n"
CODE = "## Labeling API\n\n- `env.grid.get(x, y)`: the object at a cell\n"
MARKDOWN = f"{FACTS}{CODE}"
RM_TEXT = """```plaintext
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
```"""
ACCEPT = '{"accepted":true,"feedback":"ok"}'
REJECT = '{"accepted":false,"feedback":"not yet"}'
LABELING = "```python\ndef done(env):\n    return True\n```"
OUTAGE = "Connection error."  # the OpenAI SDK wording that generate-suite files as a provider error
# A provider error that must not be retried (authentication): the engine raises ImmediateEngineError.
IMMEDIATE = "Error code: 401 - invalid api key"


def benchmark_attempts() -> int:
    """The ``--attempts`` value generate-suite passes to both arms."""
    values = set()
    for flags in (list(ARM_FLAGS["arm-fm"]), list(ARM_FLAGS["farm"])):
        values.add(int(flags[flags.index("--attempts") + 1]))
    assert len(values) == 1, f"the arms get different limits: {values}"
    return values.pop()


ATTEMPTS = benchmark_attempts()
# The tree before F7 calls the same bound UNCOUNTED_RETRIES.
RERUNS = getattr(Configuration, "OUTAGE_RETRIES", None) or Configuration.UNCOUNTED_RETRIES
TREE = Path(sys.argv[1]).resolve()  # the tree whose app/ is on PYTHONPATH
assert Path(sys.modules["scripts.generate_rm"].__file__).is_relative_to(TREE), "wrong tree loaded"


# ======================================================================================
#                                      ARM-FM
# ======================================================================================


class ArmFmEngines:
    """Scripted generator and critic for the ARM-FM path.

    ``rm_script`` lists, per RM generator request, ``"ok"``, ``"bad"`` (unparseable machine,
    a content failure) or ``"outage"``; the last entry repeats. ``critic`` is ``"accept"`` or
    ``"reject"`` for every RM critic request.
    """

    def __init__(self, rm_script: list[str], critic: str = "accept"):
        self.rm_script, self.critic_verdict = rm_script, critic
        self.rm_requests = self.rm_critic_requests = 0
        self.generator = SimpleNamespace(
            model="scripted-generator", provider_name="scripted", request_text=self.generate
        )
        self.critic = SimpleNamespace(
            model="scripted-critic", provider_name="scripted", request_text=self.review
        )

    def generate(self, _system, _user, stage="text"):
        if stage == "rm_generator":
            step = self.rm_script[min(self.rm_requests, len(self.rm_script) - 1)]
            self.rm_requests += 1
            if step == "outage":
                raise RetryableEngineError(OUTAGE)
            if step == "immediate":
                raise ImmediateEngineError(IMMEDIATE)
            return "no machine here" if step == "bad" else RM_TEXT
        if stage == "labeling_generator":
            return LABELING
        return '{"u0":"start","u1":"finished"}'

    def review(self, _system, _user, stage="text"):
        if stage == "rm_critic":
            self.rm_critic_requests += 1
            if self.critic_verdict == "outage":
                raise RetryableEngineError(OUTAGE)
            return REJECT if self.critic_verdict == "reject" else ACCEPT
        return ACCEPT


def run_arm_fm(name: str, rm_script: list[str], critic: str = "accept") -> dict:
    environment = EnvironmentDescription.from_markdown(MARKDOWN, source="demo.md")
    engines = ArmFmEngines(rm_script, critic)
    with tempfile.TemporaryDirectory() as directory:
        bundle_dir = Path(directory) / "bundle"
        CONFIG = Configuration(bundle=bundle_dir, attempts=ATTEMPTS)
        outcome, message = "accepted", ""
        try:
            result = generate_baseline_bundle(
                "finish", environment, engines.generator, CONFIG, engines.critic
            )
            result.bundle.save(bundle_dir)
        except Exception as error:
            outcome, message = type(error).__name__, str(error)
        attempts = json.loads((bundle_dir / "attempts.json").read_text(encoding="utf-8"))
    rm_records = [
        f"{item['attempt']}:{item['status']}"
        for item in attempts
        if item["stage"] == "reward_machine"
    ]
    return {
        "arm": "arm-fm",
        "case": name,
        "outcome": outcome,
        "provider_error_text": bool(PROVIDER_ERROR.search(message)),
        "rm_generator_requests": engines.rm_requests,
        "rm_critic_requests": engines.rm_critic_requests,
        "counted_attempt_records": len(rm_records),
        "last_records": rm_records[-2:],
        "message": message[:160],
    }


# ======================================================================================
#                                       FARM
# ======================================================================================

SELECTION = ProposalSelection(
    "finish done", "Existence", ("done",), PriorityLevel.HARD, Existence(Atomic("done"))
)


class FarmEngine:
    """Scripted FARM generator or critic.

    ``propose_script`` / ``review_script`` list, per request, ``"ok"``, ``"bad"`` (a content
    failure: invalid proposal or malformed critic output), ``"reject"`` (critic only) or
    ``"outage"``; the last entry repeats.
    """

    def __init__(self, propose_script=("ok",), review_script=("ok",)):
        self.propose_script, self.review_script = propose_script, review_script
        self.proposals = self.reviews = 0
        self.model, self.provider_name = "scripted", "scripted"
        self.calls: list = []

    @staticmethod
    def _step(script, count):
        return script[min(count, len(script) - 1)]

    def propose_task(self, _task, history=""):
        del history  # the scripted engine ignores the repair history
        step = self._step(self.propose_script, self.proposals)
        self.proposals += 1
        if step == "outage":
            raise RetryableEngineError(OUTAGE)
        if step == "immediate":
            raise ImmediateEngineError(IMMEDIATE)
        if step == "bad":
            raise ProposalValidationError("malformed proposal")
        return (SELECTION,)

    def describe_states(self, _task, _clauses, _candidate, nodes):
        return tuple(f"description {node}" for node in nodes)

    def review_candidate(self, _task, _clauses_json, _candidate, _warnings=()):
        step = self._step(self.review_script, self.reviews)
        self.reviews += 1
        if step == "outage":
            raise RetryableEngineError(OUTAGE)
        if step == "bad":
            raise CriticValidationError("malformed critic output")
        return CriticResult(step == "ok", "ok" if step == "ok" else "not yet")

    def request_text(self, _system, _user, stage="text"):
        del stage  # the scripted engine answers every stage with the same labeling
        return LABELING

    def review_labeling(self, **_values):
        return CriticResult(True, "NO CHANGES NEEDED")


def run_farm(name: str, propose_script=("ok",), review_script=("ok",)) -> dict:
    facts = EnvironmentDescription.from_markdown(FACTS, source="demo.md")
    labeling = EnvironmentDescription.from_markdown(MARKDOWN, source="demo.md")
    compiled = CompilationResult(
        facts,
        Proposal(task="finish", clauses=()),
        RewardMachineStructure((0, 1), 0, 1, (), ()),
        "rm",
    )
    generator, critic = FarmEngine(propose_script), FarmEngine(review_script=review_script)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        bundle_dir = root / "bundle"
        CONFIG = Configuration(
            environment="demo.md",
            tasks=["finish"],
            bundle=bundle_dir,
            mode="compiler",
            attempts=ATTEMPTS,
            generator_model="scripted-generator",
            critic_model="scripted-critic",
        )
        CONFIG.OUTPUT_PATH = root
        patches = (
            patch.object(Configuration, "LOGS_PATH", root / "logs"),
            patch(
                "scripts.generate_rm.setup_environment_and_engines",
                return_value=(facts, generator, critic),
            ),
            patch("scripts.generate_rm.compile_dfas", return_value=()),
            patch("scripts.generate_rm.build_compilation_result", return_value=compiled),
            patch.object(
                EnvironmentDescription,
                "from_file",
                side_effect=lambda _path, *, code=False: labeling if code else facts,
            ),
        )
        outcome, message = "accepted", ""
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            try:
                generate_compiler(CONFIG, labeling)
            except Exception as error:
                outcome, message = type(error).__name__, str(error)
        manifest_path = bundle_dir / "manifest.json"
        stamp = (
            json.loads(manifest_path.read_text(encoding="utf-8"))["provenance"]["stamp"]
            if manifest_path.exists()
            else {}
        )
        log = sorted((root / "logs").glob("*"))
        log_text = log[-1].read_text(encoding="utf-8") if log else ""
    failed = [line for line in log_text.splitlines() if "Generation failed" in line]
    ended = failed[-1].strip()[:200] if failed else ""
    return {
        "arm": "farm",
        "case": name,
        "outcome": outcome,
        "provider_error_text": bool(PROVIDER_ERROR.search(message + ended)),
        "proposal_requests": generator.proposals,
        "critic_requests": critic.reviews,
        "stamp.attempts": stamp.get("attempts"),
        "stamp.critic_interventions": stamp.get("critic_interventions"),
        "stamp.retries": stamp.get("retries"),
        "log_failure_line": ended,
        "message": message[:160],
    }


def main() -> None:
    last = ATTEMPTS
    rows = [
        run_farm(f"critic rejects every candidate ({last} limit)", review_script=("reject",)),
        run_farm(f"every proposal is invalid ({last} limit)", propose_script=("bad",)),
        run_farm(
            "invalid proposal and critic rejection alternate",
            propose_script=("bad", "ok") * (ATTEMPTS // 2),
            review_script=("reject",),
        ),
        run_farm("critic output is malformed every time", review_script=("bad",)),
        run_farm(
            f"{RERUNS} invalid proposals, then one rejected candidate, every attempt",
            propose_script=(("bad",) * RERUNS + ("ok",)) * ATTEMPTS,
            review_script=("reject",),
        ),
        run_farm(
            f"{RERUNS - 1} provider outages, then accepted",
            propose_script=("outage",) * (RERUNS - 1) + ("ok",),
        ),
        run_farm("provider is down for good", propose_script=("outage",)),
        run_farm(
            f"{RERUNS - 1} critic outages, then accepted (path left open)",
            review_script=("outage",) * (RERUNS - 1) + ("ok",),
        ),
        run_farm(
            f"{RERUNS} critic outages, then one rejection, every attempt",
            review_script=(("outage",) * RERUNS + ("reject",)) * ATTEMPTS,
        ),
        run_farm("critic is down for good", review_script=("outage",)),
        run_farm("authentication error (not retryable)", propose_script=("immediate",)),
        run_arm_fm(f"critic rejects every round ({last} limit)", ["ok"], critic="reject"),
        run_arm_fm(f"every machine is unparseable ({last} limit)", ["bad"]),
        run_arm_fm(
            f"{RERUNS - 1} provider outages, then accepted",
            ["outage"] * (RERUNS - 1) + ["ok"],
        ),
        run_arm_fm("provider is down for good", ["outage"]),
        run_arm_fm("critic is down for good", ["ok"], critic="outage"),
        run_arm_fm("authentication error (not retryable)", ["immediate"]),
    ]
    report = json.dumps(
        {"attempts_setting": ATTEMPTS, "outage_retries": RERUNS, "rows": rows}, indent=2
    )
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(report + "\n", encoding="utf-8")
    print(report)


main()
