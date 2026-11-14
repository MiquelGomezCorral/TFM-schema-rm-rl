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
`docs/decisions/arm-fm/catalogue-and-evidence.md`. Committed as `0ba206b`.

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
`RewardMachineObservation` (`app/src/arm_fm/environments.py`). The end judgment is commit `29cf79f` on
`feat/rule-only-rewards`.

### Rule-only rewards: a penalty the agent can earn back (`rule-only-rewards/`), 2026-11-11

**What it shows.** The result page of the rule-only rewards work, opened by the idea behind it. A rule
that waits for an event ("Whenever a window breaks, fix it") costs -0.1 on the step the event happens,
even when the agent did nothing; fixing it pays the +0.1 back, and an episode that ends with the
promise open is charged -1 (hard) or -0.5 (soft). Seen on the graph, the states with an open promise
are states to run away from, and the only free way out is doing what the rule asks. The rest of the
page is the result: progress toward the states with no open rule (Slice 1), the end judgment (Slice 2),
the seven final live tests, five examples and a generated bundle, and what was disclosed and left open.

**Evidence.** `check/window_check.py` measures the window task on the real code (totals 0 when fixed,
-1.1 hard and -0.6 soft when left open). The final live tests ran on `a56bbed`: L1.1 to L1.4 (20 machines
as simulated, 42/42 goal machines unchanged, no positive cycle in 71, 3/3 CLI runs), L2.1 (54/54 format
checks), L2.2 (24/24 runtime checks, the 15-case last-step table), L2.3 (generate, train, test on a
rerun after a critic reply that was not JSON; replay 33/33). No run measures learning.

**Files, rerun, code.** In `rule-only-rewards/README.md`: the page, 15 RM graphs, the reports in
`evidence/close/`, the window check and how to rerun it, and the commits
on `feat/rule-only-rewards`.

### ARM-FM rewards on undeclared transitions (`li2-undeclared-reward-rows/`), 2026-11-12

**What it shows.** ARM-FM writes the whole machine. On the two event-room cards, 3 of its 6 attempts
stopped at our parser: the reward section paid a self-loop the transition section never declared. The
authors' code accepts such a row and never pays it; we keep rejecting it and the error goes back to the
model as the next round (user decision, 2026-11-12). Two cards, one model pair: a data point, not a rate.

**Evidence.** The six recorded attempts of `cx-siren` and `cx-box`, with the parser or critic reply of
each, and a script that re-parses them.

**Files.** `README.md`, `check/parse_attempts.py`, `check/attempts/`.

**Rerun** (no LLM call): `PYTHONPATH=app python -W ignore docs/paper/li2-undeclared-reward-rows/check/parse_attempts.py`
prints `3 of 6 candidates stopped at the parser`.

**Code.** `_with_rewards` in `app/src/compiler/rm_format.py`, the retry loop in
`app/src/arm_fm/generation.py`; the rule is in `docs/decisions/arm-fm/rm-execution.md`.

### Event room (`s3-event-room/`), 2026-11-12

**What it shows.** `MiniGrid-ServiceRoom-v0`, a small room where events happen to the agent (a siren
rings, a box falls). Frame sheets and GIFs show the events, the answers to them, and that answering is
what earns the exit reward. A scripted policy reaches the exit with reward above 0 in 200 of 200 seeded
episodes over four setups; policies that ignore the events earn 0. It shows the room works, not that an
agent can learn it.

**Evidence.** 42 checks in `check/summary.json`, all pass; eight GIFs byte-identical to the rerun.

**Files.** `README.md`, `sheets/`, `gifs/`, `graphs/` (the two FARM machines), `check/summary.json`.

**Rerun** (no LLM call): `PYTHONPATH=app python -W ignore experiments/benchmark/scripts/check_service_room.py --out <output dir>`
ends with `all 42 checks passed`.

**Code.** `app/src/arm_fm/service_room.py`, merged as `09d7455` (`merge: tp-s3-event-room`).

### The task-card set (`s4-card-set/`), 2026-11-12

