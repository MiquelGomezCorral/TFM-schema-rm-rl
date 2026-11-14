"""Run a benchmark suite: expand a ``runs.yaml`` into ``train-rl`` runs and train them.

Usage:
    python app/main.py run-suite --suite <runs.yaml> --parallel 4 --max-ram-gb 16 --time-box-min 50
    python app/main.py run-suite --suite <runs.yaml> --dry-run

A ``mixes:`` list in the runs.yaml (``- {id: siren-serve, cards: [cx-siren, cx-box]}``) adds runs that
train one policy on several cards' machines at once: ``task_bundles`` with ``task_draw: alternate``,
for the arms with a bundle (not ``no-rm``). The run's ``summary.json`` records the ``task_split``;
the cards are written to ``members/<id>.json`` in the run's folder for ``test-rl --judge``.

A run is one card x arm x learner x variant x seed. Its folder is
``outputs/runs/<exp_name>/seed<seed>-<UTC>-<pid>/`` (written by ``train-rl``), beside the
suite's ``card.json`` and ``run-config.yaml``. A rerun skips ``finished`` runs (``summary.json``
present), leaves a run whose process is alive alone, renames an ``interrupted`` or ``timed-out``
folder to ``<folder>.<status>`` and restarts it from zero (a ``timed-out`` run only with
``--retry-timed-out``), and never trains a run whose bundle lacks a file training needs, has
status ``pipeline-failed`` or is an ablation no-op (``no-data``, with the reason). A bundle with
status ``provider-error`` or ``incomplete`` is retried by bundle generation, not here: its runs
stay ``pending``. The no-RM arm trains once per identical training config and seed, across
suites: the owner is a finished run under the runs root whose saved config matches, else a run
another driver claimed (``.share-claims/``), else the first open card here. The other cards
(``share`` in the plan) get a run folder of symlinks to the owner's run once it is
``finished``, with ``shared-run.json`` naming it, and are judged from its model with
``test-rl --run <exp_name> --judge <card.json>``. The driver writes ``resources.json`` into
each run folder. Linux only: it reads
``/proc``. One driver per suite: a second one exits at once (lock
``outputs/runs/bench__<suite>.lock``); ``--dry-run`` takes no lock. If the driver dies, its
children get SIGTERM (``PR_SET_PDEATHSIG``).
"""

import ctypes
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from functools import partial
from itertools import product
from pathlib import Path
from typing import IO

import yaml

from src.arm_fm.dqn import RUN_SETTINGS, layout_seed
from src.benchmark.traces import NO_PART, ablation_settings, read_json
from src.config import Configuration

ROOT = Configuration.WORKSPACE_PATH
RUNS_PATH = Configuration.OUTPUT_PATH / "runs"
LIBC = ctypes.CDLL(None)
PR_SET_PDEATHSIG = 1  # <linux/prctl.h>

FINISHED, RUNNING, TIMED_OUT, INTERRUPTED, NO_DATA, PENDING = (
    "finished",
    "running",
    "timed-out",
    "interrupted",
    "no-data",
    "pending",
)
ARMS = ("no-rm", "arm-fm", "farm")
SUITE_KEYS = (
    "suite",
    "tasks",
    "bundles",
    "learner",
    "learners",
    "arms",
    "seeds",
    "total_timesteps",
)
LEARNER_KEYS = ("config", "ram_gb")
# What training reads from a bundle; a missing one makes the run `no-data`.
BUNDLE_FILES = (
    "manifest.json",
    "reward_machine.txt",
    "labeling.py",
    "state_descriptions.json",
    "embeddings.json",
)
# Bundle statuses (`<card-id>.status.json`): generation retries these, so their runs wait.
BUNDLE_RETRIED = ("provider-error", "incomplete")
# A shared no-RM run is linked into each card's folder (see ``link_shared``); the card's own
# test and judge results are written there as real files, so they are never linked.
SHARED_FILE = "shared-run.json"
CARD_OWN_FILES = ("test.json", "judge.json", "agent-traces", "gifs", SHARED_FILE)
SHARE_IGNORED = ("yaml_config_name", "exp_name")  # the rest of RUN_SETTINGS decides sharing
LINK_POLL_SECONDS = 30  # how often a driver looks for a shared owner it waits for
OMP_THREADS = "2"
POLL_SECONDS = 3
KILL_GRACE_SECONDS = 30  # SIGTERM first; SIGKILL after this long
WAIT_LOG_SECONDS = 60  # a run held back for RAM is logged this often


# ======================================================================================
#                                    SUITE EXPANSION
# ======================================================================================


