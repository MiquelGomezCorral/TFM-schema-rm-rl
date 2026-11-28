# Other LLMs by thinking level (`other-llms-by-level/`), 2026-11-24

First cut, Muse Glimmer 30B, Gemma 4 31B and Qwen3.8 27B (its `none`, `low` and `medium`) added 2026-11-25, then
gpt-oss-120b (3 levels) and Qwen3.5 9B (2 levels, the first small local model) the same day, and last Qwen3.8 `max` and
Llama 3.1 8B Instruct (`none`, the second small local model). Gemma 4 12B (`none`, `high`) and gpt-oss-20b (`low`,
`medium`, `high`) were added 2026-11-26. All 35 rows below are final.

## What it shows

How often FARM generation ends with the right Reward Machine, and how long one machine takes, for each (model, thinking
level), on the benchmark of the thinking-level entry: 46 task cases, 3 runs each, 138 runs per row, the same prompts, the
same scorer and the same accepted alternatives (`also_ok`). The thesis figure is the one of its Figure 6.5: the share
right with 95% Wilson bars against the median seconds per RM on a log x axis, one point per (model, level).
`data/levels.csv` is the one file that figure reads. `figure.html` is a preview of it. Every row is scored against the
final accepted-answer lists, kept in `evidence/cards/` (see "Evidence"): the lists of the repository at `2e62e243`,
including the six answers added on 2026-11-22 (commit `21a3ef98`). Against the frozen lists of the thinking-level
entry, only six rows change: the two Qwen3.5 9B rows (33 and 92 right there, 34 and 95 here), Gemma 4 12B `none` (29
there, 32 here) and gpt-oss-20b `low`, `medium` and `high` (64, 81 and 91 there, 66, 82 and 92 here).

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
| Muse Glimmer 30B | low | 122/138 | 82.0% to 92.7% | 82.1 | yes |
| | medium | 132/138 | 90.8% to 98.0% | 154.85 | yes |
| | high | 133/138 | 91.8% to 98.4% | 229.4 | yes |
| | max | 130/138 | 89.0% to 97.0% | 270.9 | yes |
| Gemma 4 31B | none | 109/138 | 71.5% to 85.0% | 18.45 | yes |
| | high | 132/138 | 90.8% to 98.0% | 168.4 | yes (one record from a first attempt, see "Evidence") |
| Qwen3.8 27B | none | 97/138 | 62.2% to 77.3% | 37.95 | yes (the 6 runs that hit the 3600 s cap were run again on 2026-11-27: 0 timeouts now, see "How each model's time was measured") |
| | low | 133/138 | 91.8% to 98.4% | 128.2 | yes |
| | medium | 135/138 | 93.8% to 99.3% | 155.3 | yes |
| | max | 138/138 | 97.3% to 100.0% | 380.85 | yes (two parts, 79 + 59 runs, see "Evidence") |
| gpt-oss-120b | low | 100/138 | 64.5% to 79.2% | 14.75 | yes |
| | medium | 118/138 | 78.7% to 90.4% | 33.05 | yes |
| | high | 126/138 | 85.4% to 95.0% | 117.35 | yes |
| Qwen3.5 9B (Q4) | none | 34/138 | 18.2% to 32.4% | 14.55 | yes (33 against the frozen answer lists, see "Evidence") |
| | high | 95/138 | 60.7% to 76.0% | 272.3 | yes (92 against the frozen answer lists, see "Evidence") |
| Llama 3.1 8B Instruct (Q5) | none | 7/138 | 2.5% to 10.1% | 11.75 | yes (the 3 runs that hit the 3600 s cap were run again on 2026-11-26: 0 timeouts now, see "How each model's time was measured") |
| Gemma 4 12B (Q4) | none | 32/138 | 16.9% to 30.9% | 71.25 | yes (0 runs hit the 3600 s cap; 29 against the frozen answer lists, see "Evidence") |
| | high | 111/138 | 73.0% to 86.2% | 81.9 | yes (0 runs hit the 3600 s cap) |
| gpt-oss-20b | low | 66/138 | 39.7% to 56.1% | 38.8 | yes (0 runs hit the 3600 s cap; 64 against the frozen answer lists) |
| | medium | 82/138 | 51.1% to 67.2% | 120.8 | yes (0 runs hit the 3600 s cap; 81 against the frozen answer lists) |
| | high | 92/138 | 58.4% to 74.0% | 406.3 | yes (0 runs hit the 3600 s cap; 91 against the frozen answer lists) |

