"""Labeling check and repair: measure which generated labeling fails, then repair it.

``check_labeling`` gives a bundle one class, recorded before any repair: ``missing`` (no
labeling), ``load`` (the sandbox refuses it, or a machine proposition has no function), ``crash``
(it raises while the card's traces replay), ``wrong`` (its labels disagree with the reference
labeler on those traces) or ``ok``. ``repair_rounds`` asks the bundle's own generator model for
a corrected labeling with the failure evidence, up to a round limit, and checks every reply the
way the first check did. The Reward Machine is never changed. The record of one bundle sits
beside its folder (``<name>.labeling_check.json``), so a bundle folder gains no file; the repaired
labeling replaces ``labeling.py`` and the original stays in the record.

A bundle whose generation stopped at labeling has no descriptions and no embeddings either.
``needs_finish`` and ``finished_status`` decide which repaired bundles get those stages and how
their ``<name>.status.json`` reads afterwards; the driver runs the stages.
"""

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from src.arm_fm.artifacts import ArtifactBundle
from src.arm_fm.generation import extract_labeling_code
from src.arm_fm.runtime import load_labeling_functions
from src.compiler import serialize_paper_reward_machine
from src.config import Configuration
from src.engines import ImmediateEngineError, RetryableEngineError
from src.prompts import read_prompt, render_prompt

from .traces import (
    BundleRef,
    TraceRecord,
    as_object,
    label_agreement,
    read_json,
    replay_in_bundle,
    write_json,
)

MISSING, LOAD, CRASH, WRONG, OK = "missing", "load", "crash", "wrong", "ok"
CLASSES = (MISSING, LOAD, CRASH, WRONG, OK)

# Outcomes of a bundle's record. ``fixed-by-agent`` is set by a later check of a bundle whose
# loop ended ``unfixed`` and whose labeling an agent then edited; it stays flagged failed.
FIXED, UNFIXED, FIXED_BY_AGENT = "fixed", "unfixed", "fixed-by-agent"
PENDING, UNREPAIRABLE, PROVIDER_ERROR = "pending", "unrepairable", "provider-error"
DONE_OUTCOMES = (OK, FIXED, FIXED_BY_AGENT)

EVIDENCE_LIMIT = 5  # failures kept per check, and mismatching steps per proposition
RECORD_SUFFIX = ".labeling_check.json"
SUMMARY_FILE = "labeling_check.json"
STATUS_SUFFIX = ".status.json"
MACHINE_STAGES = ("reward_machine", "compiler")  # the attempt stage that accepts a machine, per arm
BY_SMALL_MODEL, BY_AGENT = "small-model", "agent"  # who repaired the labeling of a finished bundle


# ======================================================================================
#                                          CHECK
# ======================================================================================


@dataclass(frozen=True)
class Check:
    """The class of one labeling, the first failures behind it and what the comparison covered."""

    kind: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    coverage: dict[str, Any] = field(default_factory=dict)


def check_labeling(bundle: ArtifactBundle, records: Sequence[TraceRecord]) -> Check:
    """Class the bundle's labeling against the Reward Machine's propositions and the traces."""
    if not bundle.labeling_source.strip():
        return Check(MISSING, [{"error": "the labeling is empty"}])
    try:
        load_labeling_functions(bundle.labeling_source, bundle.labeling_propositions)
    except Exception as error:  # generated code can fail in any way; that is the result
        return Check(LOAD, [{"error": f"{type(error).__name__}: {error}"}])

    pairs = [(record, replay_in_bundle(bundle, record)) for record in records]
    crashes = [
        {
            "trace": f"{record.card_id}/{record.key}",
            "step": len(replay.valuations) + 1,
            "error": replay.error,
        }
        for record, replay in pairs
        if replay.error
    ]
    if crashes:
        return Check(CRASH, crashes[:EVIDENCE_LIMIT])

    agreement = label_agreement(pairs, bundle.labeling_propositions)
    compared = agreement["propositions"]
    coverage = {
        "compared": {name: item["total"] for name, item in compared.items()},
        "of": len(bundle.labeling_propositions),
        "not_in_reference": agreement["unmatched_bundle"],
    }
    wrong = {name for name, item in compared.items() if item["agree"] < item["total"]}
    if wrong:
        return Check(WRONG, _mismatches(pairs, wrong), coverage)
    return Check(OK, [], coverage)


