# Other LLMs by thinking level (`other-llms-by-level/`), 2026-11-24

First cut. All 14 rows below are final; the cluster models and the small local models are not run yet (see "Missing").

## What it shows

How often FARM generation ends with the right Reward Machine, and how long one machine takes, for each (model, thinking
level), on the benchmark of the thinking-level entry: 46 task cases, 3 runs each, 138 runs per row, the same prompts, the
same scorer and the same accepted alternatives (`also_ok`). The thesis figure is the one of its Figure 6.5: the share
right with 95% Wilson bars against the median seconds per RM on a log x axis, one point per (model, level).
`data/levels.csv` is the one file that figure reads. `figure.html` is a preview of it.

| Model | Level | Right | 95% Wilson | Median s per RM | Final |
|---|---|---|---|---|---|
| DeepSeek V4.1 Flash + GLM 5.3 Flash | none | 105/138 | 68.3% to 82.4% | 3.9 | yes |
| | low | 134/138 | 92.8% to 98.9% | 12.05 | yes |
| | medium | 136/138 | 94.9% to 99.6% | 17.6 | yes |
| | high | 138/138 | 97.3% to 100.0% | 20.35 | yes |
| | max | 138/138 | 97.3% to 100.0% | 88.1 | yes |
| Haiku 5.5 | low | 132/138 | 90.8% to 98.0% | 10.35 | yes |
| | medium | 134/138 | 92.8% to 98.9% | 11.4 | yes |
| | high | 137/138 | 96.0% to 99.9% | 14.1 | yes |
| | max | 138/138 | 97.3% to 100.0% | 111.2 | yes (two parts, 37 + 101 runs) |
| GPT-6 Luna | none | 94/138 | 59.9% to 75.3% | 18.85 | yes |
| | low | 89/138 | 56.2% to 72.0% | 18.15 | yes |
| | medium | 100/138 | 64.5% to 79.2% | 19.75 | yes |
| | high | 134/138 | 92.8% to 98.9% | 21.7 | yes (rebuilt 2026-11-24 23:00) |
| | max | 137/138 | 96.0% to 99.9% | 32.1 | yes |

Two models reach 138/138: the production pair at `high` (20.35 s) and `max` (88.1 s), and Haiku at `max` (111.2 s). The
frontier of the figure does not change: the pair at `high` is as right as Haiku `max` and faster.

The production pair is a different arrangement from the other two: DeepSeek V4.1 Flash writes the clauses and GLM 5.3
Flash checks them. For Haiku and Luna one model plays both roles (the critic is the same model named `<model>@critic`,
because the app refuses equal generator and critic names). Haiku has no `none`: Claude Code cannot turn its thinking off
(`CLAUDE_CODE_DISABLE_THINKING`, `MAX_THINKING_TOKENS=0`, `alwaysThinkingEnabled=false` and the adaptive switch all left
it thinking). Luna's `max` is Codex's `xhigh`; Luna accepts `none` (0 reasoning tokens).

## How each model's time was measured

`median_s_per_rm` is the median of `wall_s` over the level's records, for every model. `wall_s` is written by
`gen_one.py` (plan folder `multi-llm-20261124/sweep-snapshot/tools/`, the same file as `until-fix/tools/gen_one.py`
today): `time.monotonic()` taken just before `generate_rm(...)` and read just after it. So one "second per RM" is the
wall-clock time of one whole generation run:

- **Inside:** every generator request and every critic request of the run, with the reruns after a rejection (up to 10
  attempts); the provider repeats of a transient HTTP 400 (1 s wait each, `generic_engine.py:246`); the compiler steps
  (clauses to LTLf, MONA, the reward layer); a failed run counts too (its time until the loop gave up).
- **Outside:** Python start and imports, loading the card, the wait for a free slot of the driver's thread pool, and the
  quota gate of the Haiku and Luna driver (it runs before a run starts). A run killed by a usage limit is deleted and
  run again, so only the rerun's time is in the median (Luna medium dropped 4 runs that way at 22:14; the production
  `none` level had 5 runs stopped on HTTP 429 and run again). Haiku `max` stopped at 37 runs on the weekly quota and
  resumed at 23:14 for the other 101 (to 00:04 on 2026-11-25).
