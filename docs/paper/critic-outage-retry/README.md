# A critic outage no longer multiplies generator requests

Date: 2026-11-12. Scripted engines, no provider call, no model call. The probe's task is a toy one,
so it is illustrative: no benchmark card was run.

## What it shows

Before the fix, a failed critic request (provider outage, or critic output that cannot be parsed)
restarted the attempt: the generator was asked again and the attempt number did not move. In the FARM
worst case, ten outages before every rejection, that is **110 generator requests for 10 counted
attempts**. ARM-FM gets 10 in the same setting (overnight log, 13:12 and 20:20 rows). The benchmark's rule
is the same attempt limit for both arms, with no retries the other arm lacks, so this broke it.

After the fix, the failed request is repeated on the **same candidate**, up to 10 repeats (11 requests).
Generation does not restart and no new generator request is made. The same case now takes **10 generator
requests for 10 counted attempts**, and the 110 critic requests all land on those 10 candidates.

| FARM case (limit 10) | Before: generator requests / critic requests / counted attempts | After |
| --- | --- | --- |
| 10 critic outages, then one rejection, on every attempt | 110 / 110 / 10 | **10** / 110 / 10 |
| 9 critic outages, then accepted | 10 / 10 / 1 | **1** / 10 / 1 |
| critic is down for good | 11 / 11 / 0 | **1** / 11 / 1, ends with the critic error |
| critic output malformed every time | 10 / 10 / 10 | **1** / 11 / 1, ends with the critic error |
| critic rejects every candidate (control) | 10 / 10 / 10 | 10 / 10 / 10 |

ARM-FM, same script:

| ARM-FM case (limit 10) | Before: generator requests / critic requests / counted attempt records | After |
| --- | --- | --- |
| critic is down for good | 11 / 11 / 0 records, `RetryableEngineError` | **1** / 11 / 1 record, `CriticUnavailableError` |
| critic rejects every round (control) | 10 / 10 / 10 | 10 / 10 / 10 |

Rejections are untouched: a critic that says no still costs one attempt. A provider outage on the
**generator** still reruns without using an attempt, bounded by the same 10 (rows `9 provider outages,
then accepted` and `provider is down for good` are equal before and after).

The probe has no ARM-FM row for "10 critic outages, then a rejection, every round", so the ARM-FM figure of 10
is the log's, not this probe's. The strong review of the fix reproduced that case in both pipelines (see Gaps).

## The task, formula and machine the probe uses

- Natural-language task (illustrative; the script passes the string `finish`): "Reach the finish."
- LTLf: `F done` (the clause `Existence(done)`). The FARM probe builds no clauses; it feeds a prepared
  compilation result to the pipeline, so only the attempt accounting is exercised.
- Reward Machine, the one the scripted ARM-FM generator returns (`+1` when `done` holds):
  [interactive graph](graphs/probe-task.html) (drag a state, click an edge), [SVG](graphs/probe-task.svg).

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

The graph was drawn with `render-rm --html` from `graphs/probe-task.rm.txt`.

## Evidence

- `check/before-fb36d17.json`: 17 rows (11 FARM, 6 ARM-FM) on the tree before the fix.
- `check/after-a77709b.json`: the same 17 rows on the tree after it.
- Before is commit `fb36d17`, the card-fix branch before it merged the fix. After is `a77709b`, the
  pipeline freeze on `main`. Both runs use `attempts = 10` and `OUTAGE_RETRIES = 10`.

## Files

- `check/f7_limits.py`: the probe. It patches the generator and the critic with scripted engines and runs
  the real `generate_compiler` (FARM) and `generate_baseline_bundle` (ARM-FM).
- `check/before-fb36d17.json`, `check/after-a77709b.json`: its rows.
- `graphs/`: the probe's machine as HTML, SVG and RM text.

## Rerun

From the repository root, inside `RM_RL_env`. The before tree is a copy of `fb36d17`:

```bash
COPY=$(mktemp -d); git archive fb36d17 app | tar -x -C "$COPY"
PYTHONPATH="$COPY/app" python -W ignore docs/paper/critic-outage-retry/check/f7_limits.py "$COPY" before.json
PYTHONPATH=app python -W ignore docs/paper/critic-outage-retry/check/f7_limits.py . after.json
```

`PYTHONPATH` must point at the `app` of the tree in the first argument (the script does not edit `sys.path`
and stops with "wrong tree loaded" otherwise). Compare the case `10 critic outages, then one rejection, every attempt`: `proposal_requests` (generator requests) 110 before,
10 after; `critic_requests` 110 in both. No LLM call.

## Code

`retry_critic` and `CriticUnavailableError` in `app/src/engines/errors.py`; `_review_candidate` in
`app/scripts/generate_rm.py`; `_critic` in `app/src/arm_fm/generation.py`. Fix commit `9611837`
(`fix(generation): retry a failed critic request on the same candidate in FARM and ARM-FM`), merged into
`main` as `7949c1d`. The rule is in `docs/decisions/arm-fm/task-and-rm-identity.md`.

## Gaps

- The probe uses scripted engines. The fix also ran live (6 runs, generator `deepseek-v4.1-flash`, critic
  `glm-5.3-flash`, the first two critic requests made to fail); that log is not copied here.
- ARM-FM "10 outages, then a rejection, every round" is not a row of this probe. The strong review
  reported it as closed (10 generator requests, 110 critic requests, both pipelines) from its own script.
