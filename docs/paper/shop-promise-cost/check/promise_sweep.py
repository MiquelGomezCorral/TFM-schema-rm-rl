"""Every card clause set (expect and also_ok) compiled with the promise cost on; MONA, no model call.

The two committed sweeps compile with the promise cost off; this one turns it on, so before/after shows
which promise-cost machines the well change touches (only edges into the well from a state with a
hard promise open may change).

Usage (the app under test on PYTHONPATH):
  python promise_sweep.py sweep CARD_ROOT OUT.jsonl
  python promise_sweep.py compare BEFORE.jsonl AFTER.jsonl
"""

import json
import multiprocessing as mp
import sys
from pathlib import Path

from flat_tool import compile_dfa
from pylogics.syntax.ltl import Atomic

from src.arm_fm.environments import gym_step_limit
from src.benchmark.cards import load_cards
from src.compiler import parse_paper_reward_machine, serialize_reward_machine
from src.compiler.ltlf import to_flat_syntax
from src.compiler.reward_layer import RewardSwitches, build_reward_machine
from src.engines.structured import SUPPORTED_TEMPLATES


def dfa_of(pattern, props):
    template, _ = SUPPORTED_TEMPLATES[pattern]
    return compile_dfa(to_flat_syntax(template(*(Atomic(p) for p in props)).to_ltlf()))


def one(job):
    name, clauses, limit = job
    row = {"name": name, "clauses": clauses, "limit": limit}
    try:
        soft = [priority == "soft" for _, _, priority in clauses]
        dfas = [dfa_of(pattern, props) for pattern, props, _ in clauses]
        built = build_reward_machine(
            dfas, soft, RewardSwitches(step_limit=limit, reward_promise_cost=True)
        )
        row["text"] = serialize_reward_machine(built.reward_machine)
    except Exception as error:
        row["error"] = f"{type(error).__name__}: {error}"
    return row


def sweep(root: Path, out: Path) -> None:
    jobs, limits = [], {}
    for path in sorted((root / "experiments/benchmark").glob("*/tasks.json")):
        for card in load_cards(path).cards:
            env = card.env
            key = (env["gym_id"], json.dumps(env.get("env_kwargs") or {}, sort_keys=True))
            if key not in limits:
                limits[key] = gym_step_limit(env["gym_id"], **(env.get("env_kwargs") or {}))
            options = [
                ("", card.expect),
                *[(f" also_ok#{i + 1}", o) for i, o in enumerate(card.also_ok)],
            ]
            for label, clauses in options:
                jobs.append(
                    (
                        f"{path.parent.name}/{card.id}{label}",
                        [list(c) for c in clauses],
                        limits[key],
                    )
                )
    with mp.Pool(8) as pool:
        rows = pool.map(one, jobs, chunksize=2)
    with out.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    print(len(rows), "clause sets,", sum("error" in row for row in rows), "errors")


def edges(row):
    props = sorted({p for _, ps, _ in row["clauses"] for p in ps})
    machine = parse_paper_reward_machine(row["text"], propositions=props)
    well = set(machine.rejecting_states)
    return {
        (t.source, t.destination, t.condition): (t.reward, t.destination in well)
        for t in machine.transitions
    }


def compare(before: Path, after: Path) -> None:
    old = {row["name"]: row for row in map(json.loads, before.read_text().splitlines())}
    new = {row["name"]: row for row in map(json.loads, after.read_text().splitlines())}
    same, changed, bad = 0, [], []
    for name, row in old.items():
        other = new[name]
        if row.get("error") or other.get("error"):
            if row.get("error") != other.get("error"):
                bad.append((name, row.get("error"), other.get("error")))
            continue
        if row["text"] == other["text"]:
            same += 1
            continue
        a, b = edges(row), edges(other)
        moved = [(k, a.get(k), b.get(k)) for k in a.keys() | b.keys() if a.get(k) != b.get(k)]
        off_well = [m for m in moved if not (m[1] and m[2] and m[1][1] and m[2][1])]
        changed.append(
            (name, len(moved), sorted({(m[1][0], m[2][0]) for m in moved if m[1] and m[2]}))
        )
        if off_well:
            bad.append((name, "a change off the well edges", off_well[:3]))
    print(
        f"{len(old)} clause sets: {same} identical, {len(changed)} changed, {len(bad)} with a change off the well"
    )
    for name, count, pairs in changed:
        print(f"  changed {name}: {count} well edges, reward before -> after {pairs[:4]}")
    for item in bad:
        print("  BAD", item)


if __name__ == "__main__":
    if sys.argv[1] == "sweep":
        sweep(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        compare(Path(sys.argv[2]), Path(sys.argv[3]))