def _mismatches(pairs: Sequence[tuple[TraceRecord, Any]], names: set[str]) -> list[dict[str, Any]]:
    """The first steps, per proposition in ``names``, where the labeling differs from the reference."""
    found: dict[str, list[dict[str, Any]]] = {name: [] for name in sorted(names)}
    for record, replay in pairs:
        steps = enumerate(zip(record.labels, replay.valuations, strict=False), start=1)
        for step, (reference, valuation) in steps:
            for name, items in found.items():
                differs = name in reference and reference[name] != valuation[name]
                if differs and len(items) < EVIDENCE_LIMIT:
                    items.append(
                        {
                            "trace": f"{record.card_id}/{record.key}",
                            "step": step,
                            "action": record.actions[step - 1],
                            "proposition": name,
                            "reference": reference[name],
                            "labeling": valuation[name],
                        }
                    )
    return [item for items in found.values() for item in items]


# ======================================================================================
#                                          REPAIR
# ======================================================================================


@dataclass(frozen=True)
class Generator:
    """The bundle's own generator: ``ask(system, user)`` returns its reply text."""

    ask: Callable[[str, str], str]
    system: str
    model: str


@dataclass
class Repair:
    """The repair loop's state: one entry per round, and the labeling it ended with.

    ``rounds`` keeps every round ever spent on the bundle, numbered from 1. ``calls`` counts only
    the requests of the current run; the record adds them to its own total.
    """

    source: str
    final: Check
    rounds: list[dict[str, Any]] = field(default_factory=list)
    calls: int = 0
    error: str = ""  # a provider failure that ended the loop


def start_repair(bundle: ArtifactBundle, record: dict[str, Any]) -> Repair:
    """The loop state a record holds: its rounds so far, and the last candidate's check."""
    rounds = list(record["rounds"])
    final = (
        Check(rounds[-1]["class"], rounds[-1]["evidence"]) if rounds else Check(**record["initial"])
    )
    return Repair(bundle.labeling_source, final, rounds)


def repair_rounds(
    bundle: ArtifactBundle,
    records: Sequence[TraceRecord],
    generator: Generator,
    iterations: int,
    repair: Repair,
) -> Repair:
    """Ask ``generator`` for a better labeling until it checks ``ok`` or ``iterations`` rounds are spent.

    ``repair`` is where the bundle stands (``start_repair``): a rerun continues from the last
    candidate and spends only the rounds the bundle has left, none when it is at the limit. Each
    round shows the model the latest labeling and its failure evidence. A provider outage repeats
    the request without using a round, at most ``Configuration.OUTAGE_RETRIES`` times in a row;
    then, or on an error that must not be retried, the loop ends with ``error`` set. ``source``
    is the first labeling that checks ``ok``, else the original.
    """
    repair.error = ""
    current, check = bundle, repair.final
    if repair.rounds:
        current = replace(bundle, labeling_source=repair.rounds[-1]["candidate"])
    for number in range(len(repair.rounds) + 1, iterations + 1):
        user = repair_prompt(current, check)
        try:
            reply = _ask(generator, user, repair)
        except (RetryableEngineError, ImmediateEngineError) as error:
            repair.error = f"{type(error).__name__}: {error}"
            break
        current = replace(bundle, labeling_source=extract_labeling_code(reply))
        check = check_labeling(current, records)
        repair.final = check
        repair.rounds.append(
            {
                "round": number,
                "model": generator.model,
                "class": check.kind,
                "error": check.evidence[0].get("error", "") if check.evidence else "",
                "evidence": check.evidence,
                "candidate": current.labeling_source,
            }
        )
        if check.kind == OK:
            repair.source = current.labeling_source
            break
    return repair


def _ask(generator: Generator, user: str, repair: Repair) -> str:
    """One request, repeated after an outage; every request sent counts as a call."""
    outages = 0
    while True:
        repair.calls += 1
        try:
            return generator.ask(generator.system, user)
        except RetryableEngineError:
            outages += 1
            if outages > Configuration.OUTAGE_RETRIES:
                raise


