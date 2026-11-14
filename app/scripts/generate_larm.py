"""Generate one baseline or compiler-adapted ARM-FM task bundle."""

from dataclasses import replace
from pathlib import Path

from src.arm_fm import (
    PAPER_REFERENCE_SHA,
    ArtifactBundle,
    BundleManifest,
    Engines,
    PaperPrompts,
    PaperRun,
    arm_fm_role_models,
    clone_head,
    failed_compiler_bundle,
    generate_baseline_bundle,
    generate_compiler_bundle,
    generate_draw,
    load_bundle,
    load_sources,
    load_task_manifest,
    record_bundle_embeddings,
    record_bundle_role_models,
    record_compiler_failure,
)
from src.arm_fm.generation import StageAttempt
from src.compiler import CompilationResult
from src.config import Configuration
from src.models import EnvironmentDescription
from src.utils import (
    GenerationHooks,
    PipelineStep,
    embedding_artifact_path,
    get_engine,
    preflight_paths,
    print_warning,
    write_embedding_artifact,
)

from .generate_rm import generate_rm

# The bundle's name for the pipeline stage that failed.
_FAILED_STAGE = {
    PipelineStep.STATE_DESCRIPTIONS: "descriptions",
    PipelineStep.LABELING: "labeling",
    PipelineStep.EMBEDDINGS: "embeddings",
}


def generate_larm(CONFIG: Configuration) -> None:
    """Generate one inspectable bundle using baseline or compiler RM generation."""
    if CONFIG.task_manifest is not None:
        generate_manifest(CONFIG)
        return
    if CONFIG.mode == "paper":
        generate_paper(CONFIG)
        return
    if CONFIG.environment is None or CONFIG.bundle is None or len(CONFIG.tasks) != 1:
        raise ValueError("generate-larm requires one task, --environment, and --bundle")
    if CONFIG.embeddings and CONFIG.mode != "compiler":
        raise ValueError(
            "--embeddings is available for compiler bundles; use embed-larm for baseline bundles"
        )

    environment = EnvironmentDescription.from_file(CONFIG.environment, code=True)

    if CONFIG.mode == "compiler":
        generate_compiler(CONFIG, environment)
    else:
        generate_arm_fm(CONFIG, environment)


def generate_compiler(CONFIG: Configuration, environment: EnvironmentDescription) -> None:
    """Generate and save one ``compiler`` bundle; a failed run saves its failure bundle first."""
    CONFIG.output = CONFIG.output or Path("arm-fm.rm")
    # Compiler bundles require persisted labeling, so the optional stage is always on.
    CONFIG.labeling = True
    destination = None
    if CONFIG.embeddings:
        # Checked before the first provider call, so an old file cannot fail a paid-for machine.
        destination = embedding_artifact_path(CONFIG, Path(CONFIG.bundle).name)
        preflight_paths([destination], overwrite=CONFIG.overwrite, kind="Embedding artifact(s)")
    accepted = []
    run_stats = []
    failures = []

    def capture(results, _paths):
        accepted.extend(results)

    try:
        succeeded = generate_rm(
            CONFIG,
            hooks=GenerationHooks(
                completion=capture, warning=print_warning, failure=failures.append
            ),
            write_outputs=False,
            run_stats=run_stats,
        )
        if not succeeded or not accepted:
            raise RuntimeError(_failure_reason(run_stats, failures))
        bundle = _accepted_compiler_bundle(CONFIG, accepted[0], run_stats[0], destination)
    except Exception as error:
        _persist_compiler_failure(CONFIG, environment, str(error), run_stats)
        raise
    bundle.save(CONFIG.bundle, overwrite=CONFIG.overwrite)


def _failure_reason(run_stats: list[dict], failures: list[str]) -> str:
    """Why the run failed; it names the stage when the critic had accepted a machine first."""
    stage = _FAILED_STAGE.get(run_stats[0].get("last_stage")) if run_stats else None
    if stage is None or run_stats[0].get("accepted") is None or not failures:
        return "Compiler generation failed without an accepted result"
    detail = " ".join(failures[0].split())[:300]
    return (
        f"Compiler generation failed at the {stage} stage after the machine was accepted: {detail}"
    )


