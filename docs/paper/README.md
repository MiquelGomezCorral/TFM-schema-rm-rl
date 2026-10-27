# Paper evidence

Results worth citing in the paper: pages with visual proof, the data behind them, and the
scripts that reproduce them. Each entry is one folder that opens on its own from disk, with a
note below.

## How entries get here

- When work produces something worth citing (a before/after page, a measured result, a figure,
  a decisive check), the agent proposes it. It is copied here only after Miquel agrees.
- An entry keeps its page or figures, the inputs and script to rerun it, and a note here: what
  it shows, the evidence, the files, how to rerun it, and the code it refers to.
- Agent pages under `.git/agent-memory/artifacts/` are working copies and may be cleaned up.
  This folder is the copy that lasts.

## Entries

### MONA start-state merge (`mona-start-state-merge/`), 2026-10-13

**What it shows.** MONA gives each rule clause's automaton a start state that exists only before
the first step. The reward layer drops that state when nothing comes back to it and it moves
exactly like its idle successor on every input. The RM is the same machine with one state fewer,
and every reward stays the same. This is not minimisation: only the start can go, and only into
its idle successor.

**Evidence.**
- 25 sample RMs from the reward-layer test, each shown before, expected (before with the start
  removed) and got (what the compiler now writes): 25/25 match. 19 lose exactly one state, which
  is every task with a rule clause; the 6 goal-only RMs are unchanged.
- The check walks the expected and the new RM side by side on every input and pairs their states
  one to one: same rewards, same final and well, same state count.
- The code review also compiled 3,512 clause sets with and without the merge: identical rewards,
  finals and wells. The 253 reward-step checks (every episode total) still pass.

**Files.**
- `index.html`: open it in a browser. Six examples, before / expected / got. Each graph is the
  live RM component: drag a state, click an edge for its cases, Ctrl + scroll to zoom. The "RM
  text" fold-out under each graph has the exact transitions.
- `graphs/`: each of the 18 graphs as live HTML, SVG and RM text.
- `compare.txt`: the check's output for all 25 RMs. `data.json`: the page's content.
- `check/`: the check script, the 25 RMs from before the change (`before/`) and from after it
  (`after/`).

**Rerun** from the repository root, inside `RM_RL_env`:

```bash
PYTHONPATH=app python -W ignore docs/paper/mona-start-state-merge/check/start_merge_check.py compare \
  docs/paper/mona-start-state-merge/check/before docs/paper/mona-start-state-merge/check/after <output dir>
```

It prints one line per RM and ends with `25/25 RMs match the expected merge`; it also writes
the three drawings per RM into `<output dir>`.

**Code.** Commit `9b793a8` (`feat(compiler): drop the duplicate start state`),
`_drop_pre_step_start` in `app/src/compiler/reward_layer.py`; the design is in
`docs/COMPILER_REWARD_DESIGN.md`. The graphs were drawn with the interactive graph and layout
code of 2026-10-14, which was not yet committed when this copy was made; the check does not
depend on the drawing.

### Environment files (`environment-files/`), 2026-10-23

**What it shows.** How each environment is described with two files. `environment.md` holds the
environment at the top level only (what each proposition means and when the environment emits it).
`environment-code.md` holds all implementation (labeling API, source and runtime, truth conditions
in code, evidence) and adds to the facts file without copying it. The clause generator and the
critic read the facts file alone; the steps that write code (the ARM-FM baseline generator and the
labeling stage) load both as one text. A per-line test decides where a line goes: if it only helps
implement or verify, it belongs in the code file.

**Evidence.** A written convention, not a measured result. The worked example is the MiniGrid
DoorKey pair of final files. The note lists the eight sections of the facts file and the sections
of the code file with a one-line purpose each.

**Files.**
- `README.md`: the appendix note.
- `minigrid-doorkey.environment.md`, `minigrid-doorkey.environment-code.md`: the DoorKey pair
  (copied from `examples/arm-fm/minigrid-doorkey/`).

**Rerun.** The README holds a short script that joins the DoorKey pair the way the code steps do and
prints the proposition ids and the labeling API text.

**Code.** `EnvironmentDescription.from_file(path, code=True)` in `app/src/models/environment.py`
(the join), called by `generate_larm` in `app/scripts/generate_larm.py` and by the labeling stage of
`app/scripts/generate_rm.py`; the rule is in `docs/ENVIRONMENT_AUTHORING.md` and
`docs/decisions/arm-fm/catalogue-and-evidence.md`. Not committed when this entry was written.

### Recurrent soft rules (`recurrent-soft-rules/`), 2026-10-25

