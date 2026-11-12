"""Generate one bundle per task card for one arm, in parallel, with a status file per card."""

import json
import re
import subprocess
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from src.arm_fm import BundleValidationError, load_bundle
from src.config import Configuration

MAIN = Path(__file__).resolve().parents[1] / "main.py"

# Counted Reward Machine tries in both arms; what one try counts differs, see REPRODUCE.md.
RM_ATTEMPTS = 10

# The ``generate-larm`` flags of each arm; ARM-FM judges with the critic model, as FARM does.
ARM_FLAGS = {
    "farm": ("--mode", "compiler", "--attempts", str(RM_ATTEMPTS)),
    "arm-fm": ("--mode", "arm-fm", "--arm-fm-critic", "--attempts", str(RM_ATTEMPTS)),
}

# What a provider failure looks like in the final error text (OpenAI SDK wording), by cause:
# connection loss ("Connection error", "APIConnectionError", "Connection refused"); timeouts
# ("Request timed out", HTTP 408); quota and rate limits (402, 429); auth and permission
# (401, 403), kept because this provider reports an exhausted quota that way; a sticky 400,
# seen in earlier benchmark runs; and server errors (5xx). Content failures (critic
# rejections, invalid candidates) never carry these.
PROVIDER_ERROR = re.compile(
    r"Connection error|APIConnectionError|Request timed out|Connection refused"
    r"|Error code: (?:400|401|402|403|408|429|5\d\d)"
)
RESPONSES_FILE = "raw_responses.json"  # a bundle's per-call records
LOG_TAIL_CHARS = 4000
EMBEDDINGS_PENDING = "generation done, embeddings pending"


@dataclass(frozen=True)
class SuiteOptions:
    """The ``generate-suite`` settings."""

    tasks: Path
    arm: str
    output: Path
    only: tuple[str, ...]
    paraphrases: bool
    parallel: int
    max_calls: int | None
    deadline_min: float | None
    retry_failed: bool


@dataclass(frozen=True)
class Job:
    """One bundle to generate: a card's task or one of its paraphrases."""

    id: str
    environment: str
    task: str


def generate_suite(options: SuiteOptions) -> None:
    """Generate the missing bundles of one suite and one arm, then embed them one at a time.

    A card is skipped when its bundle is complete, or its status is ``pipeline-failed`` without
    ``retry_failed``; ``provider-error`` and ``incomplete`` cards run again. A bundle whose
    generation finished but has no embeddings only runs the embedding pass. Launching stops
    when the calls of the ``generate-larm`` runs this call made reach ``max_calls``, or when
    ``deadline_min`` minutes passed; running cards finish, so the count can pass the limit by
    up to ``parallel`` cards. Each card's status file is written as soon as its generation,
    and again its embedding, ends, so an interrupted call keeps what it finished.
    """
    if options.arm not in ARM_FLAGS:
        raise ValueError(f"--arm must be one of {', '.join(ARM_FLAGS)}: {options.arm!r}")
    options.output.mkdir(parents=True, exist_ok=True)
    work = [job for job in _load_jobs(options) if _needs_work(job, options)]
    print(f"{len(work)} bundle(s) to run for arm {options.arm}", flush=True)

    deadline = (
        None if options.deadline_min is None else time.monotonic() + options.deadline_min * 60
    )
    spent = 0
    lock = threading.Lock()

    def generate(job: Job) -> dict | None:
        nonlocal spent
        with lock:
            over_budget = options.max_calls is not None and spent >= options.max_calls
        if over_budget or (deadline is not None and time.monotonic() > deadline):
            return None
        result, new_calls = _generate(job, options)
        _write_status(job, options, result)
        with lock:
            spent += new_calls
        return result

    with ThreadPoolExecutor(max_workers=options.parallel) as pool:
        results = list(pool.map(generate, work))

    outcomes = {}
    for job, result in zip(work, results, strict=True):
        if result is None:
            print(f"{job.id}: not launched (cap or deadline)", flush=True)
            continue
        if result["reason"] == EMBEDDINGS_PENDING:
            result = _embed(job, options, result)
            _write_status(job, options, result)
        outcomes[job.id] = result["status"]
        _print_job(job, result)
    counts = ", ".join(f"{n} {status}" for status, n in Counter(outcomes.values()).items())
    print(f"done: {counts or 'nothing run'}; {results.count(None)} not launched", flush=True)


