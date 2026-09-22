"""Generate one baseline or compiler-adapted ARM-FM task bundle."""

from dataclasses import replace
from pathlib import Path

from src.arm_fm import (
    ArtifactBundle,
    BundleManifest,
    generate_baseline_bundle,
    generate_compiler_bundle,
    labeling_api_for_domain,
    load_bundle,
    load_task_manifest,
)
from src.config import Configuration
from src.models import EnvironmentDescription
from src.utils import GenerationHooks, get_engine

from .generate_rm import generate_rm


def generate_larm(CONFIG: Configuration) -> None:
    """Generate one inspectable bundle using baseline or compiler RM generation."""
    if CONFIG.task_manifest is not None:
        generate_manifest(CONFIG)
        return
    if CONFIG.environment is None or CONFIG.bundle is None or len(CONFIG.tasks) != 1:
        raise ValueError("generate-larm requires one task, --environment, and --bundle")

    environment = EnvironmentDescription.from_file(CONFIG.environment)

    if CONFIG.mode == "compiler":
        CONFIG.output = CONFIG.output or Path("arm-fm.rm")
        accepted = []

        def capture(results, _paths):
            accepted.extend(results)

        try:
            status = generate_rm(
                CONFIG,
                hooks=GenerationHooks(completion=capture),
                write_outputs=False,
            )
        except Exception as error:
            _persist_compiler_failure(CONFIG, environment, str(error))
            raise

        if status != 0 or not accepted:
            _persist_compiler_failure(
                CONFIG, environment, "Compiler generation returned no accepted result"
            )
            raise RuntimeError("Compiler generation failed without an accepted result")

        engine = get_engine(CONFIG, environment)
        bundles = generate_compiler_bundle(
            tuple(accepted), engine,
            api_description=labeling_api_for_domain(CONFIG.domain or str(CONFIG.environment)),
            bundle_directory=CONFIG.bundle,
            overwrite=CONFIG.overwrite,
        )
        bundles[0].save(CONFIG.bundle, overwrite=CONFIG.overwrite)
    else:
        engine = get_engine(CONFIG, environment)
        result = generate_baseline_bundle(
            CONFIG.tasks[0], environment, engine,
            api_description=labeling_api_for_domain(CONFIG.domain or str(CONFIG.environment)),
            bundle_directory=CONFIG.bundle,
            overwrite=CONFIG.overwrite,
        )
        result.bundle.save(CONFIG.bundle, overwrite=CONFIG.overwrite)


def _persist_compiler_failure(
    CONFIG: Configuration, environment: EnvironmentDescription, error: str
) -> None:
    """Persist an inspectable compiler failure without inventing RM artifacts."""
    if CONFIG.bundle is None:
        return
    manifest = BundleManifest(
        task=CONFIG.tasks[0],
        environment=str(environment.source),
        proposition_semantics={item.identifier: item.description for item in environment.propositions},
        provenance={"status": "failed", "generator": "compiler-adaptation"},
        generation={},
        validation={"structural": False, "critic": False},
        stage_status={"reward_machine": "failed", "labeling": "pending", "descriptions": "pending"},
        inputs={"task": CONFIG.tasks[0], "environment_markdown": environment.markdown},
        errors=[error],
        effective_settings={"mode": "compiler"},
        rm_mode="compiler",
    )
    try:
        ArtifactBundle(manifest, None).save(CONFIG.bundle, overwrite=CONFIG.overwrite)
    except OSError:
        pass


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
