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
