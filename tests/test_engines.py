"""Checks for the shared engine workflow and provider configuration."""

import json
import os
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import ANY, Mock, patch

from httpx import Request, Response
from nl2ltl.declare.base import TemplateEnum
from openai import BadRequestError

from src.arm_fm.generation import _extract_artifact, _refine_labeling, request_state_descriptions
from src.benchmark.labeling_repair import Check, repair_prompt
from src.compiler import (
    PaperRewardMachine,
    RuntimeTransition,
    machine_view,
    materialize_proposal,
    parse_paper_reward_machine,
    serialize_paper_reward_machine,
)
from src.compiler.reward_machine import EndJudgment
from src.config import Configuration
from src.engines import (
    CONTEXT_EXCEEDED,
    AntigravityEngine,
    ContextExceededError,
    GenericEngine,
    ImmediateEngineError,
    OpenAIEngine,
    OpenCodeEngine,
    RetryableEngineError,
)
from src.engines.errors import CriticValidationError, ProposalValidationError
from src.engines.structured import (
    SUPPORTED_TEMPLATES,
    parse_critic,
    parse_proposal,
    proposal_schema,
)
from src.models import EnvironmentDescription

ENVIRONMENT = EnvironmentDescription.from_markdown(
    "# Demo\n## Propositions\n- `done`: Finished",
    source="demo.md",
)

# IBM's formula for each template over propositions a and b, in FL-AT's flat syntax.
IBM_FLAT_FORMULAS = {
    "Existence": "(Fa)",
    "ExistenceTwo": "(F(a&(X(Fa))))",
    "Absence": "(~(Fa))",
    "RespondedExistence": "((Fa)->(Fb))",
    "Response": "(G(a->(Fb)))",
    "Precedence": "(((~b)Ua)|(G(~b)))",
    "ChainResponse": "(G(a->(Xb)))",
    "NotCoExistence": "((Fa)->(~(Fb)))",
}