**What it shows.** 58 benchmark cards and 179 judged plan runs: every solving plan is judged a success
and every wrong plan breaks exactly the clauses it says. Response and Precedence are not
trace-equivalent: 156 of 340 short traces are judged differently, so a card's Response alternative is
not the same task as its Precedence pair. The cards are under revision (D10); the numbers describe the
set as of that morning.

**Evidence.** Three trace-bank logs and summaries in `results/`, and the Response against Precedence
check.

**Files.** `README.md`, `results/`, `check/response_vs_precedence.py`.

**Rerun** (no LLM call): `PYTHONPATH=app python -W ignore docs/paper/s4-card-set/check/response_vs_precedence.py`
prints `156 of 340 traces up to 4 steps are judged differently`.

**Code.** `app/src/benchmark/declare_judge.py`, the `trace-bank` command, merged as `47403ef`
(`merge: tp-s4-cards`).

### Cross-critic caution (`s6-cross-critic-caution/`), 2026-11-12

**What it shows.** FARM's critic rejected all three ARM-FM machines of the smoke, each time because the
clause list is empty (ARM-FM has no clauses) and asking to add clauses; the same happened in LI.2. The
FARM critic's verdict on an ARM-FM machine is therefore not a quality score, and the two cross-critic
directions are reported apart. Three cards, one model pair.

**Evidence.** The smoke evidence JSON with each verdict's full text and information note, the critic
outputs, and the three ARM-FM machines as graphs.

**Files.** `README.md`, `evidence/`, `graphs/`.

**Rerun.** The smoke needs the provider; the README lists the verdicts from the evidence file.

**Code.** The `cross-critic` command of `generate-suite`, merged as `ab1ecbc` (`merge: tp-s6-generation`).

### Generation cost per bundle (`s6-generation-cost/`), 2026-11-12

**What it shows.** On the same three cards and models, FARM took 5 to 7 model calls and 21 to 31 s per
bundle, ARM-FM 7 to 9 calls and 36 to 46 s (3-attempt limit of the smoke). A smoke measurement of the
cost, not of quality; the full suites allow up to 10 attempts, so costs will rise.

**Evidence.** The `generate-suite` output lines and the stamps in the smoke evidence JSON; the six
machines as graphs, each with its NL task and clause list.

**Files.** `README.md`, `evidence/`, `graphs/`.

**Rerun.** Needs the provider; the README lists the counts from the evidence file.

**Code.** `generate-suite` and its provenance stamps, merged as `ab1ecbc`.

### Reward parts against sequences (`s8-sequence-switch-table/`), 2026-11-12

**What it shows.** `ablate-rm` rebuilds a FARM bundle with one reward part off (progress, well,
soft break, soft pending, end judgment, recurrent soft penalty). On one DoorKey machine, six hand-written
label sequences show that each switch changes only its own part of the reward: the table lists the
per-step rewards of the full machine and of each ablated copy, with the seven machines as graphs. It
checks the switches; it does not train anything.

**Evidence.** The printed table and bundle check of the live run on the slice head `35b7944`, and the
recurrent-off log.

**Files.** `README.md`, `graphs/`, `evidence/`.

**Rerun.** `ablate-rm --bundle <FARM bundle> --off <switch> --output <dir>`; the source bundle is a
git-ignored output of the S8 run (see the README).

**Code.** `RewardSwitches` in `app/src/compiler/reward_layer.py`, `app/scripts/ablate_rm.py`; commits
`a690013`, `c7140e9`, `35b7944`.

### Judge columns of the suite table (`c2-f1-judge-columns/`), 2026-11-12

**What it shows.** Before the C2 fix, `aggregate-suite` read judge keys the writer never wrote, so all
four judge columns were empty. After it, two real judge files (a no-RM run, a FARM run) fill them with
the file's own numbers. Two runs: a check that the table reads the judge, not a result about the arms.

**Evidence.** The check's verdicts before (`"pass": false`) and after (`"pass": true`), the two judge
files, and the FARM machine as a graph.

**Files.** `README.md`, `evidence/`, `check/`, `graphs/`.

**Rerun.** `f1_aggregation.py before|after`, on the code before (`0f7e56b^`) and after (`0f7e56b`) the
fix; it needs the finished runs under `outputs/` (see the README).