@dataclass(frozen=True)
class Run:
    """One training run: a card, an arm, a learner, an optional ablation variant and a seed."""

    suite: str
    card: dict
    arm: str
    learner: str
    variant: str | None
    seed: int
    bundle: Path | None  # None for the no-RM arm; the first member's for a mix
    ram_gb: float  # the learner's estimate from runs.yaml
    bundles: tuple[Path, ...] = ()  # a mix: the bundle of each of its cards, one policy for all

    @property
    def exp_name(self) -> str:
        name = f"bench__{self.suite}__{self.card['id']}__{self.arm}__{self.learner}"
        return f"{name}__off-{self.variant}" if self.variant else name

    @property
    def exp_dir(self) -> Path:
        return RUNS_PATH / self.exp_name

    @property
    def key(self) -> tuple[str, int]:
        return self.exp_name, self.seed


def bundle_path(spec: dict, card_id: str, arm: str, variant: str | None) -> Path | None:
    """The bundle folder a run trains on: ``<bundles>/<arm>/<card>``, or the ablation variant's."""
    if arm == "no-rm":
        return None
    root = Path(spec["bundles"])
    return root / card_id / f"off-{variant}" if variant else root / arm / card_id


def load_suite(path: Path) -> dict:
    """Read a ``runs.yaml`` and its task cards, checking the keys and the arms.

    ``only`` is a list of card ids or the repo-relative path of a JSON card file; the file's
    ids, in file order, replace the path, so ``spec["only"]`` is a list after this call.

    Raises:
        ValueError: If a key, arm or learner entry is missing or unknown, ``reward_source`` is
            not ``rm`` or ``both``, or ``only`` is a path that is not a card file with a
            non-empty ``cards`` list.
    """
    spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    missing = [key for key in SUITE_KEYS if key not in spec]
    if missing:
        raise ValueError(f"{path}: missing {', '.join(missing)}")
    bad_arms = [arm for arm in spec["arms"] if arm not in ARMS]
    if bad_arms:
        raise ValueError(f"{path}: unknown arms {', '.join(bad_arms)}; use {', '.join(ARMS)}")
    source = spec.get("reward_source", "rm")
    if source not in ("rm", "both"):
        raise ValueError(
            f"{path}: reward_source {source!r} is not allowed; bundle arms take rm or both "
            "(no-RM arms always train on the env reward)"
        )
    for name, learner in spec["learners"].items():
        absent = [key for key in LEARNER_KEYS if key not in learner]
        if absent:
            raise ValueError(f"{path}: learner {name} lacks {', '.join(absent)}")
    spec["cards"] = json.loads((ROOT / spec["tasks"]).read_text(encoding="utf-8"))["cards"]

    only = spec.get("only")
    if isinstance(only, str):
        try:
            entries = json.loads((ROOT / only).read_text(encoding="utf-8"))["cards"]
            spec["only"] = [card["id"] for card in entries]
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise ValueError(f"{path}: only {only} is not a card file with a cards list") from error
        if not spec["only"]:  # an empty list would fall back to every train card
            raise ValueError(f"{path}: only {only} lists no cards")
    return spec


def expand_runs(spec: dict) -> list[Run]:
    """Every run of the suite: ``train`` cards (or ``only``) x arms x learners x variants x seeds.

    ``spec`` comes from ``load_suite``, so ``only`` is a list of card ids here. Variants apply to
    the arms that have a bundle, not to ``no-rm``. A learner name must be in ``learners``
    (``TBD`` is allowed: it is refused later, except by ``--dry-run``).

    Raises:
        ValueError: If ``only`` or a learner names something unknown, or two runs share a
            name and seed.
    """
    cards = {card["id"]: card for card in spec["cards"]}
    names = spec.get("only") or [name for name, card in cards.items() if card.get("train")]
    unknown = [name for name in names if name not in cards]
    if unknown:
        raise ValueError(f"only names cards that are not in {spec['tasks']}: {', '.join(unknown)}")

    learners = spec.get("compare_learners") or [spec["learner"]]
    unknown = [name for name in learners if name != "TBD" and name not in spec["learners"]]
    if unknown:
        raise ValueError(f"learner {', '.join(unknown)} is not in the learners of {spec['suite']}")

    variants = spec.get("variants") or [None]
    combos = (
        (name, arm, learner, variant, seed)
        for name, arm, learner in product(names, spec["arms"], learners)
        for variant in ([None] if arm == "no-rm" else variants)
        for seed in spec["seeds"]
    )
    runs = [
        Run(
            spec["suite"],
            cards[name],
            arm,
            learner,
            variant,
            seed,
            bundle_path(spec, name, arm, variant),
            spec["learners"].get(learner, {}).get("ram_gb", 0),
        )
        for name, arm, learner, variant, seed in combos
    ]
    runs += mix_runs(spec, cards, learners)
    counts = Counter((run.exp_name, run.seed) for run in runs)
    repeated = [f"{name} seed {seed}" for (name, seed), count in counts.items() if count > 1]
    if repeated:
        raise ValueError(f"runs listed twice (check seeds, only, cards): {'; '.join(repeated)}")
    return runs


