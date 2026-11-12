"""Benchmark trace tools: the trace bank, the replay through bundles, and bundle facts.

Usage:
    python app/main.py trace-bank --tasks cards.json --output outputs/bank [--only ID ...]
    python app/main.py replay-traces --traces outputs/bank --bundles bundles --output outputs/replay
    python app/main.py rm-facts --bundles bundles [--tasks cards.json] [--replay summary.json] \
        --output facts.json

``trace-bank`` runs every plan of every card in the real env and checks the judge's verdicts; a
card with contract problems is reported and not run. ``replay-traces`` plays the traces the bank
lists through each bundle's own labeling and Reward Machine, judging with the clauses the bank
holds. ``rm-facts`` reads the bundle files, plus the cards (``--tasks``) and a replay summary
(``--replay``) when given. Each prints a short summary and names the file it wrote.
"""

from pathlib import Path
from typing import Any

from src import benchmark
from src.benchmark import CardError
from src.benchmark.rm_facts import STAMP_FIELDS


def trace_bank(tasks: Path, output: Path, only: list[str] | None, seed: int) -> None:
    """Run the plans of the cards in ``tasks`` into ``output`` and print what each plan did."""
    try:
        summary = benchmark.run_trace_bank(benchmark.load_cards(tasks), output, only, seed)
    except CardError as error:
        raise SystemExit(f"error: {error}") from error

    totals = summary["totals"]
    print(
        f"suite {summary['suite']!r}: {totals['cards']} cards, {totals['runs_ok']}/{totals['runs']} plans ok,"
        f" {totals['cards_with_problems']} cards with problems, {totals['cards_not_run']} not run"
    )
    for card in summary["cards"]:
        print(f"\n{card['id']}: {card['task']}")
        for item in card["expect"]:
            print(f"  {item['clause']}  {item['ltlf']['readable']}")
        for run in card["runs"]:
            detail = "; ".join(run["problems"]) or " ".join(run["verdicts"])
            print(f"  {run['plan']}-s{run['seed']}: {'ok' if run['ok'] else 'FAIL'}  {detail}")
        if "not_run" in card:
            print("  not run: the card has contract problems")
        elif not card["runs"]:
            print("  no plans")
    _print_problems(summary["card_problems"])
    print(f"\nChainResponse cards to review: {summary['chain_response_review'] or 'none'}")
    print(f"summary: {output / 'summary.json'}")


def replay_traces(traces: Path, bundles: Path, output: Path) -> None:
    """Replay the traces in ``traces`` through the bundles in ``bundles`` into ``output``."""
    try:
        summary = benchmark.replay_traces(traces, bundles, output)
    except CardError as error:
        raise SystemExit(f"error: {error}") from error

    disagree = [key for key, world in summary["world_agreement"].items() if not world["agree"]]
    print(f"world agreement: {'all traces' if not disagree else 'FAILS on ' + ', '.join(disagree)}")
    for key, result in summary["bundles"].items():
        if "error" in result:
            print(f"{key}: {result['error']}")
            continue
        check = result["machine_check"]
        agreement = result["label_agreement"]
        print(
            f"{key}: machine_check {'passed' if check['passed'] else 'FAILED'}"
            f" ({check['checked'] - len(check['failed'])}/{check['checked']})"
            f"  unmatched bundle names {agreement['unmatched_bundle'] or 'none'}"
            f"  rm {result['rm_path']}"
        )
        for failed in check["failed"]:
            print(f"    failed: {failed}")
    for card_id, header in summary["cards"].items():
        print(f"{card_id}: {header['task']}  ->  {output / summary['plots'][card_id]}")
    print(f"summary: {output / 'replay-summary.json'}")


def rm_facts(bundles: Path, tasks: Path | None, replay: Path | None, output: Path) -> None:
    """Write the facts of the bundles in ``bundles`` to ``output`` and print the shape of each."""
    try:
        summary = benchmark.write_rm_facts(bundles, tasks, replay, output)
    except CardError as error:
        raise SystemExit(f"error: {error}") from error

    for key, facts in summary["bundles"].items():
        if "error" in facts:
            print(f"{key}: {facts['error']}")
            continue
        print(
            f"{key}: {facts['states']} states, {facts['transitions']} transitions, "
            f"{facts['reward_signs']}, wells {facts['wells'] or 'none'}, "
            f"accepting {facts['accepting'] or 'none'}"
            + (f", clauses {facts['clause_check']}" if "clause_check" in facts else "")
        )
    for row in summary["generation"]:
        print(f"generation {row['arm']}: {_generation_line(row)}")
    for group in summary["paraphrases"]:
        print(
            f"paraphrases {group['arm']}/{group['card_id']}: clauses {group['clauses']}, "
            f"machine_check {group['machine_check']}"
        )
    print(f"facts: {output}")


def _print_problems(problems: dict[str, list[str]]) -> None:
    for card_id, found in problems.items():
        print(f"\ncard problems {card_id}:")
        for problem in found:
            print(f"  - {problem}")


def _generation_line(row: dict[str, Any]) -> str:
    counts = ", ".join(f"{name} {row[name]['total']} (n={row[name]['n']})" for name in STAMP_FIELDS)
    return f"{row['bundles']} bundles, {row['stamped']} stamped ({row['provisional']} provisional); {counts}"
