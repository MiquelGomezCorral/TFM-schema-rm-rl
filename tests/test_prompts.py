"""Checks for the packaged prompt interface."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.config import Configuration
from src.prompts import read_prompt, read_user_prompt


class PromptTests(unittest.TestCase):
    def setUp(self):
        self.log_directory = TemporaryDirectory()
        self.addCleanup(self.log_directory.cleanup)
        self.logs_patch = patch.object(
            Configuration, "LOGS_PATH", Path(self.log_directory.name)
        )
        self.addCleanup(self.logs_patch.stop)
        self.logs_patch.start()

    def test_prompts_load_render_and_validate(self) -> None:
        environment = "# Demo\n\n## Propositions\n- `done`: The task is done."
        creator = read_user_prompt(
            "creator",
            environment_markdown=environment,
            task="Eventually finish.",
            case_specific="The episode is finite.",
            history='[{"proposal":"old","feedback":"try again"}]',
        )
        reviewer = read_user_prompt(
            "ltlf_reviewer",
            environment_markdown=environment,
            task="Eventually finish.",
            candidate_proposal='{"clauses": []}',
        )

        self.assertTrue(read_prompt("creator"))
        self.assertTrue(read_prompt("ltlf_reviewer"))
        self.assertIn("Eventually finish.", creator)
        self.assertIn("The episode is finite.", creator)
        self.assertIn("try again", creator)
        self.assertIn('{"clauses": []}', reviewer)
        self.assertIn("None.", reviewer)
        self.assertNotIn("${", creator + reviewer)
        self.assertTrue(read_prompt("rm_reviewer"))
        rm_reviewer = read_user_prompt(
            "rm_reviewer",
            environment_markdown=environment,
            task="task",
            candidate_rm='{"s": "0"}',
        )
        self.assertIn('{"s": "0"}', rm_reviewer)

        with self.assertRaises(ValueError):
            read_user_prompt("creator", environment_markdown="", task="task")
        with self.assertRaises(ValueError):
            read_user_prompt(
                "ltlf_reviewer",
                environment_markdown=environment,
                task="task",
                candidate_proposal="",
            )

    def test_prompt_defaults_are_independent(self) -> None:
        first = Configuration()
        second = Configuration()

        first.PROMPTS["creator"] = "changed"

        self.assertEqual(second.PROMPTS["creator"], "reward-ltlf-creator")
        self.assertIsNot(first.PROMPTS, second.PROMPTS)


if __name__ == "__main__":
    unittest.main()