- **Queueing and parallel waits:** the provider's or the server's own queue is inside, because it happens during a
  request. Runs go in parallel on one machine, so CPU use of the other runs is inside too. Production ran 8 runs at once
  beside 12 to 23 RL trainings. Haiku and Luna ran 4 at once each, with overlapping drivers (see the driver log), so up
  to 8 together, beside training jobs. The root's check-ins in `.git/agent-memory/plans/farm-final-20261119/plan.md`
  counted 18 training runs at 20:47, 16 at 21:49, 11 and then 18 at 22:19, and 18 at 22:48 (2026-11-24); they are
  snapshots, not a continuous record. Haiku ran from 20:57 to 21:57 and again from 23:14 to 00:04 (beside 12 to 16
  trainings), and Luna from 20:57 to 23:22. At 21:18 another worker's local CPU model also used about 11 cores.
- No run hit the 3600 s cap of the driver, and every scored record has a `wall_s` (`build.py` stops otherwise: a record
  without one would count as 0 s).

**Calls per RM.** Counted from `calls`, `attempts_used` and `critic_rejections` in `records/*/`. A run of 2 calls is one
generator call and one critic call, accepted at the first attempt with no rejection (in every level below, all the 2-call
runs are of that kind). Luna's median of 4 at `none`, `low` and `medium` means that at the median the critic rejected the
first RM once; at `high` and `max` the median is 2.

| Model | Level | Median calls | Runs with 2 calls |
|---|---|---|---|
| Haiku | low | 2 | 115/138 |
| Haiku | medium | 2 | 125/138 |
| Haiku | high | 2 | 131/138 |
| Haiku | max | 2 | 137/138 |
| Luna | none | 4 | 64/138 |
| Luna | low | 4 | 63/138 |
| Luna | medium | 4 | 59/138 |
| Luna | high | 2 | 129/138 |
| Luna | max | 2 | 128/138 |

One line per model (the `timing` column of the data files):

| Model | `timing` | Harness and call path |
|---|---|---|
| DeepSeek V4.1 Flash + GLM 5.3 Flash | `opencode-api-stream` | The app's own OpenCode engine: one streamed chat completion over HTTPS per request to OpenCode (`https://opencode.ai/zen/v1`, Go plan), `reasoning_effort` set to the level, JSON-schema response format, 120 s idle timeout, no client retries (`provider_engines.py`, `OpenCodeEngine`). Two models, one per role. No process starts. |
| Haiku 5.5 | `claude-cli-oneshot` | `experiments/dev/model-compare/cli_engine.py`: one `claude --print --effort <level>` process per request, in an empty temporary folder, with tools, MCP servers, slash commands and session saving off; the JSON schema goes in the prompt. One model for both roles. |
| GPT-6 Luna | `codex-cli-oneshot` | The same adapter: one `codex exec -c model_reasoning_effort=<level>` process per request, with Codex's context blocks and tools switched off. One model for both roles. |
| Later local and cluster models | `local-api-stream` (planned) | `LocalEngine` of branch `exp/multi-llm`: one streamed chat completion per request to a vLLM or Ollama server, 600 s idle timeout, thinking set per model family. Not in the data yet; confirm against the run files when the first row exists. |

**The routes do not measure the same thing.** The production pair pays one network round trip per request. Every
Haiku or Luna request starts a vendor CLI process, which has its own start-up, its own harness and its own rate limits.
For Haiku the logs give the size: over 330 requests of `haiku-low`, a request's `wall_s` exceeds the `duration_ms` Claude
Code reports for itself by a median of 1.15 s (10th to 90th percentile 0.93 to 1.32 s); a run makes two or more
requests, so about 2.3 s or more of a Haiku `low` run is start-up (measured on `low` only). Codex reports no such time,
so Luna's overhead is not measured. Also the production pair uses two different models and the others one, so what a "level" times differs. Compare a
model's own levels with each other first; across models, the x position includes the route.

## Evidence

