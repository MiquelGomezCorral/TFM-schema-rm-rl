# Rule-only rewards: a penalty the agent can earn back

Date: 2026-11-11, from the result page of 2026-10-27 (live tests 2026-10-26 to 2026-10-29). Open
`index.html` in a browser; everything it needs is in this folder.

## The idea

Some rules wait for an event: "Whenever a window breaks, fix it." The agent did nothing wrong when the
window broke; it just happened. But from that step the rule is waiting, and the Reward Machine says so
at once: the step where the window breaks costs -0.1. Fixing the window pays the +0.1 back, so a window
that broke and was fixed totals 0, the same as a window that never broke. If the episode ends with the
window still broken, the machine charges the open promise: -1 for a hard rule, -0.5 for a soft one.

So the penalty tells the agent that something needs a reaction, and the only reaction that earns the
points back is the one the user asked for. The same holds when something the agent did starts the
wait (it drops the key): the -0.1 comes back when it keeps the promise.

The same idea on the graph: states with an open promise (`PENDING_PROMISES`) are states to run away
from, because ending the episode there costs -1 per hard and -0.5 per soft promise. The only free way
out is the edge that does what the rule asks. The other exits pay too: a broken hard rule falls into
the well (-1 plus what the state still owed, the episode ends), a broken soft rule pays -0.5 when it breaks. Running away from the
waiting states and doing the task or the preference are the same thing.

Measured on the real code (`check/window_check.py`, the time limit after the last step):

| Episode | Step rewards (hard) | Hard | Soft | Before the end judgment |
| --- | --- | --- | --- | --- |
| Window breaks, agent fixes it | -0.1, +0.1 | 0 | 0 | -0.5 |
| Window breaks, fixed three steps later | -0.1, 0, 0, +0.1 | 0 | 0 | -0.5 |
| Nothing happens | 0, 0 | 0 | 0 | -0.5 |
| Window breaks, never fixed | -0.1, 0, -1 | -1.1 | -0.6 | -0.6 |

The window task is `Response(window_broken, window_fixed)`, LTLf `G(window_broken -> F window_fixed)`;
its RM text is in `rm/window-hard.txt` and its graph in `graphs/window-hard.html`.

What this does not show:

- These are rewards on scripted episodes through the real runtime. No run here measures that an
  agent learns to react: L2.3 trained a smoke budget and evaluated one episode.
- A late fix costs nothing apart from discounting: fixing 50 steps late loses about 0.04 at
  gamma = 0.99 (computed, not measured). Only the end charge prices leaving the promise open.
- With two hard promises open at the end the charge was -2, more than breaking a hard rule on the last
  step (-1). Solved by the well charge below: a break from that state now costs -3, the well's -1 plus
  the same -2 (thesis example 2, from u1).

## Found in review: event loops that paid nothing (found and fixed, 2026-11-11)

The user's review of the Slice 2 examples on the page found that the same idea did not hold
everywhere: some events opened a promise and cost nothing, and their repair paid nothing, although a
reward was clearly available. The examples, with the old text from the first file and the new text
from the second:

- **The alarm** (`rm/s2-ex4.txt`, `rm/s3-ex4.txt`): "When the alarm rings, switch it off at the very
  next step. Preferably, if the power ever goes out, run the generator." The same alarm loop appeared
  three times: u0 <-> u3 paid -0.3/+0.3, u2 <-> u5 paid -0.1/+0.1, and u1 <-> u4 paid 0. The step
  u3 -> u4 (switched off, then the alarm rings again and the power goes out) paid +0.1 although the
  agent then owed one more promise.
- **The thesis example 2** (`rm/thesis-ex2-before.txt`, `rm/thesis-ex2-after.txt`): "Reach the goal. If
  the key is dropped, pick it up right away." Dropping the key (u0 -> u1) and picking it up (u1 -> u0)
  paid 0 and 0.
