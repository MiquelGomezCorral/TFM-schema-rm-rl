# Paper evidence

Results worth citing in the paper: pages with visual proof, the data behind them, and the
scripts that reproduce them. Each entry is one folder that opens on its own from disk, with a
note below.

## Objectives

The entries below serve two objectives of the paper (Miquel, 2026-11-22).

1. **Reward Machines without human intervention.** A user states a task in plain language and gets a well-shaped,
   ready-to-train Reward Machine, with no human repair and no technical knowledge of temporal logic or Reward
   Machines (knowing the task and the world is enough). The machines should be better than ARM-FM's.
   - Status after the final run: see "Wrong clauses at max" below. No machine, card, labeling or retry was edited by
     hand during generation. Of 266 FARM machines, 265 encode the task or a fair reading of it, and the one over-broad
     rule (`shop-boil~p2`) was held by the pipeline's own plan check. Two state descriptions name a goal their task
     lacks (text for the embeddings; the machines are right). Not yet without help: the pipeline's checks held 39
     right machines until a human ruled on two checks that are too strict.
2. **Getting the agent to learn the hardest machine.** A good Reward Machine alone may not be enough for the agent
   to learn a complex task; other techniques such as curriculum learning may be needed. KeyCorridorS6R3 already shows
   it: no method learned the Response goal card there (0 of 71 runs on that level), so the card moved to UnlockPickup
   (see "Response goal card on UnlockPickup" below). The plan for the shop's most
   complex machine: train one agent on each sub-task alone (the siren; serving clients; picking up fallen food; the
   boiling pot with food in hand), always with the same full machine and a world where only that sub-task happens;
   then a round where each episode picks one sub-task setup at random; then the full shop. Planned after the final
   run.

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

### Critic clues: what helps a small critic (`critic-clues/`), 2026-11-20

**What it shows.** The critic is a small model (`glm-5.3-flash`) that often accepts a wrong clause set.
Three exact clues computed by the compiler (each rule in plain words, "this hard rule is redundant",
"every way to finish includes ...") raise the share of labelled defects flagged on the critic's first
call from 30% to 56% (38 items: 28 wrong clause sets with 41 defects, 10 right ones). Through the full
loop (46 cards, generator `deepseek-v4.1-flash`) the runs that end with a right machine go from 77% to
85%, and from 64% to 72% on tasks with ordered steps. Right sets rejected by mistake: 2 of 10, against
8 of 60 before, so no gain there. Nine other clue ideas were noise and are listed with the reason.
The page shows two wrong sets with their task, LTLf, RM graph and the exact clue block.

**Evidence.** The critic-set runs of 18 variants, the pipeline loop records of v0 to v5, the two worked
examples with the prompt whole, the scorers and the code diff. Limit: the final reruns are one run per
item or card, so most per-case numbers are single runs. The report counts 2 false alarms in v5 of 13
where the scorer counts 3 (both numbers are on the page).

**Files.** `index.html` (open it from disk), `data.json`, `graphs/` (two machines as live HTML, SVG and
RM text), `check/` (`rescore.py`, `score.py`, `example_ltlf.py`), `evidence/`.

**Rerun** (no model call, from the repository root in `RM_RL_env`): `python check/rescore.py k0 v3f`
for the critic set; `D=docs/paper/critic-clues/evidence/loop; CC_ROOT=$PWD PYTHONPATH=app python
$D/tools/chain_score.py v0=$D/v0/today v3f=$D/v3f/today` for the pipeline. The prototype scripts that
called the models are not kept: the merged code (`app/src/compiler/critic_clues.py`) does what they did.

**Code.** `app/src/compiler/critic_clues.py` and the prompt changes (`evidence/final.diff`), branch
`MiquelGomezCorral/tp-critic-clues` on base `45c6747`; commit `3fb0ce0`, merged as `114e5b3`.

**Later fix (same day).** The "redundant" clue depended on clause order. For "Go to the goal. If you
reach the goal, you must also have picked up the key", with `Existence(at_goal)`, `Existence(has_key)`
and `RespondedExistence(at_goal, has_key)` all hard, each of the last two implies the other; in the
order goal, key, rule the old search named the stated "if" rule, which the critic must keep, so it had
no clue to drop the extra `Existence`. The search now tries the `Existence` and `ExistenceTwo` clauses
first. Commit `600d6a0`, merged as `6606ab7`. Evidence: the clue block before and after, 6 of 6 live
`glm-5.3-flash` critic runs (3 at `none`, 3 at `high`) that ask to remove `Existence(has_key)`, and the
review's brute-force checker on main `6606ab7`: 0 mismatches (496 random sets right, 104 skipped; 129
multi-group sets right, 21 skipped). Files: `evidence/clues-fix/`, `check/clue_order.py`. Rerun (no model
call): `PYTHONPATH=app python -W ignore docs/paper/critic-clues/check/clue_order.py` prints the clue block
of both orders. The checker and the live-run tool are review prototypes and stay in the plan folder.

### Generator prompt loop: the chain form for ordered tasks (`generator-prompt-loop/`), 2026-11-20

**What it shows.** For "use the key to open the door, then reach the goal" the generator model
(`deepseek-v4.1-flash`) used to write one "must happen" rule per step plus the order rules (form A).
The intended answer is one "must happen" rule for the last step plus one order rule per pair (form B,
the chain form). Version by version (v0 to v11, 2,430 runs), the prompts raised the ordered runs that
write the chain form from 52% to 81% and cut form A from 40% to 8%. Wrong machines over all runs: 14%
(18 of 126) to 12% (31 of 252); no earlier case got worse. The later pay fix makes both forms pay the
same (1, 1, +11, 13 in all, one identical machine), and the pay-order sweep passes 141 of 167 card
answers (87 of 168 before) and 91 of 108 stored sets (73 before). The page shows the doorkey task with
its LTLf and the old form A, old form B and current machine as live RM graphs.

**Evidence.** One slim record per version (final clause set and counts), the original scorer, the case
list, the hand judgments, the prompts before and after, the loop's notes, the pay-order verdicts per
answer before and after. Limits: the 90% chain target was not reached under the version limit (v7: 75%)
and the model drifts between hours (v7 scored 75.0% and 70.2% an hour later), so single moves under
about 10 points are noise. Two of the 108 stored sets are newly flagged by "started must pay more than
not started", a known false alarm of that check.

**Files.** `index.html`, `data.json`, `graphs/` (three machines), `check/` (`rescore.py`, `chain_score.py`,
`cases.py`, `judgments.json`, `sweep.py`, `sweep_summary.py`, `doorkey_forms.py`), `evidence/` (runs, cards,
prompts, `final.diff`, `rounds.md`, `status.md`, `pay-order-sweep.*`, `doorkey-pay.txt`). The 170 MB of full
traces are not copied, and the scripts that called the models are not kept.

**Rerun** (no model call, from the repository root in `RM_RL_env`): `CC_ROOT=$PWD PYTHONPATH=app python
docs/paper/generator-prompt-loop/check/rescore.py v0=v0 v7=v7 v11=v11 --first=6 --no-soft --base=v0`;
the sweep and the doorkey price are in the page's last section.

**Code.** Prompt commit `6b28dd0` on `MiquelGomezCorral/tp-chain-prompt`, in main as merge `45c6747`;
pay fix `0ed7052`, in main as merge `229d176`.

### Zombie garden: why PPO guards only the top lane (`zombie-garden-warm-start/`), 2026-11-20

**What it shows.** On the zombie garden card (`lanes-rules`: never let a zombie through the top lane;
try not to let zombies through the other lanes or trample plants) PPO ends up guarding only the top
lane under every plain setting tried (10 lines, 3 seeds each, RM -18.8 to -26 against -12.9 for a
scripted top-and-middle policy). The noise check explains part of it: with 10% random actions the
three-lane policy loses to top-only (-31.5 against -23.7). A warm start from a behaviour clone of a
hand-written guard policy (a hack, labelled so on the page) keeps the middle lane and reaches -10.7,
and still tramples 0.34 to 0.64 plants a game (bar 0.2). The page shows the task, the LTLf, the live
RM graph and the tables. A later section reruns the best warm-start arm (hack) and a plain control, 3
seeds each, on main `9bd6aeb` (gate passed first): the warm start keeps the top lane, halves side
breaches (17.15 to 9.85) and doubles kills, but tramples 0.50 plants a game against 0.14 for the plain
run, so it still fails the plants bar; the plain run never finds the side-lane policy. The numbers equal
the loop's.

**Evidence.** The judge output of every round, the noise check output (reruns identically), the loop's
report and rounds, the settings of each key line, the code diff of `ppo_reward_scale`, and for the rerun
on main its judge output (`rerun-main-judge.out`), gate result (`rerun-main-gate.json`) and diff
(`rerun-main-ppo_reward_scale.diff`). One sentence of
the loop's report (top-only best at PPO's noise) is stricter than its own table, which has the
top-and-middle policy ahead to 20% noise; the page follows the table.

**Files.** `index.html`, `data.json`, `graphs/lanes-rules.*`, `check/` (`noise_check.py`, `policies.py`,
`lanes_ltlf.py`), `evidence/`. The clone weights (8 MB each) are not copied; the training scripts need
the PPO trainer and were not rerun, and the clone, critic-check and replay scripts (they read run folders
that are not copied) are not kept.

**Rerun** (no model call, no training, about 12 s, from the repository root in `RM_RL_env`):
`PYTHONPATH=app:docs/paper/zombie-garden-warm-start/check python -W ignore
docs/paper/zombie-garden-warm-start/check/noise_check.py --procs 8`; the output matches
`evidence/noise_check.out`.

**Code.** `ppo_reward_scale` (two lines in `app/src/arm_fm/ppo.py` and `app/src/config/config.py`),
uncommitted in worktree `tp-lanes-tune` (branch `MiquelGomezCorral/tp-lanes-tune`, base `0389b0b`);
`evidence/ppo_reward_scale.diff`. commit: pending, not merged.

### Reward scale tries (`reward-scale-tries/`), 2026-11-20

