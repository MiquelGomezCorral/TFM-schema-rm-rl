"""Pay-order sweep of every card clause set and every stored clause set; MONA, no LLM.

Adapted from pay-default-evidence/sweep_pay_order.py (that file stays untouched). The code under test
is the one PYTHONPATH points at (main's app, or the worktree's app); the cards come from CARD_ROOT.
Each row keeps the pay-order verdict, the priced machine text and, for a card set, the per-step pay
of the card's solving plan and of idling.

Usage: PYTHONPATH=<app> OMP_NUM_THREADS=2 python sweep.py CARD_ROOT OUT.jsonl
"""

import json
import multiprocessing as mp
import re
import sys
from pathlib import Path

from flat_tool import compile_dfa
from pylogics.syntax.ltl import Atomic

import src
from src.arm_fm.environments import gym_step_limit
from src.arm_fm.pay_order import pay_order
from src.arm_fm.runtime import RewardMachineRuntime
from src.benchmark.cards import load_cards
from src.compiler import parse_paper_reward_machine, serialize_reward_machine
from src.compiler.ltlf import to_flat_syntax
from src.compiler.reward_layer import RewardSwitches, build_reward_machine
from src.engines.structured import SUPPORTED_TEMPLATES

MAIN = Path("/home/turbotowerlnx/Documents/Master/TFM/TFM-schema-rm-rl")  # stored bundles live here
GAMMA = 0.99
_DFA = {}
_LIMIT = {}


def dfa_of(pattern, props):
    key = (pattern, tuple(props))
    if key not in _DFA:
        template, _ = SUPPORTED_TEMPLATES[pattern]
        _DFA[key] = compile_dfa(to_flat_syntax(template(*(Atomic(p) for p in props)).to_ltlf()))
    return _DFA[key]


def limit_of(env):
    key = (env["gym_id"], json.dumps(env.get("env_kwargs") or {}, sort_keys=True))
    if key not in _LIMIT:
        _LIMIT[key] = gym_step_limit(env["gym_id"], **(env.get("env_kwargs") or {}))
    return _LIMIT[key]


def card_sets(root):
    """(name, suite, card id, clauses, limit, trace folder) for every card expect and also_ok."""
    for path in sorted((root / "experiments/benchmark").glob("*/tasks.json")):
        suite = path.parent.name
        for card in load_cards(path).cards:
            limit = limit_of(card.env)
            options = [
                ("expect", card.expect),
                *[(f"also_ok#{i + 1}", o) for i, o in enumerate(card.also_ok)],
            ]
            for label, clauses in options:
                name = f"{suite}/{card.id}" + ("" if label == "expect" else f" {label}")
                yield (
                    name,
                    suite,
                    card.id,
                    [(p, tuple(ps), pr) for p, ps, pr in clauses],
                    limit,
                    path.parent / "traces",
                )


def stored_sets():
    """The distinct (clauses, step limit) of every stored bundle manifest, first path wins."""
    seen = {}
    for path in sorted(
        str(found)
        for tree in ("experiments", "outputs")
        for found in (MAIN / tree).glob("**/manifest.json")
    ):
        try:
            manifest = json.loads(Path(path).read_text())
        except (OSError, ValueError):
            continue
        clauses = (manifest.get("generation") or {}).get("clauses")
        if not clauses:
            continue
        limit = (manifest.get("effective_settings") or {}).get("step_limit") or 300
        seen.setdefault(json.dumps([clauses, limit]), path.replace(str(MAIN) + "/", ""))
    for key, path in seen.items():
        clauses, limit = json.loads(key)
        yield path, [(p, tuple(ps), pr) for p, ps, pr in clauses], limit


def plan_pay(machine, trace_file, props):
    """Per-step reward of the labels of a trace; the episode stops at a final or rejecting state."""
    labels = json.loads(Path(trace_file).read_text())["labels"]
    runtime = RewardMachineRuntime(machine, warning_handler=lambda _m: None)
    ends = {*machine.final_states, *machine.rejecting_states}
    pays = []
    for step in labels:
        moved = runtime.step({name: bool(step.get(name, False)) for name in props})
        pays.append(round(moved.reward, 6))
        if moved.destination in ends:
            break
    return pays


def idle_pay(machine, props, steps=60):
    runtime = RewardMachineRuntime(machine, warning_handler=lambda _m: None)
    ends = {*machine.final_states, *machine.rejecting_states}
    pays = []
    for _ in range(steps):
        moved = runtime.step(dict.fromkeys(props, False))
        pays.append(round(moved.reward, 6))
        if moved.destination in ends:
            break
    return pays


def one(job):
    name, source, clauses, limit, card_id, traces = job
    row = {"name": name, "source": source, "limit": limit, "clauses": clauses, "card": card_id}
    try:
        dfas = [dfa_of(p, ps) for p, ps, _ in clauses]
        soft = [pr == "soft" for _, _, pr in clauses]
        props = sorted({q for _, ps, _ in clauses for q in ps})
        built = build_reward_machine(dfas, soft, RewardSwitches(step_limit=limit))
        text = serialize_reward_machine(built.reward_machine)
        machine = parse_paper_reward_machine(text, propositions=props)
        order = pay_order(machine, GAMMA, limit, False, 1.0 if any(soft) else 0.0)
    except Exception as error:
        row["error"] = repr(error)
        return row
    row.update(
        ok=order.broken is None,
        broken=order.broken,
        summary=order.summary(),
        pay=order.pay,
        text=text,
        has_final=bool(machine.final_states),
        props=props,
    )
    if card_id is not None and traces is not None:
        for plan in ("solve", "wrong-0", "wrong-1", "wrong-2"):
            trace = Path(traces) / card_id / f"{plan}-s1.json"
            if trace.exists():
                row[f"plan_{plan}"] = plan_pay(machine, trace, props)
        row["idle"] = idle_pay(machine, props)
    return row


def main():
    root, out = Path(sys.argv[1]), Path(sys.argv[2])
    print("code under test:", src.__file__, file=sys.stderr)
    jobs = [
        (name, "card:" + suite, clauses, limit, card, str(traces))
        for name, suite, card, clauses, limit, traces in card_sets(root)
    ]
    n_cards = len(jobs)
    stored = list(stored_sets())
    traces_of = {job[4]: job[5] for job in jobs}
    for path, clauses, limit in stored:
        found = next(
            (
                re.sub(r"~p\d+$", "", part)
                for part in reversed(Path(path).parts)
                if re.sub(r"~p\d+$", "", part) in traces_of
            ),
            None,
        )
        jobs.append((path, "stored", clauses, limit, found, traces_of.get(found)))
    print(f"{n_cards} card sets, {len(stored)} stored sets", file=sys.stderr)
    with mp.Pool(8) as pool:
        rows = pool.map(one, jobs, chunksize=4)
    out.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    cards, stor = rows[:n_cards], rows[n_cards:]
    print(
        f"cards ok {sum(r.get('ok', False) for r in cards)}/{len(cards)}  stored ok "
        f"{sum(r.get('ok', False) for r in stor)}/{len(stor)}  errors {sum('error' in r for r in rows)}"
    )


if __name__ == "__main__":
    main()
