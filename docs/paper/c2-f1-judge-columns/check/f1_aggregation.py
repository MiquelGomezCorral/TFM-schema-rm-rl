"""F1: aggregate-suite fills the judge columns from judge.json files the writer really emitted.

Two real finished runs (copied, not edited): a DQN run with the reviewer's real DoorKey judge
file (mean_judged_success 1.0), and the LI2 run with its own judge file (judged success 0.0, one
hard clause open). The suite's run folders are redirected into the scratch folder.
"""

import json
import shutil
import sys

import yaml
from _common import REVIEW, ROOT, save, work_dir

from scripts.aggregate_suite import aggregate_suite
from src.config import Configuration

# ``scripts.run_suite`` names the function, so the module is taken from sys.modules.
run_suite = sys.modules["scripts.run_suite"]

RUN_FILES = ("summary.json", "eval.csv", "resources.json")
WRITER_RUNS = {  # arm -> (real finished run folder, judge file the aggregator must read)
    "no-rm": (ROOT / "outputs/runs/li-l54-dqn", REVIEW / "aggregation/judge.json"),
    "farm": (ROOT / "outputs/runs/li2-l54-dqn", None),
}

work = work_dir("f1")
runs = work / "runs"
run_suite.RUNS_PATH = runs  # the aggregator reads run folders from here

expected = {}
for arm, (source_runs, judge_file) in WRITER_RUNS.items():
    source = sorted(source_runs.glob("seed1-*"))[0]
    folder = runs / f"bench__c2f1__base-doorkey__{arm}__dqn" / source.name
    folder.mkdir(parents=True)
    for name in RUN_FILES:
        if (source / name).is_file():
            shutil.copy(source / name, folder / name)
    shutil.copy(judge_file or source / "judge.json", folder / "judge.json")
    judge = json.loads((folder / "judge.json").read_text(encoding="utf-8"))
    expected[arm] = {
        "judged_success": judge["mean_judged_success"],
        "hard_breaks": judge["mean_hard_breaks"],
        "soft_breaks": judge["mean_soft_breaks"],
        "open_at_end": judge["mean_hard_open"] + judge["mean_soft_open"],
    }

suite = work / "runs.yaml"
suite.write_text(
    yaml.safe_dump(
        {
            "suite": "c2f1",
            "tasks": "experiments/benchmark/base/tasks.json",
            "bundles": str((work / "bundles").relative_to(ROOT)),
            "learner": "dqn",
            "learners": {"dqn": {"config": "experiments/benchmark/configs/dqn.yaml", "ram_gb": 9}},
            "arms": ["no-rm", "farm"],
            "seeds": [1],
            "total_timesteps": 1000,
            "only": ["base-doorkey"],
        }
    ),
    encoding="utf-8",
)
output = work / "results"
aggregate_suite(Configuration(suite=suite, suite_output=output))

rows = {row["arm"]: row for row in json.loads((output / "results.json").read_text())["runs"]}
checks = {}
for arm, want in expected.items():
    got = {key: rows[arm][key] for key in want}
    checks[arm] = {"expected": want, "aggregated": got, "ok": got == want}
save("f1", {"finding": "F1", "pass": all(c["ok"] for c in checks.values()), "arms": checks})