Three models reach 138/138: the production pair at `high` (20.35 s) and `max` (88.1 s), Haiku at `max` (111.2 s) and
Qwen3.8 27B at `max` (380.85 s).
Muse Glimmer 30B reaches none (best 133/138 at `high`). The frontier of the figure (rows no other row beats on both
axes, at least as right and at least as fast) is the pair `none`, Haiku `low`, `medium` and `high`, and the pair `high`:
the pair at `high` is as right as Haiku `max` and faster. No Muse row is on it: each has 8 to 10 rows of the other models
that are at least as right and faster. Muse's times come from a cluster GPU, so the "faster" half is weak (see below).
The pair has more right RMs than Muse at every level they share; the 95% intervals overlap at `medium` and `high`.
Gemma 4 31B has two rows, `none` and `high`: 109/138 at `none` (more than the pair's 105 and Luna's 94, at 18.45 s
against 3.9 and 18.85 s) and 132/138 at `high`. Neither Gemma row is on the frontier: Haiku `low`, `medium` and `high`
and the pair's `low` and `medium` are more right and faster than Gemma `none`; Gemma `high` has 11 rows at least as
right and faster (the pair at four levels, Haiku at four, Luna `high` and `max`, and Muse `medium`, 132/138 at 154.85 s).
Both Gemma times come from a cluster GPU too, so the "faster" half is weak here as well.
Qwen3.8 27B has four final rows: 97/138 at `none` (37.95 s), 133/138 at `low` (128.2 s), 135/138 at `medium` (155.3
s) and 138/138 at `max` (380.85 s, 0 timeouts). No Qwen3.8 row is on the frontier and no existing row leaves it: the
frontier is still the same five rows (the pair `none` and `high`, Haiku `low`, `medium` and `high`; recomputed on all 30
rows). Qwen3.8 `none`
has 13 rows at least as right and faster (the pair at four levels, Haiku at three, Luna `medium`, `high` and `max`,
Gemma `none`, gpt-oss-120b `low` and `medium`; its 97 is fewer than Gemma `none`'s 109 and the pair's 105, at 37.95 s
against 18.45 and 3.9 s). `low` has
9 such rows (the pair `low` to `max`, Haiku `medium`, `high` and `max`, Luna `high` and `max`) and `medium` has 6 (the
pair `medium`, `high` and `max`, Haiku `high` and `max`, Luna `max`). `max` has 3 such rows, all 138/138 and faster (the
pair `high` and `max`, Haiku `max`; 20.35, 88.1 and 111.2 s against 380.85 s), and it is the slowest row of the entry
except gpt-oss-20b `high` (406.3 s). Its times come from a cluster GPU too.
gpt-oss-120b has three final rows: 100/138 at `low` (14.75 s), 118/138 at `medium` (33.05 s) and 126/138 at `high`
(117.35 s); it has no `none` and no `max` (thinking cannot be turned off and its card has three efforts). No row of it is
on the frontier and no existing row leaves it: the frontier is still the same five rows (recomputed on all 30 rows).
`low` has 5 rows at least as right and faster (the pair `none` and `low`, Haiku `low`, `medium` and `high`), `medium` has
8 (the pair `low`, `medium` and `high`, Haiku `low`, `medium` and `high`, Luna `high` and `max`) and `high` has 10 (the
pair `low` to `max`, Haiku `low` to `max`, Luna `high` and `max`). Its times come from 2 cluster GPUs too.
Qwen3.5 9B (Q4) has two final rows: 34/138 at `none` (14.55 s) and 95/138 at `high` (272.3 s). Neither is on the
frontier and no existing row leaves it. `none` has 5 rows at least as right and faster (the pair `none` and `low`,
Haiku `low`, `medium` and `high`), `high` has 25 (counted on all 35 rows, after the Qwen3.8 `none` rerun): every other row except Luna `none` (94/138),
Luna `low` (89/138), Qwen3.8 27B `max` (slower, 380.85 s) and the six small local rows less right than it (its own `none`,
Llama 3.1 8B, Gemma 4 12B `none` and gpt-oss-20b at three levels). At 95/138 it is above Luna `none`, which is faster
(18.85 s). Its times come from one desktop GPU at 2 runs at once, so they compare with no other group
(see "How each model's time was measured").
Llama 3.1 8B Instruct (Q5) has one final row: 7/138 at `none` (2.5% to 10.1%, 11.75 s; 0 runs at the 3600 s cap, 3 were run again); it
does not think, so it has no other level. It is not on the frontier and no existing row leaves it (recomputed on all 30
rows). 3 rows are at least as right and faster (the pair `none`, Haiku `low` and `medium`), and it is the least right
row of the entry (Qwen3.5 9B `none` is next, 34/138). Its times come from one desktop GPU at 1 run at once, so they
compare with the other small local models only.
Gemma 4 12B (Q4) has two final rows: 32/138 at `none` (71.25 s) and 111/138 at `high` (81.9 s); no run of either hit the
3600 s cap. Neither is on the frontier and no existing row leaves it (recomputed on all 35 final rows). `none` has 18 rows
at least as right and faster (the pair at four levels, Haiku at three, Luna at five, Gemma 4 31B `none`, Qwen3.8 27B
`none`, gpt-oss-120b `low` and `medium`, Qwen3.5 9B `none`, gpt-oss-20b `low`); only Llama 3.1 8B (7/138) is less right.
Its median is high for a thinking-off model because 81 of its 138 runs failed (76 after 10 rejected attempts, 5 on a
context-length error) and the median run makes 20 calls. `high` has 9 such rows (the pair `low`, `medium` and `high`, Haiku `low`, `medium` and `high`, Luna
`high` and `max`, gpt-oss-120b `medium`) and 14 rows are less right; it is the most right of the small local models
(Qwen3.5 9B `high` 95, gpt-oss-20b `high` 92). Its times come from one desktop GPU at 2 runs at once.
gpt-oss-20b has three final rows: 66/138 at `low` (38.8 s), 82/138 at `medium` (120.8 s) and 92/138 at `high` (58.4% to
74.0%, 406.3 s). As for gpt-oss-120b it has no `none` and no `max` (thinking cannot be turned off). No row of it is on
the frontier and no existing row leaves it (recomputed on all 35 final rows). `low` has 16 rows at least as right and
faster (the pair `none` to `high`, Haiku `low`, `medium` and `high`, Luna at five levels, Gemma 4 31B `none`,
Qwen3.8 27B `none` (97/138 at 37.95 s against 38.8 s), gpt-oss-120b `low` and `medium`), `medium` has 21 (the pair at five levels, Haiku at four, Luna at five, Muse `low`,
Gemma 4 31B `none`, Qwen3.8 27B `none`, gpt-oss-120b at three levels, Gemma 4 12B `high`) and `high` has 28 (the pair at
five levels, Haiku at four, Luna `none`, `medium`, `high` and `max`, Muse at four levels, Gemma 4 31B `none` and
`high`, Qwen3.8 27B at four levels, gpt-oss-120b at three levels, Qwen3.5 9B `high`, Gemma 4 12B `high`); `high` is the
slowest row of the entry. It is less right than gpt-oss-120b at the three shared levels (66 against 100 at `low`, 82
against 118 at `medium`, 92 against 126 at `high`), but the times are of different machines (one desktop GPU at 2 runs
at once against 2 cluster GPUs at 8).
7 of its 72 not-right runs at `low` failed after 10 rejected attempts and the other 65 were accepted by the critic
loop but scored not right; at `medium` all 138 runs were accepted by the critic loop, 56 of them scored not right.

