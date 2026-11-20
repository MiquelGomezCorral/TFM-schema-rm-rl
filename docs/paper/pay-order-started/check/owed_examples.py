"""The packet's examples of the new "started" rule: per state, the propositions still owed to the goal.

Builds each clause set with the default pay (MONA, no LLM) and prints every state's owed count
(``pay_order._owed``), whether the check reads it as started, and the pay-order summary.

Usage: PYTHONPATH=<app> python owed_examples.py

Paper copy of P/checks-fix/owed_examples.py: it also prints each clause's LTLf and writes each
machine to ``graphs/<slug>.rm`` for the page (draw with ``app/main.py render-rm --html``).
"""

import math
from pathlib import Path

from flat_tool import compile_dfa
from pylogics.syntax.ltl import Atomic

from src.arm_fm.pay_order import _owed, pay_order
from src.compiler import parse_paper_reward_machine, serialize_reward_machine
from src.compiler.ltlf import to_flat_syntax
from src.compiler.reward_layer import RewardSwitches, build_reward_machine
from src.engines.structured import SUPPORTED_TEMPLATES
from src.utils import ltlf_of

GRAPHS = Path(__file__).resolve().parent.parent / "graphs"
SLUGS = {
    "door before box (Precedence + Existence)": "door-before-box",
    "never both drop the key and open the door, + box": "never-both-box",
    "if the siren sounds toggle the switch, + exit (cx-siren)": "cx-siren",
    "key, then door, then box (Existence per step)": "key-door-box-chain",
}

EXAMPLES = {
    "door before box (Precedence + Existence)": [
        ("Precedence", ("door_open", "target_picked_up"), "hard"),
        ("Existence", ("target_picked_up",), "hard"),
    ],
    "never both drop the key and open the door, + box": [
        ("NotCoExistence", ("key_lost", "door_open"), "hard"),
        ("Existence", ("target_picked_up",), "hard"),
    ],
    "if the siren sounds toggle the switch, + exit (cx-siren)": [
        ("Response", ("siren_ringing", "switch_toggled"), "hard"),
        ("Existence", ("at_exit",), "hard"),
    ],
    "key, then door, then box (Existence per step)": [
        ("Existence", ("has_key",), "hard"),
        ("Existence", ("door_open",), "hard"),
        ("Existence", ("target_picked_up",), "hard"),
        ("Precedence", ("has_key", "door_open"), "hard"),
        ("Precedence", ("door_open", "target_picked_up"), "hard"),
    ],
}


def machine_of(clauses):
    dfas = []
    for pattern, names, _ in clauses:
        template, _ = SUPPORTED_TEMPLATES[pattern]
        dfas.append(compile_dfa(to_flat_syntax(template(*map(Atomic, names)).to_ltlf())))
    soft = [priority == "soft" for *_, priority in clauses]
    built = build_reward_machine(dfas, soft, RewardSwitches(step_limit=300))
    props = sorted({name for _, names, _ in clauses for name in names})
    text = serialize_reward_machine(built.reward_machine)
    return parse_paper_reward_machine(text, propositions=props), text


def main():
    for title, clauses in EXAMPLES.items():
        machine, text = machine_of(clauses)
        (GRAPHS / f"{SLUGS[title]}.rm").write_text(text if text.endswith("\n") else text + "\n")
        owed = _owed(machine)
        start = owed.get(machine.initial_state, math.inf)
        print(f"== {title} (graphs/{SLUGS[title]}.rm)")
        for pattern, names, priority in clauses:
            print(f"  {priority} {pattern}({', '.join(names)}): {ltlf_of(pattern, names)}")
        for state in machine.states:
            if state in machine.rejecting_states:
                continue
            role = (
                "start"
                if state == machine.initial_state
                else "final"
                if state in machine.final_states
                else "started"
                if owed.get(state, math.inf) < start
                else "not started"
            )
            print(f"  {state}: owes {owed.get(state, math.inf):g} ({role})")
        print("  pay order:", pay_order(machine, 0.99, 300).summary())


if __name__ == "__main__":
    main()
