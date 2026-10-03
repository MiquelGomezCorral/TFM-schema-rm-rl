"""Compiler text interoperability with the unchanged ARM-FM runtime."""

import unittest
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

from scripts.render_rm import render_reward_machine
from src.arm_fm.runtime import RewardMachineRuntime, parse_paper_reward_machine
from src.compiler import ClauseProposal, Proposal, build_compilation_result
from src.compiler.reward_machine import parse_reward_machine, serialize_reward_machine
from src.models import EnvironmentDescription, PriorityLevel
from src.utils.generation import save_results
from src.web.visualization import reward_machine_to_elements


def _transition_tuples(structure):
    """Describe a structure's transitions as plain tuples for table comparison."""
    return tuple(
        (item.source, item.destination, item.condition, item.reward)
        for item in structure.transitions
    )


class RewardMachineFormatTests(unittest.TestCase):
    def test_compiler_output_preserves_zero_reward_progress(self):
        environment = EnvironmentDescription.from_markdown(
            "# Demo\n## Propositions\n- `done`: Completion event", source="demo.md"
        )
        proposal = Proposal("Finish twice", (ClauseProposal(
            "Finish twice", "ExistenceTwo", ("done",), PriorityLevel.NONE, "unused"
        ),))
        dfa = {
            "states": ("0", "1", "2"), "initial_state": "0",
            "accepting_states": ("2",), "alphabet": ("done",),
            "transitions": {
                ("0", "!done"): "0", ("0", "done"): "1",
                ("1", "!done"): "1", ("1", "done"): "2",
                ("2", "true"): "2",
            },
        }
        result = build_compilation_result(environment, proposal, (dfa,))
        expected = """REWARD_MACHINE:
STATES: u0, u1, u2
INITIAL_STATE: u0
FINAL_STATES: u2
DEFAULT_REWARD: 0
TRANSITION_FUNCTION:
(u0, done) -> u1
(u1, done) -> u2
REWARD_FUNCTION:
(u1, done, u2) -> 1.1
"""
        self.assertEqual(result.text, expected)
        self.assertEqual(serialize_reward_machine(parse_reward_machine(result.text)), expected)
        runtime = RewardMachineRuntime(parse_paper_reward_machine(result.text))
        for valuation, destination, reward in (
            (False, "u0", 0), (True, "u1", 0), (False, "u1", 0),
            (True, "u2", 1.1), (True, "u2", 0),
        ):
            step = runtime.step({"done": valuation})
            self.assertEqual((step.destination, step.reward), (destination, reward))

        with TemporaryDirectory() as directory:
            path = Path(directory) / "task.rm"
            save_results((result,), (path,), overwrite=False)
            self.assertEqual(path.read_text(encoding="utf-8"), expected)
            svg = ElementTree.fromstring(render_reward_machine(path.read_text(encoding="utf-8")))
            self.assertEqual(svg.tag, "{http://www.w3.org/2000/svg}svg")

    def test_import_preserves_guards_self_loops_and_else(self):
        text = """REWARD_MACHINE:
STATES: u0, u1, u2
INITIAL_STATE: u0
FINAL_STATES: u2
TRANSITION_FUNCTION:
(u0, else) -> u2
(u0, (a | b) & !c) -> u1
(u0, c) -> u0
REWARD_FUNCTION:
(u0, else, u2) -> -0.2
(u0, (a | b) & !c, u1) -> 0.25
(u0, c, u0) -> -0.1
"""
        structure = parse_reward_machine(text)
        serialized = serialize_reward_machine(structure)
        runtime = RewardMachineRuntime(parse_paper_reward_machine(serialized))
        for values, destination, reward in (
            ((True, False, False), "u1", 0.25),
            ((False, True, False), "u1", 0.25),
            ((True, False, True), "u0", -0.1),
            ((False, False, False), "u2", -0.2),
        ):
            runtime.reset()
            step = runtime.step(dict(zip(("a", "b", "c"), values, strict=True)))
            self.assertEqual((step.destination, step.reward), (destination, reward))
        self.assertEqual(structure.transitions[0].condition, ("else",))
        for invalid in (
            text.replace("FINAL_STATES: u2", "FINAL_STATES: u1, u2"),
            text.replace("FINAL_STATES: u2", "FINAL_STATES: u0"),
            text.replace("(u0, c) -> u0", "(u0, c) -> u9"),
            text.replace("(u0, c, u0) -> -0.1", "(u1, c, u0) -> -0.1"),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                parse_reward_machine(invalid)

    def test_rendering_shows_else_fallback_for_every_state(self):
        rows = (
            {
                "name": "no explicit else",
                "text": """REWARD_MACHINE:
STATES: u0, u1
INITIAL_STATE: u0
FINAL_STATES: u1
TRANSITION_FUNCTION:
(u0, a) -> u1
REWARD_FUNCTION:
(u0, a, u1) -> 1
""",
                "explicit": ((0, 1, ("a",), 1.0),),
                "fallbacks": {0: (0, 0.0), 1: (1, 0.0)},
                "labels": Counter({"1 case · r=+1.00": 1, "else · r=0": 2}),
            },
            {
                "name": "explicit else self-loop",
                "text": """REWARD_MACHINE:
STATES: u0, u1
INITIAL_STATE: u0
FINAL_STATES: u1
TRANSITION_FUNCTION:
(u0, else) -> u0
(u0, a) -> u1
REWARD_FUNCTION:
(u0, else, u0) -> -0.5
(u0, a, u1) -> 1
""",
                "explicit": ((0, 0, ("else",), -0.5), (0, 1, ("a",), 1.0)),
                "fallbacks": {0: (0, -0.5), 1: (1, 0.0)},
                "labels": Counter({"else · r=-0.50": 1, "1 case · r=+1.00": 1, "else · r=0": 1}),
            },
            {
                "name": "explicit else to another destination",
                "text": """REWARD_MACHINE:
STATES: u0, u1, u2
INITIAL_STATE: u0
FINAL_STATES: u2
TRANSITION_FUNCTION:
(u0, else) -> u1
(u0, a) -> u2
(u1, b) -> u2
REWARD_FUNCTION:
(u0, else, u1) -> -0.2
(u0, a, u2) -> 1
(u1, b, u2) -> 1
""",
                "explicit": (
                    (0, 1, ("else",), -0.2),
                    (0, 2, ("a",), 1.0),
                    (1, 2, ("b",), 1.0),
                ),
                "fallbacks": {0: (1, -0.2), 1: (1, 0.0), 2: (2, 0.0)},
                "labels": Counter(
                    {"else · r=-0.20": 1, "1 case · r=+1.00": 2, "else · r=0": 2}
                ),
            },
            {
                "name": "ordinary guarded self-loop plus implicit else",
                "text": """REWARD_MACHINE:
STATES: u0, u1
INITIAL_STATE: u0
FINAL_STATES: u1
TRANSITION_FUNCTION:
(u0, a) -> u0
(u0, b) -> u1
REWARD_FUNCTION:
(u0, a, u0) -> 0.25
(u0, b, u1) -> 1
""",
                "explicit": ((0, 0, ("a",), 0.25), (0, 1, ("b",), 1.0)),
                "fallbacks": {0: (0, 0.0), 1: (1, 0.0)},
                "labels": Counter(
                    {"1 case + else · mixed r": 1, "1 case · r=+1.00": 1, "else · r=0": 1}
                ),
            },
            {
                "name": "uppercase and whitespace else",
                "text": """REWARD_MACHINE:
STATES: u0, u1
INITIAL_STATE: u0
FINAL_STATES: u1
TRANSITION_FUNCTION:
(u0,  ELSE ) -> u1
REWARD_FUNCTION:
(u0,  ELSE , u1) -> -0.1
""",
                "explicit": ((0, 1, ("ELSE",), -0.1),),
                "fallbacks": {0: (1, -0.1), 1: (1, 0.0)},
                "labels": Counter({"else · r=-0.10": 1, "else · r=0": 1}),
            },
        )
        for row in rows:
            with self.subTest(case=row["name"]):
                structure = parse_reward_machine(row["text"])
                elements = reward_machine_to_elements(structure)
                self.assertEqual(_transition_tuples(structure), row["explicit"])

                edge_cases = {}
                for element in elements:
                    data = element["data"]
                    if "source" not in data:
                        continue
                    key = (
                        int(data["source"].removeprefix("state-")),
                        int(data["target"].removeprefix("state-")),
                    )
                    edge_cases[key] = [
                        (tuple(case["condition"]), case["reward"]) for case in data["cases"]
                    ]

                self.assertEqual(set(row["fallbacks"]), set(structure.states))
                for source, (destination, reward) in row["fallbacks"].items():
                    else_cases = [
                        (target, case)
                        for (edge_source, target), cases in edge_cases.items()
                        if edge_source == source
                        for case in cases
                        if len(case[0]) == 1 and case[0][0].strip().lower() == "else"
                    ]
                    self.assertEqual(len(else_cases), 1, f"state {source} needs one else case")
                    target, (_, case_reward) = else_cases[0]
                    self.assertEqual(target, destination)
                    self.assertEqual(case_reward, reward)

                for source, destination, condition, reward in row["explicit"]:
                    self.assertIn((condition, reward), edge_cases[(source, destination)])

                svg = ElementTree.fromstring(render_reward_machine(row["text"]))
                visible = Counter(
                    element.text
                    for element in svg.iter("{http://www.w3.org/2000/svg}text")
                    if element.text
                )
                node_labels = {f"u{state}" for state in structure.states}
                chips = Counter(
                    {text: count for text, count in visible.items() if text not in node_labels}
                )
                self.assertEqual(chips, row["labels"])


if __name__ == "__main__":
    unittest.main()