# ======================================================================================
#                                         CARDS
# ======================================================================================


def _load_jobs(options: SuiteOptions) -> list[Job]:
    """Read the task cards and return their jobs, with paraphrases when asked."""
    data = json.loads(options.tasks.read_text(encoding="utf-8"))
    if data.get("schema") != 1 or not isinstance(data.get("cards"), list):
        raise ValueError(f"{options.tasks}: expected a task card file with schema 1 and cards")
    jobs = []
    for card in data["cards"]:
        card_id, task = card.get("id"), card.get("task")
        environment = (card.get("env") or {}).get("description")
        if not all(
            isinstance(value, str) and value.strip() for value in (card_id, task, environment)
        ):
            raise ValueError(
                f"{options.tasks}: card {card_id!r} needs id, task and env.description"
            )
        jobs.append(Job(card_id, environment, task))
        if options.paraphrases:
            for number, paraphrase in enumerate(card.get("paraphrases", []), start=1):
                jobs.append(Job(f"{card_id}~p{number}", environment, paraphrase))
    if options.only:
        known = {job.id for job in jobs} | {job.id.split("~")[0] for job in jobs}
        unknown = set(options.only) - known
        if unknown:
            raise ValueError(f"--only names unknown card(s): {', '.join(sorted(unknown))}")
        jobs = [job for job in jobs if {job.id, job.id.split("~")[0]} & set(options.only)]
    return jobs


def _needs_work(job: Job, options: SuiteOptions) -> bool:
    """Apply the skip rules; a complete bundle without a status file gets its status written."""
    directory = options.output / job.id
    previous = _read_status(job, options).get("status")
    if _bundle_state(directory) == "complete":
        if previous != "complete":
            _write_status(job, options, _status("complete", None, job, options))
        print(f"{job.id}: complete (skipped)", flush=True)
        return False
    if previous == "pipeline-failed" and not options.retry_failed:
        print(f"{job.id}: pipeline-failed (skipped; --retry-failed runs it again)", flush=True)
        return False
    return True


# ======================================================================================
#                                    ONE BUNDLE
# ======================================================================================


def _generate(job: Job, options: SuiteOptions) -> tuple[dict, int]:
    """Run ``generate-larm`` for one job unless its generation is already done.

    Returns the status record and the requests this run made. Those are the records of the
    bundle's ``raw_responses.json`` when the run rewrote it, else none: a run that saved
    nothing leaves the previous run's file, whose requests were counted then. A finished
    generation without embeddings is ``incomplete`` with the reason ``EMBEDDINGS_PENDING``,
    which the embedding pass picks up.
    """
    directory = options.output / job.id
    started = time.monotonic()
    if _bundle_state(directory) == "generated":
        return _status("incomplete", EMBEDDINGS_PENDING, job, options, started), 0
    command = [
        sys.executable,
        str(MAIN),
        "generate-larm",
        *ARM_FLAGS[options.arm],
        "--environment",
        job.environment,
        "--task",
        job.task,
        "--bundle",
        str(directory),
    ]
    if directory.exists():
        command.append("--overwrite")
    responses = directory / RESPONSES_FILE
    before = _file_stamp(responses)
    exit_code = _run(command, _log_path(job, options), append=False)
    state = _bundle_state(directory)
    if exit_code == 0 and state == "complete":
        status, reason = "complete", None
    elif exit_code == 0 and state == "generated":
        status, reason = "incomplete", EMBEDDINGS_PENDING
    else:
        status, reason = _classify_failure(directory, _log_path(job, options))
    result = _status(status, reason, job, options, started)
    return result, result["calls"] if _file_stamp(responses) != before else 0


def _embed(job: Job, options: SuiteOptions, result: dict) -> dict:
    """Embed one generated bundle through the shared embedding server; mark it complete."""
    directory = options.output / job.id
    started = time.monotonic()
    command = [
        sys.executable,
        str(MAIN),
        "embed-larm",
        "--bundle",
        str(directory),
        "--embedding-server",
    ]
    exit_code = _run(command, _log_path(job, options), append=True)
    wall = round(result["wall_time_s"] + time.monotonic() - started, 1)
    if exit_code == 0 and _bundle_state(directory) == "complete":
        return {**result, "status": "complete", "reason": None, "wall_time_s": wall}
    reason = _last_line(_log_path(job, options)) or "embed-larm failed"
    return {**result, "status": "incomplete", "reason": reason, "wall_time_s": wall}


