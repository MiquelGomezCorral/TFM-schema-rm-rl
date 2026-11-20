"""The page's sample (W3a): task, clauses, LTLf and RM before and after the fix, from the two replays.

Usage: PYTHONPATH=app python -W ignore docs/paper/hidden-output-schema/check/sample.py     (from the repository root)
No model call. Before = replay W3a-orig (original prompt), after = replay W3a-fix (shape named), both
sent from the same logged request. Each clause set is compiled with the repository's compiler (MONA)
at the level's step limit and written to `graphs/<name>.rm`. The after set is also the final set of
the at-scale run `runs/shape-max/A/W3a-r1`; the script checks that the stored machine of that run is
the same text.
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
CARD = ("templates", "tpl-chain-response-2-nogoal")
SAMPLES = {"before-W3a": "W3a-orig", "after-W3a": "W3a-fix"}


def compile_rm(clauses: list[dict], step_limit: int | None) -> str:
    dfas = [compile_dfa(ltlf_of(c["pattern"], c["propositions"])) for c in clauses]
    soft = [c["priority"] == "soft" for c in clauses]
    built = build_reward_machine(dfas, soft, RewardSwitches(step_limit=step_limit))
    return serialize_reward_machine(built.reward_machine)


def main() -> None:
    suite, card_id = CARD
    cards = json.loads((EVIDENCE / "cards" / suite / "tasks.json").read_text())["cards"]
    card = next(c for c in cards if c["id"] == card_id)
    limit = gym_step_limit(card["env"]["gym_id"], **card["env"].get("env_kwargs", {}))
    print(f"Task (NL): {card['task']}")
    print(f"Card {card_id}, step limit {limit}, expect: {card['expect']}")
    texts = {}
    for name, probe in SAMPLES.items():
        replay = json.loads((EVIDENCE / "probes" / f"{probe}.json").read_text())
        print(
            f"\n{name} (replay {probe}, finish_reason {replay['finish_reason']}): content {replay['content']}"
        )
        for c in replay["clauses"]:
            print(
                f"  {c['priority']:4} {c['pattern']}({', '.join(c['propositions'])}): "
                f"{ltlf_of(c['pattern'], c['propositions'])}"
            )
        texts[name] = compile_rm(replay["clauses"], limit)
        (ENTRY / "graphs" / f"{name}.rm").write_text(texts[name])
    stored = json.loads((EVIDENCE / "runs/shape-max/A/W3a-r1.json").read_text())["machine"]
    print(
        f"\nafter-W3a equals the stored machine of runs/shape-max/A/W3a-r1: {texts['after-W3a'] == stored}"
    )


if __name__ == "__main__":
    main()
