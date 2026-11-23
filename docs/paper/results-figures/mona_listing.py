"""The thesis's MONA figure and listing, rebuilt with the frozen compiler (deterministic, no model call).

Compiles the one hard clause Absence(key_lost) the way the pipeline does at the default reward switches and
writes ``figures/mona.rm.txt`` (the listing) and ``figures/mona-post2.tex`` (panel (c) of
``paper/images/farm/mona-post2.tex``, same layout and style). Checks the facts the thesis states: u0 is an
ordinary initial state, u1 the well, ``key_lost`` pays -10, no final or accepting state, no pending promises.

Run from the repository root, in RM_RL_env with MONA on PATH:
env PYTHONPATH=app python -P -W ignore docs/paper/results-figures/mona_listing.py
"""

from pathlib import Path

from flat_tool import compile_dfa

from src.compiler import serialize_reward_machine
from src.compiler.reward_layer import RewardSwitches, build_reward_machine
from src.utils import ltlf_of

FIGURES = Path(__file__).resolve().parent / "figures"

dfa = compile_dfa(ltlf_of("Absence", ["key_lost"]))
text = serialize_reward_machine(
    build_reward_machine([dfa], [False], RewardSwitches()).reward_machine
)

lines = text.splitlines()
assert lines[1:3] == ["STATES: u0, u1", "INITIAL_STATE: u0"], text
assert "FINAL_STATES:" in lines and "REJECTING_STATES: u1" in lines, text
assert not any(key in text for key in ("ACCEPTING_STATES", "FAILED_REWARD", "PENDING_PROMISES")), (
    text
)
assert lines[-4:-1] == ["TRANSITION_FUNCTION:", "(u0, key_lost) -> u1", "REWARD_FUNCTION:"], text
reward = int(lines[-1].removeprefix("(u0, key_lost, u1) -> "))
assert reward == -10, text
(FIGURES / "mona.rm.txt").write_text(text, encoding="utf-8")

# panel (c) of the old figure, minus the accepting ring on u0, with the machine's own reward
panel = (
    "\\node[state, initial] (u0) at (0.00,0.00) {u0};\n"
    "\\node[state, fill=gray!30] (u1) at (4.40,0.00) {u1};\n"
    "\\path[->] (u0) edge[] node[pos=0.35, align=center, font=\\scriptsize, fill=white, inner sep=1pt] "
    f"{{$\\texttt{{key\\_lost}}$ / ${reward}$}} (u1);\n"
)
(FIGURES / "mona-post2.tex").write_text(panel, encoding="utf-8")
print(text, end="")