**Code.** `judge_columns` in `app/scripts/aggregate_suite.py`, `judge_means` in `app/scripts/test_rl.py`;
commit `0f7e56b`, C2 final head `7ae1157`.

### A critic outage no longer multiplies generator requests (`critic-outage-retry/`), 2026-11-12

**What it shows.** Before the fix, a failed critic request (outage or unreadable output) restarted the
attempt and asked the generator again. In the FARM worst case, ten outages before every rejection, that
was 110 generator requests for 10 counted attempts, while ARM-FM got 10 in the same setting; the benchmark
promises the same limit to both arms. Now the failed request repeats on the same candidate (up to 11
requests) and the case takes 10 generator requests for 10 counted attempts. Scripted engines on a toy
task: a data point on the accounting, not a card result.

**Evidence.** 17 probe rows (11 FARM, 6 ARM-FM) on the tree before the fix (`fb36d17`) and on the freeze
(`a77709b`), reproduced for this entry.

**Files.** `README.md`, `check/f7_limits.py` and its two JSON outputs, `graphs/` (the probe machine).

**Rerun** (no LLM call): `f7_limits.py` on a copy of `fb36d17` and on the head; compare `proposal_requests`
of the row "10 critic outages, then one rejection": 110 before, 10 after.

**Code.** `retry_critic` and `CriticUnavailableError` in `app/src/engines/errors.py`; commit `9611837`,
merged as `7949c1d`.

### Step 1 has a previous valuation (`step1-previous-valuation/`), 2026-11-12

**What it shows.** A labeling rule that remembers the previous step raised `KeyError` at step 1, because
the previous valuation started empty. It now starts with every proposition false. Fresh-runtime runs of
each environment page's executable rows on seeds 1 to 50 crashed at step 1 on 50 of 50 layouts before
(48 of 50 where the scenario can drop the key) and run with 0 errors and 0 differences from the reference
labeler after, over 10,000-step random walks too.

**Evidence.** Per-page counts before and after (`check/pages-*.json`) and the replay of the two pilot
machines, which is unchanged (`check/pilot-replay-*.json`).

**Files.** `README.md`, `check/prev_false_pages.py`, `graphs/` (the two pilot machines).

**Rerun** (no LLM call): `prev_false_pages.py before <runtime copy of 6149c47>` and `after`.

**Code.** `RewardMachineRuntime.evaluate_labeling` in `app/src/arm_fm/runtime.py`; commit `1a25106`, merged
as `50a7a96`.

### A pre-seeded probe hides the step-1 crash (`preseeded-memory-probe/`), 2026-11-12

**What it shows.** The first check of the KeyCorridor documentation example for `key_found` handed the
function a previous valuation it wrote itself and passed on 50 of 50 layouts. Run through a fresh runtime,
the same unguarded expression raised `KeyError` at step 1 on 50 of 50 (0 steps checked); the guarded form,
or the runtime default of the step-1 entry, runs 2,113 steps with 0 errors and 0 differences. A check that
supplies the state the code is meant to create hides the bug about that state.

**Evidence.** Three runs of one expression on the solving plan of `cx-sequence`, seeds 1 to 50, on the
wave before the runtime change (`6149c47`) and on the freeze (`a77709b`); the reviewer's original logs.

**Files.** `README.md`, `check/cold_start_vs_preseeded.py` and its two JSON outputs, `evidence/`,
`graphs/` (the probe machine).

**Rerun** (no LLM call): the script on a copy of `6149c47` and on the head; `error_runs` of the fresh
unguarded row is 50 before and 0 after.

**Code.** `evaluate_labeling` in `app/src/arm_fm/runtime.py` and the `key_found` row of the KeyCorridor
`environment-code.md`; commits `28ae75e` and `1a25106`.

### Box chain: the solving plan now solves it (`box-chain-solver/`), 2026-11-12

**What it shows.** The event-room cards with a falling box ship a solving plan the benchmark trusts. An
independent sweep (12 cards x 50 seeds) found the plan missed the card's own rule in 74 of 600 runs, all on
the six ChainResponse cards, and a direct walk to the exit passed 8 cards. The scripted policy now waits
holding the box until every planned fall has fired, and the box cards ask for the box at the exit. The same
sweep gives 0 solve misses of 600 and 1 card still passed by a direct exit (`tpl-absence-3-nogoal`, which
forbids only the switch). The cards changed together with the solver, so the sweep cannot separate the two.