**What it shows.** A list of every reward size or scale we changed to make a machine learn, with the
task and a one-line result each: the x10 whole-unit pay (shop step 2 learns at x10 on 3 of 3 seeds,
serves 0 at x1), the soft break size 5, 2.5 and 1 with a flat or a ceiling hard break on the zombie
garden, five shop arms at x10, `ppo_reward_scale` 0.1 and 0.01, and the value clip finding.

**Evidence.** `evidence/` holds copies of the working notes each bullet cites. A list only: no page,
no rerun.

**Files.** `README.md`, `evidence/`.

**Code.** `deff802` (whole-unit pay, in main); the soft size and ceiling default is in
`app/src/config/config.py` (`soft_break_cost`, `hard_ceiling`); `ppo_reward_scale` as above.

### Response goal card on UnlockPickup: 9 of 9 learned (`response-card-unlockpickup/`), 2026-11-20

**What it shows.** The Response goal card (`tpl-response-1-goal`) moved from KeyCorridorS6R3, where no
method solved it (the card's old machine trained 0 of 3; 0 of 71 runs on that level learned), to
UnlockPickup, the learnable level with the same key, door and box chain. Its expected answer and its two
accepted answers each trained on 3 seeds (one-hot state, PPO s07, 1.5M steps, procedural layouts):
9 of 9 learned, judged success 1.00 on 100 greedy episodes each, 221k to 324k steps to 0.9 eval success.
The page shows, per machine, the NL task, the LTLf clauses and the live RM graph with its RM text, the
per-seed table, and the earlier ARM-FM (3 of 3) and FARM (1 of 3) numbers on this level, labelled as
different machines and the old pay.

**Evidence.** `evidence/judge.out` (the chain-regression judge: 9 runs, scripted idle and solving-plan
baselines, the launch gate), the three machines, and the card as on main. The earlier numbers come from
the move report's run folders and are not copied.

**Files.** `index.html` (built from `data.json`), `graphs/` (each machine as live HTML, SVG and RM text),
`evidence/`.

**Rerun.** The judge needs the nine run folders of the `tp-response-card` worktree, which are not copied:
`PYTHONPATH=app python outputs/chain-reg/chain_judge.py --queue outputs/chain-reg/queue.json --episodes 100
--out outputs/chain-reg/judge.out`, from that worktree in `RM_RL_env`. The graphs:
`PYTHONPATH=app python app/main.py render-rm --rm-file <machine>.reward_machine.txt --svg-dir <out>.svg --html`.

**Code.** Card move `0e821b8` (branch `MiquelGomezCorral/tp-response-card`), merged into main as
`54f2c71`.

### Model comparison: who makes the wrong reward machines (`model-comparison/`), 2026-11-20

**What it shows.** Five generator and critic pairs on the 46 task cards (A deepseek-v4.1-flash + glm-5.3-flash, the
production pair; B Haiku + luna; C Haiku + glm; D deepseek + luna; E luna + Haiku), then the thinking level of the
production pair and two fixes. At reasoning `none`, A has 42 of 46 right, and its 3 wrong machines (W5a, U5, S2) are
deepseek first proposals that glm accepted on call 1; a fourth (O7) was accepted with redundant clauses. At `medium`
for both models, with the critic wording fix and the G12 card fix, 46 of 46 are right (calls per run 2.35 against
2.39; median run 6 s against 39 s). On the 38-item critic set glm catches 14 of 28 wrong sets on call 1 at `none`
and 22 of 28 at `medium`; luna catches 27 and Haiku 28. The critic wording fix removes luna's G12 loop (7.33 rounds
and 20 of 22 false alarms per run to 1 round and 0 of 2). A DFA equality proof closes a G12 card gap: old G12 runs
scored right go from 2 of 9 to 6 of 9. New at `medium`: 10 of 66 first proposals are too short (0 of 46 at
`none`), all rejected by glm. The page shows W5a, U5, S2, O7 and G12 with their task, LTLf and live RM graph at
`none` and at `medium`, with an "RM text" fold-out.

**Evidence.** The two loop reports, one summary JSON per run for every table row, the critic-set records of all
critics, the 38 critic items, the G12 equality proof output, the card for the S cases. Limits: one run per case in
most rows; the 46/46 run changes thinking, critic wording and card together (the earlier `medium` run, m1, came
before the wording: 19 of 20 on the hard and random cases); the `none` rerun with the new wording was not run
(budget); the CLI models think hard while the app default is `none`, so arms compare model plus thinking. The
call logs (55 MB: seconds per call, tokens) are not copied, so those columns are read from the reports; the 172
critic-set records had their `first_prompt` field removed.

**Files.** `index.html` (built from `data.json`; open it from disk), `graphs/` (the 9 machines drawn as live
HTML, SVG and RM text), `check/` (`arm_stats.py`, `critic_stats.py`, `loopcrit.py`, `chain_score.py`, `cases.py`,
`judgments.json`, `equiv.py`, `machines.py`), `evidence/` (1.8 MB). The run tools (`run_arms.sh`,
`run_critic_set.sh`, the CLI adapter scripts) call models and stay in the plan folder.

**Rerun** (no model call, from the repository root in `RM_RL_env`; the page's last section lists every command):
`CC_ROOT=$PWD PYTHONPATH=app python docs/paper/model-comparison/check/arm_stats.py A=<evidence>/model-compare/runs/r1/A
B4=<evidence>/llm-loop/runs/b4/A` for the arm table, `python docs/paper/model-comparison/check/critic_stats.py
"glm none=...,..." --kinds` for the critic set, `PYTHONPATH=app python docs/paper/model-comparison/check/equiv.py
'<set 1>' '<set 2>'` for the G12 proof. The graphs: `render-rm --rm-file graphs/<name>.rm --svg-dir <out>.svg --html`.

**Code.** Critic wording `d5ec36e`, G12 card `e56fcff`, CLI adapter `9f12d3a`, merged into main as `57f6a1a`; the
critic clues the critic set rests on: `3fb0ce0`, merged as `114e5b3`.

**Loop 2 (later the same day).** Two sections before the open points. The stated-order audit: an order the task
states is now required even when the level forces it; 8 of 11 cards with optional orders lost them and 16 accepted
answers that drop a stated order were removed from the repository cards, 10 more from the loop's own cards (rescore: `none` 42 to 40 of 46, B4 stays 46). With two critic prompt
lines and the relabelled critic set (30 wrong, 8 right), glm at `medium` catches 28 of 30 on call 1, against 24 of 30
for the earlier `medium` run. The thinking sweep, `low` to `max` on the 46 cards: 46 of 46 right at every level,
first proposals right 37, 38, 37 and 30, short first proposals 7, 8, 8 and 14, median wall 27 to 166 s, 2 timeouts at
`max`, the critic catching every wrong first proposal; recommendation `high` if the default moves. The sweep ran
before the shape fix of `hidden-output-schema/`, and the page marks it. Evidence: `evidence/llm-loop2/` (3.2 MB: the
audited cards, the card and prompt diffs, the relabelled items, the rescore, one summary and one slim call log per
run, prompts and schema dropped) and `evidence/llm-loop2-report.md`. The repository's cards changed afterwards, so
`evidence/cards/` keeps the cards of this entry and `check/cases.py` reads `CARD_DIR` (default: those);
`check/level_stats.py` is new and `check/chain_score.py` now takes its optional orders from every hard `Precedence`
of the card. Rerun: the commands in the page's last section. Code: loop 2 ran in worktree `tp-llm-loop2`; its prompt
changes reached main as `42003cf` (merged as `56a482a`), and the card review made stated orders required on main in
`ab27c07` (merged as `b3ba9ef`).

### Hidden output schema: why thinking cut the generator's answers short (`hidden-output-schema/`), 2026-11-20

**What it shows.** The generator (`deepseek-v4.1-flash`, through OpenCode) must answer in a JSON shape it is
never shown: the app sends it only as `response_format: json_schema`, which OpenCode enforces while decoding
but never puts in the model's context. With thinking on, the model plans under field names it guessed, and
when the decoder forces the real ones the answer often stops after the first clause. Short first proposals
on the 46 cards: 0 at `none`, 7, 8, 8 and 14 from `low` to `max` (36 of 37 are one clause). One prompt
sentence that names the shape fixes it. Replays of the same logged requests: 3 of 4 short before, 0 of 5
after. At scale: at `max` short 14 to 0 and first proposals right 12 to 26 of 26, total wall 4,470 to
2,460 s; at `high` short 8 to 0 and first right 37 to 46 of 46. Side gain: a formula in the free-text
`normalized_clause` field went from 242 of 481 final clauses to 0 of 223. The page quotes the reasoning
and shows one case (W3a) with its task, LTLf and RM before and after.

**Evidence.** The diagnosis, finding and at-scale reports; the 15 raw replay responses with their
reasoning; one summary and one slim call log per run for loop 2 and the three shape rounds; the W5a
replays. Open cost: W5a (`cx-goal-many-rules`) at `max` ended with no machine, six non-streamed calls in
a row at the SDK's 600 s timeout. Cause: OpenCode never returns a non-streamed reply after about 300 s
(1,334 logged calls: longest 298.8 s, none between 300 and 600 s); W5a at `max` reasons 12 to 36 K tokens
at 69 to 125 tokens per second, and streamed the same request came back 6 of 6 times in 154 to 520 s. The
streaming fix is merged (see `opencode-streaming/`). Limits: one run per case and level.

**Files.** `index.html` (built from `data.json`; open it from disk), `graphs/` (the two W3a machines as
live HTML, SVG and RM text), `check/` (`level_stats.py`, `arm_stats.py`, `cases.py`, `chain_score.py`,
`loopcrit.py`, `judgments.json`, copied from `model-comparison/check/`; `replays.py`, `formula_text.py`,
`w5a_speed.py`, `sample.py`), `evidence/` (5.7 MB with the page: reports, `probes/`, `scans/`, `runs/`,
`w5a-timeout/`, `cards/` and `cards-before-audit/`, `creator-prompt-vs-main.diff`). Full call logs with
prompts and the tools that call the models stay in the plan folder.

**Rerun** (no model call, from the repository root in `RM_RL_env`): the page's last section lists every
command; the first is `env CC_ROOT=$PWD PYTHONPATH=app:docs/paper/hidden-output-schema/check python -W
ignore docs/paper/hidden-output-schema/check/level_stats.py low=<runs>/loop2-low/A ...`, and
`PYTHONPATH=app python -W ignore docs/paper/hidden-output-schema/check/sample.py` rebuilds the sample.

**Code.** The sentence in `app/src/prompts/compiler-rm/reward-ltlf-creator.system.md:82-87`, commit
`42003cf`, merged as `56a482a`. The streaming fix: commit `c5219a2`, merged as `f2c3a49` (`opencode-streaming/`).

### Benchmark coverage: which rule shapes the final run really tests (`benchmark-coverage/`), 2026-11-20

**What it shows.** The 8 Declare templates, hard or soft, with or without a goal, make 32 cells. A cell is
tested well when a trained card on a level that forces the choice judges that rule. Two card reviews read
every card against that bar, before and after the card fixes: 15 of 32 cells tested well before, 18
after (both RespondedExistence hard cells). Left: 8 soft-goal cells the result test never judges (a soft
rule beside a goal passes on the goal alone), 2 gaps (hard Precedence and NotCoExistence without a goal),
3 weak cells (the level forces the rule or the count comes free) and 1 Absence cell counted once per
episode. The page has the matrix, the verdict counts, the gaps in plain words, and the 10 card groups,
each with 2 or 3 sample cards (task, clauses, LTLf, live RM graph and RM text). The rule-only cards an
idle agent passes (17 cards with hard rules and no goal) are scored on reading only and never trained,
since a run would show nothing an idle agent does not already get; two of them have forced-start
copies, and one of those copies (`tpl-response-1-nogoal-forced`) trains.

**Evidence.** The baseline review (111 cards, 660 plan traces, 165 answers swept; verdicts: OK 46, OK
generation only 14, pay-order flag only 18, soft rule not judged 10, card issue 23) and the delta review,
both reviewers' text returns; the two group files; the card-fix report of round 1 and the round-2 diff;
the delta review's trace-bank and sweep outputs; the cards of main `6606ab7`. Limits: the baseline's own
counts (15 + 8 + 4 + 2) leave 3 cells unnamed, and read with the delta review's labels its table gives 16;
`tpl-existence-two-5-nogoal` came after the count; the delta review's finding 1 (two base cards score the
goal alone as right) is still open on main.

