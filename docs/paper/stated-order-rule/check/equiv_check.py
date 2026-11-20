"""Is a FARM bundle the scorer calls `mismatch` the same task as an accepted answer? No model call.

Same task (LTLf): the hard clauses' conjunctions are equivalent and the soft ones' too, checked with
MONA: the minimal DFA of (A & ~B) | (~A & B) has no accepting state. Same machine: the answer's
clauses compiled with the bundle's recorded reward switches give the machine the bundle's own clauses
give, compared state by state over every valuation of the propositions (destination, reward, final or
rejecting, end charge), names aside. `extra` lists the bundle clauses beyond the answer when the
bundle holds the whole answer (the "implied extras" case).

Usage (cwd = worktree): PYTHONPATH=app python equiv_check.py OUT.json <suite>... | --bundle <suite>:<path>
"""

import itertools
import json
import sys
from collections import Counter
from pathlib import Path

from flat_tool import compile_dfa

from scripts.ablate_rm import _build, _recorded_switches, _stored_task
from src.arm_fm import load_bundle
from src.arm_fm.runtime import RewardMachineRuntime
from src.benchmark.cards import load_cards
from src.benchmark.declare_judge import ltlf_of
from src.benchmark.rm_facts import FARM, _normalized, clause_status
from src.benchmark.traces import BundleRef, find_bundles
from src.compiler import ClauseProposal, Proposal, compile_dfas
from src.config import Configuration, PriorityLevel
from src.utils import ltlf_of as pattern_ltlf

CONFIG = Configuration()
SUITES = Path("experiments/benchmark")


def conjunction(clauses, priority: str) -> str | None:
    parts = [ltlf_of((t, tuple(n), p))["raw"] for t, n, p in clauses if p == priority]
    return " & ".join(parts) or None


def empty(formula: str) -> bool:
    return not compile_dfa(formula, mona_executable=CONFIG.mona_executable)["accepting_states"]


def same_ltlf(first, second) -> bool:
    for priority in ("hard", "soft"):
        a, b = conjunction(first, priority), conjunction(second, priority)
        if a is None and b is None:
            continue
        if a is None or b is None:
            if not empty(f"~({a or b})"):  # one side has none: the other must hold on every trace
                return False
        elif not empty(f"(({a}) & ~({b})) | (~({a}) & ({b}))"):
            return False
    return True


def machine_of(bundle, clauses):
    environment, stored = _stored_task(CONFIG, bundle)
    proposal = Proposal(
        task=stored.task,
        clauses=tuple(
            ClauseProposal(
                f"{t}({', '.join(n)})", t, tuple(n), PriorityLevel(p), pattern_ltlf(t, n)
            )
            for t, n, p in clauses
        ),
    )
    return _build(
        environment, proposal, compile_dfas(proposal, CONFIG), _recorded_switches(bundle)
    )[1]


def steps_from(runs, pair, props):
    """Per valuation of ``props``, the step each runtime takes from its state in ``pair``."""
    for values in itertools.product((False, True), repeat=len(props)):
        valuation = dict(zip(props, values, strict=True))
        steps = []
        for run, state in zip(runs, pair, strict=True):
            run.state = state
            steps.append(run.step(valuation))
        yield steps


