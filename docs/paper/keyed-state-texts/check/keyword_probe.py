"""Probe a keyword check of state descriptions over every stored bundle (no model call).

Check: a non-final state's text must not claim the task is complete; the final's must not say
it is pending. Writes each hit with its state, role and text so false alarms can be read.

Usage: python keyword_probe.py REPO_ROOT OUT_JSON
"""

import json
import re
import sys
from pathlib import Path

# What a text claiming the task is done says, and what a text saying work remains says.
DONE = re.compile(
    r"\b(task|mission|objective)s? (is|are|has been|have been) (now )?"
    r"(complete|completed|finished|accomplished|satisfied)\b"
    r"|\ball (the )?(task |mandatory |hard )?(requirements|objectives|goals) "
    r"(are|have been) (now )?(satisfied|met|fulfilled|complete)\b"
    r"|\bthis is (the )?successful completion\b",
    re.IGNORECASE,
)
PENDING = re.compile(
    r"\b(still (needs?|has|must|required?|pending|to)|not yet|yet to|remains? (pending|to)"
    r"|is pending|are pending|must (still|now|next))\b",
    re.IGNORECASE,
)


def header(text: str, name: str) -> list[str]:
    for line in text.splitlines():
        if line.startswith(f"{name}:"):
            return [item.strip() for item in line.split(":", 1)[1].split(",") if item.strip()]
    return []


def main(root: Path, out: Path) -> None:
    hits, counted = [], {"bundles": 0, "non_final_texts": 0, "final_texts": 0}
    for descriptions_path in sorted(root.glob("experiments/**/bundles/**/state_descriptions.json")):
        folder = descriptions_path.parent
        machine_path = folder / "reward_machine.txt"
        if not machine_path.is_file():
            continue
        text = machine_path.read_text(encoding="utf-8")
        finals = set(header(text, "FINAL_STATES"))
        descriptions = json.loads(descriptions_path.read_text(encoding="utf-8"))
        counted["bundles"] += 1
        for state, description in descriptions.items():
            final = state in finals
            counted["final_texts" if final else "non_final_texts"] += 1
            pattern = PENDING if final else DONE
            if match := pattern.search(description):
                hits.append(
                    {
                        "bundle": str(folder.relative_to(root)),
                        "state": state,
                        "role": "final" if final else "not final",
                        "match": match.group(0),
                        "text": description,
                    }
                )
    summary = {
        **counted,
        "non_final_claims_done": sum(hit["role"] == "not final" for hit in hits),
        "final_says_pending": sum(hit["role"] == "final" for hit in hits),
    }
    out.write_text(json.dumps({"summary": summary, "hits": hits}, indent=2) + "\n", "utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
