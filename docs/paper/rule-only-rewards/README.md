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
the well (-1, the episode ends), a broken soft rule pays -0.5 when it breaks. Running away from the
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
- With two hard promises open at the end the charge is -2, more than breaking a hard rule on the last
  step (-1). Disclosed on the page, not changed.

## What it shows

The result page of the rule-only rewards work, with the idea above as its first section. A task made
only of rules has no goal, so its Reward Machine had no final state and paid almost nothing; every
episode lost the same flat -0.5 at the time limit, kept rules or not. Two changes fix that:

- **Slice 1, progress:** +0.1 per step toward a state where no rule is waiting, -0.1 per step away.
- **Slice 2, end judgment:** when the environment ends the episode, the open promises are charged at
  values the RM text carries (`HARD_FAILED_REWARD: -1`, `SOFT_FAILED_REWARD: -0.5`), in place of the
  flat -0.5. An episode that ends in an accepting state is a success.

Machines with a final state and author bundles keep their text, rewards and flat -0.5; PPO and DQN are
unchanged. The page then shows the seven final live tests, the before and after machines of Slice 1,
five Slice 2 examples and the generated bundle (each with its task, LTLf and RM text), the review
findings, what was disclosed and not changed, and the open follow-ups.

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
- `graphs/`: 15 RM graphs, interactive HTML and SVG (the window task, Slice 1 before and after, the five
  Slice 2 examples, the L2.3 bundle). `rm/`: their RM texts.
- `check/window_check.py`, `check/window_check.txt`: the window task and its output.
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

It ends with `PASS: every total matches; idling with two hard promises open costs more than the well`.

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
Files: `app/src/compiler/reward_layer.py`, `rm_format.py`, `reward_machine.py`,
`app/src/config/config.py`, `app/src/arm_fm/runtime.py`, `app/src/arm_fm/environments.py`. Design:
"The end judgment" in `docs/COMPILER_REWARD_DESIGN.md`; decision record
`docs/decisions/arm-fm/rm-execution.md`.
