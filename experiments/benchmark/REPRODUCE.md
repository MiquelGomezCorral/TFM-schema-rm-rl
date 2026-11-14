# Reproducing the benchmark

Every command runs from the repository root inside the `RM_RL_env` Conda environment
(Python 3.13) with `PYTHONPATH=app`. The shell scripts under `experiments/benchmark/scripts/` set
`PYTHONPATH` themselves and take the interpreter from `PYTHON` (default `python`); the Python
scripts there (section 6) need `PYTHONPATH=app` on the command line.

## 1. Setup

1. Environment: `RM_RL_env` with `requirements.txt` and this package installed editably
   (`uv pip install -r requirements.txt` and `uv pip install -e .`). MONA must be on `PATH` or named
   by `MONA_EXECUTABLE`.
2. Provider variables in `.env` (the prefix is the uppercase `LLM_PROVIDER`, for example `OPENCODE`):
   `<PREFIX>_API_KEY`, `<PREFIX>_MODEL_GENERATOR` = `deepseek-v4.1-flash` and `<PREFIX>_MODEL_CRITIC` =
   `glm-5.3-flash`. Generation uses only these two models.
3. Embedding server. Embeddings come from a local `llama-server` on `LLAMA_SERVER_PORT`
   (default 8934). Without it `generate-suite` ends bundles as `incomplete` with `Connection refused`.
   `python app/app.py` prints the exact command at launch; its shape is

   ```text
   $LLAMA_SERVER_BIN -m $LLAMA_SERVER_MODEL --host 127.0.0.1 --port 8934 --embedding --pooling mean \
     --alias nomic-embed-text --n-gpu-layers 99 --ctx-size 2048
   ```

   `LLAMA_SERVER_BIN` and `LLAMA_SERVER_MODEL` (a plain nomic-embed-text GGUF) come from `.env`.
   Start it once and leave it running; the scripts never start or stop it.

## 2. Generation

Task cards live in `experiments/benchmark/<suite>/tasks.json` (`env.description`, `task`,
`paraphrases`). Smoke first, then everything:

```bash
bash experiments/benchmark/scripts/generate.sh --suite smoke --dry-run   # list the commands
bash experiments/benchmark/scripts/generate.sh --suite smoke             # 3 cards x 2 arms, capped
bash experiments/benchmark/scripts/generate.sh --dry-run                 # the whole plan
```

The script runs the closed set, then every suite for both arms (the `pilot` suite for FARM only),
then `ablate-rm` for the ablation cards. Everything but `smoke` is refused while
`experiments/benchmark/prompt-budget.md` is undecided: the file is missing, has a line starting
`decision: pending`, or has no line starting `decision:`. Each step is a
`python app/main.py generate-suite --tasks <file> --arm farm|arm-fm --output <dir>` call, one per
suite and arm, with `--paraphrases` (which also covers the base wordings) except for `smoke`. The
closed-set pass is its own `generate-suite` call per suite and arm with its own cap; the cards it
completes are skipped by that suite's later call:

- Per card, one `generate-larm --mode compiler` (FARM) or `--mode arm-fm --arm-fm-critic` (ARM-FM)
  child process; bundle folder `<dir>/<card-id>/`, paraphrase k at `<card-id>~p<k>`.
- Both arms get the same counted Reward Machine budget: `--attempts 10` (`RM_ATTEMPTS` in
  `app/scripts/generate_suite.py`). In both, every new candidate counts (accepted, rejected by the
  critic, or invalid); a provider outage counts nothing and reruns the round, 10 times in a row at
  most (`Configuration.OUTAGE_RETRIES`), then the card ends as a provider error. ARM-FM
  labeling and state descriptions keep their three tries and FARM's tagging keeps its own limit.
  A bundle records the limit in `effective_settings.max_attempts` (the Reward Machine stage's,
  in both arms).
- A card keeps the limit it was generated with: `complete` and `pipeline-failed` cards are
  skipped on a rerun, so start a new output folder when the limit changes. The bundle's
  `effective_settings.max_attempts` shows the limit it ran with.
