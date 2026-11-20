"""Score chain-loop samples: right / accepted / wrong per case and per version.

    CC_ROOT=$PWD PYTHONPATH=app python chain_score.py LABEL=FOLDER[,FOLDER...] [LABEL=...] [--sets] [--base=LABEL]

right    = the card passes (exact or also_ok) and, on an ordered case, no hard Existence on an
           event the card's answer does not make a goal (the chain form: Existence of the last
           step plus Precedence, forced Precedences optional).
accepted = an ordered case whose set passes the card only with an Existence on an earlier step
           (one Existence per step, alone or next to the order clauses).
wrong    = the card rejects the set, or the run failed.
Cards that this loop may not edit get their forced chain Precedences as optional extras (CHAIN_EXTRAS).
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import cases

from src.benchmark.rm_facts import _normalized, clause_status

ORDERED = [
    "W4b",
    "W5a",
    "U5",
    "O1",
    "O2",
    "O3",
    "O4",
    "O5",
    "O6",
    "O7",
    "O8",
    "G1",
    "G7",
    "G10",
    "S1",
    "S2",
    "S3",
    "S4",
]
# Regression set: cases the n6 prompts passed on at least 2/3 of their earlier samples (n6, n6r, live loop, guard).
REGRESSION = [
    "W1a",
    "W1b",
    "W2a",
    "W2b",
    "W3a",
    "W3b",
    "W4a",
    "W4b",
    "W5a",
    "W5b",
    "CX",
    "C1",
    "C2",
    "C3",
    "U1",
    "U2",
    "U3",
    "U4",
    "U5",
    "U6",
    "U7",
    "G3",
    "G5",
    "G6",
    "G8",
    "G9",
    "G10",
    "G11",
    "G12",
]
H = "hard"
# Forced chain Precedences that a card we may not edit leaves out (the level guarantees each order).
CHAIN_EXTRAS = {
    "tpl-precedence-1-goal": {
        ("Precedence", ("has_door_key", "door_open"), H),
        ("Precedence", ("door_open", "target_picked_up"), H),
        ("Precedence", ("has_door_key", "target_picked_up"), H),
    },
    "cx-goal-many-rules": {
        ("Precedence", ("has_door_key", "door_open"), H),
        ("Precedence", ("has_door_key", "target_picked_up"), H),
    },
    "tpl-response-1-goal": {("Precedence", ("target_door_open", "target_picked_up"), H)},
}


def fmt(c):
    t, n, p = c
    return f"{t}({','.join(n)}){'' if p == 'hard' else '~s'}"


def canon(clauses):
    return ", ".join(sorted(fmt(c) for c in clauses))


def base_id(case):
    return cases.ALL[case][2].partition("~p")[0]


def forced_closure(card):
    """Precedence pairs the level forces: the transitive closure of the card's forced Precedences."""
    pairs = {
        c[1]
        for i, c in enumerate(card.expect)
        if i in card.forced and c[0] == "Precedence" and c[2] == H
    }
    grew = True
    while grew:
        grew = False
        for a, b in list(pairs):
            for b2, c in list(pairs):
                if b == b2 and a != c and (a, c) not in pairs:
                    pairs.add((a, c))
                    grew = True
    return {("Precedence", pair, H) for pair in pairs}


def passes(stored, card, extras):
    """Exact / also_ok / mismatch, with the optional extras (forced orders) allowed next to expect."""
    status = clause_status([[t, list(n), p] for t, n, p in stored], card)
    if status in ("exact", "also_ok"):
        return status
    required = Counter(c for i, c in enumerate(card.expect) if i not in card.forced)
    allowed = Counter(card.expect) + Counter(dict.fromkeys(extras, 1))
    have = Counter(stored)
    if required <= have and all(have[c] <= allowed[c] for c in have):
        return "exact+forced"
    return "mismatch"


def redundant_existences(stored):
    """Hard Existence(x) clauses the rest already forces: Existence(y) with a hard Precedence path x -> y."""
    prec = {c[1] for c in stored if c[0] == "Precedence" and c[2] == H}
    out = []
    for c in stored:
        if c[0] != "Existence" or c[2] != H:
            continue
        goals = {
            d[1][0] for d in stored if d is not c and d != c and d[0] == "Existence" and d[2] == H
        }
        forced, grew = set(goals), True
        while grew:
            grew = False
            for a, b in prec:
                if b in forced and a not in forced:
                    forced.add(a)
                    grew = True
        if c[1][0] in forced - goals or (c[1][0] in forced and c[1][0] not in goals):
            out.append(c)
    return out


