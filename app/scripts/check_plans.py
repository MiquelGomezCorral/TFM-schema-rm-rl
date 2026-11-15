"""Plan check of every bundle of one suite.

Usage:
    python app/main.py check-plans --tasks cards.json --bundles bundles [--only ID ...]

Plays each bundle's card plans through its machine (``src.benchmark.plan_check``), writes
``<name>.plan_check.json`` beside each bundle folder and prints one line per bundle. No model call.
"""

from pathlib import Path

from src.benchmark import CardError, load_cards
from src.benchmark.plan_check import check_and_record
from src.benchmark.traces import find_bundles, load_machine_bundle


def check_plans(tasks: Path, bundles: Path, only: list[str] | None, seed: int) -> None:
    """Check every bundle under ``bundles`` against its card in ``tasks``; ablations are skipped.

    ``only`` limits the run to card ids or bundle names; ``seed`` is the run seed of the trace
    bank, for a card with neither event seeds nor a layout seed.
    """
    try:
        cards = {card.id: card for card in load_cards(tasks).cards}
    except CardError as error:
        raise SystemExit(f"error: {error}") from error

    counts = {"pass": 0, "FAIL": 0, "unchecked": 0}
    for ref in find_bundles(bundles):
        if ref.ablation or (only and not {ref.card_id, ref.name} & set(only)):
            continue
        card = cards.get(ref.card_id)
        bundle = load_machine_bundle(ref)
        if card is None or isinstance(bundle, str):
            counts["unchecked"] += 1
            print(f"{ref.key}: unchecked ({bundle if card else 'no card'})")
            continue
        record = check_and_record(bundle, card, seed, ref.path)
        outcome = {True: "pass", False: "FAIL", None: "unchecked"}[record["passed"]]
        counts[outcome] += 1
        print(f"{ref.key}: {outcome} {' '.join(record['problems'][:1])}")
    print(f"{counts['pass']} pass, {counts['FAIL']} FAIL, {counts['unchecked']} unchecked")
