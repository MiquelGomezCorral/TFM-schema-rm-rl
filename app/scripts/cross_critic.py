"""Judge every generated machine with the other pipeline's critic."""

import hashlib
import json
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.arm_fm import load_bundle, review_reward_machine
from src.config import Configuration
from src.models import EnvironmentDescription
from src.utils import get_engine

# The only file this command adds to a bundle.
RESULT_FILE = "cross_critic.json"

# Which bundles each critic judges: the other pipeline's, by the ``rm_mode`` they record.
JUDGED_RM_MODE = {"farm": "arm-fm", "arm-fm": "compiler"}

# FARM's critic reviews compiled clauses; a machine written directly has none.
DIRECT_NOTE = "The machine was written directly by a model; no clauses were compiled from it."
INFORMATION_NOTES = {
    "farm": (
        "FARM's critic saw the environment facts, the task and the machine text with an empty "
        "clause list and a note that the machine was written directly; it cannot check clause "
        "fidelity, which it normally judges."
    ),
    "arm-fm": (
        "ARM-FM's critic saw the environment facts and labeling code, the task and the machine "
        "text only; it did not see the clauses or the compiler warnings that FARM's critic reads."
    ),
}


def cross_critic(
    CONFIG: Configuration, bundles: Path, direction: str, max_calls: int | None, parallel: int
) -> None:
    """Write ``cross_critic.json`` into each bundle the critic has not judged yet.

    ``direction`` names the critic: ``farm`` judges ARM-FM bundles and ``arm-fm`` judges FARM
    bundles. ``cross_critic.json`` is the only file added; it holds the verdict, the raw reply
    and the identity of the machine judged, so a regenerated machine is judged again. Launching
    stops once ``max_calls`` requests were sent; requests already running finish, so the count
    can pass it by up to ``parallel``. Raises ``ValueError`` when no bundle is one this critic
    judges, and ``RuntimeError`` after the run when any bundle could not be judged.
    """
    if direction not in JUDGED_RM_MODE:
        raise ValueError(f"--critic must be one of {', '.join(JUDGED_RM_MODE)}: {direction!r}")
    if not CONFIG.critic_model:
        raise ValueError("cross-critic needs a critic model; set the provider's critic variable")
    pending, eligible = _pending(bundles, direction)
    if not eligible:
        raise ValueError(
            f"--critic {direction} judges bundles with rm_mode {JUDGED_RM_MODE[direction]!r}; "
            f"none under {bundles}"
        )
    used = 0
    lock = threading.Lock()

    def judge(directory: Path) -> str:
        nonlocal used
        with lock:
            if max_calls is not None and used >= max_calls:
                return "stopped"
        outcome, sent = _judge(CONFIG, directory, direction)
        with lock:
            used += sent
        return outcome

    with ThreadPoolExecutor(max_workers=parallel) as pool:
        outcomes = list(pool.map(judge, pending))
    if "stopped" in outcomes:
        print(f"stopped at --max-calls: {outcomes.count('stopped')} bundle(s) left", flush=True)
    _print_summary(bundles)
    if "failed" in outcomes:
        raise RuntimeError(
            f"{outcomes.count('failed')} bundle(s) were not judged; run again to retry them"
        )


def _pending(bundles: Path, direction: str) -> tuple[list[Path], int]:
    """Return the bundles this critic still has to judge and how many it is eligible for.

    A bundle is eligible when its ``rm_mode`` is the one this critic judges. It stays pending
    unless it was judged already, in this direction and for this very task and machine. The
    reason for every skip is printed.
    """
    pending = []
    eligible = 0
    for directory in sorted(
        path for path in bundles.iterdir() if (path / "manifest.json").is_file()
    ):
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        machine_file = directory / "reward_machine.txt"
        if manifest.get("rm_mode") != JUDGED_RM_MODE[direction]:
            reason = f"rm_mode is not {JUDGED_RM_MODE[direction]}"
        elif not machine_file.is_file():
            eligible += 1
            reason = "no reward machine"
        else:
            eligible += 1
            identity = _identity(manifest.get("task", ""), machine_file.read_text(encoding="utf-8"))
            if _judged(directory, direction) == identity:
                reason = "already judged"
            else:
                pending.append(directory)
                continue
        print(f"{directory.name}: skipped ({reason})", flush=True)
    return pending, eligible


def _identity(task: str, machine: str) -> str:
    """Return a short identity of the task and machine a verdict is about."""
    return hashlib.sha256(f"{task}\0{machine}".encode()).hexdigest()


def _judged(directory: Path, direction: str) -> str | None:
    """Return the identity a bundle's existing result in this direction judged, if any."""
    try:
        record = json.loads((directory / RESULT_FILE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return record.get("judged_sha256") if record.get("direction") == direction else None


def _judge(CONFIG: Configuration, directory: Path, direction: str) -> tuple[str, int]:
    """Judge one bundle and write its result; return ``judged`` or ``failed`` and the requests.

    A failure is printed, not raised: one bundle must not stop the others. The request count
    includes the requests of a judgment that failed.
    """
    engine = None
    outcome = "failed"
    try:
        bundle = load_bundle(directory)
        task = bundle.manifest.task
        machine = (directory / "reward_machine.txt").read_text(encoding="utf-8")
        farm = direction == "farm"
        # Each critic reads the environment as its own pipeline gives it: FARM's without the code.
        environment = EnvironmentDescription.from_file(bundle.manifest.environment, code=not farm)
        engine = get_engine(CONFIG, environment, CONFIG.critic_model)
        if farm:
            result = engine.review_candidate(task, "[]", machine, (DIRECT_NOTE,))
            accepted, feedback = result.accepted, result.feedback
        else:
            accepted, feedback = review_reward_machine(engine, environment.markdown, task, machine)
        verdict = "accepted" if accepted else "rejected"
        record = {
            "direction": direction,
            "critic_model": CONFIG.critic_model,
            "verdict": verdict,
            "flags": [] if accepted else [feedback],
            "raw_reply": engine.last_reply or "",
            "raw_reply_path": None,
            "judged_sha256": _identity(task, machine),
            "information_note": INFORMATION_NOTES[direction],
        }
        (directory / RESULT_FILE).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(f"{directory.name}: {verdict}", flush=True)
        outcome = "judged"
    except Exception as error:
        print(f"{directory.name}: not judged ({type(error).__name__}: {error})", flush=True)
    return outcome, len(engine.calls) if engine is not None else 0


def _print_summary(bundles: Path) -> None:
    """Print the verdict counts of every direction found under ``bundles``, never pooled."""
    counts: dict[str, Counter[str]] = {}
    for path in sorted(bundles.glob(f"*/{RESULT_FILE}")):
        record = json.loads(path.read_text(encoding="utf-8"))
        counts.setdefault(record["direction"], Counter())[record["verdict"]] += 1
    for direction, verdicts in sorted(counts.items()):
        total = sum(verdicts.values())
        print(
            f"critic {direction}: {total} judged, {verdicts['accepted']} accepted, "
            f"{verdicts['rejected']} rejected",
            flush=True,
        )
