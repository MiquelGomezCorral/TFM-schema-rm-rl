"""Facts about generated bundles: the machine's shape, how well it matches the card, how it was made.

Read from the bundle files, plus the card file (``--tasks``) and a replay summary (``--replay``)
when given. The FARM clause check compares the clauses the compiler stored
(``manifest.generation["clauses"]``) with the card's ``expect`` and ``also_ok``, and, when the
lists differ, asks MONA whether they still state the same task; the generation
table sums the stamps (``manifest.provenance["stamp"]``); paraphrase agreement compares the
bundles of one card across ``~p<k>`` (clauses, and the machine-check verdicts of the replay).
"""

import json
from collections import Counter, defaultdict
from collections.abc import Collection, Mapping
from itertools import combinations
from pathlib import Path
from statistics import fmean
from typing import Any

from flat_tool import compile_dfa

from src.arm_fm.artifacts import ArtifactBundle
from src.config import Configuration
from src.utils import ltlf_of

from .cards import Card, card_header, load_cards
from .declare_judge import HARD, SOFT, Clause, ClauseError, as_clause
from .traces import BundleRef, as_object, find_bundles, load_machine_bundle, read_json, write_json

STAMP_FIELDS = ("attempts", "critic_interventions", "retries", "wall_time_s")
FARM = "farm"


def write_rm_facts(
    bundles: Path, tasks: Path | None, replay: Path | None, output: Path
) -> dict[str, Any]:
    """Collect the facts of every bundle under ``bundles`` into the JSON file ``output``.

    ``tasks`` adds each card and the FARM clause check; ``replay`` (a ``replay-summary.json``)
    adds the machine-check comparison across paraphrases.
    """
    card_file = load_cards(tasks) if tasks else None
    cards = {card.id: card for card in card_file.cards} if card_file else {}
    replay_summary = json.loads(replay.read_text(encoding="utf-8")) if replay else None
    facts = {ref.key: _bundle_facts(ref, cards.get(ref.card_id)) for ref in find_bundles(bundles)}
    suite = card_file.suite if card_file else ""
    summary = {
        "suite": suite,
        "bundles": facts,
        "generation": generation_table(suite, facts),
        "paraphrases": paraphrase_groups(facts, replay_summary),
    }
    write_json(output, summary, indent=2)
    return summary


def _manifest_stamp(ref: BundleRef) -> dict[str, Any] | None:
    """The manifest's provenance stamp, read apart from the machine so a failed bundle keeps it.

    A provenance or stamp that is not an object counts as missing (``None``).
    """
    provenance = as_object(read_json(ref.path / "manifest.json").get("provenance"))
    return as_object(provenance.get("stamp")) or None


def _bundle_facts(ref: BundleRef, card: Card | None) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "arm": ref.arm,
        "card_id": ref.card_id,
        "ablation": ref.ablation,
        "stamp": _manifest_stamp(ref),
    }
    bundle = load_machine_bundle(ref)
    if isinstance(bundle, str):
        return {**facts, "error": bundle}
    stored = _normalized(bundle.manifest.generation.get("clauses"))
    facts |= {
        "rm_path": str(ref.rm_path),
        **machine_facts(bundle),
        "stored_clauses": stored,
    }
    if card is not None:
        facts["card"] = card_header(card)
        if ref.arm == FARM:
            facts["clause_check"] = clause_status(stored, card)
    return facts


def machine_facts(bundle: ArtifactBundle) -> dict[str, Any]:
    """States, transitions, reward values, wells, accepting states and node labels of the RM.

    ``reward_values`` are the transition rewards, ``end_charges`` what the end judgment charges
    an episode that ends open; ``reward_signs`` classifies both.
    """
    machine = bundle.reward_machine
    judgment = machine.judgment
    rewards = sorted({float(transition.reward) for transition in machine.transitions})
    # What an episode that ends in a state with open promises is charged, beside the transitions.
    end_charges = (
        sorted({float(judgment.end_charge(state)) for state, _, _ in judgment.pending})
        if judgment
        else []
    )
    return {
        "states": len(machine.states),
        "state_names": list(machine.states),
        "initial": machine.initial_state,
        "finals": list(machine.final_states),
        "wells": list(machine.rejecting_states),
        "accepting": list(judgment.accepting) if judgment else [],
        "pending": [list(item) for item in judgment.pending] if judgment else [],
        "transitions": len(machine.transitions),
        "else_transitions": sum(transition.is_else for transition in machine.transitions),
        "reward_values": rewards,
        "end_charges": end_charges,
        "reward_signs": (
            "also negative" if any(r < 0 for r in [*rewards, *end_charges]) else "positive only"
        ),
        "propositions": list(bundle.labeling_propositions),
        "node_labels": dict(bundle.state_descriptions),
    }


