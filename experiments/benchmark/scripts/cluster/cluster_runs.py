"""Train benchmark runs on the UPV tensor cluster through SLURM and bring the finished ones back.

Usage (repository root, `RM_RL_env`, UPV VPN up):
    PYTHONPATH=app python experiments/benchmark/scripts/cluster/cluster_runs.py sync
    PYTHONPATH=app python experiments/benchmark/scripts/cluster/cluster_runs.py submit RUNS \
        [--slots 12] [--lanes 2] [--partition docencia] [--time H:MM:SS] [--dry-run]
    PYTHONPATH=app python experiments/benchmark/scripts/cluster/cluster_runs.py status
    PYTHONPATH=app python experiments/benchmark/scripts/cluster/cluster_runs.py fetch [--dest DIR]

`sync` fast-forwards the cluster clone `~/tfm/repo` to local `main` (a git bundle) and copies the
job scripts. `submit` reads RUNS: a run-suite runs.yaml (all its runs) or a text file of lines
`<runs.yaml> <card> <arm> <seed> [<steps>]` (a mix run is named by its mix id; steps default to
the runs file's total_timesteps). It refuses unless the cluster clone is at this checkout's HEAD
and what the runs read (app, the learner configs, the task files, the bundles) has no uncommitted
change here, and it drops the runs finished, running or untrainable here, finished on the cluster,
or asked for by a live job. It writes one runs.yaml copy per (runs file, arm, steps, env family,
seeds) group, narrowed with `only`, `mixes`, `arms`, `seeds` and `total_timesteps`, so run-suite
trains exactly the requested runs under their usual names. Copies are packed into SLURM jobs of at
most `--slots` runs and one copy per suite name (run-suite locks per suite). Each job takes the
GPU shards its runs need (6 shards = one L40S), the CPUs its runs keep busy, a time limit
estimated from its steps unless `--time` is given, and one of `--lanes` job names with
`--dependency=singleton`, so at most that many jobs run at once. `fetch` copies every
finished run folder into DEST (default `outputs/runs`) with the local layout, newest job first,
rewriting the cluster paths in its `config.yaml` (a shared no-RM run's links point at its owner's
copy); it never overwrites a folder, skips a run that DEST already has another folder for, and
goes on past a folder that fails.
"""

import argparse
import contextlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import yaml

from scripts.run_suite import (
    FINISHED,
    ROOT,
    RUNNING,
    RUNS_PATH,
    SHARED_FILE,
    Run,
    expand_runs,
    load_suite,
    run_state,
)
from src.benchmark.plan_check import RECORD_SUFFIX as PLAN_CHECK_SUFFIX

REMOTE = "tensor"
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", REMOTE]
HERE = Path(__file__).resolve().parent
LANE = "tfm-lane"  # SLURM job name prefix; singleton keeps one running job per name
SHARDS_PER_GPU = 6  # tensor: 24 shards over 4 L40S
SLOTS = 12  # runs per L40S: see README.md, "Throughput"
GPU_STEPS_PER_S = 8_500  # one L40S, all its runs together: README.md, "Throughput"
SOLO_STEPS_PER_S = 2_100  # one run alone on an L40S is CPU-bound near this: README.md
TIME_MARGIN = 1.5  # over the estimate: evals, start-up and other users' jobs on the GPU vary
# Env families whose worlds step on the CPU (XLand: jax, CPU only), so one of their runs is
# CPU-bound well below SOLO_STEPS_PER_S: (steps/s of one run, CPUs it keeps busy). README.md, "XLand".
CPU_BOUND = {"xland": (780, 2)}
# The copies narrow cards and mixes x arms x seeds, so runs files with these are refused.
UNSUPPORTED = ("variants", "compare_learners")
# Every finished run folder of every job folder that fetch has not copied yet (fetch leaves a
# FETCHED_MARK in it, so a run archived here for retraining is neither skipped nor copied back);
# a shared no-RM run's links count too.
FETCHED_MARK = ".fetched"
FINISHED_FOLDERS = (
    "for f in tfm/jobs/*/repo/outputs/runs/bench__*/seed*-*/resources.json; do"
    f' [ -e "${{f%/*}}/{FETCHED_MARK}" ] || grep -l \'"status": "finished"\' "$f";'
    " done 2>/dev/null || true"
)


class CommandError(RuntimeError):
    """A local command (ssh, rsync, git) exited with an error."""