**Files.** `index.html` (built from `data.json`; open it from disk), `graphs/` (24 sample machines as live
HTML, SVG and RM text; `shop-boil`, 65 states and 10,662 transitions, is too large to draw), `check/card_machines.py`,
`evidence/` (`card-review-report.md`, `delta-review.md`, `groups.json`, `groups-v2.json`,
`card-fix-report.json`, `card-fix-round2.out`, `delta-checks/`, `cards/`). The review sweep scripts and
their 20 MB of traces stay in the plan folder.

**Rerun** (no model call, from the repository root in `RM_RL_env`):
`PYTHONPATH=app python -W ignore docs/paper/benchmark-coverage/check/card_machines.py` prints each sample's
task, clauses, LTLf and machine size and writes `graphs/<card>.rm`; `render-rm --rm-file graphs/<card>.rm
--svg-dir graphs/<card>.svg --html` draws each.

**Code.** The cards in `experiments/benchmark/<suite>/tasks.json`; the card fixes are commit `ab27c07`, merged
as `b3ba9ef`. Scoring in `app/src/benchmark/rm_facts.py`, the test bars in `app/scripts/test_rl.py`.

### KeyCorridor room size: the labeling now reads the room (`keycorridor-room-size/`), 2026-11-20

**What it shows.** The KeyCorridor facts page and the reference labeler assumed 6x6 rooms. On the 4x4 rooms of
`MiniGrid-KeyCorridorS4R3-v0`, the old generated labelings set `target_room_entered` outside the room before the
door opened in 155 of 300 random episodes and crashed in 144. After the fix, 0 differ on S4R3, S5R3 and S6R3.
Pipeline side, not model side. With the fixed labeling (1.5M steps, judged on 100 episodes, learned = at least
0.8), FARM learns cx-sequence in 3 of 3 seeds (0.91, 0.81, 0.87) and base-key-corridor in 2 of 3 (0.85, 0.82,
0.00); no-RM learns 0 of 3 on both. The base-key-corridor machine adds Precedence(key_found, has_matching_key):
the user ruled on 2026-11-20 that "find and acquire the key" states that order, so it counts. Since commit
`f29c47a` (merge `97baab7`, entry `stated-order-rule/`) the card accepts it and the S4R3 bundle scores `also_ok`.
The page shows the old and new labeling line and both machines with task, LTLf, live RM graph and RM text.

**Evidence.** The labeling checks before and after (old bundles on S4R3, new bundles on three sizes, the paraphrase
bundles, the fixed reference labeler) and the two bundle gates; the judge tables, queues and run log; per seed of
the 12 runs `judge.json`, `summary.json`, `eval.csv`, `config.yaml`, `test.json` and `judge.log` (no weights, no
traces); the 12 run configs; the two S4R3 card copies. Limits: three seeds per arm, one level.

**Files.** `index.html` (built from `data.json`; open it from disk), `graphs/` (the two S4R3 machines as live HTML,
SVG and RM text, copied from the bundles on main `78c666c`), `check/` (`probe_run.py`, `probe_judge.py`),
`evidence/` (`checks/`, `judge/`, `runs/`, `configs/`, `cards/`). The labeling check itself is tracked at
`experiments/benchmark/envs/minigrid-key-corridor/check/room_size_check.py`.

**Rerun** (from the repository root in `RM_RL_env`): `PYTHONPATH=app python
experiments/benchmark/envs/minigrid-key-corridor/check/room_size_check.py
experiments/benchmark/complex/bundles/farm/cx-sequence --sizes 4 5 6` (no model call, about 2.5 min per bundle).
The page's last section has the before row, the graphs and the training queue (about 30 min per seed).

**Code.** Commit `673566d`, merged as `d2d9249`: `app/src/benchmark/reference_labels.py` and the facts pages
`experiments/benchmark/envs/minigrid-key-corridor/environment.md` and `environment-code.md` read the room size;
`run-suite` refuses a bundle made for another level. The old S6R3 bundles are archived under
`experiments/benchmark/{complex,base}/kc-page-s6r3/farm/`.

### OpenCode streaming: long answers now arrive (`opencode-streaming/`), 2026-11-20

**What it shows.** OpenCode never returned a non-streamed reply that took longer than about 300 s. At reasoning
`max` the generator (`deepseek-v4.1-flash`) reasons 12 to 36 K tokens on W5a (`cx-goal-many-rules`), so each call
waited the SDK's 600 s and failed: five timeouts in a row and no machine. Every OpenCode completion is now streamed,
with a 120 s limit on the silence between two chunks, and joined into the reply callers already expect. After the
fix, W5a at `max` gave an accepted, right machine in 5 of 5 runs (the same machine text each time), the longest
generator call took 384 s, and none of 59 runs (13 at `max`, 46 at `high`) had a timeout. At `high` it changes
little: 44 of 46 right before, 43 of 46 after, and the three wrong are model mistakes the critic missed. Pipeline
side, not model side: the W5a machine is the chain-regression bundle `many-rules-reworded`, judged success 1.0 in 3
of 3 seeds. This is the streaming fix the hidden-output-schema entry above lists as pending. The page shows W5a's
task, LTLf, live RM graph and RM text.

**Evidence.** One run record per run (status, clauses, machine, wall time) and a slim call log per run (timing,
tokens, errors; prompts and schema dropped) for four rounds: before and after, at `max` (27 and 13 runs) and at
`high` (46 and 46); the W5a run logs; `round-table.out`. Limits: one run per case and level except W5a at `max`;
the after round at `max` covers 9 of the 27 cases; wrong counts are scored against the cards on main `78c666c`,
which changed after the before round. The failed W5a run logs five timed-out calls; the hidden-output-schema entry
counts six.

**Files.** `index.html` (built from `data.json`; open it from disk), `graphs/` (W5a's machine as live HTML, SVG and
RM text), `tools/` (`round_table.py` with its scorer `arm_stats.py`, `chain_score.py`, `cases.py`, `loopcrit.py`,
and `slim_calls.py`), `evidence/` (`before-max/`, `after-max/`, `before-high/`, `after-high/`,
`round-table.out`, and `cards/`, the local cards the scorer reads). Full call logs with prompts stay in the plan
folder.

**Rerun** (no model call, in `RM_RL_env`): `env -C docs/paper/opencode-streaming/tools CC_ROOT=$PWD
PYTHONPATH=$PWD/app python -W ignore round_table.py before-max=../evidence/before-max ...`; the page's last section
has the full command and the graph.

**Code.** Commit `c5219a2`, merged as `f2c3a49`: `OpenCodeEngine._stream_completion` and `_joined_completion` in
`app/src/engines/provider_engines.py`, `httpx2==2.12.0` in `requirements.txt`, tests in `tests/test_engines.py`
and `tests/test_pipeline_orchestration.py`.

### Soft-break quality: how often the agent breaks a preference (`soft-break-quality/`), 2026-11-20

**What it shows.** The user's question: "it solves the task, but how well? Is it really following the human
preferences?" Pass or fail stays goal plus hard rules. The judge used to count a broken soft rule once per episode,
however often it broke. It now also counts each separate break (a new one starts at the first later step whose
labels change) and the share of episodes with one. Recomputed from saved test traces, without retraining: on
cx-goal-one-rule, ARM-FM breaks "try not to drop the key" about 221 times per episode where the old count said
0.79, while FARM and no-RM break it 0 times; every arm is judged 0 there, so 0 breaks is not care by itself. 26 of
27 FARM experiments on the two BlockedUnlockPickup cards show 0 breaks (the other, the ablation without the
soft-break charge, 0.97). On the zombie garden (lanes-rules) the new count puts warm-started runs at 10.25 and
plain PPO at 16.66, which the old count ranked the other way (1.36 and 1.14). On the forcing suite FARM shows
1.05 against 10.58 for no-RM, but FARM breaks the hard rule in every episode and ends near step 80; that bundle
predates `deff802`, carries the old end charge, and is generated again at the freeze. The page also says what one
break means for each template and shows six machines with task, LTLf, live RM graph and RM text.