def _accepted_compiler_bundle(
    CONFIG: Configuration, result: CompilationResult, run_stats: dict, destination: Path | None
) -> ArtifactBundle:
    """Adapt the accepted compiler result into its bundle, with the run's records and stamp.

    The compiler pipeline already produced accepted labeling and node descriptions; the adapter
    reuses them, so no baseline engine or extra provider call is needed. ``destination`` is the
    embedding artifact to write, if any.
    """
    bundle = generate_compiler_bundle((result,), None, CONFIG)[0]
    record_bundle_role_models(bundle, CONFIG, run_stats)
    if destination is not None:
        write_embedding_artifact(result, destination)
        record_bundle_embeddings(bundle, result, destination)
    return bundle


def generate_arm_fm(CONFIG: Configuration, environment: EnvironmentDescription) -> None:
    """Generate and save one ``arm-fm`` bundle; ``--arm-fm-critic`` gives the critic its own model."""
    generator_model, critic_model = arm_fm_role_models(CONFIG)
    engine = get_engine(
        CONFIG,
        environment,
        generator_model,
        warn=lambda message: print_warning(f"Baseline {message}"),
    )
    critic_engine = None
    if critic_model != generator_model:
        critic_engine = get_engine(
            CONFIG,
            environment,
            critic_model,
            warn=lambda message: print_warning(f"Critic {message}"),
        )
    result = generate_baseline_bundle(CONFIG.tasks[0], environment, engine, CONFIG, critic_engine)
    result.bundle.save(CONFIG.bundle, overwrite=CONFIG.overwrite)


def generate_paper(CONFIG: Configuration) -> None:
    """Generate ``CONFIG.draws`` paper-profile bundles; the first passing one becomes the bundle.

    Every draw is saved next to the bundle as ``<name>-draw<N>`` for inspection. The prompts
    come from the authors' clone (``--reference``) as named by ``--paper-sources``; the
    generator and critic roles use the configured generator and critic models.
    """
    if CONFIG.reference is None or CONFIG.paper_sources is None or CONFIG.bundle is None:
        raise ValueError("--mode paper requires --reference, --paper-sources and --bundle")
    if clone_head(CONFIG.reference) != PAPER_REFERENCE_SHA:
        raise ValueError(f"--reference must be at commit {PAPER_REFERENCE_SHA}")
    if not CONFIG.generator_model or not CONFIG.critic_model:
        raise ValueError("--mode paper needs a generator and a critic model")
    if CONFIG.generator_model == CONFIG.critic_model:
        raise ValueError("The generator and critic models must differ")
    if CONFIG.draws < 1:
        raise ValueError("--draws must be at least 1")

    sources = load_sources(CONFIG.paper_sources)
    prompts = PaperPrompts.read(CONFIG.reference, sources)
    draw_dirs = {
        number: CONFIG.bundle.with_name(f"{CONFIG.bundle.name}-draw{number}")
        for number in range(1, CONFIG.draws + 1)
    }
    preflight_paths(
        [CONFIG.bundle, *draw_dirs.values()], overwrite=CONFIG.overwrite, kind="Bundle folder(s)"
    )

    engines = Engines(
        get_engine(
            CONFIG,
            None,
            CONFIG.generator_model,
            warn=lambda message: print_warning(f"Generator {message}"),
        ),
        get_engine(
            CONFIG,
            None,
            CONFIG.critic_model,
            warn=lambda message: print_warning(f"Critic {message}"),
        ),
    )
    models = {"generator": CONFIG.generator_model, "critic": CONFIG.critic_model}
    run = PaperRun(prompts, sources, models, engines)

    selected = None
    for number, directory in draw_dirs.items():
        draw = generate_draw(number, run)
        draw.bundle.save(directory, overwrite=CONFIG.overwrite)
        verdicts = [item.verdict for item in [*draw.rm_stage.rounds, *draw.labeling_stage.rounds]]
        print(
            f"draw {number}: passed={draw.passed} verdicts={verdicts} error={draw.error!r} -> {directory}"
        )
        if selected is None and draw.passed:
            selected = draw
    if selected is None:
        raise RuntimeError("No draw passed the gates; inspect the draw folders next to the bundle")
    selected.bundle.save(CONFIG.bundle, overwrite=CONFIG.overwrite)
    print(f"draw {selected.number} is the bundle: {CONFIG.bundle}")


