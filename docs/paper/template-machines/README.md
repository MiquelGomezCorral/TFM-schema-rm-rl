# Single-template machines, hard and soft

The eight IBM templates the generator can choose (Absence, ChainResponse, Existence, ExistenceTwo,
NotCoExistence, Precedence, RespondedExistence, Response), each compiled alone by the pipeline on `main`, once hard
and once soft: 16 Reward Machines for the thesis appendix "IBM template examples". No model call: each clause goes
from its template to LTLf (`ltlf_of`), to a MONA DFA (`flat_tool.compile_dfa`) and through the reward layer
(`build_reward_machine`), and the machine text is parsed back with `parse_paper_reward_machine` and drawn.

## What it shows

`preview.pdf` holds the two figures of the appendix (`fig:templates-alone-1` and `-2`): hard on the left, soft on
the right, one row per template. Each row's caption carries the plain-language task, the clause and its LTLf
formula. Reading the figures:

- Rewards are the config's: +1 per progress step, +10 completion (+11 with the last progress step), -10 the well,
  -1 a soft break. A double ring is a final state and grey the rejecting well. An arrow joins the guards of the same
  pay; green pays, red only costs, grey pays nothing or holds both signs (`render-rm`'s rule).
- Only Absence, Precedence, ChainResponse and NotCoExistence can be broken for good, so only their hard machines
  have a well. The goal templates (Existence, ExistenceTwo) give the hard machine its final state. A soft machine
  never has a well.
- RespondedExistence and Response give the same machine hard and soft: their DFA has no violated state, so no
  rule can be broken.
- A soft violation re-arms: the violated state takes the start state's edges, so each new break pays again (soft
  Absence folds into one priced loop on `u0`).

## Settings

Soft is the frozen pipeline's default: `recurrent_soft_penalty=True`, `fold_soft_absence=True`,
`minimize_machine=True` and `soft_break_cost=1` (`app/src/config/config.py`), with `RewardSwitches()` at its
defaults (hard ceiling on, end judgment off).

## Evidence

`build.py` stops before writing anything unless every machine passes its checks: each reward is one the config
gives (0, +-1, -1 per soft break, +10/+11, -10); every edge into the well pays the well charge; a hard machine has a
well exactly when its clause has a violated DFA state; a soft machine has none; final states exist exactly for the
hard goal templates; no soft clause is inert; and the TeX formula in the captions equals the raw LTLf of the
pipeline token for token. All 16 passed. `preview.pdf` was read page by page as PNG at 110 dpi and in 200 dpi
crops: no label overlaps a state or the neighbouring drawing, and nothing overflows (no `Overfull` in the log).

## Gaps

- The tasks are hand-written illustrations (reused from the October template catalogue); the clauses use the
  DoorKey propositions `has_key`, `door_open` and `key_lost`.
- Node positions and label places are laid out by hand in `LAYOUT` (cm), as in `results-figures/draw_machines.py`.
  A new template or a changed compiler needs a new layout entry; the script stops on an unknown machine.
- The hard machines of the four unbreakable templates (Existence, ExistenceTwo, RespondedExistence, Response) have
  no well by design.
- Soft ChainResponse: a step that breaks the rule (`has_key` owes the door, the door stays shut) and also has
  `has_key` goes back to `u0`, so that `has_key` does not owe the next step again. This is the pipeline's re-arm
  design, drawn as it writes it.

## Files

`build.py`, `data/machines.json` (per machine: clause, setting, task, LTLf, states, edges with guard and reward,
the RM text), `preview.tex`, `preview.pdf`. It writes `paper/images/templates/<Template>-hard.tex`,
`<Template>-soft.tex` (16) and `all.tex` (the two figure environments, ready to `\input`).

## Rerun

From the repository root, in `RM_RL_env` (no model call):

    env PYTHONPATH=app:docs/paper/results-figures python -P docs/paper/template-machines/build.py

then, to regenerate the preview, in this folder:

    TEXINPUTS=../../../paper: latexmk -pdf preview.tex

## Code

Built on `main` at `5f9674ea` with `app/` unchanged. Style from `docs/paper/results-figures/draw_machines.py`
(`arrow_colour`, `reward_text`) and `paper/images/results/fig-palette.tex`.
