"""Rebuild a compiler bundle's Reward Machine with one reward part switched off.

No model call, except the redo of the state descriptions when the recurrent soft penalty is off.
"""

import copy
from collections.abc import Sequence
from dataclasses import asdict, fields, replace
from pathlib import Path

from src.arm_fm import ArtifactBundle, BundleValidationError, load_bundle
from src.arm_fm.generation import pair_state_descriptions
from src.benchmark.traces import NO_PART
from src.compiler import (
    ClauseProposal,
    CompilationResult,
    PaperRewardMachine,
    Proposal,
    RewardSwitches,
    build_compilation_result,
    compile_dfas,
    compiler_machine_to_paper,
    serialize_paper_reward_machine,
)
from src.config import Configuration, PriorityLevel
from src.models import EnvironmentDescription
from src.utils import get_engine, ltlf_of, preflight_paths, print_warning

from .embed_larm import embed_larm
from .generate_rm import tag_states

# Command-line name -> the RewardSwitches field it switches off.
OFF_PARTS = {item.name.removeprefix("reward_"): item.name for item in fields(RewardSwitches)}
OFF_CHOICES = (NO_PART, *OFF_PARTS)

# What a machine must have for the switch to change anything; named when the ablation is a no-op.
_MISSING_PART = {
    "progress": "progress term",
    "well": "edge into the well",
    "soft_break": "soft rule that can break",
    "soft_pending": "soft rule that can still be pending at the finish",
    "end_judgment": "end judgment",
    "recurrent_soft_penalty": "soft rule that can break more than once",
}


class AblationError(Exception):
    """The bundle cannot be ablated; the message says why in one line."""


def ablate_rm(CONFIG: Configuration, off: str, destination: Path) -> bool:
    """Write ``destination``: ``CONFIG.bundle`` with one reward part switched off.

    The machine is rebuilt from the compiled clauses the source stores, through the compiler
    path (clause, LTLf, MONA, reward layer), with no model call, starting from the reward
    switches the source records. A rebuild with nothing switched off must give the source's
    text, or nothing is written. Labeling, state descriptions and embeddings are copied while
    the states and their transitions are unchanged. Switching the recurrent soft penalty off
    changes them, and then the descriptions (a model call) and the embeddings (the local
    server) are made again. The ablated bundle drops the source's critic verdict: no critic
    judged the new machine.

    Args:
        CONFIG: Settings; ``bundle`` is the source bundle.
        off: A key of ``OFF_PARTS``, or ``none`` for a rebuild with nothing switched off.
        destination: The bundle folder to write.

    Returns:
        True when the bundle was written, False after a one-line message on stderr. After a
        failed embedding step the folder is already written, without embeddings; the message
        says so.
    """
    try:
        summary = _ablate(CONFIG, off, destination)
    # RuntimeError: the engine, the state tagging or the embedding server failed.
    except (AblationError, RuntimeError) as error:
        print_warning(f"ablate-rm: {error}")
        return False
    print(summary)
    return True


def _load_source(CONFIG: Configuration, off: str, destination: Path) -> ArtifactBundle:
    """The source bundle, after the checks that need no rebuild."""
    if off not in OFF_CHOICES:
        raise AblationError(f"--off must be one of {', '.join(OFF_CHOICES)}: {off!r}")
    if destination.resolve() == CONFIG.bundle.resolve():
        raise AblationError(f"--output is the source bundle {CONFIG.bundle}; choose another folder")
    try:
        source = load_bundle(CONFIG.bundle)
    except BundleValidationError as error:
        raise AblationError(str(error)) from error
    if source.reward_machine is None:
        raise AblationError(f"{CONFIG.bundle} has no reward machine")
    if not source.manifest.generation.get("clauses"):
        raise AblationError(
            f"{CONFIG.bundle} stores no compiled clauses (manifest generation.clauses); "
            "only bundles made by generate-larm --mode compiler with the reward switches can be "
            "ablated"
        )
    previous = source.manifest.effective_settings.get("ablation")
    if previous is not None:
        raise AblationError(
            f"{CONFIG.bundle} is already an ablation (off={previous['off']}); "
            f"ablate its source bundle {previous['source_bundle']}"
        )
    try:
        preflight_paths([destination], overwrite=CONFIG.overwrite, kind="Bundle folder")
    except ValueError as error:
        raise AblationError(str(error)) from error
    return source