def mix_runs(spec: dict, cards: dict[str, dict], learners: list[str]) -> list[Run]:
    """The runs of ``mixes:`` (``{id, cards: [card ids]}``): arms with a bundle x learners x seeds.

    A mix trains one policy on the machines of its cards in alternating episodes
    (``task_bundles`` with ``task_draw: alternate``). Its cards must share the environment
    (family, gym id, observation, layout); they may differ in ``env_kwargs``. The mix has no
    no-RM arm, since without a machine its cards are the same task.

    Raises:
        ValueError: If a mix has fewer than two cards, names an unknown card or has cards whose
            environments differ.
    """
    runs = []
    for mix in spec.get("mixes") or []:
        unknown = [name for name in mix["cards"] if name not in cards]
        if unknown or len(mix["cards"]) < 2:
            raise ValueError(
                f"mix {mix['id']}: needs two or more cards of {spec['tasks']}: {unknown}"
            )
        members = [cards[name] for name in mix["cards"]]
        for key in ("family", "gym_id", "observation", "layout", "layout_seed"):
            if len({json.dumps(member["env"].get(key)) for member in members}) > 1:
                raise ValueError(f"mix {mix['id']}: its cards differ in env.{key}")
        card = {"id": mix["id"], "env": members[0]["env"], "members": members}
        for arm, learner, seed in product(
            [arm for arm in spec["arms"] if arm != "no-rm"], learners, spec["seeds"]
        ):
            bundles = tuple(bundle_path(spec, member["id"], arm, None) for member in members)
            ram_gb = spec["learners"].get(learner, {}).get("ram_gb", 0)
            runs.append(
                Run(spec["suite"], card, arm, learner, None, seed, bundles[0], ram_gb, bundles)
            )
    return runs


# ======================================================================================
#                                      RUN STATUS
# ======================================================================================


def write_atomic(path: Path, text: str) -> None:
    """Write through a temporary file and rename it, so a reader never sees half a file."""
    temp = path.with_name(f"{path.name}.tmp")
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)


def bundle_problem(run: Run) -> tuple[str, str] | None:
    """The run status and the reason when its bundle cannot be trained on now, else None.

    ``no-data``: the bundle folder or a file training needs is missing, or its
    ``<card-id>.status.json`` (beside the folder) says ``pipeline-failed``, or it is an ablation
    variant whose manifest marks it a no-op (the machine equals its source: not trained; the
    ``none`` control stays eligible). ``pending``: that status is ``provider-error`` or
    ``incomplete``, which bundle generation retries.
    """
    problems = (_bundle_problem(bundle) for bundle in run.bundles or (run.bundle,) if bundle)
    return next((problem for problem in problems if problem), None)


def _bundle_problem(bundle: Path) -> tuple[str, str] | None:
    status_file = ROOT / bundle.parent / f"{bundle.name}.status.json"
    record = read_json(status_file)
    status = record.get("status")
    if status == "pipeline-failed":
        return NO_DATA, f"bundle pipeline-failed: {record.get('reason')}"
    if status in BUNDLE_RETRIED:
        return PENDING, f"bundle {status}: {record.get('reason')}"

    if not (ROOT / bundle).is_dir():
        return NO_DATA, "bundle missing"
    missing = [name for name in BUNDLE_FILES if not (ROOT / bundle / name).is_file()]
    if missing:
        return NO_DATA, f"bundle lacks {', '.join(missing)}"

    ablation = ablation_settings(ROOT / bundle)
    if ablation.get("no_op") and ablation.get("off") != NO_PART:
        return NO_DATA, f"ablation no-op: off={ablation.get('off')} changes nothing, not trained"
    return None


def process_alive(folder: Path, run: Run) -> bool:
    """Whether the process named by the run folder (its last part is the pid) is this run's."""
    pid = folder.name.rsplit("-", 1)[1]
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return False
    return b"train-rl" in cmdline and run.exp_name.encode() in cmdline


def run_state(run: Run) -> tuple[str, Path | None, str | None]:
    """The run's status, its latest run folder (None when it has none) and the bundle reason.

    A ``summary.json`` in any of the run's folders means ``finished``, whatever else is recorded;
    a live process means ``running``. Otherwise an unusable bundle makes the run ``no-data`` (or
    ``pending``), also when an old folder exists. The reason (``bundle_problem``'s) is set only
    for those two statuses.
    """
    folders = sorted(
        path
        for path in run.exp_dir.glob(f"seed{run.seed}-*")
        if path.is_dir() and "." not in path.name  # `<folder>.<status>` ones are archived
    )
    finished = [folder for folder in folders if (folder / "summary.json").is_file()]
    if finished:
        return FINISHED, finished[-1], None
    live = [folder for folder in folders if process_alive(folder, run)]
    if live:
        return RUNNING, live[-1], None

    folder = folders[-1] if folders else None
    problem = bundle_problem(run)
    if problem:
        status, reason = problem
        return status, folder, reason
    if folder is None:
        return PENDING, None, None
    if read_json(folder / "resources.json").get("status") == TIMED_OUT:
        return TIMED_OUT, folder, None
    return INTERRUPTED, folder, None