**Evidence.** Per-card counts before (`69b64db`) and after (`a77709b`), with the first misses by seed.

**Files.** `README.md`, `check/box_chain_sweep.py`, `check/compile_cards.py`, two JSON outputs, `graphs/`
(the `cx-box` and `tpl-chain-response-2-goal` machines).

**Rerun** (no LLM call): the sweep on a copy of `69b64db` and on the head; it ends with `total: 74 solve
misses over 600 runs on 12 cards` and `total: 0 ...`.

**Code.** `_fall_pending` in `app/src/arm_fm/service_room.py` and the `tpl-chain-response-*` cards; commit
`fb36d17`, merged as `6149c47`.

### `key_found` needs a clear view (`key-found-clear-view/`), 2026-11-12

**What it shows.** The reference labeler read `key_found` as "the key is inside the 7x7 box in front of the
agent", so a wall or closed door did not hide it: it was already true on step 1 in 9 of 50 KeyCorridor
layouts without the key in the agent's view. It now reads the agent's own view (`env.gen_obs()["image"]`),
which stops at walls and doors: 0 of 50, with the solving plan still succeeding on 50 of 50 and no matching
key held before `key_found`.

**Evidence.** Counts on each tree (`check/before-69b64db.json`, `check/after-a77709b.json`); the per-seed
list of the nine layouts is in the reviewer's run, not here.

**Files.** `README.md`, `check/key_view_check.py`, `check/compile_cards.py`, `graphs/` (the `cx-sequence`
machine).

**Rerun** (no LLM call): `key_view_check.py` on a copy of `69b64db` and on the head; `key_found_without_view`
is 9 before, 0 after.

**Code.** `key_seen` in `app/src/benchmark/reference_labels.py`; commit `fb36d17`, merged as `6149c47`.

### One counted attempt per candidate, the same in both arms (`attempt-counting/`), 2026-11-12

**What it shows.** The benchmark gives both arms 10 attempts, but FARM reran a failed attempt for free (110
generator requests for 10 counted attempts in the worst case) while ARM-FM counted outages and
authentication errors as used attempts, and FARM stamped 1 attempt when the provider never answered. Now
every candidate the generator returns uses one attempt; only a provider outage keeps the attempt number,
10 reruns at most, then ends as a provider error. Scripted engines on a toy task, so illustrative: no card
was run.

**Evidence.** 17 probe rows on the tree before (`69b64db`) and on the freeze (`a77709b`).

**Files.** `README.md`, `check/f7_limits.py` and its two JSON outputs, `graphs/`.

**Rerun** (no LLM call): `f7_limits.py` on a copy of `69b64db` and on the head; compare generator requests
and counted attempts row by row.

**Code.** `_Pipeline.generated` in `app/scripts/generate_rm.py`, `_Generation.generate_reward_machine` in
`app/src/arm_fm/generation.py`; commits `fb36d17` and `28ae75e`, merged as `6149c47`.

### What an independent card review found (`card-verdict-counterexamples/`), 2026-11-12

**What it shows.** A reviewer who had not seen earlier audits judged all 58 cards by building physical
counterexamples: 21 ok, 16 weak, 5 unclear, 8 wrong-expected, 8 broken. Eight broken cards are the six
ChainResponse cards (see the box-chain entry) and two counting cards whose "wrong" plan (pick the key up and
put it down) actually held it for two or more steps: 7 of 100 layouts satisfied the count before, 0 of 100
now. The eight Response cards still judge a state, not an event, so opening and closing a door fails the
card by design (the Response limitation, an open paper item).

