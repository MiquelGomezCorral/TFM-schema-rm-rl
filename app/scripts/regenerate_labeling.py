"""Regenerate the labeling of bundles whose machine a critic accepted, with the generation loop.

The loop is the one generation runs: the bundle's writer and critic models (its stamp), the same
reasoning, ``MAX_ATTEMPTS`` tries with the critic's review, and only the propositions the machine
uses. The machine is never changed. The old labeling, its attempts and its check record go to
``<name>.labeling_regen.json`` beside the folder; the bundle gets the new attempts and, when one is
accepted, the new ``labeling.py``. A loop that fails leaves a complete bundle exactly as it was (its
tries are only in the sidecar); a bundle whose labeling was not complete gets the failed tries. The
first sidecar's ``previous`` is kept on every rerun, so the original generation is never lost. A
bundle whose sidecar is ``accepted`` for the same machine is skipped; a ``failed`` or ``pending``
one is retried, so the command can run again. ``repair-labeling`` then checks the new labeling and
finishes a bundle whose generation had stopped at labeling.
"""

import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from src.arm_fm import ArtifactBundle
from src.arm_fm.generation import (
    LabelingError,
    StageAttempt,
    call_records,
    generate_compiler_labeling,
    regenerate_baseline_labeling,
)
from src.benchmark.labeling_repair import (
    has_accepted_machine,
    record_path,
    sha256,
)
from src.benchmark.traces import (
    BundleRef,
    as_object,
    find_bundles,
    load_machine_bundle,
    read_json,
    write_json,
)
from src.compiler import (
    CompilationResult,
    build_compilation_result,
    compile_dfas,
    compiler_machine_to_paper,
    serialize_paper_reward_machine,
)
from src.config import Configuration
from src.engines import ImmediateEngineError, RetryableEngineError
from src.models import EnvironmentDescription
from src.utils import get_engine, print_warning

from .ablate_rm import AblationError, _recorded_switches, _stored_task

SIDECAR_SUFFIX = ".labeling_regen.json"
ACCEPTED, FAILED, PROVIDER_ERROR, SKIPPED = "accepted", "failed", "provider-error", "skipped"
PENDING = "pending"  # the sidecar of a run whose bundle write has not finished


def regenerate_labeling(CONFIG: Configuration, bundles: Path, only: Sequence[str]) -> None:
    """Regenerate the labeling of every bundle under ``bundles`` that has an accepted machine.

    ``only`` limits the run to card ids or bundle names; ``CONFIG.repair_parallel`` bundles run at
    once.

    Raises:
        RuntimeError: After every bundle ran, when a provider failure stopped one; running again
            continues it.
    """
    refs = [ref for ref in find_bundles(bundles) if not only or {ref.card_id, ref.name} & set(only)]
    with ThreadPoolExecutor(max_workers=CONFIG.repair_parallel) as pool:
        outcomes = list(pool.map(lambda ref: _regenerate(CONFIG, ref), refs))
    print(f"labeling regeneration: { {kind: outcomes.count(kind) for kind in set(outcomes)} }")
    if (failed := outcomes.count(PROVIDER_ERROR)) > 0:
        raise RuntimeError(f"{failed} bundle(s) hit a provider failure; run again")


def sidecar_path(ref: BundleRef) -> Path:
    """The regeneration record of a bundle, beside its folder."""
    return ref.path.with_name(ref.path.name + SIDECAR_SUFFIX)


def _regenerate(CONFIG: Configuration, ref: BundleRef) -> str:
    """Regenerate one bundle's labeling and record it; return the outcome."""
    bundle = load_machine_bundle(ref, allow_missing_labeling=True)
    if isinstance(bundle, str):
        return _skip(ref, bundle)
    if not has_accepted_machine(bundle):
        return _skip(ref, "no critic accepted its machine")
    record = read_json(sidecar_path(ref))
    if record.get("outcome") == ACCEPTED and record.get("rm_sha256") == sha256(
        ref.rm_path.read_bytes()
    ):
        return _skip(ref, "already regenerated")
    stamp = as_object(bundle.manifest.provenance.get("stamp"))
    models = (stamp.get("generator_model"), stamp.get("critic_model"))
    if not all(model in Configuration.REPAIR_MODELS for model in models if model):
        return _skip(ref, f"models {models} are not the small pair")

    started = time.monotonic()
    attempts: list[StageAttempt] = []
    engines: list[object] = []
    own = replace(CONFIG, bundle=ref.path, reasoning=stamp.get("reasoning", CONFIG.reasoning))
    try:
        source = _generate(own, bundle, models, attempts, engines)
    except LabelingError as error:
        source, attempts = "", error.attempts
    except (RetryableEngineError, ImmediateEngineError) as error:
        print(f"{ref.key}: {PROVIDER_ERROR} ({type(error).__name__}: {error})", flush=True)
        return PROVIDER_ERROR

    outcome = ACCEPTED if source else FAILED
    wall = round(time.monotonic() - started, 1)
    calls = len(call_records(*engines))
    _write(ref, bundle, source, attempts, {"models": models, "calls": calls, "wall_time_s": wall})
    print(f"{ref.key}: {outcome} ({len(attempts)} try(ies), {calls} call(s), {wall}s)", flush=True)
    return outcome


