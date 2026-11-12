"""Check every bundle's labeling against a trace bank, then repair the failed ones.

The check comes first and is the measurement: it class each bundle (``missing``, ``load``,
``crash``, ``wrong``, ``ok``) before any repair and writes a record beside it. The repair loop
then asks the bundle's own small generator model for a better labeling, with the failure as
feedback. A bundle the loop leaves ``unfixed`` is handed to an agent outside this command; a
later run notices the edited labeling, checks it and marks it ``fixed-by-agent``.

A repaired bundle whose generation stopped at labeling still lacks descriptions and embeddings, so
its ``<name>.status.json`` says ``pipeline-failed`` and ``run-suite`` has no data for it. The run
ends by finishing those bundles: the arm's own description stage with the bundle's generator, then
``embed-larm`` through the embedding server, then the status goes to ``complete`` with the
generation outcome kept in ``generation_status`` and ``generation_reason``. It also finishes
bundles repaired by an earlier run or by the agent step, and resumes one that stopped half way.
"""

import json
import time
from collections import defaultdict
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from src.arm_fm.artifacts import ArtifactBundle
from src.arm_fm.generation import StageAttempt, request_state_descriptions
from src.benchmark import CardError
from src.benchmark.labeling_repair import (
    DONE_OUTCOMES,
    FIXED,
    FIXED_BY_AGENT,
    OK,
    PENDING,
    PROVIDER_ERROR,
    SUMMARY_FILE,
    UNFIXED,
    UNREPAIRABLE,
    Check,
    Generator,
    check_labeling,
    finished_status,
    generator_model,
    generator_system_prompt,
    needs_finish,
    new_record,
    read_record,
    repair_rounds,
    sha256,
    start_repair,
    status_path,
    summarize,
    unrepairable_reason,
    write_record,
)
from src.benchmark.traces import (
    BundleRef,
    TraceRecord,
    find_bundles,
    load_bank,
    load_machine_bundle,
    read_json,
    write_json,
)
from src.config import Configuration
from src.models import EnvironmentDescription
from src.utils import get_engine, print_warning

from .embed_larm import embed_larm


@dataclass
class Job:
    """One bundle the loop has to repair, with its record and the check that started it."""

    ref: BundleRef
    bundle: ArtifactBundle
    records: list[TraceRecord]
    record: dict
    check: Check


def repair_labeling(
    CONFIG: Configuration, traces: Path, bundles: Path, only: tuple[str, ...], check_only: bool
) -> None:
    """Check the labeling of every bundle under ``bundles`` and repair the ones that fail.

    ``traces`` is a ``trace-bank`` output; ``only`` limits the run to card ids or bundle names.
    Every bundle gets a record beside its folder and the run writes ``labeling_check.json`` under
    ``bundles``. The loop (``CONFIG.repair_iterations`` rounds, ``CONFIG.repair_parallel``
    bundles at once) and then the finish step for repaired bundles (see the module text) run
    unless ``check_only``. A bundle that has a record is not checked again, except to notice an
    edited labeling.

    Raises:
        RuntimeError: After writing the summary, when a provider failure stopped a bundle of
            this run, or a repaired bundle could not be finished; running again continues it.
    """
    try:
        _, records = load_bank(traces)
    except CardError as error:
        raise SystemExit(f"error: {error}") from error
    by_card: dict[str, list[TraceRecord]] = defaultdict(list)
    for record in records:
        by_card[record.card_id].append(record)

    selected = [
        ref for ref in find_bundles(bundles) if not only or {ref.card_id, ref.name} & set(only)
    ]
    skipped: dict[str, str] = {}
    jobs = []
    for ref in selected:
        job = _open_job(ref, by_card, skipped)
        if job is not None:
            jobs.append(job)
    for key, reason in skipped.items():
        print(f"{key}: skipped ({reason})", flush=True)

    outcomes: list[str] = []
    unfinished: list[str] = []
    if not check_only:
        with ThreadPoolExecutor(max_workers=CONFIG.repair_parallel) as pool:
            outcomes = list(pool.map(lambda job: _repair_job(CONFIG, job), jobs))
        unfinished = _finish_bundles(CONFIG, selected)
    summary = summarize(bundles, skipped)
    write_json(bundles / SUMMARY_FILE, summary, indent=2)
    _print_summary(summary, bundles)
    if (failed := outcomes.count(PROVIDER_ERROR)) > 0:
        raise RuntimeError(f"{failed} bundle(s) hit a provider failure; run again")
    if unfinished:
        raise RuntimeError(f"could not finish {', '.join(unfinished)}; run again")