- **The box and the key** (`rm/s2-ex3.txt`, `rm/s3-ex3.txt`): "Whenever the box falls off the shelf, put
  it back. Preferably pick up the key at some point." The box falling cost -0.1 when the agent held the
  key (u1 -> u3) and 0 when it did not (u0 -> u2); putting it back paid +0.1 and 0.
- **The door and the box** (`rm/s2-ex5.txt`, `rm/s3-ex5.txt`): "Open the door. Whenever the box falls
  off the shelf, preferably put it back." The box falling and being put back (u0 <-> u2) paid 0; the
  soft rule was priced only on the last step (1.1 or 0.6).

Cause, in `_progress` of `app/src/compiler/reward_layer.py`: progress paid by the longest path to a
target (a final state, or a state where nothing is pending), and to keep loops from being farmed every
loop was squashed into one point that pays nothing. A break-and-repair loop is such a loop unless one of
its ends is a target, because targets' outgoing edges are left out. Loops between two states that both
owe something (the soft key, the generator, the goal) therefore paid 0, and the longest path gave the
same event different prices depending on what else was pending.

The fix, in the user's words: "getting closer to finishing a task or a rule pays; stepping back from
it, or getting a new thing to do, costs." Each state is a to-do list:

- Each goal and each rule is an item. A state scores -0.1 for each step its items still need, and an
  edge pays the difference between the scores of its two ends: +0.1 for a step toward finishing,
  -0.1 for a step back or a new item. Tasks with and without a goal work the same way, and any loop
  totals 0, so nothing can be farmed.
- When the environment ends the episode, every open item is charged: -1 if hard, -0.5 if soft. A goal
  is a hard item, so goal tasks are judged this way too (before, they paid a flat -0.5).
- The well rule: an edge into the well pays -1 plus what timing out in the state it leaves would cost
  (`WELL_REWARD + hard * HARD_FAILED_REWARD + soft * SOFT_FAILED_REWARD`, the counts `PENDING_PROMISES`
  writes). Breaking a rule is therefore always worse than running out of time. The user's words: "the
  arrows that point to the reaction wells do get the today's point plus, or in this case minus, the
  same reward penalization that the agent would get by ... finishing the environment time limit on that
  state." The runtime needed no change.

Old and new rewards, from `check/todo_list_check.txt` (a pair of numbers is the edge one way / back):

| Alarm edge | Old | New |
| --- | --- | --- |
| u0 -> u3 alarm rings / u3 -> u0 switched off | -0.3 / +0.3 | -0.1 / +0.1 |
| u2 -> u5 / u5 -> u2 | -0.1 / +0.1 | -0.1 / +0.1 |
| u1 -> u4 / u4 -> u1 | 0 / 0 | -0.1 / +0.1 |
| u3 -> u4 switched off, rings again, power cut | +0.1 | -0.1 |
| into the well from u3 / u4 / u5 | -1 / -1 / -1 | -2 / -2.5 / -2 |

| Thesis example 2 | Old | New |
| --- | --- | --- |
| u0 -> u1 key dropped / u1 -> u0 picked up | 0 / 0 | -0.1 / +0.1 |
| into the well from u1 / u3 | -1 / -1 | -3 / -2 |
| key dropped, then the time limit (step reward, in u1) | -0.5 | -2.1 |
| key dropped, then a break (step rewards, from u1) | 0, -1 | -0.1, -3 |

| Box and key edge | Old | New |
| --- | --- | --- |
| u0 -> u2 box falls, no key / u2 -> u0 box back | 0 / 0 | -0.1 / +0.1 |
| u1 -> u3 box falls, key held / u3 -> u1 box back | -0.1 / +0.1 | -0.1 / +0.1 |
| u0 -> u1 key picked up | +0.2 | +0.1 |
| u0 -> u3 box falls and key in one step | +0.1 | 0 |

