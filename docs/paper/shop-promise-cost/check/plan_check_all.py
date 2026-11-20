"""Plan check of every committed bundle, without writing records beside the bundles. No model call.

Same call as check-plans (``check_card_plans``, run seed 42, the CLI default; ablations skipped), but
the record goes to OUT.jsonl, so the committed ``*.plan_check.json`` files stay as they are.

With `off`, each no-goal bundle is first rebuilt in memory with the end judgment off (what
`ablate-rm --off end_judgment` writes: the stored clauses, the recorded switches, MONA, no model
call), so the check sees the machine the default (end judgment off) would make.

Usage (the app under test on PYTHONPATH; run from its checkout, card env paths are relative):
  python plan_check_all.py BENCH OUT.jsonl [off]
"""

import json
import sys
from dataclasses import replace
from multiprocessing import Pool
from pathlib import Path

from scripts.ablate_rm import _build, _recorded_switches, _stored_task
from src.benchmark import load_cards
from src.benchmark.plan_check import check_card_plans
from src.benchmark.traces import find_bundles, load_machine_bundle
from src.compiler import compile_dfas, serialize_paper_reward_machine
from src.config import Configuration

SEED = 42
OFF = sys.argv[3:] == ["off"]


def judgment_off(ref, bundle):
    """The bundle with its machine rebuilt with the end judgment off; also whether the control held."""
    CONFIG = Configuration(bundle=ref.path)
    environment, proposal = _stored_task(CONFIG, bundle)
    dfas = compile_dfas(proposal, CONFIG)
    recorded = _recorded_switches(bundle)
    _, control = _build(environment, proposal, dfas, recorded)
    same = serialize_paper_reward_machine(control) == (ref.path / "reward_machine.txt").read_text(
        encoding="utf-8"
    )
    _, machine = _build(environment, proposal, dfas, replace(recorded, reward_end_judgment=False))
    return replace(bundle, reward_machine=machine), same


def job(item):
    suite, tasks, ref = item
    card = {card.id: card for card in load_cards(tasks).cards}.get(ref.card_id)
    bundle = load_machine_bundle(ref)
    row = {"suite": suite, "key": ref.key, "card": ref.card_id}
    if card is None or isinstance(bundle, str):
        return {**row, "passed": None, "problems": [bundle if card else "no card"]}
    if OFF and not bundle.reward_machine.final_states:
        try:
            bundle, row["control_same"] = judgment_off(ref, bundle)
        except Exception as error:
            return {
                **row,
                "goal": False,
                "passed": None,
                "problems": [f"rebuild failed: {error!r}"[:300]],
            }
    record = check_card_plans(bundle, card, SEED)
    runs = [
        {k: run.get(k) for k in ("plan", "kind", "seed", "end", "steps", "owed", "pay", "error")}
        for run in record["runs"]
    ]
    return {
        **row,
        "goal": bool(bundle.reward_machine.final_states),
        "judgment": bundle.reward_machine.judgment is not None,
        "passed": record["passed"],
        "problems": record["problems"],
        "runs": runs,
    }


def main() -> None:
    bench, out = Path(sys.argv[1]), Path(sys.argv[2])
    items = [
        (suite.name, suite / "tasks.json", ref)
        for suite in sorted(bench.iterdir())
        if (suite / "tasks.json").is_file() and (suite / "bundles").is_dir()
        for ref in find_bundles(suite / "bundles")
        if not ref.ablation
    ]
    with Pool(10) as pool:
        rows = pool.map(job, items, chunksize=1)
    with out.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    counts = {}
    for row in rows:
        key = (
            "goal" if row.get("goal") else "no-goal",
            {True: "pass", False: "FAIL", None: "unchecked"}[row["passed"]],
        )
        counts[key] = counts.get(key, 0) + 1
    print(len(rows), "bundles", dict(sorted(counts.items())))


if __name__ == "__main__":
    main()