def _ablate(CONFIG: Configuration, off: str, destination: Path) -> str:
    source = _load_source(CONFIG, off, destination)
    environment, proposal = _stored_task(CONFIG, source)
    dfas = compile_dfas(proposal, CONFIG)
    source_text = (CONFIG.bundle / "reward_machine.txt").read_text(encoding="utf-8")

    # The control: the source's own switches, nothing off, must give the source's text.
    recorded = _recorded_switches(source)
    result, machine = _build(environment, proposal, dfas, recorded)
    if serialize_paper_reward_machine(machine) != source_text:
        raise AblationError(
            f"rebuilding {CONFIG.bundle} with the settings it records gives another machine; "
            "the compiler or a setting the bundle does not record changed since it was made, "
            "so an ablation would not be comparable to it"
        )

    switches = recorded
    if off in OFF_PARTS:
        switches = replace(recorded, **{OFF_PARTS[off]: False})
        result, machine = _build(environment, proposal, dfas, switches)
    no_op = serialize_paper_reward_machine(machine) == source_text

    bundle = _ablated_bundle(source, machine, result.text)
    bundle.manifest.effective_settings.update(asdict(switches))
    bundle.manifest.effective_settings["ablation"] = {
        "off": off,
        "source_bundle": str(CONFIG.bundle.resolve()),
        # `source_revision` is the commit in the source's provenance stamp; null when the source
        # has no stamp.
        "source_revision": (source.manifest.provenance.get("stamp") or {}).get("commit"),
        "no_op": no_op,
    }
    unchanged = skeleton(machine) == skeleton(source.reward_machine)
    embedded = bool(source.embeddings)
    if not unchanged:
        _redescribe(CONFIG, source, bundle, result)
    bundle.save(destination, overwrite=CONFIG.overwrite)
    if not unchanged and embedded:
        # The same local-server embedding the other bundles use (``embed-larm --embedding-server``).
        try:
            embed_larm(replace(CONFIG, bundle=destination, embeddings=True))
        except RuntimeError as error:
            raise AblationError(
                f"{error}; {destination} was written without embeddings, "
                "rerun with --overwrite to try again"
            ) from error

    return _summary(off, no_op, unchanged, embedded, destination)


def _stored_task(
    CONFIG: Configuration, source: ArtifactBundle
) -> tuple[EnvironmentDescription, Proposal]:
    """The environment and the compiled clauses the source stores."""
    markdown = source.manifest.inputs.get("environment_markdown", "")
    if not markdown:
        raise AblationError(f"{CONFIG.bundle} stores no environment text (inputs)")
    environment = EnvironmentDescription.from_markdown(markdown, source.manifest.environment)

    stored = source.manifest.generation["clauses"]
    # A bundle made before `clause_texts` falls back to the formula as the clause's sentence.
    texts = source.manifest.generation.get("clause_texts") or [
        f"{pattern}({', '.join(propositions)})" for pattern, propositions, _ in stored
    ]
    clauses = tuple(
        ClauseProposal(
            text,
            pattern,
            tuple(propositions),
            PriorityLevel(priority),
            ltlf_of(pattern, propositions),
        )
        for text, (pattern, propositions, priority) in zip(texts, stored, strict=True)
    )
    return environment, Proposal(task=source.manifest.task.strip(), clauses=clauses)


def _recorded_switches(source: ArtifactBundle) -> RewardSwitches:
    """The reward switches the source was made with; one that records none paid every part."""
    settings = source.manifest.effective_settings
    return RewardSwitches(
        **{
            item.name: settings[item.name]
            for item in fields(RewardSwitches)
            if item.name in settings
        }
    )


def _build(
    environment: EnvironmentDescription,
    proposal: Proposal,
    dfas: Sequence[dict],
    switches: RewardSwitches,
) -> tuple[CompilationResult, PaperRewardMachine]:
    """The compiler's result and its machine in the bundle's paper format, with the DFAs reused."""
    result = build_compilation_result(environment, proposal, dfas, switches)
    return result, compiler_machine_to_paper(result.reward_machine, environment.proposition_ids)