def same_machine(first, second) -> dict:
    """Walk both machines from their initial states over every valuation.

    ``structure`` is 'same' (states pair one to one, with the same final and rejecting kind) or the
    first difference; ``rewards`` lists each different transition reward or end charge, by state pair.
    """
    props = sorted(set(first.used_propositions) | set(second.used_propositions))
    runs = (
        RewardMachineRuntime(first, propositions=props),
        RewardMachineRuntime(second, propositions=props),
    )
    pairs, seen, todo, rewards = {}, set(), [(first.initial_state, second.initial_state)], set()
    while todo:
        pair = todo.pop()
        if pair in seen:
            continue
        seen.add(pair)
        a, b = pair
        if pairs.setdefault(a, b) != b:
            return {
                "structure": f"state {a} pairs with {pairs[a]} and {b}",
                "rewards": sorted(rewards),
            }
        kind = (
            (a in first.final_states, a in first.rejecting_states),
            (b in second.final_states, b in second.rejecting_states),
        )
        if kind[0] != kind[1]:
            return {
                "structure": f"{a} vs {b}: final/rejecting {kind[0]} vs {kind[1]}",
                "rewards": sorted(rewards),
            }
        charge = [
            m.judgment.end_charge(s) if m.judgment else None for m, s in ((first, a), (second, b))
        ]
        if charge[0] != charge[1]:
            rewards.add(f"{a}/{b} end charge {charge[0]} vs {charge[1]}")
        if kind[0] != (False, False):
            continue  # an ending state: the episode stops there
        for steps in steps_from(runs, pair, props):
            if steps[0].reward != steps[1].reward:
                rewards.add(
                    f"{a}->{steps[0].destination} / {b}->{steps[1].destination} reward {steps[0].reward} vs {steps[1].reward}"
                )
            todo.append((steps[0].destination, steps[1].destination))
    if (
        len(set(pairs.values())) != len(pairs)
        or len(pairs) != len(first.states)
        or len(set(pairs.values())) != len(second.states)
    ):
        return {
            "structure": f"reachable pairs {len(pairs)} for {len(first.states)} and {len(second.states)} states",
            "rewards": sorted(rewards),
        }
    return {"structure": "same", "rewards": sorted(rewards)}


def answers(card):
    options = [("expect", list(card.expect))]
    if card.forced:
        options.append(
            (
                "expect without forced",
                [c for i, c in enumerate(card.expect) if i not in card.forced],
            )
        )
    options += [(f"also_ok[{i}]", list(option)) for i, option in enumerate(card.also_ok)]
    return options


def check(suite: str, path: Path, card) -> dict:
    bundle = load_bundle(path)
    stored = _normalized(bundle.manifest.generation.get("clauses"))
    clauses = [(t, tuple(n), p) for t, n, p in stored or []]
    row = {
        "suite": suite,
        "bundle": str(path),
        "card": card.id,
        "status": clause_status(stored, card),
        "clauses": stored,
    }
    if row["status"] != "mismatch":
        return row
    own = machine_of(bundle, clauses)
    row["own_rebuilt_vs_stored"] = same_machine(own, bundle.reward_machine)
    row["equivalent_to"] = []
    for name, option in answers(card):
        if same_ltlf(clauses, option):
            extra = Counter(clauses) - Counter(option)
            holds_answer = not Counter(option) - Counter(clauses)
            answer = machine_of(bundle, option)
            row["equivalent_to"].append(
                {
                    "answer": name,
                    "extra": [list(c) for c in extra.elements()] if holds_answer else None,
                    "machine": same_machine(answer, own),
                    "states": [len(answer.states), len(own.states)],
                    "transitions": [len(answer.transitions), len(own.transitions)],
                }
            )
    return row


def main() -> None:
    out, *args = sys.argv[1:]
    rows = []
    if args[0] == "--bundle":
        suite, path = args[1].split(":", 1)
        cards = {c.id: c for c in load_cards(SUITES / suite / "tasks.json").cards}
        ref = BundleRef(FARM, Path(path).name, Path(path), ablation=False)
        rows.append(check(suite, ref.path, cards[ref.card_id]))
    else:
        for suite in args:
            cards = {c.id: c for c in load_cards(SUITES / suite / "tasks.json").cards}
            for ref in find_bundles(SUITES / suite / "bundles"):
                if ref.arm == FARM and not ref.ablation and ref.card_id in cards:
                    try:
                        rows.append(check(suite, ref.path, cards[ref.card_id]))
                    except Exception as error:  # a stored bundle can fail in any way; report it
                        rows.append(
                            {
                                "suite": suite,
                                "bundle": str(ref.path),
                                "error": f"{type(error).__name__}: {error}",
                            }
                        )
    Path(out).write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    counts = Counter(row.get("status", "error") for row in rows)
    print(f"{len(rows)} FARM bundles: {dict(counts)}")
    for row in rows:
        if row.get("status") == "mismatch" or "error" in row:
            print(
                json.dumps(
                    {
                        k: row.get(k)
                        for k in ("bundle", "error", "own_rebuilt_vs_stored", "equivalent_to")
                    }
                )
            )


if __name__ == "__main__":
    main()
