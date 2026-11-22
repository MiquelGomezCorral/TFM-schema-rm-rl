"""Build the reference bundles of the XLand suite (the right answer) with no model call.

Usage (repository root, `RM_RL_env`, MONA on the PATH):
    PYTHONPATH=app python experiments/benchmark/scripts/build_xland_reference.py [--overwrite]

For each card of `experiments/benchmark/xland/tasks.json` it compiles the card's `expect` clauses
like `build_forcing_bundles.py` does (DECLARE template -> LTLf -> MONA DFA -> Reward Machine,
default reward switches priced over the card's level), adds the labeling of the code page's truth
table (only the machine's propositions) and saves the bundle to
`experiments/benchmark/xland/reference/<card-id>/`, outside `bundles/` because it is not an arm.
The bundles carry no state descriptions or embeddings: they serve the plan check, the labeling
check and `rm_state_encoding: one_hot` training.
"""

import argparse
from dataclasses import asdict
from pathlib import Path

from build_forcing_bundles import proposal_of
from flat_tool import compile_dfa
from render_xland import truth_expressions

from src.arm_fm.custom_envs.xland_env import RULESETS, Ruleset
from src.arm_fm.environments import gym_step_limit
from src.arm_fm.generation import build_compiler_bundle, record_bundle_stamp
from src.arm_fm.pay_order import record_pay_order
from src.benchmark.cards import load_cards
from src.compiler import RewardSwitches
from src.compiler.pipeline import build_compilation_result
from src.config import Configuration
from src.models import EnvironmentDescription

SUITE = Path("experiments/benchmark/xland")


def build_card(card, destination: Path, *, overwrite: bool) -> Path:
    """Compile one card, add its labeling, and save the bundle."""
    environment = EnvironmentDescription.from_file(card.env["description"], code=True)
    proposal = proposal_of(card.task, card.expect)
    dfas = tuple(compile_dfa(clause.ltlf_formula) for clause in proposal.clauses)
    switches = RewardSwitches(
        step_limit=gym_step_limit(card.env["gym_id"], **card.env.get("env_kwargs", {}))
    )
    result = build_compilation_result(environment, proposal, dfas, switches)
    truth = truth_expressions(Ruleset.decode(RULESETS[card.env["env_kwargs"]["ruleset"]]))
    used = sorted({name for _, propositions, _ in card.expect for name in propositions})
    labeling = "\n".join(f"def {name}(env):\n    return {truth[name]}\n" for name in used)
    bundle = build_compiler_bundle(result, labeling_source=labeling)
    bundle.manifest.effective_settings.update(asdict(switches))
    print(record_pay_order(bundle)["summary"])
    bundle.manifest.provenance = {
        "generator": "hand-written",
        "status": "reconstructed",
        "script": "experiments/benchmark/scripts/build_xland_reference.py",
    }
    # No model ran: the stamp keeps the commit and dirty flag, its reasoning field is cleared.
    record_bundle_stamp(bundle, Configuration(), (None, None), {})
    bundle.manifest.provenance["stamp"]["reasoning"] = None
    return bundle.save(destination, overwrite=overwrite)


def main() -> None:
    """Build every card's bundle under `<suite>/reference/`."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--overwrite", action="store_true", help="Replace existing bundles")
    args = parser.parse_args()
    for card in load_cards(SUITE / "tasks.json").cards:
        print(build_card(card, SUITE / "reference" / card.id, overwrite=args.overwrite))


if __name__ == "__main__":
    main()