The production pair is a different arrangement from the other two: DeepSeek V4.1 Flash writes the clauses and GLM 5.3
Flash checks them. For Haiku and Luna one model plays both roles (the critic is the same model named `<model>@critic`,
because the app refuses equal generator and critic names). Haiku has no `none`: Claude Code cannot turn its thinking off
(`CLAUDE_CODE_DISABLE_THINKING`, `MAX_THINKING_TOKENS=0`, `alwaysThinkingEnabled=false` and the adaptive switch all left
it thinking). Luna's `max` is Codex's `xhigh`; Luna accepts `none` (0 reasoning tokens). Muse Glimmer 30B is also one
model for both roles (critic `muse-glimmer-30b@critic`, the same weights, so it checks its own work). It is served by
vLLM on one cluster L40S, quantized to FP8 at load, through the `local` provider; its level goes in the system line
"Reasoning strength: <level>", `max` is `xhigh`, and it has no `none` (its card documents no off switch).
Gemma 4 31B is one model for both roles too (critic `gemma-4-31b@critic`, the same weights, so it checks its own work).
It is served by vLLM on one cluster GPU, quantized to FP8 at load, through the `local` provider. Its card documents one
control, `enable_thinking`, so it has two levels only: `none` is thinking off (median 0 reasoning characters) and `high`
is thinking on (median 3998; `LocalEngine`, `_LOCAL_LEVELS["gemma4"]`).
Qwen3.8 27B is one model for both roles too (critic `qwen3.8-27b@critic`, the same weights, so it checks its own work;
the `gen` and `critic` fields of the records and the `model` field of the call logs say so). It is served by vLLM on one
cluster GPU from the FP8 checkpoint `Qwen/Qwen3.8-27B-FP8` (no load-time quantization), with `--reasoning-parser qwen3`
and `--language-model-only`, through the `local` provider. Its card documents `enable_thinking` and `reasoning_effort`
(`low`, `medium`, `xhigh`), so it has four levels: `none` is thinking off (median 0 reasoning characters), `low` and
`medium` send that effort (medians 3966 and 5142), `max` is `xhigh`; it has no `high` (`_LOCAL_LEVELS["qwen3.8"]`).
gpt-oss-120b is one model for both roles too (critic `gpt-oss-120b@critic`, the same weights, so it checks its own work;
the `gen` and `critic` fields of the records say so). It is served by vLLM on 2 cluster GPUs (tensor parallel 2) from the
MXFP4 weights (60.8 GiB), with `--reasoning-parser openai_gptoss`, through the `local` provider. Its card documents the
efforts `low`, `medium` and `high` and no off switch, so it has those three levels (medians of 1346, 4176 and 17072
reasoning characters; `_LOCAL_LEVELS["gptoss"]`).
Qwen3.5 9B (Q4) is one model for both roles too (critic `qwen3.5:9b-q4_K_M@critic`, the same weights, so it checks its own
work). It is the first small local model: the library tag `qwen3.5:9b-q4_K_M` (4-bit `Q4_K_M` quantization, since the 8-bit
file does not fit the 12 GB GPU) served by a user-space Ollama 0.40.18 on the desktop's RTX 5070, through the `local`
provider with `LOCAL_LLM_SERVER=ollama`. The driver `multi-llm-20261124/tools/small-local-run.sh` runs it at 2 runs at once
(2 Ollama slots), 49152 tokens of context per slot, flash attention and a `q8_0` KV cache, at `nice -n 10`; the model is
fully on the GPU (about 8.4 GB). Its card documents `enable_thinking` only, so it has two levels: `none` is thinking off
and `high` is thinking on (`_LOCAL_LEVELS["qwen3.5"]`; the smoke runs showed no reasoning at `none` and reasoning at
`high`).
Llama 3.1 8B Instruct (Q5) is one model for both roles too (critic `llama3.1:8b-instruct-q5_K_M@critic`, the same
weights, so it checks its own work). It is the second small local model: the library tag `llama3.1:8b-instruct-q5_K_M`
(5-bit `Q5_K_M`) on the same Ollama arrangement as Qwen3.5 9B (49152 tokens of context per slot, flash attention, `q8_0`
KV cache), but with 1 slot, because 2 slots put 22% of the model on the CPU (`small-local-run.sh`). The model does not
think, so it has the one level `none` (`_LOCAL_LEVELS["llama3.1"]` sends no thinking control).
Gemma 4 12B (Q4) is one model for both roles too (critic `gemma4:12b-it-q4_K_M@critic`, the same weights, so it checks
its own work). It is the third small local model: the library tag `gemma4:12b-it-q4_K_M` (4-bit `Q4_K_M`) on the same
Ollama arrangement, with 2 slots (49152 tokens of context per slot, flash attention, `q8_0` KV cache); at the smoke it
was fully on the GPU (about 9.9 GB, `j-small-local-report.md`). Like Gemma 4 31B its card documents `enable_thinking`
only, so it has two levels: `none` is thinking off and `high` is thinking on (`_LOCAL_LEVELS["gemma4"]`, the same key as
the 31B; the smoke runs showed no reasoning at `none` and reasoning at `high`).
gpt-oss-20b is one model for both roles too (critic `gpt-oss:20b@critic`, the same weights, so it checks its own work).
It is the fourth small local model: the library tag `gpt-oss:20b` (MXFP4 weights) on the same Ollama arrangement, with 2
slots. The model is 13 GB and the GPU has 12 GB, so 37.1% of it runs on the CPU (4,880 of 13,141 MiB sit in host memory,
25 layers with 11 overflowing; `ollama ps` leaves out host-mapped weights and shows less) and 62.9% on the GPU (about
9.6 GB of VRAM at the smoke; `small-local-run.sh`), and its times are those of a part-CPU model. Its card documents the efforts
`low`, `medium` and `high` and no off switch, so it has those three levels (`_LOCAL_LEVELS["gptoss"]`, the key of
gpt-oss-120b).

