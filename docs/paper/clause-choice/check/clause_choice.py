"""Which listed answer FARM's final clauses pick on cards that allow several.

A card's answers are ``expect`` and each ``also_ok`` option. For every generation of such a card
this finds the answer its final clauses match by the repo scorer's rule (``clause_status``: exact
clauses first, then the MONA same-task check), or ``none`` when the scorer rejects them. Two
sources, never mixed:

- ``farm``: the final-run FARM bundles ``experiments/benchmark/<suite>/bundles/farm/<card>[~pN]/``.
- ``levels``: the thinking-level benchmark at the freeze, ``docs/paper/level-benchmark-freeze/``
  (records per level, 3 runs per case). Its cards are today's cards, else the run's snapshot.

Read-only, no model call. Writes ``../evidence/choices.json`` (one row per generation),
``../evidence/tables.md`` and one RM text per (card, chosen answer) under ``../evidence/rm/``
(copied from the plan folder's ``tools/clause_choice.py``; only the output folder changed).

Usage (repository root, RM_RL_env, MONA on PATH):
    PYTHONPATH=app python docs/paper/clause-choice/check/clause_choice.py
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

from scipy.stats import binomtest

from src.benchmark.cards import Card
from src.benchmark.rm_facts import _accepted_answers, _normalized, _same_task, clause_status
from src.benchmark.traces import find_bundles, read_json
from src.config import Configuration
from src.utils import ltlf_of, pretty_ltlf

OUT = (
    Path(__file__).resolve().parents[1] / "evidence"
)  # this entry (the plan folder in the original)
BENCH = Configuration.WORKSPACE_PATH / "experiments/benchmark"
LEVEL_DIR = Configuration.WORKSPACE_PATH / "docs/paper/level-benchmark-freeze"
SNAPSHOT = LEVEL_DIR / "evidence/cards"  # the cards at the level run (main e6c3acb)
LEVELS = ("none", "low", "medium", "high", "max")
LETTERS = {"expect": "E", "also_ok[0]": "A", "also_ok[1]": "B", "none": "X"}
# Hand reading: on ordered tasks, the answer the generator prompt's order rules write
# (reward-ltlf-creator.system.md:31-36, 41, 62-63): the last step's Existence plus one Precedence
# per pair, no Existence a hard Precedence already forces, a hard Precedence before a preferred step.
PROMPT_FORM = {
    "base-key-corridor": "also_ok[0]",
    "base-unlock-pickup": "also_ok[0]",
    "cx-goal-one-rule": "expect",
    "tpl-existence-1-goal": "expect",
    "tpl-existence-two-3-goal": "also_ok[0]",
    "soft-key-goal": "also_ok[0]",
    "soft-key-door-goal": "also_ok[0]",
    "soft-door-box": "also_ok[0]",
    "soft-key-door-box": "also_ok[0]",
}


# ======================================================================================
#                                       MATCHING
# ======================================================================================
def chosen_option(stored: list | None, card: Card, CONFIG: Configuration) -> tuple[str, str]:
    """(answer, how): ``expect``, ``also_ok[i]`` or ``none``, and ``exact``, ``equivalent`` or the verdict.

    ``clause_status`` decides right or wrong; this only names which answer it accepted, in its order.
    """
    status = clause_status(stored, card)
    if status == "exact":
        return "expect", "exact"
    if status in ("mismatch", "missing"):
        return "none", status

    clauses = Counter((template, tuple(names), priority) for template, names, priority in stored)
    if status == "also_ok":
        index = next(i for i, option in enumerate(card.also_ok) if clauses == Counter(option))
        return f"also_ok[{index}]", "exact"

    # _accepted_answers lists expect's variants first, then each also_ok option in card order.
    answers = _accepted_answers(card)
    first_option = len(answers) - len(card.also_ok)
    index = next(
        i for i, answer in enumerate(answers) if _same_task(clauses, Counter(answer), CONFIG)
    )
    name = "expect" if index < first_option else f"also_ok[{index - first_option}]"
    return name, "equivalent"


def card_index(tasks: Path) -> dict[str, Card]:
    data = json.loads(tasks.read_text(encoding="utf-8"))
    return {item["id"]: Card.from_dict(item) for item in data["cards"]}


def snapshot_options() -> dict[str, list[tuple]]:
    """Card id -> its ``also_ok`` options at the level run, before the final-run rulings."""
    options: dict[str, list[tuple]] = {}
    for tasks in sorted(SNAPSHOT.glob("*/tasks.json")):
        for card_id, card in card_index(tasks).items():
            options.setdefault(card_id, [Counter(option) for option in card.also_ok])
    return options


# ======================================================================================
#                                       GENERATIONS
# ======================================================================================
def farm_rows(CONFIG: Configuration) -> tuple[list[dict], dict[str, Card]]:
    rows, cards = [], {}
    for tasks in sorted(BENCH.glob("*/tasks.json")):
        suite_cards = {cid: card for cid, card in card_index(tasks).items() if card.also_ok}
        bundles = tasks.parent / "bundles"
        if not suite_cards or not (bundles / "farm").is_dir():
            continue
        for ref in find_bundles(bundles):
            card = suite_cards.get(ref.card_id)
            if ref.arm != "farm" or ref.ablation or card is None:
                continue
            manifest = read_json(ref.path / "manifest.json")
            stamp = (manifest.get("provenance") or {}).get("stamp") or {}
            stored = _normalized((manifest.get("generation") or {}).get("clauses"))
            answer, how = chosen_option(stored, card, CONFIG)
            key = f"{tasks.parent.name}/{card.id}"
            cards[key] = card
            rows.append(
                {
                    "source": "farm",
                    "card": key,
                    "paraphrase": ref.name.partition("~")[2] or "main",
                    "level": stamp.get("reasoning"),
                    "run": ref.name,
                    "commit": (stamp.get("commit") or "")[:7],
                    "task": manifest.get("task"),
                    "answer": answer,
                    "how": how,
                    "clauses": stored,
                    "rm_path": str(ref.rm_path),
                }
            )
    return rows, cards


def level_card(suite: str, card_id: str) -> Card | None:
    """Today's card, else the level run's snapshot (the local-soft cards exist only there)."""
    for tasks in (BENCH / suite / "tasks.json", SNAPSHOT / suite / "tasks.json"):
        if tasks.exists() and card_id in (cards := card_index(tasks)):
            return cards[card_id]
    return None


def level_rows(CONFIG: Configuration) -> tuple[list[dict], dict[str, Card]]:
    rows, cards = [], {}
    for level in LEVELS:
        for path in sorted((LEVEL_DIR / "records" / level).glob("*-r*.json")):
            record = read_json(path)
            card = level_card(record["suite"], record["name"].partition("~")[0])
            if card is None or not card.also_ok:
                continue
            case, _, run = path.stem.rpartition("-")
            accepted = record.get("status") == "accepted" and record.get("clauses")
            stored = _normalized(record["clauses"]) if accepted else None
            answer, how = chosen_option(stored, card, CONFIG) if accepted else ("none", "failed")
            key = f"{record['suite']}/{card.id}"
            cards[key] = card
            rows.append(
                {
                    "source": "levels",
                    "card": key,
                    "paraphrase": record["name"].partition("~")[2] or "main",
                    "case": case,
                    "level": level,
                    "run": run,
                    "task": record.get("task"),
                    "answer": answer,
                    "how": how,
                    "clauses": stored,
                    "machine": record.get("machine"),
                }
            )
    return rows, cards


# ======================================================================================
#                                       TABLES
# ======================================================================================
def wilson(count: int, total: int) -> str:
    if not total:
        return "-"
    interval = binomtest(count, total).proportion_ci(method="wilson")
    return f"{count}/{total} = {count / total:.0%} [{interval.low:.0%}, {interval.high:.0%}]"


def clause_text(clauses) -> str:
    return "; ".join(
        f"`{pretty_ltlf(ltlf_of(template, names))}`{' (soft)' if priority == 'soft' else ''}"
        for template, names, priority in clauses
    )


def options_of(card: Card) -> list[tuple[str, tuple]]:
    return [("expect", card.expect), *((f"also_ok[{i}]", o) for i, o in enumerate(card.also_ok))]


def write_rms(rows: list[dict]) -> dict[tuple[str, str], str]:
    """One RM text per (card, chosen answer), from its first FARM bundle, else its first level run."""
    written: dict[tuple[str, str], str] = {}
    (OUT / "rm").mkdir(parents=True, exist_ok=True)
    for row in sorted(rows, key=lambda r: r["source"]):  # "farm" sorts before "levels"
        key = (row["card"], row["answer"])
        if row["answer"] == "none" or key in written:
            continue
        text = (
            Path(row["rm_path"]).read_text(encoding="utf-8") if "rm_path" in row else row["machine"]
        )
        name = f"{row['card'].replace('/', '__')}__{row['answer'].replace('[', '-').strip(']')}.txt"
        (OUT / "rm" / name).write_text(text, encoding="utf-8")
        written[key] = f"clause-choice/rm/{name}"
    return written


def summary_line(rows: list[dict], cards: dict[str, Card], group: str) -> str:
    """Expect share among right answers against a uniform pick among the listed answers."""
    right = [row for row in rows if row["answer"] != "none"]
    if not right:
        return f"| {group} | {len({r['card'] for r in rows})} | {len(rows)} | 0 | - | - | - |"
    expect = sum(row["answer"] == "expect" for row in right)
    uniform = sum(1 / (1 + len(cards[row["card"]].also_ok)) for row in right) / len(right)
    test = binomtest(expect, len(right), uniform)
    return (
        f"| {group} | {len({r['card'] for r in rows})} | {len(rows)} | {len(right)} | "
        f"{wilson(expect, len(right))} | {uniform:.0%} | {test.pvalue:.2g} |"
    )


def prompt_form_line(rows: list[dict], label: str) -> str:
    """How often a right answer on a ``PROMPT_FORM`` card is the prompt's form, and its expect share."""
    right = [r for r in rows if r["answer"] != "none" and r["card"].split("/")[1] in PROMPT_FORM]
    form = sum(r["answer"] == PROMPT_FORM[r["card"].split("/")[1]] for r in right)
    expect = sum(r["answer"] == "expect" for r in right)
    return f"| {label} | {wilson(form, len(right))} | {wilson(expect, len(right))} |"


