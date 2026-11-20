"""Training gate for templates FARM bundles (no model call); adapted from tp-kc-room/outputs/kc-room/gate_kc.py.

Per bundle folder, every check must pass before any training:
- review: the card scorer (`clause_status`) gives `exact` or `also_ok`, and the labeling covers only the machine's
  propositions;
- pay_order: `check-pay-order` says ok;
- plan_trace: solve, wrong and idle plans on seeds 1-5, judged by the stored clauses and by the card's `expect`,
  give the same verdict (0 mismatches);
- labeling: the bundle's labeling equals the reference labeler on those traces;
- plan_check: the card's plan check passes on seeds 1-5.
The card is the bundle name before `~` (paraphrase bundles share it). Writes the entry's
evidence/gate/<bundle>.json.

Usage (cwd = worktree root): PYTHONPATH=app OMP_NUM_THREADS=2 python <this file> <suite> BUNDLE...
"""

import json
import subprocess
import sys
from pathlib import Path

from src.arm_fm.artifacts import load_bundle
from src.benchmark.cards import load_cards
from src.benchmark.declare_judge import HARD, HOLDS, judge_trace
from src.benchmark.labeling_repair import check_labeling
from src.benchmark.plan_check import check_card_plans
from src.benchmark.plans import run_plan
from src.benchmark.rm_facts import _normalized, clause_status
from src.benchmark.traces import make_record

OUT = Path(__file__).resolve().parent.parent / "evidence" / "gate"
SEEDS = (1, 2, 3, 4, 5)
IDLE = [{"do": "wait", "n": 1000}]


def verdict(clauses, labels):
    judgment = judge_trace(clauses, labels)
    soft_failed = any(v.status != HOLDS for v in judgment.verdicts if v.clause[2] != HARD)
    return judgment.success, soft_failed


def gate(suite: str, card, folder: Path) -> dict:
    bundle = load_bundle(folder)
    record = {"bundle": str(folder), "task": bundle.manifest.task}
    out = subprocess.run(  # noqa: S603  fixed argv, no shell
        [
            sys.executable,
            "app/main.py",
            "check-pay-order",
            str(folder),
            "--gym-id",
            card.env["gym_id"],
            "--env-kwargs",
            json.dumps(card.env.get("env_kwargs") or {}),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    text = (out.stdout + out.stderr).strip()
    record["pay_order"] = {
        "ok": out.returncode == 0
        and "; ok" in text
        and "broken" not in text
        and "not checked" not in text,
        "output": text,
    }

    stored = _normalized(bundle.manifest.generation["clauses"])
    status = clause_status(stored, card)
    labeling_props, machine_props = (
        set(bundle.labeling_propositions),
        set(bundle.reward_machine.used_propositions),
    )
    record["review"] = {
        "stored_clauses": stored,
        "scorer": status,
        "labeling_propositions": sorted(labeling_props),
        "machine_propositions": sorted(machine_props),
        "ok": status in ("exact", "also_ok") and labeling_props == machine_props,
    }

    clauses = tuple((t, tuple(n), p) for t, n, p in stored)
    plans = [("solve", list(card.solve))] + [
        (f"wrong-{i}", w["steps"]) for i, w in enumerate(card.wrong)
    ]
    plans.append(("idle", IDLE))
    rollouts = [
        (name, seed, run_plan(card.env, steps, seed)) for name, steps in plans for seed in SEEDS
    ]
    mismatches = [
        (n, s)
        for n, s, r in rollouts
        if verdict(clauses, r.labels) != verdict(card.expect, r.labels)
    ]
    record["plan_trace"] = {"ok": not mismatches, "traces": len(rollouts), "mismatches": mismatches}

    checked = check_labeling(
        bundle, [make_record(suite, card, f"{n}-s{s}", "plan", r) for n, s, r in rollouts]
    )
    record["labeling"] = {"ok": checked.kind == "ok", "check": repr(checked)[:600]}
    plan_checks = {seed: check_card_plans(bundle, card, seed) for seed in SEEDS}
    record["plan_check"] = {
        "ok": all(c["passed"] is True for c in plan_checks.values()),
        "problems": {
            s: c["problems"][:3] for s, c in plan_checks.items() if c["passed"] is not True
        },
    }
    record["passed"] = all(
        record[k]["ok"] for k in ("review", "pay_order", "plan_trace", "labeling", "plan_check")
    )
    return record


def main() -> None:
    suite, *folders = sys.argv[1:]
    cards = {
        c.id: c for c in load_cards(Path("experiments/benchmark") / suite / "tasks.json").cards
    }
    OUT.mkdir(exist_ok=True)
    for folder in map(Path, folders):
        record = gate(suite, cards[folder.name.split("~")[0]], folder)
        (OUT / f"{folder.name}.json").write_text(
            json.dumps(record, indent=1) + "\n", encoding="utf-8"
        )
        checks = " ".join(
            f"{k}={'ok' if record[k]['ok'] else 'FAIL'}"
            for k in ("review", "pay_order", "plan_trace", "labeling", "plan_check")
        )
        print(
            f"{folder.name}: scorer={record['review']['scorer']} traces={record['plan_trace']['traces']} "
            f"mismatches={len(record['plan_trace']['mismatches'])} {checks} passed={record['passed']}",
            flush=True,
        )


if __name__ == "__main__":
    main()
