"""The committed shop-serve machine without its fall rule: the old no-goal rule against the new one.

Takes the committed FARM bundle's stored clauses, drops the hard ChainResponse(food_fell,
holding_food) ("if the food falls, pick it up on your very next move"), rebuilds with the bundle's
recorded switches and the end judgment off, and runs the card's plan check (the new rule: every
wrong or idle run pays less than the solve, and a hard rule broken for good ends in the well).
Then lists the runs the old rule would fail: a hard break that ends open with nothing owed. MONA,
no model call. Writes the rebuilt machine to graphs/shop-serve-no-fall-rule.rm and what it prints
to evidence/no-fall-rule.out.

Usage, from the repository root inside RM_RL_env:
    PYTHONPATH=app python -W ignore docs/paper/shop-promise-cost/check/no_fall_rule.py

Adapted from the plan folder's shop-well/drop_rule.py (the reviewer's check): the bundle, card and
dropped rule are fixed here, and the machine text is written out for the graph.
"""

from dataclasses import replace
from pathlib import Path

from scripts.ablate_rm import _build, _recorded_switches, _stored_task
from src.arm_fm import load_bundle
from src.benchmark import load_cards
from src.benchmark.plan_check import check_card_plans
from src.compiler import compile_dfas, serialize_paper_reward_machine
from src.config import Configuration

ENTRY = Path(__file__).resolve().parent.parent
BUNDLE = Path("experiments/benchmark/shop/bundles/farm/shop-serve")
CARD_ID, DROPPED = "shop-serve", "ChainResponse"


def main() -> None:
    bundle = load_bundle(BUNDLE)
    config = Configuration(bundle=BUNDLE)
    environment, proposal = _stored_task(config, bundle)
    kept = tuple(clause for clause in proposal.clauses if clause.pattern != DROPPED)
    lines = [f"bundle {BUNDLE}: dropped {len(proposal.clauses) - len(kept)} clause(s): {DROPPED}"]
    proposal = replace(proposal, clauses=kept)
    switches = replace(_recorded_switches(bundle), reward_end_judgment=False)
    _, machine = _build(environment, proposal, compile_dfas(proposal, config), switches)
    (ENTRY / "graphs" / "shop-serve-no-fall-rule.rm").write_text(
        serialize_paper_reward_machine(machine), encoding="utf-8"
    )
    lines.append("wrote graphs/shop-serve-no-fall-rule.rm")
    cards = load_cards(Path("experiments/benchmark/shop/tasks.json")).cards
    card = next(card for card in cards if card.id == CARD_ID)
    record = check_card_plans(replace(bundle, reward_machine=machine), card, 42)
    lines.append(f"new rule passed: {record['passed']}")
    lines += [f"   problem: {problem}" for problem in record["problems"]]
    old_fail = [
        f"{run['plan']}-s{run['seed']}"
        for run in record["runs"]
        if run["kind"] == "hard-break" and run.get("end") == "open" and not run.get("owed")
    ]
    lines.append(f"old rule would fail: {old_fail}")
    lines += [
        f"   {run['plan']}-s{run['seed']} {run['kind']} end={run.get('end')} pay={run.get('pay')}"
        for run in record["runs"]
    ]
    text = "\n".join(lines) + "\n"
    (ENTRY / "evidence" / "no-fall-rule.out").write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
