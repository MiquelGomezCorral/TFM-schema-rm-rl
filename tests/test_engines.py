"""Checks for the shared engine workflow and provider configuration."""

import json
import os
import subprocess
import unittest
from unittest.mock import ANY, patch

from nl2ltl.declare.base import TemplateEnum

from src.arm_fm.generation import _extract_artifact
from src.compiler import materialize_proposal, parse_paper_reward_machine
from src.engines import (
    AntigravityEngine,
    GenericEngine,
    ImmediateEngineError,
    OpenAIEngine,
    OpenCodeEngine,
    RetryableEngineError,
)
from src.engines.errors import ProposalValidationError
from src.engines.structured import SUPPORTED_TEMPLATES, parse_proposal, proposal_schema
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
            "translate",
            "propose_task",
            "propose",
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
        self.assertTrue(engine.review_candidate("Finish", "[]", "REWARD_MACHINE:").accepted)

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

    def test_generic_engine_tags_states(self) -> None:
        requests = []

        def request(model, system, user, schema, name):
            return '{"accepted":true,"feedback":"ok"}'

        def request_text(model, system, user):
            requests.append(user)
            return '["first progress", "task satisfied"]'

        engine = GenericEngine(ENVIRONMENT, "test-model", "Test", request, request_text)

        descriptions = engine.describe_states(
            "Finish",
            '[{"pattern": "Existence"}]',
            "REWARD_MACHINE:",
            "[]",
            ("u0", "u1"),
        )

        self.assertEqual(descriptions, ("first progress", "task satisfied"))
        self.assertIn('["u0", "u1"]', requests[0])
        self.assertIn("### Reward Machine", requests[0])
        self.assertIn('"pattern": "Existence"', requests[0])

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
                engine_for(response).describe_states("Finish", "[]", "m", "[]", nodes)

        accepted = engine_for('[" first ", "second"]')
        self.assertEqual(
            accepted.describe_states("Finish", "[]", "m", "[]", nodes),
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
        self.assertTrue(engine.review_candidate("Finish", proposal, "REWARD_MACHINE:").accepted)
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
        self.assertEqual(command[command.index("--thinking") + 1], "minimal")
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
