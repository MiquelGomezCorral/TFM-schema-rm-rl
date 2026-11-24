"""The RM sets and the state vectors that ``state_similarity.py`` and ``state_pca.py`` both read.

Three RM sets, each per arm:
- ``all built``: every ``experiments/benchmark/*/bundles/{farm,arm-fm}/*/embeddings.json`` (all suites,
  the ARM-FM paper and XLand baselines and the pre-freeze ARM-FM shop machines included);
- ``frozen set``: the bundles each arm was asked for in the final run and built
  (``docs/paper/reward-loops-and-rounds/evidence/bundles.json``, status complete);
- ``trained``: the machines of the final runs that were judged, read from the run folders
  ``outputs/runs/bench__<suite>__<card>__<arm>__ppo/`` (their ``run-config.yaml`` names the bundle).

``trained`` needs the main checkout that holds ``outputs/runs``. Needs numpy only; no model call.
"""

import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
BENCH = REPO / "experiments/benchmark"
FROZEN = REPO / "docs/paper/reward-loops-and-rounds/evidence/bundles.json"
ARMS = ("farm", "arm-fm")
SETS = ("all built", "frozen set", "trained")
# the suites the final results count (final-run report SUITES); side and study suites are left out
FINAL_SUITES = (
    "base",
    "pilot",
    "complex",
    "templates",
    "box-carry",
    "forced-start",
    "forcing",
    "shop",
    "shop-reward",
)


def bundle_dir(path):
    return (REPO / path).resolve()


def run_bundle(config):
    """The bundle path a run folder's run-config.yaml trains on."""
    for line in config.read_text(encoding="utf-8").splitlines():
        if line.startswith("bundle:"):
            return bundle_dir(line.split(":", 1)[1].strip())
    return None


def trained_bundles(arm, frozen):
    """Frozen-set machines with a judged final run, skipping renamed (rerun) seed folders."""
    found = set()
    for config in sorted((REPO / "outputs/runs").glob(f"bench__*__{arm}__ppo/run-config.yaml")):
        suite = config.parent.name.split("__")[1]
        judged = [j for j in config.parent.glob("seed*/judge.json") if "." not in j.parent.name]
        bundle = run_bundle(config)
        if suite in FINAL_SUITES and judged and bundle in frozen:
            found.add(bundle)
    return found


def rm_sets():
    """``{arm: {set name: bundle folders}}`` for the three RM sets."""
    frozen_rows = json.loads(FROZEN.read_text(encoding="utf-8"))
    members = {}
    for arm in ARMS:
        frozen = {bundle_dir(r["path"]) for r in frozen_rows if r["arm"] == arm and r["built"]}
        members[arm] = {
            "all built": {p.parent for p in BENCH.glob(f"*/bundles/{arm}/*/embeddings.json")},
            "frozen set": frozen,
            "trained": trained_bundles(arm, frozen),
        }
    return members


def read_embeddings(bundle):
    """Unit vectors, one row per RM state (empty array when the bundle was not embedded)."""
    vectors = json.loads((bundle / "embeddings.json").read_text(encoding="utf-8"))
    if not vectors:
        return np.empty((0, 0))
    matrix = np.array(list(vectors.values()), dtype=float)
    return matrix / np.linalg.norm(matrix, axis=1, keepdims=True)


def embedding_settings(bundle):
    """(model, dimension) the bundle's manifest says its vectors come from."""
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    setting = manifest["effective_settings"]["embedding"]
    return setting["model"], setting["dimension"]
