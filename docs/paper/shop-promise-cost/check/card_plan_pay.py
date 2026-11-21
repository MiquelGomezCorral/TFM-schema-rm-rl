"""Plan pay and judging of one card's plans through one or more bundles. No model call.

Usage (worktree root, RM_RL_env, MONA on the PATH for the clause status):
    PYTHONPATH=app python card_plan_pay.py OUT.json TASKS.json CARD_ID BUNDLE [BUNDLE ...]

For each bundle: the machine's shape and rewards, the recorded pricing, the pay-order verdict and
stamp, the scorer status of its stored clauses against the card (``clause_status``), and the card's
solve, wrong and idle plans on seeds 1-3 plus the card's own reset seeds: the judge's verdict
(``judge_trace`` on the reference labels; a wrong plan must fail exactly its ``breaks``), whether the
bundle's labeling agrees with the reference labels on every step, and the machine pay up to the
first final or well state (plain and discounted at the bundle's gamma, as training ends there).
``order`` lists every seed where a wrong plan or idle pays at least the solve, discounted.
"""

import json
import sys
from multiprocessing import Pool
from pathlib import Path

from src.arm_fm.artifacts import load_bundle
from src.arm_fm.environments import gym_step_limit
from src.benchmark.cards import load_cards
from src.benchmark.declare_judge import judge_trace
from src.benchmark.plans import PlanError, run_plan
from src.benchmark.rm_facts import _normalized, clause_status
from src.benchmark.traces import make_record, replay_in_bundle

SEEDS = (1, 2, 3)


def plans_of(card) -> list[tuple[str, list, list | None]]:
    limit = gym_step_limit(card.env["gym_id"], **(card.env.get("env_kwargs") or {}))
    wrong = [(f"wrong-{i}", w["steps"], w.get("breaks") or []) for i, w in enumerate(card.wrong)]
    return [("solve", list(card.solve), None), *wrong, ("idle", [{"do": "wait", "n": limit}], None)]


def rollout_job(job):
    card, name, steps, seed = job
    try:
        return name, seed, run_plan(card.env, steps, seed)
    except PlanError as error:
        return name, seed, f"cannot run: {str(error)[:200]}"


def verdict(card, name: str, breaks, rollout) -> dict:
    judgment = judge_trace(card.expect, rollout.labels)
    row = {"judged": judgment.to_dict()["verdicts"], "failed": judgment.failed()}
    if name == "solve":
        row["as_card"] = judgment.success
    elif breaks is not None:
        row["as_card"] = sorted(judgment.failed()) == sorted(breaks)
    return row


def pay(bundle, card, name: str, rollout) -> dict:
    replay = replay_in_bundle(bundle, make_record("", card, name, "plan", rollout))
    machine = bundle.reward_machine
    gamma = bundle.manifest.effective_settings.get("gamma", 0.99)
    finals, well = set(machine.final_states), set(machine.rejecting_states)
    states = replay.rm_states  # states[0] is the start state, states[i] after step i
    stop = next((i for i, s in enumerate(states) if s in finals | well), len(states) - 1)
    rewards = replay.rewards[:stop]
    end = "final" if states[stop] in finals else "well" if states[stop] in well else "cut"
    used = bundle.labeling_propositions
    mismatches = [
        i + 1
        for i, (mine, ref) in enumerate(zip(replay.valuations, rollout.labels, strict=False))
        if any(bool(mine.get(p)) != bool(ref.get(p)) for p in used)
    ]
    return {
        "plain": round(sum(rewards), 4),
        "discounted": round(sum(gamma**i * r for i, r in enumerate(rewards)), 4),
        "end": f"{end}@{stop}",
        "in_well": end == "well",
        "labeling_mismatch_steps": mismatches[:5],
        "error": replay.error or None,
    }


def order_problems(plans: dict) -> list[str]:
    problems = []
    for name, seeds in plans.items():
        for seed, row in seeds.items():
            solve = plans["solve"].get(seed, {})
            if name == "solve" or "pay" not in row or "pay" not in solve:
                continue
            if row["pay"]["discounted"] >= solve["pay"]["discounted"]:
                problems.append(
                    f"{name} s{seed} pays {row['pay']['discounted']} >= solve "
                    f"{solve['pay']['discounted']}"
                )
    return problems


def bundle_table(path: Path, card, rows: list) -> dict:
    bundle = load_bundle(path)
    machine = bundle.reward_machine
    settings = bundle.manifest.effective_settings
    stored = _normalized(bundle.manifest.generation.get("clauses"))
    breaks = {name: b for name, _, b in plans_of(card)}
    plans: dict = {}
    for name, seed, rollout in rows:
        if isinstance(rollout, str):
            plans.setdefault(name, {})[seed] = {"error": rollout}
            continue
        plans.setdefault(name, {})[seed] = {
            **verdict(card, name, breaks[name], rollout),
            "pay": pay(bundle, card, name, rollout),
        }
    return {
        "bundle": str(path),
        "card": card.id,
        "task": card.task,
        "stored_clauses": stored,
        "clause_status": clause_status(stored, card),
        "states": list(machine.states),
        "finals": list(machine.final_states),
        "wells": list(machine.rejecting_states),
        "transitions": [
            [t.source, t.condition, t.destination, float(t.reward)] for t in machine.transitions
        ],
        "descriptions": dict(bundle.state_descriptions),
        "settings": {k: v for k, v in settings.items() if k not in ("embedding", "pay_order")},
        "pay_order": (settings.get("pay_order") or {}).get("summary"),
        "stamp": bundle.manifest.provenance.get("stamp"),
        "complete": bundle.complete,
        "plans": plans,
        "order_problems": order_problems(plans),
    }


def main() -> None:
    out, tasks, card_id, *bundles = sys.argv[1:]
    card = next(c for c in load_cards(Path(tasks)).cards if c.id == card_id)
    seeds = sorted({*SEEDS, *card.reset_seeds(1)})
    jobs = [(card, name, steps, seed) for name, steps, _ in plans_of(card) for seed in seeds]
    with Pool(8) as pool:
        rows = pool.map(rollout_job, jobs)
    tables = [bundle_table(Path(path), card, rows) for path in bundles]
    Path(out).write_text(json.dumps(tables, indent=1) + "\n", encoding="utf-8")
    for table in tables:
        print(f"== {table['bundle']} | {table['clause_status']} | states {table['states']}")
        print(f"   pay order: {table['pay_order']}")
        for name, by_seed in table["plans"].items():
            cells = []
            for seed, row in by_seed.items():
                if "error" in row:
                    cells.append(f"s{seed} {row['error']}")
                    continue
                p = row["pay"]
                flag = "" if row.get("as_card", True) else " NOT-AS-CARD"
                lab = (
                    f" LABEL{p['labeling_mismatch_steps']}" if p["labeling_mismatch_steps"] else ""
                )
                cells.append(
                    f"s{seed} {p['plain']:g}/{p['discounted']:g} {p['end']} fail{row['failed']}"
                    f"{flag}{lab}"
                )
            print(f"   {name:8} " + " | ".join(cells))
        print(f"   order problems: {table['order_problems'] or 'none'}")


if __name__ == "__main__":
    main()
