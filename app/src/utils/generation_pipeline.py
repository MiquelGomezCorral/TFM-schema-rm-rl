"""Name, check, and write the outputs of one Reward Machine generation run."""

import json
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from src.arm_fm.generation import (
    generate_compiler_bundle,
    pair_state_descriptions,
    record_bundle_embeddings,
    record_bundle_role_models,
)
from src.compiler import CompilationResult
from src.config import Configuration

from .generation_logging import Progress
from .svg import render_structure_svg

# ============================================================================
#
#                                 OUTPUT PATHS
#
# ============================================================================


def prepare_outputs(CONFIG: Configuration, progress: Progress) -> tuple[Path, ...]:
    """Validate the run inputs and return one Reward Machine output path per task."""
    progress("Validating output configuration.")

    _validate_configuration(CONFIG)
    output_paths = derive_output_paths(CONFIG)

    for output_path in output_paths:
        progress(f"Output path: {output_path}")
    progress(f"Output setup complete for {len(CONFIG.tasks)} task(s).")

    return output_paths


def derive_output_names(output: Path, task_count: int) -> tuple[Path, ...]:
    """Return the file names one run writes for ``output`` and ``task_count``."""
    if task_count <= 1:
        return (output,)
    return tuple(
        output.with_name(f"{output.stem}-{index}{output.suffix}")
        for index in range(1, task_count + 1)
    )


def derive_output_paths(CONFIG: Configuration) -> tuple[Path, ...]:
    return tuple(
        CONFIG.RM_PATH / name for name in derive_output_names(CONFIG.output, len(CONFIG.tasks))
    )


def preflight_paths(destinations: Sequence[Path], *, overwrite: bool, kind: str) -> None:
    """Reject existing destinations before any final output is written."""
    occupied = [path for path in destinations if path.exists()]
    if occupied and not overwrite:
        raise ValueError(
            f"{kind} already exist; pass --overwrite to replace them: "
            + ", ".join(str(path) for path in occupied)
        )


def _validate_configuration(CONFIG: Configuration) -> None:
    if CONFIG.environment is None:
        raise ValueError("An environment file is required")
    if CONFIG.output is None:
        raise ValueError("An output file is required")
    if not CONFIG.tasks:
        raise ValueError("At least one task is required")
    if any(not isinstance(task, str) or not task.strip() for task in CONFIG.tasks):
        raise ValueError("Tasks must be nonempty")


# ============================================================================
#
#                                    OUTPUTS
#
# ============================================================================


def write_run_outputs(
    results: tuple[CompilationResult, ...],
    output_paths: tuple[Path, ...],
    CONFIG: Configuration,
    labeling_api: str,
    progress: Progress,
) -> tuple[CompilationResult, ...]:
    """Check every destination, then write the RM files and each requested artifact."""
    if CONFIG.labeling:
        _preflight_labeling_bundles(CONFIG, output_paths)
    if CONFIG.embeddings:
        preflight_paths(
            [embedding_artifact_path(CONFIG, path.stem) for path in output_paths],
            overwrite=CONFIG.overwrite,
            kind="Embedding artifact(s)",
        )
    if CONFIG.svg:
        preflight_paths(
            _svg_paths(CONFIG, output_paths),
            overwrite=CONFIG.overwrite,
            kind="SVG file(s)",
        )

    save_results(results, output_paths, overwrite=CONFIG.overwrite)
    if CONFIG.labeling:
        bundle_paths = _write_labeling_bundles(
            results, output_paths, CONFIG, labeling_api, progress
        )
        results = tuple(
            replace(result, bundle_path=path)
            for result, path in zip(results, bundle_paths, strict=True)
        )
    if CONFIG.embeddings:
        embedding_paths = _write_embedding_artifacts(results, output_paths, CONFIG, progress)
        results = tuple(
            replace(result, embedding_path=path)
            for result, path in zip(results, embedding_paths, strict=True)
        )
    if CONFIG.svg:
        _write_svgs(results, output_paths, CONFIG, progress)
    return results


def save_results(
    results: tuple[CompilationResult, ...],
    output_paths: tuple[Path, ...],
    overwrite: bool,
) -> None:
    mode = "w" if overwrite else "x"
    for output_path, result in zip(output_paths, results, strict=True):
        try:
            with output_path.open(mode, encoding="utf-8") as output_file:
                output_file.write(result.text)
        except FileExistsError as error:
            raise ValueError(
                f"Output file '{output_path}' already exists; pass --overwrite to replace it"
            ) from error
        except OSError as error:
            raise ValueError(f"Could not write output file '{output_path}': {error}") from error


# ============================================================================
#
#                                  SVG OUTPUT
#
# ============================================================================


