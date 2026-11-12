# One counted attempt per candidate, the same in both arms

Date: 2026-11-12. Scripted engines, no provider call, no model call. The probe's task is a toy one, so it is
illustrative: no benchmark card was run.

## What it shows

The benchmark gives both arms the same limit (10 attempts) and no retry the other arm lacks. A review of the
card work found that the two pipelines counted differently:

- FARM reran a failed attempt for free, up to 10 times in a row, on any content failure (an invalid
  proposal, clauses that do not compile, malformed critic output). Its worst case, an invalid proposal ten
  times before each rejected candidate, was **110 generator requests for 10 counted attempts**. ARM-FM, which
  counted every failed round, got 10.
- ARM-FM counted a provider outage as a used attempt, and an authentication error too.
- The attempt count in the run's cost stamp was the loop counter, so FARM stamped 1 when the provider never
  answered.

Now **every candidate the generator returns uses one attempt**, whether it is accepted, rejected or unusable.
Only a provider outage (no candidate came back) keeps the attempt number and reruns, at most 10 times in a
row, then ends as a provider error. The stamp counts the candidates that ended in a verdict, so a generator
that never answers stamps 0 in both arms.

| FARM case (limit 10) | Before (`69b64db`): generator requests / counted attempts | After (`a77709b`) |
| --- | --- | --- |
| 10 invalid proposals, then one rejected candidate, on every attempt | **110** / 10 | **10** / 10 |
| every proposal is invalid | 11 / 1 | 10 / 10 |
| invalid proposal and critic rejection alternate | 15 / 10 | 10 / 10 |
| provider is down for good | 11 / 1 | 11 / 0, ends as a provider error |
| authentication error (not retryable) | 1 / 1 | 1 / 0 |
| critic rejects every candidate (control) | 10 / 10 | 10 / 10 |

| ARM-FM case (limit 10) | Before: generator requests / counted attempts | After |
| --- | --- | --- |
| 9 provider outages, then accepted | 10 / 10 | 10 / **1** |
| provider is down for good | 10 / 10, "not accepted within 10 attempts" | 11 / **0**, ends as a provider error |
| authentication error (not retryable) | 10 / 10 | **1** / **0**, ends at once |
| critic rejects every round (control) | 10 / 10 | 10 / 10 |

Rows for a critic that fails (outage or malformed output) are in
[`../critic-outage-retry/`](../critic-outage-retry/README.md); they changed on a later commit.

## The task, formula and machine the probe uses

- Natural-language task (illustrative; the script passes the string `finish`): "Reach the finish."
- LTLf: `F done` (`Existence(done)`). The FARM probe builds no clauses; it feeds a prepared compilation result
  to the pipeline, so only the attempt accounting is exercised.
- Reward Machine, the one the scripted ARM-FM generator returns:
  [interactive graph](graphs/probe-task.html), [SVG](graphs/probe-task.svg).

<details>
<summary>RM text</summary>

```text
REWARD_MACHINE:
STATES: u0, u1
INITIAL_STATE: u0
FINAL_STATES: u1
TRANSITION_FUNCTION:
(u0, done) -> u1
(u0, else) -> u0
(u1, else) -> u1
REWARD_FUNCTION:
(u0, done, u1) -> 1
```

</details>

## Evidence

- `check/before-69b64db.json`: 17 rows on the tree before the card fixes. `check/after-a77709b.json`: the same
  rows on the pipeline freeze. Both with `attempts = 10` and `OUTAGE_RETRIES` (before: `UNCOUNTED_RETRIES`) 10.
- Before is commit `69b64db`; after is `a77709b`. Rows were reproduced on both trees for this entry.

## Files

- `check/f7_limits.py`: the probe. It runs the real `generate_compiler` (FARM) and `generate_baseline_bundle`
  (ARM-FM) against scripted generator and critic engines.
- `check/before-69b64db.json`, `check/after-a77709b.json`; `graphs/` (the probe's machine).

## Rerun

From the repository root, inside `RM_RL_env`. The before tree is a copy of `69b64db`:

```bash
COPY=$(mktemp -d); git archive 69b64db app | tar -x -C "$COPY"
PYTHONPATH="$COPY/app" python -W ignore docs/paper/attempt-counting/check/f7_limits.py "$COPY" before.json
PYTHONPATH=app python -W ignore docs/paper/attempt-counting/check/f7_limits.py . after.json
```

`PYTHONPATH` must point at the `app` of the tree in the first argument (the script does not edit `sys.path`
and stops with "wrong tree loaded" otherwise). Compare `proposal_requests` and `stamp.attempts` (FARM) and `rm_generator_requests` and
`counted_attempt_records` (ARM-FM) row by row. No LLM call.

## Code

`generate_rm.py` (`_Pipeline.generated`, `run_task`), `app/src/arm_fm/generation.py`
(`_Generation.generate_reward_machine`), `OUTAGE_RETRIES` in `app/src/config/config.py`. Commits `fb36d17`
(`feat(benchmark): apply card fixes F1-F7 ...`) and `28ae75e` (`fix(benchmark): guard first-step latch reads
and count every candidate the generator returned`), merged into the wave as `6149c47`. The rule is in
`docs/decisions/arm-fm/task-and-rm-identity.md`.

## Gaps

- Scripted engines only. In the real run of the benchmark the first live check of the 10-attempt budget
  completed on attempt 1, so the 10th round was not seen with a real provider.
- The "before" tree predates the critic-retry fix, so its critic-failure rows mix two changes; the
  `critic-outage-retry` entry holds the isolated comparison.
