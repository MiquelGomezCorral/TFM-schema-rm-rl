"""Do trained agents earn from a loop that pays? The trained-run side of ``pay_cycles.py``.

Reads the judged runs of the final run: the results builder's ``JUDGED``, the PPO runs of FARM and
ARM-FM (the paper's 275 runs). The 4 FARM DQN pilot runs are counted apart. Two checks:

1. Against the best scripted plan. A judged episode's ``rm_return`` (judge.json, per_episode) is the
   plain sum of what its RM paid over the episode. The best scripted plan of that RM is the largest
   ``pay[0]`` (plain sum) of a ``solve`` run in the RM's ``<bundle>.plan_check.json``. Count the
   episodes above it, at it and below it.
2. On the ARM-FM RMs that have a loop that pays (``evidence/pay_cycles.json``): per judged episode,
   the box falls in the agent trace (``labels[*].box_fell``), the loop rounds the RM paid and the
   drop actions. A round is a fall picked up again (``holding_box`` in ``u1``), 0.1 each; the exit
   pays 1. The environment schedules at most two falls per episode (``service_room.py:199``).

Reads ``evidence/bundles.json`` (``bundle_list.py``) and ``evidence/pay_cycles.json``
(``pay_cycles.py``; run both first), the run folders under ``outputs/runs``, and the plan checks.
Writes ``evidence/trained-loops.txt``.

Run from the repository root:
env PYTHONPATH=app:.git/agent-memory/artifacts/final-results python -P
docs/paper/reward-loops-and-rounds/check/trained_loops.py
"""

import contextlib
import io
import json
import re
from collections import Counter
from pathlib import Path

from minigrid.core.actions import Actions

with contextlib.redirect_stdout(io.StringIO()):  # the builder prints its report on import
    import build_results as b

REPO = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parents[1] / "evidence"
EPS = 1e-6
EXIT_PAY, ROUND_PAY, MAX_FALLS = 1.0, 0.1, 2


def read_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def best_scripted(bundle: Path) -> float:
    """Largest plain sum (``pay[0]``) that a solving plan earns on the bundle's RM in its plan check."""
    plan_check = read_json(bundle.with_name(bundle.name + ".plan_check.json"))
    return max(run["pay"][0] for run in plan_check["runs"] if run["kind"] == "solve")


def rewards_of(bundle: Path) -> list[float]:
    """The rewards listed in the RM's REWARD_FUNCTION."""
    text = (bundle / "reward_machine.txt").read_text(encoding="utf-8")
    return sorted(
        float(r) for r in re.findall(r"->\s*(\S+)\s*$", text.partition("REWARD_FUNCTION:")[2], re.M)
    )


# ========= Judged runs, FARM and ARM-FM =========
runs = []
for suite, card, arm, learner, folder in b.JUDGED:
    if arm not in ("farm", "arm-fm"):
        continue
    judge = read_json(folder / "judge.json")
    runs.append(
        {
            "suite": suite,
            "card": card,
            "arm": arm,
            "learner": learner,
            "folder": folder,
            "judge": judge,
            "bundle": Path(judge["rm_bundle"]),
            "git_head": next(
                ln.split(": ", 1)[1]
                for ln in (folder / "config.yaml").read_text(encoding="utf-8").splitlines()
                if ln.startswith("git_head:")
            ),
        }
    )
ppo = [r for r in runs if r["learner"] == "ppo"]
dqn = [r for r in runs if r["learner"] != "ppo"]
assert len(ppo) == 275 and all(r["arm"] == "farm" for r in dqn), (len(ppo), len(dqn))

lines = [
    f"judged PPO runs: {len(ppo)} {dict(Counter(r['arm'] for r in ppo))}; "
    f"episodes per run {dict(Counter(len(r['judge']['per_episode']) for r in ppo))}",
    f"judged DQN runs: {len(dqn)} {dict(Counter(r['arm'] for r in dqn))}; "
    f"episodes per run {dict(Counter(len(r['judge']['per_episode']) for r in dqn))}",
    f"code the runs trained on (config.yaml git_head): {dict(Counter(r['git_head'][:7] for r in runs))}",
]

