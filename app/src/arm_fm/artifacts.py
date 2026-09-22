"""Inspectable, one-task ARM-FM artifact bundles."""

from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from .runtime import (
    PaperRewardMachine,
    RuntimeValidationError,
    load_labeling_functions,
    parse_paper_reward_machine,
)


class BundleValidationError(ValueError):
    """A generated task bundle is incomplete or internally inconsistent."""


@dataclass
class BundleManifest:
    """Versioned metadata for one task and one generated artifact bundle."""

    task: str
    environment: str
    proposition_semantics: dict[str, str] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    generation: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)
    stage_status: dict[str, str] = field(default_factory=dict)
    inputs: dict[str, Any] = field(default_factory=dict)
    api_definitions: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    effective_settings: dict[str, Any] = field(default_factory=dict)
    rm_mode: str = "arm-fm"
    bundle_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BundleManifest":
        if not isinstance(data, dict):
            raise BundleValidationError("Bundle manifest must be an object")
        required = {"task", "environment"}
        if not required <= data.keys():
            raise BundleValidationError("Bundle manifest requires task and environment")
        allowed = set(cls.__dataclass_fields__)
        unknown = set(data) - allowed
        if unknown:
            raise BundleValidationError("Bundle manifest has unknown field(s): " + ", ".join(sorted(unknown)))
        return cls(**data)


@dataclass
class ArtifactBundle:
    """In-memory representation of all files needed by training/evaluation."""

    manifest: BundleManifest
    reward_machine: PaperRewardMachine | None
    labeling_source: str = ""
    state_descriptions: dict[str, str] = field(default_factory=dict)
    embeddings: dict[str, list[float]] = field(default_factory=dict)
    attempts: list[dict[str, Any]] = field(default_factory=list)
    raw_responses: list[dict[str, Any]] = field(default_factory=list)
    execution_evidence: list[dict[str, Any]] = field(default_factory=list)

    def validate(self, *, require_complete: bool = False) -> list[str]:
        """Return diagnostics, or raise for malformed structure."""
        diagnostics: list[str] = []
        if not self.manifest.task.strip():
            raise BundleValidationError("Bundle task must be nonempty")
        if self.reward_machine is None:
            diagnostics.append("reward machine is missing")
            if require_complete:
                raise BundleValidationError("reward machine is missing")
            return diagnostics
        expected_propositions = tuple(self.manifest.proposition_semantics) or self.reward_machine.propositions
        if set(expected_propositions) != set(self.reward_machine.propositions):
            diagnostics.append("RM propositions do not match the environment vocabulary")
        try:
            load_labeling_functions(self.labeling_source, expected_propositions)
        except RuntimeValidationError as error:
            diagnostics.append(str(error))
        if set(self.state_descriptions) != set(self.reward_machine.states):
            diagnostics.append("state descriptions do not align with RM states")
        if self.embeddings and set(self.embeddings) != set(self.state_descriptions):
            diagnostics.append("embeddings do not align with state descriptions")
        if self.embeddings:
            for state, vector in self.embeddings.items():
                try:
                    if not vector or not all(math.isfinite(float(value)) for value in vector):
                        diagnostics.append(f"embedding for {state!r} must be finite and nonempty")
                except (TypeError, ValueError):
                    diagnostics.append(f"embedding for {state!r} must be numeric")
        if require_complete:
            required = {"reward_machine", "labeling", "descriptions", "embeddings"}
            missing_stages = required - {
                stage for stage, status in self.manifest.stage_status.items() if status == "complete"
            }
            if missing_stages:
                diagnostics.append("incomplete stages: " + ", ".join(sorted(missing_stages)))
            if not self.embeddings:
                diagnostics.append("embeddings are missing")
            for check in ("structural", "critic"):
                if check in self.manifest.validation and self.manifest.validation.get(check) is not True:
                    diagnostics.append(f"{check} validation is incomplete")
            if diagnostics:
                raise BundleValidationError("; ".join(diagnostics))
        return diagnostics

    @property
    def complete(self) -> bool:
        try:
            return not self.validate(require_complete=True)
        except BundleValidationError:
            return False

    def save(self, directory: str | Path, *, overwrite: bool = False) -> Path:
        """Write a bundle using simple JSON/text files and no hidden state."""
        target = Path(directory)
        if target.exists() and any(target.iterdir()) and not overwrite:
            raise FileExistsError(f"Bundle directory already exists: {target}")
        target.mkdir(parents=True, exist_ok=True)
        _atomic_text(target / "manifest.json", json.dumps(self.manifest.to_dict(), indent=2, sort_keys=True) + "\n")
        reward_path = target / "reward_machine.txt"
        if self.reward_machine is None:
            if reward_path.exists():
                reward_path.unlink()
        else:
            _atomic_text(reward_path, _serialize_machine(self.reward_machine))
        _atomic_text(target / "labeling.py", self.labeling_source)
        _atomic_text(target / "state_descriptions.json", _json(self.state_descriptions))
        _atomic_text(target / "embeddings.json", _json(self.embeddings))
        _atomic_text(target / "attempts.json", _json(self.attempts))
        _atomic_text(target / "raw_responses.json", _json(self.raw_responses))
        _atomic_text(target / "execution_evidence.json", _json(self.execution_evidence))
        return target

    @classmethod
    def load(cls, directory: str | Path) -> "ArtifactBundle":
        root = Path(directory)
        try:
            manifest = BundleManifest.from_dict(json.loads((root / "manifest.json").read_text(encoding="utf-8")))
            reward_path = root / "reward_machine.txt"
            machine = (
                parse_paper_reward_machine(
                    reward_path.read_text(encoding="utf-8"),
                    propositions=tuple(manifest.proposition_semantics),
                )
                if reward_path.exists()
                else None
            )
            labeling = (root / "labeling.py").read_text(encoding="utf-8")
            descriptions = _load_json(root / "state_descriptions.json", {})
            embeddings = _load_json(root / "embeddings.json", {})
            attempts = _load_json(root / "attempts.json", [])
            responses = _load_json(root / "raw_responses.json", [])
            evidence = _load_json(root / "execution_evidence.json", [])
        except (OSError, json.JSONDecodeError, RuntimeValidationError) as error:
            raise BundleValidationError(f"Could not load bundle '{root}': {error}") from error
        bundle = cls(manifest, machine, labeling, descriptions, embeddings, attempts, responses, evidence)
        bundle.validate()
        return bundle


def load_bundle(directory: str | Path) -> ArtifactBundle:
    """Convenience loader for persisted bundles."""
    return ArtifactBundle.load(directory)


def validate_bundle(directory: str | Path, *, require_complete: bool = False) -> list[str]:
    """Validate a persisted bundle without mutating it."""
    return ArtifactBundle.load(directory).validate(require_complete=require_complete)


def _serialize_machine(machine: PaperRewardMachine) -> str:
    from .runtime import serialize_paper_reward_machine

    return serialize_paper_reward_machine(machine)


def _json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _load_json(path: Path, default: object) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temporary:
        temporary.write(value)
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, path)