**Evidence.** `soft-quality.jsonl`, one row per experiment for 59 experiments (card, task, worktree, arm, episodes,
judged success, stored and recomputed counts): the recomputed old count matches the stored one in all 59. The
ARM-FM key-drop series of one seed; two live re-judge tables (`aggregate-suite` with the new code on finished seed-1
runs, no training) with their suite files. Limits: the live tables are one seed; the agent traces the recompute
reads stay in the worktrees (about 100 files per seed).

**Files.** `index.html` (built from `data.json`; open it from disk), `graphs/` (six machines as live HTML, SVG and
RM text; two copied from git-ignored worktree folders), `check/` (`recompute_soft.py`, `label_runs.py`,
`judge_diff.py`), `evidence/` (`soft-quality.jsonl`, `arm-fm-key-lost.out`, `live/results-ta1/`,
`live/results-forcing/`, `ta1-cx-goal-one-rule.yaml`, `forcing-lanes-rules.yaml`).

**Rerun** (no model call, no training, from the repository root in `RM_RL_env`): `PYTHONPATH=app python
docs/paper/soft-break-quality/check/recompute_soft.py OUT.jsonl <worktrees folder>` rebuilds the table from the
runs' `agent-traces/`; the page's last section has the key-drop series, the judge diff and the graphs.

**Code.** Commit `865b623`, merged as `78c666c`: `_break_count` and the `soft_break_count` and `any_soft_break`
fields in `app/src/benchmark/declare_judge.py`, their means in `app/scripts/test_rl.py`, the two table columns in
`app/scripts/aggregate_suite.py`, tests in `tests/test_declare_judge.py`. Record:
`docs/decisions/benchmark/thesis-benchmark.md`, entry of 2026-11-20.

**Update 2026-11-21: the judge counts what the machine charges.** The user chose to count every broken step, as the
machine charges, instead of merging back-to-back breaks into one. The new count equals the machine's soft-break
charges on every trace: 300 random traces per template against a one-clause soft machine (MONA, today's reward
layer), where the count above disagreed on 150 Absence, 24 Precedence, 18 ChainResponse and 42 NotCoExistence traces;
the other four templates never charge (`check/judge_vs_machine.py`, output `check/judge_vs_machine.out`). Recounted
from the same traces (`evidence/soft-quality-every-step.jsonl`, 63 rows: the 59 above plus 4 one-seed live re-judge
runs), the share of episodes with a break is unchanged in every row and the counts grow by up to 10%: warm-started
lanes-rules 10.35 and plain PPO 17.29 (were 10.25 and 16.66), ARM-FM's key drops on cx-goal-one-rule stay 221.26. The
ranking holds. The page and its two live tables still show the earlier count. Rerun:
`env -C <repo> PYTHONPATH=app python docs/paper/soft-break-quality/check/judge_vs_machine.py 300 7`, and
`recompute_soft.py` as above. Code: the `tp-judge-graphs` commit (`_break_count` in
`app/src/benchmark/declare_judge.py`).

### Pay order: "started" now means closer to the goal (`pay-order-started/`), 2026-11-20

**What it shows.** Before training, `check-pay-order` checks that a machine pays finished > started > not
started > soft break > hard break. It called every middle state started, so a state that only remembers a ringing
siren, and owes more than the start, paid 0 like doing nothing, and the check flagged 41 correct clause sets. A state now
counts as started only when it owes fewer propositions to a final state than the start does (the shortest path
that avoids rejecting states). Chain sweep: 106 of 130 card answers and 91 of 108 stored sets passed before, all
after. Card sweep: 106 to 130 of 130. Promise sweep: 125 of 130 both times. No other verdict changed. The real
flags stay: the fear-ceiling door edge, the lanes soft-break stream (one hard break costs -1, a stream of soft
breaks -47.5) and 5 soft cards with the promise cost on. Pipeline side, not model side. The page shows the owed
count per state of four machines (door before box, never both, cx-siren, key-door-box chain), each with task,
LTLf, live RM graph and RM text; three of the tasks are illustrative wording and say so.

**Evidence.** The three sweeps before and after (238, 130 and 130 rows; the chain and card sweeps as slim copies
without per-step traces); the owed counts of the four examples; the check run on the bundles behind the two kept
flags. Limits: the card sweep's trace bank is not copied, and the chain sweep reads the stored bundles from the
main checkout.

**Files.** `index.html` (built from `data.json`; open it from disk), `graphs/` (four machines as live HTML, SVG and
RM text), `check/` (`chain_sweep.py`, `card_sweep.py`, `promise_sweep.py`, `compare.py`, `owed_examples.py`,
`slim_sweep.py`), `evidence/` (`before/`, `after/`, `owed-examples.out`, `kept-flags.out`).

**Rerun** (no model call, from the repository root in `RM_RL_env`): `PYTHONPATH=app python -W ignore
docs/paper/pay-order-started/check/owed_examples.py` prints the examples and writes `graphs/*.rm`; `compare.py
BEFORE.jsonl AFTER.jsonl` lists every change; the page's last section has the three sweeps and the one-bundle
check (`check-pay-order --step-limit 300`).

**Code.** Commit `865b623`, merged as `78c666c`: `_owed` and the started test in `app/src/arm_fm/pay_order.py`,
`fewest_true` in `app/src/compiler/reward_machine.py`. Records: `docs/decisions/arm-fm/rm-execution.md` and
`docs/COMPILER_REWARD_DESIGN.md`, entries of 2026-11-20.

### Until prompt fix: "until" stays an order (`until-prompt-fix/`), 2026-11-20

**What it shows.** At reasoning `max` the production pair (generator `deepseek-v4.1-flash`, critic `glm-5.3-flash`)
read "do not drop the key while the door is closed until the door has been opened once" as `Absence(key_lost)`, a
ban for the whole episode, instead of `Precedence(door_open, key_lost)`: 6 of 6 runs on G6 and W5b, each accepted
by the critic. The prompt's example of a ban the event already holds ("an event described as 'lost before `a`
happened'") matched the `key_lost` description on the environment pages ("no longer carrying it before opening the
door") almost word for word, and the critic quoted the rule back. Rewording two existing passages fixed it, with
no new rule: only a "while ... still shut" condition folds into `Absence`, "until `a`" is always `Precedence(a, b)`,
and steps listed after a leading "then" keep their order (W5a had dropped it). Before and after: G6 0 of 3 to 4 of
4, W5b 0 of 3 to 4 of 4, W5a 2 of 3 to 4 of 4; 5 random passing cases 15 of 15; the full 46-case rerun 46 of 46,
against 44 of 46 for main's last full run at `max`. G2 ("Open the door and pick up the box in the other room.")
stays unordered. Prompt side, not pipeline side. The practice cited is Anthropic's prompting guide on examples
("Use examples effectively", and "Be vigilant with examples & details" in its Claude 4 version). The page shows
G6, W5b, W5a and G2 with task, LTLf, live RM graph and RM text, before and after.

**Evidence.** One run record (task, clauses, critic trail, machine, wall) and one slim call log (prompts and schema
dropped) per run for six rounds: before (9 runs), the two fix rounds (6 and 3), the regression rerun (3 failing
and 15 passing) and the full rerun (46); `round-table.out`; the prompt diff. 164 model calls in all, no
usage-limit error. Limits: main's full run is the older loop-2 sweep (before the shape fix and streaming), not a
same-prompt control; the targeted before round is. After the fix the critic accepted every first answer, so the
critic never judged a wrong set under the new wording. The `fix-until/` runs had the "until" edit only.

**Files.** `index.html` (built from `data.json`; open it from disk), `graphs/` (eight machines as live HTML, SVG and
RM text), `tools/` (`round_table.py`, `run_table.py`, the scorer `arm_stats.py`, `chain_score.py`, `cases.py`,
`loopcrit.py` as in `opencode-streaming/tools/`, and `slim_calls.py`), `evidence/` (952 KB: `runs/before-max/`,
`fix-until/`, `fix-then/`, `regression-fail/`, `regression-pass/`, `full-after/`, `round-table.out`,
`prompt-fix.diff`, and `cards/`, the local cards the scorer reads). Main's full run is read from
`model-comparison/evidence/llm-loop2/runs/f-max/A/`. Full call logs with prompts and the tools that call the
models stay in the plan folder.

**Rerun** (no model call, in `RM_RL_env`): `env -C docs/paper/until-prompt-fix/tools CC_ROOT=$PWD
PYTHONPATH=$PWD/app python -W ignore round_table.py before-max=../evidence/runs/before-max ...` and `run_table.py
... --cases G2,G6,W5a,W5b`; the page's last section has the full commands and a graph.

**Code.** Commit `40e6614`, merged as `f778643`: `app/src/prompts/compiler-rm/reward-ltlf-creator.system.md` and
`app/src/prompts/compiler-rm/declare-templates.md`, which the critic prompt shares.

### Stated-order rule: the machine keeps the order the task states (`stated-order-rule/`), 2026-11-20