# ========= 1. Every judged episode against the best scripted plan =========
lines += ["", "== 1. rm_return per judged episode against the best scripted plan =="]
for label, group in (("PPO", ppo), ("DQN pilot", dqn)):
    counts = Counter()
    for run in group:
        best = best_scripted(run["bundle"])
        for episode in run["judge"]["per_episode"]:
            value = episode["rm_return"]
            counts["above" if value > best + EPS else "at" if value >= best - EPS else "below"] += 1
    lines.append(
        f"{label}: {sum(counts.values())} episodes, above the best scripted plan {counts['above']}, "
        f"at it {counts['at']}, below it {counts['below']}"
    )
    assert counts["above"] == 0, f"{label}: an episode beat the best scripted plan"
lines.append(
    "per card and arm (seeds together): best scripted plan, largest judged rm_return, episodes at best"
)
cells = {}
for run in runs:
    cells.setdefault((run["suite"], run["card"], run["arm"], run["learner"]), []).append(run)
for (suite, card, arm, learner), group in sorted(cells.items()):
    best = best_scripted(group[0]["bundle"])
    values = [e["rm_return"] for run in group for e in run["judge"]["per_episode"]]
    lines.append(
        f"{suite}/{card} {arm} {learner}: best {best:g}, largest {max(values):g}, "
        f"{sum(abs(v - best) <= EPS for v in values)} of {len(values)} at best"
    )

# ========= 2. ARM-FM RMs that have a loop that pays =========
looping = {
    (row["suite"], row["bundle"])
    for row in read_json(EVIDENCE / "pay_cycles.json")["arm-fm"]["hits"]
}
paying_paths = {
    REPO / row["path"]
    for row in read_json(EVIDENCE / "bundles.json")
    if row["arm"] == "arm-fm" and (row["suite"], row["bundle"]) in looping
}
trained_loop_runs = [r for r in ppo if r["arm"] == "arm-fm" and r["bundle"] in paying_paths]
rms = {r["bundle"] for r in trained_loop_runs}
lines += [
    "",
    "== 2. trained ARM-FM runs on an RM with a loop that pays ==",
    f"{len(looping)} ARM-FM RMs have one; {len(rms)} of them trained: {sorted(p.name for p in rms)}; "
    f"{len(trained_loop_runs)} judged runs "
    f"({sum(r['card'] == r['bundle'].name for r in trained_loop_runs)} on the RM's own card, "
    f"{sum(r['card'] != r['bundle'].name for r in trained_loop_runs)} on a copy card that reuses it)",
]
for rm in sorted(rms):
    assert rewards_of(rm) == [ROUND_PAY, EXIT_PAY], (rm, rewards_of(rm))
    lines.append(f"{rm.name}: best scripted plan {best_scripted(rm):g}")

totals = Counter()
for run in sorted(trained_loop_runs, key=lambda r: (r["card"], r["folder"].name)):
    seed = run["folder"].name.split("-")[0]
    cells_of_run = Counter()
    for episode in run["judge"]["per_episode"]:
        trace = read_json(run["folder"] / episode["file"])
        falls = sum(bool(step["box_fell"]) for step in trace["labels"])
        drops = sum(action == Actions.drop for action in trace["actions"])
        value = episode["rm_return"]
        rounds = round((value - (EXIT_PAY if value >= EXIT_PAY - EPS else 0.0)) / ROUND_PAY)
        assert falls <= MAX_FALLS and rounds <= falls, (run["card"], seed, episode["file"])
        cells_of_run[(falls, rounds, value >= EXIT_PAY - EPS, drops > 0)] += 1
        totals[(falls, rounds)] += 1
    own = "own card" if run["card"] == run["bundle"].name else f"copy of {run['bundle'].name}"
    shown = ", ".join(
        f"falls {f} rounds paid {r} exit {'yes' if x else 'no'} drop {'yes' if d else 'no'}: {n}"
        for (f, r, x, d), n in sorted(cells_of_run.items())
    )
    lines.append(
        f"{run['card']} {seed} ({own}, code {run['git_head'][:7]}): judged success "
        f"{run['judge']['mean_judged_success']:g}, "
        f"mean rm_return {run['judge']['mean_rm_return']:.3f}; {shown}"
    )
lines.append(
    f"all {sum(totals.values())} episodes: (falls, rounds paid) {dict(sorted(totals.items()))}; "
    "never more than two falls, never more rounds paid than falls"
)
own_values = Counter(
    round(e["rm_return"], 1)
    for r in trained_loop_runs
    if r["card"] == r["bundle"].name
    for e in r["judge"]["per_episode"]
)
lines.append(f"rm_return of the own-card runs: {dict(sorted(own_values.items()))}")

text = "\n".join(lines) + "\n"
(EVIDENCE / "trained-loops.txt").write_text(text, encoding="utf-8")
print(text, end="")
