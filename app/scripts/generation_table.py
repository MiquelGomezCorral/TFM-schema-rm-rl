"""The generation table of a benchmark folder: how often each generation step was accepted.

Per arm and suite, and per arm over the main suites (``base``, ``complex``, ``templates``; the
pilot and the ablations stay apart): the Reward Machine (RM) generations accepted out of all
bundles, the mean RM tries, the labeling generations accepted at generation out of those that
reached labeling, the mean labeling tries, the labelings ok after repair out of the checked ones,
the mean repair rounds and the bundles restored from a log.

Only the files beside each bundle are read: ``attempts.json``, the manifest, the card log, the
labeling-check record, the regeneration sidecar and the ``restored_from_log`` mark of a restored
bundle. The RM tries of a bundle come from the run stats the manifest's stamp holds, else from the
card log's ``attempt k/N`` lines, else from ``attempts.json``; each row says how many bundles used
which. The two "at generation" labeling columns come from the original generation: the sidecar's
``previous`` attempts when ``regenerate-labeling`` ran, else ``attempts.json``. The regenerated
columns come from the latest loop of a sidecar.
"""

import json
import re
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path
from statistics import mean
from typing import Any

from src.benchmark.labeling_repair import DONE_OUTCOMES
from src.benchmark.labeling_repair import record_path as check_record_path
from src.benchmark.traces import BundleRef, as_object, find_bundles, read_json, write_json

from .regenerate_labeling import ACCEPTED, FAILED, sidecar_path

MAIN_SUITES = ("base", "complex", "templates")
RM_STAGES = ("reward_machine", "compiler")
ACCEPTED_STATUSES = ("accepted", "ablated")
PROPOSAL_STEP = re.compile(r"attempt \d+/\d+ — Generating proposal")
NOTES = (
    "RM tries (all): mean over the bundles with at least one try; a bundle with 0 tries is left out.",
    "labeling tries: original generation only (the regeneration sidecar's previous attempts); "
    "restored bundles whose log has no per-try labeling lines are left out of the mean.",
    "labeling regenerated accepted: bundles accepted out of those a regeneration loop ran on; "
    "regeneration tries: mean tries of the latest loop.",
    "repair rounds: mean over the failed check records with at least one round; a failed record "
    "with 0 rounds is left out, though it stays in the ok-after-repair denominator.",
)
HEADER = (
    "group",
    "arm",
    "bundles",
    "RM accepted",
    "RM tries (accepted)",
    "RM tries (all)",
    "RM tries from",
    "labeling accepted at generation",
    "labeling tries",
    "labeling regenerated accepted",
    "regeneration tries",
    "labeling ok after repair",
    "repair rounds",
    "restored from log",
)


def generation_table(root: Path, output: Path | None) -> None:
    """Print the Markdown table of ``root`` (``<suite>/bundles/<arm>/<name>/``); write its JSON.

    Args:
        root: Folder of suites, such as ``experiments/benchmark``.
        output: JSON file to write, or None to print only.
    """
    rows = _rows(root)
    print(_markdown(rows))
    print("\n" + "\n".join(f"- {note}" for note in NOTES))
    if output is not None:
        print(f"wrote {write_json(output, rows, indent=2)}")