def _skip(ref: BundleRef, reason: str) -> str:
    print(f"{ref.key}: skipped ({reason})", flush=True)
    return SKIPPED


def _generate(
    CONFIG: Configuration,
    bundle: ArtifactBundle,
    models: tuple[str | None, str | None],
    attempts: list[StageAttempt],
    engines: list[object],
) -> str:
    """The new labeling source; ``attempts`` and ``engines`` keep every try and request.

    A stamp whose critic model equals its generator model gets no critic here, so a FARM
    regeneration then skips the review the original run made; benchmark pairs differ today.
    """
    generator_model, critic_model = models
    environment = EnvironmentDescription.from_markdown(
        bundle.manifest.inputs["environment_markdown"], bundle.manifest.environment
    )
    generator = get_engine(CONFIG, environment, generator_model, warn=print_warning)
    critic = (
        get_engine(CONFIG, environment, critic_model, warn=print_warning)
        if critic_model and critic_model != generator_model
        else None
    )
    engines += [generator, critic]
    if bundle.manifest.rm_mode != "compiler":
        source, tried = regenerate_baseline_labeling(bundle, environment, generator, critic)
        attempts += tried
        return source
    compiled = _rebuild_compiler_result(CONFIG, bundle)
    return generate_compiler_labeling(bundle.manifest.task, compiled, generator, critic, attempts)


def _rebuild_compiler_result(CONFIG: Configuration, bundle: ArtifactBundle) -> CompilationResult:
    """The compiler's result for the bundle's stored clauses, the way ``ablate-rm`` rebuilds it.

    It must give the bundle's own machine, or the labeling would be written for another one.
    """
    try:
        environment, proposal = _stored_task(CONFIG, bundle)
    except AblationError as error:
        raise ImmediateEngineError(str(error)) from error
    dfas = compile_dfas(proposal, CONFIG)
    result = build_compilation_result(environment, proposal, dfas, _recorded_switches(bundle))
    machine = compiler_machine_to_paper(result.reward_machine, environment.proposition_ids)
    if serialize_paper_reward_machine(machine) != serialize_paper_reward_machine(
        bundle.reward_machine
    ):
        raise ImmediateEngineError("the stored clauses do not rebuild the bundle's machine")
    return replace(
        result,
        state_descriptions=tuple(bundle.state_descriptions[state] for state in machine.states)
        if bundle.state_descriptions
        else (),
    )


def _write(
    ref: BundleRef,
    bundle: ArtifactBundle,
    source: str,
    attempts: Sequence[StageAttempt],
    run: dict,
) -> None:
    """Record the loop: the sidecar first as ``pending``, then the bundle, then the final sidecar.

    A crash between the steps leaves a ``pending`` sidecar that keeps the original labeling, so
    the next run retries and never mistakes the new labeling for the original one. A failed loop
    on a complete bundle changes nothing but the sidecar. A ``pending`` sidecar whose bundle already
    holds another labeling than its ``previous`` is a crashed run's: a failed rerun puts ``previous``
    back, so the bundle and the final sidecar agree on the original.
    """
    record = read_json(sidecar_path(ref))
    outcome = ACCEPTED if source else FAILED
    complete = bundle.manifest.stage_status.get("labeling") == "complete"
    check_path = record_path(ref)
    old_attempts = [item for item in bundle.attempts if item["stage"] == "labeling"]
    rm_sha256 = sha256(ref.rm_path.read_bytes())
    original = record.get("previous", {}).get("labeling")
    crashed = (
        record.get("outcome") == PENDING
        and record.get("rm_sha256") == rm_sha256
        and original is not None
        and bundle.labeling_source != original
    )
    touches_bundle = bool(source) or not complete or crashed
    # An earlier sidecar of the same machine already holds the original generation.
    previous = (
        record["previous"]
        if record.get("rm_sha256") == rm_sha256 and "previous" in record
        else {
            "labeling": bundle.labeling_source,
            "attempts": old_attempts,
            "stage_status": bundle.manifest.stage_status.get("labeling"),
            "check_record": read_json(check_path),
        }
    )
    sidecar = {
        "bundle": ref.key,
        "rm_sha256": rm_sha256,
        "attempts": [item.__dict__ for item in attempts],
        "previous": previous,
        **run,
    }
    write_json(
        sidecar_path(ref), {**sidecar, "outcome": PENDING if touches_bundle else outcome}, indent=2
    )
    if not touches_bundle:
        return
    kept = [item for item in bundle.attempts if item["stage"] != "labeling"]
    if source:
        # The old check record described the old labeling; a new check starts from the new one.
        check_path.unlink(missing_ok=True)
        bundle.labeling_source = source
        bundle.attempts = kept + [item.__dict__ for item in attempts]
        bundle.manifest.stage_status["labeling"] = "complete"
    elif crashed:
        bundle.labeling_source = previous["labeling"]
        bundle.attempts = kept + previous["attempts"]
        bundle.manifest.stage_status["labeling"] = previous["stage_status"] or "pending"
        if previous["check_record"]:
            write_json(check_path, previous["check_record"], indent=2)
    else:
        bundle.attempts = kept + [item.__dict__ for item in attempts]
        bundle.manifest.stage_status["labeling"] = "failed"
    bundle.save(ref.path, overwrite=True)
    write_json(sidecar_path(ref), {**sidecar, "outcome": outcome}, indent=2)
