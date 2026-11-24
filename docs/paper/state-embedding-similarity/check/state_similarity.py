"""How close are the state embeddings inside each benchmark RM, FARM and ARM-FM?

For every RM with 2+ embedded states: each state's nearest other state (max cosine, averaged over the RM)
and the mean cosine over all state pairs of the RM. Per arm and RM set, the mean, minimum and maximum
over RMs. Baseline: the cosine between states of different RMs of the same arm and set, over every such
pair (1,697 FARM and 819 ARM-FM states in all, so no sampling), with the lowest pair.
A ``pooled`` row per set puts the FARM and ARM-FM RMs together (an RM both arms built identically counts
once per arm) and takes the same mean over the pooled RMs; its baseline pairs every state of two different
RMs, FARM-to-ARM-FM pairs included.

The three RM sets (``all built``, ``frozen set``, ``trained``), each per arm, come from ``rm_sets.py``.

Writes ``evidence/state-similarity.json`` and ``.md``. Needs numpy only; no model call.
Run: python docs/paper/state-embedding-similarity/check/state_similarity.py (from the repo root, in the
main checkout that holds ``outputs/runs``).
"""

import json
from pathlib import Path

import numpy as np
from rm_sets import ARMS, REPO, SETS, embedding_settings, read_embeddings, rm_sets

EVIDENCE = Path(__file__).resolve().parents[1] / "evidence"


def inside(unit):
    """(mean over states of the nearest other state's cosine, mean over all state pairs)."""
    cos = unit @ unit.T
    np.fill_diagonal(cos, np.nan)
    return np.nanmax(cos, axis=1).mean(), np.nanmean(cos)


def across(units):
    """(mean, lowest) cosine over every pair of states from two different RMs."""
    stacked = np.vstack(units)
    owner = np.repeat(np.arange(len(units)), [len(u) for u in units])
    cos = (stacked @ stacked.T)[owner[:, None] != owner[None, :]]
    return cos.mean(), cos.min()


# ========= One row per RM, then the three sets =========
members = rm_sets()
rows, units_of, settings = [], {}, set()
for arm in ARMS:
    for bundle in sorted(members[arm]["all built"] | members[arm]["frozen set"]):
        if not (bundle / "embeddings.json").exists():
            continue
        path = str(bundle.relative_to(REPO))
        units_of[path] = unit = read_embeddings(bundle)
        if len(unit):
            model, dimension = embedding_settings(bundle)
            assert unit.shape[1] == dimension, f"{path}: vector size differs from its manifest"
            settings.add(f"{model} {dimension}")
        nearest, pairs = inside(unit) if len(unit) >= 2 else (None, None)
        rows.append(
            {"arm": arm, "path": path, "states": len(unit), "nearest": nearest, "pairs": pairs}
        )

# ========= Summary per arm and set, then FARM and ARM-FM pooled =========
# Pooled: the RMs of both arms' sets together, so an RM both arms built identically counts twice (once
# per arm). Its nearest-other mean is over the pooled RMs; its baseline pairs every state of two
# different RMs, FARM-to-ARM-FM pairs included.
GROUPS = {**{arm: (arm,) for arm in ARMS}, "pooled": ARMS}
summary = {}
for group, group_arms in GROUPS.items():
    for name in SETS:
        paths = {str(b.relative_to(REPO)) for arm in group_arms for b in members[arm][name]}
        used = [
            r
            for r in rows
            if r["arm"] in group_arms and r["path"] in paths and r["nearest"] is not None
        ]
        nearest = np.array([r["nearest"] for r in used])
        cross_mean, cross_low = across([units_of[r["path"]] for r in used])
        summary[f"{group} | {name}"] = {
            "rms_listed": len(paths),
            "rms_unusable": len(paths) - len(used),
            "rms": len(used),
            "states_median": float(np.median([r["states"] for r in used])),
            "states_total": sum(r["states"] for r in used),
            "nearest_other_mean": nearest.mean(),
            "nearest_other_min": nearest.min(),
            "nearest_other_max": nearest.max(),
            "all_pairs_mean": float(np.mean([r["pairs"] for r in used])),
            "other_rm_mean": cross_mean,
            "other_rm_lowest": cross_low,
        }
EVIDENCE.mkdir(exist_ok=True)
record = {
    "embedding model and dimension (manifests)": sorted(settings),
    "sets": summary,
    "trained bundles": {
        arm: sorted(str(b.relative_to(REPO)) for b in members[arm]["trained"]) for arm in ARMS
    },
    "rows": rows,
}
(EVIDENCE / "state-similarity.json").write_text(
    json.dumps(record, indent=1, default=float) + "\n", encoding="utf-8"
)

lines = [
    "| arm | RM set | RMs | median states | nearest other state, mean over RMs (min to max) | all pairs, mean over RMs | states of other RMs, mean (lowest pair) |",
    "|---|---|---|---|---|---|---|",
]
for key, s in summary.items():
    arm, name = key.split(" | ")
    lines.append(
        f"| {arm} | {name} | {s['rms']} | {s['states_median']:.0f} "
        f"| {s['nearest_other_mean']:.3f} ({s['nearest_other_min']:.3f} to {s['nearest_other_max']:.3f}) "
        f"| {s['all_pairs_mean']:.3f} | {s['other_rm_mean']:.3f} ({s['other_rm_lowest']:.3f}) |"
    )
table = "\n".join(lines) + "\n"
(EVIDENCE / "state-similarity.md").write_text(table, encoding="utf-8")
print(f"embedding model and dimension: {', '.join(sorted(settings))}")
print(table)
for key, s in summary.items():
    print(key, f"listed {s['rms_listed']}, usable (2+ embedded states) {s['rms']}")
