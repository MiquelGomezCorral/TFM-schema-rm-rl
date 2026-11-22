# Training on the UPV tensor cluster

`cluster_runs.py` trains benchmark runs on `tensor` (one node: 96 CPUs, 4x NVIDIA L40S, shared with
teaching) through SLURM, with the same `run-suite` and `train-rl` as this machine, and brings the
finished run folders back into `outputs/runs` under their usual names.

Training needs no API key, no MONA and no embedding server: the RM-state embeddings come from the
bundle's `embeddings.json`. Every command needs the UPV VPN; `ssh tensor` must work without a
password prompt (`~/.ssh/config` alias, key auth). rsync must be 3.2.3 or newer on both sides
(`--mkpath`); both had 3.2.7 on 2026-11-22.

## Use

From the repository root, inside `RM_RL_env`:

```bash
PYTHONPATH=app python experiments/benchmark/scripts/cluster/cluster_runs.py sync     # local main -> cluster
PYTHONPATH=app python experiments/benchmark/scripts/cluster/cluster_runs.py submit RUNS [--dry-run]
PYTHONPATH=app python experiments/benchmark/scripts/cluster/cluster_runs.py status
PYTHONPATH=app python experiments/benchmark/scripts/cluster/cluster_runs.py fetch [--dest DIR]
```

- `sync` sends local `main` as a git bundle and fast-forwards `~/tfm/repo` on the cluster (the
  cluster cannot pull from here, and GitHub is behind). Run it before `submit` whenever `main` moved;
  each job trains the commit the clone had when it was submitted.
