"""Judge ARM-FM bundles and write aggregate accounting."""

import json
from dataclasses import replace

from src.arm_fm import (
    EMBEDDING_MODEL,
    ArtifactBundle,
    JudgeDecision,
    JudgeSettings,
    aggregate_judgments,
    judge_bundle,
    load_bundle,
)
from src.config import Configuration
from src.models import EnvironmentDescription
from src.utils import get_engine


def evaluate_larm(CONFIG: Configuration) -> None:
    """Judge one or more bundles and write aggregate accounting."""
    paths = CONFIG.manifests or ([CONFIG.bundle] if CONFIG.bundle is not None else [])
    if not paths:
        raise ValueError("evaluate-larm requires --bundle or --manifest")

    judge_model = CONFIG.judge_model or EMBEDDING_MODEL
    settings = JudgeSettings(model=judge_model, provider=CONFIG.llm_provider)
    decisions = []
    failures = 0

    for path in paths:
        bundle = None
        try:
            bundle = load_bundle(path)
            environment = EnvironmentDescription.from_markdown(
                bundle.manifest.inputs["environment_markdown"], source=bundle.manifest.environment
            )
            engine = get_engine(replace(CONFIG, model=judge_model), environment)
            decisions.append(judge_bundle(bundle, engine, settings=settings))
        except Exception as error:
            if bundle is None or not _generation_complete(bundle):
                failures += 1
            decisions.append(JudgeDecision(False, False, f"unscored: {error}", scored=False))

    summary = aggregate_judgments(decisions, submitted=len(paths), generation_failures=failures)
    if CONFIG.output is not None:
        target = Configuration.OUTPUT_PATH / CONFIG.output
        target.write_text(json.dumps(summary.__dict__, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _generation_complete(bundle: ArtifactBundle) -> bool:
    """Identify generation failures without requiring optional embedding output."""
    try:
        diagnostics = bundle.validate()
    except Exception:
        return False

    required = {"reward_machine", "labeling", "descriptions"}
    complete = {
        stage for stage, status in bundle.manifest.stage_status.items()
        if status == "complete"
    }
    environment_markdown = bundle.manifest.inputs.get("environment_markdown")
    return (
        not diagnostics
        and required <= complete
        and isinstance(environment_markdown, str)
        and bool(environment_markdown.strip())
    )