**What it shows.** The user ruled that a Reward Machine matches the instruction, whatever the world forces ("like
the task says to get order, do keep it"). Order words ("then", "after", "before") and a compound whose second verb
needs the first ("find and acquire the key") state an order, and a stated order is now required; a plain list of
facts is one `Existence` per fact, with the ordered chain also accepted. Before, three cards marked the orders the
level forces as optional (`forced`). Commit `f29c47a` rewrote them: base-unlock-pickup (and its smoke and pilot
copies) now expects the three facts and accepts the chain and the chain with its implied `Existence`s, which MONA
finds the same task; base-key-corridor expects the facts plus `Precedence(key_found, has_matching_key)`;
tpl-responded-existence-2-goal requires both box orders. Live at reasoning `max` (production pair, main `d2d9249`),
"then" gave the exact chain in 3 of 3 runs and the plain list gave the chain, an accepted answer, in 3 of 3; no run
gave the facts. The trained "then" card tpl-response-1-goal, with its FARM bundles made again for UnlockPickup,
learned in FARM 3 of 3 seeds against no-RM 0 of 3; base-key-corridor's compound order learned in FARM 2 of 3
against 0 of 3 (shown in `keycorridor-room-size/`). The scorer compares clause lists, not tasks: on main, 9 of the 64 `mismatch` FARM
bundles state the same task as an accepted answer, an open user question. Also open: whether "Then" after an
if-rule puts the box after the ball (tpl-responded-existence-2-goal, which does not train). The page shows every
answer with task, LTLf, live RM graph and RM text.

**Evidence.** The four card files before and after the commit and the per-card clause and LTLf listing
(`order-cards.out`); the same-task sweep of all 169 FARM bundles on main, the sweep before the commit and two
one-bundle checks; the six live bundles and arm A's temporary card; six gate records; per seed of the six training
runs `judge.json`, `summary.json`, `eval.csv`, `config.yaml` and `test.json` (no weights, no traces), and the runs
file. Limits: three live runs per arm on one level, run before the until prompt fix; one trained card; the FARM
seeds used the `embedding` RM state encoding; base-unlock-pickup's bundle is stale (end judgment on, old x0.1
scale) and was not trained.

**Files.** `index.html` (built from `data.json`; open it from disk), `graphs/` (six machines as live HTML, SVG and
RM text), `check/` (`order_cards.py`, new, and `equiv_check.py`, `equiv_summary.py`, `score_live.py`,
`judge_summary.py`, `gate_order.py` from the plan folder), `evidence/` (`cards/before/`, `cards/after/`,
`order-cards.out`, `equiv/`, `live/`, `gate/`, `runs/`). The tools that called the models stay in the plan folder.

**Rerun** (no model call, from the repository root in `RM_RL_env`): `PYTHONPATH=app python -W ignore
docs/paper/stated-order-rule/check/order_cards.py` prints the card changes and the MONA checks and writes the two
compiled answers to `graphs/`; the page's last section has the live scoring, the sweep, the training table, the
gate and the training queue (about 17 min per FARM seed).

**Code.** Commit `f29c47a`, merged as `97baab7`: the cards in `experiments/benchmark/{base,smoke,pilot,templates}/
tasks.json`, the usage paragraph in `docs/LTLF_TASK_LANGUAGE.md` and the tpl-response-1-goal FARM bundles. The scorer
(`clause_status` in `app/src/benchmark/rm_facts.py`) is unchanged and keeps `forced`. Record:
`docs/decisions/benchmark/thesis-benchmark.md`, entry of 2026-11-20.

### Shop promise cost: a hard break pays the promise cost of the step limit (`shop-promise-cost/`), 2026-11-20

**What it shows.** Every shop run that learned had an open promise that cost something as the step limit ran out:
the promise cost (-0.1 a step while a hard promise is open) or the end judgment (each hard promise open at the end
pays). With either on, 12 of 12 seeds served (round 6 D and E, round 7 B4 and B8b); with both off, 0 of 12 (round 6
A, B and C and today's probe), since a whole shift of serving then paid only 2 more than one order and a stop. With
the promise cost on and a well the agent can reach, the step into the well paid -10.1 and ended the episode without
the promise cost still to come, so on all four of today's shop levels letting the food fall paid more than serving
(-16.4 against -35.5 on shop-serve, seed 1). Commit `a727b2b` charges that step the promise cost of the whole step
limit, -70 on the shop: a break at step t pays γ^t(W + cL), at most the cost of keeping the promise to the end.
After it the solve is the best plan on all eight level variants, and with the promise cost off every machine is
byte-identical. The round 7 level still trains to 12.21 / 12.07 / 12.21 served, identical to r7-B8b. Today's
shop-serve still learns 0 of 3: random play never prepares food in 1,000 episodes and the trained agents never pick
it up. Whether to pay the fetch step, add a slip-free warm-up or accept a known limit is an open user question. The
same commit replaces the no-goal plan check: the old rule failed 38 of 62 no-goal bundles by construction; the new
one passes 35 of them, leaves the 275 goal bundles unchanged, catches shop-serve built without its fall rule on 3 of
3 seeds and finds a real defect in forcing/lanes-rules (a -1 well). The page shows every machine with task, LTLf,
live RM graph and RM text.

**Evidence.** Copies of the 11 bundles the page uses and their four cards; plan pay of the round 6 and 7 and probe
bundles, and of the four levels built before (`78c666c`) and after the fix with the promise cost on and off; md5 of
the chain, card and promise sweeps and of every level machine before and after; per seed of 30 training runs (round
6 A to E, round 7 B4 and B8b, the probe, the regression and today's shop-serve) `judge.json`, `test.json`,
`summary.json`, `config.yaml` and `eval.csv`, with the configs and logs of the six runs of 2026-11-20; the random
play, trained agent and scripted plan diagnosis and the fall rate per 1M steps; the plan check of every committed
bundle before and after, stored and with the end judgment off; two gate records. Limits: the page quotes seed 1 of
the card's event seeds; the end-judgment-off rebuild gives back no stored no-goal text; rounds 6 and 7 trained with
a -5 time-limit charge, today's runs with 0; the chain sweep also reads the main checkout's local `outputs/`, and
the card sweep's trace bank was not recorded; a late break is charged all L steps, not the L - t left (user question
Q6).

**Files.** `index.html` (built from `data.json`; open it from disk), `graphs/` (eleven machines as live HTML, SVG and
RM text), `check/` (`machines.py`, `runs_table.py`, `no_fall_rule.py` and `tee.py`, new; `plan_pay.py` and
`diagnose.py`, pointed at the entry's copies; `pay_table.py`, `fall_rate.py`, `fetch_variant.py`, `chain_sweep.py`,
`card_sweep.py`, `promise_sweep.py`, `plan_check_all.py` and `compare_checks.py` from the plan folder), `evidence/`
(`bundles/`, `cards/`, `runs/`, `configs/`, `logs/`, `gate/`, `diagnosis/`, `plan-check/`, the plan pay JSON files
and the `.out` listings). No weights, agent traces or `episodes.csv`; the sweep outputs and the level bundles stay in
the plan folder's `shop-well/`. The repository's hooks added blank lines to the copied `labeling.py` files (the same
code; machine, manifest and state files are byte copies), a final newline to the two gate records, and lint fixes
to the scripts from the plan folder; the reruns of `plan_pay.py rounds`, `diagnose.py plans`, `fall_rate.py` and
`machines.py` give the stored outputs (the recorded bundle paths aside).

**Rerun** (no model call, no training, from the repository root in `RM_RL_env`): `PYTHONPATH=app python -W ignore
docs/paper/shop-promise-cost/check/no_fall_rule.py`, then the same for `check/machines.py`, prints every machine's
task, clauses, size and well pay and writes `graphs/<name>.rm`; `python docs/paper/shop-promise-cost/check/
runs_table.py` prints the served counts; `check/plan_pay.py rounds` and `levels` give the plan pay. The page's last
section lists every command.

**Code.** Commit `a727b2b`, merged as `ee9a803`: the well edge in `_price_edges` (`app/src/compiler/
reward_layer.py`), the step-limit checks in `app/main.py` and `app/src/arm_fm/environments.py`, the no-goal rule in
`app/src/benchmark/plan_check.py`, `app/scripts/ablate_rm.py`, `app/scripts/rebuild_rewards.py`,
`experiments/benchmark/configs/ppo-shop.yaml` and `experiments/benchmark/shop/runs-levels2-5.yaml`, with
`tests/test_reward_layer.py` and `tests/test_plan_check.py`. Records, changed in the same commit:
`docs/decisions/arm-fm/rm-execution.md`, `docs/COMPILER_REWARD_DESIGN.md` and
`docs/decisions/generation/run-observability.md`.

**Rebuilt on today's pipeline (2026-11-21).** shop-serve built with the code of main `56c4a1e` at the defaults
(promise cost off, end judgment off, step limit 600), twice: the card's answer compiled with no model, and a
generation from the task text with deepseek-v4.1-flash and the glm-5.3-flash critic at max thinking. The two
machines are byte-identical (md5 `68f3adf9e6122eee683a0b93d2ac5c6e`, also `shop-serve-both-off`, the machine the
probe trained to 0 served): scorer exact, 17 states, 406 transitions, well u14, pay order ok. Plan pay at the
bundle's gamma 0.99, seeds 1-3: solve -1.506 / -1.399 / -1.391, idle and wrong-0 -2.633 / -2.824 / -2.713, wrong-2
(one order, then nothing) -1.922 / -2.114 / -2.003, wrong-1 (a fall left for one step) -8.794 / -10.580 / -10.163.
Serving wins on every seed, but only by 0.42 to 0.72 over wrong-2; undiscounted it earns 0. Parts 1 and 2 discount
at 0.995, the shop runs' PPO gamma, so their numbers for the same machine differ. Limits: this build was not
trained; the generated bundle stopped at the embedding step (the embedding server refused the connection), and its
17 state texts come from the tagger before `6539207` (`keyed-state-texts/`). Files: `evidence/today-pipeline/`
(both bundle copies, the two plan pay records, `pay.out`, the generation's status, plan check and log),
`check/compile_card.py` and `check/card_plan_pay.py` (from the plan folder, where the second is `plan_pay.py`,
renamed beside the entry's own; the hooks reformatted it and the copied `labeling.py` files, the same code, and the
pay rerun after them gives the same records). The page shows it as Part 6 (version 2). Rerun (no model call, MONA on PATH):
`PYTHONPATH=app python -W ignore docs/paper/shop-promise-cost/check/compile_card.py
experiments/benchmark/shop/tasks.json shop-serve <labeling.py> OUT_DIR` gives the same machine text, and
`check/card_plan_pay.py OUT.json experiments/benchmark/shop/tasks.json shop-serve <bundle>...` gives the same pay
records, bundle paths aside. The page's last section has the generation command.

### Keyed state texts: each state's text now sits on its own state (`keyed-state-texts/`), 2026-11-21

**What it shows.** Every Reward Machine state carries a short text from the state tagger, and training builds the
state embeddings from these texts. The tagger answered with a bare JSON list that the code matched to the states by
position, so a text written for another state passed without an error. On three stored bundles, 13 of 37 texts
describe another state or the wrong duties: on tpl-response-1-goal the texts of u4, u5 and u6 are rotated by one,
so the final reads as pending and u6 claims success; on tpl-precedence-1-goal u1 holds u6's content, and u8 and u10
claim completion without being final; on shop-serve seven texts drop or mix up a duty, most often the food still to
prepare. Commit `6539207` (merge `ba918a9`) sends each state's role (final, rejecting, in progress) beside it and
keys the reply by state id; parsing refuses a missing, repeated or unknown id. Re-tagged live three times with
deepseek-v4.1-flash, every new text sits on its own state, 37 of 37 in each round; in round 1 two precedence texts
(u1, u10) are half right, adding the false claim that picking up the box ends the episode. A negative result: a word
search for completion and pending words over the 379 stored bundles finds 26 hits, 22 of them false alarms, and
misses 9 of the 13 wrong texts above. The page shows each bundle's task, LTLf, live RM graph and RM text, and a
per-state table of role, stored text, new text and verdict.

**Evidence.** Copies of the three stored bundles (main `5284fff`); the three re-tag rounds, one JSON per bundle with
each state's role, entry guards, new and stored text, the model's raw reply and its calls (9 calls in all, no
warning, no refused reply); the verdict per text; the word-search hits. `check/state_texts.py` checks that each raw
reply is keyed by exactly the machine's states and equals the recorded texts, and that the recorded stored texts are
the bundle's and still the committed ones. Limits: three bundles, one model and one provider (OpenCode); round 1
allowed 3 attempts per request, rounds 2 and 3 one; the verdicts are one reader's (the fix worker's, plus this
entry's two half-right stored texts of tpl-precedence-1-goal, u5 and u6, which say that dropping the ball back
before the key is taken breaks the order, though no edge from them reaches the failure state); the re-tag wrote no bundle, so the stored bundles keep their old texts; no training ran with
the new texts.

**Files.** `index.html` (built from `data.json`; open it from disk), `graphs/` (the three machines as live HTML, SVG
and RM text), `check/` (`state_texts.py` and `build_page.py`, new; `retag.py`, `state_list.py` and
`keyword_probe.py`, from the plan folder), `evidence/` (`bundles/`, `round-1/`, `round-2/`, `round-3/`,
`verdicts.json`, `state-texts.out`, `keyword_probe.json`). The repository's hooks reformatted the copied
`labeling.py` files and `retag.py` (ruff format, the same code); the machine, manifest, state text and round files
are byte copies, and `state_texts.py` passes its checks after the hooks.

**Rerun** (no model call, from the repository root in `RM_RL_env`): `PYTHONPATH=app python -W ignore
docs/paper/keyed-state-texts/check/state_texts.py` prints every state's texts and verdicts, runs the checks and
writes `graphs/<name>.rm`; `check/build_page.py` writes `data.json`. `check/retag.py` is the live tool: one
deepseek-v4.1-flash call per bundle over OpenCode, under `dotenv -f .env run --no-override`. The page's last section
lists every command.

**Code.** Commit `6539207`, merged as `ba918a9`: the keyed reply schema and parser in `app/src/engines/structured.py`
(`state_descriptions_schema`, `parse_state_descriptions`, `_refuse_repeated_keys`), the request in
`app/src/engines/generic_engine.py` (`describe_states`), the roles in `app/scripts/generate_rm.py` (`_state_roles`)
and the prompt `app/src/prompts/compiler-rm/reward-machine-tagger.system.md`, with `tests/test_engines.py`,
`tests/test_pipeline_orchestration.py` and `tests/test_prompts.py`. Records: `docs/decisions/arm-fm/
task-and-rm-identity.md` (reply shape) and `docs/decisions/benchmark/thesis-benchmark.md` (pre-freeze prompt log).

### Thinking levels on the frozen code (`level-benchmark-freeze/`), 2026-11-22

**What it shows.** How often FARM generation ends with the right Reward Machine at each thinking level, on the code
freeze `809dfe3`, with the production pair (generator deepseek-v4.1-flash, critic glm-5.3-flash, over OpenCode): 46
task cases of the generator loop, 3 runs each, at none, low, medium, high and max, 690 runs on 2026-11-22 between
08:49 and 10:06. Right: 105 of 138 at none (76%), 134 at low (97%), 136 at medium (99%), 138 at high and 138 at max
(100%). The median run took 4 s, 12 s, 18 s, 20 s and 88 s; 1,473 model calls in all. With any thinking the
generator's first answer was right in all 552 runs: the 6 wrong runs at low and medium each started right, the critic
rejected the right answer, and it accepted a wrong second one (4 of the 6 are G9, where the card reads "Then" as an
order from holding the key to the goal and the critic does not; one is G4, which the critic made order the key count
before the door against the 2026-11-21 ruling). At none 31 runs are wrong and 2 are form A; the page groups them by
mistake (a soft ban read as an order, 10; a stated order dropped, 12; an unstated order added, 5; an order on the
wrong step, 2; "never both" read as a plain ban, 1; an extra shop step, 1). The page shows, for every case, the task,
the card answer and the right count per level, one live RM graph per case with its task, LTLf and RM text, every wrong
run at low and medium with the critic's reply, and one full example per mistake group at none.

**Evidence.** The 690 run records (`records/<level>/<case>-r<k>.json`: task, models, every candidate and critic
reply, final clauses, machine text, time and call count) and the five rate-limited records kept as `*.json.429`.
`check/arm_stats.py` on `records/` prints `stats.md`'s table again (runs, right, form A, wrong, first right, catch@1,
false alarm, rounds and time match; its call-log columns print 0, since no call log is copied). `check/build_page.py`
scores every run with the same scorer, checks that the records' call counts equal the call logs' (1,473), compiles
every shown machine again from its run's clauses with the frozen compiler and stops if one differs from the record's
`machine` text, and checks that the mistake groups cover every run not right at none. Limits: one model pair and one
provider, 3 runs per case and level; the 46 cases are picked around past mistakes, not sampled; times come from 8
runs at once beside 12 to 23 RL trainings; the mistake groups are this entry's reading. The 46 cases are the `CASES` list in
`check/level-bench.sh`.