- `submit` refuses unless the cluster clone is at this checkout's HEAD and what the runs read has no
  uncommitted change here (`app`, `experiments/benchmark/configs`, the learner config, the task
  files, each run's bundle with its `.status.json` and `.plan_check.json`); it lists the dirty paths.
  It drops, naming each with the reason: runs finished, running, `no-data` or `pending` here (as
  run-suite sees them), runs finished in a cluster job folder (fetch them), and runs a queued or
  running job asks for. A finished run here blocks its name: archive that folder first to retrain it.
- `RUNS` is a run-suite `runs.yaml` (all its runs) or a text file with one run per line:
  `<runs.yaml> <card> <arm> <seed> [<steps>]`, paths relative to the repository root, `#` comments.
  A mix run is named by its mix id in the card column. Steps default to the runs file's
  `total_timesteps`. Example: `experiments/benchmark/base/runs.yaml base-doorkey arm-fm 2 5000000`.
  One run at two step counts is refused (run names carry no steps).
- `submit --dry-run` prints the jobs and their `sbatch` lines without touching the cluster: the
  dirty paths are listed but do not stop it, and only the runs here are checked for repeats.
- `status` shows our SLURM jobs and, per job folder, how many runs finished, each driver's last line,
  and the runs not trained because their bundle is `no-data` or `pending` there (`job.sh` then
  exits 1).
- `fetch` copies every finished run folder (its `resources.json` says `finished`) into DEST
  (default `outputs/runs`), with the experiment's `card.json`, `run-config.yaml`, `seed<N>.log`
  and, for a mix, `members/` when DEST lacks them. Judge them as usual afterwards (`judge_all.py` or `test-rl --judge`). A folder
  that fails is reported and retried by the next fetch; the others still come, and fetch exits 1.
- Cancel a job with `ssh tensor scancel <job id>` (ids are in `status`).

## How a submit becomes jobs

1. The runs are grouped by (runs file, arm, steps, env family, seeds of the card or mix). Each group
   becomes a copy of its runs file with `only` (its cards), `mixes` (its mixes), `arms`, `seeds` and
   `total_timesteps` narrowed, and run-suite's own `load_suite` + `expand_runs` must expand the copy
   to exactly the requested runs. Run names do not include steps, so a 5M run keeps its card's usual
   name. A copy of mixes alone has `only: []`, which run-suite reads as every `train: true` card, so
   that check refuses it in a suite with such cards (XLand has none; `complex/mixes-example.yaml`
   does: send its mix with one of its cards). Runs files with `variants` or `compare_learners` are
   refused (train those here).
2. Copies are packed into jobs of at most `--slots` runs (default in the script, see Throughput),
   whole cards only, and at most one copy per suite name, because run-suite takes one lock per suite.
3. Each job gets its own folder `~/tfm/jobs/<UTC stamp>-<n>/` with a shared clone (`repo/`) at the
   pinned commit, so drivers of different jobs never share a lock or an `outputs/runs`. The clone
   is built as `repo.part/` and renamed when complete, so a job killed while cloning leaves none.
   `job.sh` starts one `run-suite --parallel <slots>` per copy, all at once. run-suite never queues
   a run whose bundle is `no-data` or `pending` and still exits 0, so `job.sh` fails the job (exit
   1) when a driver's plan lists one.
4. Resources: `--gres=shard:K` with K = ceil(6 x runs / slots) (6 shards = one L40S), 1 CPU per run
   (2 for XLand, see XLand) + 2 (a GPU run keeps one core busy, 2 GB RSS; SLURM here binds no
   cores, so the request is for fair scheduling), memory = the learner's `ram_gb` per run + 4 GB,
   partition `docencia`. The time limit is the job's longest run at min(8,500 / slots, one run
   alone) steps/s (Throughput; one run alone is 2,100 for MiniGrid, 780 for XLand), x1.5, rounded
   up to a quarter hour, at least 30 min: 3:00:00 for 5M steps at 12 slots (MiniGrid or XLand),
   1:00:00 for 1.5M. `--time` overrides it. Each job takes one of `--lanes` names (`tfm-lane1`, `tfm-lane2`, ...) with
   `--dependency=singleton`, so at most `--lanes` of our jobs run at once (default 2: two GPUs' worth).

## Rules fetch keeps

- It never overwrites: a run folder already in DEST is skipped, and a run that DEST already has
  another folder for (same experiment and seed, not archived) stays on the cluster with a message,
  so a judge never sees two folders of one run. The newest job folder goes first, so when two jobs
  finished one run, the newer folder is the one fetched.
- A folder is staged in `DEST/.fetch/<experiment>/<folder>/`, outside every experiment folder, and
  renamed into place when complete. Not inside the experiment folder: `test-rl --run` globs
  `*/summary.json`, which matches dotted folders too.
- A shared no-RM run (`shared-run.json`) holds absolute symlinks to its owner on the cluster. Owners
  are fetched first; the linked folder's links are then pointed at the owner's copy in DEST and its
  `shared-run.json` names that copy, as a local run-suite writes them. A linked run whose owner is
  not in DEST fails with a message.
- The copied `config.yaml` has the cluster clone path (`/home/alumno.upv.es/.../repo/`) replaced by
  this checkout's root, so `test-rl` finds the bundle here. `git_head` keeps the commit it trained.

## Differences from this machine

- Python 3.13.14 (uv-managed) instead of conda's 3.13.15, and torch 2.14.0+cu130 instead of +cu132.
  Same pinned versions of everything in `requirements.txt`.
- `requirements.txt` lacks Pillow, which `app/scripts/test_rl.py` imports; `setup.sh` adds the local
  version (12.3.0).
- No-RM runs are shared only inside one job (one run-suite driver), never with runs trained here or
  in other jobs.
- `nvidia-smi` in a job lists all four GPUs, but `CUDA_VISIBLE_DEVICES` names the one holding the
  job's shards, so torch sees only that one.

## Queue notes

- SLURM backfill starts a job early only if its time limit ends before the next big job's planned
  start. On 2026-11-22 a 96-CPU job (8 h) was planned for 08:56 the next morning: a 12 h limit kept
  our job pending, 2 h started at once. Ask for little more than the runs need.
  `squeue -o '%.8i %.10u %.8T %S %R'` shows planned starts.
- A just-submitted job shows `(InvalidAccount)` for up to a minute (no accounting database); it then
  starts normally.

## One-time setup (done 2026-11-22)

```bash
# on tensor, user space only (no conda, no root):
curl -LsSf -o ~/tfm/dl/uv.tar.gz https://github.com/astral-sh/uv/releases/download/0.11.29/uv-x86_64-unknown-linux-gnu.tar.gz
# check it against the release's .sha256, then:
tar -xzf ~/tfm/dl/uv.tar.gz -C ~/tfm/dl && cp ~/tfm/dl/uv-x86_64-unknown-linux-gnu/uv* ~/.local/bin/
~/.local/bin/uv python install 3.13
# here: git bundle create <tmp>/tfm-main.bundle main; rsync it to tensor:tfm/dl/tfm-main.bundle
git clone --branch main ~/tfm/dl/tfm-main.bundle ~/tfm/repo
git -C ~/tfm/repo submodule update --init dependencies/nl2ltl dependencies/Flat   # from GitHub
# here: rsync -a experiments/benchmark/scripts/cluster/ tensor:tfm/cluster/
srun -p docencia -c 8 --mem 16G -t 60 bash ~/tfm/cluster/setup.sh    # venv ~/tfm/venv
```

Rerun `setup.sh` (inside `srun`) when `requirements.txt` changes.

## Throughput

Measured 2026-11-22 with base-doorkey, FARM, PPO (16 envs x 256 steps), one job per L40S, the other
three GPUs busy with other users. Steps/s per run are end to end (`total_env_steps / wall_seconds`,
evals and start-up included); runs of 300k steps except the 1.5M live test.

| Runs on one L40S | Steps/s per run | Total steps/s | GPU use |
| ---: | ---: | ---: | ---: |
| 1 (1.5M steps) | 2,141 | 2,141 | about 15% |
| 6 | 1,283 | 7,700 | 99% |
| 12 | 714 | 8,566 | 99% |
| 24 | 358 | 8,596 | 99% |

One L40S tops out near 8,600 steps/s, so 12 runs per GPU (`SLOTS`) give the full total at half the
wall time per run of 24. A 5M-step run then takes about 2 h. This machine, for comparison, gives
about 620 steps/s per run with 18 at once (about 11,000 total on its RTX 5070); two lanes here give
about 17,000. Each run keeps one CPU core at 100% and peaks at 1.9-2.4 GB RSS.

A cluster run and its local twin, same seed, are not bit-identical (losses differ from the first
update: GPU and CUDA builds differ), but the live test matched on every judged field: base-doorkey
FARM seed 1 at 1.5M steps judged 1.00 success on both, 0 hard or soft breaks, RM return 13.0, mean
length 16.93 vs 16.91, steps to success 253,952 on both.

## XLand

XLand-MiniGrid steps its worlds with jax, on the CPU only (`custom_envs/xland_env.py`), so an XLand
run is CPU-bound well below a MiniGrid run alone. `CPU_BOUND` in `cluster_runs.py` gives the
`xland` env family its own speed and CPU request; every other family keeps 2,100 steps/s and 1 CPU.

Measured 2026-11-23 with one check job (job 56363): the no-RM arm of `xland-x1-197` and of the
3-card mix `xland-mix3`, PPO (16 envs x 256 steps), 100k steps, both on one L40S shard, while our
9-run MiniGrid job ran. Both ended `finished`, 2.3 GB peak RSS each, 2.7-2.8 min end to end.

| Measure | X1 card | 3-card mix |
| ---: | ---: | ---: |
| Training loop, no pinning (steps/s, `train.csv` collect + update) | 1,420-2,010 | 1,860 |
| Training loop, pinned mid-run to 1 core / 2 cores (`taskset`) | 2,280 (1 core) | 1,950 (2 cores) |
| Cores in use, no pinning (`top`, 10 s samples) | 1.0-1.3 | 1.3-1.4 |
| Evaluation of 10 episodes every 50k steps (untrained policy, 5,070 steps) | 8.8 s | 8.4 s |
| Final evaluation, 100 episodes | 88 s | 89 s |

- **One core is enough.** A run starts 543 threads (jax sizes its pool to the node's 96 cores),
  and SLURM here binds no cores (`ConstrainCores=no`), so unpinned it keeps 1.0-1.4 cores busy;
  pinned to one core it trains as fast or faster. `submit` asks for 2 CPUs per run, so the
  request covers what an unpinned run really uses.
- **5M steps, no RM:** about 2,940 s of training at 1,700 steps/s, 99 evaluations x 8.6 s, the
  final evaluation and start-up: about 3,900 s, 1,290 steps/s end to end.
- **5M steps with a machine:** not measured here (no XLand bundle was committed yet). Locally a
  run with a machine is 0.61x one without (970 vs 1,600 steps/s), so the estimate is 780 steps/s,
  the `CPU_BOUND` speed for every XLand run.

At 12 slots the GPU's share (8,500 / 12 = 708 steps/s) is below 780, so XLand jobs get the
MiniGrid time limit, 3:00:00 for 5M steps; at `--slots 6` the CPU speed caps them (2:45:00).
