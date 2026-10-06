"""Embed validated ARM-FM state descriptions."""

from dataclasses import asdict

from src.arm_fm import (
    EMBEDDING_MODEL,
    EmbeddingCache,
    EmbeddingSettings,
    embed_state_descriptions,
    load_bundle,
    load_qwen_embedding_model,
)
from src.config import Configuration


def embed_larm(CONFIG: Configuration) -> None:
    """Embed a validated bundle with the built-in Qwen loader and persist its state-to-row map."""
    if CONFIG.bundle is None:
        raise ValueError("embed-larm requires --bundle")

    model, tokenizer, settings = load_qwen_embedding_model(
        EmbeddingSettings(model=CONFIG.model or EMBEDDING_MODEL)
    )
    bundle = load_bundle(CONFIG.bundle)
    diagnostics = bundle.validate()

    if diagnostics or not bundle.generation_complete:
        raise ValueError("Embedding requires accepted RM, labeling, and description stages")

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
