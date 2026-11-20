"""The replay table: 15 resends of logged first generator requests, original prompt against shape named.

Usage: CC_ROOT=$PWD PYTHONPATH=app:docs/paper/hidden-output-schema/check python -W ignore \
    docs/paper/hidden-output-schema/check/replays.py     (from the repository root)
No model call: it reads `evidence/probes/*.json`, the raw responses the replays got (deepseek at
`medium`, OpenCode). Per replay: the prompt, clauses in the content, `finish_reason`, the score against
the card, short (not right and fewer clauses than the card's smallest answer), whether the reasoning
says the schema is not shown, and whether it plans the guessed keys `template` / `arguments`.
"""

import json
import re
from pathlib import Path

import arm_stats
import level_stats

PROBES = Path(__file__).resolve().parent.parent / "evidence" / "probes"
NOT_SHOWN = re.compile(
    r"schema[^.]{0,40}(not|n't)\s+(explicitly\s+)?(shown|included|visible|provided)"
    r"|no schema (shown|visible)|don't have the schema",
    re.IGNORECASE,
)
GUESSED_KEYS = re.compile(r'"(template|arguments)"')


def row(path: Path) -> dict:
    replay = json.loads(path.read_text())
    case = replay["label"].split("-")[0]
    clauses = replay["clauses"] or []
    verdict = arm_stats.score(case, clauses)
    reasoning = replay["reasoning_fields"].get("reasoning_content", "")
    return {
        "replay": replay["label"],
        "prompt": "shape named" if replay["edits"] else "original",
        "clauses": len(clauses),
        "finish": replay["finish_reason"],
        "score": verdict,
        "short": verdict != "right" and len(clauses) < level_stats.smallest_answer(case),
        "says not shown": bool(NOT_SHOWN.search(reasoning)),
        "plans template/arguments": bool(GUESSED_KEYS.search(reasoning)),
    }


def main() -> None:
    rows = [row(path) for path in sorted(PROBES.glob("*.json"))]
    print("| " + " | ".join(rows[0]) + " |")
    print("|---" * len(rows[0]) + "|")
    for r in sorted(rows, key=lambda r: (r["prompt"], r["replay"])):
        print("| " + " | ".join(str(v) for v in r.values()) + " |")
    for prompt in ("original", "shape named"):
        group = [r for r in rows if r["prompt"] == prompt]
        print(
            f"{prompt}: {len(group)} replays, short {sum(r['short'] for r in group)}, "
            f"right {sum(r['score'] == 'right' for r in group)}, "
            f"reasoning says the schema is not shown {sum(r['says not shown'] for r in group)}"
        )


if __name__ == "__main__":
    main()
