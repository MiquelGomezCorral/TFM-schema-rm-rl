"""Compile one card's `expect` with today's compiler at the default pricing. No model call.

Usage (worktree root, RM_RL_env, MONA on the PATH):
    PYTHONPATH=app python compile_card.py TASKS.json CARD_ID LABELING.py OUT_FOLDER

Same path as `experiments/benchmark/scripts/build_forcing_bundles.py`: the card's clauses as the
compiler's proposal, MONA DFAs, `RewardSwitches` at their defaults over the level's step limit, the
given labeling, no state descriptions. Records the settings and the pay order in the manifest.
"""

import importlib.util
import sys
from dataclasses import asdict
from pathlib import Path

from flat_tool import compile_dfa

from src.arm_fm.environments import gym_step_limit
from src.arm_fm.generation import build_compiler_bundle
from src.arm_fm.pay_order import record_pay_order
from src.benchmark.cards import load_cards
from src.compiler import RewardSwitches
from src.compiler.pipeline import build_compilation_result
from src.models import EnvironmentDescription

BUILDER = Path("experiments/benchmark/scripts/build_forcing_bundles.py")


def proposal_of(task, expect):
    spec = importlib.util.spec_from_file_location(BUILDER.stem, BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.proposal_of(task, expect)


def main() -> None:
    tasks, card_id, labeling, out = sys.argv[1:]
    card = next(c for c in load_cards(Path(tasks)).cards if c.id == card_id)
    environment = EnvironmentDescription.from_file(card.env["description"], code=True)
    proposal = proposal_of(card.task, card.expect)
    dfas = tuple(compile_dfa(clause.ltlf_formula) for clause in proposal.clauses)
    switches = RewardSwitches(
        step_limit=gym_step_limit(card.env["gym_id"], **(card.env.get("env_kwargs") or {}))
    )
    result = build_compilation_result(environment, proposal, dfas, switches)
    bundle = build_compiler_bundle(
        result,
        labeling_source=Path(labeling).read_text(encoding="utf-8"),
        state_descriptions=None,
    )
    bundle.manifest.effective_settings.update(asdict(switches))
    print(record_pay_order(bundle)["summary"])
    print(bundle.save(Path(out), overwrite=True))


if __name__ == "__main__":
    main()
