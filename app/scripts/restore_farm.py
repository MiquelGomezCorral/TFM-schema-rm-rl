"""Rebuild FARM failure bundles from their generation logs.

Before generation kept its accepted steps, a FARM run that failed after the critic accepted a
machine (labeling rejected three times, or a labeling request that timed out) saved a bundle with
no machine. The accepted machine, its clauses and its state descriptions survive in the card's log
(``<name>.log`` beside the bundle folder). This command rebuilds the bundle the current
``generate-larm`` would have saved: the machine, its clauses, the compiler attempt, the state
descriptions, one attempt for the stage that failed and ``stage_status`` naming it. The manifest
gets ``provenance.restored_from_log`` (card log, run log, ``labeling_tries``). The role models, the
attempt limit and the reward switches go in through ``record_bundle_role_models`` (models and
reasoning from the failed run's stamp, the limit from the log's ``attempt k/N`` lines, the default
reward switches: they rebuild the log's machine byte for byte, as checked below); the failed run's
own stamp is kept as it was.

A log holds no per-try labeling lines (only ``failed after N requests``), so the one recorded
labeling attempt is not a count of the run. The mark says ``labeling_tries: "unknown"`` and
``generation-table`` leaves the bundle out of its "labeling tries" mean.

``status.json`` stays ``pipeline-failed`` with a reason naming the stage. A bundle the run classed
``provider-error`` (a labeling-critic request timed out after the critic accepted the machine) is
restored too: its status becomes ``pipeline-failed`` and the old one is kept as ``original_status``,
so ``repair-labeling`` can finish it.

The machine is rebuilt from the log's clauses (FL-AT/MONA) and must serialize to the log's accepted
machine text, byte for byte. Run it on a bundle folder once: a restored bundle is no longer a
failure bundle and is skipped.
"""

import ast
import json
import re
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from src.arm_fm import ArtifactBundle
from src.arm_fm.generation import StageAttempt, failed_compiler_bundle, record_bundle_role_models
from src.benchmark.labeling_repair import status_path
from src.benchmark.traces import write_json
from src.compiler import (
    ClauseProposal,
    CompilationResult,
    Proposal,
    build_compilation_result,
    compile_dfas,
    compiler_machine_to_paper,
)
from src.config import Configuration, PriorityLevel
from src.models import EnvironmentDescription
from src.utils import ltlf_of

ENTRY = re.compile(r"^\[total [\d.]+s \| step [\d.]+s\] ", re.MULTILINE)
RESTORABLE_STATUSES = ("pipeline-failed", "provider-error")
# "Embedding state descriptions" contains "state descriptions", so the embeddings key is first.
FAILED_STEPS = {
    "embedding": "embeddings",
    "labeling": "labeling",
    "state descriptions": "descriptions",
}


class RestoreError(RuntimeError):
    """The log gives an accepted machine, but what it gives does not rebuild it."""


class NothingToRestoreError(RestoreError):
    """The bundle is not a FARM failure bundle without a machine, or its log has no accepted one."""


def restore_farm(bundles: Path, only: Sequence[str]) -> bool:
    """Restore every FARM failure bundle of ``bundles`` (or the names in ``only``) from its log.

    Args:
        bundles: The folder of FARM bundles (``<name>/`` with ``<name>.status.json`` and
            ``<name>.log`` beside it).
        only: Bundle names to restore; a name that cannot be restored is an error. Without
            names, every bundle that cannot be restored is skipped with its reason.

    Returns:
        False when a bundle that had to be restored could not be.
    """
    names = list(only) or sorted(
        path.name.removesuffix(".status.json") for path in bundles.glob("*.status.json")
    )
    errors = 0
    for name in names:
        try:
            print(f"{name}: restored ({restore(bundles, name)[:110]}...)", flush=True)
        except NothingToRestoreError as error:
            errors += bool(only)
            print(f"{name}: {'ERROR' if only else 'skipped'} ({error})", flush=True)
        except (RestoreError, OSError, KeyError, ValueError) as error:
            errors += 1
            print(f"{name}: ERROR {error}", flush=True)
    print(f"restore-farm: {errors} error(s)")
    return errors == 0


def parse_log(text: str) -> dict:
    """The last critic-accepted machine of a log, with what followed it.

    Keys: ``proposal`` (the validated clauses), ``machine`` (the accepted RM text),
    ``descriptions`` (state -> text, or None), ``stage`` (the stage that failed after the
    acceptance), ``detail`` (its failure text) and ``run_log``.

    Raises:
        NothingToRestoreError: The log shows no critic-accepted machine.
        RestoreError: The log shows an accepted machine but no stage that failed after it.
    """
    entries = [(match.end(), match.start()) for match in ENTRY.finditer(text)]
    messages = [
        text[start : entries[index + 1][1] if index + 1 < len(entries) else len(text)].rstrip("\n")
        for index, (start, _) in enumerate(entries)
    ]
    accepted: dict | None = None
    proposal = machine = None
    for message in messages:
        head, _, body = message.partition("\n")
        if head == "Validated proposal:":
            proposal = json.loads(body)
        elif head == "Serialized Reward Machine:":
            lines = body.split("\n")
            machine = "\n".join(lines[: lines.index("") if "" in lines else len(lines)]) + "\n"
        elif head == "Critic verdict:":
            if ast.literal_eval(body).get("accepted") is True and proposal and machine:
                accepted = {
                    "proposal": proposal,
                    "machine": machine,
                    "descriptions": None,
                    "stage": None,
                    "detail": "",
                }
        elif accepted is not None and head == "State descriptions:":
            accepted["descriptions"] = ast.literal_eval(body)
        elif accepted is not None:
            _read_failure(accepted, head)
    if accepted is None:
        raise NothingToRestoreError("the log shows no critic-accepted machine")
    if accepted["stage"] is None:
        raise RestoreError("the log shows an accepted machine but no failed stage after it")
    run_log = re.search(r"Run log: (\S+)", text)
    accepted["run_log"] = run_log.group(1) if run_log else None
    return accepted


