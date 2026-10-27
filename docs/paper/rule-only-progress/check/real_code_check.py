"""Simulation = code: the real reward layer (no patch) compiles the 20 machines alone to the "P2" texts.

Run from the repository root, inside RM_RL_env (no LLM calls; MONA and FL-AT run locally):

    PYTHONPATH=app python -W ignore docs/paper/rule-only-progress/check/real_code_check.py

Reads rm-texts.txt (each machine's "today" and "P2" text), compiles every machine with
`build_reward_machine` as it stands (the template list and `selection` come from p2_sim.py; its P2
patch is never applied) and checks:
  * the compiled text equals the "P2" text, byte for byte, for all 20, with the end judgment removed
    (it adds no transition and no REWARD_FUNCTION entry);
  * exactly the machines whose "P2" differs from "today" differ from "today": 9 (8 with the recurrent soft rules
    on, plus ChainResponse soft with them off); the rest equal their "today" text.
Exits 1 on any difference.
"""

import sys
from dataclasses import replace
from pathlib import Path

import p2_sim as sim

from src.compiler import compile_dfas, materialize_proposal, serialize_reward_machine
from src.compiler.reward_layer import build_reward_machine
from src.config import PriorityLevel

HERE = Path(__file__).resolve().parent
TEXTS = HERE / "rm-texts.txt"


def expected_texts() -> dict[str, tuple[str, str]]:
    """Map name -> (today, p2) from rm-texts.txt."""
    # The file is "\n".join(f"===== {head}\n--- today\n{today}\n--- P2\n{p2}\n") ending with one newline:
    # every block's P2 text is the RM text with its single final newline, and a block that is not the
    # last one is followed by a blank line.
    chunks = TEXTS.read_text(encoding="utf-8").split("===== ")[1:]
    blocks = {}
    for chunk in chunks:
        header, _, body = chunk.partition("\n--- today\n")
        today, _, p2 = body.partition("\n--- P2\n")
        blocks[header.split(" · ")[0]] = (today, p2.removesuffix("\n\n"))
    return blocks


def compile_real(pattern: str, props: list[str], priority: str):
    """The clause alone, compiled by the real layer; one (recurrent, text) per setting that matters."""
    proposal = materialize_proposal(
        f"{pattern} {priority}", [sim.selection(pattern, props, priority)]
    )
    dfas = compile_dfas(proposal, sim.CONFIG)
    soft = [clause.priority is PriorityLevel.SOFT for clause in proposal.clauses]
    texts = {}
    for recurrent in (False, True):
        layer = build_reward_machine(dfas, soft, recurrent_soft_penalty=recurrent)
        texts[recurrent] = serialize_reward_machine(replace(layer.reward_machine, judgment=None))
    return (
        [(True, texts[True])]
        if texts[False] == texts[True]
        else [(False, texts[False]), (True, texts[True])]
    )


def main() -> int:
    expected = expected_texts()
    bad, changed, seen = [], 0, set()
    for pattern, props in sim.TEMPLATES:
        for priority in ("hard", "soft"):
            for recurrent, text in compile_real(pattern, props, priority):
                name = f"{pattern}({', '.join(props)}) {priority}{'' if recurrent else ' (recurrent off)'}"
                seen.add(name)
                today, p2 = expected[name]
                same_p2 = text == p2
                differs_today = text != today
                changed += differs_today
                status = "ok" if same_p2 else "DIFF"
                if status == "DIFF":
                    bad.append(name)
                print(
                    f"{status:5} {name:70} equals P2: {same_p2!s:5} differs from today: {differs_today}"
                )
    if seen != set(expected):
        bad.append(f"machine names differ: {sorted(seen ^ set(expected))}")
    print(
        f"\n{len(seen)} machines, {changed} differ from today's text, {len(seen) - len(bad)} equal their P2 text"
    )
    if bad or len(seen) != 20 or changed != 9:
        print("FAIL:", bad, f"(machines {len(seen)}, changed {changed})")
        return 1
    print(
        "PASS: the real code, no patch, compiles all 20 machines to exactly their P2 text; 9 changed, 11 unchanged"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
