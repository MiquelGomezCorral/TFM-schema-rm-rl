"""Cases of the second generator-critic loop and the (a)/(b) scorer.

The gold is the card itself: `expect` and every `also_ok` answer (repo `clause_status`).
(a) = the final clause set matches `expect` (forced clauses optional) or one `also_ok` exactly.
(b) = for a set that fails (a): a reasonable answer that could still do the task in that level, yes/no.
(b) is a judgment written by hand in `judgments.json`: key = "<case>|<canonical clause set>" ->
{"ok": true|false, "why": "one line"}. A failing set without an entry counts as unjudged.
"""

import json
import os
from pathlib import Path

from src.benchmark.cards import Card
from src.benchmark.rm_facts import _normalized, clause_status

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("CC_ROOT", "/home/turbotowerlnx/Documents/Master/TFM/TFM-schema-rm-rl"))
# The cards each run was scored against; CARD_DIR=<entry>/evidence/llm-loop2/cards scores the loop-2 runs.
CARD_DIR = Path(os.environ.get("CARD_DIR", HERE.parent / "evidence" / "cards"))

# case -> (group, suite, bundle name, card id). W6 has one flagged bundle, so only it is in the working set.
CASES = {
    "W1a": ("W1", "box-carry", "cx-box-carry"),
    "W1b": ("W1", "templates", "tpl-chain-response-1-goal"),
    "W2a": ("W2", "templates", "tpl-precedence-1-nogoal"),
    "W2b": ("W2", "box-carry", "tpl-chain-response-1-nogoal-carry~p1"),
    "W3a": ("W3", "templates", "tpl-chain-response-2-nogoal"),
    "W3b": ("W3", "shop", "shop-siren~p2"),
    "W4a": ("W4", "shop", "shop-serve~p1"),
    "W4b": ("W4", "complex", "cx-goal-one-rule~p2"),
    "W5a": ("W5", "complex", "cx-goal-many-rules"),
    "W5b": ("W5", "templates", "tpl-precedence-3-goal"),
    "W6": ("W6", "complex", "cx-rules-only~p3"),
    "CX": ("cannot", "complex", "cx-box"),
    "NM": ("nomachine", "shop", "shop-boil"),
    "C1": ("control", "complex", "cx-siren"),
    "C2": ("control", "templates", "tpl-existence-1-nogoal"),
    "C3": ("control", "shop", "shop-pot"),
}
UNSEEN = {
    "U1": ("W1", "templates", "tpl-chain-response-3-goal"),
    "U2": ("W2", "templates", "tpl-chain-response-3-nogoal"),
    "U3": ("W3", "templates", "tpl-response-1-nogoal~p1"),
    "U4": ("W4", "forced-start", "tpl-responded-existence-1-nogoal-forced~p2"),
    "U5": ("W5", "complex", "cx-goal-one-rule~p3"),
    "U6": ("W6", "complex", "cx-rules-only~p1"),
    "U7": ("guard", "templates", "tpl-responded-existence-1-nogoal"),
}
# Chain prompt loop (2026-11-19): ordered tasks without earlier samples, and the 12 guard cards.
EXTRA = {
    "O1": ("ordered", "complex", "cx-goal-one-rule"),
    "O2": ("ordered", "complex", "cx-sequence"),
    "O3": ("ordered", "complex", "cx-sequence~p1"),
    "O4": ("ordered", "templates", "tpl-existence-1-goal~p2"),
    "O5": ("ordered", "templates", "tpl-precedence-4-goal"),
    "O6": ("ordered", "base", "base-doorkey"),
    "O7": ("ordered", "base", "base-blocked-unlock-pickup"),
    "O8": ("ordered", "templates", "tpl-precedence-1-goal~p3"),
    "G1": ("guard", "templates", "tpl-existence-1-goal"),
    "G2": ("guard", "templates", "tpl-existence-2-goal"),
    "G3": ("guard", "templates", "tpl-existence-3-goal"),
    "G4": ("guard", "templates", "tpl-existence-two-3-goal"),
    "G5": ("guard", "templates", "tpl-absence-2-nogoal"),
    "G6": ("guard", "templates", "tpl-precedence-2-goal"),
    "G7": ("guard", "templates", "tpl-precedence-1-goal"),
    "G8": ("guard", "templates", "tpl-precedence-3-nogoal"),
    "G9": ("guard", "templates", "tpl-response-2-goal"),
    "G10": ("guard", "templates", "tpl-response-1-goal"),
    "G11": ("guard", "templates", "tpl-not-co-existence-2-nogoal"),
    "G12": ("guard", "templates", "tpl-responded-existence-2-goal"),
    # Fix round: ordered tasks whose last step is only preferred (local cards, new wording).
    "S1": ("soft-last", "local-soft", "soft-key-goal"),
    "S2": ("soft-last", "local-soft", "soft-key-door-goal"),
    "S3": ("soft-last", "local-soft", "soft-door-box"),
    "S4": ("soft-last", "local-soft", "soft-key-door-box"),
}
ALL = {**CASES, **UNSEEN, **EXTRA}
WORKING = list(CASES)

_JUDGMENTS = HERE / "judgments.json"


def card_of(case: str) -> Card:
    _g, suite, name = ALL[case]
    base = name.partition("~p")[0]
    local = CARD_DIR / suite / "tasks.json"
    data = json.loads(
        (
            local if local.exists() else ROOT / "experiments/benchmark" / suite / "tasks.json"
        ).read_text()
    )
    return Card.from_dict({c["id"]: c for c in data["cards"]}[base])


def fmt(clause) -> str:
    template, names, priority = clause
    return f"{template}({','.join(names)}){'' if priority == 'hard' else '~s'}"


def canon(clauses) -> str:
    return ", ".join(sorted(fmt(c) for c in clauses))


def judgments() -> dict:
    return json.loads(_JUDGMENTS.read_text()) if _JUDGMENTS.exists() else {}


def classify(case: str, record: dict) -> tuple[str, str, str]:
    """Return (a, b, detail). a: exact / also_ok / mismatch / failed. b: yes / no / unjudged / - (a holds)."""
    if record.get("status") != "accepted" or not record.get("clauses"):
        return "failed", "no", (record.get("error") or record.get("status") or "")[:100]
    stored = _normalized(record["clauses"])
    a = clause_status(stored, card_of(case))
    shown = canon([(t, tuple(n), p) for t, n, p in stored])
    if a in ("exact", "also_ok"):
        return a, "-", shown
    entry = judgments().get(f"{case}|{shown}")
    if entry is None:
        return a, "unjudged", shown
    return a, "yes" if entry["ok"] else "no", shown


def is_goal_tag(case: str, shown: str) -> bool:
    """True for a (b)=yes set whose only extra is a goal the task does not state (judgment tag `added-goal`)."""
    return (judgments().get(f"{case}|{shown}") or {}).get("tag") == "added-goal"


def case_pass(rows) -> tuple[int, int, int]:
    """(samples (a), samples (a) or (b), samples) for a case's classify() rows."""
    a = sum(1 for r in rows if r[0] in ("exact", "also_ok"))
    b = sum(1 for r in rows if r[0] in ("exact", "also_ok") or r[1] == "yes")
    return a, b, len(rows)