def decide(run: Run, CONFIG: Configuration) -> tuple[str, str]:
    """What a driver does with the run: (action, note).

    The action is ``skip``, ``start``, ``restart``, ``no-data`` or ``pending`` (bundle being
    retried); the note is the run status, or the bundle problem for the last two. A ``timed-out``
    run is skipped unless ``CONFIG.suite_retry_timed_out``.
    """
    status, _, reason = run_state(run)
    if status in (FINISHED, RUNNING) or (status == TIMED_OUT and not CONFIG.suite_retry_timed_out):
        return "skip", status
    if reason:
        return status, reason
    return ("start" if status == PENDING else "restart"), status


# ======================================================================================
#                                     RUN FILES
# ======================================================================================


def run_config(run: Run, spec: dict) -> dict:
    """The ``train-rl`` config of a run: learner config, learner overrides, card, arm.

    Later layers win: the card and the arm decide the protocol, so an override cannot undo them.
    """
    learner = spec["learners"][run.learner]
    config = yaml.safe_load((ROOT / learner["config"]).read_text(encoding="utf-8"))
    config.update(learner.get("overrides", {}))

    env = run.card["env"]
    config.update(
        exp_name=run.exp_name,
        env_family=env["family"],
        gym_id=env["gym_id"],
        env_kwargs=env.get("env_kwargs", {}),
        observation=env["observation"],
        layout=env["layout"],
        layout_seed=env.get("layout_seed"),
        total_timesteps=spec["total_timesteps"],
        success="env",
    )
    if run.bundle is None:
        config["reward_source"] = "env"
    elif run.bundles:  # a mix: each card keeps its own setup and machine
        entries = [
            {"bundle": str(bundle), "env_kwargs": member["env"].get("env_kwargs", {})}
            for bundle, member in zip(run.bundles, run.card["members"], strict=True)
        ]
        config.update(
            reward_source="rm",
            env_kwargs={},
            task_bundles=entries,
            task_draw="alternate",
            time_limit_penalty=0.0,
        )
    else:
        source = spec.get("reward_source", "rm")  # "both" adds the env reward to the RM reward
        config.update(reward_source=source, bundle=str(run.bundle), time_limit_penalty=0.0)
    return config


# ======================================================================================
#                                  SHARED NO-RM RUNS
# ======================================================================================
# The no-RM agent never sees the card text, so one training serves every card whose ``train-rl``
# settings and seed are identical, whatever suite asks. Its owner is, in this order: (a) a
# finished run under the runs root whose *saved* settings match, (b) a run another driver has
# claimed for that key, (c) the first open card of this suite, claimed here. A claim is a file
# per key under the runs root, written under one lock, so two drivers never train one key.


@dataclass(frozen=True)
class Owner:
    """The run a no-RM card gets its model from: ``run`` is set when this suite trains it."""

    exp_name: str
    state: str
    folder: Path | None = None
    run: Run | None = None


def settings_key(settings: dict) -> str:
    """The training settings a run records in its ``config.yaml`` (minus its name), comparable."""
    wanted = {name: settings.get(name) for name in RUN_SETTINGS if name not in SHARE_IGNORED}
    return json.dumps(wanted, sort_keys=True, default=str)


def requested_key(run: Run, spec: dict) -> str:
    """``settings_key`` of what ``train-rl`` would record for this run, defaults included."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "run-config.yaml"
        path.write_text(yaml.safe_dump(run_config(run, spec)), encoding="utf-8")
        config = Configuration(yaml_config_name=str(path), seed=run.seed)
    settings = {name: getattr(config, name) for name in RUN_SETTINGS}
    settings["layout_seed"] = layout_seed(config)
    return settings_key(settings)


def finished_runs() -> dict[str, Path]:
    """Every finished real run folder under the runs root, by its saved ``settings_key``.

    A linked folder (``shared-run.json``) is not a run of its own; later names win a tie.
    """
    found = {}
    for summary in sorted(RUNS_PATH.glob("*/seed*-*/summary.json")):
        folder = summary.parent
        if "." in folder.name or (folder / SHARED_FILE).exists():
            continue
        try:
            saved = yaml.safe_load((folder / "config.yaml").read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if isinstance(saved, dict):
            found[settings_key(saved)] = folder
    return found


def share_groups(runs: list[Run], spec: dict) -> dict[str, list[Run]]:
    """The suite's no-RM runs by requested training key; undecided learners (TBD) stay out."""
    groups: dict[str, list[Run]] = {}
    for run in runs:
        if run.arm == "no-rm" and run.learner in spec["learners"]:
            groups.setdefault(requested_key(run, spec), []).append(run)
    return groups