@dataclass(frozen=True)
class Request:
    runs_file: Path
    card: str
    arm: str
    seed: int
    steps: int

    @property
    def key(self) -> tuple[Path, str, str, int]:
        """The run it asks for, whatever the steps."""
        return self.runs_file, self.card, self.arm, self.seed


@dataclass
class Chunk:
    """The runs of one runs.yaml copy: cards and mixes (ids) x one arm x seeds, at one step count."""

    runs_file: Path
    suite: str
    arm: str
    steps: int
    seeds: tuple[int, ...]
    cards: list[str]
    ram_gb: float  # per run, the learner's run-suite estimate
    solo_steps_per_s: int  # one run alone; the GPU's share caps it further (job_time)
    cpus_per_run: int

    @property
    def runs(self) -> int:
        return len(self.cards) * len(self.seeds)


# ======================================================================================
#                                      CLUSTER CALLS
# ======================================================================================


def run(*argv: str) -> str:
    """Run a local command (ssh, rsync, git) and return its output.

    Raises:
        CommandError: If the command exits with an error.
    """
    program = shutil.which(argv[0])
    if program is None:
        sys.exit(f"{argv[0]} is not on PATH")
    result = subprocess.run(  # noqa: S603  approved: argv built here (ssh, rsync, git), no local shell
        [program, *argv[1:]], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise CommandError(f"{argv[0]} failed ({result.returncode}): {result.stderr.strip()}")
    return result.stdout


def remote(command: str) -> str:
    """Run a shell command on the cluster and return its output."""
    return run(*SSH, command)


def rsync(*arguments: str) -> None:
    run("rsync", "-a", *arguments)


def finished_on_cluster() -> list[PurePosixPath]:
    """Every finished run folder in the cluster job folders, newest job folder first."""
    return sorted(
        {PurePosixPath(line).parent for line in remote(FINISHED_FOLDERS).split()}, reverse=True
    )


# ======================================================================================
#                                      PLANNING
# ======================================================================================


def suite_spec(runs_file: Path, cache: dict[Path, dict]) -> dict:
    if runs_file not in cache:
        spec = load_suite(runs_file)
        used = [key for key in UNSUPPORTED if spec.get(key)]
        if used:
            raise ValueError(f"{runs_file}: {', '.join(used)} not supported here; train it locally")
        cache[runs_file] = spec
    return cache[runs_file]


def read_requests(path: Path, specs: dict[Path, dict]) -> list[Request]:
    """The requested runs, each checked against its runs file's own runs."""
    if path.suffix in (".yaml", ".yml"):
        spec = suite_spec(path.resolve(), specs)
        steps = spec["total_timesteps"]
        return [
            Request(path.resolve(), run.card["id"], run.arm, run.seed, steps)
            for run in expand_runs(spec)
        ]

    requests = []
    steps_asked: dict[tuple[Path, str, str, int], int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split("#")[0].split()
        if not fields:
            continue
        runs_file = (ROOT / fields[0]).resolve()
        card, arm, seed = fields[1], fields[2], int(fields[3])
        spec = suite_spec(runs_file, specs)
        if (card, arm, seed) not in {(r.card["id"], r.arm, r.seed) for r in expand_runs(spec)}:
            raise ValueError(
                f"{line!r}: not a run of {fields[0]} (card or mix, arm or seed unknown)"
            )
        steps = int(fields[4]) if len(fields) > 4 else spec["total_timesteps"]
        request = Request(runs_file, card, arm, seed, steps)
        # Run names carry no steps, so two step counts would be two runs of one name.
        earlier = steps_asked.setdefault(request.key, steps)
        if earlier != steps:
            raise ValueError(f"{line!r}: this run is already asked for at {earlier} steps")
        requests.append(request)
    return requests


def plan_chunks(
    requests: list[Request], runs: dict[tuple, Run], specs: dict[Path, dict], slots: int
) -> list[Chunk]:
    """Group the requests into runs.yaml copies of at most ``slots`` runs (whole cards or mixes).

    A copy holds one env family, so its runs share one speed and CPU need.
    """
    seeds: dict[tuple, set[int]] = {}
    for request in dict.fromkeys(requests):
        family = runs[request.key].card["env"]["family"]  # a mix's is its cards' (mix_runs)
        key = (request.runs_file, request.arm, request.steps, family, request.card)
        seeds.setdefault(key, set()).add(request.seed)

    groups: dict[tuple, list[str]] = {}
    for (runs_file, arm, steps, family, card), card_seeds in seeds.items():
        group = (runs_file, arm, steps, family, tuple(sorted(card_seeds)))
        groups.setdefault(group, []).append(card)

    chunks = []
    for (runs_file, arm, steps, family, group_seeds), cards in groups.items():
        spec = specs[runs_file]
        ram_gb = spec["learners"][spec["learner"]]["ram_gb"]
        solo, cpus = CPU_BOUND.get(family, (SOLO_STEPS_PER_S, 1))
        per_chunk = max(1, slots // len(group_seeds))
        for start in range(0, len(cards), per_chunk):
            part = cards[start : start + per_chunk]
            chunks.append(
                Chunk(runs_file, spec["suite"], arm, steps, group_seeds, part, ram_gb, solo, cpus)
            )
    return chunks


def pack_jobs(chunks: list[Chunk], slots: int) -> list[list[Chunk]]:
    """First fit: at most ``slots`` runs per job and one chunk per suite name."""
    jobs: list[list[Chunk]] = []
    for chunk in chunks:
        for job in jobs:
            fits = sum(c.runs for c in job) + chunk.runs <= slots
            if fits and chunk.suite not in {c.suite for c in job}:
                job.append(chunk)
                break
        else:
            jobs.append([chunk])
    return jobs


def write_copy(chunk: Chunk, path: Path) -> None:
    """Write the chunk's runs.yaml copy and check run-suite expands it to exactly its runs."""
    spec = yaml.safe_load(chunk.runs_file.read_text(encoding="utf-8"))
    mixes = [mix for mix in spec.get("mixes") or [] if mix["id"] in chunk.cards]
    mix_ids = {mix["id"] for mix in mixes}
    # shortcut: a copy of mixes alone gets `only: []`, which run-suite reads as every card with
    # train: true (XLand has none); the check below refuses such a copy, so train those mixes
    # beside one of their suite's cards, or locally.
    spec.update(
        only=[card for card in chunk.cards if card not in mix_ids],
        mixes=mixes,
        arms=[chunk.arm],
        seeds=list(chunk.seeds),
        total_timesteps=chunk.steps,
    )
    path.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")

    got = {(run.card["id"], run.arm, run.seed) for run in expand_runs(load_suite(path))}
    wanted = {(card, chunk.arm, seed) for card in chunk.cards for seed in chunk.seeds}
    if got != wanted:
        raise RuntimeError(f"{path}: run-suite would train {sorted(got)}, not {sorted(wanted)}")


def pick_lanes(lanes: int, count: int) -> list[int]:
    """The lane of each new job: the one with the fewest of our queued or running jobs."""
    names = remote("squeue -h -u $USER -o %j").split()
    load = Counter(name for name in names if name.startswith(LANE))
    picks = []
    for _ in range(count):
        lane = min(range(1, lanes + 1), key=lambda k: load[f"{LANE}{k}"])
        load[f"{LANE}{lane}"] += 1
        picks.append(lane)
    return picks


def job_time(job: list[Chunk], slots: int) -> str:
    """A time limit for the job, estimated from its longest run.

    One GPU's speed shared by ``slots`` runs, but never faster than one run alone, times
    ``TIME_MARGIN``, rounded up to a quarter hour, at least half an hour.
    """
    seconds = TIME_MARGIN * max(
        chunk.steps / min(GPU_STEPS_PER_S / slots, chunk.solo_steps_per_s) for chunk in job
    )
    minutes = max(30, math.ceil(seconds / 900) * 15)
    return f"{minutes // 60}:{minutes % 60:02d}:00"


# ======================================================================================
#                                  CHECKS BEFORE A SUBMIT
# ======================================================================================


def dirty_paths(
    requests: list[Request], runs: dict[tuple, Run], specs: dict[Path, dict]
) -> list[str]:
    """The `git status --porcelain` lines of what the runs read.

    That is app, the learner configs, the task files, and each run's bundle with the status
    and plan-check records beside it.
    """
    paths = {"app", "experiments/benchmark/configs"}
    for request in requests:
        spec = specs[request.runs_file]
        paths.add(spec["learners"][spec["learner"]]["config"])
        paths.update([spec["tasks"]] if isinstance(spec["tasks"], str) else spec["tasks"])
        planned = runs[request.key]
        for bundle in planned.bundles or (planned.bundle,):  # a mix trains on each card's bundle
            if bundle is not None:
                paths.update((str(bundle), f"{bundle}.status.json", f"{bundle}{PLAN_CHECK_SUFFIX}"))
    return run("git", "-C", str(ROOT), "status", "--porcelain", "--", *sorted(paths)).splitlines()


def cluster_commit() -> str:
    """The cluster clone's commit; exit unless it is this checkout's HEAD."""
    local = run("git", "-C", str(ROOT), "rev-parse", "HEAD").strip()
    cluster = remote("git -C ~/tfm/repo rev-parse HEAD").strip()
    if cluster != local:
        sys.exit(
            f"the cluster clone is at {cluster[:8]}, this checkout at {local[:8]}: "
            "run sync (it sends main)"
        )
    return cluster


def cluster_places() -> dict[tuple[str, int], str]:
    """Where runs already are on the cluster, by (exp_name, seed).

    A job folder holding the finished run, or a queued or running job whose runs files ask for it.
    """
    places = {}
    for folder in finished_on_cluster():
        seed = int(folder.name.split("-")[0].removeprefix("seed"))
        places.setdefault(
            (folder.parent.name, seed), f"finished on the cluster in {folder.parts[2]}"
        )

    live = remote("squeue -h -u $USER -o %k").split()  # a job's comment is its job folder name
    if not live:
        return places
    with tempfile.TemporaryDirectory() as tmp:
        only_runs_files = ("--include=/*/", "--include=/*/runs/", "--include=/*/runs/*.yaml")
        rsync(*only_runs_files, "--exclude=*", f"{REMOTE}:tfm/jobs/", f"{tmp}/")
        for job in live:
            for copy in sorted((Path(tmp) / job / "runs").glob("*.yaml")):
                for planned in expand_runs(load_suite(copy)):
                    places.setdefault(planned.key, f"asked for by live cluster job {job}")
    return places


def skip_reason(run: Run, places: dict[tuple[str, int], str]) -> str | None:
    """Why the run is not sent, or None when it should be.

    Run-suite's state here (finished, running, or a bundle it will not train), else its place
    on the cluster.
    """
    state, folder, reason = run_state(run)
    if reason:
        return f"{state} here: {reason}"
    if state in (FINISHED, RUNNING):
        return f"{state} here"
    if folder is not None:  # fetch would keep the cluster copy beside it, so it never lands
        return f"{state} folder here ({folder.name}): archive it first"
    return places.get(run.key)


# ======================================================================================
#                                      COMMANDS
# ======================================================================================


def sync() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "tfm-main.bundle"
        run("git", "-C", str(ROOT), "bundle", "create", str(bundle), "main")
        rsync(str(bundle), f"{REMOTE}:tfm/dl/tfm-main.bundle")
    rsync(str(HERE / "job.sh"), str(HERE / "setup.sh"), f"{REMOTE}:tfm/cluster/")
    print(
        remote(
            "git -C ~/tfm/repo pull --quiet --ff-only ~/tfm/dl/tfm-main.bundle main"
            " && git -C ~/tfm/repo submodule update --init --quiet dependencies/nl2ltl dependencies/Flat"
            " && git -C ~/tfm/repo log --oneline -1"
        ),
        end="",
    )


def submit(args: argparse.Namespace) -> None:
    specs: dict[Path, dict] = {}
    requests = list(dict.fromkeys(read_requests(args.runs, specs)))
    suite_runs = {
        (runs_file, run.card["id"], run.arm, run.seed): run
        for runs_file, spec in specs.items()
        for run in expand_runs(spec)
    }

    # == The cluster must train what is here: the same commit, nothing the runs read uncommitted ==
    dirty = dirty_paths(requests, suite_runs, specs)
    if dirty and not args.dry_run:
        sys.exit("uncommitted changes the runs would miss; commit, then sync:\n" + "\n".join(dirty))
    for line in dirty:
        print(f"uncommitted (a real submit refuses): {line}")
    commit = "<cluster HEAD>" if args.dry_run else cluster_commit()

    # == Never train a run twice; a dry run looks only here ==
    places = {} if args.dry_run else cluster_places()
    sent = []
    for request in requests:
        reason = skip_reason(suite_runs[request.key], places)
        if reason:
            print(f"skip {suite_runs[request.key].exp_name} seed {request.seed}: {reason}")
        else:
            sent.append(request)
    if not sent:
        print("nothing to submit")
        return

    jobs = pack_jobs(plan_chunks(sent, suite_runs, specs, args.slots), args.slots)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    lanes = [1] * len(jobs) if args.dry_run else pick_lanes(args.lanes, len(jobs))
    print(f"{len(sent)} runs in {len(jobs)} jobs, commit {commit}")

    with tempfile.TemporaryDirectory() as tmp:
        for number, (job, lane) in enumerate(zip(jobs, lanes, strict=True), start=1):
            name = f"{stamp}-{number:02d}"
            runs_dir = Path(tmp) / name / "runs"
            runs_dir.mkdir(parents=True)
            for index, chunk in enumerate(job, start=1):
                write_copy(chunk, runs_dir / f"{chunk.suite}-{index}.yaml")
                print(
                    f"  {name}: {chunk.runs_file.relative_to(ROOT, walk_up=True)} {chunk.arm} "
                    f"{chunk.steps} steps, seeds {list(chunk.seeds)}, {', '.join(chunk.cards)}"
                )

            runs = sum(chunk.runs for chunk in job)
            shards = min(SHARDS_PER_GPU, math.ceil(SHARDS_PER_GPU * runs / args.slots))
            cpus = sum(chunk.runs * chunk.cpus_per_run for chunk in job) + 2
            mem_gb = math.ceil(sum(chunk.runs * chunk.ram_gb for chunk in job)) + 4
            time_limit = args.time or job_time(job, args.slots)
            sbatch = (
                f"sbatch --parsable -p {args.partition} -t {time_limit} -J {LANE}{lane} "
                f"--dependency=singleton --comment {name} -c {cpus} --mem {mem_gb}G "
                f"--gres=shard:{shards} -o tfm/jobs/{name}/slurm.out "
                f"tfm/cluster/job.sh tfm/jobs/{name} {commit} {args.slots}"
            )
            if args.dry_run:
                print(f"  {sbatch}")
                continue
            rsync("--mkpath", f"{Path(tmp) / name}/", f"{REMOTE}:tfm/jobs/{name}/")
            job_id = remote(sbatch).strip()
            print(
                f"  {name}: {runs} runs, {shards} shards, {time_limit}, lane {lane}, job {job_id}"
            )


def status() -> None:
    print(remote("squeue -u $USER -o '%.8i %.11j %.18k %.8T %.10M %R'"), end="")
    print(
        remote(
            "for d in tfm/jobs/*/; do"
            ' f=$(ls -d "$d"repo/outputs/runs/bench__*/seed*-* 2>/dev/null | wc -l);'
            ' n=$(grep -l \'"status": "finished"\''
            ' "$d"repo/outputs/runs/bench__*/seed*-*/resources.json 2>/dev/null | wc -l);'
            ' echo "$d: $f run folders, $n finished";'
            ' for log in "$d"*.log; do [ -f "$log" ] && echo "  $(tail -n 1 "$log")"; done;'
            # run-suite plans these and never queues them: job.sh fails the job for them
            " grep -hE '^(no-data|pending) ' \"$d\"*.log 2>/dev/null | sed 's/^/  not trained: /';"
            " done; true"
        ),
        end="",
    )


def localize(config: Path) -> None:
    """Point a fetched ``config.yaml`` at this checkout instead of the cluster clone."""
    text = config.read_text(encoding="utf-8")
    # yaml_config_name is <clone>/outputs/runs/<exp>/run-config.yaml
    clone = PurePosixPath(yaml.safe_load(text)["yaml_config_name"]).parents[3]
    config.write_text(text.replace(f"{clone}/", f"{ROOT}/"), encoding="utf-8")


def relink(folder: Path, dest: Path) -> None:
    """Point a fetched shared no-RM run folder at its owner's copy in ``dest``.

    run-suite's ``link_shared`` links each owner file under its own name by its absolute cluster
    path, and names the owner folder in ``shared-run.json``; both are redone here, as a local
    run-suite writes them.

    Raises:
        FileNotFoundError: If the owner folder is not in ``dest``.
    """
    record = json.loads((folder / SHARED_FILE).read_text(encoding="utf-8"))
    owner = dest.joinpath(*PurePosixPath(record["owner_folder"]).parts[-2:])  # <exp>/<folder>
    if not owner.is_dir():
        raise FileNotFoundError(f"its owner {owner} is not here")
    for link in folder.iterdir():
        if link.is_symlink():
            link.unlink()
            link.symlink_to(owner / link.name)
    record["owner_folder"] = str(owner)
    (folder / SHARED_FILE).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def fetch_folder(folder: PurePosixPath, exp_dir: Path, dest: Path, linked: bool) -> None:
    """Copy one finished cluster run folder into ``exp_dir``, with the experiment's own files.

    It is staged under ``dest/.fetch/``, outside every experiment folder, where no run glob
    looks, and renamed into place when complete.
    """
    part = dest / ".fetch" / exp_dir.name / folder.name
    part.parent.mkdir(parents=True, exist_ok=True)
    rsync(f"{REMOTE}:{folder}/", f"{part}/")
    if linked:
        relink(part, dest)
    else:
        localize(part / "config.yaml")

    seed = folder.name.split("-")[0]
    # A linked run has no log; only a mix has members/ (its cards, for test-rl --judge).
    names = ("card.json", "run-config.yaml", f"{seed}.log", "members")
    sources = [f"{REMOTE}:{folder.parent / name}" for name in names]
    exp_dir.mkdir(parents=True, exist_ok=True)
    rsync("--ignore-existing", "--ignore-missing-args", *sources, f"{exp_dir}/")
    part.rename(exp_dir / folder.name)
    remote(f"touch {folder}/{FETCHED_MARK}")  # paths here have no spaces or shell characters
    with contextlib.suppress(OSError):  # a folder of the experiment that failed stays staged
        part.parent.rmdir()


def fetch(dest: Path) -> None:
    linked = {
        PurePosixPath(line).parent
        for line in remote(
            "ls -d tfm/jobs/*/repo/outputs/runs/bench__*/seed*-*/" + SHARED_FILE + " 2>/dev/null"
            " || true"
        ).split()
    }
    folders = finished_on_cluster()
    folders.sort(key=lambda folder: folder in linked)  # owners before the runs linking them

    copied, failed = 0, 0
    for folder in folders:
        exp_dir = dest / folder.parent.name
        seed = folder.name.split("-")[0]
        if (exp_dir / folder.name).exists():
            continue
        others = [path.name for path in exp_dir.glob(f"{seed}-*") if "." not in path.name]
        if others:
            print(f"kept on the cluster: {folder}; {exp_dir} already has {', '.join(others)}")
            continue

        try:
            fetch_folder(folder, exp_dir, dest, folder in linked)
        except (CommandError, OSError, KeyError, ValueError, yaml.YAMLError) as error:
            print(f"failed, will retry next fetch: {folder}: {error}")
            failed += 1
            continue
        print(f"fetched {exp_dir.name}/{folder.name}")
        copied += 1

    print(f"{copied} run folders fetched into {dest}, {failed} failed")
    if failed:
        sys.exit(1)


# ======================================================================================
#                                      ARGUMENTS
# ======================================================================================


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("sync", help="Send local main and the job scripts to the cluster")
    commands.add_parser("status", help="Our SLURM jobs and each job folder's progress")
    fetch_parser = commands.add_parser("fetch", help="Copy finished run folders back")
    fetch_parser.add_argument("--dest", type=Path, default=RUNS_PATH, help="(default: %(default)s)")

    submit_parser = commands.add_parser("submit", help="Pack the runs into SLURM jobs and submit")
    submit_parser.add_argument("runs", type=Path, help="A runs.yaml or a file of run lines")
    submit_parser.add_argument("--slots", type=int, default=SLOTS, help="Runs per L40S")
    submit_parser.add_argument("--lanes", type=int, default=2, help="Most jobs running at once")
    submit_parser.add_argument("--partition", default="docencia", help="docencia (1 day), long")
    submit_parser.add_argument(
        "--time",
        help="Time limit per job (H:MM:SS); default: estimated from its steps. Shorter ones "
        "backfill sooner",
    )
    submit_parser.add_argument("--dry-run", action="store_true", help="Print the plan only")

    args = parser.parse_args()
    try:
        if args.command == "sync":
            sync()
        elif args.command == "status":
            status()
        elif args.command == "fetch":
            fetch(args.dest.resolve())
        else:
            submit(args)
    except (CommandError, ValueError) as error:  # ValueError: a bad RUNS line or runs file
        sys.exit(str(error))


if __name__ == "__main__":
    main()