class EngineTests(unittest.TestCase):
    def test_provider_classes_inherit_the_shared_workflow(self) -> None:
        methods = {
            "propose_task",
            "review_candidate",
            "describe_states",
            "_request_structured",
        }

        for provider in (OpenAIEngine, OpenCodeEngine, AntigravityEngine):
            self.assertTrue(methods.isdisjoint(provider.__dict__))

    def test_every_ibm_template_validates_with_its_arity_and_uses_ibm_formulas(self) -> None:
        environment = EnvironmentDescription.from_markdown(
            "# Demo\n## Propositions\n- `a`: First\n- `b`: Second", source="demo.md"
        )
        variants = proposal_schema("Task", environment)["properties"]["clauses"]["items"]["anyOf"]
        patterns = {name for item in variants for name in item["properties"]["pattern"]["enum"]}
        self.assertEqual(patterns, {template.value for template in TemplateEnum})
        self.assertEqual(set(IBM_FLAT_FORMULAS), set(SUPPORTED_TEMPLATES))

        for pattern, (_, arity) in SUPPORTED_TEMPLATES.items():
            clause = {
                "normalized_clause": pattern,
                "pattern": pattern,
                "propositions": ["a", "b"][:arity],
                "priority": "soft",
            }
            selections = parse_proposal(json.dumps({"clauses": [clause]}), environment, "Test")
            proposal = materialize_proposal("Task", selections)
            self.assertEqual(proposal.clauses[0].ltlf_formula, IBM_FLAT_FORMULAS[pattern])

            clause["propositions"] = ["a", "b"][: 3 - arity]
            with self.assertRaises(ProposalValidationError):
                parse_proposal(json.dumps({"clauses": [clause]}), environment, "Test")

        valid = {
            "normalized_clause": "a before b",
            "pattern": "Precedence",
            "propositions": ["a", "b"],
            "priority": "hard",
        }
        for invalid in ({"propositions": ["a", "a"]}, {"priority": "none"}):
            with self.assertRaises(ProposalValidationError):
                parse_proposal(json.dumps({"clauses": [valid | invalid]}), environment, "Test")

    @patch("src.engines.provider_engines.OpenAI")
    def test_providers_read_their_own_environment(self, openai) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "openai-key"}, clear=True):
            OpenAIEngine(ENVIRONMENT, "openai-model")
        openai.assert_called_once_with(api_key="openai-key", max_retries=0)

        openai.reset_mock()
        with patch.dict(
            os.environ,
            {
                "OPENCODE_API_KEY": "opencode-key",
                "OPENCODE_BASE_URL": "https://example.test/v1",
            },
            clear=True,
        ):
            OpenCodeEngine(ENVIRONMENT, "opencode-model")
        openai.assert_called_once_with(
            api_key="opencode-key",
            base_url="https://example.test/v1",
            max_retries=0,
            # The adapter adds a per-request session header.
            default_headers={"x-opencode-session": ANY},
        )

    @patch("src.engines.provider_engines.subprocess.run")
    def test_antigravity_returns_structured_output_without_using_tools(self, run) -> None:
        response = {
            "clauses": [
                {
                    "normalized_clause": "finish",
                    "pattern": "Existence",
                    "propositions": ["done"],
                    "priority": "hard",
                }
            ],
        }
        run.return_value = subprocess.CompletedProcess(
            ["agy"],
            0,
            stdout="\n".join(
                [
                    json.dumps(
                        {
                            "event": "init",
                            "init": {
                                "agent": "schema-rm-provider",
                                "tools": ["view_file"],
                            },
                        }
                    ),
                    json.dumps({"event": "assistant", "message": {"content": "ignored"}}),
                    json.dumps(
                        {
                            "event": "result",
                            "result": {
                                "status": "SUCCESS",
                                "structured_output": response,
                            },
                        }
                    ),
                ]
            ),
            stderr="",
        )

        engine = AntigravityEngine(ENVIRONMENT, "gemini-model")
        proposal = engine.propose_task("Finish")

        self.assertEqual(proposal[0].normalized_clause, "finish")
        call = run.call_args
        command = call.args[0]
        self.assertNotIn("--print", command)
        self.assertIn("--input-format", command)
        self.assertIn("stream-json", command)
        self.assertIn("--output-format", command)
        self.assertIn("--json-schema", command)
        self.assertIn("--model", command)
        self.assertIn("gemini-model", command)
        self.assertIn("--agent", command)
        self.assertIn("schema-rm-provider", command)
        self.assertIn("--disable-slash-commands", command)
        self.assertNotIn("--dangerously-skip-permissions", command)
        self.assertFalse(call.kwargs["shell"])
        self.assertTrue(call.kwargs["capture_output"])
        self.assertTrue(call.kwargs["text"])
        self.assertEqual(call.kwargs["timeout"], 305)

        event = json.loads(call.kwargs["input"])
        application = json.loads(event["message"]["content"])
        self.assertEqual(event["event"], "user")
        self.assertEqual(set(application), {"application_instructions", "application_input"})
        self.assertEqual(call.kwargs["cwd"].name, "TFM-schema-rm-rl")
        schema = json.loads(command[command.index("--json-schema") + 1])
        self.assertEqual(schema["required"], ["clauses"])

        critic_response = {"accepted": True, "feedback": "looks good"}
        run.return_value = subprocess.CompletedProcess(
            ["agy"],
            0,
            stdout="\n".join(
                [
                    json.dumps(
                        {
                            "event": "init",
                            "init": {
                                "agent": "schema-rm-provider",
                                "tools": ["view_file"],
                            },
                        }
                    ),
                    json.dumps(
                        {
                            "event": "result",
                            "result": {
                                "status": "SUCCESS",
                                "structured_output": critic_response,
                            },
                        }
                    ),
                ]
            ),
            stderr="",
        )
        self.assertTrue(engine.review_candidate("Finish", "[]", "REWARD_MACHINE:", ()).accepted)

    @patch("src.engines.provider_engines.subprocess.run")
    def test_antigravity_provider_errors_are_safe_and_typed(self, run) -> None:
        engine = AntigravityEngine(ENVIRONMENT, "gemini-model")
        cases = (
            (FileNotFoundError(), ImmediateEngineError),
            (subprocess.TimeoutExpired(["agy"], 305), RetryableEngineError),
        )
        for failure, expected in cases:
            with self.subTest(failure=type(failure).__name__):
                run.side_effect = failure
                with self.assertRaises(expected):
                    engine.propose_task("Finish")

        run.side_effect = None
        run.return_value = subprocess.CompletedProcess(
            ["agy"], 1, stdout="", stderr="authentication required"
        )
        with self.assertRaisesRegex(ImmediateEngineError, "authentication failed"):
            engine.propose_task("Finish")

        run.return_value = subprocess.CompletedProcess(
            ["agy"],
            0,
            stdout="\n".join(
                [
                    json.dumps(
                        {
                            "event": "init",
                            "init": {
                                "agent": "schema-rm-provider",
                                "tools": ["view_file"],
                            },
                        }
                    ),
                    json.dumps(
                        {
                            "event": "result",
                            "result": {
                                "status": "FAILURE",
                                "error": "model unavailable",
                            },
                        }
                    ),
                ]
            ),
            stderr="",
        )
        with self.assertRaisesRegex(ImmediateEngineError, "model is unavailable"):
            engine.propose_task("Finish")

        run.return_value = subprocess.CompletedProcess(
            ["agy"],
            2,
            stdout="\n".join(
                [
                    json.dumps(
                        {
                            "event": "result",
                            "result": {"status": "FAILURE", "error": "login required"},
                        }
                    ),
                ]
            ),
            stderr="",
        )
        with self.assertRaisesRegex(ImmediateEngineError, "authentication failed"):
            engine.propose_task("Finish")

        run.return_value = subprocess.CompletedProcess(
            ["agy"],
            2,
            stdout=json.dumps(
                {
                    "event": "result",
                    "result": {"status": "FAILURE", "error": "invalid model"},
                }
            ),
            stderr="",
        )
        with self.assertRaisesRegex(ImmediateEngineError, "model is unavailable"):
            engine.propose_task("Finish")

    @patch("src.engines.provider_engines.subprocess.run")
    def test_antigravity_rejects_invalid_streams(self, run) -> None:
        engine = AntigravityEngine(ENVIRONMENT, "gemini-model")
        outputs = (
            "not-json",
            json.dumps({"event": "init", "init": {"tools": "invalid"}}),
            json.dumps(
                {
                    "event": "init",
                    "init": {
                        "agent": "wrong-agent",
                        "tools": [],
                    },
                }
            ),
            "\n".join(
                [
                    json.dumps(
                        {
                            "event": "init",
                            "init": {
                                "agent": "schema-rm-provider",
                                "tools": ["view_file"],
                            },
                        }
                    ),
                    json.dumps(
                        {
                            "event": "result",
                            "result": {"status": "FAILURE", "error": "login required"},
                        }
                    ),
                ]
            ),
            "\n".join(
                [
                    json.dumps(
                        {
                            "event": "init",
                            "init": {
                                "agent": "schema-rm-provider",
                                "tools": ["view_file"],
                            },
                        }
                    ),
                    json.dumps({"event": "result", "result": {"status": "SUCCESS"}}),
                ]
            ),
            "\n".join(
                [
                    json.dumps(
                        {
                            "event": "init",
                            "init": {
                                "agent": "schema-rm-provider",
                                "tools": ["view_file"],
                            },
                        }
                    ),
                    json.dumps(
                        {
                            "event": "result",
                            "result": {"status": "SUCCESS", "structured_output": []},
                        }
                    ),
                ]
            ),
        )
        for output in outputs:
            with self.subTest(output=output):
                run.return_value = subprocess.CompletedProcess(["agy"], 0, stdout=output, stderr="")
                with self.assertRaises(ImmediateEngineError):
                    engine.propose_task("Finish")

    def test_critic_verdict_must_agree_with_its_feedback_prefix(self) -> None:
        def verdict(accepted: bool, feedback: str) -> str:
            return json.dumps({"accepted": accepted, "feedback": feedback})

        for accepted, feedback in (
            (False, "no changes needed: the clauses are right"),
            (True, "CHANGES REQUIRED: add Existence(a)"),
        ):
            with self.subTest(feedback=feedback), self.assertRaises(CriticValidationError):
                parse_critic(verdict(accepted, feedback))

        # Consistent verdicts, and a phrase that only appears later, are left alone.
        self.assertFalse(parse_critic(verdict(False, "CHANGES REQUIRED: add it")).accepted)
        self.assertTrue(parse_critic(verdict(True, "NO CHANGES NEEDED: ok")).accepted)
        late = "The clause is wrong, so this is not a case of NO CHANGES NEEDED."
        self.assertFalse(parse_critic(verdict(False, late)).accepted)

    def test_generic_engine_uses_the_shared_prompt_pipeline(self) -> None:
        responses = iter(
            [
                '{"clauses":[{"normalized_clause":"finish","pattern":"Existence",'
                '"propositions":["done"],"priority":"hard"}]}',
                '{"accepted":true,"feedback":"candidate ok"}',
            ]
        )
        requests = []

        def request(model, system, user, schema, name):
            requests.append((model, system, user, schema, name))
            return next(responses)

        engine = GenericEngine(ENVIRONMENT, "test-model", "Test", request)

        proposal = engine.propose_task("Finish")
        review = engine.review_candidate(
            "Finish", '[{"pattern": "Existence"}]', "REWARD_MACHINE:", ("Rule-only task",)
        )

        self.assertEqual(proposal[0].normalized_clause, "finish")
        self.assertTrue(review.accepted)
        self.assertEqual([request[-1] for request in requests], ["declare_proposal", "critic"])
        self.assertIn('[{"pattern": "Existence"}]', requests[1][2])
        self.assertIn("- Rule-only task", requests[1][2])

    def test_machine_over_the_prompt_bound_reaches_the_prompts_as_a_state_list(self) -> None:
        states = tuple(f"u{index}" for index in range(301))
        transitions = tuple(
            RuntimeTransition("u0", "a&!b", state, 1.0 if state == "u1" else 0.0)
            for state in states[1:]
        )
        machine = PaperRewardMachine(states, "u0", transitions, final_states=("u7",))
        text = serialize_paper_reward_machine(machine)
        bundle = SimpleNamespace(
            manifest=SimpleNamespace(
                inputs={"environment_markdown": "env"},
                task="Finish",
                api_definitions={"labeling": "api"},
            ),
            reward_machine=machine,
            labeling_source="labeling",
        )
        requests = []
        repairs = []
        sent, descriptions = [], []

        def request(model, system, user, schema, name):
            requests.append(user)
            return '{"accepted":true,"feedback":"ok"}'

        def request_text(model, system, user):
            sent.append(user)
            asked = user.rsplit("state keys:\n", 1)[1].split(", ")
            return json.dumps(dict.fromkeys(asked, "text"))

        engine = GenericEngine(ENVIRONMENT, "test-model", "Test", request, request_text)
        for bound in (len(text), len(text) - 1):  # the text at the bound, then one over it
            with patch.object(Configuration, "MACHINE_PROMPT_MAX_CHARS", bound):
                engine.review_candidate("Finish", "[]", text, ())
                engine.review_labeling(
                    "Finish",
                    text,
                    "api",
                    "labeling",
                    clauses_json="[]",
                    state_descriptions_json="{}",
                    nodes_json="[]",
                    propositions_json="{}",
                )
                repairs.append(repair_prompt(bundle, Check("missing")))
                request_state_descriptions(engine, "env", "Finish", machine, [])
                descriptions.append(sent.copy())
                sent.clear()

        # Under the bound one description request carries the whole text.
        for whole in (requests[0], requests[1], repairs[0], *descriptions[0]):
            self.assertIn(text, whole)
        self.assertEqual(len(descriptions[0]), 1)
        # Over it, the descriptions come in batches of 20 states, each with only its own lines.
        batches = descriptions[1]
        self.assertEqual(len(batches), 16)
        for number, batch in enumerate(batches):
            asked = states[20 * number : 20 * (number + 1)]
            lines = batch.split("STATE_LIST:\n")[1].split("\n\nReturn")[0].splitlines()
            self.assertEqual([line.split(":")[0] for line in lines], list(asked))
            self.assertNotIn("more state", batch)
        for summary in (requests[2], requests[3], repairs[1], batches[0]):
            self.assertIn("FINAL_STATES: u7", summary)
            self.assertIn("(301 in all)", summary)
            self.assertIn("TRANSITION_FUNCTION: 300 rows, not listed", summary)
            self.assertIn("REWARD_FUNCTION: 1 row, not listed", summary)
            self.assertNotIn("(u0, a&!b)", summary)
            self.assertIn("u0: start\n", summary)
            self.assertIn("u1: in progress; shortest path from the start: a\n", summary)
            self.assertIn("u7: final: every hard goal is reached; shortest path", summary)
        # The critics and the labeling prompts list the first 300 states.
        for summary in (requests[2], requests[3], repairs[1]):
            self.assertIn("u299: in progress", summary)
            self.assertNotIn("u300: in progress", summary)
            self.assertIn("(1 more state not listed)", summary)

    def test_state_list_shows_the_last_steps_of_a_path_and_marks_other_guards(self) -> None:
        steps = ("a", "b&!c", "d", "!(a&b)", "e", "f")
        transitions = tuple(
            RuntimeTransition(f"u{index}", guard, f"u{index + 1}")
            for index, guard in enumerate(steps)
        )
        machine = PaperRewardMachine(
            tuple(f"u{index}" for index in range(7)), "u0", transitions, final_states=("u6",)
        )

        with patch.object(Configuration, "MACHINE_PROMPT_MAX_CHARS", 1):
            view = machine_view(serialize_paper_reward_machine(machine))

        self.assertIn("u2: in progress; shortest path from the start: a then b\n", view)
        self.assertIn(
            "u6: final: every hard goal is reached; shortest path from the start: "
            "... then d then guard over a, b then e then f\n",
            view,
        )

    def test_state_list_says_which_stages_a_state_still_owes(self) -> None:
        transitions = (RuntimeTransition("u0", "a", "u1"), RuntimeTransition("u1", "b", "u2"))
        judgment = EndJudgment(
            accepting=("u2",),
            pending=(("u0", 1, 0), ("u1", 2, 1)),
            hard_failed_reward=-1.0,
            soft_failed_reward=-0.5,
        )
        machine = PaperRewardMachine(("u0", "u1", "u2"), "u0", transitions, judgment=judgment)

        with patch.object(Configuration, "MACHINE_PROMPT_MAX_CHARS", 1):
            view = machine_view(serialize_paper_reward_machine(machine))

        self.assertIn("u0: start; owes 1 hard and 0 soft stages\n", view)
        self.assertIn("u1: in progress; owes 2 hard and 1 soft stages; shortest path", view)
        self.assertIn("u2: in progress; owes nothing; shortest path", view)

    def test_generic_engine_tags_states(self) -> None:
        requests = []

        def request_text(model, system, user):
            requests.append(user)
            return '["first progress", "task satisfied"]'

        engine = GenericEngine(ENVIRONMENT, "test-model", "Test", lambda *args: "", request_text)

        descriptions = engine.describe_states(
            "Finish",
            '[{"pattern": "Existence"}]',
            "REWARD_MACHINE:",
            ("u0", "u1"),
        )

        self.assertEqual(descriptions, ("first progress", "task satisfied"))
        self.assertIn('["u0", "u1"]', requests[0])
        self.assertIn("### Reward Machine", requests[0])
        self.assertIn('"pattern": "Existence"', requests[0])

    @patch("src.engines.generic_engine.sleep")
    @patch.object(GenericEngine, "_renew_session")
    def test_transient_bad_request_is_repeated_before_it_counts_as_a_failure(
        self, renew_session, sleep
    ) -> None:
        response = Response(400, request=Request("POST", "https://provider.test/v1"))
        failure = BadRequestError("Error code: 400", response=response, body=None)
        request_text = Mock(side_effect=[failure, failure, "finished"])
        engine = GenericEngine(ENVIRONMENT, "test-model", "Test", lambda *args: "", request_text)

        self.assertEqual(engine.request_text("system", "user"), "finished")
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(renew_session.call_count, 2)

    @patch("src.engines.generic_engine.sleep")
    @patch.object(GenericEngine, "_renew_session")
    def test_context_overflow_fails_at_once_naming_the_stage(self, renew_session, sleep) -> None:
        response = Response(400, request=Request("POST", "https://provider.test/v1"))
        # The three bodies the provider sent for one overflow (farm-questions/probe_tokens.out):
        # at reasoning none, and at reasoning low with another code and with none.
        bodies = {
            "none": {
                "message": "Your request resulted in more tokens than this model's maximum "
                "context length allows. Please reduce the length of the messages or run "
                "compaction.",
                "type": "invalid_request_error",
                "code": "context_length_exceeded",
            },
            "low, text only": {
                "type": "invalid_request_error",
                "message": "Upstream request failed: [400] This model's maximum context length "
                "is 1048576 tokens. However, your messages resulted in 1682839 tokens. Please "
                "reduce the length of the messages.",
            },
            "low, other code": {
                "type": "invalid_request_error",
                "code": "invalid_request_error",
                "message": "Upstream request failed: [invalid_request_error] The prompt is too "
                "long: 6518612, model maximum context length: 1048573",
            },
        }
        for name, body in bodies.items():
            with self.subTest(reasoning=name):
                renew_session.reset_mock()
                failure = BadRequestError(f"Error code: 400 - {body}", response=response, body=body)
                request = Mock(side_effect=failure)
                engine = GenericEngine(ENVIRONMENT, "test-model", "Test", request, lambda *args: "")

                with self.assertRaises(ContextExceededError) as raised:
                    engine.review_candidate("Finish", "[]", "REWARD_MACHINE:", ())

                self.assertEqual(request.call_count, 1)
                self.assertEqual(len(engine.calls), 1)
                self.assertEqual(renew_session.call_count, 0)
                self.assertTrue(str(raised.exception).startswith(f"critic-{CONTEXT_EXCEEDED}:"))
                # No "Error code" text, so generate-suite does not read it as a provider error.
                self.assertNotIn("Error code", str(raised.exception))

        # Every other stage stops the same way and names itself in the reason.
        stages = {
            "declare-proposal": lambda engine: engine.propose_task("Finish"),
            "rm-tagger": lambda engine: engine.describe_states("Finish", "[]", "RM", ("u0",)),
            "labeling-generator": lambda engine: engine.request_text(
                "system", "user", stage="labeling_generator"
            ),
            "labeling-critic": lambda engine: engine.review_labeling(
                "Finish",
                "RM",
                "api",
                "code",
                clauses_json="[]",
                state_descriptions_json="{}",
                nodes_json="[]",
                propositions_json="{}",
            ),
        }
        body = bodies["none"]
        failure = BadRequestError(f"Error code: 400 - {body}", response=response, body=body)
        for name, call in stages.items():
            with self.subTest(stage=name):
                request = Mock(side_effect=failure)
                engine = GenericEngine(ENVIRONMENT, "test-model", "Test", request, request)

                with self.assertRaises(ContextExceededError) as raised:
                    call(engine)

                self.assertEqual(request.call_count, 1)
                self.assertTrue(str(raised.exception).startswith(f"{name}-{CONTEXT_EXCEEDED}:"))

        # Any other 400 is still the sticky one: it repeats with a new session each time.
        other = BadRequestError("Error code: 400", response=response, body=None)
        request = Mock(side_effect=[other, other, '{"accepted": true, "feedback": "ok"}'])
        engine = GenericEngine(ENVIRONMENT, "test-model", "Test", request, lambda *args: "")
        renew_session.reset_mock()
        self.assertTrue(engine.review_candidate("Finish", "[]", "REWARD_MACHINE:", ()).accepted)
        self.assertEqual(renew_session.call_count, 2)

    @patch("src.arm_fm.generation.load_labeling_functions")
    @patch("src.arm_fm.generation.extract_labeling_code", return_value="source")
    def test_labeling_critic_overflow_is_not_refined_again(self, extract, load) -> None:
        request = Mock(return_value="candidate")
        review = Mock(side_effect=ContextExceededError(CONTEXT_EXCEEDED))
        attempts = []

        with self.assertRaises(ContextExceededError):
            _refine_labeling(("done",), request, review, attempts)

        self.assertEqual(request.call_count, 1)
        self.assertEqual(review.call_count, 1)
        self.assertEqual(attempts, [])

    def test_state_tagger_output_shapes_are_validated(self) -> None:
        nodes = ("u0", "u1")

        def engine_for(response):
            return GenericEngine(
                ENVIRONMENT,
                "test-model",
                "Test",
                lambda *args: "",
                lambda *args: response,
            )

        rejected = (
            "not json",
            '{"u0": "a", "u1": "b"}',
            '["only one"]',
            '["ok", 3]',
            '["ok", "   "]',
            '```json\n["ok", "two"]\n```',
        )
        for response in rejected:
            with (
                self.subTest(response=response),
                self.assertRaises(RetryableEngineError),
            ):
                engine_for(response).describe_states("Finish", "[]", "m", nodes)

        accepted = engine_for('[" first ", "second"]')
        self.assertEqual(
            accepted.describe_states("Finish", "[]", "m", nodes),
            ("first", "second"),
        )

    @patch("src.engines.provider_engines.subprocess.run")
    def test_opencode_go_pi_validates_proposal_and_critic(self, run) -> None:
        proposal = '{"clauses":[{"normalized_clause":"finish","pattern":"Existence","propositions":["done"],"priority":"hard"}]}'
        critic = '{"accepted":true,"feedback":"task is grounded"}'

        def event(text):
            return json.dumps(
                {
                    "type": "message_end",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": text}],
                    },
                }
            )

        run.side_effect = [
            subprocess.CompletedProcess(["pi"], 0, stdout=event(proposal), stderr=""),
            subprocess.CompletedProcess(["pi"], 0, stdout=event(critic), stderr=""),
        ]

        engine = OpenCodeEngine(ENVIRONMENT, "opencode-go/mimo-v2.5")
        self.assertEqual(engine.propose_task("Finish")[0].normalized_clause, "finish")
        self.assertTrue(engine.review_candidate("Finish", proposal, "REWARD_MACHINE:", ()).accepted)
        command = run.call_args_list[0].args[0]
        self.assertEqual(command[command.index("--model") + 1], "opencode-go/mimo-v2.5")
        for flag in (
            "--no-tools",
            "--no-extensions",
            "--no-context-files",
            "--no-session",
            "--mode",
            "json",
        ):
            self.assertIn(flag, command)
        self.assertEqual(command[command.index("--thinking") + 1], "off")
        self.assertEqual(run.call_args_list[0].kwargs["cwd"].name, "TFM-schema-rm-rl")

    @patch("src.engines.provider_engines.subprocess.run")
    def test_opencode_go_pi_returns_plain_artifacts_and_rejects_missing_text(self, run) -> None:
        artifact = "REWARD_MACHINE:\nSTATES: u0, u1\nINITIAL_STATE: u0\nFINAL_STATES: u1\nTRANSITION_FUNCTION:\n(u0, done) -> u1\nREWARD_FUNCTION:\n"
        run.return_value = subprocess.CompletedProcess(
            ["pi"],
            0,
            stdout=json.dumps(
                {
                    "type": "agent_end",
                    "messages": [
                        {
                            "role": "assistant",
                            "content": [{"type": "text", "text": artifact}],
                        }
                    ],
                }
            ),
            stderr="",
        )
        engine = OpenCodeEngine(ENVIRONMENT, "opencode-go/mimo-v2.5")
        output = engine.request_text("system", "user")
        machine = parse_paper_reward_machine(_extract_artifact(output))
        self.assertEqual(machine.states, ("u0", "u1"))

        run.return_value = subprocess.CompletedProcess(["pi"], 0, stdout="{}\n", stderr="")
        with self.assertRaises(ImmediateEngineError):
            engine.request_text("system", "user")


if __name__ == "__main__":
    unittest.main()
