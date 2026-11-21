"""Per-state texts of the three re-tagged bundles: role, stored text, new texts and verdicts. No model call.

Usage, from the repository root inside RM_RL_env:
    PYTHONPATH=app python -W ignore docs/paper/keyed-state-texts/check/state_texts.py

Reads the stored bundle copies in `evidence/bundles/` (as committed on main `5284fff`), the three
re-tag rounds in `evidence/round-{1,2,3}/` (written by `retag.py`) and `evidence/verdicts.json`.
Checks that every round has one text per machine state, that each round's raw reply is a JSON object
keyed by exactly those state ids with the recorded texts, and that the recorded stored texts are the
bundle's. Copies each `reward_machine.txt` to `graphs/<name>.rm` and writes what it prints to
`evidence/state-texts.out`.
"""

import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

from src.arm_fm import load_bundle
from src.benchmark.declare_judge import ltlf_of

ENTRY = Path(__file__).resolve().parent.parent
EVIDENCE = ENTRY / "evidence"
BUNDLES = ("tpl-response-1-goal", "tpl-precedence-1-goal", "shop-serve")
ROUNDS = ("1", "2", "3")
VERDICTS = ("right", "half right", "wrong")


def round_record(name: str, number: str) -> dict:
    path = EVIDENCE / f"round-{number}" / f"bundles-{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def check_round(record: dict, states: list[str], stored: dict) -> list[str]:
    """Assert the round's texts are keyed by the machine's states and return its summary line."""
    ids = [row["state"] for row in record["states"]]
    reply = json.loads(record["last_reply"])
    assert ids == states, (record["bundle"], ids)
    assert list(reply) == states, (record["bundle"], list(reply))
    assert all(reply[row["state"]] == row["new"] for row in record["states"]), record["bundle"]
    assert all(row["old"] == stored[row["state"]] for row in record["states"]), record["bundle"]
    return [
        f"{len(record['calls'])} call(s), {len(record['warnings'])} warning(s), reply keyed by the "
        f"{len(states)} state ids and equal to the recorded texts: True"
    ]


def bundle_lines(name: str, verdicts: dict, tally: Counter) -> list[str]:
    folder = EVIDENCE / "bundles" / name
    bundle = load_bundle(folder)
    machine = bundle.reward_machine
    states = list(machine.states)
    stored = json.loads((folder / "state_descriptions.json").read_text(encoding="utf-8"))
    text = (folder / "reward_machine.txt").read_text(encoding="utf-8")
    records = {number: round_record(name, number) for number in ROUNDS}

    # == Header: task, clauses with their LTLf, machine ==
    lines = [
        f"== {name} ({records['1']['bundle']})",
        f"   task: {bundle.manifest.task}",
        "   clauses:",
    ]
    for template, names, priority in bundle.manifest.generation["clauses"]:
        readable = ltlf_of((template, tuple(names), priority))["readable"]
        lines.append(f"     {priority} {template}({', '.join(names)}): {readable}")
    digest = hashlib.md5(text.encode("utf-8"), usedforsecurity=False).hexdigest()
    lines.append(
        f"   {len(states)} states, {len(machine.transitions)} transitions, final "
        f"{list(machine.final_states)}, rejecting {list(machine.rejecting_states)}; md5 {digest}"
    )
    for number, record in records.items():
        lines += [f"   round {number}: " + line for line in check_round(record, states, stored)]
    repository = Path(records["1"]["bundle"]) / "state_descriptions.json"
    if repository.is_file():
        same = json.loads(repository.read_text(encoding="utf-8")) == stored
        lines.append(f"   {repository} still holds these stored texts: {same}")
    shutil.copyfile(folder / "reward_machine.txt", ENTRY / "graphs" / f"{name}.rm")
    lines.append(f"   wrote graphs/{name}.rm")

    # == One block per state ==
    roles = {row["state"]: row["role"] for row in records["1"]["states"]}
    for state in states:
        lines.append(f"-- {state} ({roles[state]})")
        verdict, why = verdicts["stored"].get(state, ["right", ""])
        tally[name, "stored", verdict] += 1
        lines.append(f"   stored [{verdict}]: {stored[state]}")
        if why:
            lines.append(f"     why: {why}")
        for number, record in records.items():
            new = next(row["new"] for row in record["states"] if row["state"] == state)
            verdict, why = verdicts["new"][number].get(state, ["right", ""])
            tally[name, f"round {number}", verdict] += 1
            lines.append(f"   new {number} [{verdict}]: {new}")
            if why:
                lines.append(f"     why: {why}")
    return lines


def tally_lines(tally: Counter) -> list[str]:
    lines = ["== verdicts (right / half right / wrong)"]
    for name in BUNDLES:
        cells = []
        for column in ("stored", *(f"round {number}" for number in ROUNDS)):
            counts = " / ".join(str(tally[name, column, verdict]) for verdict in VERDICTS)
            cells.append(f"{column} {counts}")
        lines.append(f"   {name}: " + " | ".join(cells))
    return lines


def main() -> None:
    verdicts = json.loads((EVIDENCE / "verdicts.json").read_text(encoding="utf-8"))["bundles"]
    tally: Counter = Counter()
    lines = []
    for name in BUNDLES:
        lines += bundle_lines(name, verdicts[name], tally)
    lines += tally_lines(tally)
    text = "\n".join(lines) + "\n"
    (EVIDENCE / "state-texts.out").write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
