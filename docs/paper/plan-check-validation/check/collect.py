"""Join truth.json with the plan-check records of S_DIR/records/PHASE/; write PHASE-results.json and PHASE.md.

Usage: python collect.py S_DIR PHASE   (PHASE like phase1). Reasons for false verdicts come from
S_DIR/PHASE-reasons.json ({"<arm>/<copy name>": why}) when it exists.
"""

import json
import sys
from collections import Counter
from pathlib import Path

SETS = ("1-right-final", "2-wrong-past", "3-arm-fm", "4-mutant")


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def outcome(truth: str, passed: bool | None) -> str:
    if truth == "unclear" or passed is None:
        return "not counted"
    if truth == "right":
        return "true pass" if passed else "FALSE FAIL"
    return "FALSE PASS" if passed else "true fail"


def row_of(study: Path, phase: str, item: dict) -> dict:
    folder = study / "records" / phase / item["set"] / item["suite"] / item["arm"]
    record = read(folder / f"{item['name']}.plan_check.json") or {}
    problems = record.get("problems") or []
    first = problems[0] if problems else ""
    passed = record.get("passed")
    return {
        **item,
        "card": record.get("card", item["name"].split("~", 1)[0]),
        "verdict": {True: "pass", False: "FAIL"}.get(passed, "unchecked"),
        "deciding_plan": first.split(":", 1)[0] if first else "-",
        "first_problem": first,
        "problems": problems,
        "outcome": outcome(item["truth"], passed),
    }


def table(rows: list[dict]) -> list[str]:
    lines = [
        "| set | machine | card | truth | check | deciding plan | outcome |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['set']} | {r['arm']}/{r['name']} | {r['card']} | {r['truth']} | {r['verdict']} "
            f"| {r['deciding_plan']} | {r['outcome']} |"
        )
    return lines


def counts(rows: list[dict]) -> list[str]:
    names = ("true pass", "true fail", "FALSE PASS", "FALSE FAIL", "not counted")
    lines = ["| set | " + " | ".join(names) + " | total |", "|---|" + "---|" * (len(names) + 1)]
    for name in (*SETS, "all"):
        tally = Counter(r["outcome"] for r in rows if name in ("all", r["set"]))
        lines.append(
            f"| {name} | "
            + " | ".join(str(tally[n]) for n in names)
            + f" | {sum(tally.values())} |"
        )
    return lines


def false_verdicts(rows: list[dict], reasons: dict) -> list[str]:
    lines = []
    for r in rows:
        if r["outcome"].startswith("FALSE") or r["outcome"] == "not counted":
            lines.append(
                f"- **{r['outcome']}** {r['set']} {r['arm']}/{r['name']} (check: {r['first_problem'] or 'pass'})"
            )
            lines.append(
                f"  - truth: {r['truth']}, {'; '.join(r['sources'])}. {r['what']}".rstrip()
            )
            if f"{r['arm']}/{r['name']}" in reasons:
                lines.append(f"  - why: {reasons[r['arm'] + '/' + r['name']]}")
    doubtful = reasons.get("_right_verdict_doubtful_reason", {})
    if doubtful:
        lines += ["", "Right verdicts whose deciding reason is not the real defect:", ""]
        lines += [f"- {name}: {why}" for name, why in doubtful.items()]
    return lines


def main() -> None:
    study, phase = Path(sys.argv[1]), sys.argv[2]
    truth = read(study / "truth.json")["machines"]
    reasons = read(study / f"{phase}-reasons.json") or {}
    rows = [row_of(study, phase, item) for item in truth]
    (study / f"{phase}-results.json").write_text(
        json.dumps(rows, indent=1) + "\n", encoding="utf-8"
    )
    notes = [f"- {note}" for note in reasons.get("_notes", [])]
    text = [
        f"# Plan check study, {phase}",
        "",
        *notes,
        "",
        "## Counts",
        "",
        *counts(rows),
        "",
        "## False and uncounted verdicts",
        "",
        *false_verdicts(rows, reasons),
        "",
        "## Every machine",
        "",
        *table(rows),
        "",
    ]
    (study / f"{phase}.md").write_text("\n".join(text), encoding="utf-8")
    print("\n".join(counts(rows)))


if __name__ == "__main__":
    main()
