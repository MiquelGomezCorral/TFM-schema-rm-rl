"""Judge ARM-FM bundles and write aggregate accounting."""

import json
from dataclasses import replace

from src.arm_fm import (
    EMBEDDING_MODEL,
    ArtifactBundle,
    JudgeDecision,
    aggregate_judgments,
    judge_bundle,
    load_bundle,
)
from src.benchmark.labeling_repair import status_path
from src.benchmark.traces import ablation_settings, read_json
from src.config import Configuration
from src.models import EnvironmentDescription
from src.utils import get_engine, print_warning


def evaluate_larm(CONFIG: Configuration) -> None:
    """Judge one or more bundles and write aggregate accounting."""
    paths = CONFIG.manifests or ([CONFIG.bundle] if CONFIG.bundle is not None else [])
    if not paths:
        raise ValueError("evaluate-larm requires --bundle or --manifest")

    judge_model = CONFIG.judge_model or EMBEDDING_MODEL
    decisions = []
    failures = 0

    for path in paths:
        bundle = None
        try:
            # A bundle finished after a failed generation keeps that failure here, not a judged win.
            outcome = read_json(status_path(path)).get("generation_status")
            if outcome not in (None, "complete"):
                raise ValueError(f"generation ended {outcome}; the bundle was repaired afterwards")
            bundle = load_bundle(path)
            environment = EnvironmentDescription.from_markdown(
                bundle.manifest.inputs["environment_markdown"],
                source=bundle.manifest.environment,
            )
            engine = get_engine(
                replace(CONFIG, model=judge_model),
                environment,
                warn=lambda message: print_warning(f"Judge {message}"),
            )
            decisions.append(judge_bundle(bundle, engine))
        except Exception as error:
            # Read from the manifest file: the bundle may not have loaded. A variant is no failure.
            ablation = bool(ablation_settings(path))
            if not ablation and (bundle is None or not _generation_complete(bundle)):
                failures += 1
            decisions.append(
                JudgeDecision(False, False, f"unscored: {error}", scored=False, ablation=ablation)
            )

    summary = aggregate_judgments(decisions, submitted=len(paths), generation_failures=failures)
    if CONFIG.output is not None:
        target = CONFIG.OUTPUT_PATH / CONFIG.output
        target.write_text(
            json.dumps(summary.__dict__, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _generation_complete(bundle: ArtifactBundle) -> bool:
    """Identify generation failures without requiring optional embedding output."""
    try:
        diagnostics = bundle.validate()
    except Exception:
        return False

    environment_markdown = bundle.manifest.inputs.get("environment_markdown")
    return (
        not diagnostics
        and bundle.generation_complete
        and isinstance(environment_markdown, str)
        and bool(environment_markdown.strip())
    )