- Beside each folder: `<card-id>.status.json` (`status`, `reason`, `calls`, `wall_time_s`, `log`) and
  `<card-id>.log`. `repair-labeling` finishes a repaired ARM-FM bundle whose generation stopped at
  labeling (descriptions, embeddings): its status turns `complete` and gains `generation_status`,
  `generation_reason` and `labeling_repaired_by`; count generation successes from
  `generation_status` when it is there (`evaluate-larm` does: a finished bundle stays a generation
  failure there).
- Embeddings run afterwards, one bundle at a time, with `embed-larm --embedding-server`.
- Caps: `--parallel` (default 10), `--max-calls` and `--deadline-min` stop launching new cards;
  cards already running finish, so the call count can pass the cap by up to `--parallel` cards.
  A cap holds per `generate-suite` call, not for the whole `generate.sh` run: each suite and arm
  starts its own count. Only the requests of `generate-larm` runs made by that call count, and
  only when the run rewrote the bundle's `raw_responses.json` (a run that saved nothing adds none,
  and neither does a card that waits just for embeddings). Each card prints one line, including
  `not launched (cap or deadline)` for the ones left out. `calls` in a status counts the per-call
  records in the bundle's `raw_responses.json`, so it may show a previous run's total; failed
  cards of both arms keep their records.
- Each status file is written as soon as its card finishes generating and again after its
  embedding, so an interrupted call keeps the statuses of the cards it finished.

Statuses and what a rerun does:

| Status | Meaning | Rerun |
| --- | --- | --- |
| `complete` | every stage and `embeddings.json` | skipped |
| `pipeline-failed` | Reward Machine attempts exhausted (10 in the benchmark) or a stage rejected | skipped; `--retry-failed` runs it again |
| `provider-error` | connection, timeout, quota or server error | runs again |
| `incomplete` | a stage file is missing, embeddings are pending, or the run crashed before writing a bundle | runs again; a bundle with generation done only embeds |

Known gap: `generate-larm` saves a bundle only at the end of a run and has no stage resume, so an
`incomplete` card that needs generation runs again whole, not just its missing stages. A run
killed mid-save leaves a new `manifest.json`; with `--overwrite`, files of an earlier run stay
beside it. Either way the card reads `pipeline-failed`.

A run is a `provider-error` when its final error text carries an OpenAI-SDK network or HTTP
failure in the log tail or in the last failed attempt of the ARM-FM path: connection loss
(`Connection error`, `APIConnectionError`, `Connection refused`), timeouts (`Request timed out`,
HTTP 408), quota and rate limits (402, 429), auth and permission (401, 403; this provider reports an
exhausted quota that way), a sticky 400 (seen in earlier benchmark runs) and server errors (5xx).
Any other failure that left a bundle is `pipeline-failed`. The match is a heuristic on error text.

### Stamp and per-call records

Each bundle's `manifest.json`, failed bundles included, holds `provenance["stamp"]`: `commit`,
`dirty` (any change under `app/`, untracked files included), `generator_model`, `critic_model`,
`reasoning`, `attempts`, `critic_interventions`, `retries`, `wall_time_s`, `provisional`. A value
the pipeline does not report is `null`; a FARM failure bundle has `null` `critic_interventions`
and `retries`, because its labeling attempts are lost with the run. If git cannot tell, `commit`
and `dirty` are `null` and `provisional` is true. `provisional` is true unless `main` is checked
out and nothing under `app/` changed (the dirty check covers `app/`).
`raw_responses.json` adds one record per request sent to the provider,
`{stage, role, model_requested, model_reported}`; `model_reported` is the model named in the
provider's reply and `null` when the provider names none. A model that refuses reasoning `none`
gets it again as `low`: that is two requests, and the refused one has `model_reported` `null`.
`attempts` count the same in both arms: every new Reward Machine candidate (accepted, rejected by
the critic, or invalid) is one, up to the same limit (`effective_settings.max_attempts`, 10 in the
benchmark). `retries` still differ, so do not compare them: FARM `retries` are reruns after provider
outages and failed tagging requests (11 failed tries in a row make 10 retries and end the run as a
provider error); ARM-FM `retries` are the rounds that failed on their content, and its provider
outages are rerun the same bounded way without a record. A provider that never answers leaves
`attempts` 0 in both arms.

