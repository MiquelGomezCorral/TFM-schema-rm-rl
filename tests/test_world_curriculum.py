import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.arm_fm.curriculum import STAGE_LOG, EpisodeWorld, WorldCurriculum

STAGES = [
    {"env_kwargs": {"slip_chance": 0.0}, "until": {"served": 2, "episodes": 3}},
    {
        "env_kwargs": {"back_fall_chance": 0.0},
        "until": {"served": 2, "caught": 0.9, "episodes": 3},
    },
]


class WorldCurriculumTest(unittest.TestCase):
    """The stage switch is the one rule of the run that no other check pins down."""

    def test_each_stage_moves_on_only_when_its_window_meets_its_goal(self) -> None:
        curriculum = WorldCurriculum(SimpleNamespace(env_stages=STAGES))
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)

            def finish(step: int, *episodes: EpisodeWorld) -> None:
                curriculum.finished.extend(episodes)
                curriculum.update(step, directory)

            def served(stage: int, count: int, falls: int = 0, caught: int = 0) -> EpisodeWorld:
                return EpisodeWorld(stage, count, falls, caught)

            self.assertEqual(curriculum.world, {"slip_chance": 0.0})
            finish(10, served(0, 5), served(0, 5))  # window of 3 not full yet
            self.assertEqual(curriculum.stage, 0)
            finish(20, served(0, 0))  # full, mean 3.33: moves on
            self.assertEqual((curriculum.stage, curriculum.world), (1, {"back_fall_chance": 0.0}))

            # an episode begun before the switch does not count for the new stage
            finish(30, served(0, 9), served(1, 2, 4, 3), served(1, 2, 4, 3))
            self.assertEqual(curriculum.stage, 1)
            finish(40, served(1, 2, 2, 2))  # full, served 2, but caught 8 of 10: below 0.9
            self.assertEqual(curriculum.stage, 1)
            finish(50, served(1, 2, 0, 0), served(1, 2, 8, 8), served(1, 2, 2, 2))  # 10 of 10
            self.assertEqual((curriculum.stage, curriculum.world), (2, {}))
            finish(60, served(2, 0), served(2, 0), served(2, 0))  # the final world: nothing moves
            self.assertEqual(curriculum.stage, 2)

            with (Path(directory) / STAGE_LOG).open(encoding="utf-8", newline="") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(
                [(row["global_step"], row["stage"]) for row in rows], [("20", "1"), ("50", "2")]
            )
            self.assertEqual(rows[1]["caught_share"], "1.0")
