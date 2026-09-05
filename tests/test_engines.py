"""Checks for the shared engine workflow and provider configuration."""

import os
import unittest
from unittest.mock import patch

from src.engines import GenericEngine, OpenAIEngine, OpenCodeEngine
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

        for provider in (OpenAIEngine, OpenCodeEngine):
            self.assertTrue(methods.isdisjoint(provider.__dict__))

    @patch("src.engines.openai_engine.OpenAI")
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