def classify(case, record):
    """(verdict, tag, shown set): verdict right / accepted / wrong."""
    if record.get("status") != "accepted" or not record.get("clauses"):
        return "wrong", "failed", (record.get("error") or record.get("status") or "")[:90]
    stored = [(t, tuple(n), p) for t, n, p in _normalized(record["clauses"])]
    shown = canon(stored)
    card = cases.card_of(case)
    extras = forced_closure(card) | CHAIN_EXTRAS.get(base_id(case), set())
    status = passes(stored, card, extras)
    if status == "mismatch":
        drop = redundant_existences(stored)
        if drop:
            rest = [c for c in stored if c not in drop]
            if passes(rest, card, extras) != "mismatch":
                status = "redundant"
    if status == "mismatch":
        return "wrong", status, shown
    if case in ORDERED:
        goals = {
            c[1] for i, c in enumerate(card.expect) if c[0] == "Existence" and i not in card.forced
        }
        early = [c for c in stored if c[0] == "Existence" and c[2] == H and c[1] not in goals]
        if early:
            return "accepted", status, shown
    return "right", status, shown


def load(folders):
    rows = defaultdict(list)
    for folder in folders:
        for path in sorted(Path(folder).glob("*-r*.json")):
            case = path.stem.rsplit("-r", 1)[0]
            if case not in cases.ALL:
                continue
            record = json.loads(path.read_text())
            if record.get("status") not in ("accepted", "failed"):
                continue
            rows[case].append((path, record, *classify(case, record)))
    return rows


LETTER = {"right": "R", "accepted": "A", "wrong": "W"}


def print_per_case(versions, case_ids):
    print(
        "case  card                                   "
        + "  ".join(f"{label:>10}" for label in versions)
    )
    for case in case_ids:
        cells = []
        for rows in versions.values():
            cells.append("".join(LETTER[r[2]] for r in rows.get(case, [])) or "-")
        mark = ("O" if case in ORDERED else " ") + ("R" if case in REGRESSION else " ")
        print(
            f"{case:5} {mark} {cases.ALL[case][2][:36]:36} " + "  ".join(f"{c:>10}" for c in cells)
        )


def print_per_version(versions):
    print("version     runs  right  accepted  wrong | ordered runs  chain  accepted  wrong  chain%")
    for label, rows in versions.items():
        allv = Counter(r[2] for case in rows for r in rows[case])
        ordv = Counter(r[2] for case in rows if case in ORDERED for r in rows[case])
        n, no = sum(allv.values()), sum(ordv.values())
        pct = f"{100 * ordv['right'] / no:5.1f}" if no else "  -  "
        print(
            f"{label:10} {n:5} {allv['right']:6} {allv['accepted']:9} {allv['wrong']:6} | {no:12} {ordv['right']:6}"
            f" {ordv['accepted']:9} {ordv['wrong']:6}  {pct}"
        )


def lost_cases(base, rows):
    """Regression cases whose pass rate fell under 2/3 and 0.2 below the base version's."""
    lost = []
    for case in REGRESSION:
        b = base.get(case, [])
        v = rows.get(case, [])
        if not b or not v:
            continue
        rb = sum(r[2] != "wrong" for r in b) / len(b)
        rv = sum(r[2] != "wrong" for r in v) / len(v)
        if rv < 2 / 3 and rv < rb - 0.2:
            lost.append(f"{case} {sum(r[2] != 'wrong' for r in v)}/{len(v)} (base {rb:.2f})")
    return lost


def print_regression(versions, base_label):
    print("regression check (pass = right or accepted; rate vs base):")
    base = versions[base_label]
    for label, rows in versions.items():
        if label == base_label:
            continue
        lost = lost_cases(base, rows)
        print(f"  {label}: {'none lost' if not lost else '; '.join(lost)}")


def print_sets(versions, case_ids):
    for label, rows in versions.items():
        print(f"== {label}")
        for case in case_ids:
            for path, _record, verdict, tag, shown in rows.get(case, []):
                if verdict != "right" or "--all" in sys.argv:
                    print(f"  {path.stem:8} {verdict:8} {tag:11} {shown}")


def main():
    specs = [a for a in sys.argv[1:] if "=" in a and not a.startswith("--")]
    base_label = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--base=")), None)
    versions = {}
    for spec in specs:
        label, folders = spec.split("=", 1)
        versions[label] = load(folders.split(","))
    case_ids = [c for c in cases.ALL if any(c in v for v in versions.values())]
    print_per_case(versions, case_ids)
    print()
    print_per_version(versions)
    if base_label and base_label in versions:
        print()
        print_regression(versions, base_label)
    if "--sets" in sys.argv:
        print()
        print_sets(versions, case_ids)


if __name__ == "__main__":
    main()
