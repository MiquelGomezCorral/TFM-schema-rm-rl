"""The keys ``test-rl --judge`` writes into ``judge.json`` are the ones ``aggregate-suite`` reads.

Run with ``PYTHONPATH=app python -m unittest tests.test_aggregate_suite``.
"""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.aggregate_suite import fired_success, judge_columns
from scripts.test_rl import JUDGE_MEANS, judge_means


class JudgeColumnsTest(unittest.TestCase):
    def test_every_judge_column_is_filled_from_the_writer_means(self):
        # Two fake episodes; hard and soft break means differ (1.0 vs 3.0), so a column read from
        # the other break key gives another number.
        judged = ("judged_success", "hard_breaks", "soft_breaks", "hard_open", "soft_open")
        judged += ("non_empty_success", "raw_judged_success", "cannot_start")
        filler = {**dict.fromkeys(JUDGE_MEANS, 0)}
        filler.update(rm_return=None, rm_return_positive=None, rm_return_negative=None)  # no RM
        episodes = [
            {**filler, **dict(zip(judged, values, strict=True))}
            for values in ((1, 0, 6, 1, 0, 1, 1, 1), (0, 2, 0, 0, 3, 0, 1, 1))
        ]

        with tempfile.TemporaryDirectory() as folder:
            judge = json.dumps(judge_means(episodes))
            (Path(folder) / "judge.json").write_text(judge, encoding="utf-8")
            columns = judge_columns(Path(folder))

        expected = {
            "judged_success": 0.5,
            "non_empty_success": 0.5,
            "hard_breaks": 1.0,
            "soft_breaks": 3.0,
            "open_at_end": 2.0,
            "rm_return_positive": None,
            "raw_judged_success": 1.0,
            "episodes_cannot_start": 1.0,
            "cannot_start_flag": True,
            "machine_too_simple": None,  # no machine: the writer leaves it out
        }
        self.assertEqual({key: columns[key] for key in expected}, expected)


class FiredSuccessTest(unittest.TestCase):
    def test_only_a_judged_episode_where_a_hard_rule_fired_counts(self):
        # Rules: a hard Response, a hard Absence (no trigger: None) and a soft Existence.
        expect = [
            {"clause": ["Response", ["a", "b"], "hard"]},
            {"clause": ["Absence", ["c"], "hard"]},
            {"clause": ["Existence", ["d"], "soft"]},
        ]
        episodes = [
            {"judged_success": True, "activated": [True, None, False]},  # counts
            {"judged_success": True, "activated": [False, None, True]},  # only a soft rule fired
            {"judged_success": True, "activated": [False, None, False]},  # idle: an empty pass
            {
                "judged_success": False,
                "activated": [True, None, True],
            },  # a rule fired, judged failed
        ]

        self.assertEqual(fired_success({"expect": expect, "per_episode": episodes}), 0.25)
        self.assertIsNone(fired_success({"mean_judged_success": 1.0}))  # judged before per_episode
        absence_only = {"clause": ["Absence", ["c"], "hard"]}  # no trigger: nothing could fire
        episode = {"judged_success": True, "activated": [None]}
        self.assertIsNone(fired_success({"expect": [absence_only], "per_episode": [episode]}))


if __name__ == "__main__":
    unittest.main()