- `build.py` rescores the run folders with the scorer of `level-benchmark-freeze/check` (`arm_stats.arm`) against the
  cards of `level-benchmark-freeze/evidence/cards` (main `e6c3acb` plus the local soft cards), counts the right
  machines, takes the Wilson interval (`scipy` `binomtest`, as the final-results builder) and the median `wall_s`.
  A row is `final` only with 138 runs scored and an `end <round>:` line for it in the driver log.
- The production rows equal `level-benchmark-freeze/stats.md` and `results-figures/data/thinking.csv` (105, 134, 136,
  138 and 138 right; medians 3.9, 12.05, 17.6, 20.35 and 88.1 s; same Wilson bounds).
- The nine final Haiku and Luna rows equal the driver's own counts in `multi-llm-20261124/c-subs-run.log` (132, 134, 137,
  138, 94, 89, 100, 134 and 137 of 138): 0 differ. The driver scored with the cards of main (only `W2a` differs from the level-bench
  cards, in `also_ok` and notes); this entry scores with the level-bench cards; the totals are equal. The engine review
  (`b-review-report.md`, item 5) found 0 verdict changes between the two card sets on these folders.
- `arm_stats.py` run on `records/` reproduces the final Haiku and Luna rows (its call-log columns print 0, since no call
  log is copied).

## Files

- `data/levels.csv` and `data/levels.json`: `model, level, right, n, rate, wilson_low, wilson_high, median_s_per_rm,
  final, timing, source`. `source` is the folder the row was counted from. Not final rows are in the file; the figure
  leaves them out.
- `figure.html`: open it from disk. Plain SVG, no script; hover a point for its numbers; the table under it lists every
  row, the not final ones greyed.
- `records/<model>-<level>/`: the 138 run records (`<case>-r<k>.json`) of each final Haiku and Luna level, copied by
  `build.py`. The production records stay in `level-benchmark-freeze/records/`. Not copied: the call logs
  (`*.calls.jsonl`, 25 to 75 MB a level) and the work folders; they stay in the plan folder run folders.
- `check/build.py` (recount, data files, record copy) and `check/figure.py` (the page).

## Rerun

No model call. From the repository root, in `RM_RL_env`:

```bash
env CC_ROOT=$PWD PYTHONPATH=app:docs/paper/level-benchmark-freeze/check python -P -W ignore docs/paper/other-llms-by-level/check/build.py
python -I docs/paper/other-llms-by-level/check/figure.py
```

`build.py` reads the plan folder `.git/agent-memory/plans/farm-final-20261119/multi-llm-20261124/` (it exists in the main
checkout only) and, when a new level has finished, copies its records here. If a driver is writing a record at that
moment it stops on a half-written file: run it again. To recount the kept records alone:
`env CC_ROOT=$PWD PYTHONPATH=app python -W ignore docs/paper/level-benchmark-freeze/check/arm_stats.py haiku-low=docs/paper/other-llms-by-level/records/haiku-low ...`.

## Code and run folders

- Haiku and Luna runs: drivers `multi-llm-20261124/tools/subs_driver.py` (4 runs at once each, 3600 s cap) and
  `sweep-snapshot/tools/{run_arms.py,gen_one.py}`, main `7a005656` plus the uncommitted
  `experiments/dev/model-compare/cli_engine.py` (level maps, `@critic`, usage guard). Run folders
  `multi-llm-20261124/runs/subs-<model>-<level>/`, log `multi-llm-20261124/c-subs-run.log`.
- Production runs: code freeze `809dfe3`, runs on main `e6c3acb`; see `level-benchmark-freeze/`.
- Later local models: engine commit `dace1558` on branch `exp/multi-llm` (not merged), driver
  `multi-llm-20261124/tools/multi-llm-bench.sh`.

## Missing

- The four cluster models (Qwen3.8, Gemma 4, Muse Glimmer, gpt-oss): no run yet; they wait for a cluster GPU.
- The small local models: no run yet; they wait for the local GPU after the training runs.
- Haiku `none`: not available (see above).
- Limits: the 46 cases were picked around past mistakes, not sampled; one model pair for the production rows; each Haiku
  or Luna row has the model checking its own work; 3 runs per case.
