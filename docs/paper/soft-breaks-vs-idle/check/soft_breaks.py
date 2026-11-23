"""Soft breaks per judged episode on the soft-rule cards of the 60 trained cards: FARM, idle plan, no-RM.

A soft break is counted at every broken step, as the machine charges it (the judge's
``mean_soft_break_count``, a mean over the judge's 100 test episodes of one seed). Per arm: the
mean over seeds with a 95% t interval over seeds. The idle plan is one fixed policy, so it has one
value: the results builder's ``IDLE_EVERY`` (the judge's idle plan on the same 100 test seeds),
which exists for the soft-only cards only; the judge plays no idle plan on a card with a goal or
a hard rule. The cards, seed folders and idle figures are the final-results builder's
(``TRAINABLE``, ``JUDGED`` from ``RUN_FOLDERS``, ``IDLE_EVERY``); a card trained on another
card's machine (``bundle_of``) keeps its own row.
Writes ``evidence/soft-breaks.json`` and ``evidence/soft-breaks.txt``.

Run from the repository root:
env PYTHONPATH=app:.git/agent-memory/artifacts/final-results python -P
docs/paper/soft-breaks-vs-idle/check/soft_breaks.py
"""

import contextlib
import io
import json
from collections import defaultdict
from pathlib import Path
from statistics import fmean, stdev

from scipy.stats import t

with contextlib.redirect_stdout(io.StringIO()):  # the builder prints its report on import
    import build_results as b

EVIDENCE = Path(__file__).resolve().parents[1] / "evidence"
ARMS = ("farm", "no-rm")


def seed_of(folder):
    return int(folder.name.split("-")[0].removeprefix("seed"))


def over_seeds(runs):
    """Mean and 95% t interval over seeds of the judge's every-break count; no interval for one seed."""
    values = [run["soft_break_count"] for run in runs]
    mean = fmean(values)
    if len(values) < 2:
        return {"seeds": len(values), "mean": round(mean, 4), "ci95": None, "runs": runs}
    half = t.ppf(0.975, len(values) - 1) * stdev(values) / len(values) ** 0.5
    low = max(0.0, mean - half)  # a count is never below 0
    return {
        "seeds": len(values),
        "mean": round(mean, 4),
        "ci95": [round(low, 4), round(mean + half, 4)],
        "runs": runs,
    }


# ========= Judged PPO seeds per card and arm =========
runs = defaultdict(list)
for suite, card, arm, learner, folder in b.JUDGED:
    if learner != "ppo" or arm not in ARMS:
        continue
    judge = json.loads((folder / "judge.json").read_text(encoding="utf-8"))
    runs[(suite, card, arm)].append(
        {
            "run": f"{folder.parent.name}/{folder.name}",
            "seed": seed_of(folder),
            "episodes": judge["episodes"],
            "judge": judge,
        }
    )
for key, members in runs.items():
    seeds = [run["seed"] for run in members]
    assert len(seeds) == len(set(seeds)), f"{key}: two judged folders for one seed"

# ========= One row per soft-rule card =========
rows = []
for suite, card in b.TRAINABLE:
    judges = [run["judge"] for arm in ARMS for run in runs[(suite, card, arm)]]
    soft = b.old.soft_clauses(judges[0]) if judges else []
    if not soft:
        continue
    idle = b.IDLE_EVERY.get(f"{suite}/{card}")
    row = {
        "suite": suite,
        "card": card,
        "soft_only": bool(judges[0].get("soft_only")),
        "soft_rules": [b.old.clause_text(e["clause"]) for e in soft],
        "farm_machine": b.old.bundle_of(suite, card, "farm"),
        "idle": None if idle is None else idle["soft_break_count"],
        "idle_seeds": None if idle is None else idle["seeds"],
    }
    for arm in ARMS:
        members = [
            {
                **{k: v for k, v in run.items() if k != "judge"},
                "soft_break_count": run["judge"]["mean_soft_break_count"],
            }
            for run in runs[(suite, card, arm)]
        ]
        row[arm] = over_seeds(members) if members else None
    rows.append(row)

# ========= Evidence: JSON and a plain table =========
(EVIDENCE / "soft-breaks.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")


def cell(stats):
    if stats is None:
        return "not trained"
    ci = "no CI" if stats["ci95"] is None else f"[{stats['ci95'][0]:.2f}, {stats['ci95'][1]:.2f}]"
    return f"{stats['mean']:.2f} {ci} (n={stats['seeds']})"


lines = [
    "Soft breaks per judged episode (every broken step, judge mean_soft_break_count), mean over seeds",
    "[95% t CI over seeds, low end clipped at 0] (n = seeds). Idle: the judge's idle plan on the same",
    "100 test seeds, one fixed policy; '-' where the judge plays no idle plan (card has a goal or hard rule).",
    "",
    f"{'suite/card':<52} {'soft only':<9} {'FARM':<26} {'idle':<6} no-RM",
]
for row in rows:
    idle = "-" if row["idle"] is None else f"{row['idle']:.2f}"
    lines.append(
        f"{row['suite'] + '/' + row['card']:<52} {'yes' if row['soft_only'] else 'no':<9} "
        f"{cell(row['farm']):<26} {idle:<6} {cell(row['no-rm'])}"
    )
lines.append("")
lines.append(
    f"soft-rule cards {len(rows)} of {len(b.TRAINABLE)} trained; with an idle figure {sum(r['idle'] is not None for r in rows)}"
)
text = "\n".join(lines) + "\n"
(EVIDENCE / "soft-breaks.txt").write_text(text, encoding="utf-8")
print(text, end="")