### Cross-critic

```bash
python app/main.py cross-critic --bundles <dir>/arm-fm --critic farm   [--max-calls N]
python app/main.py cross-critic --bundles <dir>/farm   --critic arm-fm [--max-calls N]
```

The other pipeline's critic (`glm-5.3-flash`) judges each machine and writes `cross_critic.json`,
the only file it adds, into the bundle: verdict, flags, the critic's `raw_reply` (`raw_reply_path`
stays `null`) and `judged_sha256`, the identity of what was judged: the bundle's task and machine
text, the environment file as the critic reads it, the critic model and the direction. A bundle
is skipped only when its file holds the current identity; otherwise the old file is removed and
the bundle is judged again. The summary counts only verdicts with the current identity and prints
the others on a `stale` line. A bundle with no machine is skipped and keeps its old file, which
the summary reports as stale. With no bundle this critic judges the command prints `error: ...`
to stderr and exits 1. The two critics read different inputs (see each file's `information_note`), so the two
directions are reported apart and never pooled.

## 3. Training and evaluation

Runs expand from each suite's `runs.yaml`; `run-suite` and `aggregate-suite` and the wrapper scripts
`experiments/benchmark/scripts/train.sh` and `experiments/benchmark/scripts/evaluate.sh` come from the
runs slice. The `runs.yaml` key `only` is a list of card ids or the path of a JSON card file whose
ids are used: the ablation suite reads its cards from `complex/tasks.json` and takes its 3 ids from
`complex/ablation.json`.

In order: `run-suite --suite <runs.yaml> --dry-run`, then without `--dry-run`, then
`test-rl --judge` over the finished runs, then `aggregate-suite --suite <runs.yaml> --output <dir>`.

An ablation variant whose manifest marks it a no-op (`effective_settings.ablation.no_op`: the switch
changes nothing in that machine) is listed `no-data` with that reason and is not trained. The
`none` control, which `ablate-rm` also marks no-op, stays eligible.

<!-- seeds: the target is three seeds [1, 2, 3]; the committed runs.yaml files carry seed 1. -->

Learner calibrations (disclosed, not tuned per arm): see `experiments/benchmark/configs/dqn.yaml`
(`double_q: true`, gamma 0.95, `learning_starts` 20000, `end_e` 0.05, `batch_size` 128,
`buffer_size` 1000000) and `experiments/benchmark/configs/ppo.yaml` (CleanRL MiniGrid values: lr
2.5e-4, 8 envs, 128 steps, 4 minibatches, 4 epochs, clip 0.1, entropy 0.01, value 0.5, GAE 0.95,
gamma 0.99, greedy evaluation). RM arms set `time_limit_penalty: 0.0`.

Time-limit asymmetry: FARM machines charge open items at any end of the episode, ARM-FM machines
get 0 at the time limit. Read cross-arm return differences with that in mind.

## 4. Outputs

| Path | Content |
| --- | --- |
| `experiments/benchmark/<suite>/bundles/<arm>/<card-id>/` | bundle: manifest with stamp, machine, labeling, descriptions, embeddings, attempts, per-call records |
| `experiments/benchmark/<suite>/bundles/<arm>/<card-id>.{status.json,log}` | generation status and log |
| `experiments/benchmark/ablation/bundles/<card-id>/off-<switch>/` | ablation machines |
| `outputs/runs/<exp_name>/` | one folder per training run, with `resources.json` and `summary.json` |
| `--output <dir>` of `aggregate-suite` | `results.csv`, `results.json` |

Smoke and test output goes to `outputs/wave-tests/` and is never committed.

## 5. Metrics

Generation (from the stamps): attempts, critic interventions, retries, wall time, calls. Training
(from `aggregate-suite`): run status, judged success, environment success, hard and soft breaks,
open items at the end (hard and soft clauses together; judged success, breaks and open items are
means over the test episodes), steps to first environment success (`n/a` when the environment
reward does not match the task), evaluation success over the last three evaluation points,
environment return, RM return (within an arm only), episode length, wall time, peak RSS, and the
`machine-wrong` flag.

## 6. Testing-program runbook

The steps that follow section 2's generation, in the order they ran. Each has one command, what it
reads, what it writes, and how to retry it. `<suite>` is `base`, `complex`, `templates`, `pilot`
(FARM only) or `box-carry`. A command that calls a provider runs through
`dotenv -f .env run --no-override --` (shown once here, in front of the command); the embedding
server of section 1 must answer for every step that writes embeddings. Every command is safe to
rerun unless its step says otherwise. Scripts under `experiments/benchmark/scripts/` print a usage
header with `--help`.

`regenerate-labeling`, `repair-labeling` and `generation-table` read the folder that **holds the arm
folders** (`experiments/benchmark/<suite>/bundles`, or `experiments/benchmark` for `--root`). Pointing
them at `.../bundles/farm` finds no bundle. `restore-farm` is the exception: it takes the FARM folder.

### 6.1 Restore FARM bundles that lost their machine

```bash
python app/main.py restore-farm --bundles experiments/benchmark/<suite>/bundles/farm
```

Needed only for bundles made before `generate-larm` kept accepted steps: a FARM run that failed at
labeling or descriptions after the critic accepted a machine saved a bundle with no machine. A bundle
made by today's `generate.sh` already keeps it. The command reads `<card>.status.json`, `<card>.log`
and the bundle's manifest, rebuilds the machine from the log's clauses (FL-AT, MONA), and writes it
into the bundle with its descriptions, the failed stage and `provenance.restored_from_log`. It
refuses a machine that does not equal the log's accepted text byte for byte. The status file stays
`pipeline-failed` with a reason naming the stage; a bundle that was `provider-error` becomes
`pipeline-failed` and keeps the old status as `original_status`, so `repair-labeling` can finish it.
The "labeling tries" of a restored bundle are `unknown`, and `generation-table` leaves them out of its
mean. Retry: run it again. A restored bundle is no longer a failure bundle and is skipped. `--only
<name> ...` restores the named bundles; a named bundle that cannot be restored is an error (exit 1).

### 6.2 Regenerate FARM labeling

`regenerate-labeling` runs every arm under the folder it is given, so give it a folder that holds only
FARM: a one-arm view of symlinks.

```bash
mkdir -p outputs/view/<suite> && ln -sfn "$PWD/experiments/benchmark/<suite>/bundles/farm" outputs/view/<suite>/farm
dotenv -f .env run --no-override -- python app/main.py regenerate-labeling \
    --bundles outputs/view/<suite> --parallel 4
```

For each bundle whose machine a critic accepted, it runs the generation labeling loop again with the
bundle's own models (only the small pair). The machine does not change. It writes the new
`labeling.py` and attempts into the bundle and the old labeling, its attempts and the outcome into
`<card>.labeling_regen.json` beside the folder; the first sidecar's `previous` is kept on every rerun.
`--only <card-id> ...` limits the run (a card id also matches its `~p<k>` paraphrases). Retry once:
run the same command again. A bundle whose sidecar is `accepted` for the same machine is skipped, a
`failed` or `pending` one runs again, and a provider failure ends the command with an error after
the other bundles ran. A bundle whose loop fails again keeps its old labeling (its tries are only in
the sidecar). `--parallel` is safe since the machine rebuild runs under one lock (FL-AT's BDD parser
keeps global state); before that, one process per card family was needed.

### 6.3 Check and repair labeling

```bash
python app/main.py repair-labeling --traces experiments/benchmark/<suite>/traces \
    --bundles experiments/benchmark/<suite>/bundles --check-only --parallel 10
dotenv -f .env run --no-override -- python app/main.py repair-labeling \
    --traces experiments/benchmark/<suite>/traces --bundles experiments/benchmark/<suite>/bundles --parallel 10
```

The first call checks each bundle's labeling against the trace bank (`trace-bank`, section 6.6),
classes it (`missing`, `load`, `crash`, `wrong`, `ok`) and writes `<card>.labeling_check.json` beside
the folder; it asks no model. The second repairs the failures with the bundle's own small generator,
and finishes a bundle whose generation stopped at labeling (descriptions, embeddings) and rewrites
the status as in section 2. Retry: run it again; it also finishes bundles repaired by an earlier run
and resumes one that stopped half way. A bundle the loop leaves `unfixed` is for an agent to edit by
hand; a later run checks the edited labeling and marks it `fixed-by-agent`. `--only <card-id> ...`
limits it.

### 6.4 Generation table

```bash
python app/main.py generation-table --root experiments/benchmark \
    --output outputs/tables/generation-table.json > outputs/tables/generation-table.md
```

Reads the files beside every bundle under the root (`attempts.json`, the manifest, the card log, the
labeling-check record, the regeneration sidecar, the `restored_from_log` mark) and prints, per arm and
suite, the Reward Machines accepted out of all bundles and their mean tries, the labelings accepted
at generation out of those that reached labeling and their mean tries, the labelings ok after repair
and the mean repair rounds, and the bundles restored from a log. It writes the JSON and the Markdown
only where you send them; `mkdir -p outputs/tables` first. Retry: run it again; it changes no bundle.

### 6.5 Check the machines: too simple, and ready to train

```bash
PYTHONPATH=app python experiments/benchmark/scripts/check_too_simple.py --output outputs/tables/too-simple.json
PYTHONPATH=app python experiments/benchmark/scripts/ready_list.py --output outputs/tables
```

`check_too_simple.py` runs the judge's `machine_too_simple` on every bundle's machine and lists the
flagged ones: the start state is final, or a final state is reached from it by walking only `else`
transitions and always-true guards. A flagged machine is the judge's call, not an error. `--suite
<name> ...` limits it, and `--start-labels` also evaluates the bundle's own labeling on the
just-reset environment for seeds 1 to 20, as the judge does, and walks the machine holding that
valuation (it needs the card in `<suite>/tasks.json`). `ready_list.py` loads and
validates every bundle the way training does (`validate(require_complete=True)`) and writes
`ready-list.md` (per card) and `ready-list.json` (per bundle, with the reason a bundle is not ready).
Both only read; rerun them whenever bundles change.

### 6.6 The box-carry suite

Task cards in `experiments/benchmark/box-carry/tasks.json`; the suite trains on `runs.yaml` there.

```bash
python app/main.py trace-bank --tasks experiments/benchmark/box-carry/tasks.json \
    --output experiments/benchmark/box-carry/traces
dotenv -f .env run --no-override -- python app/main.py generate-suite \
    --tasks experiments/benchmark/box-carry/tasks.json --arm arm-fm \
    --output experiments/benchmark/box-carry/bundles/arm-fm --paraphrases --parallel 10
dotenv -f .env run --no-override -- python app/main.py generate-suite \
    --tasks experiments/benchmark/box-carry/tasks.json --arm farm \
    --output experiments/benchmark/box-carry/bundles/farm --paraphrases --parallel 10
dotenv -f .env run --no-override -- python app/main.py repair-labeling \
    --traces experiments/benchmark/box-carry/traces --bundles experiments/benchmark/box-carry/bundles
PYTHONPATH=app python experiments/benchmark/scripts/check_too_simple.py --suite box-carry \
    --start-labels --output outputs/tables/box-carry-too-simple.json
PYTHONPATH=app python experiments/benchmark/scripts/ready_list.py --suite box-carry --output outputs/tables
python app/main.py run-suite --suite experiments/benchmark/box-carry/runs.yaml --dry-run
```

`trace-bank` runs each card's plans on its environment and writes the bank `repair-labeling` checks
against. `generate-suite` is section 2's call for one suite and arm: it skips `complete` bundles on a
rerun and needs the embedding server. The last command prints one line per run (`start`, `share`,
`skip`, `no-data`) and writes nothing. Retry: run the step that failed again; each one skips finished
work.

### 6.7 Ablation rebuild

```bash
dotenv -f .env run --no-override -- env PYTHONPATH=app python experiments/benchmark/scripts/build_ablation.py \
    cx-rules-only cx-goal-one-rule cx-goal-many-rules
```

Runs `ablate-rm` on `complex/bundles/farm/<card>` for each reward switch in `OFF_PARTS` (`progress`,
`well`, `soft_break`, `soft_pending`, `end_judgment`, `recurrent_soft_penalty`) and writes
`ablation/bundles/<card>/off-<switch>/`. Then it checks each one against its source and prints one
line each: `labeling.py` byte-equal, loads and validates complete, not too simple, the text changed
unless the manifest marks the switch a no-op, descriptions and embeddings remade only when the states
or transitions changed (in practice `recurrent_soft_penalty`), and the manifest names the switch. Exit 1 if a build or a check failed. Only
`recurrent_soft_penalty` calls a model (it writes the state descriptions again) and the embedding server; leave it out with
`--variants progress well soft_break soft_pending end_judgment` to work with no provider. Retry: run
it again; an existing `off-<switch>` folder is kept, so delete the one to rebuild. `--check-only`
checks without building.

### 6.8 Training schedule: pass 2

Placeholder. Training goes through `run-suite --suite <runs.yaml> --parallel N` (section 3), and a
scheduler that starts each suite in order will be described here in pass 2. Until then, train a suite
with the commands of section 3 and come back to section 6.9 when its runs finish.

### 6.9 Judge finished runs, and judge old ones again

```bash
PYTHONPATH=app python experiments/benchmark/scripts/judge_runs.py                       # list, change nothing
PYTHONPATH=app python experiments/benchmark/scripts/judge_runs.py --rejudge \
    --results outputs/judge/results.jsonl --logs outputs/judge/logs
```

The first call lists every `seed*` folder under `outputs/runs` with its state (`finished`, `training`,
`archived`) and judge format (`new`, `old`, `none`), and marks the ones that need a judge. The second
judges them: it copies an existing `judge.json` to `judge.v1.json` (an existing `judge.v1.json` is
never overwritten), then runs `test-rl --run <folder> --episodes 100 --judge <experiment>/card.json`
from this checkout, two folders at a time with two threads each and only while 8 GB of memory is
available. It skips a run that is still training, already judged in the new format, or being judged by
another `test-rl`. A failed judge is retried once and recorded as `failed` in `--results`. Retry:
run the same command; a run already in the new format is skipped, so only the failed ones run again.
`--runs-root` points at another runs folder (a missing one counts as empty), `--min-age` (minutes,
default 10) holds back a run with no `judge.json` until its summary is that old, because the training
run may still judge it itself. `--results` is written only when a folder was handled (no folder to
judge, no file; `results_table.py` skips a `--results` file that is missing), and a judge that waits
for memory says so once.

### 6.10 Shared no-RM runs

No separate step: `run-suite` links them. The no-RM arm trains once per identical training config and
seed across suites; the other cards get a run folder of symlinks to the owner's finished run, with
`shared-run.json` naming it (`share` in the plan, `skip` once linked). Judge a linked run with the same
`judge_runs.py` call as any other run; `aggregate-suite` notes it as a shared no-RM run of its owner.

### 6.11 Results table

```bash
PYTHONPATH=app python experiments/benchmark/scripts/cycles.py --output outputs/tables/cycles.md
PYTHONPATH=app python experiments/benchmark/scripts/results_table.py --out outputs/tables \
    --results outputs/judge/results.jsonl
```

`cycles.py` lists, per ARM-FM bundle, the laps of its machine whose rewards add to more than zero (an
agent can loop one for reward without finishing). `results_table.py` reads `outputs/runs` (or
`--runs-root`) and writes `tables.csv` (one row per card x arm x seed) and `tables.md`: the judge
columns, the training eval, the first step with greedy or sampled success of at least 0.8, wall time,
rule breaks, flags (too simple, cannot start, positive cycle, farming, shared run, judge crashed), what
the new judge changed against `judge.v1.json`, the cards that do not learn, and each card's NL task,
LTLf and machine files. `--results` is the JSONL of section 6.9 and only names the runs whose judge
crashed. It reads only; rerun it whenever runs or judges change.
