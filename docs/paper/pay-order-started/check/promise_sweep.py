"""Pay-order sweep of every card answer with the promise cost ON (machine and check); MONA, no LLM.

The two other sweeps price with the promise cost off, so they cannot show the promise-cost-on shop
flag (known-errors: "Promise cost on makes the well a cheap exit"). This one builds every card
answer (expect + also_ok) with ``reward_promise_cost`` on and checks it with ``promise_cost=True``,
at the level's gym step limit. Code under test: the ``src`` PYTHONPATH points at.

Usage: PYTHONPATH=<app> OMP_NUM_THREADS=2 python promise_sweep.py CARD_ROOT OUT.jsonl
"""

import json
import multiprocessing as mp
import sys
from pathlib import Path

from flat_tool import compile_dfa
from pylogics.syntax.ltl import Atomic

import src
from src.arm_fm.environments import gym_step_limit
from src.arm_fm.pay_order import pay_order
from src.benchmark.cards import load_cards
from src.compiler import parse_paper_reward_machine, serialize_reward_machine
from src.compiler.ltlf import to_flat_syntax
from src.compiler.reward_layer import RewardSwitches, build_reward_machine
from src.config import Configuration
from src.engines.structured import SUPPORTED_TEMPLATES

GAMMA = 0.99


def dfa_of(pattern, props):
    template, _ = SUPPORTED_TEMPLATES[pattern]
    return compile_dfa(to_flat_syntax(template(*(Atomic(p) for p in props)).to_ltlf()))


def one(job):
    suite, card_id, label, clauses, limit = job
    row = {"suite": suite, "card": card_id, "answer": label, "clauses": clauses, "limit": limit}
    try:
        soft = [priority == "soft" for _, _, priority in clauses]
        props = sorted({name for _, names, _ in clauses for name in names})
        switches = RewardSwitches(step_limit=limit, reward_promise_cost=True)
        built = build_reward_machine([dfa_of(p, ps) for p, ps, _ in clauses], soft, switches)
        machine = parse_paper_reward_machine(
            serialize_reward_machine(built.reward_machine), propositions=props
        )
        cap = (
            Configuration.soft_breaks_per_step * Configuration.soft_break_cost if any(soft) else 0.0
        )
        order = pay_order(machine, GAMMA, limit, True, cap)
    except Exception as error:  # report only
        row["error"] = repr(error)
        return row
    row.update(ok=order.broken is None, summary=order.summary())
    return row


def main():
    root, out = Path(sys.argv[1]), Path(sys.argv[2])
    print("code under test:", src.__file__, file=sys.stderr)
    jobs, limits = [], {}
    for path in sorted((root / "experiments/benchmark").glob("*/tasks.json")):
        for card in load_cards(path).cards:
            key = (card.env["gym_id"], json.dumps(card.env.get("env_kwargs") or {}, sort_keys=True))
            if key not in limits:
                limits[key] = gym_step_limit(
                    card.env["gym_id"], **(card.env.get("env_kwargs") or {})
                )
            options = [
                ("expect", card.expect),
                *[(f"also_ok#{i}", o) for i, o in enumerate(card.also_ok)],
            ]
            for label, clauses in options:
                jobs.append(
                    (path.parent.name, card.id, label, [list(c) for c in clauses], limits[key])
                )
    with mp.Pool(8) as pool:
        rows = pool.map(one, jobs, chunksize=2)
    out.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    broken = [row for row in rows if row.get("ok") is False]
    print(f"{len(rows)} answers, errors {sum('error' in r for r in rows)}, broken {len(broken)}")
    for row in broken:
        print(f"  {row['suite']}/{row['card']} {row['answer']}: {row['summary']}")


if __name__ == "__main__":
    main()