**What it shows.** Which soft rules charge −0.5 again at every new break, and why only those.
A soft rule re-arms only when its DFA has a "broken for good" state, which holds for Absence,
Precedence, ChainResponse and NotCoExistence. For these the goal is recovery: with one charge
per episode, the first break makes every later one free, and a penalty cannot be farmed. Rules
that only say "eventually" (Existence, ExistenceTwo, RespondedExistence) never break
mid-episode, and paying a goal again would invite reward farming. RespondedExistence has no
exact recurring version: the two ordered, stricter rules near it are Precedence (`y` before `x`)
and Response (`y` after `x`), and keeping "any order" would need counting, which the setup cannot
do. The note ends with a theory it did not try:
sending the Reward Machine back to its start while the environment keeps running, as the
cookie domain of Toro Icarte et al. (NeurIPS 2019) does.

**Evidence.** A design note, not a measured result. It holds the supervisor's nine example
traces with their charges, which the feature's live check reproduced through the real runtime,
and the two published sources behind the theory section.

**Files.**
- `README.md`: the note.

**Rerun.** The unit check of the on and off charges, from the repository root inside
`RM_RL_env`:

```bash
PYTHONPATH=app python -W ignore -m unittest tests.test_reward_layer
```

**Code.** Merge commits `ddb0c82` (`merge: recurrent soft penalty and the reasoning none
fallback`) and `0effa25` (`merge: recurrent soft rules wording`); `_rearm_violated` in
`app/src/compiler/reward_layer.py`; the design is the "Recurrent soft rules" section of
`docs/COMPILER_REWARD_DESIGN.md`.

### Clause semantics appendix (`clause-semantics/`), 2026-10-25

**What it shows.** What the hard, soft and recurrent-soft version of each of the eight IBM
templates (Existence, ExistenceTwo, Absence, RespondedExistence, Response, Precedence,
ChainResponse, NotCoExistence) means, shown as step-by-step traces with the state and reward at
every step. Each template has its meaning in plain words and in DoorKey, its LTLf formula, its
Reward Machines, and the traces that tell the versions apart. Each also has a "What it does not
mean" part: the readings a reader may expect, with the formula each would need, compiled through
the same path and walked next to the real template. The scope section states that the clause DFAs
are MONA's, unchanged, except the re-arm of a soft rule's broken-for-good state, and that the
compiler's hard passes then only redirect, unmark or prune the product from the DFA labels,
without changing any formula or break. A section on the end of the episode says how a machine with no
final state judges an episode the environment ends. It holds a paragraph ready to quote in the pipeline
section.

**Evidence.**
- 201 asserted counts (charges with the recurrent soft setting on and off, every episode
  total, and three cut-off totals for Response), all checked against the real machines; 0 differ.
  Every packet count held.
- Charges are counted from the reward layer's own product labels, and the rewards come from
  `RewardMachineRuntime` on the reloaded RM text, cross-checked against the layer's priced edge.
- The 58 trace tables in the README are pasted from `check/traces.txt`; the script fails if one
  differs. No number in the README was computed by hand.
- 47 graphs (SVG and RM text), one per distinct machine.

**Files.**
- `README.md`: the appendix; it opens on its own from disk.
- `check/clause_semantics.py`: compiles each template through the real path (nl2ltl formula,
  MONA, FL-AT, reward layer), walks the traces, asserts the counts and writes the files below.
- `check/traces.txt` and `check/traces.json`: all traces, formulas, DFAs and tables.
- `check/graphs/`: the 47 machines as SVG and RM text.

**Rerun** from the repository root, inside `RM_RL_env`:

```bash
PYTHONPATH=app python -W ignore docs/paper/clause-semantics/check/clause_semantics.py
```

It ends with `201 asserted counts checked, 0 differ` and
`OK: all assertions hold; wrote traces.txt and graphs/`. No LLM call.

**Code.** `build_reward_machine`, `_clause_labels` and `_rearm_violated` in
`app/src/compiler/reward_layer.py`; the design is in `docs/COMPILER_REWARD_DESIGN.md`. Branch
`docs/clause-semantics-appendix`, from `05f13d8`; committed as e0a054a.
The note on which soft rules recur is in [`recurrent-soft-rules/`](recurrent-soft-rules/README.md).

### Rule-only progress, simulated (`rule-only-progress/`), 2026-10-26

