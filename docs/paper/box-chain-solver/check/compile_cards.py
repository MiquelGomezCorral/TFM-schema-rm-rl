"""Compile benchmark cards to the Reward Machine their clauses give. No provider call.

Run from the repository root, inside RM_RL_env:

    PYTHONPATH=app python compile_cards.py <out dir> <card id> [<card id> ...]

Each card's `expect` clauses go through the compiler's own path (clause templates -> LTLf -> MONA DFA ->
reward layer). It writes `<id>.rm.txt` (the machine, in the repository's RM text format) and prints the
card's natural-language task, each clause's LTLf and the state count. The machine is the reference
machine of the card, not the output of a language model.
"""

import json
import sys
from pathlib import Path

from pylogics.syntax.ltl import Atomic

from src.compiler import compile_dfas, materialize_proposal, serialize_reward_machine
from src.compiler.reward_layer import RewardSwitches, build_reward_machine
from src.config import Configuration, PriorityLevel
from src.engines.structured import SUPPORTED_TEMPLATES, ProposalSelection
from src.utils.presentation import ltlf_of, pretty_ltlf

CARDS = {
    c["id"]: c
    for suite in ("base", "templates", "complex")
    for c in json.loads(Path(f"experiments/benchmark/{suite}/tasks.json").read_text())["cards"]
}


def selection(pattern: str, propositions: tuple[str, ...], priority: str) -> ProposalSelection:
    template_class, _ = SUPPORTED_TEMPLATES[pattern]
    return ProposalSelection(
        normalized_clause=f"{pattern}({', '.join(propositions)})",
        pattern=pattern,
        propositions=propositions,
        priority=PriorityLevel(priority),
        template=template_class(*(Atomic(name) for name in propositions)),
    )


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    config = Configuration()
    for card_id in sys.argv[2:]:
        card = CARDS[card_id]
        selections = [selection(p, tuple(props), priority) for p, props, priority in card["expect"]]
        proposal = materialize_proposal(card["task"], selections)
        dfas = compile_dfas(proposal, config)
        soft = [clause.priority is PriorityLevel.SOFT for clause in proposal.clauses]
        result = build_reward_machine(dfas, soft, RewardSwitches.from_config(config))
        text = serialize_reward_machine(result.reward_machine)
        (out / f"{card_id}.rm.txt").write_text(
            text if text.endswith("\n") else text + "\n", encoding="utf-8"
        )
        print(f"{card_id}: {card['task']}")
        for p, props, priority in card["expect"]:
            print(f"  {p}({', '.join(props)}) [{priority}]  {pretty_ltlf(ltlf_of(p, props))}")
        print(f"  states: {len(result.reward_machine.states)}")


if __name__ == "__main__":
    main()