**Evidence.** `evidence/verdicts.json` and `independence.json` (the reviewer's frozen verdicts and marker),
the counting check on both trees, and the counterexample cases on the freeze.

**Files.** `README.md`, `check/` (three scripts, three outputs), `evidence/`, `graphs/` (two card machines).

**Rerun** (no LLM call): `count_negatives.py` on a copy of `7ae1157` and on the head: `"false_negatives": 7`
then `0`.

**Code.** The counting cards in `experiments/benchmark/templates/tasks.json`; commit `fb36d17`, merged as
`6149c47`.

### Learner probe X1: PPO tuning (`x1-ppo-tune/`), 2026-11-12

**What it shows.** The pilot chose DQN (0.77 of evaluation points solved) over PPO (0.413), which never
solved UnlockPickup. Setting `s07` (learning rate 1e-3, 16 minibatches, 10 epochs, 16 environments, rollout
256) solves both pilot cards on 3 of 3 seeds, scores 0.711 on the same rule, and ran 2.2 times faster than
the pilot DQN at the same load (4.4 against 9.9 minutes). Nine of 18 settings solve UnlockPickup on both
seeds, so it is not a lucky value. On procedural layouts `s07` solves UnlockPickup on 2 of 3 seeds.

**Evidence.** Per-run tables for all 18 settings, the pilot's own evaluation files, the same-load speed
check and the layout reset check.

**Files.** `README.md`, `evidence/`, `check/` (summary script, reset check, suite files), `graphs/` (the two
pilot machines).

**Rerun.** Training only, 4 to 17 minutes a run, on branch `MiquelGomezCorral/tp-x1-ppo-tune`; the README
lists the commands.

**Code.** The tuning suites, commit `306d402` on that branch (not merged at the freeze).

### Learner probe X2: DQN on 8 environments and counterfactual experience (`x2-dqn-crm/`), 2026-11-12

**What it shows.** DQN on 8 training environments with half the gradient updates (`train_frequency: 8`)
solves 0.735 of evaluation points on the two pilot cards (pilot DQN 0.77) and ran 1.9 times faster than one
environment in a concurrent 100k-step check (1.85 times for the same update ratio over 500k). Counterfactual
experience (one extra transition per other machine state) hurt: 0.00 with 8 environments and 0.12 with one.
On procedural layouts the final evaluation spreads from 0.01 to 0.82 over three seeds. A seeding finding:
neighbouring run seeds share 28 of 32 layouts in the 8-environment code.

**Evidence.** Per-run tables, the saved output of three code checks (defaults identical, counterfactual adds
exactly 3 rows per step, equal update counts for 1 and 8 environments), the timing check and the reset check.

**Files.** `README.md`, `evidence/`, `check/` (check scripts, the code diff), `graphs/` (the two pilot
machines).

**Rerun.** Checks K1 to K3 need no training; the runs are training only, 7 to 33 minutes each, on branch
`MiquelGomezCorral/tp-x2-dqn-crm`.

**Code.** The learner change, commit `236dda1` on that branch (not merged at the freeze).

### Generation table, ARM-FM against FARM (`generation-table/`), 2026-11-14

**What it shows.** Per suite and arm, how often each generation step was accepted and what it cost,
for every suite (base, complex, templates, box-carry, forced-start, pilot). On the 124 main-suite
bundles FARM got its machine accepted 124 times in 1.23 tries on average (6.6 calls per bundle);
ARM-FM 121 times in 2.42 tries (8.5 calls). After repair 123 of 124 FARM and 124 of 124 ARM-FM
labelings pass the check. One model pair (`deepseek-v4.1-flash` writer, `glm-5.3-flash` critic), one
run per bundle: a count, not a rate.

**Evidence.** The output of the `generation-table` command, calls per bundle from the status files,
and the 150 cards behind it with NL task and expected LTLf. The caveats are in the entry: 3 FARM
bundles keep a labeling written before the RM-only rule, FARM `tpl-existence-2-nogoal` has an accepted
machine and no labeling, 27 FARM bundles were restored from logs, and the 18 ablation bundles are
derived, not generated.

**Files.** `README.md`, `generation-table.md` and `.json`, `calls-table.md`, `cards.md`,
`check/calls_table.py`, `check/cards_list.py`.

**Rerun** (no LLM call, from the main checkout that holds the bundles): the three commands in the
entry's README; the first is `generation-table --root experiments/benchmark --output <file>.json`.

**Code.** `app/scripts/generation_table.py` at `b332ecf` (`experiments/benchmark/REPRODUCE.md` 6.4).
