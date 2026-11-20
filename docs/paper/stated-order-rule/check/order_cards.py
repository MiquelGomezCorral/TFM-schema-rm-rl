"""Card changes of the stated-order rule, same-task checks and the drawn answers. No model call.

Usage, from the repository root inside RM_RL_env:
    PYTHONPATH=app python -W ignore docs/paper/stated-order-rule/check/order_cards.py

Reads each changed card before and after commit f29c47a from the pinned copies in
`evidence/cards/{before,after}/<suite>/tasks.json` and prints its task and both answer keys with the
LTLf of every clause. Then checks with MONA (`same_ltlf` of `equiv_check.py`: the hard conjunctions
are equivalent, and the soft ones too) which answers of each new card are the same task, and whether
the stored FARM bundle of the open card states the card's task. Compiles the three base-unlock-pickup
answers with the default reward switches, compares the machines, writes the facts and the chain to
`graphs/<name>.rm`, and writes everything it prints to `evidence/order-cards.out`.
"""

import json
from itertools import combinations
from pathlib import Path

from equiv_check import same_ltlf
from flat_tool import compile_dfa

from src.arm_fm.environments import gym_step_limit
from src.benchmark.declare_judge import ltlf_of
from src.benchmark.rm_facts import _normalized
from src.compiler import serialize_reward_machine
from src.compiler.reward_layer import RewardSwitches, build_reward_machine

ENTRY = Path(__file__).resolve().parent.parent
CARDS = ENTRY / "evidence" / "cards"
CHANGED = (
    ("base", "base-unlock-pickup"),
    ("smoke", "smoke-unlock-pickup-base"),
    ("pilot", "base-unlock-pickup"),
    ("base", "base-key-corridor"),
    ("templates", "tpl-responded-existence-2-goal"),
)
# The smoke and pilot cards copy base-unlock-pickup; main() asserts their new answers are the same.
COPIES = (("smoke", "smoke-unlock-pickup-base"), ("pilot", "base-unlock-pickup"))
OPEN_BUNDLE = Path("experiments/benchmark/templates/bundles/farm/tpl-responded-existence-2-goal")
DRAWN = (
    ("bup-facts", "expect"),
    ("bup-chain", "also_ok[0]"),
    ("bup-chain-existences", "also_ok[1]"),
)


def card(when: str, suite: str, card_id: str) -> dict:
    cards = json.loads((CARDS / when / suite / "tasks.json").read_text(encoding="utf-8"))["cards"]
    return next(c for c in cards if c["id"] == card_id)


def answers(card: dict) -> list[tuple[str, list]]:
    options = [("expect", card["expect"])]
    if card.get("forced"):
        required = [c for i, c in enumerate(card["expect"]) if i not in card["forced"]]
        options.append(("expect without forced (what `exact` required)", required))
    options += [(f"also_ok[{i}]", option) for i, option in enumerate(card["also_ok"])]
    return options


def clause_lines(clauses: list) -> list[str]:
    return [
        f"       {p:4} {t}({', '.join(n)}): {ltlf_of((t, tuple(n), p))['readable']}"
        for t, n, p in clauses
    ]


def card_lines(suite: str, card_id: str) -> list[str]:
    old, new = card("before", suite, card_id), card("after", suite, card_id)
    assert old["task"] == new["task"], f"{suite}/{card_id}: the task text changed"
    lines = [f"== {suite}/{card_id} ({new['env']['gym_id']}, train {new['train']})"]
    lines.append(f"   task: {new['task']}")
    for when, version in (("before", old), ("after", new)):
        lines.append(f"   {when} f29c47a, forced {version.get('forced', [])}:")
        for name, clauses in answers(version):
            lines.append(f"     {name}:")
            lines += clause_lines(clauses)
    return lines


def same_task_lines(new: dict) -> list[str]:
    return [
        f"   same task (MONA), {name_a} vs {name_b}: {same_ltlf(a, b)}"
        for (name_a, a), (name_b, b) in combinations(answers(new), 2)
    ]


def open_bundle_lines(new: dict) -> list[str]:
    manifest = json.loads((OPEN_BUNDLE / "manifest.json").read_text(encoding="utf-8"))
    stored = _normalized(manifest["generation"]["clauses"])
    lines = [f"   stored FARM bundle {OPEN_BUNDLE}:", *clause_lines(stored)]
    lines.append(f"   same task (MONA), expect vs the bundle: {same_ltlf(new['expect'], stored)}")
    return lines


def compiled_rm(clauses: list, step_limit: int | None) -> str:
    dfas = [compile_dfa(ltlf_of((t, tuple(n), p))["raw"]) for t, n, p in clauses]
    soft = [p == "soft" for _, _, p in clauses]
    built = build_reward_machine(dfas, soft, RewardSwitches(step_limit=step_limit))
    return serialize_reward_machine(built.reward_machine)


def drawn_lines(new: dict) -> list[str]:
    limit = gym_step_limit(new["env"]["gym_id"], **new["env"].get("env_kwargs", {}))
    options = dict(answers(new))
    lines = [f"== base/base-unlock-pickup answers, compiled (default switches, step limit {limit})"]
    texts = {}
    for name, which in DRAWN:
        texts[name] = compiled_rm(options[which], limit)
        rows = texts[name].splitlines()
        states = next(r for r in rows if r.startswith("STATES:")).count(",") + 1
        transitions = rows.index("REWARD_FUNCTION:") - rows.index("TRANSITION_FUNCTION:") - 1
        lines.append(f"   {which} ({name}): {states} states, {transitions} transitions")

    # == The chain with its implied Existences compiles to the chain's machine: draw one of them ==
    same = texts["bup-chain-existences"] == texts["bup-chain"]
    lines.append(f"   also_ok[1] gives the same machine text as also_ok[0]: {same}")
    live = (ENTRY / "graphs" / "live-b.rm").read_text(encoding="utf-8")
    lines.append(
        f"   also_ok[0] gives the live machine graphs/live-b.rm: {texts['bup-chain'] == live}"
    )
    for name in ("bup-facts", "bup-chain"):
        (ENTRY / "graphs" / f"{name}.rm").write_text(texts[name], encoding="utf-8")
        lines.append(f"   wrote graphs/{name}.rm")
    return lines


def main() -> None:
    lines = []
    base = card("after", "base", "base-unlock-pickup")
    for suite, card_id in CHANGED:
        lines += card_lines(suite, card_id)
        new = card("after", suite, card_id)
        if (suite, card_id) in COPIES:
            assert answers(new) == answers(base), f"{suite}/{card_id} differs from the base card"
            lines.append("   new answers: the same as base/base-unlock-pickup")
            continue
        lines += same_task_lines(new)
        if card_id == "tpl-responded-existence-2-goal":
            lines += open_bundle_lines(new)
    lines += drawn_lines(base)
    text = "\n".join(lines) + "\n"
    (ENTRY / "evidence" / "order-cards.out").write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