**What it shows.** Proposal P2 simulated before any code change. A task made only of rules has no
final state, so today its progress reward pays 0. P2 measures progress toward the states where no
rule clause is still waiting (each is kept or already broken): +0.1 per step closer, -0.1 per step
away, only when the task has no final state. The page shows all 16 machines (the eight IBM templates
alone, hard and soft), the Reward Machine today and with P2 for each changed one, and the traces
walked on both with their totals. The examples for rules that wait are events the environment
causes (a box falls, an alarm rings, the power goes out) and the agent only recovers: the trigger
costs 0.1 until the promise is kept, and when the agent controls the trigger the 0.1 comes back when
it keeps the promise, so the total is the same (apart from discounting). The note ends with what P2
leaves open and the end judgment that followed, in the user's framing: the machine "accepting" or
"rejecting" the "string of propositions" the environment generates. A machine with no final state
now lists its accepting states, two editable failed rewards (-1 hard, -0.5 soft) and the open promises
of every other state; when the environment ends an episode with a promise open, the step pays them. A
kept rule no longer pays the flat -0.5 of the time limit. The trainers keep their time-limit bootstrap
and receive the charge on top. The note also keeps one consequence we did not change: with two hard
promises open at the end the charge is -2, more than breaking a hard rule on the last step (-1).

**Evidence.**
- 20 compiled machines (the 16 plus four soft rows with the recurrent soft rules off): 9 change,
  among them 8 of the 16 (soft Existence and ExistenceTwo; RespondedExistence, Response and
  ChainResponse, hard and soft). The positive-cycle check is false on all 20, and every machine with
  a final state (hard Existence, hard ExistenceTwo) is unchanged.
- 35 traces walked on both machines, with every step's reward checked against the layer's priced
  edge. A kept rule totals 0 today and with P2; a promise left open at the end totals 0 today and
  -0.1 with P2; hard ChainResponse broken goes from -1 to -1.1; soft ChainResponse broken stays at
  -0.5; soft Existence done pays +0.1.
- Each renamed example matches the one it replaces: same rewards and state count on all 1,364
  input sequences up to 5 steps, today and with P2, for 9 pairs.
- The end judgment, played through the real `RewardMachineEnvironment` with the time limit after the
  last step (hard Response, box falls): a rule kept or never started totals 0 instead of -0.5; a box
  never put back totals -1.1 hard and -0.6 soft. With two hard promises open, idling on the last step
  totals -2.1 and breaking a hard rule totals -1.1.

**Files.**
- `index.html`: open it in a browser. A summary table, one card per changed machine with an "RM text"
  fold-out, trace tables, and "What P2 leaves open". `data.json`: the page's content.
- `README.md`: the note. `graphs/`: the 18 graphs as live HTML.
- `check/`: the script (`p2_sim.py`), the check on the real code (`real_code_check.py`), the end
  judgment check (`end_judgment_check.py`), the page builder (`build_page.py`) and the outputs
  (`results.json`, `rm-texts.txt`, `traces.txt`).

**Rerun** from the repository root, inside `RM_RL_env`. "Today" is the code of `e0a054a`, so the
simulation runs against a copy of it:

```bash
COPY=$(mktemp -d); git archive e0a054a app | tar -x -C "$COPY"
PYTHONPATH="$COPY/app" python -W ignore docs/paper/rule-only-progress/check/p2_sim.py
```

It prints one line per machine and the traces, and ends with `20 machines, 9 changed; positive-cycle
check false on every machine; every machine with a final unchanged; every renamed example matches the
one it replaces`. The real code is checked with
`PYTHONPATH=app python -W ignore docs/paper/rule-only-progress/check/real_code_check.py` (it leaves out
the end-judgment lines) and the end judgment with `end_judgment_check.py` in the same folder. No LLM
call.

**Code.** Implemented in `app/src/compiler/reward_layer.py` (`_progress` and `_price_edges`) on branch
`feat/rule-only-rewards`, base commit `e0a054a`; the progress change is commit `d4df200`, the cleanup
commit `633c3cd`. The real code compiles the 20 machines to exactly the P2 texts
(`check/real_code_check.py`). The simulation itself reproduces only on the code of `e0a054a`; the
entry's README says how to rerun it. The end judgment is a second step on the same branch, after
`a5ba449`: `EndJudgment` (`app/src/compiler/reward_machine.py`), the RM text parser and printer
(`app/src/compiler/rm_format.py`), `_end_judgment` (`app/src/compiler/reward_layer.py`), the charge in
`RewardMachineEnvironment.step` (`app/src/arm_fm/runtime.py`) and the success flag in
`RewardMachineObservation` (`app/src/arm_fm/environments.py`). Not committed when this entry was
written.
