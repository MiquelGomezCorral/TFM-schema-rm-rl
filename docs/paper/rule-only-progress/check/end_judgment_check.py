"""The end judgment on the real code: what an open promise costs when the environment ends the episode.

Run from the repository root, inside RM_RL_env (no LLM calls; MONA and FL-AT run locally):

    PYTHONPATH=app python -W ignore docs/paper/rule-only-progress/check/end_judgment_check.py

Compiles Response(box_fell, box_on_shelf) alone, hard and soft, and a task with two hard Response
rules and a hard Absence. Plays short episodes through `RewardMachineEnvironment` with the time limit
after the last step and asserts each total. The last three show the consequence the note discloses:
with two hard promises open, idling to the end (-2.1) costs more than breaking a hard rule on the
last step (-1.1). Exits 1 on any difference.
"""

import sys
from dataclasses import replace

import p2_sim as sim

from src.arm_fm.runtime import RewardMachineEnvironment, RewardMachineRuntime
from src.compiler import (
    PaperRewardMachine,
    compile_dfas,
    materialize_proposal,
    parse_paper_reward_machine,
    serialize_reward_machine,
)
from src.compiler.reward_layer import build_reward_machine
from src.config import PriorityLevel

BOX = ["box_fell", "box_on_shelf"]
ALARM = ["alarm_rings", "alarm_off"]
# A token lists the propositions true in a step, joined by "+"; "-" is a step with none.
SINGLE = {  # trace: (hard, soft, hard without the end judgment, soft without it)
    "box_fell box_on_shelf": (0, 0, -0.5, -0.5),
    "- -": (0, 0, -0.5, -0.5),
    "box_fell - -": (-1.1, -0.6, -0.6, -0.6),
}
TWO_HARD = {  # trace: total
    "box_fell+alarm_rings -": -2.1,
    "box_fell+alarm_rings key_lost": -1.1,
    "box_fell+alarm_rings box_on_shelf": -1.1,
}


class CutOffEnvironment:
    """Plays the given valuations, then the time limit ends the episode on the last step."""

    def __init__(self, valuations: list[dict[str, bool]]) -> None:
        self.valuations = valuations
        self.current: dict[str, bool] = {}
        self.index = 0

    def reset(self, **_kwargs):
        self.index = 0
        return 0, {}

    def step(self, _action):
        self.current = self.valuations[self.index]
        self.index += 1
        return 0, 0.0, False, self.index == len(self.valuations), {}


def compile_machine(clauses: list[tuple[str, list[str], str]]) -> PaperRewardMachine:
    """The clauses together, compiled by the real layer (recurrent soft rules on)."""
    proposal = materialize_proposal("probe", [sim.selection(*clause) for clause in clauses])
    dfas = compile_dfas(proposal, sim.CONFIG)
    soft = [clause.priority is PriorityLevel.SOFT for clause in proposal.clauses]
    result = build_reward_machine(dfas, soft, recurrent_soft_penalty=True)
    return parse_paper_reward_machine(serialize_reward_machine(result.reward_machine))


def episode_total(machine: PaperRewardMachine, trace: str) -> float:
    """The episode total through the wrapper, with the time limit after the last token."""
    valuations = [
        {name: name in token.split("+") for name in machine.propositions} for token in trace.split()
    ]
    labeling = {name: (lambda env, name=name: env.current[name]) for name in machine.propositions}
    environment = RewardMachineEnvironment(
        CutOffEnvironment(valuations), RewardMachineRuntime(machine), labeling
    )
    environment.reset()
    return round(sum(environment.step(0)[1] for _ in valuations), 9) + 0.0


def main() -> int:
    bad = []
    hard, soft = (compile_machine([("Response", BOX, priority)]) for priority in ("hard", "soft"))
    for trace, wanted in SINGLE.items():
        got = (
            episode_total(hard, trace),
            episode_total(soft, trace),
            episode_total(replace(hard, judgment=None), trace),
            episode_total(replace(soft, judgment=None), trace),
        )
        print(f"Response {trace!r:28} hard, soft, without: {got}")
        bad += [] if got == wanted else [f"Response {trace!r}: {got} != {wanted}"]
    two = compile_machine(
        [("Response", BOX, "hard"), ("Response", ALARM, "hard"), ("Absence", ["key_lost"], "hard")]
    )
    for trace, wanted in TWO_HARD.items():
        got = episode_total(two, trace)
        print(f"two hard promises {trace!r:36} total: {got}")
        bad += [] if got == wanted else [f"two hard promises {trace!r}: {got} != {wanted}"]
    if bad:
        print("FAIL:", bad)
        return 1
    print("PASS: every total matches; idling with two hard promises open costs more than the well")
    return 0


if __name__ == "__main__":
    sys.exit(main())