def _rows(root: Path) -> list[dict[str, Any]]:
    """One row per (suite, arm), then one per arm over the main suites."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for suite_folder in sorted(root.glob("*/bundles")):
        suite = suite_folder.parent.name
        for ref in find_bundles(suite_folder):
            facts = _bundle_facts(ref)
            groups[(suite, facts["arm"])].append(facts)
            if suite in MAIN_SUITES:
                groups[("all main suites", facts["arm"])].append(facts)
    return [_row(group, arm, bundles) for (group, arm), bundles in sorted(groups.items())]


def _bundle_facts(ref: BundleRef) -> dict[str, Any]:
    """What one bundle says about its own generation; a failed FARM bundle has no machine file."""
    manifest = read_json(ref.path / "manifest.json")
    attempts = _read_list(ref.path / "attempts.json")
    machine = [item for item in attempts if item.get("stage") in RM_STAGES]
    regeneration = read_json(sidecar_path(ref))
    # The original generation: a regeneration replaced the bundle's own labeling attempts.
    original = as_object(regeneration.get("previous")).get("attempts", attempts)
    labeling = [item for item in original if item.get("stage") == "labeling"]
    regenerated = regeneration.get("outcome") in (ACCEPTED, FAILED)
    restored = as_object(as_object(manifest.get("provenance")).get("restored_from_log"))
    record = read_json(check_record_path(ref))
    accepted = any(item.get("status") in ACCEPTED_STATUSES for item in machine)
    tries, source = _rm_tries(ref, manifest, machine)
    return {
        "arm": ref.arm if not ref.ablation else _arm_of(manifest),
        "rm_accepted": accepted,
        "rm_tries": tries,
        "rm_tries_source": source,
        "reached_labeling": accepted and bool(labeling),
        "labeling_accepted": any(item.get("status") == "accepted" for item in labeling),
        "labeling_tries": len(labeling),
        # A restored log without per-try lines gave one try; that is not a count of the run.
        "labeling_tries_known": not restored or restored.get("labeling_tries") == "logged",
        "regenerated": regenerated,
        "regenerated_accepted": regeneration.get("outcome") == ACCEPTED,
        "regenerated_tries": len(regeneration.get("attempts", ())) if regenerated else None,
        "checked": bool(record),
        "label_ok": record.get("outcome") in DONE_OUTCOMES,
        "repair_rounds": len(record.get("rounds", ())) if record.get("failed") else None,
        "restored": bool(restored),
    }


def _rm_tries(
    ref: BundleRef, manifest: Mapping[str, Any], machine: list[dict[str, Any]]
) -> tuple[int, str]:
    """How many Reward Machine candidates the run made, and where that number came from.

    A FARM bundle used to keep only its accepted candidate in ``attempts.json``, so the run
    stats come first.
    """
    stamp = as_object(as_object(manifest.get("provenance")).get("stamp")).get("attempts")
    if isinstance(stamp, int):
        return stamp, "run stats"
    log = ref.path.with_name(ref.path.name + ".log")
    try:
        logged = len(PROPOSAL_STEP.findall(log.read_text(encoding="utf-8")))
    except OSError:
        logged = 0
    return (logged, "card log") if logged else (len(machine), "attempts.json")


def _arm_of(manifest: Mapping[str, Any]) -> str:
    """An ablation folder is named after its card, so its arm comes from the manifest."""
    return "farm" if manifest.get("rm_mode") == "compiler" else "arm-fm"


def _read_list(path: Path) -> list[dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [as_object(item) for item in value] if isinstance(value, list) else []


def _row(group: str, arm: str, bundles: list[dict[str, Any]]) -> dict[str, Any]:
    reached = [item for item in bundles if item["reached_labeling"]]
    accepted = [item for item in bundles if item["rm_accepted"]]
    checked = [item for item in bundles if item["checked"]]
    regenerated = [item for item in bundles if item["regenerated"]]
    tried = [item["rm_tries"] for item in bundles if item["rm_tries"]]
    return {
        "group": group,
        "arm": arm,
        "bundles": len(bundles),
        "rm_accepted": len(accepted),
        "rm_total": len(bundles),
        "rm_tries_accepted": _mean([item["rm_tries"] for item in accepted]),
        "rm_tries_all": _mean(tried),
        "rm_tries_source": dict(Counter(item["rm_tries_source"] for item in bundles)),
        "labeling_accepted": sum(item["labeling_accepted"] for item in reached),
        "labeling_reached": len(reached),
        "labeling_tries": _mean(
            [item["labeling_tries"] for item in reached if item["labeling_tries_known"]]
        ),
        "labeling_regenerated_accepted": sum(item["regenerated_accepted"] for item in regenerated),
        "labeling_regenerated": len(regenerated),
        "regeneration_tries": _mean([item["regenerated_tries"] for item in regenerated]),
        "labeling_ok_after_repair": sum(item["label_ok"] for item in checked),
        "labeling_checked": len(checked),
        "repair_rounds": _mean(
            [item["repair_rounds"] for item in bundles if item["repair_rounds"]]
        ),
        "restored_from_log": sum(item["restored"] for item in bundles),
    }


def _mean(values: list[int]) -> float | None:
    return round(mean(values), 2) if values else None


def _markdown(rows: list[dict[str, Any]]) -> str:
    lines = ["| " + " | ".join(HEADER) + " |", "|" + "---|" * len(HEADER)]
    for row in rows:
        cells = (
            row["group"],
            row["arm"],
            row["bundles"],
            f"{row['rm_accepted']}/{row['rm_total']}",
            row["rm_tries_accepted"],
            row["rm_tries_all"],
            ", ".join(f"{name} {count}" for name, count in sorted(row["rm_tries_source"].items())),
            f"{row['labeling_accepted']}/{row['labeling_reached']}",
            row["labeling_tries"],
            f"{row['labeling_regenerated_accepted']}/{row['labeling_regenerated']}",
            row["regeneration_tries"],
            f"{row['labeling_ok_after_repair']}/{row['labeling_checked']}",
            row["repair_rounds"],
            row["restored_from_log"],
        )
        lines.append("| " + " | ".join("-" if cell is None else str(cell) for cell in cells) + " |")
    return "\n".join(lines)
