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
            state_descriptions='{"u0": "start"}',
        )
        self.assertIn('{"s": "0"}', rm_reviewer)
        self.assertIn('{"u0": "start"}', rm_reviewer)

        with self.assertRaises(ValueError):
            read_user_prompt("creator", environment_markdown="", task="task")
        with self.assertRaises(ValueError):
            read_user_prompt(
                "ltlf_reviewer",
                environment_markdown=environment,
                task="task",
                candidate_proposal="",
            )

    def test_tagger_prompt_renders_the_ordered_tagging_context(self) -> None:
        clauses = '[{"normalized_clause": "finish", "pattern": "Existence"}]'
        tagger = read_user_prompt(
            "rm_tagger",
            environment_markdown="# Demo",
            task="Finish",
            clauses_json=clauses,
            reward_machine="REWARD_MACHINE:\nSTATES: u0, u1",
            rejecting_states_json="[]",
            nodes_json='["u0", "u1"]',
        )

        self.assertTrue(read_prompt("rm_tagger"))
        self.assertIn("Finish", tagger)
        self.assertIn(clauses, tagger)
        self.assertIn('["u0", "u1"]', tagger)
        self.assertNotIn("${", tagger)
        with self.assertRaises(ValueError):
            read_user_prompt(
                "rm_tagger",
                environment_markdown="",
                task="Finish",
                clauses_json=clauses,
                reward_machine="REWARD_MACHINE:",
                rejecting_states_json="[]",
                nodes_json='["u0"]',
            )

    def test_compiler_labeling_prompts_render_grounded_context(self) -> None:
        values = dict(
            environment_markdown="# Demo\n## Propositions\n- `done`: Finished",
            task="Finish after starting",
            clauses_json='[{"normalized_clause": "finish"}]',
            reward_machine="REWARD_MACHINE:\nSTATES: u0, u1",
            state_descriptions_json='{"u0": "start", "u1": "done"}',
            nodes_json='["u0", "u1"]',
            propositions_json='{"done": "Finished"}',
            api="env.grid.get(x, y), env.agent_pos",
        )
        generator = read_user_prompt("labeling_generator", **values, history="")
        reviewer = read_user_prompt(
            "labeling_reviewer", **values, labeling="def done(env):\n    return True\n"
        )

        self.assertTrue(read_prompt("labeling_generator"))
        self.assertTrue(read_prompt("labeling_reviewer"))
        for rendered in (generator, reviewer):
            self.assertNotIn("${", rendered)
            self.assertIn("REWARD_MACHINE", rendered)
            self.assertIn('["u0", "u1"]', rendered)
            self.assertIn('{"done": "Finished"}', rendered)
        self.assertIn("None.", generator)
        self.assertIn("def done(env)", reviewer)
        with self.assertRaises(ValueError):
            read_user_prompt("labeling_reviewer", **values, labeling="")

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