def agreement_line(groups: dict[tuple, list[dict]], cards: dict[str, Card], label: str) -> str:
    """Groups whose right answers all agree, against the chance of that under a uniform pick."""
    cells = [
        (rows, 1 + len(cards[rows[0]["card"]].also_ok))
        for rows in groups.values()
        if sum(row["answer"] != "none" for row in rows) >= 2
    ]
    agree = 0
    chance = 0.0
    for rows, answers in cells:
        picked = [row["answer"] for row in rows if row["answer"] != "none"]
        agree += len(set(picked)) == 1
        chance += answers ** (1 - len(picked))
    if not cells:
        return f"- {label}: no group with 2 or more right answers."
    test = binomtest(agree, len(cells), chance / len(cells), alternative="greater")
    return (
        f"- {label}: {wilson(agree, len(cells))} groups agree; a uniform pick would make "
        f"{chance / len(cells):.0%} agree (one-sided binomial p = {test.pvalue:.2g})."
    )


def card_section(key: str, card: Card, rows: list[dict], rms: dict, snapshot: dict) -> list[str]:
    lines = [f"### `{key}`", "", f'Task: "{card.task}"', "", "Answers:"]
    before = snapshot.get(card.id, [])
    for name, clauses in options_of(card):
        added = name != "expect" and Counter(clauses) not in before
        rm = rms.get((key, name), "never chosen, no RM")
        tag = " (added after the final run)" if added else ""
        lines.append(f"- {LETTERS[name]} = {name}{tag}: {clause_text(clauses)}. RM: `{rm}`")
    lines.append("")

    farm = [row for row in rows if row["source"] == "farm"]
    if farm:
        lines += ["| FARM bundle | wording | answer | how |", "|---|---|---|---|"]
        lines += [
            f"| {r['run']} | {r['task']} | {LETTERS[r['answer']]} | {r['how']} |" for r in farm
        ]
        lines.append("")

    levels = [row for row in rows if row["source"] == "levels"]
    if levels:
        by_case: dict[tuple, dict[str, str]] = defaultdict(dict)
        for row in levels:
            letter = LETTERS[row["answer"]]
            cell = by_case[(row["case"], row["paraphrase"], row["task"])]
            cell[row["level"]] = cell.get(row["level"], "") + (
                letter.lower() if row["how"] == "equivalent" else letter
            )
        lines += [
            "| level case | wording | " + " | ".join(LEVELS) + " |",
            "|---|---|" + "---|" * len(LEVELS),
        ]
        for (case, paraphrase, task), cells in sorted(by_case.items()):
            letters = " | ".join(cells.get(level, "") for level in LEVELS)
            lines.append(f"| {case} ({paraphrase}) | {task} | {letters} |")
        lines.append("")
    return lines


