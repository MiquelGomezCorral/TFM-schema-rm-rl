"""The keys ``test-rl --judge`` writes into ``judge.json`` are the ones ``aggregate-suite`` reads.

Run with ``PYTHONPATH=app python -m unittest tests.test_aggregate_suite``.
"""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.aggregate_suite import judge_columns
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


if __name__ == "__main__":
    unittest.main()