**Caveat, context window.** Gemma was served with `--max-model-len 49152` (`serve_vllm.sbatch` notes about 6 GiB of KV
room on its one GPU), against 65536 for Muse and Qwen3.8; the server's refusal text in the call logs names the limit
("maximum context length is 49152 tokens"). A request longer than that fails, so some of Gemma's misses at `none` come
from the window and not from the model alone: 5 of the 29 wrong runs at `none` ended on a context-length error (3
`declare_proposal` requests, 2 critic requests; all 5 are failed runs, on two cases: `W4a` three times, `W5a` twice),
and 0 of the 6 wrong runs at `high`. No right run had one (counted from the records' `error` and the call logs).
Qwen3.8 had the 65536-token window and still lost 3 of its 41 not-right runs at `none` to it (the case `W4a`, all three
repeats: two critic requests and one `declare_proposal` request; all three are failed runs), against 0 of the 5 at `low`
and 0 of the 3 at `medium`. No right run had one (records' `error` and call logs).
gpt-oss-120b had the 65536-token window and lost 3 runs at each level to it (the case `W4a`, all three repeats, a critic
request each; all are failed runs): 3 of its 38 not-right runs at `low`, 3 of 20 at `medium` and 3 of 12 at `high`.
Qwen3.5 9B had 49152 tokens per Ollama slot and lost 5 of its 104 not-right runs at `none` (4 `declare_proposal` requests
and 1 critic request, on the cases `W4a` twice, `O3`, `W1b` and `O7`) and 1 of its 43 at `high` (a critic request, `W4a`).
No right run of either model had one (counted from the records' `error`).
No record of Qwen3.8 `max` (0 failed runs) or of Llama 3.1 8B (18 failed runs: 15 critic loops and 3 compiler loops; 0
timeouts) has a context-length error (counted from the records' `error`).
Gemma 4 12B had 49152 tokens per Ollama slot and lost 5 of its 106 not-right runs at `none` to it (5 `declare_proposal`
requests, all failed runs, on the cases `W4a` twice and `W5a` three times), against 0 of its 27 at `high`. No record of
gpt-oss-20b (`low`: 7 failed runs, all of them 10 rejected attempts; `medium`: 0 failed runs) has a context-length error.
No right run had one (counted from the records' `error`).

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
- **Cluster models (Muse, Gemma, Qwen3.8):** 8 runs at once against one vLLM server on one cluster GPU (Muse and Gemma:
  L40S, FP8), reached through an SSH tunnel. Muse: the four levels one after the other from 23:28 on 2026-11-24 to 04:11
  on 2026-11-25. Gemma: `none` from 13:20:15 to 13:40:43 and `high` from 13:40:43 to 14:42:56 on 2026-11-25. Qwen3.8 (all
  on 2026-11-25): `none` from 04:43:08 to 06:54:00 (its 6 timed-out runs again on 2026-11-27, 05:12:20 to 05:18:43, see "Timeouts"), `low` from 07:00:26 to 08:02:59 and `medium` from 08:16:40 to
  09:27:56. Qwen3.8 `max` ran in two parts: from 09:50:50 to 11:08 (79 runs; the watcher then lost the cluster and wrote
  `incomplete qwen3.8-27b max n=79` at 11:09:33) and, after a fresh serve at 18:45:55 (cluster job 57283), from 18:45:57
  to 19:47:42 (the other 59 runs; a restart skips finished runs). So a cluster time is the generation speed of that one
  GPU shared by 8 runs, plus the tunnel; it is not
  comparable to the API models' times, nor to the CLI ones. The medians of Muse are 82.1 to 270.9 s, those of Gemma 18.45
  s (`none`, no thinking) and 168.4 s (`high`), those of Qwen3.8 37.95 s (`none`), 128.2 s, 155.3 s and 380.85 s
  (`max`); those of the other models are 3.9 to 111.2 s. No Muse or Gemma run needed a provider repeat
  (`provider_reruns` is 0 in all 552 Muse and 276 Gemma records); in Qwen3.8 the total is 1 in the `none` records and 0
  in `low`, `medium` and `max`.
- **gpt-oss-120b (cluster):** 8 runs at once against vLLM on 2 cluster GPUs, through the same tunnel. All on 2026-11-25:
  `low` from 14:49:32 to 14:58:34, `medium` from 14:59:21 to 15:12:52 and `high` from 15:15:20 to 16:01:44 (watcher log).
  Medians 14.75, 33.05 and 117.35 s; like the other cluster models, its time is that of the GPUs shared by 8 runs plus
  the tunnel. `provider_reruns` is 0 in all 414 records.
- **Qwen3.5 9B (desktop GPU):** 2 runs at once on one RTX 5070 with 12 GB, through a local Ollama (see above), `nice -n
  10` (at the start no training job ran and about 1.2 GB of the VRAM was the desktop's, `j-small-local-report.md`; not
  checked later). `none` from 08:32:52 to 09:38:59 and `high` from 09:38:59 to 15:42:19 on
  2026-11-25 (`small-local.log`). Medians 14.55 and 272.3 s. A desktop GPU at 2 runs at once is neither a cluster GPU at
  8 runs at once nor an API, so these times compare with no other group, and the small local models only with each
  other. `provider_reruns` is 0 in all 276 records.
- **Llama 3.1 8B (desktop GPU):** 1 run at once (1 Ollama slot) on the same RTX 5070 with the same Ollama version, `nice -n 10`.
  `none` from 15:42:23 to 19:28:48 on 2026-11-25 (`small-local.log`: `end llama3.1:8b-instruct-q5_K_M none rc=0` at
  19:28:55). Median 11.75 s. 1 run at once is a different load than the 2 of Qwen3.5 9B, so the two small local models
  compare only roughly. `provider_reruns` is 0 in all 138 records.
- **Gemma 4 12B (desktop GPU):** 2 runs at once on the same RTX 5070, same Ollama and `nice -n 10`. `none` from 19:28:57
  to 21:13:11 and `high` from 21:13:11 to 23:05:46 on 2026-11-25 (`small-local.log`). Medians 71.25 and 81.9 s (the
  longest run: 941.5 s at `none`, 609.8 s at `high`). `provider_reruns` is 0 in all 276 records.
- **gpt-oss-20b (desktop GPU):** 2 runs at once on the same RTX 5070, same Ollama and `nice -n 10`, with 37.1% of the
  model on the CPU. `low` from 23:05:50 on 2026-11-25 to 00:39:18 on 2026-11-26, `medium` from 00:39:18 to 04:30:15 and
  `high` from 04:30:15 to 15:09:10 (`small-local.log`). Medians 38.8, 120.8 and 406.3 s (the longest run: 553.8 s at
  `low`, 1625.8 s at `medium`, 2099.9 s at `high`). `provider_reruns` is 0 in all 414 records.
- **Timeouts.** Outside Qwen3.8 `none` and the first run of Llama 3.1 8B `none`, no run hit the 3600 s cap of the driver (`timeouts=0` on
  every other `end` line of `cluster-watch.log` for the cluster models, gpt-oss-120b and Qwen3.8 `max` included; for
  Qwen3.5 9B, Gemma 4 12B and gpt-oss-20b (`low`, `medium`), no record has the error `timeout 3600s`, no `round.log` has
  a timeout line and every record has a `wall_s`: 0 timeouts at all six levels).
  Llama 3.1 8B `none` had 3 of 138 in its first run (`round.log` and the records' `error` agree: `W4a` r3, `W5b` r1,
  `W5b` r3), all failed runs; the driver's `end` line (11 s) counted them as 0 s. They were run again on 2026-11-26
  with the same code (`tp-multi-llm`, commit `dace1558`), prompts, settings and 3600 s limit, on the study's Ollama
  server with `OLLAMA_GPU_OVERHEAD=2147483648` added (2 GiB of the GPU left free for the trainings running then, which
  made 16 of the 33 layers run on the GPU): `W4a` r3 alone at 22:53 and `W5b` r1 and r3 together at 22:58 (2 runs at
  once on the 1-slot server). All 3 ended accepted by the critic loop (86.9, 271.4 and 249.3 s) and scored not right,
  and they replaced the timed-out records, so the row has 0 timeouts, 7/138 right as before and a median of 11.75 s as
  before (the longest run is now 271.4 s). The first records are kept in
  `.git/agent-memory/plans/farm-final-20261119/llm-timeouts-old/`. Qwen3.8 `none` had 6 of 138 in its first run (`timeouts=6`; `O2` r2, `W3a` r3, `W3b` r2,
  `O7` r2, `G1` r1, `S2` r2), all failed runs. Their call logs end with a call that finished (at most 140 s long) and
  show nothing after it; the cause is not diagnosed here. A killed run's record has no `wall_s`, so `build.py` counted
  it as 3600 s (46.65 s median that way; the first run's `end` line counted them as 0 s and printed 30 s). They were run
  again on 2026-11-27 with the same code (`tp-multi-llm`, commit `dace1558`), prompts, settings, vLLM 0.34.0, server
  flags and 3600 s limit, on cluster job 60004 (one L40S GPU, served from 05:11:59, cancelled by the watcher at 05:18:43;
  the job had 2 CPUs where the study's jobs had 4), the 6 runs at once. All 6 ended accepted by the critic loop (`G1` r1
  26.9 s, `O2` r2 76.1 s, `O7` r2 365.7 s, `S2` r2 28.4 s, `W3a` r3 26.0 s, `W3b` r2 78.3 s); 5 scored right and `S2` r2 not
  right, and they replaced the timed-out records. So the row has 0 timeouts, 97/138 right (92 before) and a median of
  37.95 s (46.65 s before); the longest run is 2099.4 s. The rerun's `end` line says 97 right, 83 first right and 38 s.
  The first records are kept in `.git/agent-memory/plans/farm-final-20261119/llm-timeouts-old/qwen3.8-27b-none/`. Every
  scored record has a `wall_s` (`build.py` stops on a missing one that is not a driver timeout, because it would count as
  0 s).

**Calls per RM.** Counted from `calls`, `attempts_used` and `critic_rejections` in `records/*/`. A run of 2 calls is one
generator call and one critic call, accepted at the first attempt with no rejection (in every level below, all the 2-call
runs are of that kind, except the failed runs that ended on a critic context error after one generator call: 2, 3 and 2
of the 2-call runs of gpt-oss-120b `low`, `medium` and `high`, and 1 each at Qwen3.5 9B `none` and `high`). Luna's
median of 4 at `none`, `low` and `medium` means that at the median the critic rejected the first RM once; at `high` and
`max` the median is 2. Muse's and Gemma's median is 2 at every level. Qwen3.8's is 4 at
`none` (counted over all 138 runs; none has a timeout now) and 2 at `low`, `medium` and `max`.
gpt-oss-120b's median is 2 at the three levels. Qwen3.5 9B's is 4 at `none` (55 of 138 runs have 2 calls) and 2 at `high`.
Llama 3.1 8B's is 8 at `none` (29 of 138 runs have 2 calls; counted over all 138 runs, none has a timeout now). Gemma 4 12B's is 20 at `none` (25 of 138 runs have 2 calls; 76 runs used all 10 attempts and
failed) and 2 at `high`; gpt-oss-20b's is 2 at `low` and at `medium`. In all four, every 2-call run was accepted at the
first attempt with no rejection.

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
| Muse | low | 2 | 133/138 |
| Muse | medium | 2 | 136/138 |
| Muse | high | 2 | 135/138 |
| Muse | max | 2 | 134/138 |
| Gemma | none | 2 | 117/138 |
| Gemma | high | 2 | 133/138 |
| Qwen3.8 | none | 4 | 68/138 |
| Qwen3.8 | low | 2 | 129/138 |
| Qwen3.8 | medium | 2 | 131/138 |
| Qwen3.8 | max | 2 | 137/138 |
| gpt-oss-120b | low | 2 | 97/138 |
| gpt-oss-120b | medium | 2 | 109/138 |
| gpt-oss-120b | high | 2 | 118/138 |
| Qwen3.5 9B | none | 4 | 55/138 |
| Qwen3.5 9B | high | 2 | 115/138 |
| Llama 3.1 8B | none | 8 | 29/138 |
| Gemma 4 12B | none | 20 | 25/138 |
| Gemma 4 12B | high | 2 | 131/138 |
| gpt-oss-20b | low | 2 | 72/138 |
| gpt-oss-20b | medium | 2 | 92/138 |

One line per model (the `timing` column of the data files):

| Model | `timing` | Harness and call path |
|---|---|---|
| DeepSeek V4.1 Flash + GLM 5.3 Flash | `opencode-api-stream` | The app's own OpenCode engine: one streamed chat completion over HTTPS per request to OpenCode (`https://opencode.ai/zen/v1`, Go plan), `reasoning_effort` set to the level, JSON-schema response format, 120 s idle timeout, no client retries (`provider_engines.py`, `OpenCodeEngine`). Two models, one per role. No process starts. |
| Haiku 5.5 | `claude-cli-oneshot` | `experiments/dev/model-compare/cli_engine.py`: one `claude --print --effort <level>` process per request, in an empty temporary folder, with tools, MCP servers, slash commands and session saving off; the JSON schema goes in the prompt. One model for both roles. |
| GPT-6 Luna | `codex-cli-oneshot` | The same adapter: one `codex exec -c model_reasoning_effort=<level>` process per request, with Codex's context blocks and tools switched off. One model for both roles. |
| Muse Glimmer 30B | `local-api-stream` | `LocalEngine` (`provider_engines.py`, commit `dace1558`, merged to main by `624b5503`): one streamed chat completion per request to the vLLM server on the cluster, 600 s idle timeout, no client retries, thinking set per model family. One model for both roles. The call logs (`provider.reasoning_sent`, `resends`) agree. |
| Gemma 4 31B | `local-api-stream` | The same engine and server arrangement as Muse; thinking on or off through `enable_thinking`, 49152 tokens of context (see the caveat above). One model for both roles. |
| Qwen3.8 27B | `local-api-stream` | The same engine and server arrangement as Muse; thinking per `_LOCAL_LEVELS["qwen3.8"]` (`enable_thinking` and `reasoning_effort`), 65536 tokens of context. One model for both roles. |
| gpt-oss-120b | `local-api-stream` | The same engine and server arrangement as Muse, on 2 cluster GPUs; the effort goes in the request (`_LOCAL_LEVELS["gptoss"]`), 65536 tokens of context. One model for both roles. |
| Qwen3.5 9B (Q4) | `local-api-stream` | The same engine against an Ollama server on the desktop GPU (`LOCAL_LLM_SERVER=ollama`), thinking through `enable_thinking` (`_LOCAL_LEVELS["qwen3.5"]`), 49152 tokens of context per slot, 2 runs at once. One model for both roles. |
| Llama 3.1 8B Instruct (Q5) | `local-api-stream` | The same engine and Ollama server on the desktop GPU, no thinking control (`_LOCAL_LEVELS["llama3.1"]`), 49152 tokens of context per slot, 1 run at once (1 slot). One model for both roles. |
| Gemma 4 12B (Q4) | `local-api-stream` | The same engine and Ollama server on the desktop GPU, thinking through `enable_thinking` (`_LOCAL_LEVELS["gemma4"]`), 49152 tokens of context per slot, 2 runs at once. One model for both roles. |
| gpt-oss-20b | `local-api-stream` | The same engine and Ollama server on the desktop GPU, the effort goes in the request (`_LOCAL_LEVELS["gptoss"]`), 49152 tokens of context per slot, 2 runs at once, 37.1% of the model on the CPU. One model for both roles. |

**The routes do not measure the same thing.** The production pair pays one network round trip per request. Every
Haiku or Luna request starts a vendor CLI process, which has its own start-up, its own harness and its own rate limits.
For Haiku the logs give the size: over 330 requests of `haiku-low`, a request's `wall_s` exceeds the `duration_ms` Claude
Code reports for itself by a median of 1.15 s (10th to 90th percentile 0.93 to 1.32 s); a run makes two or more
requests, so about 2.3 s or more of a Haiku `low` run is start-up (measured on `low` only). Codex reports no such time,
so Luna's overhead is not measured. Also the production pair uses two different models and the others one, so what a "level" times differs. Compare a
model's own levels with each other first; across models, the x position includes the route.

## Evidence

- **The cards.** `build.py` rescores the run folders with the scorer of `level-benchmark-freeze/check`
  (`arm_stats.arm`) against the final accepted-answer lists in `evidence/cards/` (it sets `cases.CARD_DIR` to that
  folder), counts the right machines, takes the Wilson interval (`scipy` `binomtest`, as the final-results builder)
  and the median `wall_s`. `evidence/cards/` holds the `tasks.json` of the suites `base`, `box-carry`, `complex`,
  `forced-start`, `shop` and `templates` as at commit `2e62e243` of the repository (`experiments/benchmark/<suite>/`;
  the answers are the final ones, with the six added on 2026-11-22, commit `21a3ef98`) and the `local-soft` one from
  `level-benchmark-freeze/evidence/cards/local-soft/` (the loop's local soft cards `S1` to `S4`, which are in no
  suite of `experiments/`). The entry therefore reads no card outside its own folder. The thinking-level entry keeps
  its frozen copy, from before those six answers (main `e6c3acb` plus the local soft cards).
- **Against the frozen lists, rows that change.** Among the cards of the benchmark's cases, only `W2a`
  (`tpl-precedence-1-nogoal`) has a different answer list (`also_ok` and `notes`; checked card by card). Qwen3.5 9B
  `none` goes from 33 to 34 right and `high` from 92 to 95 (the driver's own counts); Gemma 4 12B `none` from 29 to 32,
  gpt-oss-20b `low` from 64 to 66, `medium` from 81 to 82 and `high` from 91 to 92 (per-case letters compared, `W2a` is
  the only case that differs: `WWW` to `RRR`, `WRW` to `RRR`, `RWR` to `RRR` and, at `high`, `WRR` to `RRR`); no other
  row of `data/levels.csv` changes. In the `arm_stats.py` columns that the data files do not carry, gpt-oss-120b `medium`
  has false alarms of 12/130 (11/129 before) and `high` 117 first right and 8/134 (116 and 7/133 before).
  A row is `final` only with 138 runs scored and an `end <round>:` line for it in the driver log (the watcher log
  `cluster-watch.log` for the cluster models; for the small local models the line `end <tag> <level> rc=0` of
  `small-local.log`).
- The production rows equal `level-benchmark-freeze/stats.md` and `results-figures/data/thinking.csv` (105, 134, 136,
  138 and 138 right; medians 3.9, 12.05, 17.6, 20.35 and 88.1 s; same Wilson bounds).
- The nine final Haiku and Luna rows equal the driver's own counts in `multi-llm-20261124/c-subs-run.log` (132, 134, 137,
  138, 94, 89, 100, 134 and 137 of 138): 0 differ. The driver scored with the cards of main, which are the lists this
  entry now scores with; scored with the frozen lists (only `W2a` differs, in `also_ok` and notes) the totals are equal
  too. The engine review (`b-review-report.md`, item 5) found 0 verdict changes between the two card sets on these
  folders.
- The four final Muse rows equal the watcher's own `end` lines in `multi-llm-20261124/cluster-watch.log` (122, 132, 133
  and 130 right of 138; medians 82, 155, 229 and 271 s): 0 differ. `arm_stats.py` run on the run folders
  (`until-fix/runs/multillm-muse-glimmer-30b-<level>/L`) and on the copied records prints the same right counts and
  medians.
- The two final Gemma rows equal the watcher's own `end` lines in `cluster-watch.log` (109 and 132 right of 138; medians
  18 and 168 s; 112/138 and 130/138 first right): 0 differ. `arm_stats.py` on the run folders
  (`until-fix/runs/multillm-gemma-4-31b-<level>/L`) and on the copied records prints the same counts and medians.
- **Which records are counted for Gemma.** `build.py` reads one folder per level, `multillm-gemma-4-31b-<level>/L`, 138
  `*-r*.json` records each (`status` accepted or failed). The smoke runs live in separate folders
  (`multillm-smoke-gemma-4-31b-<level>`) and are never read. The first `none` attempt was only a smoke: the watcher
  ignored it at 13:09:30 (a call failed with the context-length error, which the smoke check counted as a failed
  control; fixed in `tools/level_checks.py`, see `l-smoke-context-report.md`) and went on to `high` at 13:16:21. It was
  restarted at 13:20 with the fix and ran the real `none` from 13:20:15 and `high` again from 13:40:43.
  - `none`: the 138 records have file times 13:21:08 to 13:40:37, all after the final run's start at 13:20:15 (`round.log`
    has one `start` line, 13:20:15); none is older.
  - `high`: the folder has two `start` lines (13:16:21 and 13:40:43). One record, `O2-r2` (finished 13:19:43, 196.5 s,
    right), comes from the first attempt; the restart skipped it as finished (`round.log`: "L O2 r2 kept", and
    `multi-llm-bench.sh`: "A restart skips finished runs"). It is the same model, server, level and code, so it is
    counted: 132/138. Without it the row would be 131/137.
- The Qwen3.8 rows `none`, `low` and `medium` equal the watcher's own `end` lines in `cluster-watch.log` (97, 133 and 135 right of 138;
  83, 125 and 128 first right; the `none` line is the one of the rerun of 2026-11-27, the first run's line said 92 and 82
  because 6 timed-out runs were still in it, see "Timeouts" above): 0 differ in the right counts. The medians equal them
  for `none` (38 s), `low` (128) and `medium` (155). `arm_stats.py` on the run folders
  (`until-fix/runs/multillm-qwen3.8-27b-<level>/L`) and on the copied records prints the same right counts and medians.
- **Which records are counted for Qwen3.8 `none`, `low` and `medium`.** `build.py` reads one folder per level, `multillm-qwen3.8-27b-<level>/L`, 138
  `*-r*.json` records each; the smoke runs are in separate folders (`multillm-smoke-qwen3.8-27b-<level>`) and are never
  read. `low` and `medium` have one `start` line in their `round.log` and every record's file time falls after it: `low`
  07:01:51 to 08:02:57 (start 07:00:26), `medium` 08:18:29 to 09:27:51 (start 08:16:40); no record is from an earlier
  attempt. `none` has three `start` lines: 04:43:08 on 2026-11-25 (the study run; 132 kept records, file times 04:43:26 to
  05:57:52), and on 2026-11-27 05:12:01 (stopped after 19 s, "no model server ... timed out", done 05:12:20) and 05:12:20
  (the rerun: the 6 records `G1` r1, `O2` r2, `O7` r2, `S2` r2, `W3a` r3 and `W3b` r2, file times 05:12:55 to 05:18:34,
  which replaced the 6 timed-out ones). The rerun is the same model, level, serve script and code as the first run, and a
  restart skips finished runs (as for Gemma `high`, above), so the 138 are counted; no kept record is from an attempt that
  timed out.
- The three final gpt-oss-120b rows equal the watcher's own `end` lines in `cluster-watch.log` (100, 118 and 126 right
  of 138; medians 15, 33 and 117 s; 87/138, 109/138 and 117/138 first right): 0 differ in the right counts and the
  medians. `arm_stats.py` on the copied records with `CARD_DIR` set to `evidence/cards` prints 87, 109 and 117 first
  right and false alarms of 23/123, 12/130 and 8/134, as the `end` lines. With the frozen lists (its default `CARD_DIR`)
  it printed 116 first right at `high` and 11/129 and 7/133 at `medium` and `high`: the difference is the `W2a` card
  (see below) and sits in first attempts only, not in the final verdicts.
- **The Qwen3.5 9B rows equal the driver's own count, and the frozen lists did not.** The driver line of
  `small-local.log` says 34 right at `none` and 95 at `high`, which are the rows here. Scored with the frozen lists
  (an earlier version of this entry) they were 33 and 92. The driver's scorer reads the cards of main
  (`until-fix/tools/`), the frozen copy differs from them in the `also_ok` list of `W2a` only (see the Haiku and Luna
  line above). Run both ways on the same records, every other case gets the same letters; `W2a` gets `WRR` where the
  frozen lists give `WRW` at `none` (1 run) and `RRR` where they give `WWW` at `high` (3 runs). Neither row is on the
  frontier either way. The medians equal the driver's (15 and 272 s).
- **Which records are counted for gpt-oss-120b and Qwen3.5 9B.** `build.py` reads one folder per level, 138 `*-r*.json`
  records each; the smoke runs are in separate folders (`multillm-smoke-...`) and are never read. Each `round.log` has
  one `start` line and every record's file time falls after it: gpt-oss `low` 14:50:00 to 14:58:27 (start 14:49:32),
  `medium` 15:00:01 to 15:12:47 (start 14:59:21), `high` 15:18:03 to 16:01:39 (start 15:15:20); Qwen3.5 `none` 08:33:21 to
  09:38:51 (start 08:32:52), `high` 09:45:42 to 15:42:14 (start 09:38:59). No record is from an earlier attempt, none
  is missing a `wall_s` and none has the error `timeout 3600s`. A Qwen3.5 level is final with 138 scored records and its
  `end qwen3.5:9b-q4_K_M <level> rc=0` line in `small-local.log` (09:38:59 and 15:42:19).
- **The Qwen3.8 `max` and Llama 3.1 8B `none` rows equal the driver's own counts.** The `end` line of
  `cluster-watch.log` says 138 right of 138 for Qwen3.8 `max` (137 first right, median 381 s, `timeouts=0`) and the `end`
  line of `small-local.log` says 7 right of 138 for Llama (7 first right, 31/38 false alarms, median 11 s): 0 differ.
  The Llama median is 11.4 s there because the driver counted its 3 timeouts as 0 s; they were run again (see
  "Timeouts") and the median is now 11.75 s here and 12 s in `arm_stats.py` (rounded). Scored with the
  frozen lists both rows keep their right counts (138 and 7; Llama's false alarms are 30/37 there, 31/38 here); `W2a`
  is the only card that differs. `arm_stats.py` on the copied records prints the same right counts.
- **Which records are counted for Qwen3.8 `max` and Llama 3.1 8B.** `build.py` reads one folder per level, 138
  `*-r*.json` records each; the smoke runs are in separate folders and are never read. Llama's `round.log` has three
  `start` lines: 15:42:23 (the study run: records' file times 15:42:43 to 19:28:46) and the two reruns of 2026-11-26,
  22:53:21 (`W4a` r3) and 22:58:56 (`W5b` r1 and r3), which replaced the 3 timed-out records; no other record is from
  an earlier attempt.
  Qwen3.8 `max` has records from two attempts. `round.log` has many `start` lines, but only two ran anything: the one at
  09:50:50 (79 records, file times 09:54:43 to 11:08:11) and the one at 18:45:57 (the other 59, 18:48:07 to 19:47:36);
  the ones between 11:09:27 and 12:39:12 found 79 finished runs and ended within seconds (the watcher wrote
  `incomplete ... n=79` each time). Both attempts use the same model, level, serve script and code, and a restart
  skips finished runs (as for Gemma `high`, above), so the 138 are counted. No record is missing a `wall_s` (the 3
  timeouts of Llama and the 6 of Qwen3.8 `none` were replaced), and Qwen3.8 `max` has none.
- **The four small local rows of 2026-11-26 equal the driver's own counts.** The `end` lines of `small-local.log` say 32
  and 111 right of 138 for Gemma 4 12B `none` and `high` (75 and 114 first right; medians 71 and 82 s) and 66 and 82
  right for gpt-oss-20b `low` and `medium` (46 and 68 first right; medians 39 and 121 s): 0 differ. The driver scores with
  the cards of main, as the final lists here do, so the frozen lists give lower counts for three of the rows (see
  "Against the frozen lists"). The medians have no timeouts to disagree on (no run hit the 3600 s cap).
- **Which records are counted for Gemma 4 12B and gpt-oss-20b.** `build.py` reads one folder per level, 138 `*-r*.json`
  records each; the smoke runs are in separate folders and are never read. Each `round.log` has one `start` line and every
  record's file time falls after it: Gemma `none` 19:31:42 to 21:13:00 (start 19:28:57), `high` 21:16:26 to 23:05:41 (start
  21:13:11); gpt-oss-20b `low` 23:07:30 to 00:39:10 (start 23:05:50), `medium` 00:44:32 to 04:30:08 (start 00:39:18). No
  record is from an earlier attempt and none is missing a `wall_s`. Each level is final with its `end <tag> <level> rc=0`
  line in `small-local.log` (21:13:11, 23:05:46, 00:39:18 and 04:30:15).
- `arm_stats.py` run on `records/` with `CARD_DIR=docs/paper/other-llms-by-level/evidence/cards` reproduces the final
  Haiku, Luna, Muse, Gemma, Qwen3.8, gpt-oss-120b, Qwen3.5, Llama, Gemma 4 12B and gpt-oss-20b rows (its call-log
  columns print 0, since no call log is copied; its `none` median for Qwen3.8 is 38 s (the first run's driver printed 30 s) and its Llama median 12
  s (the driver's first run printed 11)). Without `CARD_DIR` it reads the frozen lists and the Qwen3.5 rows come out 33 and 92, Gemma 4 12B `none` 29 and
  gpt-oss-20b `low`, `medium` and `high` 64, 81 and 91.

## Files

- `data/levels.csv` and `data/levels.json`: `model, level, right, n, rate, wilson_low, wilson_high, median_s_per_rm,
  final, timing, source`. `source` is the folder the row was counted from. Not final rows would be in the file too
  (today none: all 35 are final); the figure leaves them out and `results-figures/records.py` reads the final ones only.
- `figure.html`: open it from disk. Plain SVG, no script; hover a point for its numbers; the table under it lists every
  row, the not final ones greyed.
- `records/<model>-<level>/`: the 138 run records (`<case>-r<k>.json`) of each final Haiku, Luna, cluster-model and small
  local model level (`muse-glimmer-30b-<level>`, `gemma-4-31b-<level>`, `qwen3.8-27b-<level>`, `gpt-oss-120b-<level>`,
  `qwen3.5-9b-q4_K_M-<level>`, `llama3.1-8b-instruct-q5_K_M-<level>`, `gemma4-12b-it-q4_K_M-<level>`,
  `gpt-oss-20b-<level>`), copied by `build.py`. The production records stay in `level-benchmark-freeze/records/`.
  Not copied: the call logs (`*.calls.jsonl`, 25 to 75 MB a level) and the work folders; they stay in the run folders.
- `evidence/cards/<suite>/tasks.json`: the final accepted-answer lists the rows are scored against, 7 suites (see
  "Evidence" for the source commit and the `local-soft` file). `build.py` points the scorer at this folder.
- `check/build.py` (recount, data files, record copy) and `check/figure.py` (the page). A new cluster model is one line
  of the `CLUSTER_MODELS` table of `build.py` (slug, display name, levels); a new small local model is one line of the
  `SMALL_LOCAL_MODELS` table (Ollama tag, display name, levels), final when its `end <tag> <level> rc=0` line is in
  `small-local.log`. `figure.py` takes its models from the data (it has 11 series colours: a twelfth model needs one more in each list).

## Rerun

No model call. From the repository root, in `RM_RL_env`:

```bash
env CC_ROOT=$PWD PYTHONPATH=app:docs/paper/level-benchmark-freeze/check python -P -W ignore docs/paper/other-llms-by-level/check/build.py
python -I docs/paper/other-llms-by-level/check/figure.py
```

`build.py` reads the plan folder `.git/agent-memory/plans/farm-final-20261119/multi-llm-20261124/` (its logs
`cluster-watch.log`, `small-local.log` and `c-subs-run.log`) and the run folders
`.git/agent-memory/plans/farm-final-20261119/until-fix/runs/` (they exist in the main checkout only) and, when a new
level has finished, copies its records here. If a driver is writing a record at that
moment it stops on a half-written file: run it again. To recount the kept records alone, with the final lists (without
`CARD_DIR` the scorer reads the frozen ones):
`env CC_ROOT=$PWD CARD_DIR=docs/paper/other-llms-by-level/evidence/cards PYTHONPATH=app python -W ignore docs/paper/level-benchmark-freeze/check/arm_stats.py haiku-low=docs/paper/other-llms-by-level/records/haiku-low ...`.

## Code and run folders

- Haiku and Luna runs: drivers `multi-llm-20261124/tools/subs_driver.py` (4 runs at once each, 3600 s cap) and
  `sweep-snapshot/tools/{run_arms.py,gen_one.py}`, main `7a005656` plus the uncommitted
  `experiments/dev/model-compare/cli_engine.py` (level maps, `@critic`, usage guard). Run folders
  `multi-llm-20261124/runs/subs-<model>-<level>/`, log `multi-llm-20261124/c-subs-run.log`.
- Production runs: code freeze `809dfe3`, runs on main `e6c3acb`; see `level-benchmark-freeze/`.
- Muse Glimmer 30B runs: engine commit `dace1558` (`LocalEngine`, now in main), watcher `multi-llm-20261124/tools/` with
  its log `multi-llm-20261124/cluster-watch.log`, server script `multi-llm-20261124/serve_vllm.sbatch` (vLLM 0.34, FP8,
  one L40S, 65536 tokens of context, `--reasoning-parser muse_glimmer`), bench driver
  `multi-llm-20261124/tools/multi-llm-bench.sh` (8 runs at once), run folders
  `until-fix/runs/multillm-muse-glimmer-30b-<level>/L/`.
- Gemma 4 31B runs: the same engine, watcher and bench driver as Muse; server script `serve_vllm.sbatch` (vLLM 0.34, FP8,
  one GPU, 49152 tokens of context, `--reasoning-parser gemma4`); run folders
  `until-fix/runs/multillm-gemma-4-31b-<level>/L/` for `none` and `high`.
- Qwen3.8 27B runs: the same engine, watcher and bench driver; server script `serve_vllm.sbatch` (vLLM 0.34, the FP8
  checkpoint `Qwen/Qwen3.8-27B-FP8`, one GPU, 65536 tokens of context, `--reasoning-parser qwen3 --language-model-only`);
  run folders `until-fix/runs/multillm-qwen3.8-27b-<level>/L/` for `none`, `low`, `medium` and `max`.
- gpt-oss-120b runs: the same engine, watcher and bench driver; server script `serve_vllm.sbatch` (vLLM 0.34, MXFP4
  weights of `openai/gpt-oss-120b`, 2 GPUs, 65536 tokens of context, `--reasoning-parser openai_gptoss`); run folders
  `until-fix/runs/multillm-gpt-oss-120b-<level>/L/` for `low`, `medium` and `high`.
- Qwen3.5 9B runs: the same engine and bench driver (`multi-llm-bench.sh`), started by
  `multi-llm-20261124/tools/small-local-run.sh` (user-space Ollama 0.40.18, tag `qwen3.5:9b-q4_K_M`, 2 slots, 49152
  tokens of context per slot, flash attention, `q8_0` KV cache), log `multi-llm-20261124/small-local.log`; run folders
  `until-fix/runs/multillm-qwen3.5-9b-q4_K_M-<level>/L/` for `none` and `high`.
- Llama 3.1 8B Instruct runs: the same engine, bench driver and `small-local-run.sh` (tag `llama3.1:8b-instruct-q5_K_M`,
  1 slot, otherwise the same Ollama settings); run folder `until-fix/runs/multillm-llama3.1-8b-instruct-q5_K_M-none/L/`.
- Gemma 4 12B runs: the same engine, bench driver and `small-local-run.sh` (tag `gemma4:12b-it-q4_K_M`, 2 slots,
  otherwise the same Ollama settings); run folders `until-fix/runs/multillm-gemma4-12b-it-q4_K_M-<level>/L/` for `none`
  and `high`.
- gpt-oss-20b runs: the same engine, bench driver and `small-local-run.sh` (tag `gpt-oss:20b`, 2 slots, otherwise the
  same Ollama settings); run folders `until-fix/runs/multillm-gpt-oss-20b-<level>/L/` for `low`, `medium` and `high`.

## Missing

- Qwen3.8 has no `high` (see above).
- Haiku `none`, Muse `none` and gpt-oss `none` (120b and 20b): not available (see above). The two Gemma models and
  Qwen3.5 have no `low`, `medium` or `max` (their cards have one switch only); gpt-oss has no `none` or `max`.
- Limits: the 46 cases were picked around past mistakes, not sampled; one model pair for the production rows; each Haiku,
  Luna, Muse, Gemma, Qwen3.8, gpt-oss, Qwen3.5 or Llama row has the model checking its own work; 3 runs per case; Muse,
  Gemma 4 31B, Qwen3.8 and gpt-oss-120b times are from the cluster at 8 runs at once, those of Qwen3.5, Gemma 4 12B and
  gpt-oss-20b from one desktop GPU at 2 runs at once (gpt-oss-20b with 37.1% of the model on the CPU) and those of
  Llama from the same GPU at 1 run at once; Gemma 4 31B's context window was 49152 tokens and the small local models'
  49152 per slot (see the caveat above); no Qwen3.8 `none` or Llama `none` run is counted at the 3600 s cap (the 6 and the 3 that hit it were run again, see
  "Timeouts"); Qwen3.8 `max` has records from two attempts (see "Evidence").
