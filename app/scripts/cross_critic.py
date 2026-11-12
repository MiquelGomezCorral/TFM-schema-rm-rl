"""Judge every generated machine with the other pipeline's critic."""

import hashlib
import json
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.arm_fm import load_bundle, review_reward_machine
from src.compiler import parse_paper_reward_machine
from src.config import Configuration
from src.models import EnvironmentDescription, EnvironmentValidationError
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
    and the identity of what was judged (see ``_identity``), so a regenerated machine, another
    critic model or another direction is judged again and its old result removed. Launching
    stops once ``max_calls`` requests were sent; requests already running finish, so the count
    can pass it by up to ``parallel``. A pipeline-failed bundle is judged on its last candidate
    only when that candidate parses; otherwise it is skipped with the parser error and no
    request is sent. Raises ``ValueError`` when no bundle is one this critic judges, and
    ``RuntimeError`` after the run when any bundle could not be judged.
    """
    if direction not in JUDGED_RM_MODE:
        raise ValueError(f"--critic must be one of {', '.join(JUDGED_RM_MODE)}: {direction!r}")
    if not CONFIG.critic_model:
        raise ValueError("cross-critic needs a critic model; set the provider's critic variable")
    pending, eligible, unparseable = _pending(bundles, direction, CONFIG.critic_model)
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
    if unparseable:
        print(
            f"critic {direction}: {unparseable} not judged, the last candidate does not parse",
            flush=True,
        )
    if "failed" in outcomes:
        raise RuntimeError(
            f"{outcomes.count('failed')} bundle(s) were not judged; run again to retry them"
        )


def _pending(bundles: Path, direction: str, critic_model: str) -> tuple[list[Path], int, int]:
    """Return the bundles to judge, the eligible count and the unparseable-last-candidate count.

    A bundle is eligible when its ``rm_mode`` is the one this critic judges. It stays pending
    unless its result already holds the bundle's current identity; a result with another
    identity is removed here, so it can neither be counted nor outlive a failed rejudgment.
    A bundle whose last candidate does not parse is never pending and loses its result, which
    judged an older candidate. The reason for every skip is printed.
    """
    pending = []
    eligible = unparseable = 0
    for directory in sorted(
        path for path in bundles.iterdir() if (path / "manifest.json").is_file()
    ):
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("rm_mode") != JUDGED_RM_MODE[direction]:
            print(
                f"{directory.name}: skipped (rm_mode is not {JUDGED_RM_MODE[direction]})",
                flush=True,
            )
            continue
        eligible += 1
        identity = _identity(directory, direction, critic_model)
        parse_error = _last_candidate_error(directory, manifest)
        if identity is None:
            print(f"{directory.name}: skipped (no reward machine)", flush=True)
        elif parse_error:
            unparseable += 1
            (directory / RESULT_FILE).unlink(missing_ok=True)
            print(
                f"{directory.name}: skipped (last candidate does not parse: {parse_error})",
                flush=True,
            )
        elif _stored_identity(directory) == identity:
            print(f"{directory.name}: skipped (already judged)", flush=True)
        else:
            (directory / RESULT_FILE).unlink(missing_ok=True)
            pending.append(directory)
    return pending, eligible, unparseable


def _last_candidate_error(directory: Path, manifest: dict) -> str | None:
    """Return the parser error of a pipeline-failed bundle's last candidate, else None.

    A pipeline-failed ARM-FM bundle has Reward Machine attempts and none accepted. Its
    ``reward_machine.txt`` is the last candidate that parsed, which is an older one when the
    last candidate did not. Any other bundle (accepted attempt, compiler attempts, no
    ``attempts.json``) returns None.
    """
    try:
        attempts = json.loads((directory / "attempts.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    rounds = [item for item in attempts if item.get("stage") == "reward_machine"]
    if not rounds or any(item.get("status") == "accepted" for item in rounds):
        return None
    try:
        parse_paper_reward_machine(
            rounds[-1].get("candidate", ""),
            propositions=tuple(manifest["proposition_semantics"]),
            require_final_states=True,
        )
    except Exception as error:  # the generation loop records any failure as a failed attempt
        return f"{type(error).__name__}: {' '.join(str(error).split())[:100]}"
    return None


def _identity(directory: Path, direction: str, critic_model: str) -> str | None:
    """Return the identity of what a verdict is about, or None for a bundle without a machine.

    It hashes the task and the machine text of the bundle, the environment text as the critic
    reads it (the live environment file, loaded as ``_judge`` loads it; empty when unreadable or
    invalid, which ``_judge`` then reports as not judged), the critic model and the direction: a
    verdict stands only while all of them are unchanged.
    """
    machine_file = directory / "reward_machine.txt"
    if not machine_file.is_file():
        return None
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    try:
        environment = EnvironmentDescription.from_file(
            manifest["environment"], code=direction == "arm-fm"
        ).markdown
    except EnvironmentValidationError:  # ``from_file`` wraps a read error in this one
        environment = ""
    parts = (
        manifest.get("task", ""),
        environment,
        machine_file.read_text(encoding="utf-8"),
        critic_model,
        direction,
    )
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()


def _stored_identity(directory: Path) -> str | None:
    """Return the identity a bundle's existing result judged, if it has a readable one."""
    try:
        return json.loads((directory / RESULT_FILE).read_text(encoding="utf-8")).get(
            "judged_sha256"
        )
    except (OSError, json.JSONDecodeError):
        return None


def _judge(CONFIG: Configuration, directory: Path, direction: str) -> tuple[str, int]:
    """Judge one bundle and write its result; return ``judged`` or ``failed`` and the requests.

    A failure is printed, not raised: one bundle must not stop the others. The request count
    includes the requests of a judgment that failed.
    """
    engine = None
    outcome = "failed"
    try:
        identity = _identity(directory, direction, CONFIG.critic_model)
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
            "judged_sha256": identity,
            "information_note": INFORMATION_NOTES[direction],
        }
        (directory / RESULT_FILE).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(f"{directory.name}: {verdict}", flush=True)
        outcome = "judged"
    except Exception as error:
        print(f"{directory.name}: not judged ({type(error).__name__}: {error})", flush=True)
    return outcome, len(engine.calls) if engine is not None else 0


def _print_summary(bundles: Path) -> None:
    """Print the verdict counts of every direction found under ``bundles``, never pooled.

    Only a verdict about the bundle as it is now counts; the others get a ``stale`` line.
    """
    counts: dict[str, Counter[str]] = {}
    stale: Counter[str] = Counter()
    for path in sorted(bundles.glob(f"*/{RESULT_FILE}")):
        record = json.loads(path.read_text(encoding="utf-8"))
        direction = record["direction"]
        if record.get("judged_sha256") != _identity(path.parent, direction, record["critic_model"]):
            stale[direction] += 1
        else:
            counts.setdefault(direction, Counter())[record["verdict"]] += 1
    for direction, verdicts in sorted(counts.items()):
        total = sum(verdicts.values())
        print(
            f"critic {direction}: {total} judged, {verdicts['accepted']} accepted, "
            f"{verdicts['rejected']} rejected",
            flush=True,
        )
    for direction, number in sorted(stale.items()):
        print(f"critic {direction}: {number} stale, not counted (the bundle changed)", flush=True)