def _run(command: list[str], log: Path, *, append: bool) -> int:
    """Run one command in the repository root with its output in ``log``; return its exit code."""
    with log.open("a" if append else "w", encoding="utf-8") as handle:
        handle.write(f"$ {' '.join(command)}\n")
        handle.flush()
        completed = subprocess.run(  # noqa: S603  approved: argv of this app's own commands, no shell
            command,
            cwd=Configuration.WORKSPACE_PATH,
            stdout=handle,
            stderr=subprocess.STDOUT,
            check=False,
        )
    return completed.returncode


def _classify_failure(directory: Path, log: Path) -> tuple[str, str]:
    """Name a failed run ``provider-error``, ``pipeline-failed`` or ``incomplete``, with why.

    A provider error shows in the final error text of the run: the log tail, and for the
    ``arm-fm`` path (which folds provider errors into failed attempts) the last attempt's error.
    A failed run that left a bundle on disk is a pipeline failure; one that left nothing
    crashed before generating, so it stays ``incomplete`` and the next run tries it again.
    """
    tail = log.read_text(encoding="utf-8", errors="replace")[-LOG_TAIL_CHARS:]
    attempts = _read_json(directory / "attempts.json", [])
    last_error = (
        attempts[-1].get("error", "") if attempts and attempts[-1].get("status") == "failed" else ""
    )
    reason = _last_line(log)
    if PROVIDER_ERROR.search(tail) or PROVIDER_ERROR.search(last_error):
        return "provider-error", reason
    if (directory / "manifest.json").exists():
        return "pipeline-failed", reason
    return "incomplete", reason


def _bundle_state(directory: Path) -> str:
    """Return ``complete``, ``generated`` (no embeddings yet) or ``missing`` for a bundle folder."""
    try:
        bundle = load_bundle(directory)
    except BundleValidationError:
        return "missing"
    if bundle.complete:
        return "complete"
    # Diagnostics mean a half-saved bundle (a manifest written before its stage files).
    if bundle.validate():
        return "missing"
    return "generated" if bundle.generation_complete else "missing"


# ======================================================================================
#                                  STATUS FILES AND LOGS
# ======================================================================================


def _log_path(job: Job, options: SuiteOptions) -> Path:
    return options.output / f"{job.id}.log"


def _status_path(job: Job, options: SuiteOptions) -> Path:
    return options.output / f"{job.id}.status.json"


def _read_status(job: Job, options: SuiteOptions) -> dict:
    return _read_json(_status_path(job, options), {})


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _status(
    status: str, reason: str | None, job: Job, options: SuiteOptions, started: float | None = None
) -> dict:
    """Build one status record; the calls come from the per-call records of the bundle."""
    responses = _read_json(options.output / job.id / RESPONSES_FILE, [])
    return {
        "status": status,
        "reason": reason,
        "calls": sum("model_requested" in item for item in responses),
        "wall_time_s": None if started is None else round(time.monotonic() - started, 1),
        "log": str(_log_path(job, options)),
    }


def _file_stamp(path: Path) -> tuple[int, int] | None:
    """Return the size and modification time of a file, or None when it does not exist."""
    try:
        info = path.stat()
    except OSError:
        return None
    return info.st_size, info.st_mtime_ns


def _write_status(job: Job, options: SuiteOptions, result: dict) -> None:
    _status_path(job, options).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def _last_line(log: Path) -> str:
    lines = [
        line.strip() for line in log.read_text(encoding="utf-8", errors="replace").splitlines()
    ]
    return next((line for line in reversed(lines) if line), "")


def _print_job(job: Job, result: dict) -> None:
    detail = f" - {result['reason']}" if result["reason"] else ""
    print(
        f"{job.id}: {result['status']} ({result['calls']} calls, {result['wall_time_s']}s){detail}",
        flush=True,
    )
