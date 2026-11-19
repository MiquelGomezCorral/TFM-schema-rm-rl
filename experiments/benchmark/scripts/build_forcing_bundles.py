"""Build the FARM bundles of the forcing suite with no model call.

Usage (repository root, `RM_RL_env`, MONA on the PATH):
    PYTHONPATH=app python experiments/benchmark/scripts/build_forcing_bundles.py [--overwrite]
    PYTHONPATH=app python app/main.py embed-larm --bundle <bundle folder> --embedding-server

For each card of `experiments/benchmark/forcing/tasks.json` it compiles the card's `expect` clauses
through the project's own compiler (DECLARE template -> LTLf -> MONA DFA -> Reward Machine, default
reward switches priced over the card's level, recorded in the manifest), adds the hand-written `labeling.py` (only the machine's propositions) and the
hand-written state descriptions below, and saves the bundle to
`experiments/benchmark/forcing/bundles/farm/<card-id>/`. The embeddings come from the second command
(local server on 127.0.0.1:8934); until then the bundle is not complete.
"""

import argparse
from dataclasses import asdict
from pathlib import Path

from flat_tool import compile_dfa
from pylogics.syntax.ltl import Atomic

from src.arm_fm.environments import gym_step_limit
from src.arm_fm.generation import build_compiler_bundle
from src.arm_fm.pay_order import record_pay_order
from src.benchmark.cards import load_cards
from src.benchmark.declare_judge import ltlf_of
from src.compiler import RewardSwitches
from src.compiler.ltlf import to_flat_syntax
from src.compiler.pipeline import ClauseProposal, Proposal, build_compilation_result
from src.config import PriorityLevel
from src.engines.structured import SUPPORTED_TEMPLATES
from src.models import EnvironmentDescription

SUITE = Path("experiments/benchmark/forcing")
# The labeling of each proposition: the state the environment already exposes, read after the step.
GRID_DOOR = (
    'any(cell is not None and cell.type == "door" and cell.is_open for x in range(env.width) '
    "for y in range(env.height) for cell in [env.grid.get(x, y)])"
)
LABELING = {
    "top_breach": '"top_breach" in env.events_this_step',
    "side_breach": '"side_breach" in env.events_this_step',
    "plant_trampled": '"plant_trampled" in env.events_this_step',
    "has_door_key": 'env.carrying is not None and env.carrying.type == "key"',
    "door_open": GRID_DOOR,
}

TOP_REJECT = (
    "A zombie got through the top lane, so the rule is broken for good. This is the rejecting "
    "state: the episode ends here and the break costs 1."
)
GIFT_IDLE = (
    "The agent holds no key that needs answering. It waits for a key to land in its hands; once "
    "it holds the key with the door shut, the rule is triggered."
)
DESCRIPTIONS = {
    "lanes-guard": {
        "u0": (
            "No zombie has got through the top lane yet, so the rule holds and costs nothing. The "
            "agent keeps it by killing every zombie of the top lane before it reaches the left end."
        ),
        "u1": TOP_REJECT,
    },
    "lanes-rules": {
        "u0": (
            "No zombie has got through the top lane and no soft penalty was just paid. The agent "
            "keeps the top lane clear, and tries to stop the zombies of the other lanes and to "
            "avoid the plants."
        ),
        "u1": TOP_REJECT,
        "u2": (
            "A zombie just got through the middle or the bottom lane: a soft rule broke and cost "
            "0.5. The top lane is still safe. The agent goes back to guarding it and to stopping "
            "the other zombies."
        ),
        "u3": (
            "The agent just stepped on a plant: a soft rule broke and cost 0.5. The top lane is "
            "still safe. The agent avoids plants from here on."
        ),
        "u4": (
            "A zombie got through a side lane and the agent stepped on a plant: both soft rules "
            "broke and cost 0.5 each. The top lane is still safe."
        ),
    },
    "keygift-hard": {
        "u0": GIFT_IDLE,
        "u1": (
            "The agent holds the key and the door is still shut, so it owes the rule: open the "
            "door. Toggling the door in front of it with the key in hand opens it, pays a small "
            "reward and returns to the start state. Staying here leaves a hard promise open."
        ),
    },
    "keygift-soft": {
        "u0": GIFT_IDLE,
        "u1": (
            "The agent holds the key and the door is still shut, so it owes the rule: try to open "
            "the door. Toggling the door in front of it with the key in hand opens it, pays a "
            "small reward and returns to the start state. Staying here leaves a soft promise open "
            "and it is charged when the episode ends."
        ),
    },
}


def labeling_source(propositions: set[str]) -> str:
    """One function per proposition of the machine, in name order."""
    return "\n".join(
        f"def {name}(env):\n    return {LABELING[name]}\n" for name in sorted(propositions)
    )


def proposal_of(task: str, expect: tuple) -> Proposal:
    """The task's clauses as the compiler's proposal; LTLf comes from the DECLARE template."""
    clauses = []
    for pattern, propositions, priority in expect:
        template, _arity = SUPPORTED_TEMPLATES[pattern]
        readable = ltlf_of((pattern, propositions, priority))["readable"]
        clauses.append(
            ClauseProposal(
                normalized_clause=f"{pattern}({', '.join(propositions)}), {priority}: {readable}",
                pattern=pattern,
                propositions=tuple(propositions),
                priority=PriorityLevel(priority),
                ltlf_formula=to_flat_syntax(template(*(Atomic(p) for p in propositions)).to_ltlf()),
            )
        )
    return Proposal(task=task, clauses=tuple(clauses))


def build_card(card, destination: Path, *, overwrite: bool) -> Path:
    """Compile one card, add its labeling and descriptions, and save the bundle."""
    environment = EnvironmentDescription.from_file(card.env["description"], code=True)
    proposal = proposal_of(card.task, card.expect)
    dfas = tuple(compile_dfa(clause.ltlf_formula) for clause in proposal.clauses)
    # The default pricing, over the step limit of the card's level.
    switches = RewardSwitches(
        step_limit=gym_step_limit(card.env["gym_id"], **card.env.get("env_kwargs", {}))
    )
    result = build_compilation_result(environment, proposal, dfas, switches)
    used = {name for _, propositions, _ in card.expect for name in propositions}
    bundle = build_compiler_bundle(
        result,
        labeling_source=labeling_source(used),
        state_descriptions=DESCRIPTIONS[card.id],
    )
    bundle.manifest.effective_settings.update(asdict(switches))
    print(record_pay_order(bundle)["summary"])
    bundle.manifest.provenance = {
        "generator": "hand-written",
        "status": "reconstructed",
        "script": "experiments/benchmark/scripts/build_forcing_bundles.py",
    }
    return bundle.save(destination, overwrite=overwrite)


def main() -> None:
    """Build every card's bundle under `<suite>/bundles/farm/`."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--overwrite", action="store_true", help="Replace existing bundles")
    args = parser.parse_args()
    for card in load_cards(SUITE / "tasks.json").cards:
        print(build_card(card, SUITE / "bundles" / "farm" / card.id, overwrite=args.overwrite))


if __name__ == "__main__":
    main()