def claim_path(key: str) -> Path:
    return RUNS_PATH / ".share-claims" / f"{hashlib.sha256(key.encode()).hexdigest()}.json"


def driver_alive(pid: int) -> bool:
    try:
        return b"run-suite" in Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return False


def held_claim(key: str, template: Run, CONFIG: Configuration) -> Run | None:
    """The run that holds the key's claim, or None when there is none or it went stale.

    A claim holds while its driver lives, its run is running, or its run timed out and no
    retry was asked (the owner then stays stopped, and its followers say so).
    """
    record = read_json(claim_path(key))
    if not record:
        return None
    holder = replace(
        template, suite=record["suite"], card={"id": record["card_id"]}, learner=record["learner"]
    )
    state = run_state(holder)[0]
    alive = record["driver_pid"] == os.getpid() or driver_alive(record["driver_pid"])
    stopped_for_good = state == TIMED_OUT and not CONFIG.suite_retry_timed_out
    # A finished holder whose settings did not match is no owner: it never reaches ``finished``.
    return holder if state != FINISHED and (alive or state == RUNNING or stopped_for_good) else None


def find_owner(
    key: str, members: list[Run], finished: dict[str, Path], CONFIG: Configuration, claim: bool
) -> Owner | None:
    """Who trains for this key, or None when every card of the group finished on its own.

    With ``claim`` (a real run, under the claims lock) a newly chosen owner is claimed.
    """
    if key in finished:
        return Owner(finished[key].parent.name, FINISHED, finished[key])

    holder = held_claim(key, members[0], CONFIG)
    if holder is not None:
        own = next((member for member in members if member.exp_name == holder.exp_name), None)
        state, folder, _ = run_state(holder)
        return Owner(holder.exp_name, state, folder, own)

    states = {member.key: run_state(member) for member in members}
    open_members = [member for member in members if states[member.key][0] != FINISHED]
    if not open_members:
        return None
    running = [member for member in open_members if states[member.key][0] == RUNNING]
    trainer = (running or open_members)[0]
    if claim:
        record = {
            "suite": trainer.suite,
            "card_id": trainer.card["id"],
            "learner": trainer.learner,
            "driver_pid": os.getpid(),
        }
        claim_path(key).parent.mkdir(parents=True, exist_ok=True)
        write_atomic(claim_path(key), json.dumps(record, indent=2) + "\n")
    state, folder, _ = states[trainer.key]
    return Owner(trainer.exp_name, state, folder, trainer)


def share_owners(
    runs: list[Run], spec: dict, CONFIG: Configuration, claim: bool = False
) -> dict[tuple[str, int], Owner]:
    """The owner of every no-RM run that has one (the run it trains for itself maps to itself)."""
    finished = finished_runs()
    owners = {}
    for key, members in share_groups(runs, spec).items():
        owner = find_owner(key, members, finished, CONFIG, claim)
        if owner is not None:
            owners.update({member.key: owner for member in members})
    return owners


def claimed_owners(
    runs: list[Run], spec: dict, CONFIG: Configuration
) -> dict[tuple[str, int], Owner]:
    """``share_owners`` that claims the keys it newly gives to this driver, one driver at a time."""
    RUNS_PATH.mkdir(parents=True, exist_ok=True)
    with (RUNS_PATH / ".share-claims.lock").open("a", encoding="utf-8") as claims_lock:
        fcntl.flock(claims_lock, fcntl.LOCK_EX)
        return share_owners(runs, spec, CONFIG, claim=True)


def link_shared(runs: list[Run], owners: dict[tuple[str, int], Owner], spec: dict) -> None:
    """Give each unfinished no-RM run a run folder that links its owner's finished run.

    The folder holds symlinks to the owner's files, except the ones a card writes itself
    (``CARD_OWN_FILES``), and ``shared-run.json`` naming the owner; ``summary.json`` goes in
    last, so the run is ``finished`` only when the folder is complete. The owner's saved
    settings were matched against the request when it was found, so a model trained with other
    settings is never linked.
    """
    for run in runs:
        owner = owners.get(run.key)
        if owner is None or owner.state != FINISHED or run_state(run)[0] == FINISHED:
            continue
        write_run_files(run, spec)
        folder = run.exp_dir / owner.folder.name
        folder.mkdir(exist_ok=True)
        record = {"owner_exp_name": owner.exp_name, "owner_folder": str(owner.folder)}
        write_atomic(folder / SHARED_FILE, json.dumps(record, indent=2) + "\n")
        for item in sorted(owner.folder.iterdir(), key=lambda path: path.name == "summary.json"):
            link = folder / item.name
            if item.name not in CARD_OWN_FILES and not link.is_symlink():
                link.symlink_to(item)
        log(f"{run.exp_name} seed {run.seed} shares the run of {owner.exp_name}")