**Incidents.** Rate limit: at none 5 runs (G6-r3, G7-r1, G7-r2, G7-r3, G8-r1) stopped on HTTP 429 after 10 reruns;
their records were renamed `*.json.429`, kept, and the 5 runs were run again and accepted. Guard bug: the low round's
budget guard outlived its round and stopped medium after 14 runs (`evidence/STOP.guard-bug-0900`); the driver now
stops each level's guard, and medium resumed, skipping finished runs.

**Files.** `index.html` (built from `data.json`; open it from disk), `records/`, `graphs/` (every machine on the page
as live HTML, SVG and RM text; the 1,122-transition shop machine `w4a-none-r3` only as RM text), `stats.md` (the
scorer's output on the full run folders, call logs included), `check/` (the scorer `arm_stats.py`, `chain_score.py`, `loopcrit.py` and `cases.py`, lint-clean copies of the plan
folder's with the same logic; the page builder `build_page.py` with its prose in `page_text.json`; the run drivers
`level-bench.sh` and `run_arms.sh`), `evidence/` (`cards/`, the cards the scorer reads: main `e6c3acb` plus the
loop's local soft cards for S1 to S4; `round-logs/`, one per level with the account usage lines removed;
`level-bench.log`; `STOP.guard-bug-0900`). Not copied: the call logs (`*.calls.jsonl`), the work folders and the
Python tools the drivers call (`run_arms.py`, `gen_one.py`, `budget.py`, `budget_guard.sh`), which call the models and
use path tricks the repository's hooks reject; they stay in the plan folder `farm-final-20261119/until-fix/tools/`.

**Rerun** (no model call, from the repository root in `RM_RL_env`, MONA on PATH): `env -C
docs/paper/level-benchmark-freeze/check CC_ROOT=$PWD PYTHONPATH=$PWD/app python -W ignore arm_stats.py
none=../records/none low=../records/low medium=../records/medium high=../records/high max=../records/max
--letters` prints the table and one letter per run; the same with `build_page.py` writes `graphs/` and `data.json`,
and the artifacts skill's `fill.py` renders `index.html`. The run itself (model calls, credentials from `.env`), from
the plan folder `farm-final-20261119/`: `bash freeze-prep/tools/level-bench.sh 8`, which runs each level as `bash
until-fix/tools/run_arms.sh freeze-<level> <the 46 cases> A 3 8 <level>` (arm A, 3 runs per case, 8 at once) and keeps
finished runs.

**Code.** The code freeze `809dfe3` (merge "minimization on by default", feature commit `a849dfb`). The runs read main
at `e6c3acb`, which adds only bundle data: no file under `app/` and no card file differs from the freeze.

### Wrong clauses at max: every one reads two ways (`wrong-clauses-at-max/`), 2026-11-22

**What it shows.** The final-run FARM bundles (266, generator deepseek-v4.1-flash and critic glm-5.3-flash at max
thinking, code freeze `809dfe3`) whose stored clauses differed from their card's answer on the model's side: 8. Each
came from a sentence a person could also read the model's way: an extra soft "at some point" beside a soft order (4),
"not both" read as "neither" or as a plain ban (2), and an extra hard rule from the wording (2). Miquel accepted 7
readings and added them to the cards' `also_ok`; `shop-boil~p2` stays held (below). The page shows each bundle's task,
one row per clause (card answer, model answer, which side differs), the machine the model's clauses compile to as a
live graph with its RM text, and the verdict.

