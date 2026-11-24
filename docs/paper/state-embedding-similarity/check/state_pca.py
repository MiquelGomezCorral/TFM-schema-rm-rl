"""PCA of the RM state embeddings: how many components hold 80% and 90% of the variance.

Reruns the 17 November whole-corpus study (1,883 distinct vectors: 80% at 32 components, 89% at 64,
broken stick 37) on the final bundles. For each RM set of ``rm_sets.py``, FARM and ARM-FM pooled:
the distinct state vectors (exact copies dropped), the components that hold 80% and 90% of the
variance, the variance held by 32 and 64 components, and the broken-stick count (components kept
while their variance share beats a random split of the variance into ``rank`` parts, up to the first
one that does not). A bootstrap resamples the RMs (BOOTSTRAPS times, fixed SEED, vectors deduplicated
again) and refits, to show whether the counts are stable.

Writes ``evidence/state-pca.json``, ``.md`` and ``.png``. Needs numpy and matplotlib; no model call.
Run: python docs/paper/state-embedding-similarity/check/state_pca.py (from the repo root, in the
main checkout that holds ``outputs/runs``).
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from rm_sets import ARMS, SETS, embedding_settings, read_embeddings, rm_sets

EVIDENCE = Path(__file__).resolve().parents[1] / "evidence"
TARGETS = (0.80, 0.90)  # shares of the variance to reach
MILESTONES = (32, 64)  # component counts whose variance share is reported
BOOTSTRAPS = 200
SEED = 0
# stable = the fit has the full rank (768) and, on both targets, the 95% bootstrap interval is at
# most this share of the full-fit count wide and the bootstrap median at most MAX_SHIFT of it away
MAX_WIDTH = 0.20
MAX_SHIFT = 0.10
PLOTTED = 128  # components drawn


def distinct(per_rm):
    """One row per distinct vector over the given per-RM arrays (exact copies dropped)."""
    return np.unique(np.vstack(per_rm), axis=0)


def variance_ratio(vectors):
    """Share of the variance of each principal component (at most n - 1 of them, at most 768)."""
    centered = vectors - vectors.mean(axis=0)
    rank = min(len(vectors) - 1, vectors.shape[1])
    # eigenvalues of the 768 x 768 scatter matrix = squared singular values, but much faster to refit
    variance = np.linalg.eigvalsh(centered.T @ centered)[::-1][:rank]
    return variance / variance.sum()


def components_for(cumulative, target):
    return int(np.searchsorted(cumulative, target)) + 1


def broken_stick_count(ratio):
    """Leading components whose share beats the broken-stick expectation for ``len(ratio)`` parts."""
    parts = len(ratio)
    stick = np.cumsum((1.0 / np.arange(1, parts + 1))[::-1])[::-1] / parts
    beats = ratio > stick
    return int(np.argmin(beats)) if not beats.all() else parts


def resample_counts(per_rm, rng):
    """Components for each target on one resample of the RMs."""
    picked = rng.integers(len(per_rm), size=len(per_rm))
    cumulative = np.cumsum(variance_ratio(distinct([per_rm[i] for i in picked])))
    return [components_for(cumulative, t) for t in TARGETS]


def fit_set(per_rm, rng):
    """The PCA record of one RM set, and the variance ratios for the plot."""
    vectors = distinct(per_rm)
    ratio = variance_ratio(vectors)
    cumulative = np.cumsum(ratio)
    assert len(ratio) >= max(MILESTONES), "too few vectors for the milestones"
    boot = np.array([resample_counts(per_rm, rng) for _ in range(BOOTSTRAPS)])
    record = {
        "rms": len(per_rm),
        "vectors_listed": sum(len(u) for u in per_rm),
        "distinct_vectors": len(vectors),
        "rank": len(ratio),
        "rank_limited": len(ratio) < vectors.shape[1],
        "broken_stick": broken_stick_count(ratio),
        **{f"variance_at_{k}": float(cumulative[k - 1]) for k in MILESTONES},
    }
    stable = not record["rank_limited"]
    for column, target in enumerate(TARGETS):
        key = f"{round(target * 100)}"
        full = components_for(cumulative, target)
        low, median, high = np.percentile(boot[:, column], [2.5, 50, 97.5])
        record[f"components_{key}"] = full
        record[f"bootstrap_{key}"] = {
            "median": float(median),
            "low_2.5": float(low),
            "high_97.5": float(high),
        }
        stable &= (high - low) <= MAX_WIDTH * full and abs(median - full) <= MAX_SHIFT * full
    record["stable"] = bool(stable)
    return record, ratio


def draw_scree(ratios, path):
    fig, (scree, cumulative) = plt.subplots(1, 2, figsize=(12, 4.5))
    for name, ratio in ratios.items():
        shown = ratio[:PLOTTED]
        scree.semilogy(np.arange(1, len(shown) + 1), shown, label=name)
        cumulative.plot(np.arange(1, len(shown) + 1), np.cumsum(ratio)[:PLOTTED] * 100, label=name)
    for target in TARGETS:
        cumulative.axhline(target * 100, color="grey", ls=":", lw=1)
    for k in MILESTONES:
        cumulative.axvline(k, color="grey", ls="--", lw=1)
    scree.set(xlabel="component", ylabel="share of the variance (log)", title="Scree")
    cumulative.set(xlabel="component", ylabel="cumulative variance (%)", title="Cumulative")
    scree.legend()
    fig.suptitle("PCA of the RM state embeddings (FARM and ARM-FM pooled, distinct vectors)")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def markdown_table(records):
    lines = [
        "| RM set | RMs | distinct vectors | rank (of 768) | 80% at | 90% at | variance at 32 | variance at 64 "
        "| broken stick | bootstrap 80% median (95%) | bootstrap 90% median (95%) | stable |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name, r in records.items():
        b80, b90 = r["bootstrap_80"], r["bootstrap_90"]
        lines.append(
            f"| {name} | {r['rms']} | {r['distinct_vectors']} | {r['rank']} "
            f"| {r['components_80']} | {r['components_90']} "
            f"| {r['variance_at_32']:.1%} | {r['variance_at_64']:.1%} | {r['broken_stick']} "
            f"| {b80['median']:.0f} ({b80['low_2.5']:.0f} to {b80['high_97.5']:.0f}) "
            f"| {b90['median']:.0f} ({b90['low_2.5']:.0f} to {b90['high_97.5']:.0f}) "
            f"| {'yes' if r['stable'] else 'no'} |"
        )
    return "\n".join(lines) + "\n"


def main():
    members = rm_sets()
    units_of, settings = {}, set()
    for bundle in sorted({b for arm in ARMS for name in SETS for b in members[arm][name]}):
        if not (bundle / "embeddings.json").exists():
            continue
        units_of[bundle] = units = read_embeddings(bundle)
        if len(units):
            model, dimension = embedding_settings(bundle)
            assert units.shape[1] == dimension, f"{bundle}: vector size differs from its manifest"
            settings.add(f"{model} {dimension}")
    assert len(settings) == 1, f"vectors of different models cannot be pooled: {sorted(settings)}"

    rng = np.random.default_rng(SEED)
    records, ratios = {}, {}
    for name in SETS:
        per_rm = [
            units_of[b]
            for arm in ARMS
            for b in sorted(members[arm][name])
            if len(units_of.get(b, ()))
        ]
        records[name], ratios[name] = fit_set(per_rm, rng)

    EVIDENCE.mkdir(exist_ok=True)
    record = {
        "embedding model and dimension (manifests)": sorted(settings),
        "bootstraps": BOOTSTRAPS,
        "seed": SEED,
        "stable rule": "rank 768 (not limited by the vector count), and for the 80% and the 90% "
        f"count a 95% bootstrap interval <= {MAX_WIDTH:.0%} of the full-fit count wide and a "
        f"median within {MAX_SHIFT:.0%} of it",
        "sets": records,
    }
    (EVIDENCE / "state-pca.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    table = markdown_table(records)
    (EVIDENCE / "state-pca.md").write_text(table, encoding="utf-8")
    draw_scree(ratios, EVIDENCE / "state-pca.png")
    print(f"embedding model and dimension: {', '.join(sorted(settings))}")
    print(table)


if __name__ == "__main__":
    main()