def write_run_files(run: Run, spec: dict) -> Path:
    """Write the run's ``card.json`` and ``run-config.yaml``; return the config path."""
    run.exp_dir.mkdir(parents=True, exist_ok=True)
    write_atomic(run.exp_dir / "card.json", json.dumps(run.card, indent=2) + "\n")
    if run.bundles:  # a mix's cards, one file each: ``test-rl --judge`` takes one card
        (run.exp_dir / "members").mkdir(exist_ok=True)
        for member in run.card["members"]:
            path = run.exp_dir / "members" / f"{member['id']}.json"
            write_atomic(path, json.dumps(member, indent=2) + "\n")
    config_path = run.exp_dir / "run-config.yaml"
    write_atomic(config_path, yaml.safe_dump(run_config(run, spec), sort_keys=False))
    return config_path


def config_error(config_path: Path) -> str | None:
    """Why ``train-rl`` would reject the config, or None."""
    try:
        Configuration(yaml_config_name=str(config_path))
    except (ValueError, TypeError, OSError) as error:
        return f"{config_path.parent.name}: {error}"
    return None


def archive_old(run: Run) -> None:
    """Rename the run's interrupted or timed-out folder to ``<folder>.<status>``.

    Any other state is left alone: a live process owns its folder, a finished run keeps it.
    """
    status, folder, _ = run_state(run)
    if folder is None or status not in (INTERRUPTED, TIMED_OUT):
        return
    resources = read_json(folder / "resources.json")
    if resources:
        resources["status"] = status
        write_atomic(folder / "resources.json", json.dumps(resources, indent=2) + "\n")
    folder.rename(folder.with_name(f"{folder.name}.{status}"))
    log(f"renamed {folder.name} to {folder.name}.{status}")


# ======================================================================================
#                                    PROCESS CONTROL
# ======================================================================================


def log(message: str) -> None:
    print(f"{datetime.now():%H:%M:%S} {message}", flush=True)


def now_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def die_with_driver(driver_pid: int) -> None:
    """Child side, after fork: the kernel sends SIGTERM when the driver dies.

    Linux ties this to the thread that forked, which is the main (and only) thread. A driver that
    died before ``prctl`` ran is caught by comparing the parent pid.
    """
    LIBC.prctl(PR_SET_PDEATHSIG, signal.SIGTERM)
    if os.getppid() != driver_pid:
        os._exit(1)


def available_gb() -> float:
    """Free RAM in GB (``MemAvailable``)."""
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 1024**2
    raise RuntimeError("MemAvailable missing from /proc/meminfo")


def last_line(path: Path) -> str:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return lines[-1] if lines else "(no output)"


