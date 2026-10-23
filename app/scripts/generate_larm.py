"""Generate one baseline or compiler-adapted ARM-FM task bundle."""

from contextlib import suppress
from dataclasses import replace
from pathlib import Path

from src.arm_fm import (
    PAPER_REFERENCE_SHA,
    ArtifactBundle,
    BundleManifest,
    Engines,
    PaperPrompts,
    PaperRun,
    clone_head,
    generate_baseline_bundle,
    generate_compiler_bundle,
    generate_draw,
    load_bundle,
    load_sources,
    load_task_manifest,
    record_bundle_embeddings,
    record_bundle_role_models,
)
from src.config import Configuration
from src.models import EnvironmentDescription
from src.utils import (
    GenerationHooks,
    embedding_artifact_path,
    get_engine,
    preflight_paths,
    write_embedding_artifact,
)

from .generate_rm import generate_rm


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
        CONFIG.output = CONFIG.output or Path("arm-fm.rm")
        # Compiler bundles require persisted labeling, so the optional stage is always on.
        CONFIG.labeling = True
        accepted = []

        def capture(results, _paths):
            accepted.extend(results)

        try:
            succeeded = generate_rm(
                CONFIG,
                hooks=GenerationHooks(completion=capture),
                write_outputs=False,
            )
        except Exception as error:
            _persist_compiler_failure(CONFIG, environment, str(error))
            raise

        if not succeeded or not accepted:
            _persist_compiler_failure(
                CONFIG, environment, "Compiler generation returned no accepted result"
            )
            raise RuntimeError("Compiler generation failed without an accepted result")

        # The compiler pipeline already produced accepted labeling and node descriptions;
        # the adapter reuses them, so no baseline engine or extra provider call is needed.
        bundles = generate_compiler_bundle(tuple(accepted), None, CONFIG)
        record_bundle_role_models(bundles[0], CONFIG)
        if CONFIG.embeddings:
            destination = embedding_artifact_path(CONFIG, Path(CONFIG.bundle).name)
            preflight_paths([destination], overwrite=CONFIG.overwrite, kind="Embedding artifact(s)")
            write_embedding_artifact(accepted[0], destination)
            record_bundle_embeddings(bundles[0], accepted[0], destination)
        bundles[0].save(CONFIG.bundle, overwrite=CONFIG.overwrite)
    else:
        engine = get_engine(CONFIG, environment)
        result = generate_baseline_bundle(CONFIG.tasks[0], environment, engine, CONFIG)
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
        get_engine(CONFIG, None, CONFIG.generator_model),
        get_engine(CONFIG, None, CONFIG.critic_model),
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
    CONFIG: Configuration, environment: EnvironmentDescription, error: str
) -> None:
    """Persist an inspectable compiler failure without inventing RM artifacts."""
    if CONFIG.bundle is None:
        return
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
    with suppress(OSError):
        ArtifactBundle(manifest, None).save(CONFIG.bundle, overwrite=CONFIG.overwrite)


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