| Door and box edge | Old | New |
| --- | --- | --- |
| u0 -> u2 box falls / u2 -> u0 box back | 0 / 0 | -0.1 / +0.1 |
| u2 -> u1 door, box down / box back | 0.6 / 1.1 | 0.7 / 1.2 |
| fall, then door: total, box down / box back | 0.6 / 1.1 | 0.6 / 1.1 |
| time limit in u0 / u2 | -0.5 / -0.5 | -1 / -1.5 |

From u1 of the thesis example, the time limit charges -2 (the drop before it cost -0.1) and a break
costs -3. Before, the time limit paid the flat -0.5 and a break -1.

What it does not show:

- No learning run measures the effect. These are rewards on machines compiled with the real code and on
  scripted episodes.
- Reward numbers are not comparable with runs trained before the change. Success rates are.
- A goal machine is now charged whenever the environment ends the episode outside a final state,
  termination included. Before, only the time limit paid the flat -0.5.
- `rule-only-progress/check/end_judgment_check.py` and `real_code_check.py` now fail on purpose: they
  record the older code.
- The "forced breaks" thresholds in `docs/COMPILER_REWARD_DESIGN.md` are derived, not measured.
- The live tests below ran on the earlier commit and were not rerun. A rebuild of the 65 machines of
  `tests/rm_texts.py` gives: all 42 goal machines carry the judgment lines and 28 change rewards (each
  has a rule clause); 19 of the 20 one-rule machines keep their rewards (the hard `ChainResponse`
  changes at its well edge). The L1.3 check on the rebuilt texts finds no positive reward loop in 71
  machines.

## What it shows

The result page of the rule-only rewards work, with the idea above as its first section. A task made
only of rules has no goal, so its Reward Machine had no final state and paid almost nothing; every
episode lost the same flat -0.5 at the time limit, kept rules or not. Two changes fix that:

- **Slice 1, progress:** +0.1 per step toward a state where no rule is waiting, -0.1 per step away.
- **Slice 2, end judgment:** when the environment ends the episode, the open promises are charged at
  values the RM text carries (`HARD_FAILED_REWARD: -1`, `SOFT_FAILED_REWARD: -0.5`), in place of the
  flat -0.5. An episode that ends in an accepting state is a success.

At Slices 1 and 2, machines with a final state and author bundles kept their text, rewards and flat
-0.5; Slice 3 (the section above) later changed compiled goal machines too. Author bundles, PPO and
DQN are unchanged. The page shows the idea, the Slice 3 fix with the before and after of four examples,
the seven final live tests, the before and after machines of Slice 1, five Slice 2 examples and the
generated bundle (each with its task, LTLf and RM text), the review findings, what was disclosed and
not changed, and the open follow-ups.

## Evidence

The final live tests ran on commit `a56bbed`; each report is `evidence/close/<test>/report.md`.

- **L1.1:** the real code builds the 20 one-rule machines exactly as simulated in `rule-only-progress/`;
  9 differ from the old code.
- **L1.2:** 42 of 42 machines with a final state are byte-identical to before.
- **L1.3:** 71 machines, none with a positive reward cycle.
- **L1.4:** 3 of 3 real CLI runs of "Whenever you drop the key, pick it up again" give the two-state
  machine, -0.1 on the drop and +0.1 on the pick-up.
- **L2.1:** 54 of 54 checks on the RM text format (round trips, rejected and accepted texts).
- **L2.2:** 24 of 24 checks on scripted DoorKey episodes; the page's table of what the last step pays
  (15 cases) comes from it.
