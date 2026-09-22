"""Embedding, judging, and benchmark accounting for ARM-FM bundles."""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from .artifacts import ArtifactBundle, BundleValidationError


EMBEDDING_MODEL = "Qwen3-30B-A3B-Instruct-2507"


@dataclass(frozen=True)
class EmbeddingSettings:
    model: str = EMBEDDING_MODEL
    model_revision: str = "unspecified"
    tokenizer_revision: str = "unspecified"
    extraction: str = "last-layer-last-non-padding-token"
    normalize: bool = True
    device: str = "auto"

    def cache_identity(self) -> str:
        payload = json.dumps(self.__dict__, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class EmbeddingCache:
    """Small JSON cache keyed by description text and extraction settings."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self.values: dict[str, list[float]] = {}
        if self.path is not None and self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.values = loaded
            except (OSError, json.JSONDecodeError):
                self.values = {}

    def key(self, text: str, settings: EmbeddingSettings) -> str:
        return hashlib.sha256((settings.cache_identity() + "\0" + text).encode()).hexdigest()

    def get(self, text: str, settings: EmbeddingSettings) -> list[float] | None:
        value = self.values.get(self.key(text, settings))
        return list(value) if isinstance(value, list) else None

    def put(self, text: str, settings: EmbeddingSettings, vector: Sequence[float]) -> None:
        self.values[self.key(text, settings)] = [float(item) for item in vector]
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.values, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def embed_state_descriptions(
    descriptions: Mapping[str, str],
    model: object,
    tokenizer: object,
    *,
    settings: EmbeddingSettings | None = None,
    cache: EmbeddingCache | None = None,
) -> dict[str, list[float]]:
    """Embed only state-description text, using the final non-padding token."""
    settings = settings or EmbeddingSettings()
    settings = resolve_embedding_settings(model, tokenizer, settings)
    cache = cache or EmbeddingCache()
    result: dict[str, list[float]] = {}
    for state, text in descriptions.items():
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"State description for {state!r} must be nonempty")
        cached = cache.get(text, settings)
        if cached is None:
            cached = _embed_one(text, model, tokenizer, settings)
            cache.put(text, settings, cached)
        result[state] = cached
    return result


def load_qwen_embedding_model(
    settings: EmbeddingSettings | None = None,
    *,
    local_files_only: bool = True,
) -> tuple[object, object, EmbeddingSettings]:
    """Load the frozen Qwen embedding pair without silently selecting another model."""
    settings = settings or EmbeddingSettings()
    try:
        from transformers import AutoModel, AutoTokenizer
    except ImportError as error:
        raise RuntimeError("Qwen embedding loader requires Transformers") from error
    common_kwargs = {
        "local_files_only": local_files_only,
        "trust_remote_code": True,
    }
    tokenizer_kwargs = {
        **common_kwargs,
        "revision": settings.tokenizer_revision
        if settings.tokenizer_revision != "unspecified" else None,
    }
    model_kwargs = {
        **common_kwargs,
        "revision": settings.model_revision
        if settings.model_revision != "unspecified" else None,
    }
    tokenizer_kwargs = {key: value for key, value in tokenizer_kwargs.items() if value is not None}
    model_kwargs = {key: value for key, value in model_kwargs.items() if value is not None}
    tokenizer = AutoTokenizer.from_pretrained(settings.model, **tokenizer_kwargs)
    model = AutoModel.from_pretrained(settings.model, **model_kwargs)
    device = settings.device
    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
    if hasattr(model, "to"):
        model.to(device)
    if hasattr(model, "eval"):
        model.eval()
    return model, tokenizer, resolve_embedding_settings(
        model, tokenizer, settings, device=device
    )


def resolve_embedding_settings(
    model: object,
    tokenizer: object,
    settings: EmbeddingSettings,
    *,
    device: str | None = None,
) -> EmbeddingSettings:
    """Resolve stable loaded revisions for cache identity and persisted provenance."""
    model_revision = _resolved_revision(model, settings.model_revision)
    tokenizer_fallback = (
        settings.tokenizer_revision
        if settings.tokenizer_revision != "unspecified"
        else settings.model_revision
    )
    tokenizer_revision = _resolved_revision(tokenizer, tokenizer_fallback)
    if model_revision is None or tokenizer_revision is None:
        raise RuntimeError("Embedding model and tokenizer must expose stable resolved revisions")
    return replace(
        settings,
        model_revision=model_revision,
        tokenizer_revision=tokenizer_revision,
        device=device or settings.device,
    )


def _resolved_revision(component: object, fallback: str) -> str | None:
    """Return a loaded commit or snapshot id, rejecting floating revisions."""
    init_kwargs = getattr(component, "init_kwargs", None)
    init_revisions = (
        [init_kwargs.get(key) for key in ("_commit_hash", "commit_hash", "revision")]
        if isinstance(init_kwargs, Mapping) else []
    )
    candidates = [
        (getattr(component, "_commit_hash", None), True),
        (getattr(component, "commit_hash", None), True),
        (getattr(component, "hub_commit_hash", None), True),
        (getattr(getattr(component, "config", None), "_commit_hash", None), True),
        *[(value, True) for value in init_revisions],
        (getattr(component, "name_or_path", None), False),
        (getattr(getattr(component, "config", None), "_name_or_path", None), False),
    ]
    for value, allow_bare in candidates:
        value = _stable_revision(value, allow_bare=allow_bare)
        if value is not None:
            return value
    return _stable_revision(fallback, allow_bare=True)


def _stable_revision(value: object, *, allow_bare: bool) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    if "/snapshots/" in value:
        value = value.split("/snapshots/", 1)[1].split("/", 1)[0]
    elif not allow_bare:
        return None
    if value.lower() in {"main", "master", "latest", "default", "unspecified", "unknown"}:
        return None
    if os.path.sep in value or value.startswith("."):
        return None
    return value


def _embed_one(text: str, model: object, tokenizer: object, settings: EmbeddingSettings) -> list[float]:
    encoded = tokenizer([text], return_tensors="pt", padding=True, truncation=True)
    try:
        import torch
    except ImportError as error:
        raise RuntimeError("Embedding requires torch; no model download is performed") from error
    device = settings.device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if hasattr(model, "to"):
        model.to(device)
    if hasattr(encoded, "items"):
        encoded = {key: value.to(device) if hasattr(value, "to") else value for key, value in encoded.items()}
    with torch.no_grad():
        output = model(**encoded)
    hidden = getattr(output, "last_hidden_state", None)
    if hidden is None:
        hidden = output[0]
    mask = encoded.get("attention_mask")
    if mask is None:
        index = hidden.shape[1] - 1
    else:
        index = int(mask[0].sum().item()) - 1
    vector = hidden[0, index].detach().float().cpu().tolist()
    values = [float(item) for item in vector]
    if settings.normalize:
        norm = math.sqrt(sum(item * item for item in values))
        if norm:
            values = [item / norm for item in values]
    return values


@dataclass(frozen=True)
class JudgeDecision:
    rm_correct: bool
    labeling_correct: bool
    reason: str
    scored: bool = True
    attempt: int = 1

    @property
    def category(self) -> str:
        if not self.scored:
            return "unscored"
        if self.rm_correct and self.labeling_correct:
            return "both"
        if self.rm_correct:
            return "rm_only"
        if self.labeling_correct:
            return "labeling_only"
        return "neither"


@dataclass(frozen=True)
class JudgeSettings:
    """Independent judge selection; generation metadata is intentionally absent."""

    model: str = EMBEDDING_MODEL
    provider: str | None = None
    revision: str = "unspecified"


@dataclass(frozen=True)
class BenchmarkSummary:
    submitted: int
    scored: int
    generation_failures: int
    counts: dict[str, int]
    first_attempt_scored: int = 0
    refined_scored: int = 0

    @property
    def coverage(self) -> float:
        return self.scored / self.submitted if self.submitted else 0.0


def judge_bundle(
    bundle: ArtifactBundle,
    engine: object,
    *,
    execution_evidence: Sequence[Mapping[str, Any]] | None = None,
    settings: JudgeSettings | None = None,
) -> JudgeDecision:
    """Ask a provider-neutral judge with full context and method-blind RM origin."""
    diagnostics = bundle.validate()
    required = {"reward_machine", "labeling", "descriptions"}
    complete = {stage for stage, status in bundle.manifest.stage_status.items() if status == "complete"}
    if required - complete or diagnostics:
        raise ValueError("Judging requires accepted RM, labeling, and description stages")
    request = getattr(engine, "request_text", None)
    if request is None:
        raise RuntimeError("Judging requires an engine with request_text")
    settings = settings or JudgeSettings()
    evidence = bundle.execution_evidence if execution_evidence is None else execution_evidence
    prompt = json.dumps(
        {
            "task": bundle.manifest.inputs.get("task", bundle.manifest.task),
            "environment_markdown": bundle.manifest.inputs.get("environment_markdown", ""),
            "proposition_semantics": bundle.manifest.proposition_semantics,
            "api_definitions": bundle.manifest.api_definitions,
            "candidate_rm": _machine_text(bundle),
            "candidate_labeling": bundle.labeling_source,
            "candidate_state_descriptions": bundle.state_descriptions,
            "execution_evidence": list(evidence),
        },
        indent=2,
        sort_keys=True,
    )
    try:
        response = request(
            "You are an independent ARM-FM artifact judge. Return JSON with rm_correct, labeling_correct, and reason.",
            prompt,
            model=settings.model,
        )
    except TypeError:
        try:
            response = request(
                "You are an independent ARM-FM artifact judge. Return JSON with rm_correct, labeling_correct, and reason.",
                prompt,
            )
        except Exception as error:
            return JudgeDecision(False, False, f"unscored: {error}", scored=False, attempt=_bundle_attempt(bundle))
    except Exception as error:
        return JudgeDecision(False, False, f"unscored: {error}", scored=False, attempt=_bundle_attempt(bundle))
    try:
        value = json.loads(_strip_fence(str(response)))
    except json.JSONDecodeError as error:
        return JudgeDecision(False, False, f"missing judgment: {error}", scored=False, attempt=_bundle_attempt(bundle))
    if not isinstance(value, dict) or not isinstance(value.get("rm_correct"), bool) or not isinstance(value.get("labeling_correct"), bool):
        return JudgeDecision(False, False, "missing judgment fields", scored=False, attempt=_bundle_attempt(bundle))
    reason = value.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return JudgeDecision(False, False, "missing judgment reason", scored=False, attempt=_bundle_attempt(bundle))
    return JudgeDecision(
        value["rm_correct"], value["labeling_correct"], reason.strip(),
        attempt=_bundle_attempt(bundle),
    )


def aggregate_judgments(
    decisions: Iterable[JudgeDecision],
    *,
    submitted: int | None = None,
    generation_failures: int = 0,
) -> BenchmarkSummary:
    decisions = tuple(decisions)
    submitted = len(decisions) + generation_failures if submitted is None else submitted
    counts = Counter(decision.category for decision in decisions)
    for category in ("both", "rm_only", "labeling_only", "neither", "unscored"):
        counts.setdefault(category, 0)
    return BenchmarkSummary(
        submitted,
        sum(decision.scored for decision in decisions),
        generation_failures,
        dict(counts),
        first_attempt_scored=sum(decision.scored and decision.attempt == 1 for decision in decisions),
        refined_scored=sum(decision.scored and decision.attempt > 1 for decision in decisions),
    )


def frozen_evaluate(
    policy: object,
    tasks: Sequence[ArtifactBundle],
    *,
    episodes: int = 1,
    runner: Callable[[object, ArtifactBundle], Mapping[str, float]] | None = None,
) -> list[Mapping[str, float]]:
    """Evaluate frozen policy/bundle pairs; the policy is never updated here."""
    if episodes < 1:
        raise ValueError("episodes must be positive")
    if getattr(policy, "training", False):
        raise ValueError("Frozen evaluation requires a policy in evaluation mode")
    if hasattr(policy, "eval"):
        policy.eval()
    parameters = list(policy.parameters()) if hasattr(policy, "parameters") else []
    requires_grad = [parameter.requires_grad for parameter in parameters]
    for parameter in parameters:
        parameter.requires_grad_(False)
    if runner is None:
        raise ValueError("A frozen evaluation runner is required")
    results = []
    try:
        try:
            import torch
            context = torch.no_grad()
        except ImportError:
            from contextlib import nullcontext
            context = nullcontext()
        with context:
            for bundle in tasks:
                bundle.validate(require_complete=True)
                for _ in range(episodes):
                    results.append(runner(policy, bundle))
    finally:
        for parameter, was_trainable in zip(parameters, requires_grad, strict=True):
            parameter.requires_grad_(was_trainable)
    return results


def _machine_text(bundle: ArtifactBundle) -> str:
    from .runtime import serialize_paper_reward_machine

    if bundle.reward_machine is None:
        return ""
    return serialize_paper_reward_machine(bundle.reward_machine)


def _bundle_attempt(bundle: ArtifactBundle) -> int:
    value = bundle.manifest.generation.get("attempt", 1)
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 1


def _strip_fence(text: str) -> str:
    if "```" not in text:
        return text.strip()
    return text.split("```", 2)[1].removeprefix("json").strip()