def _normalized(raw: object) -> list[list[Any]] | None:
    """The stored clauses as a sorted list of ``[template, [props], priority]``; None if absent."""
    if not isinstance(raw, list) or not raw:
        return None
    try:
        return sorted([c[0], list(c[1]), c[2]] for c in map(as_clause, raw))
    except ClauseError:
        return [["unreadable", [], json.dumps(raw)]]


def clause_status(stored: list[list[Any]] | None, card: Card) -> str:
    """``exact``, ``also_ok``, ``equivalent``, ``mismatch`` or ``missing`` for stored clauses.

    ``stored`` comes from ``_normalized``. ``exact`` holds every clause of ``expect`` except the
    card's ``forced`` ones, which are optional extras: neither keeping nor dropping them counts
    against the output. ``also_ok`` is one listed alternative. ``equivalent`` is another clause list
    that states the same task as one of those answers (``_same_task``), such as an ``Existence`` the
    other clauses already force: it counts as right like ``exact`` and ``also_ok``, and the status
    shows which machines needed the check. The current rule keeps a stated order even when the world
    forces it and never adds an unstated one from environment facts.
    """
    if stored is None:
        return "missing"
    # A Counter keeps a repeated clause: the reward compiler prices each copy.
    clauses = Counter((template, tuple(names), priority) for template, names, priority in stored)
    expected = Counter(card.expect)
    required = Counter(c for i, c in enumerate(card.expect) if i not in card.forced)
    if required <= clauses <= expected:
        return "exact"
    if any(clauses == Counter(option) for option in card.also_ok):
        return "also_ok"
    CONFIG = Configuration()
    if any(_same_task(clauses, Counter(answer), CONFIG) for answer in _accepted_answers(card)):
        return "equivalent"
    return "mismatch"


def _accepted_answers(card: Card) -> list[list[Clause]]:
    """Every nonempty clause list ``exact`` or ``also_ok`` accepts.

    That is ``expect`` with any subset of its ``forced`` clauses left out, and each ``also_ok``.
    An empty answer is left out, so an unreadable stored list never matches an all-forced card.
    """
    required = [clause for i, clause in enumerate(card.expect) if i not in card.forced]
    optional = [card.expect[i] for i in card.forced]
    kept = [extra for size in range(len(optional) + 1) for extra in combinations(optional, size)]
    answers = [*([*required, *extra] for extra in kept), *(list(option) for option in card.also_ok)]
    return [answer for answer in answers if answer]


def _same_task(first: Counter[Clause], second: Counter[Clause], CONFIG: Configuration) -> bool:
    """True when the two clause lists state the same task, by MONA.

    Both lists must name the same propositions. Hard clauses are compared with hard and soft with
    soft, so a soft rule written as hard stays different. The hard clauses are compared as one
    conjunction of their pipeline LTLf (``ltlf_of``). The soft ones are paired one to one, repeats
    counted, because the compiler prices each soft clause on its own: an extra implied soft rule or
    a repeated one changes the soft-break pay.
    """
    if _propositions(first) != _propositions(second):
        return False
    if not _equivalent(_conjunction(first, HARD), _conjunction(second, HARD), CONFIG):
        return False
    return _paired(_soft_formulas(first), _soft_formulas(second), CONFIG)


def _equivalent(a: str, b: str, CONFIG: Configuration) -> bool:
    """True when no finite trace satisfies one LTLf formula and not the other.

    That is, MONA's DFA of their exclusive or accepts nothing.
    """
    if a == b:
        return True
    difference = compile_dfa(
        f"(({a}) & ~({b})) | (~({a}) & ({b}))", mona_executable=CONFIG.mona_executable
    )
    return not difference["accepting_states"]