class Child:
    """One running ``train-rl`` process: its sampled memory, run folder and final status."""

    def __init__(self, run: Run, process: subprocess.Popen, log_file: IO[str]) -> None:
        self.run = run
        self.process = process
        self.log_file = log_file
        self.started = time.monotonic()
        self.started_utc = now_utc()
        self.folder: Path | None = None
        self.rss_gb = 0.0
        self.peak_gb = 0.0
        self.stopped_as: str | None = None  # the status we stopped it with, if we did

    @property
    def wall_s(self) -> float:
        return time.monotonic() - self.started

    def sample(self) -> None:
        """Read RSS and the peak (``VmHWM``) from ``/proc``, find the run folder, write resources."""
        if self.folder is None:
            found = list(self.run.exp_dir.glob(f"seed{self.run.seed}-*-{self.process.pid}"))
            self.folder = found[0] if found else None
        try:
            lines = (
                Path(f"/proc/{self.process.pid}/status").read_text(encoding="utf-8").splitlines()
            )
        except OSError:  # already gone: keep the last sample
            lines = []
        kb = {}
        for line in lines:
            name, _, rest = line.partition(":")
            if name in ("VmRSS", "VmHWM"):
                kb[name] = int(rest.split()[0])
        self.rss_gb = kb.get("VmRSS", 0) / 1024**2
        self.peak_gb = max(self.peak_gb, kb.get("VmHWM", 0) / 1024**2)
        if self.process.poll() is None:
            self.write_resources(RUNNING, None)

    def write_resources(self, status: str, exit_code: int | None) -> None:
        """Record the run's resources in its folder; nothing to write before the folder exists."""
        if self.folder is None:
            return
        record = {
            "status": status,
            "exit_code": exit_code,
            "wall_time_s": round(self.wall_s, 1),
            "peak_rss_gb": round(self.peak_gb, 2),
            "started_utc": self.started_utc,
            "ended_utc": None if status == RUNNING else now_utc(),
        }
        write_atomic(self.folder / "resources.json", json.dumps(record, indent=2) + "\n")

    def stop(self, status: str) -> None:
        """Stop this child by its pid: SIGTERM, then SIGKILL after the grace time."""
        if self.stopped_as is None:  # the first reason stays: a later stop must not overwrite it
            self.stopped_as = status
        self.process.terminate()
        try:
            self.process.wait(timeout=KILL_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()

    def settle(self) -> bool:
        """Record the ended child's final status; return True when the run did not end well.

        A ``summary.json`` makes the run ``finished``, even if we stopped it or it exited non-zero.
        """
        code = self.process.returncode
        done = self.folder is not None and (self.folder / "summary.json").is_file()
        status = FINISHED if done else (self.stopped_as or INTERRUPTED)
        self.write_resources(status, code)
        self.log_file.close()
        log(
            f"{status}: {self.run.exp_name} seed {self.run.seed} exit {code}, "
            f"peak {self.peak_gb:.1f} GB, {self.wall_s / 60:.1f} min"
        )
        if self.folder is None and status == INTERRUPTED:
            log(
                f"  no run folder; last output: {last_line(self.run.exp_dir / f'seed{self.run.seed}.log')}"
            )
        return status not in (FINISHED, TIMED_OUT)


class Driver:
    """Start queued runs while slots and RAM allow, sample them, and settle the ended ones."""

    def __init__(
        self,
        CONFIG: Configuration,
        spec: dict,
        queue: list[tuple[Run, str]],
        runs: list[Run],
    ) -> None:
        self.CONFIG = CONFIG
        self.spec = spec
        self.queue = queue
        self.runs = runs
        self.handled = {run.key for run, _ in queue}  # owners this driver already queued
        self.waiting = False  # a no-RM run waits for an owner another driver trains
        self.relink = True
        self.last_link = float("-inf")
        self.active: list[Child] = []
        self.failed = 0
        self.last_wait_log = float("-inf")
        self.time_box_min = CONFIG.suite_time_box_min or spec.get("time_box_min")

    def loop(self) -> bool:
        """Run until the queue and the children are done; True when every run ended well.

        However the loop ends (Ctrl-C, SIGTERM, SIGHUP unless the driver runs under ``nohup``, an
        error), the children still alive are stopped by pid; only a driver killed with SIGKILL
        leaves that to the kernel.
        """
        try:
            while self.relink or self.queue or self.active or self.waiting:
                if self.relink or (time.monotonic() - self.last_link >= LINK_POLL_SECONDS):
                    self.link_ready()
                self.start_ready()
                time.sleep(POLL_SECONDS)
                self.poll()
        except KeyboardInterrupt:
            log("driver interrupted: stopping only its own children, by pid")
            self.failed += 1
        finally:
            for child in self.active:
                child.stop(INTERRUPTED)
            for child in self.active:
                child.settle()
            self.active.clear()
        return self.failed == 0

    def link_ready(self) -> None:
        """Link the no-RM runs whose owner has finished; note whether any still waits for one.

        A run that waited for another driver's owner and becomes its own group's owner (that
        driver died) is claimed and queued here, once, so this driver does not end without it.
        """
        owners = share_owners(self.runs, self.spec, self.CONFIG)
        if any(
            owner.run is run and run.key not in self.handled
            for run in self.runs
            if (owner := owners.get(run.key))
        ):
            owners = claimed_owners(self.runs, self.spec, self.CONFIG)
            for run in self.runs:
                owner = owners.get(run.key)
                if owner is None or owner.run is not run or run.key in self.handled:
                    continue
                self.handled.add(run.key)
                action, _ = decide(run, self.CONFIG)
                if action in ("start", "restart"):
                    log(f"{run.exp_name} seed {run.seed} takes over its group's training")
                    self.queue.append((run, action))
        link_shared(self.runs, owners, self.spec)
        self.waiting = any(
            owner.run is None
            and owner.state in (RUNNING, PENDING)
            and run_state(run)[0] != FINISHED
            for run in self.runs
            if (owner := owners.get(run.key))
        )
        self.relink = False
        self.last_link = time.monotonic()

    def ram_reason(self, run: Run) -> str | None:
        """Why the run must wait for RAM, or None when it fits."""
        budget = self.CONFIG.suite_max_ram_gb
        in_use = sum(child.run.ram_gb for child in self.active)
        if budget is not None and in_use + run.ram_gb > budget:
            return (
                f"needs {run.ram_gb:g} GB on top of {in_use:g} GB running, --max-ram-gb {budget:g}"
            )
        # A running child is still below its peak: keep the rest of its estimate free.
        reserved = sum(max(0.0, child.run.ram_gb - child.rss_gb) for child in self.active)
        free = available_gb() - reserved
        if free < run.ram_gb:
            return f"needs {run.ram_gb:g} GB, only {free:.1f} GB free after the running runs' share"
        return None

    def start_ready(self) -> None:
        while self.queue and len(self.active) < self.CONFIG.suite_parallel:
            run, action = self.queue[0]
            reason = self.ram_reason(run)
            if reason:
                if time.monotonic() - self.last_wait_log >= WAIT_LOG_SECONDS:
                    log(f"waiting: {run.exp_name} seed {run.seed} {reason}")
                    self.last_wait_log = time.monotonic()
                return
            self.queue.pop(0)
            self.launch(run, action)

    def launch(self, run: Run, action: str) -> None:
        config_path = write_run_files(run, self.spec)
        error = config_error(config_path)
        if error:
            log(f"refused: {error}")
            self.failed += 1
            return
        if action == "restart":
            archive_old(run)

        log_file = (run.exp_dir / f"seed{run.seed}.log").open("a", encoding="utf-8")
        process = subprocess.Popen(  # noqa: S603  approved: fixed argv built here, no shell
            [
                sys.executable,
                "app/main.py",
                "train-rl",
                "--config",
                str(config_path),
                "--seed",
                str(run.seed),
            ],
            cwd=ROOT,
            env={**os.environ, "OMP_NUM_THREADS": OMP_THREADS, "PYTHONUNBUFFERED": "1"},
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,  # Ctrl-C reaches the driver only, which then stops its children
            preexec_fn=partial(die_with_driver, os.getpid()),  # single-threaded driver: safe
        )
        self.active.append(Child(run, process, log_file))
        log(f"started {run.exp_name} seed {run.seed} pid {process.pid}")

    def poll(self) -> None:
        for child in list(self.active):
            child.sample()
            if child.process.poll() is None:
                if not (self.time_box_min and child.wall_s > self.time_box_min * 60):
                    continue
                log(f"time box of {self.time_box_min:g} min: stopping pid {child.process.pid}")
                child.write_resources(TIMED_OUT, None)  # first: a driver dying now still leaves it
                child.stop(TIMED_OUT)
            self.failed += child.settle()
            self.relink = True  # an owner may have finished
            self.active.remove(child)


# ======================================================================================
#                                      PUBLIC API
# ======================================================================================


def _raise_interrupt(_signal: int, _frame: object) -> None:
    raise KeyboardInterrupt


def plan(
    runs: list[Run], CONFIG: Configuration, owners: dict[tuple[str, int], Owner]
) -> list[tuple[Run, str]]:
    """Print what happens to each run; return the runs to train, with ``start`` or ``restart``.

    A no-RM run whose owner is another run (``share_owners``) is not trained: ``share`` until
    its owner has finished and the run is linked, then ``skip``. The note says who owns it and
    what state that run is in.
    """
    queue, counts = [], Counter()
    for run in runs:
        owner = owners.get(run.key)
        if owner is not None and owner.run is not run:
            status = run_state(run)[0]
            action = "skip" if status == FINISHED else "share"
            note = status if status == FINISHED else f"owner {owner.exp_name} is {owner.state}"
        else:
            action, note = decide(run, CONFIG)
        print(f"{action:<8} {run.exp_name} seed {run.seed} ({note})")
        counts[action] += 1
        if action in ("start", "restart"):
            queue.append((run, action))
    print(
        f"{len(runs)} runs: " + ", ".join(f"{count} {action}" for action, count in counts.items())
    )
    return queue


def run_suite(CONFIG: Configuration) -> bool:
    """Train the suite named by ``CONFIG.suite``; return True when every started run ended well.

    With ``CONFIG.suite_dry_run`` it only lists what would happen: no lock, nothing written.
    A second driver on the same suite logs why and returns False.

    Raises:
        ValueError: If ``--suite`` is missing, the runs.yaml is malformed, or its learner is TBD
            on a real run.
    """
    if CONFIG.suite is None:
        raise ValueError("run-suite requires --suite")
    spec = load_suite(CONFIG.suite)
    runs = expand_runs(spec)
    if not CONFIG.suite_dry_run and any(run.learner == "TBD" for run in runs):
        raise ValueError("learner is TBD: set dqn or ppo in the runs.yaml after the pilot")
    if CONFIG.suite_parallel < 1:
        raise ValueError("--parallel must be at least 1")

    if CONFIG.suite_dry_run:
        plan(runs, CONFIG, share_owners(runs, spec, CONFIG))
        return True

    # The lock is held while this file is open: it ends with the driver, however it ends.
    RUNS_PATH.mkdir(parents=True, exist_ok=True)
    lock_path = RUNS_PATH / f"bench__{spec['suite']}.lock"
    with lock_path.open("a", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log(
                f"another run-suite already drives suite {spec['suite']} (lock {lock_path}): exiting"
            )
            return False

        queue = plan(runs, CONFIG, claimed_owners(runs, spec, CONFIG))
        signal.signal(signal.SIGTERM, _raise_interrupt)
        if signal.getsignal(signal.SIGHUP) == signal.SIG_DFL:  # under nohup it is ignored: keep it
            signal.signal(signal.SIGHUP, _raise_interrupt)
        return Driver(CONFIG, spec, queue, runs).loop()