# ======================================================================================
#                                      CHECK
# ======================================================================================


def _open_job(
    ref: BundleRef, by_card: dict[str, list[TraceRecord]], skipped: dict[str, str]
) -> Job | None:
    """Check one bundle and return its repair job, or ``None`` when there is nothing to repair.

    A bundle without a record gets its first check, which stays as ``initial``. A bundle whose
    labeling is not the one the record last saw was edited since (the agent step): it is checked
    again and marked ``fixed-by-agent`` when it passes now.
    """
    bundle = load_machine_bundle(ref, allow_missing_labeling=True)
    if isinstance(bundle, str):
        skipped[ref.key] = bundle
        return None
    traces = by_card.get(ref.card_id)
    if not traces:
        skipped[ref.key] = f"no traces for card {ref.card_id!r}"
        return None

    record = read_record(ref)
    if not record:
        check = check_labeling(bundle, traces)
        record = new_record(ref, bundle, check, traces[0].gym_id)
        write_record(ref, record)
        return Job(ref, bundle, traces, record, check) if check.kind != OK else None

    check = Check(**record["initial"])
    if record["outcome"] in DONE_OUTCOMES:
        return None
    if sha256(bundle.labeling_source) != record["labeling_sha256"]:
        check = check_labeling(bundle, traces)
        record["agent_check"] = asdict(check)
        if check.kind == OK:
            record.update(outcome=FIXED_BY_AGENT, labeling_sha256=sha256(bundle.labeling_source))
        write_record(ref, record)
    if record["outcome"] in (PENDING, PROVIDER_ERROR):
        return Job(ref, bundle, traces, record, check)
    return None


# ======================================================================================
#                                      REPAIR
# ======================================================================================


def _repair_job(CONFIG: Configuration, job: Job) -> str:
    """Run the loop on one bundle and record it; return its outcome.

    A repaired labeling replaces ``labeling.py``; the original stays in the record.
    """
    ref, bundle, record = job.ref, job.bundle, job.record
    reason = unrepairable_reason(bundle)
    if reason is not None:
        record.update(outcome=UNREPAIRABLE, reason=reason)
        write_record(ref, record)
        print(f"{ref.key}: unrepairable ({reason})", flush=True)
        return UNREPAIRABLE

    started = time.monotonic()
    environment = EnvironmentDescription(
        Path(bundle.manifest.environment), "", bundle.manifest.inputs["environment_markdown"], ()
    )
    model = generator_model(bundle)
    engine = get_engine(CONFIG, environment, model, warn=print_warning)
    generator = Generator(
        lambda system, user: engine.request_text(system, user, stage="labeling_repair"),
        generator_system_prompt(bundle),
        model,
    )
    repair = repair_rounds(
        bundle, job.records, generator, CONFIG.repair_iterations, start_repair(bundle, record)
    )

    if repair.error:
        outcome = PROVIDER_ERROR
    elif repair.final.kind == OK:
        outcome = FIXED
    else:
        outcome = UNFIXED
    wall = round(time.monotonic() - started, 1)
    record.update(
        outcome=outcome,
        rounds=repair.rounds,
        error=repair.error,
        final=asdict(repair.final),
        labeling_sha256=sha256(repair.source),
        calls=record["calls"] + repair.calls,
        wall_time_s=round(record["wall_time_s"] + wall, 1),
    )
    # The record keeps the original labeling, so it is written before the file is replaced.
    write_record(ref, record)
    if outcome == FIXED:
        (ref.path / "labeling.py").write_text(repair.source, encoding="utf-8")
    print(
        f"{ref.key}: {outcome} ({job.check.kind} -> {repair.final.kind}, "
        f"{len(repair.rounds)} round(s), {repair.calls} call(s), {wall}s)",
        flush=True,
    )
    return outcome


# ======================================================================================
#                                      FINISH
# ======================================================================================