def _paired(first: list[str], second: list[str], CONFIG: Configuration) -> bool:
    """True when each formula of ``first`` has its own ``_equivalent`` formula in ``second``.

    Equivalence is transitive, so taking the first unused match never blocks a full pairing.
    """
    if len(first) != len(second):
        return False
    unused = list(second)
    for formula in first:
        match = next((other for other in unused if _equivalent(formula, other, CONFIG)), None)
        if match is None:
            return False
        unused.remove(match)
    return True


def _propositions(clauses: Collection[Clause]) -> set[str]:
    return {name for _, names, _ in clauses for name in names}


def _conjunction(clauses: Collection[Clause], priority: str) -> str:
    """The LTLf of one priority's clauses, sorted and joined by ``&``; ``true`` when there are none."""
    parts = {ltlf_of(template, names) for template, names, level in clauses if level == priority}
    return " & ".join(sorted(parts)) or "true"


def _soft_formulas(clauses: Counter[Clause]) -> list[str]:
    """The pipeline LTLf of each soft clause, one per copy."""
    return [
        ltlf_of(template, names) for template, names, level in clauses.elements() if level == SOFT
    ]


def generation_table(suite: str, facts: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Per arm: bundles, stamped bundles and the stamped counts (R22); null counts are skipped.

    An ablation variant is left out: it copies its source machine's stamp, which the source
    bundle already counts once.
    """
    stamps_by_arm: dict[str, list[Mapping[str, Any] | None]] = defaultdict(list)
    for entry in facts.values():
        if not entry["ablation"]:
            stamps_by_arm[entry["arm"]].append(entry.get("stamp"))
    rows = []
    for arm, stamps in sorted(stamps_by_arm.items()):
        stamped = [stamp for stamp in stamps if stamp]
        row: dict[str, Any] = {
            "suite": suite,
            "arm": arm,
            "bundles": len(stamps),
            "stamped": len(stamped),
            "provisional": sum(bool(stamp.get("provisional")) for stamp in stamped),
        }
        for name in STAMP_FIELDS:
            values = [stamp[name] for stamp in stamped if stamp.get(name) is not None]
            row[name] = {
                "n": len(values),
                "total": sum(values),
                "mean": fmean(values) if values else None,
            }
        rows.append(row)
    return rows


def paraphrase_groups(
    facts: Mapping[str, Mapping[str, Any]], replay: Mapping[str, Any] | None
) -> list[dict[str, Any]]:
    """Per card and arm with several bundles (``<id>`` and ``<id>~p<k>``): do the paraphrases agree?

    FARM: the stored clause sets are ``identical`` (or ``different``, ``missing``). Both arms:
    the machine-check verdicts are ``equal`` (or ``different``, ``no-replay``). Ablation variants
    of one card are different machines, not paraphrases, so they never form a group.
    """
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for key, entry in facts.items():
        if not entry["ablation"]:
            groups[entry["arm"], entry["card_id"]].append(key)
    return [
        {
            "arm": arm,
            "card_id": card_id,
            "bundles": keys,
            "clauses": _clause_agreement(arm, [facts[key].get("stored_clauses") for key in keys]),
            "machine_check": _verdict_agreement(keys, replay),
        }
        for (arm, card_id), keys in sorted(groups.items())
        if len(keys) > 1
    ]


def _clause_agreement(arm: str, stored: list[list[list[Any]] | None]) -> str:
    if arm != FARM:
        return "n/a"
    if any(clauses is None for clauses in stored):
        return "missing"
    return "identical" if len({json.dumps(clauses) for clauses in stored}) == 1 else "different"


def _verdict_agreement(keys: list[str], replay: Mapping[str, Any] | None) -> str:
    checks = [
        ((replay or {}).get("bundles", {}).get(key) or {}).get("machine_check") for key in keys
    ]
    if not all(checks):
        return "no-replay"
    verdicts = [{row["trace"]: row["ok"] for row in check["rows"]} for check in checks]
    return "equal" if all(item == verdicts[0] for item in verdicts) else "different"
