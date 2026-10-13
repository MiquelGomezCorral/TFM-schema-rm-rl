"""Checks for the packaged prompt interface."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.config import Configuration
from src.prompts import read_prompt, render_prompt


class PromptTests(unittest.TestCase):
    def setUp(self):
        self.log_directory = TemporaryDirectory()
        self.addCleanup(self.log_directory.cleanup)
        self.logs_patch = patch.object(Configuration, "LOGS_PATH", Path(self.log_directory.name))
        self.addCleanup(self.logs_patch.stop)
        self.logs_patch.start()

    def test_prompts_load_render_and_validate(self) -> None:
        environment = "# Demo\n\n## Propositions\n- `done`: The task is done."
        creator = render_prompt(
            "compiler",
            "creator",
            environment_markdown=environment,
            task="Eventually finish.",
            history='[{"proposal":"old","feedback":"try again"}]',
        )
        critic = render_prompt(
            "compiler",
            "critic",
            environment_markdown=environment,
            task="Eventually finish.",
            clauses_json='{"clauses": []}',
            reward_machine='{"s": "0"}',
            warnings="- Rule-only task",
        )
        no_warnings = render_prompt(
            "compiler",
            "critic",
            environment_markdown=environment,
            task="task",
            clauses_json="[]",
            reward_machine="rm",
        )

        self.assertTrue(read_prompt("compiler", "creator"))
        self.assertTrue(read_prompt("compiler", "critic"))
        self.assertIn("Eventually finish.", creator)
        self.assertIn("try again", creator)
        self.assertIn('{"clauses": []}', critic)
        self.assertIn('{"s": "0"}', critic)
        self.assertIn("- Rule-only task", critic)
        self.assertIn("None.", no_warnings)
        self.assertNotIn("${", creator + critic)
        for agent in ("creator", "critic"):
            system = read_prompt("compiler", agent)
            self.assertNotIn("${", system)
            self.assertIn("`NotCoExistence(a, b)`", system)

        with self.assertRaises(ValueError):
            render_prompt("compiler", "creator", environment_markdown="", task="task")
        with self.assertRaises(ValueError):
            render_prompt(
                "compiler",
                "critic",
                environment_markdown=environment,
                task="task",
                clauses_json="",
                reward_machine="rm",
            )

    def test_tagger_prompt_renders_the_ordered_tagging_context(self) -> None:
        clauses = '[{"normalized_clause": "finish", "pattern": "Existence"}]'
        tagger = render_prompt(
            "compiler",
            "rm_tagger",
            environment_markdown="# Demo",
            task="Finish",
            clauses_json=clauses,
            reward_machine="REWARD_MACHINE:\nSTATES: u0, u1",
            nodes_json='["u0", "u1"]',
        )

        self.assertTrue(read_prompt("compiler", "rm_tagger"))
        self.assertIn("Finish", tagger)
        self.assertIn(clauses, tagger)
        self.assertIn('["u0", "u1"]', tagger)
        self.assertNotIn("${", tagger)
        with self.assertRaises(ValueError):
            render_prompt(
                "compiler",
                "rm_tagger",
                environment_markdown="",
                task="Finish",
                clauses_json=clauses,
                reward_machine="REWARD_MACHINE:",
                nodes_json='["u0"]',
            )

    def test_compiler_labeling_prompts_render_grounded_context(self) -> None:
        values = {
            "environment_markdown": "# Demo\n## Propositions\n- `done`: Finished",
            "task": "Finish after starting",
            "clauses_json": '[{"normalized_clause": "finish"}]',
            "reward_machine": "REWARD_MACHINE:\nSTATES: u0, u1",
            "state_descriptions_json": '{"u0": "start", "u1": "done"}',
            "nodes_json": '["u0", "u1"]',
            "propositions_json": '{"done": "Finished"}',
            "api": "env.grid.get(x, y), env.agent_pos",
        }
        generator = render_prompt("compiler", "labeling_generator", **values, history="")
        reviewer = render_prompt(
            "compiler", "labeling_reviewer", **values, labeling="def done(env):\n    return True\n"
        )

        self.assertTrue(read_prompt("compiler", "labeling_generator"))
        self.assertTrue(read_prompt("compiler", "labeling_reviewer"))
        for rendered in (generator, reviewer):
            self.assertNotIn("${", rendered)
            self.assertIn(values["api"], rendered)
            self.assertIn("REWARD_MACHINE", rendered)
            self.assertIn('["u0", "u1"]', rendered)
            self.assertIn('{"done": "Finished"}', rendered)
        self.assertIn("None.", generator)
        self.assertIn("def done(env)", reviewer)
        with self.assertRaises(ValueError):
            render_prompt("compiler", "labeling_reviewer", **values, labeling="")

    def test_arm_fm_rm_prompt_declares_runtime_guard_syntax(self) -> None:
        prompt = read_prompt("arm_fm", "rm_generator")

        self.assertIn("conjunction `&`, disjunction `|`, and negation `!`", prompt)
        self.assertIn("never\nwrite English `and`, `or`, or `not` in guard conditions", prompt)

    def test_arm_fm_labeling_prompt_declares_expression_only_syntax(self) -> None:
        prompt = read_prompt("arm_fm", "labeling_generator")

        self.assertIn(
            "Use expression-only predicates: no `if`, `for`, `while`, assignments",
            prompt,
        )
        self.assertIn("approved `any`/`all` comprehensions for scans", prompt)
        self.assertIn("Never call a sibling predicate or `.get` on", prompt)
        self.assertIn("exactly one `return` statement and no other statements", prompt)
        self.assertIn("def event_name(env): return", prompt)

    def test_arm_fm_labeling_critic_requires_all_declared_predicates(self) -> None:
        prompt = read_prompt("arm_fm", "labeling_critic")

        self.assertIn("an unused declared", prompt)
        self.assertIn("must never be rejected for being unused", prompt)


if __name__ == "__main__":
    unittest.main()