def write_tables(rows: list[dict], cards: dict[str, Card], rms: dict) -> None:
    snapshot = snapshot_options()
    farm = [row for row in rows if row["source"] == "farm"]
    levels = [row for row in rows if row["source"] == "levels"]

    def listed_before(card_key: str) -> bool:
        card = cards[card_key]
        return all(Counter(option) in snapshot.get(card.id, []) for option in card.also_ok)

    lines = [
        "# Clause choice tables (generated by `tools/clause_choice.py`)",
        "",
        "Letters: E = expect, A = also_ok[0], B = also_ok[1], X = scorer rejects it or the run",
        "failed; lower case = accepted only by the MONA same-task check. Level cells hold one letter",
        "per run (3 runs). `uniform` = expected expect share if each right answer were a uniform pick",
        "among the card's listed answers; p = two-sided binomial test of the expect count against it.",
        "",
        "## Expect share among right answers",
        "",
        "| set | cards | generations | right | expect [95% Wilson CI] | uniform | p |",
        "|---|---|---|---|---|---|---|",
    ]
    farm_before = [row for row in farm if listed_before(row["card"])]
    farm_added = [row for row in farm if not listed_before(row["card"])]
    lines.append(summary_line(farm, cards, "FARM final run, all"))
    lines.append(summary_line(farm_before, cards, "FARM final run, answers listed before it"))
    lines.append(summary_line(farm_added, cards, "FARM final run, an answer added from it"))
    for level in LEVELS:
        at_level = [row for row in levels if row["level"] == level]
        lines.append(summary_line(at_level, cards, f"levels: {level}"))
    lines.append(summary_line(levels, cards, "levels: all"))
    lines += [
        "",
        "## Ordered tasks: the prompt's form",
        "",
        "Cards in `PROMPT_FORM` (hand reading of the generator prompt's order rules).",
        "",
        "| set | prompt's form [95% CI] | expect [95% CI] |",
        "|---|---|---|",
        prompt_form_line(farm, "FARM final run"),
        prompt_form_line([row for row in levels if row["level"] == "none"], "levels: none"),
        prompt_form_line([row for row in levels if row["level"] != "none"], "levels: low to max"),
        "",
        "## Do repeated runs agree?",
        "",
    ]

    by_card: dict[tuple, list[dict]] = defaultdict(list)
    by_cell: dict[tuple, list[dict]] = defaultdict(list)
    by_wording: dict[tuple, list[dict]] = defaultdict(list)
    for row in farm:
        by_card[(row["card"],)].append(row)
    for row in levels:
        by_cell[(row["case"], row["level"])].append(row)
        if row["level"] != "none":
            by_wording[(row["case"],)].append(row)
    listed = {key: rows for key, rows in by_card.items() if listed_before(key[0])}
    lines.append(agreement_line(listed, cards, "FARM, one card's wordings (answers listed before)"))
    lines.append(agreement_line(by_card, cards, "FARM, one card's wordings (all cards)"))
    lines.append(agreement_line(by_cell, cards, "levels, one case at one level (3 runs)"))
    lines.append(agreement_line(by_wording, cards, "levels, one case over low to max (12 runs)"))
    lines += ["", "## Per card", ""]

    rows_by_card: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        rows_by_card[row["card"]].append(row)
    for key in sorted(rows_by_card):
        lines += card_section(key, cards[key], rows_by_card[key], rms, snapshot)
    (OUT / "tables.md").write_text("\n".join(lines), encoding="utf-8")


# ======================================================================================
#                                       MAIN
# ======================================================================================
def main() -> None:
    CONFIG = Configuration()
    farm, farm_cards = farm_rows(CONFIG)
    levels, level_cards = level_rows(CONFIG)
    rows = farm + levels
    cards = {**level_cards, **farm_cards}

    OUT.mkdir(parents=True, exist_ok=True)
    rms = write_rms(rows)
    kept = [{k: v for k, v in row.items() if k != "machine"} for row in rows]
    (OUT / "choices.json").write_text(json.dumps(kept, indent=1) + "\n", encoding="utf-8")
    write_tables(rows, cards, rms)
    print(f"{len(farm)} FARM bundles, {len(levels)} level runs -> {OUT}")


if __name__ == "__main__":
    main()
