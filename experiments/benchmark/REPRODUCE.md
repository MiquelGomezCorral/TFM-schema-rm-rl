# Reproducing the benchmark

Every command runs from the repository root inside the `RM_RL_env` Conda environment
(Python 3.13) with `PYTHONPATH=app`. The scripts under `experiments/benchmark/scripts/` set
`PYTHONPATH` themselves and take the interpreter from `PYTHON` (default `python`).

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
suite and arm, with `--paraphrases` (which also covers the base wordings) except for `smoke`:

- Per card, one `generate-larm --mode compiler` (FARM) or `--mode arm-fm --arm-fm-critic` (ARM-FM)
  child process; bundle folder `<dir>/<card-id>/`, paraphrase k at `<card-id>~p<k>`.
- Beside each folder: `<card-id>.status.json` (`status`, `reason`, `calls`, `wall_time_s`, `log`) and
  `<card-id>.log`.
- Embeddings run afterwards, one bundle at a time, with `embed-larm --embedding-server`.
- Caps: `--parallel` (default 10), `--max-calls` and `--deadline-min` stop launching new cards;
  cards already running finish, so the call count can pass the cap by up to `--parallel` cards.
  A cap holds per `generate-suite` call, not for the whole `generate.sh` run: each suite and arm
  starts its own count. Only the requests of `generate-larm` runs made by that call count; a card
  that waits just for embeddings adds none. Each card prints one line, including `not launched
  (cap or deadline)` for the ones left out. `calls` in a status counts the per-call records in the
  bundle's `raw_responses.json`; failed cards of both arms keep theirs.
- Each status file is written as soon as its card finishes generating and again after its
  embedding, so an interrupted call keeps the statuses of the cards it finished.

Statuses and what a rerun does:

| Status | Meaning | Rerun |
| --- | --- | --- |
| `complete` | every stage and `embeddings.json` | skipped |
| `pipeline-failed` | attempts exhausted or a stage rejected | skipped; `--retry-failed` runs it again |
| `provider-error` | connection, timeout, quota or server error | runs again |
| `incomplete` | a stage file is missing, embeddings are pending, or the run crashed before writing a bundle | runs again; a bundle with generation done only embeds |

Known gap: `generate-larm` saves a bundle only at the end of a run and has no stage resume, so an
`incomplete` card that needs generation runs again whole, not just its missing stages.

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
the pipeline does not report, or git cannot tell, is `null`. `provisional` is true unless the
tree is clean on `main`. `raw_responses.json` adds one record per model request,
`{stage, role, model_requested, model_reported}`; `model_reported` is the model named in the
provider's reply and `null` when the provider names none. The arms count differently, so their
`attempts` and `retries` are not comparable numbers: FARM `attempts` are proposals (a critic
rejection starts the next one) and `retries` are reruns after provider or content failures;
ARM-FM `attempts` are loop rounds and `retries` the rounds that failed.

### Cross-critic

```bash
python app/main.py cross-critic --bundles <dir>/arm-fm --critic farm   [--max-calls N]
python app/main.py cross-critic --bundles <dir>/farm   --critic arm-fm [--max-calls N]
```

The other pipeline's critic (`glm-5.3-flash`) judges each machine and writes `cross_critic.json`,
the only file it adds, into the bundle: verdict, flags, the critic's `raw_reply` (`raw_reply_path`
stays `null`) and `judged_sha256`, the identity of the task and machine judged. A bundle is
skipped only when its file has the same direction and identity; a regenerated machine is judged
again and the file overwritten. The command fails when no bundle is one this critic judges. The
two critics read different inputs (see each file's `information_note`), so the two directions are
reported apart and never pooled.

## 3. Training and evaluation

Runs expand from each suite's `runs.yaml`; `run-suite` and `aggregate-suite` and the wrapper scripts
`experiments/benchmark/scripts/train.sh` and `experiments/benchmark/scripts/evaluate.sh` come from the
runs slice. In order: `run-suite --suite <runs.yaml> --dry-run`, then without `--dry-run`, then
`test-rl --judge` over the finished runs, then `aggregate-suite --suite <runs.yaml> --output <dir>`.

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
open items at the end, steps to first environment success (`n/a` when the environment reward does
not match the task), evaluation success over the last three evaluation points, environment return,
RM return (within an arm only), episode length, wall time, peak RSS, and the `machine-wrong` flag.