def _ablated_bundle(
    source: ArtifactBundle, machine: PaperRewardMachine, compiler_text: str
) -> ArtifactBundle:
    """The source bundle with the new machine; its history shows the new text, not the old.

    No critic judged the new machine, so the critic verdict is dropped (an absent key passes
    ``validate(require_complete=True)``; ``None`` would not), the critic model is cleared, and
    the compiler attempt is ``ablated``, not ``accepted``. The generation record says the copy
    is not a first-attempt or refined win. No loader reads an attempt's status.
    """
    bundle = replace(
        source,
        manifest=copy.deepcopy(source.manifest),
        reward_machine=machine,
        attempts=copy.deepcopy(source.attempts),
        raw_responses=copy.deepcopy(source.raw_responses),
    )
    bundle.manifest.generation["compiler_text"] = compiler_text
    bundle.manifest.validation.pop("critic", None)
    bundle.manifest.effective_settings["critic_model"] = None
    bundle.manifest.generation.update(
        first_attempt=False, refined=False, attempt_classification="ablated"
    )
    for entry in (*bundle.attempts, *bundle.raw_responses):
        if entry.get("stage") == "compiler":
            entry["candidate"] = compiler_text
            if "raw_response" in entry:
                entry["raw_response"] = compiler_text
            if "status" in entry:
                entry["status"] = "ablated"
    return bundle


def skeleton(machine: PaperRewardMachine) -> tuple:
    """What the state descriptions and embeddings depend on: states and their transitions."""
    return (
        set(machine.states),
        machine.initial_state,
        set(machine.final_states),
        set(machine.rejecting_states),
        {(item.source, item.condition, item.destination) for item in machine.transitions},
    )


def _redescribe(
    CONFIG: Configuration, source: ArtifactBundle, bundle: ArtifactBundle, result: CompilationResult
) -> None:
    """Describe the changed states again; the embeddings follow after the save.

    ``tag_states`` returns only the descriptions, not the raw answers, so the call is recorded by
    its model in ``ablation.description_model``, not as attempts.
    """
    model = source.manifest.effective_settings.get("generator_model") or CONFIG.generator_model
    print(
        f"ablate-rm: the states changed, so the {len(bundle.reward_machine.states)} state "
        f"descriptions are made again with {model}"
    )
    ablation = bundle.manifest.effective_settings["ablation"]
    ablation["description_model"] = model
    if not source.manifest.generation.get("clause_texts"):
        print_warning(
            "the source stores no clause sentences; the new descriptions are written from the "
            "formulas"
        )
    engine = get_engine(
        CONFIG,
        result.environment,
        model,
        warn=lambda message: print_warning(f"Generator {message}"),
    )
    descriptions = tag_states(engine, bundle.manifest.task, result, print_warning)
    bundle.state_descriptions = pair_state_descriptions(result, descriptions)
    bundle.embeddings = {}
    bundle.manifest.stage_status.pop("embeddings", None)
    bundle.manifest.effective_settings.pop("embedding", None)
    # The server path of embed_larm embeds with CONFIG's model and no context prefix.
    new = {
        "model": CONFIG.embedding_model,
        "model_revision": CONFIG.embedding_revision,
        "context": "",
    }
    recorded = source.manifest.effective_settings.get("embedding")
    absent = {"context": ""}  # an in-process embedding records no context
    old = {key: recorded.get(key, absent.get(key)) for key in new} if recorded else new
    if old != new:
        print_warning(f"the new embeddings use {new}; the source's use {old}")


def _summary(off: str, no_op: bool, unchanged: bool, embedded: bool, destination: Path) -> str:
    descriptions = "copied" if unchanged else "regenerated"
    embeddings = ("copied" if unchanged else "regenerated") if embedded else "none"
    lines = [
        f"ablate-rm: off={off} no_op={str(no_op).lower()} descriptions={descriptions} "
        f"embeddings={embeddings} -> {destination}"
    ]
    if no_op and off != NO_PART:
        lines.append(
            f"ablate-rm: no-op, the machine has no {_MISSING_PART[off]}, "
            f"so switching {off} off changes nothing"
        )
    return "\n".join(lines)