**Evaluation methodology.** A rule set that differs from the card's answer still counts as right when it is a fair
reading of the sentence and its machine still trains the task in the card's world. The model gets the environment
description, so world knowledge in its choice is fine (rule in `docs/decisions/benchmark/thesis-benchmark.md`, card
scoring, 2026-11-22). Example: on `tpl-precedence-soft-1-goal` the extra soft `Existence(blocker_moved)` pays +1 for
moving the ball, which every way to the box needs; the right order still beats taking the key first by 1, as in the
card's own machine (12 vs 11, against 11 vs 10).

**The writing lesson.** With thinking on, the generator's remaining mistakes are readings, not errors: how a task is
worded decides which machine comes out. The task-language guide now lists these readings and how to write each one
(`docs/LTLF_TASK_LANGUAGE.md`, "Wordings that read two ways"), next to the rules for commas, full stops and "then".

**Held: `shop-boil~p2`.** "Each time the pot boils over, put your load down beside the stove, turn the stove down and
pick the load back up" gave an extra hard `Response(stove_fixed, holding_food)`. The reading is fair, but the rule
holds after every stove fix, even with empty hands, and the plan check measures the cost: the plan that ignores the
siren pays no less than the solving plan (seed 1: -1.0 both; seed 3: discounted -2.25 against -2.40;
`evidence/shop-boil_p2.plan_check.json`). When the agent carries food for an order, the card's own rules already make
it pick the food back up (the food still has to be prepared or served), so the extra rule only bites with empty
hands. The step the task states has no exact fact in the shop world: there is no "put the food down" event, only
`holding_food`. With one, `Response(food_set_down, holding_food)` would say it exactly; without it the model chose a
broader rule where the card leaves the step to the order rules. One more paraphrase, `tpl-not-co-existence-1-goal~p2`
("You must not drop the key while the door is still closed and open the door in the same run"), read "and open the
door" as its own order (`Existence(door_open)` beside the `Absence`); the "not" may or may not cover it, so it was
accepted too.

**Evidence.** `evidence/clause-status-after-rulings.json`: `rm-facts` on the stored bundles with the updated cards.
Templates: 159 exact, 8 `also_ok`, 4 equivalent, 1 mismatch (`tpl-not-co-existence-1-goal~p2`, accepted afterwards);
shop: 23 exact, 1 mismatch (`shop-boil~p2`, held). `evidence/wrong-bundles.json`: the 8 bundles' tasks, card clauses and model clauses with
their LTLf.

