"""The order fix: the clue block for one clause set in two orders, with the repository's code.

Usage: PYTHONPATH=app python -W ignore docs/paper/critic-clues/check/clue_order.py     (from the repository root)
No model call. The set is the live check's candidate (`evidence/clues-fix/`): hard Existence(at_goal),
Existence(has_key) and RespondedExistence(at_goal, has_key). Before the fix (`600d6a0`), the second
order named the RespondedExistence redundant; since the fix both orders name Existence(has_key).
"""

from flat_tool import compile_dfa

from src.compiler.critic_clues import critic_clues
from src.compiler.pipeline import ClauseProposal
from src.compiler.reward_layer import build_reward_machine
from src.config import PriorityLevel
from src.utils import ltlf_of

GOAL = ("Existence", ("at_goal",))
KEY = ("Existence", ("has_key",))
RULE = ("RespondedExistence", ("at_goal", "has_key"))
ORDERS = {
    "order A: goal, rule, key": [GOAL, RULE, KEY],
    "order B: goal, key, rule": [GOAL, KEY, RULE],
}


def clue_block(clauses: list[tuple[str, tuple[str, ...]]]) -> str:
    proposals = [
        ClauseProposal(f"{p}{props}", p, props, PriorityLevel.HARD, ltlf_of(p, props))
        for p, props in clauses
    ]
    machine_dfas = [compile_dfa(c.ltlf_formula) for c in proposals]
    machine = build_reward_machine(machine_dfas, [False] * len(proposals)).reward_machine
    # The machine build may edit the DFAs it gets, so the clues read freshly compiled ones.
    return critic_clues(proposals, [compile_dfa(c.ltlf_formula) for c in proposals], machine)


def main() -> None:
    for name, clauses in ORDERS.items():
        print(f"== {name}")
        print(clue_block(clauses))


if __name__ == "__main__":
    main()
