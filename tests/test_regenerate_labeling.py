import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import test_arm_fm

from scripts.generation_table import _bundle_facts
from scripts.regenerate_labeling import (
    ACCEPTED,
    FAILED,
    PENDING,
    SKIPPED,
    _regenerate,
    sidecar_path,
)
from src.arm_fm import ArtifactBundle
from src.arm_fm.generation import (
    LabelingError,
    StageAttempt,
    build_compiler_bundle,
    record_bundle_embeddings,
)
from src.benchmark.labeling_repair import record_path
from src.benchmark.traces import find_bundles
from src.config import Configuration

# ``scripts`` re-exports a function of the same name, so the module is taken from the import table.
regeneration = sys.modules["scripts.regenerate_labeling"]
NEW_SOURCE = "def done(env):\n    return False\n"


def rejected_tries():
    return [
        StageAttempt("labeling", number, "rejected", "bad", feedback="no") for number in (1, 2, 3)
    ]


class RegenerateLabelingTests(unittest.TestCase):
    """A stubbed provider: the loop's outcome is given, nothing is requested."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        compiled = test_arm_fm.ArmFMArtifactTests._compiler_result(
            embeddings={"u0": [1.0, 0.0], "u1": [0.0, 1.0]},
            embedding_settings={"model": "nomic-embed-text", "dimension": 2},
        )
        bundle = build_compiler_bundle(
            compiled,
            labeling_source=compiled.labeling_source,
            state_descriptions={"u0": "start", "u1": "finished"},
            attempts=[StageAttempt(**item) for item in compiled.labeling_attempts],
        )
        record_bundle_embeddings(bundle, compiled)
        bundle.manifest.provenance["stamp"] = {
            "generator_model": "deepseek-v4.1-flash",
            "critic_model": "glm-5.3-flash",
        }
        self.folder = Path(directory.name)
        self.path = self.folder / "farm" / "card"
        bundle.save(self.path)
        self.ref = find_bundles(self.folder)[0]
        self.original = bundle.labeling_source

    def run_loop(self, outcome):
        def generate(_config, _bundle, _models, attempts, _engines):
            if isinstance(outcome, list):
                raise LabelingError(outcome)
            attempts.append(StageAttempt("labeling", 1, "accepted", outcome))
            return outcome

        with (
            patch.object(regeneration, "_generate", generate),
            patch.object(regeneration, "call_records", return_value=[]),
        ):
            return _regenerate(Configuration(), self.ref)

    def sidecar(self):
        return json.loads(sidecar_path(self.ref).read_text(encoding="utf-8"))

    def test_failed_loop_leaves_a_complete_bundle_untouched(self):
        before = (self.path / "attempts.json").read_text(encoding="utf-8")
        self.assertEqual(self.run_loop(rejected_tries()), FAILED)
        bundle = ArtifactBundle.load(self.path)
        self.assertEqual(bundle.validate(require_complete=True), [])
        self.assertEqual(bundle.labeling_source, self.original)
        self.assertEqual(bundle.manifest.stage_status["labeling"], "complete")
        self.assertEqual((self.path / "attempts.json").read_text(encoding="utf-8"), before)
        self.assertEqual(self.sidecar()["outcome"], FAILED)
        self.assertEqual(len(self.sidecar()["attempts"]), 3)

    def test_failed_sidecar_is_retried_and_keeps_the_original_generation(self):
        self.run_loop(rejected_tries())
        self.assertEqual(self.run_loop(NEW_SOURCE), ACCEPTED)
        self.assertEqual(ArtifactBundle.load(self.path).labeling_source, NEW_SOURCE)
        self.assertEqual(self.sidecar()["outcome"], ACCEPTED)
        self.assertEqual(self.sidecar()["previous"]["labeling"], self.original)
        # an accepted sidecar of the same machine is skipped; a rerun keeps the sidecar as it is
        self.assertEqual(self.run_loop("def other(env):\n    return True\n"), SKIPPED)
        self.assertEqual(self.sidecar()["previous"]["labeling"], self.original)

    def test_a_pending_sidecar_keeps_the_original_after_an_interrupted_run(self):
        self.run_loop(NEW_SOURCE)
        record = self.sidecar()
        record["outcome"] = PENDING  # as if the final write never happened
        sidecar_path(self.ref).write_text(json.dumps(record), encoding="utf-8")
        self.assertEqual(self.run_loop("def again(env):\n    return True\n"), ACCEPTED)
        self.assertEqual(self.sidecar()["previous"]["labeling"], self.original)

    def test_failed_rerun_after_a_crash_puts_the_original_back(self):
        original_attempts = (self.path / "attempts.json").read_text(encoding="utf-8")
        check = record_path(self.ref)
        check.write_text('{"outcome": "ok"}\n', encoding="utf-8")
        self.run_loop(NEW_SOURCE)
        record = self.sidecar()
        record["outcome"] = PENDING  # the run died before it wrote its final sidecar
        sidecar_path(self.ref).write_text(json.dumps(record), encoding="utf-8")
        self.assertEqual(self.run_loop(rejected_tries()), FAILED)
        bundle = ArtifactBundle.load(self.path)
        self.assertEqual(bundle.validate(require_complete=True), [])
        self.assertEqual(bundle.labeling_source, self.original)
        self.assertEqual(
            (self.path / "attempts.json").read_text(encoding="utf-8"), original_attempts
        )
        self.assertEqual(json.loads(check.read_text(encoding="utf-8")), {"outcome": "ok"})
        self.assertEqual(
            (self.sidecar()["outcome"], self.sidecar()["previous"]["labeling"]),
            (FAILED, self.original),
        )
        self.assertEqual(_bundle_facts(self.ref)["regenerated_accepted"], False)

    def test_table_counts_the_original_generation_and_the_regeneration_apart(self):
        # The original generation spent two rejected tries before it was accepted.
        bundle = ArtifactBundle.load(self.path)
        bundle.attempts = [
            *bundle.attempts,
            *(StageAttempt("labeling", n, "rejected", "x").__dict__ for n in (1, 2)),
        ]
        bundle.save(self.path, overwrite=True)
        before = _bundle_facts(self.ref)
        self.run_loop(NEW_SOURCE)
        after = _bundle_facts(self.ref)
        self.assertEqual((before["labeling_tries"], before["regenerated"]), (3, False))
        self.assertEqual((after["labeling_tries"], after["regenerated"]), (3, True))
        self.assertEqual((after["regenerated_accepted"], after["regenerated_tries"]), (True, 1))
        self.run_loop(rejected_tries())  # skipped: accepted already, the table keeps the numbers
        self.assertEqual(_bundle_facts(self.ref)["regenerated_tries"], 1)


if __name__ == "__main__":
    unittest.main()
