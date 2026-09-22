"""Checks for the packaged prompt interface."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.config import Configuration
from src.prompts import read_arm_fm_prompt, read_prompt, read_user_prompt


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

    def test_arm_fm_rm_prompt_declares_runtime_guard_syntax(self) -> None:
        prompt = read_arm_fm_prompt("rm_generator")

        self.assertIn("conjunction `&`, disjunction `|`, and negation `!`", prompt)
        self.assertIn("never\nwrite English `and`, `or`, or `not` in guard conditions", prompt)

    def test_arm_fm_labeling_prompt_declares_expression_only_syntax(self) -> None:
        prompt = read_arm_fm_prompt("labeling_generator")

        self.assertIn("Use expression-only predicates: no `if`, `for`, `while`, assignments", prompt)
        self.assertIn("approved `any`/`all` comprehensions for scans", prompt)
        self.assertIn("Never call a sibling predicate or `.get` on", prompt)
        self.assertIn("for cell in [env.grid.get(x, y)]", prompt)
        self.assertIn("exactly one `return` statement and no other statements", prompt)
        self.assertIn("def event_name(env): return", prompt)

    def test_arm_fm_labeling_critic_requires_all_declared_predicates(self) -> None:
        prompt = read_arm_fm_prompt("labeling_critic")

        self.assertIn("an unused declared", prompt)
        self.assertIn("must never be rejected for being unused", prompt)


if __name__ == "__main__":
    unittest.main()