def _read_failure(accepted: dict, head: str) -> None:
    """Take the failed stage and the failure text from one log entry that follows the acceptance."""
    step = re.search(r"Task \d+: (?:Generating (?:MiniGrid )?)?([\w ]+?) failed", head)
    if step and accepted["stage"] is None:
        accepted["stage"] = next(
            (stage for key, stage in FAILED_STEPS.items() if key in step.group(1).lower()), None
        )
    if head.startswith("Generation failed: "):
        # The failure text is the entry's first line; a traceback may follow it.
        accepted["detail"] = " ".join(head.removeprefix("Generation failed: ").split())


def restore(folder: Path, name: str) -> str:
    """Rebuild bundle ``name`` of ``folder`` from ``<name>.log``; return the reason it now holds."""
    path, log_path = folder / name, folder / f"{name}.log"
    status_file = status_path(path)
    status = json.loads(status_file.read_text(encoding="utf-8"))
    if status.get("status") not in RESTORABLE_STATUSES or (path / "reward_machine.txt").exists():
        raise NothingToRestoreError("not a FARM failure bundle without a machine")
    log_text = log_path.read_text(encoding="utf-8")
    found = parse_log(log_text)
    old = ArtifactBundle.load(path, allow_missing_labeling=True)

    result = _rebuild_machine(old, found)
    stage, detail = found["stage"], found["detail"]
    reason = (
        f"Compiler generation failed at the {stage} stage after the machine was accepted: "
        f"{detail[:300]}"
    )
    bundle = failed_compiler_bundle(
        result, stage, reason, [StageAttempt(stage, 1, "failed", error=detail)]
    )

    # What the failed run already recorded: its requests, stamp, settings. The critic accepted it.
    stamp = old.manifest.provenance.get("stamp") or {}
    limit = re.search(r"attempt \d+/(\d+)", log_text)
    config = Configuration(
        generator_model=stamp.get("generator_model"),
        critic_model=stamp.get("critic_model"),
        reasoning=stamp.get("reasoning", "none"),
        **({"attempts": int(limit.group(1))} if limit else {}),
    )
    bundle.raw_responses.extend(old.raw_responses)
    record_bundle_role_models(bundle, config)  # sets the critic verdict, models, limit, switches
    bundle.manifest.effective_settings.update(old.manifest.effective_settings)
    # The stamp is the failed run's own, not the commit of this restore.
    if stamp:
        bundle.manifest.provenance["stamp"] = stamp
    bundle.manifest.provenance["restored_from_log"] = {
        "log": str(log_path),
        "run_log": found["run_log"],
        "labeling_tries": "unknown",
    }

    # The status goes first: the machine file is what marks a bundle as restored, so a crash
    # between the two writes leaves a failure bundle that a rerun restores again.
    new_status = {**status, "reason": f"RuntimeError: {reason}"}
    if status["status"] != "pipeline-failed":
        new_status |= {"status": "pipeline-failed", "original_status": status["status"]}
    write_json(status_file, new_status, indent=2)
    bundle.save(path, overwrite=True)
    return reason


def _rebuild_machine(old: ArtifactBundle, found: dict) -> CompilationResult:
    """The compiler result for the log's clauses, with the log's state descriptions.

    Raises:
        RestoreError: The clauses do not rebuild the log's accepted machine text.
    """
    environment = EnvironmentDescription.from_markdown(
        old.manifest.inputs["environment_markdown"], old.manifest.environment
    )
    clauses = tuple(
        ClauseProposal(
            item["normalized_clause"],
            item["pattern"],
            tuple(item["propositions"]),
            PriorityLevel(item["priority"]),
            ltlf_of(item["pattern"], item["propositions"]),
        )
        for item in found["proposal"]
    )
    proposal = Proposal(task=old.manifest.task.strip(), clauses=clauses)
    result = build_compilation_result(
        environment, proposal, compile_dfas(proposal, Configuration())
    )
    if result.text != found["machine"]:
        raise RestoreError("the clauses of the log do not rebuild the log's accepted machine")
    if found["descriptions"]:
        states = compiler_machine_to_paper(
            result.reward_machine, result.environment.proposition_ids
        ).states
        result = replace(
            result, state_descriptions=tuple(found["descriptions"][state] for state in states)
        )
    return result
