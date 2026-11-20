"""The page's sample cards: task, clauses, LTLf and the Reward Machine of each card's answer.

Usage: PYTHONPATH=app python -W ignore docs/paper/benchmark-coverage/check/card_machines.py     (from the repository root)
No model call. The samples are the ones the card review picked per group (`evidence/groups-v2.json`).
Each card is read from the pinned cards (`evidence/cards/<suite>/tasks.json`, main `6606ab7`); its
`expect` set is compiled with the repository's compiler (MONA) and the default reward switches at the
level's step limit, and written to `graphs/<card>.rm` when it has at most `MAX_DRAWN_TRANSITIONS`
transitions (the script prints the size of the others). Draw each with
`python app/main.py render-rm --rm-file graphs/<card>.rm --svg-dir graphs/<card>.svg --html`.
"""

import json
from pathlib import Path

from flat_tool import compile_dfa

from src.arm_fm.environments import gym_step_limit
from src.compiler import serialize_reward_machine
from src.compiler.reward_layer import RewardSwitches, build_reward_machine
from src.utils import ltlf_of

ENTRY = Path(__file__).resolve().parent.parent
EVIDENCE = ENTRY / "evidence"
# shop-boil's six rules compile to 65 states and 10,662 transitions (2.4 MB of text): no graph can show it.
MAX_DRAWN_TRANSITIONS = 500


def pinned_cards() -> dict[str, tuple[str, dict]]:
    cards = {}
    for path in sorted((EVIDENCE / "cards").glob("*/tasks.json")):
        for card in json.loads(path.read_text())["cards"]:
            cards[card["id"]] = (path.parent.name, card)
    return cards


def compile_rm(expect: list, step_limit: int | None) -> str:
    dfas = [compile_dfa(ltlf_of(pattern, props)) for pattern, props, _ in expect]
    soft = [priority == "soft" for _, _, priority in expect]
    built = build_reward_machine(dfas, soft, RewardSwitches(step_limit=step_limit))
    return serialize_reward_machine(built.reward_machine)


def main() -> None:
    cards = pinned_cards()
    groups = json.loads((EVIDENCE / "groups-v2.json").read_text())
    done = set()
    for group in groups:
        for sample in group["samples"]:
            card_id = sample["id"]
            if card_id in done:
                continue
            done.add(card_id)
            suite, card = cards[card_id]
            env = card["env"]
            limit = gym_step_limit(env["gym_id"], **env.get("env_kwargs", {}))
            lines = compile_rm(card["expect"], limit).splitlines()
            states = next(line for line in lines if line.startswith("STATES:")).count(",") + 1
            transitions = lines.index("REWARD_FUNCTION:") - lines.index("TRANSITION_FUNCTION:") - 1
            if transitions <= MAX_DRAWN_TRANSITIONS:
                (ENTRY / "graphs" / f"{card_id}.rm").write_text("\n".join(lines) + "\n")
            print(
                f"== {card_id} ({suite}, {env['gym_id']}, step limit {limit}, train {card.get('train')})"
            )
            print(f"   task: {card['task']}")
            for pattern, props, priority in card["expect"]:
                print(f"   {priority:4} {pattern}({', '.join(props)}): {ltlf_of(pattern, props)}")
            drawn = (
                "graphs/" + card_id + ".rm"
                if transitions <= MAX_DRAWN_TRANSITIONS
                else "too large to draw, not written"
            )
            print(f"   {states} states, {transitions} transitions: {drawn}")


if __name__ == "__main__":
    main()