@dataclass
class Finish:
    """One repaired bundle whose generation stopped at labeling, and what the step did so far."""

    ref: BundleRef
    bundle: ArtifactBundle
    record: dict
    status: dict
    calls: int = 0
    wall_time_s: float = 0.0
    error: str = ""


def _finish_bundles(CONFIG: Configuration, refs: Sequence[BundleRef]) -> list[str]:
    """Give every repaired bundle that stopped at labeling its descriptions and embeddings.

    Descriptions run in parallel; the embeddings run one bundle at a time because they share the
    server's cache file. Returns the keys of the bundles left ``pipeline-failed``.
    """
    steps = []
    for ref in refs:
        bundle = load_machine_bundle(ref)
        if isinstance(bundle, str):  # no machine to finish (a failed FARM bundle), as in _open_job
            continue
        record, status = read_record(ref), read_json(status_path(ref.path))
        if needs_finish(bundle, record, status):
            steps.append(Finish(ref, bundle, record, status))
    with ThreadPoolExecutor(max_workers=CONFIG.repair_parallel) as pool:
        list(pool.map(lambda step: _describe(CONFIG, step), steps))
    for step in steps:
        if not step.error:
            _embed_and_finish(CONFIG, step)
        if step.error:
            print(f"{step.ref.key}: not finished ({step.error})", flush=True)
    return [step.ref.key for step in steps if step.error]


def _describe(CONFIG: Configuration, step: Finish) -> None:
    """Generate the state descriptions the generation never reached, and save the bundle.

    The machine and ``labeling.py`` are not touched: the bundle is rewritten with the two stages
    marked ``complete`` and the descriptions added. A bundle that already has descriptions (a
    stopped earlier run) skips the request.
    """
    bundle, started = step.bundle, time.monotonic()
    if not bundle.state_descriptions:
        markdown = bundle.manifest.inputs["environment_markdown"]
        environment = EnvironmentDescription(Path(bundle.manifest.environment), "", markdown, ())
        engine = get_engine(CONFIG, environment, generator_model(bundle), warn=print_warning)
        attempts: list[StageAttempt] = []
        try:
            bundle.state_descriptions = request_state_descriptions(
                engine, markdown, bundle.manifest.task, bundle.reward_machine, attempts
            )
        except RuntimeError as error:
            step.error = f"{error}: {attempts[-1].error}"
        step.calls = len(attempts)
    step.wall_time_s = round(time.monotonic() - started, 1)
    if not step.error:
        bundle.manifest.stage_status.update(labeling="complete", descriptions="complete")
        bundle.save(step.ref.path, overwrite=True)


def _embed_and_finish(CONFIG: Configuration, step: Finish) -> None:
    """Embed the descriptions with the pipeline's own ``embed-larm`` server path, then mark it done."""
    ref, started = step.ref, time.monotonic()
    try:
        embed_larm(replace(CONFIG, bundle=ref.path, embeddings=True))
    except Exception as error:  # the server, the bundle files and the cache can each fail
        step.error = f"{type(error).__name__}: {error}"
        return
    finished = load_machine_bundle(ref)
    if isinstance(finished, str) or not finished.complete:
        step.error = "the bundle is not complete after embedding"
        return
    step.record["finish"] = {
        "description_calls": step.calls,
        "wall_time_s": round(step.wall_time_s + time.monotonic() - started, 1),
    }
    write_record(ref, step.record)
    status_path(ref.path).write_text(
        json.dumps(finished_status(step.status, step.record), indent=2) + "\n", encoding="utf-8"
    )
    print(f"{ref.key}: finished ({step.calls} description call(s)), status complete", flush=True)


# ======================================================================================
#                                      SUMMARY
# ======================================================================================


def _print_summary(summary: dict, bundles: Path) -> None:
    """Print the class counts before repair per arm and environment, then the outcomes."""
    for key, group in {"all": summary["initial"], **summary["by_arm_environment"]}.items():
        counts = ", ".join(f"{kind} {n}" for kind, n in group["counts"].items())
        print(f"{key}: {group['total']} bundles, failure rate {group['failure_rate']}; {counts}")
    print(f"outcomes: {summary['outcomes']}")
    if summary["unfixed"]:
        print(f"unfixed, for the agent step: {', '.join(summary['unfixed'])}")
    print(f"summary: {bundles / SUMMARY_FILE}")
