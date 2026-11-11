"""The window task: an event the agent did not cause costs a little, and the repair earns it back.

Run from the repository root, inside RM_RL_env (no LLM calls; MONA and FL-AT run locally):

    PYTHONPATH=app:docs/paper/rule-only-progress/check python -W ignore \
        docs/paper/rule-only-rewards/check/window_check.py

Compiles "Whenever a window breaks, fix it" (Response(window_broken, window_fixed)), hard and soft,
with the helpers of `rule-only-progress/check/end_judgment_check.py`, prints its RM text, and plays
short episodes through `RewardMachineEnvironment` with the time limit after the last step. Prints
the step rewards of the hard machine and asserts each total. Exits 1 on any difference.
"""

import sys
from dataclasses import replace

import end_judgment_check as box

from src.compiler import serialize_paper_reward_machine

WINDOW = ["window_broken", "window_fixed"]
# A token lists the propositions true in a step, joined by "+"; "-" is a step with none.
EPISODES = {  # trace: (hard, soft, hard without the end judgment, soft without it)
    "window_broken window_fixed": (0, 0, -0.5, -0.5),
    "window_broken - - window_fixed": (0, 0, -0.5, -0.5),
    "- -": (0, 0, -0.5, -0.5),
    "window_broken - -": (-1.1, -0.6, -0.6, -0.6),
}


def step_rewards(machine: box.PaperRewardMachine, trace: str) -> list[float]:
    """Each step's reward through the wrapper, with the time limit after the last token."""
    valuations = [
        {name: name in token.split("+") for name in machine.propositions} for token in trace.split()
    ]
    labeling = {name: (lambda env, name=name: env.current[name]) for name in machine.propositions}
    environment = box.RewardMachineEnvironment(
        box.CutOffEnvironment(valuations), box.RewardMachineRuntime(machine), labeling
    )
    environment.reset()
    return [round(environment.step(0)[1], 9) + 0.0 for _ in valuations]


def main() -> int:
    bad = []
    hard, soft = (
        box.compile_machine([("Response", WINDOW, priority)]) for priority in ("hard", "soft")
    )
    print(serialize_paper_reward_machine(hard))
    for trace, wanted in EPISODES.items():
        machines = (hard, soft, replace(hard, judgment=None), replace(soft, judgment=None))
        steps = [step_rewards(machine, trace) for machine in machines]
        got = tuple(round(sum(rewards), 9) + 0.0 for rewards in steps)
        print(f"{trace!r:34} hard steps {steps[0]}; totals hard, soft, without: {got}")
        bad += [] if got == wanted else [f"{trace!r}: {got} != {wanted}"]
    print("\n".join(bad) or "PASS: every total matches; the repair earns back what the break cost")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