def _svg_paths(CONFIG: Configuration, output_paths: tuple[Path, ...]) -> list[Path]:
    return [CONFIG.svg_dir / f"{output_path.stem}.svg" for output_path in output_paths]


def _write_svgs(
    results: tuple[CompilationResult, ...],
    output_paths: tuple[Path, ...],
    CONFIG: Configuration,
    progress: Progress,
) -> None:
    """Write one SVG graph per accepted Reward Machine beside the requested outputs."""
    CONFIG.svg_dir.mkdir(parents=True, exist_ok=True)
    mode = "w" if CONFIG.overwrite else "x"
    for svg_path, result in zip(_svg_paths(CONFIG, output_paths), results, strict=True):
        try:
            with svg_path.open(mode, encoding="utf-8") as svg_file:
                svg_file.write(render_structure_svg(result.reward_machine))
        except FileExistsError as error:
            raise ValueError(
                f"SVG file '{svg_path}' already exists; pass --overwrite to replace it"
            ) from error
        except OSError as error:
            raise ValueError(f"Could not write SVG file '{svg_path}': {error}") from error
        progress(f"SVG graph: {svg_path}")


# ============================================================================
#
#                              LABELING BUNDLES
#
# ============================================================================


def _labeling_bundle_paths(
    CONFIG: Configuration,
    output_paths: tuple[Path, ...],
) -> tuple[Path, ...]:
    """Return one bundle directory per accepted task output, reusing its stem."""
    return tuple(CONFIG.OUTPUT_PATH / "bundles" / output_path.stem for output_path in output_paths)


def _preflight_labeling_bundles(CONFIG: Configuration, output_paths: tuple[Path, ...]) -> None:
    """Reject occupied bundle destinations before any final output is written."""
    occupied = [
        path
        for path in _labeling_bundle_paths(CONFIG, output_paths)
        if path.exists() and any(path.iterdir())
    ]
    if occupied and not CONFIG.overwrite:
        raise ValueError(
            "Labeling bundle(s) already exist; pass --overwrite to replace them: "
            + ", ".join(str(path) for path in occupied)
        )


def _write_labeling_bundles(
    results: tuple[CompilationResult, ...],
    output_paths: tuple[Path, ...],
    CONFIG: Configuration,
    api_description: str,
    progress: Progress,
) -> tuple[Path, ...]:
    """Persist one reuse bundle per accepted task and return their directories."""
    written = []
    bundles = generate_compiler_bundle(results, None, CONFIG, api_description=api_description)
    bundle_paths = _labeling_bundle_paths(CONFIG, output_paths)
    for result, bundle, bundle_path, output_path in zip(
        results, bundles, bundle_paths, output_paths, strict=True
    ):
        record_bundle_role_models(bundle, CONFIG)
        if CONFIG.embeddings:
            record_bundle_embeddings(
                bundle, result, embedding_artifact_path(CONFIG, output_path.stem)
            )
        try:
            bundle.save(bundle_path, overwrite=CONFIG.overwrite)
        except OSError as error:
            raise ValueError(f"Could not write labeling bundle '{bundle_path}': {error}") from error
        progress(f"Labeling bundle: {bundle_path}")
        written.append(bundle_path)
    return tuple(written)


# ============================================================================
#
#                               EMBEDDING ARTIFACTS
#
# ============================================================================


def embedding_artifact_path(CONFIG: Configuration, stem: str) -> Path:
    """Return the persisted node-embedding artifact path for one task stem."""
    return Path(CONFIG.EMBEDDINGS_PATH) / stem / "embeddings.json"


def write_embedding_artifact(result: CompilationResult, destination: Path) -> None:
    """Write one accepted task's node vectors, effective texts, and settings as JSON."""
    payload = {
        "task": result.proposal.task,
        "environment": str(result.environment.source),
        "reward_machine": result.text,
        "proposition_semantics": {
            item.identifier: item.description for item in result.environment.propositions
        },
        "nodes": list(result.embeddings),
        "embeddings": result.embeddings,
        "descriptions": pair_state_descriptions(result, result.state_descriptions),
        "effective_texts": result.embedding_texts,
        "settings": dict(result.embedding_settings),
    }
    serialized = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(serialized, encoding="utf-8")
    except OSError as error:
        raise ValueError(f"Could not write embedding artifact '{destination}': {error}") from error


def _write_embedding_artifacts(
    results: tuple[CompilationResult, ...],
    output_paths: tuple[Path, ...],
    CONFIG: Configuration,
    progress: Progress,
) -> tuple[Path, ...]:
    """Persist one embedding artifact per accepted task and return their paths."""
    written = []
    for result, output_path in zip(results, output_paths, strict=True):
        destination = embedding_artifact_path(CONFIG, output_path.stem)
        write_embedding_artifact(result, destination)
        progress(f"State embeddings: {destination}")
        written.append(destination)
    return tuple(written)
