"""Checks for the shared engine workflow and provider configuration."""

import os
import unittest
import json
import subprocess
from unittest.mock import patch

from src.engines import (
    AntigravityEngine,
    GenericEngine,
    ImmediateEngineError,
    OpenAIEngine,
    OpenCodeEngine,
    RetryableEngineError,
)
from src.models import EnvironmentDescription


ENVIRONMENT = EnvironmentDescription.from_markdown(
    "# Demo\n## Propositions\n- `done`: Finished",
    source="demo.md",
)


class EngineTests(unittest.TestCase):
    def test_provider_classes_inherit_the_shared_workflow(self) -> None:
        methods = {
            "translate",
            "propose_task",
            "propose",
            "review_task",
            "review_reward_machine",
            "_request_structured",
        }

        for provider in (OpenAIEngine, OpenCodeEngine, AntigravityEngine):
            self.assertTrue(methods.isdisjoint(provider.__dict__))

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
        )

    @patch("src.engines.provider_engines.subprocess.run")
    def test_antigravity_returns_structured_output_without_using_tools(self, run) -> None:
        response = {
            "clauses": [{
                "normalized_clause": "finish",
                "pattern": "Existence",
                "propositions": ["done"],
                "priority": "none",
            }],
        }
        run.return_value = subprocess.CompletedProcess(
            ["agy"],
            0,
            stdout="\n".join([
                json.dumps({"event": "init", "init": {
                    "agent": "schema-rm-provider", "tools": ["view_file"],
                }}),
                json.dumps({"event": "assistant", "message": {"content": "ignored"}}),
                json.dumps({"event": "result", "result": {"status": "SUCCESS", "structured_output": response}}),
            ]),
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
            stdout="\n".join([
                json.dumps({"event": "init", "init": {
                    "agent": "schema-rm-provider", "tools": ["view_file"],
                }}),
                json.dumps({"event": "result", "result": {"status": "SUCCESS", "structured_output": critic_response}}),
            ]),
            stderr="",
        )
        self.assertTrue(engine.review_task("Finish", "{}").accepted)

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
            stdout="\n".join([
                json.dumps({"event": "init", "init": {
                    "agent": "schema-rm-provider", "tools": ["view_file"],
                }}),
                json.dumps({"event": "result", "result": {"status": "FAILURE", "error": "model unavailable"}}),
            ]),
            stderr="",
        )
        with self.assertRaisesRegex(ImmediateEngineError, "model is unavailable"):
            engine.propose_task("Finish")

        run.return_value = subprocess.CompletedProcess(
            ["agy"],
            2,
            stdout="\n".join([
                json.dumps({"event": "result", "result": {"status": "FAILURE", "error": "login required"}}),
            ]),
            stderr="",
        )
        with self.assertRaisesRegex(ImmediateEngineError, "authentication failed"):
            engine.propose_task("Finish")

        run.return_value = subprocess.CompletedProcess(
            ["agy"],
            2,
            stdout=json.dumps({
                "event": "result",
                "result": {"status": "FAILURE", "error": "invalid model"},
            }),
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
            json.dumps({"event": "init", "init": {
                "agent": "wrong-agent", "tools": [],
            }}),
            "\n".join([
                json.dumps({"event": "init", "init": {
                    "agent": "schema-rm-provider", "tools": ["view_file"],
                }}),
                json.dumps({"event": "result", "result": {"status": "FAILURE", "error": "login required"}}),
            ]),
            "\n".join([
                json.dumps({"event": "init", "init": {
                    "agent": "schema-rm-provider", "tools": ["view_file"],
                }}),
                json.dumps({"event": "result", "result": {"status": "SUCCESS"}}),
            ]),
            "\n".join([
                json.dumps({"event": "init", "init": {
                    "agent": "schema-rm-provider", "tools": ["view_file"],
                }}),
                json.dumps({"event": "result", "result": {"status": "SUCCESS", "structured_output": []}}),
            ]),
        )
        for output in outputs:
            with self.subTest(output=output):
                run.return_value = subprocess.CompletedProcess(
                    ["agy"], 0, stdout=output, stderr=""
                )
                with self.assertRaises(ImmediateEngineError):
                    engine.propose_task("Finish")

    def test_generic_engine_uses_the_shared_prompt_pipeline(self) -> None:
        responses = iter(
            [
                '{"clauses":[{"normalized_clause":"finish","pattern":"Existence",'
                '"propositions":["done"],"priority":"none"}]}',
                '{"accepted":true,"feedback":"task ok"}',
                '{"accepted":true,"feedback":"machine ok"}',
            ]
        )
        requests = []

        def request(model, system, user, schema, name):
            requests.append((model, system, user, schema, name))
            return next(responses)

        engine = GenericEngine(ENVIRONMENT, "test-model", "Test", request)

        proposal = engine.propose_task("Finish")
        task_review = engine.review_task("Finish", '{"clauses": []}')
        machine_review = engine.review_reward_machine("Finish", '{"states": [0]}')

        self.assertEqual(proposal[0].normalized_clause, "finish")
        self.assertTrue(task_review.accepted)
        self.assertTrue(machine_review.accepted)
        self.assertEqual(
            [request[-1] for request in requests],
            ["declare_proposal", "task_critic", "rm_critic"],
        )


if __name__ == "__main__":
    unittest.main()
