"""Build the shop-serve machine with the commanded fetch step paid. No model call.

The card's expect plus hard Response(order_taken, holding_food) ("fetch food from the pantry", as the
round 7 card that learned). Promise cost on, default pricing over the level's step limit, gamma 0.995
(plan_pay.build).

Usage (tp-shop-well on PYTHONPATH, run from its checkout): python fetch_variant.py OUT_FOLDER

Copied from the plan folder's shop-well/; this note and the lint fixes the repository's hooks asked
for aside, unchanged. Its output is evidence/bundles/shop-serve-fetch-promise.
"""

import json
import sys
from dataclasses import replace
from pathlib import Path

from plan_pay import build

from src.benchmark.cards import Card

FETCH = ("Response", ("order_taken", "holding_food"), "hard")


def main() -> None:
    shop = json.loads(Path("experiments/benchmark/shop/tasks.json").read_text(encoding="utf-8"))
    card = next(Card.from_dict(item) for item in shop["cards"] if item["id"] == "shop-serve")
    expect = tuple(card.expect)
    fetch_card = replace(card, expect=(expect[0], FETCH, *expect[1:]))
    path = build(fetch_card, True, Path(sys.argv[1]))
    print(path, list(fetch_card.expect))


if __name__ == "__main__":
    main()