def _persist_compiler_failure(
    CONFIG: Configuration,
    environment: EnvironmentDescription,
    error: str,
    run_stats: list[dict],
) -> None:
    """Persist an inspectable compiler failure, keeping every stage accepted before it.

    A run the critic had accepted keeps its machine, clauses, state descriptions and labeling
    tries (``failed_compiler_bundle``); an earlier failure has no RM artifacts to keep. The
    failed run's request records and stamp go in with it (``run_stats`` is empty when the run
    made no request); a save error is printed, not raised over the failure itself.
    """
    if CONFIG.bundle is None:
        return
    stats = run_stats[0] if run_stats else {}
    accepted = stats.get("accepted")
    stage = _FAILED_STAGE.get(stats.get("last_stage"))
    bundle = None
    if accepted is not None and stage is not None:
        try:
            attempts = [StageAttempt(**item) for item in accepted.labeling_attempts]
            bundle = failed_compiler_bundle(accepted, stage, error, attempts)
            record_bundle_role_models(bundle, CONFIG, stats)
        except Exception as build_error:  # the failure itself must still leave a bundle
            print_warning(f"could not keep the accepted machine: {build_error}")
            bundle = None
    if bundle is None:
        bundle = _bare_failure_bundle(CONFIG, environment, error, stats)
    try:
        bundle.save(CONFIG.bundle, overwrite=CONFIG.overwrite)
    except OSError as save_error:
        print_warning(f"could not save the failed bundle: {save_error}")


def _bare_failure_bundle(
    CONFIG: Configuration, environment: EnvironmentDescription, error: str, stats: dict
) -> ArtifactBundle:
    """The failure bundle of a run the critic never accepted: no RM artifacts are invented."""
    manifest = BundleManifest(
        task=CONFIG.tasks[0],
        environment=str(environment.source),
        proposition_semantics={
            item.identifier: item.description for item in environment.propositions
        },
        provenance={"status": "failed", "generator": "compiler-adaptation"},
        generation={},
        validation={"structural": False, "critic": False},
        stage_status={
            "reward_machine": "failed",
            "labeling": "pending",
            "descriptions": "pending",
        },
        inputs={"task": CONFIG.tasks[0], "environment_markdown": environment.markdown},
        errors=[error],
        effective_settings={
            "mode": "compiler",
            "recurrent_soft_penalty": CONFIG.recurrent_soft_penalty,
        },
        rm_mode="compiler",
    )
    bundle = ArtifactBundle(manifest, None)
    record_compiler_failure(bundle, CONFIG, stats)
    return bundle


def generate_manifest(CONFIG: Configuration) -> None:
    """Generate manifest entries independently, retaining failed entries for inspection."""
    if CONFIG.task_manifest is None:
        raise ValueError("generate_manifest requires task_manifest")

    entries = load_task_manifest(CONFIG.task_manifest)
    failures = 0
    for entry in entries:
        try:
            child = replace(
                CONFIG,
                task_manifest=None,
                tasks=[entry.settings.get("task", entry.task_id)],
                environment=entry.environment_description,
                bundle=entry.bundle,
            )
            generate_larm(child)
            bundle = load_bundle(entry.bundle)
            bundle.manifest.effective_settings.update(entry.settings)
            bundle.save(entry.bundle, overwrite=True)
        except Exception:
            failures += 1

    if failures:
        raise RuntimeError(f"{failures} manifest task(s) failed; inspect their persisted bundles")
