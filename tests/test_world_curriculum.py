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
    {"env_kwargs": {"siren": True}, "until": {"served": 2, "silenced": 0.9, "episodes": 3}},
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

            def sirens(rings: int, silenced: int) -> EpisodeWorld:
                return EpisodeWorld(2, 3, 0, 0, rings, silenced)

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
            self.assertEqual((curriculum.stage, curriculum.world), (2, {"siren": True}))

            finish(60, sirens(2, 1), sirens(2, 2), sirens(0, 0))  # 3 of 4 sirens
            self.assertEqual(curriculum.stage, 2)
            finish(70, sirens(5, 4), sirens(0, 0), sirens(1, 1))  # 5 of 6
            self.assertEqual(curriculum.stage, 2)
            finish(80, sirens(4, 4), sirens(1, 1), sirens(0, 0))  # 5 of 5
            self.assertEqual((curriculum.stage, curriculum.world), (3, {}))
            finish(90, served(3, 0), served(3, 0), served(3, 0))  # the final world: nothing moves
            self.assertEqual(curriculum.stage, 3)

            with (Path(directory) / STAGE_LOG).open(encoding="utf-8", newline="") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(
                [(row["global_step"], row["stage"]) for row in rows],
                [("20", "1"), ("50", "2"), ("80", "3")],
            )
            self.assertEqual(rows[1]["caught_share"], "1.0")
            self.assertEqual(rows[2]["silenced_share"], "1.0")
