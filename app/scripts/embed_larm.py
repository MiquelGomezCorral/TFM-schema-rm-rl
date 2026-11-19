"""Embed validated ARM-FM state descriptions."""

from dataclasses import asdict

from src.arm_fm import (
    EMBEDDING_MODEL,
    EmbeddingCache,
    EmbeddingSettings,
    embed_descriptions_over_http,
    embed_state_descriptions,
    load_bundle,
    load_qwen_embedding_model,
)
from src.arm_fm.evaluation import SERVER_EMBEDDING_EXTRACTION
from src.config import Configuration


def embed_larm(CONFIG: Configuration) -> None:
    """Embed a validated bundle and persist its state-to-row map.

    ``--embedding-server`` (``CONFIG.embeddings``) uses the configured local server;
    otherwise the built-in Qwen loader embeds the descriptions.
    """
    if CONFIG.bundle is None:
        raise ValueError("embed-larm requires --bundle")
    if CONFIG.embeddings:
        _embed_over_server(CONFIG)
        return

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


def _embed_over_server(CONFIG: Configuration) -> None:
    """Embed with the compiler's server settings (``generate_rm.py`` ``_embed_states``).

    Baseline and compiler bundles then share one embedding space, model and cache.
    """
    bundle = load_bundle(CONFIG.bundle)
    if bundle.validate() or not bundle.generation_complete:
        raise ValueError("Embedding requires accepted RM, labeling, and description stages")

    settings = EmbeddingSettings(
        model=CONFIG.embedding_model,
        model_revision=CONFIG.embedding_revision,
        tokenizer_revision=CONFIG.embedding_revision,
        extraction=SERVER_EMBEDDING_EXTRACTION,
        normalize=True,
        device="remote",
    )
    vectors = embed_descriptions_over_http(
        bundle.state_descriptions,
        CONFIG,
        settings=settings,
        context="",
        cache=EmbeddingCache(CONFIG.EMBEDDINGS_PATH / "cache.json"),
    )

    bundle.embeddings = vectors
    bundle.manifest.stage_status["embeddings"] = "complete"
    bundle.manifest.effective_settings["embedding"] = {
        **asdict(settings),
        "dimension": len(next(iter(vectors.values()))),
        "context": "",
        "endpoint": CONFIG.embedding_endpoint,
    }
    bundle.save(CONFIG.bundle, overwrite=True)
