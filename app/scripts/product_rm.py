"""Build the product of two bundles' machines, to test a policy trained on them (evaluation only).

The product has one state per reachable pair of states. Each pair's description is the two
descriptions the policy saw in training, joined, and is embedded with the settings both bundles
share (same server and model). The labeling covers both machines' propositions. The machines must
be on one environment and one embedding; the rewards of a pair add up. Both arms work. A FARM
machine's end judgment is combined (the open promises of both parts add up), so the two machines
must both have one, with the same failed rewards; a pair is rejecting when either part is.

Usage:
    python app/main.py product-rm \
        --first experiments/benchmark/complex/bundles/arm-fm/cx-siren \
        --second experiments/benchmark/complex/bundles/arm-fm/cx-box \
        --output outputs/product/cx-siren-box \
        --first-card <card.json> --second-card <card.json>

With both ``--first-card`` and ``--second-card`` it also writes ``<output>/card.json``, a card that
holds both cards' rules and merged setup, to judge the product with
``test-rl --bundle <output> --judge <output>/card.json``. ``<output>/product.json`` names the pair
of every product state. The embedding server of the bundles must be up.
"""

import json
from pathlib import Path

from src.arm_fm.transfer import build_product_bundle, product_card, read_card
from src.benchmark import load_card
from src.config import Configuration


def product_rm(
    CONFIG: Configuration,
    first: Path,
    second: Path,
    output: Path,
    cards: tuple[Path | None, Path | None] = (None, None),
) -> None:
    """Write the product bundle of ``first`` and ``second`` (and, with both ``cards``, its card).

    Raises:
        ValueError: If only one card is given, the bundles do not fit (environment, embedding,
            propositions, machine kind, labeling) or the cards cannot be combined.
        FileExistsError: If ``output`` is not empty and ``CONFIG.overwrite`` is off.
    """
    first_card, second_card = cards
    if (first_card is None) != (second_card is None):
        raise ValueError("--first-card and --second-card come together")
    record = build_product_bundle(first, second, output, CONFIG)
    print(f"product of {first.name} and {second.name}: {len(record['states'])} states -> {output}")
    for name, state in record["states"].items():
        print(f"  {name} = ({state['first']}, {state['second']})")
    if first_card is not None and second_card is not None:
        card = product_card(read_card(first_card), read_card(second_card))
        path = output / "card.json"
        path.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
        load_card(path)  # the merged card must pass the card contract
        print(f"card {card['id']} -> {path}")