def repair_prompt(bundle: ArtifactBundle, check: Check) -> str:
    """The repair request: what the pipeline gave the generator, the labeling and its failure."""
    manifest = bundle.manifest
    return render_prompt(
        "repair",
        "labeling_repair",
        environment_markdown=str(manifest.inputs.get("environment_markdown", "")),
        task=manifest.task,
        reward_machine=serialize_paper_reward_machine(bundle.reward_machine),
        api=str(manifest.api_definitions.get("labeling", "")),
        labeling=bundle.labeling_source,
        failure=failure_text(check),
    )


def failure_text(check: Check) -> str:
    """The evidence of ``check`` as the plain text the generator reads."""
    if check.kind == MISSING:
        return "The labeling is empty: no predicate was produced."
    if check.kind == LOAD:
        return f"The sandbox refused to load the labeling: {check.evidence[0]['error']}"
    if check.kind == CRASH:
        lines = [
            f"- trace {item['trace']}, step {item['step']}: {item['error']}"
            for item in check.evidence
        ]
        return "The labeling raised an error while recorded episodes were replayed:\n" + "\n".join(
            lines
        )
    lines = [
        f"- trace {item['trace']}, step {item['step']} (action {item['action']}): "
        f"`{item['proposition']}` should be {item['reference']}, the labeling returned {item['labeling']}"
        for item in check.evidence
    ]
    return (
        "The labels differ from the environment's true values on replayed episodes:\n"
        + "\n".join(lines)
    )


def unrepairable_reason(bundle: ArtifactBundle) -> str | None:
    """Why the loop cannot run on ``bundle``: a model outside the small pair, or missing inputs."""
    model = generator_model(bundle)
    if model not in Configuration.REPAIR_MODELS:
        return f"generator model {model!r} is not one of {', '.join(Configuration.REPAIR_MODELS)}"
    if not bundle.manifest.inputs.get("environment_markdown"):
        return "the manifest keeps no environment description"
    if not bundle.manifest.api_definitions.get("labeling"):
        return "the manifest keeps no Labeling API"
    return None


def generator_model(bundle: ArtifactBundle) -> str | None:
    """The model that generated the bundle: its stamp, else the settings the pipeline recorded."""
    stamp = as_object(bundle.manifest.provenance.get("stamp"))
    settings = bundle.manifest.effective_settings
    return stamp.get("generator_model") or settings.get("generator_model") or settings.get("model")


def prompt_family(bundle: ArtifactBundle) -> str:
    """The prompt family whose labeling generator wrote the bundle."""
    return "compiler" if bundle.manifest.rm_mode == "compiler" else "arm_fm"


def generator_system_prompt(bundle: ArtifactBundle) -> str:
    """The bundle's own pipeline's labeling-generator system prompt, the contract it wrote under."""
    return read_prompt(prompt_family(bundle), "labeling_generator")


# ======================================================================================
#                                  RECORDS AND SUMMARY
# ======================================================================================


def record_path(ref: BundleRef) -> Path:
    """The record of a bundle, beside its folder."""
    return ref.path.with_name(ref.path.name + RECORD_SUFFIX)


def sha256(value: str | bytes) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def new_record(
    ref: BundleRef, bundle: ArtifactBundle, check: Check, environment: str
) -> dict[str, Any]:
    """The record of a first check: the class before any repair, and the original labeling."""
    return {
        "bundle": ref.key,
        "arm": ref.arm,
        "card_id": ref.card_id,
        "environment": environment,
        "rm_sha256": sha256(ref.rm_path.read_bytes()),
        "initial": asdict(check),
        "failed": check.kind != OK,
        "labeling_original": bundle.labeling_source,
        "labeling_sha256": sha256(bundle.labeling_source),
        "outcome": OK if check.kind == OK else PENDING,
        "generator_model": generator_model(bundle),
        "rounds": [],
        "calls": 0,
        "wall_time_s": 0.0,
    }


