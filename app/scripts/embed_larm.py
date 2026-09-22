"""Embed validated ARM-FM state descriptions."""

from dataclasses import asdict

from src.arm_fm import (
    EMBEDDING_MODEL,
    EmbeddingCache,
    EmbeddingSettings,
    embed_state_descriptions,
    load_bundle,
    resolve_embedding_settings,
)
from src.config import Configuration


def embed_larm(CONFIG: Configuration, *, model: object, tokenizer: object, settings=None) -> None:
    """Embed a validated bundle and persist its state-to-row mapping."""
    if CONFIG.bundle is None:
        raise ValueError("embed-larm requires --bundle")
    bundle = load_bundle(CONFIG.bundle)
    diagnostics = bundle.validate()

    required = {"reward_machine", "labeling", "descriptions"}
    complete = {stage for stage, status in bundle.manifest.stage_status.items() if status == "complete"}

    if diagnostics or required - complete:
        raise ValueError("Embedding requires accepted RM, labeling, and description stages")

    settings = settings or EmbeddingSettings(model=CONFIG.model or EMBEDDING_MODEL)
    settings = resolve_embedding_settings(model, tokenizer, settings)

    bundle.embeddings = embed_state_descriptions(
        bundle.state_descriptions,
        model,
        tokenizer,
        settings=settings,
        cache=EmbeddingCache(CONFIG.bundle / "embedding-cache.json"),
    )

    bundle.manifest.stage_status["embeddings"] = "complete"
    bundle.manifest.effective_settings["embedding"] = asdict(settings)
    bundle.save(CONFIG.bundle, overwrite=True)