- **L2.3:** the full flow (generate, train, test) on the key task. The first run stopped at labeling
  (the critic's reply was not JSON) and is kept; one approved rerun passed all six steps, replay 33 of 33.

## Files

- `index.html`, `data.json`: the page and its content.
- `graphs/`: 20 RM graphs, interactive HTML and SVG (the window task, Slice 1 before and after, the five
  Slice 2 examples, the L2.3 bundle, and the Slice 3 graphs `s3-ex3`, `s3-ex4`, `s3-ex5`,
  `thesis-ex2-before`, `thesis-ex2-after`). `rm/`: their RM texts.
- `check/window_check.py`, `check/window_check.txt`: the window task and its output.
- `check/todo_list_check.py`, `check/todo_list_check.txt`: Slice 3. Compiles the four fix examples with
  the real code, prints the old and new reward of every edge, asserts the tables and that every event loop
  nets 0, plays the time limit through `RewardMachineEnvironment`, and writes the new RM texts to
  `rm/s3-ex3.txt`, `s3-ex4.txt`, `s3-ex5.txt` and `thesis-ex2-after.txt`. The old texts are
  `rm/s2-ex3.txt`, `s2-ex4.txt`, `s2-ex5.txt` and `thesis-ex2-before.txt`.
- `evidence/close/`: the reports and outputs of the final live tests. The embeddings server logs are
  left out.
- `samples/`: the inputs of the live tests (the L1.4 and L2.3 task, the L2.3 training config, the
  RM texts the parser must accept or reject).
- The live-test scripts are not copied: they fail the repository's lint rules, and the Slice 1 and L2.1
  ones read private plan files. Their outputs are in `evidence/close/`. `check/window_check.py` and
  `rule-only-progress/check/` rerun the same machines and the end-judgment totals.

## Rerun

From the repository root, inside `RM_RL_env`, on the code below. No LLM call unless stated.

```bash
PYTHONPATH=app:docs/paper/rule-only-progress/check python -W ignore \
    docs/paper/rule-only-rewards/check/window_check.py
```

It ends with `PASS: every total matches; the repair earns back what the break cost`.

```bash
PYTHONPATH=app python -W ignore docs/paper/rule-only-progress/check/end_judgment_check.py
```

It ends with `PASS: every total matches; idling with two hard promises open costs more than the well`
on the code of Slice 2. Since Slice 3 it exits 1 on purpose: it records the older code.

```bash
PYTHONPATH=app:docs/paper/rule-only-progress/check python -W ignore \
    docs/paper/rule-only-rewards/check/todo_list_check.py
```

Slice 3. It ends with `PASS: every edge matches its table; every loop nets to 0` and writes the after
RM texts to `rm/`.

L2.3 calls `deepseek-v4.1-flash` once (key from `.env`) and needs the local embeddings server on the
`.env` port (default 8934); the generated machine can differ between runs. With `E` an empty folder:

```bash
dotenv -f .env run --no-override -- python -W ignore app/main.py generate-larm --mode compiler \
    --environment examples/arm-fm/minigrid-doorkey/environment.md \
    --task "$(cat docs/paper/rule-only-rewards/samples/l1_4-task.txt)" \
    --bundle $E/bundle --embeddings --overwrite --model deepseek-v4.1-flash
sed "s#BUNDLE_DIR#$E/bundle#" docs/paper/rule-only-rewards/samples/l2_3-smoke.yaml > $E/smoke.yaml
python -W ignore app/main.py train-rl --config $E/smoke.yaml --seed 1
python -W ignore app/main.py test-rl --run l2-3-smoke --episodes 10 --seed-base 2000000
```

The machine must carry `ACCEPTING_STATES` and `PENDING_PROMISES`; `test.json` in the run folder has the
success and accept rates. The 33-episode replay of the recorded run is in
`evidence/close/L23-rerun/replay.txt`.

To rebuild the page, edit `data.json` and run `fill.py` of the artifacts skill on it.

## Code

Branch `feat/rule-only-rewards`, base `e0a054a`. Slice 1: progress (`d4df200`), cleanups (`633c3cd`,
`a5ba449`). Slice 2: end judgment (`29cf79f`), tidy-up (`0a933c1`), decision records (`a56bbed`).
Slice 3: the to-do list and the well charge (commit "feat(compiler): score rewards as a to-do list and charge open
items at any end") and its decision records (commit "docs(decisions): record the to-do list rewards and the well
charge").
Files: `app/src/compiler/reward_layer.py`, `rm_format.py`, `reward_machine.py`,
`app/src/config/config.py`, `app/src/arm_fm/runtime.py`, `app/src/arm_fm/environments.py`. Design:
"The end judgment" in `docs/COMPILER_REWARD_DESIGN.md`; decision record
`docs/decisions/arm-fm/rm-execution.md`.

## Appendix: the alarm machine, step by step

A candidate for the thesis appendix; the user decides with the paper agent. The thesis keeps "Reach the goal.
If the key is dropped, pick it up right away." as its before and after. This machine is worth a full reading
because it has every case at once: three loops on the same event, a well, and steps where two or three things
happen together. Task: "When the alarm rings, switch it off at the very next step. Preferably, if the power ever
goes out, run the generator." RM texts: `rm/s2-ex4.txt` (before), `rm/s3-ex4.txt` (after).

### The claim this example backs

The user's claim: with our method, the transitions encode everything that happens in the environment, cover every case, and give a consistent, reliable reward. The reward tells the agent what is good and what is wrong, what it must do, how it should react, and in which order to finish the task while following the rules. A claim like this cannot sit flat in the text without a real example; this machine is that example.

What the machine shows, each point checked by `check/todo_list_check.py`:

- the same event costs the same wherever it happens: the alarm ringing costs -0.1 in u0, u1 and u2;
- fixing it pays the cost back, so every loop nets to 0 and the agent cannot farm reward;
- events that happen at once add up: switching the alarm off as the power goes out pays 0;
- breaking the hard rule always costs more than running out of time in the same state.

What it does not show: that an agent learns better with these rewards (no learning run measures it), or that every task's machine behaves like this one. The broader check found no loop that pays in any of the 65 compiled machines of the corpus.

| State | To-do list | Score | Charged if the episode ends here |
| --- | --- | --- | --- |
| u0 | nothing | 0 | 0 |
| u1 | run the generator (soft) | -0.1 | -0.5 |
| u2 | nothing (the generator ran) | 0 | 0 |
| u3 | switch the alarm off (hard) | -0.1 | -1 |
| u4 | switch the alarm off, run the generator | -0.2 | -1.5 |
| u5 | switch the alarm off (the generator ran) | -0.1 | -1 |
| u6 | the well: a hard rule broke | | ends the episode |

A step pays the change in the score: +0.1 per item crossed off, -0.1 per item added. The three alarm loops
(u0 <-> u3, u2 <-> u5, u1 <-> u4) all pay -0.1 and +0.1; before, they paid -0.3/+0.3, -0.1/+0.1 and 0.

| Step | What happens | List change | Before | After |
| --- | --- | --- | --- | --- |
| u3 -> u1 | alarm off, power goes out | -1 item, +1 item | +0.1 | 0 |
| u3 -> u4 | alarm off, rings again, power goes out | -1 item, +2 items | +0.1 | -0.1 |
| u3 -> u5 | alarm off, rings again, generator on | -1 item, +1 item | +0.2 | 0 |
| u3 -> u2 | alarm off, generator on | -1 item | +0.3 | +0.1 |
| u1 -> u5 | alarm rings, generator on | -1 item, +1 item | +0.1 | 0 |
| u0 -> u4 | alarm rings, power goes out | +2 items | -0.2 | -0.2 |
| u4 -> u2 | alarm off, generator on | -2 items | +0.2 | +0.2 |
| u4 -> u5 | alarm off, rings again, generator on | -2 items, +1 item | +0.1 | +0.1 |

The arrows into the well pay -1 plus what timing out in the state they leave would cost: from u3 -2, from u4
-2.5, from u5 -2 (before, -1 each). Not switching the alarm off is always worse than letting the time run out.
