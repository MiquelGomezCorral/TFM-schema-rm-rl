"""Card review sweep: every card answer compiled with main's code, its pay order and plan pay. No LLM.

Every card answer (expect + also_ok): the pay order, the per-step pay of every fresh trace-bank plan,
and an idle plan judged and paid.

Usage: PYTHONPATH=app OMP_NUM_THREADS=2 python review_sweep.py TB_ROOT OUT.jsonl

Copied from the plan folder's card-fix/sweep.py; this note and the lint fixes the repository's hooks
asked for aside (formatting, two unused names), unchanged. TB_ROOT is a trace bank
(`app/main.py trace-bank`); the cards come from CARD_ROOT, by default the main checkout.
"""

import json
import multiprocessing as mp
import os
import sys
from pathlib import Path

from flat_tool import compile_dfa
from pylogics.syntax.ltl import Atomic

from src.arm_fm.environments import gym_step_limit
from src.arm_fm.pay_order import pay_order
from src.arm_fm.runtime import RewardMachineRuntime
from src.benchmark.cards import load_cards
from src.benchmark.declare_judge import judge_trace
from src.benchmark.plans import run_plan
from src.compiler import parse_paper_reward_machine, serialize_reward_machine
from src.compiler.ltlf import to_flat_syntax
from src.compiler.reward_layer import RewardSwitches, build_reward_machine
from src.config import Configuration
from src.engines.structured import SUPPORTED_TEMPLATES

C = Path(os.environ.get("CARD_ROOT", "/home/turbotowerlnx/Documents/Master/TFM/TFM-schema-rm-rl"))
GAMMA = 0.99
IDLE = [{"do": "wait", "n": 1000}]


def dfa_of(pattern, props):
    template, _ = SUPPORTED_TEMPLATES[pattern]
    return compile_dfa(to_flat_syntax(template(*(Atomic(p) for p in props)).to_ltlf()))


def pay_of(machine, labels, props):
    runtime = RewardMachineRuntime(machine, warning_handler=lambda _m: None)
    ends = {*machine.final_states, *machine.rejecting_states}
    pays, end = [], None
    for step in labels:
        moved = runtime.step({name: bool(step.get(name, False)) for name in props})
        pays.append(round(moved.reward, 4))
        if moved.destination in ends:
            end = "final" if moved.destination in machine.final_states else "well"
            break
    return pays, end, runtime


def one(job):
    suite, card_id, label, clauses, limit, tb, _env, reset_seeds, plans = job
    row = {"suite": suite, "card": card_id, "answer": label, "clauses": clauses, "limit": limit}
    try:
        dfas = [dfa_of(p, ps) for p, ps, _ in clauses]
        soft = [pr == "soft" for _, _, pr in clauses]
        props = sorted({q for _, ps, _ in clauses for q in ps})
        built = build_reward_machine(dfas, soft, RewardSwitches(step_limit=limit))
        text = serialize_reward_machine(built.reward_machine)
        machine = parse_paper_reward_machine(text, propositions=props)
        cap = (
            Configuration.soft_breaks_per_step * Configuration.soft_break_cost if any(soft) else 0.0
        )
        order = pay_order(machine, GAMMA, limit, False, cap)
    except Exception as error:
        row["error"] = repr(error)
        return row
    row.update(
        ok=order.broken is None,
        summary=order.summary(),
        states=len(machine.states),
        has_final=bool(machine.final_states),
    )
    traces = {}
    for plan, _breaks in plans:
        for seed in reset_seeds:
            path = Path(tb) / suite / card_id / f"{plan}-s{seed}.json"
            if path.exists():
                labels = json.loads(path.read_text())["labels"]
                pays, end, _ = pay_of(machine, labels, props)
                traces[f"{plan}-s{seed}"] = {
                    "total": round(sum(pays), 3),
                    "end": end,
                    "n": len(pays),
                    "neg": [(i + 1, p) for i, p in enumerate(pays) if p < 0][:6],
                    "pos": [(i + 1, p) for i, p in enumerate(pays) if p > 0][:8],
                }
    row["traces"] = traces
    return row


def idle_job(job):
    suite, card_id, env, reset_seeds, expect = job
    out = {}
    for seed in reset_seeds:
        try:
            rollout = run_plan(env, IDLE, seed)
        except Exception as error:
            out[seed] = {"error": repr(error)}
            continue
        j = judge_trace(expect, rollout.labels)
        out[seed] = {**j.to_dict(), "steps": len(rollout.labels), "labels": rollout.labels}
    return suite, card_id, out


def main():
    tb, out = Path(sys.argv[1]), Path(sys.argv[2])
    jobs, idle_jobs = [], []
    limits = {}
    for path in sorted((C / "experiments/benchmark").glob("*/tasks.json")):
        suite = path.parent.name
        for card in load_cards(path).cards:
            key = (card.env["gym_id"], json.dumps(card.env.get("env_kwargs") or {}, sort_keys=True))
            if key not in limits:
                limits[key] = gym_step_limit(
                    card.env["gym_id"], **(card.env.get("env_kwargs") or {})
                )
            seeds = list(card.reset_seeds(1))
            plans = [("solve", None)] + [
                (f"wrong-{i}", w.get("breaks")) for i, w in enumerate(card.wrong)
            ]
            options = [
                ("expect", card.expect),
                *[(f"also_ok#{i}", o) for i, o in enumerate(card.also_ok)],
            ]
            for label, clauses in options:
                jobs.append(
                    (
                        suite,
                        card.id,
                        label,
                        [list(c) for c in clauses],
                        limits[key],
                        str(tb),
                        card.env,
                        seeds,
                        plans,
                    )
                )
            idle_jobs.append((suite, card.id, card.env, seeds, card.expect))
    with mp.Pool(8) as pool:
        rows = pool.map(one, jobs, chunksize=2)
        idles = pool.map(idle_job, idle_jobs, chunksize=2)
    idle_map = {(s, c): o for s, c, o in idles}
    # pay the idle labels through every answer machine
    for row in rows:
        if "error" in row:
            continue
        idle = idle_map[(row["suite"], row["card"])]
        clauses = row["clauses"]
        soft = [pr == "soft" for _, _, pr in clauses]
        props = sorted({q for _, ps, _ in clauses for q in ps})
        built = build_reward_machine(
            [dfa_of(p, ps) for p, ps, _ in clauses], soft, RewardSwitches(step_limit=row["limit"])
        )
        machine = parse_paper_reward_machine(
            serialize_reward_machine(built.reward_machine), propositions=props
        )
        for seed, item in idle.items():
            if "labels" in item:
                pays, end, _ = pay_of(machine, item["labels"], props)
                row["traces"][f"idle-s{seed}"] = {
                    "total": round(sum(pays), 3),
                    "end": end,
                    "n": len(pays),
                    "neg": [(i + 1, p) for i, p in enumerate(pays) if p < 0][:6],
                }
    with out.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    idle_out = out.with_name(out.stem + "-idle.json")
    idle_out.write_text(
        json.dumps(
            {
                f"{s}/{c}": {
                    k: {kk: vv for kk, vv in v.items() if kk != "labels"} for k, v in o.items()
                }
                for (s, c), o in idle_map.items()
            },
            indent=1,
        )
    )
    print(
        f"{len(rows)} answers, errors {sum('error' in r for r in rows)}, "
        f"pay-order broken {sum(1 for r in rows if r.get('ok') is False)}"
    )


if __name__ == "__main__":
    main()