**Files.** `index.html` (built from `data.json`; open it from disk), `graphs/` (7 machines as live HTML and SVG;
`shop-boil~p2`'s 7.2 MB machine is too big to draw), `evidence/`.

**Rerun** (no model call, from the repository root in `RM_RL_env`, MONA on PATH): `PYTHONPATH=app python -W ignore
app/main.py rm-facts --bundles experiments/benchmark/<suite>/bundles --tasks experiments/benchmark/<suite>/tasks.json
--output <file>.json` for `templates` and `shop`; the artifacts skill's `fill.py` renders `index.html` from
`data.json`.

**Code.** Bundles from main `e6c3acb` (freeze `809dfe3`); cards as edited on 2026-11-22 (the `also_ok` answers
above).

### Plan-check validation: right machines pass, 6 wrong ones slip through (`plan-check-validation/`), 2026-11-22

**What it shows.** Whether the plan check (`app/src/benchmark/plan_check.py`) passes right machines and fails wrong
ones, tested on 62 machines whose rightness comes from other sources: 16 right final-run FARM bundles, 15 wrong FARM
bundles from before the freeze, 16 ARM-FM bundles, and 15 mutants (a right bundle with one planted defect in its
machine or its labeling). With the soft-break fix (main `029d82c`) every right machine passes (26 of 26) and 29 of 35
wrong ones fail; 1 is not counted. Before the fix (`e6c3acb`) 4 right machines failed, each a soft rule priced by
paying less than the solve, which ruling D1 (2026-11-22) accepts; the fix flips exactly those 4 and no other verdict.
The 6 false passes are the check's blind spots: a soft break on every step that costs more than one hard break (2), an
added goal the solve reaches anyway (1), a no-goal ARM-FM machine that ends the shift early (1), a well edge that pays
more than the solve on a machine with a final state (1), and a fact that fires late but in the right order (1). The
page shows the counts, one task with a machine from each set, every false verdict and the right verdicts whose reason
is loose, each with its NL task, LTL (ARM-FM bundles store none), live graph and RM text, and the method.

**Evaluation methodology.** Truth never comes from the plan check: the clause scorer (`rm-facts`, against the card's
answer and `also_ok`), the labeling replay (`repair-labeling --check-only` on the suite's reference traces; the shop's
freeze gate record), training results, the 2026-11-22 rulings D1-D3, and for mutants the planted defect. Two sources are
supplementary and marked on the page: `check-pay-order` (it decides the two pricing blind spots) and a hand read of the
ARM-FM machines, which store no clauses (the only source for ARM-FM `shop-serve` and `shop-siren`).
`tpl-responded-existence-1-goal~prefreeze` stays out of the counts: it misses a `Response` its hard goal makes
redundant. A fail can be trusted here; a pass alone cannot (6 of 32 counted passes are wrong), and 4 of the 6 are
flagged by another tool in the study (pay order, scorer, labeling replay).

**Evidence.** `evidence/records/phase1/` and `phase2/`: the 62 plan-check records per code version;
`evidence/phase2-changes.json`: the 4 verdicts the fix changed; `evidence/truth.json` and `truth-raw/`: the truth and
the scorer and pay-order outputs behind it. A rerun from the packed copies with the `029d82c` code gave the same verdict
and problem list for all 62.

**Files.** `index.html` (built from `data.json`; open it from disk), `graphs/` (19 machines as `.rm`, SVG and live
HTML), `evidence/` (`copies.tar.gz`, the 62 bundle copies, packed so the hooks leave their `labeling.py` byte-exact;
records, truth, joined results), `check/` (`spec.json` and `build.py` made the copies; `run_checks.py`,
`snapshot_records.py`, `compare.py`, `collect.py`, `clause_diff.py`, `pay_order.py`, `export_code.py`;
`build_page.py`).

**Rerun** (no model call, from the repository root in `RM_RL_env`, MONA on PATH; `W` a scratch folder):
`cp -r docs/paper/plan-check-validation/evidence W`, `tar -xzf W/copies.tar.gz -C W`, `python
docs/paper/plan-check-validation/check/export_code.py 029d82c W/code`, `python
docs/paper/plan-check-validation/check/run_checks.py W W/code/app W/logs`, `snapshot_records.py W W/records/again`,
then `compare.py W/records/phase2 W/records/again W/changes.json` (expect 0 of 62 changed) and `collect.py W phase2`
for the table. The page: `PYTHONPATH=app python docs/paper/plan-check-validation/check/build_page.py`, then the
artifacts skill's `fill.py`.

**Code.** Final-run bundles generated on the freeze `809dfe3` (stored at main `e6c3acb`); pre-freeze bundles from the
`809dfe3` tree and the archives named in `check/spec.json`. Plan check of `e6c3acb` (before) and of `029d82c`, the
merge of the soft-break fix `57a91cb` and the no-goal trace fix `957ccf2`; cards of `029d82c` for both runs.

### Shop machines pay nothing per order (`shop-net-zero-pay/`), 2026-11-22

**What it shows.** A FARM shop machine charges 3 when a client arrives and pays 1 back each for taking the order,
cooking and serving, so a served order nets about 0 and the return mostly counts what is still open when the shift
ends. A served order nets exactly 0 on 3 of the 10 machines; on the other 7 it pays +1 or -1 on 2.2% to 7.1% of orders
(siren pay falling between serves), a mean of -0.003 to -0.010 (review R3, 2026-11-22).
On `shop-serve` all 724 orders the scripted worker served on the judge's 100 test seeds netted exactly 0: solve 0, take
one order and stop -2, serve one order and stop -3, idle -3. The solve still ranks first on every machine, but only by
0.47 to 1.85 per episode discounted, and serving more does not raise it. This is the pricing rule, not a bug and not the
model: all 10 clause sets equal the card's answer, and the end charge for an order left open is off by default since
`deff802`. It is also not why the agents serve nothing: 0 of 51 trained shop runs served an order in their 100 test
episodes (0%, 95% Wilson CI [0%, 7.0%]), FARM and no-RM with the world's +1 per serve included. On the six counted
cards serving needs cooking, and no arm gets that far. Replayed with the promise cost on, the solve wins by 19.68 to
43.79 plain. The page shows the plan returns, the judge table, the ladder check, and the ten machines with task, LTLf
and RM text (a live graph for the six small enough to draw).

**Evidence.** `evidence/shop-pricing/<bundle>.json` and `table.md`: four scripted plans per bundle on the judge seeds
2000000-2000099, replayed through the stored FARM bundle (plain and discounted at 0.995, cut at the well as in the runs)
and through a copy rebuilt with `rebuild-rewards --promise-cost`. `evidence/pricing-check.json`: the four ladder rungs
and `shop-serve` on reset seeds 1-20. `evidence/judge/`: the 51 judge files. `evidence/plan_vs_agent.json`: the earlier
solve returns the replay must match (it does, on every seed of the six counted cards). `evidence/shop-pricing.md`: the
source note.

**Gaps.** `shop-boil` at main `881b22d` holds a failed generation; the replayed bundle is the uncommitted worktree one,
marked `reconstructed`, so no hash proves its labeling is the one the runs used. The end-judgment option and the
paraphrase bundles were not replayed.

**Files.** `index.html` (built from `data.json`; open it from disk), `graphs/` (6 machines as `.rm`, SVG and live HTML;
the other 4 are too big to draw), `evidence/`, `check/` (`shop_pricing.py`, `pricing_check.py`, `build_page.py`).

**Rerun** (no model call, no training, from the repository root in `RM_RL_env`): `PYTHONPATH=app python -P -W ignore
docs/paper/shop-net-zero-pay/check/shop_pricing.py table` rebuilds the table from the copies; `shop_pricing.py play
<bundle>` replays one bundle (about 5 minutes; the `rebuild-rewards --promise-cost` line before it is on the page);
`PYTHONPATH=app python -W ignore docs/paper/shop-net-zero-pay/check/pricing_check.py --out <json> --seeds 20
CARD@BUNDLE ...` is the ladder check. The page: `PYTHONPATH=app python -W ignore
docs/paper/shop-net-zero-pay/check/build_page.py`, then the artifacts skill's `fill.py`.

**Code.** Replays and checks on main `881b22d` with the FARM bundles stored there; the end charge has been off by
default since `deff802` (2026-11-18).

### ARM-FM shop machines end before the agent moves (`armfm-shop-start-final/`), 2026-11-22

**What it shows.** Asked for reward machines for the shop's never-ending tasks, the ARM-FM generator made the start
state final in 21 of 22 gated machines (95% Wilson CI [78%, 99%]), and 0 of 22 pass the gate. Our ARM-FM prompt asks
the model to declare every accepting state in `FINAL_STATES`; for "whenever the siren rings, turn it off" the state
where nothing is owed accepts, and that is the start. The runtime ends an episode at a final state, so each episode
ends before the first action and nothing trains: none of the 11 counted ARM-FM shop cards gets a run, and all count as
not learned. `shop-boil` (main) finished at 21:21, after the gate and after this entry was built; its machine also
starts final (root check: INITIAL_STATE u0 = FINAL_STATES u0), so 23 of all 24 ARM-FM shop machines start final; it is
not in the packed 23. Apart from that, all 8 siren and pot machines are
right Response machines. The one exception, `shop-boil~p3`, steps to its final state on any served order, so wrong
plans also end at their first serve; it passes the pay order check and fails the plan check. The page shows the siren,
pot and serve machines and `shop-boil~p3` with task, the card's LTLf (ARM-FM bundles store none), live graph and RM
text, and a table of all 23 finished bundles.

**Evidence.** `evidence/bundles-freeze.tar.gz`: the 23 finished ARM-FM shop bundles from
`experiments/benchmark/shop/bundles-freeze/arm-fm` with their status and plan-check files, packed so the hooks leave
their `labeling.py` byte-exact. `evidence/gate/`: the gate records of the 22 gated bundles (precheck, gate verdict,
summaries) and the gate's `summary.py`, kept as written; it predates `shop-boil~p2`, which finished after the gate, and
stops there. `evidence/armfm-shop-gate.md`: the gate's source note.

**Files.** `index.html` (built from `data.json`; open it from disk), `graphs/` (4 machines as `.rm`, SVG and live
HTML), `evidence/`, `check/build_page.py`.

**Rerun** (no model call, from the repository root in `RM_RL_env`, MONA on PATH; `W` a scratch folder): `PYTHONPATH=app
python -W ignore docs/paper/armfm-shop-start-final/check/build_page.py` reads the pack and the gate records, then the
artifacts skill's `fill.py`. The plan check again: `tar -xzf
docs/paper/armfm-shop-start-final/evidence/bundles-freeze.tar.gz -C W`, then `PYTHONPATH=app python -W ignore
app/main.py check-plans --tasks experiments/benchmark/shop/tasks.json --bundles W/bundles-freeze` (it needs the
`<bundles>/arm-fm/<card>` layout and writes `W/bundles-freeze/arm-fm/<name>.plan_check.json`).

**Code.** Bundles generated after the freeze `809dfe3`, on main commits `029d82c` to `881b22d` (main moved while the
background generation ran; in `app/` only the half fall world `e37dff9` and the tagger default `f634e0f` changed, and
neither touches the generator). Page built on main `881b22d`.

### Two right answers: the wording picks, not chance (`clause-choice/`), 2026-11-22

**What it shows.** Some cards accept more than one rule set (`expect` and `also_ok`); this entry asks which one the
generator writes. It is not random: runs of one wording give one answer (51 of 52 three-run groups agree, where a
uniform pick among the listed answers would make 27% agree). The card's `expect` gets no extra pull: it wins 84 of 153
right level runs, 55% [47%, 63%], against 50% for a uniform pick. Ordered tasks get the form the generator prompt
teaches, the last step's `Existence` plus the `Precedence`s: 12 of 12 final-run bundles and 119 of 119 level runs from
low to max, whichever side the card lists it on. Rewording moves the pick and thinking does not: on each of the 5
wording cards with four wordings, one or more wordings took the other answer (8 of 24 bundles), while low, medium, high
and max pick the same on every right run. The page shows the shares as bars with 95% Wilson intervals, the ordered and
wording tables, and each chosen answer's machine with its task, LTLf, live graph and RM text.

**Evaluation methodology.** Two sets, never mixed: the final-run FARM bundles (36 bundles of 15 card entries that list
more than one answer; freeze `809dfe3`, max thinking, generator deepseek-v4.1-flash, critic glm-5.3-flash) and the
thinking-level benchmark at the freeze (`level-benchmark-freeze/`: 11 of its 46 cases, 3 runs at each of 5 levels, 165
runs). The repo scorer `clause_status` decides right or wrong; the script only names which listed answer it matched:
`expect`, then each `also_ok`, then the MONA same-task check. All 189 right answers matched exactly. The prompt's form
is a hand reading of the generator prompt's order rules (`PROMPT_FORM` in `check/clause_choice.py`).

**Gaps.** Six `also_ok` answers came from these same bundles: the readings accepted on 2026-11-22
(`wrong-clauses-at-max/`) added them to six cards, which entered this set because a wording disagreed. So the final run
overstates how often wordings split: its `expect` share is 24/36 with those answers and 11/15 without. Each reworded
bundle ran once, so whether a wording repeats its pick is untested; three reruns of the 8 wordings at max (24 model
calls) would settle it.

**Evidence.** `evidence/choices.json`: the 201 generations (36 final-run, 165 level runs) with card, task, clauses and
the answer matched; `evidence/tables.md`; `evidence/rm/`: the 25 chosen answers' machines; `evidence/clause-choice.md`:
the source note.

**Files.** `index.html` (built from `data.json`; open it from disk), `plots/choice-shares.svg` and
`choice-shares-dark.svg`, `graphs/` (25 machines as SVG and live HTML), `evidence/`, `check/` (`clause_choice.py`,
`build_page.py`).

**Rerun** (no model call, from the repository root in `RM_RL_env`, MONA on PATH): `PYTHONPATH=app python -W ignore
docs/paper/clause-choice/check/clause_choice.py` rewrites `evidence/` from the stored bundles and
`docs/paper/level-benchmark-freeze/`; `PYTHONPATH=app python -W ignore docs/paper/clause-choice/check/build_page.py`
writes `data.json` and the plot, then the artifacts skill's `fill.py`.

**Code.** Final-run bundles generated on the freeze `809dfe3`; level runs with the cards of main `e6c3acb` (the
snapshot in `level-benchmark-freeze/evidence/cards`); final-run scoring with the cards and scorer of main `881b22d`.

### How often the next move can pick up a fallen box (`fall-rate/`), 2026-11-22

**What it shows.** The box-carry rule "whenever the box falls, pick it up on your very next move" can only be met when
the box lands right in front of the agent, and each fall world decides that differently. Two scripted agents, the
solving plan and a walker, on reset seeds 0-999: face 100% for both; side 100% and 77.4% [75.1%, 79.5%]; none 71.1%
[68.8%, 73.4%] and 41.1% [38.5%, 43.7%]; half, added on 2026-11-22, 51.6% [49.1%, 54.2%] and 52.7% [50.0%, 55.3%], the
only world near one in two for both. The intended 25% and 75% of none and side hold only on open floor: in the start
corner, walls send three landings in four to the front. The rule first asked for (turn only for a box at the right) was
rejected at 93.9% and 75.4%. In the earlier training series (3 seeds), every arm solved face on 3 of 3 seeds; FARM
solved side 3 of 3 and none 0 of 3, where its agent drops the box after the first fall and walks out for the safe +1.
The page shows the rates as bars with 95% Wilson intervals (z = 1.96, as in the source), the full table, the task with
its LTLf, the FARM and ARM-FM machines as live graphs with RM text, and the runs.

**Evidence.** `evidence/table.md`, `falls.json`, `digests.json`: the rates, every fall (step, agent cell, direction,
what lies in front) and one digest per episode. `evidence/before-029d82c/`: the same three files on the code before the
half rule. `evidence/judge/`: the 15 judge files of the earlier series. `evidence/fall-half.md`: the source note. Rerun
on main `881b22d`: the same table byte for byte and the same digest on all 13,200 episodes; against `029d82c`, 0 of
11,000 shared episodes changed; half has the draws, first landing cell and step of none and side on 1000 of 1000
seeds.

**Gaps.** The rates come from scripted agents; a trained agent can stand elsewhere and see other rates on none and
side. The half-world trainings and the ARM-FM and no-RM runs on side and none finished on 2026-11-22 after these
sources and are not here; the Test 2 count owns them.

**Files.** `index.html` (built from `data.json`; open it from disk), `plots/pickable-falls.svg` and
`pickable-falls-dark.svg`, `graphs/` (2 machines as `.rm`, SVG and live HTML), `evidence/`, `check/`
(`fall_half_rates.py`, `compare_digests.py`, `same_landing.py`, `missed_falls.py`, `build_page.py`).

**Rerun** (no model call, no training, from the repository root in `RM_RL_env`): `PYTHONPATH=app python -W ignore
docs/paper/fall-rate/check/fall_half_rates.py --out docs/paper/fall-rate/evidence`; `python
docs/paper/fall-rate/check/compare_digests.py docs/paper/fall-rate/evidence/before-029d82c/digests.json
docs/paper/fall-rate/evidence/digests.json`; `PYTHONPATH=app python -W ignore
docs/paper/fall-rate/check/same_landing.py`; `python docs/paper/fall-rate/check/missed_falls.py
docs/paper/fall-rate/evidence/falls.json templates walk`. The page: `PYTHONPATH=app python -W ignore
docs/paper/fall-rate/check/build_page.py`, then the artifacts skill's `fill.py`.

**Code.** Half rule `507886e`, merged as `e37dff9`; the before-code `029d82c`; reruns and page on main `881b22d`.