def status_path(folder: Path) -> Path:
    """The generation status of a bundle, beside its folder (written by ``generate-suite``)."""
    return folder.with_name(folder.name + STATUS_SUFFIX)


def has_accepted_machine(bundle: ArtifactBundle) -> bool:
    """Whether a critic accepted the bundle's machine: its attempts say so, in either arm."""
    return any(
        item.get("stage") in MACHINE_STAGES and item.get("status") == "accepted"
        for item in bundle.attempts
    )


def needs_finish(bundle: ArtifactBundle, record: dict[str, Any], status: dict[str, Any]) -> bool:
    """Whether generation stopped after an accepted Reward Machine and the labeling now checks out.

    The status ``pipeline-failed`` is what ``run-suite`` reads, so it gates the step and goes back
    to ``complete`` only when the step ends. The record must say the labeling passes (``ok``, as
    after a regeneration, or repaired), and the file must still be the one that passed the check.
    A machine the critic never accepted stays failed: it is saved like a labeling-stage failure
    but its generation never got there. Both arms keep an accepted machine on a failure, so a
    FARM failure bundle finishes like an ARM-FM one.
    """
    return (
        status.get("status") == "pipeline-failed"
        and has_accepted_machine(bundle)
        and record.get("outcome") in DONE_OUTCOMES
        and record.get("labeling_sha256") == sha256(bundle.labeling_source)
    )


def finished_status(status: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    """The status of a finished bundle: ``complete``, with the generation outcome kept apart.

    ``generation_status`` and ``generation_reason`` hold what the generation itself ended with, so a
    count of generation successes reads them and not ``status``. ``calls`` and ``wall_time_s`` stay
    the generation's. ``labeling_repaired_by`` is set only for a labeling a repair changed.
    """
    repaired_by = {FIXED: BY_SMALL_MODEL, FIXED_BY_AGENT: BY_AGENT}.get(record["outcome"])
    return {
        **status,
        "status": "complete",
        "reason": None,
        "generation_status": status["status"],
        "generation_reason": status.get("reason"),
        "labeling_repaired_by": repaired_by,
    }


def read_record(ref: BundleRef) -> dict[str, Any]:
    """The bundle's record, or ``{}`` when there is none or it belongs to another machine."""
    record = read_json(record_path(ref))
    return record if record.get("rm_sha256") == sha256(ref.rm_path.read_bytes()) else {}


def write_record(ref: BundleRef, record: dict[str, Any]) -> None:
    write_json(record_path(ref), record, indent=2)


def summarize(bundles: Path, skipped: dict[str, str]) -> dict[str, Any]:
    """Counts and rates per class before repair, overall and per arm and environment.

    Read from the records on disk, so a rerun and the agent step update it. ``failures`` holds the
    evidence of every bundle that did not check ``ok`` at first; ``unfixed`` lists the bundles the
    loop did not repair, for the agent step.
    """
    records = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(Path(bundles).glob(f"*/*{RECORD_SUFFIX}"))
    ]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[f"{record['arm']} | {record['environment']}"].append(record)
    return {
        "bundles": len(records),
        "initial": _counts(records),
        "by_arm_environment": {key: _counts(items) for key, items in sorted(groups.items())},
        "outcomes": dict(Counter(record["outcome"] for record in records)),
        "unfixed": [record["bundle"] for record in records if record["outcome"] == UNFIXED],
        "failures": [
            {
                "bundle": record["bundle"],
                "class": record["initial"]["kind"],
                "evidence": record["initial"]["evidence"],
                "coverage": record["initial"]["coverage"],
                "outcome": record["outcome"],
                "rounds": len(record["rounds"]),
            }
            for record in records
            if record["failed"]
        ],
        "skipped": skipped,
    }


def _counts(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    kinds = Counter(record["initial"]["kind"] for record in records)
    total = len(records)

    def rate(count: int) -> float:
        return round(count / total, 3) if total else 0.0  # no bundles, no rate

    return {
        "total": total,
        "counts": {kind: kinds[kind] for kind in CLASSES},
        "rates": {kind: rate(kinds[kind]) for kind in CLASSES},
        "failure_rate": rate(total - kinds[OK]),
    }
