"""Parse the six ARM-FM candidates of the event-room smoke with our RM parser.

Run from the repository root, inside RM_RL_env (no LLM call):

    PYTHONPATH=app python -W ignore docs/paper/li2-undeclared-reward-rows/check/parse_attempts.py

Reads `attempts/<card>/attempts.json` (the generation record of each ARM-FM attempt) and parses
every candidate text. A candidate our parser rejects shows its error and the reward row it names.
"""

import json
from pathlib import Path

from src.arm_fm.runtime import RuntimeValidationError
from src.compiler.rm_format import parse_paper_reward_machine

HERE = Path(__file__).resolve().parent


def main() -> None:
    rejected = total = 0
    for record in sorted(HERE.glob("attempts/*/attempts.json")):
        for attempt in json.loads(record.read_text(encoding="utf-8")):
            total += 1
            try:
                parse_paper_reward_machine(attempt["candidate"])
                outcome = "parses"
            except RuntimeValidationError as error:
                rejected += 1
                outcome = f"parser error: {error}"
            print(f"{record.parent.name} attempt {attempt['attempt']}: {outcome}")
    print(f"{rejected} of {total} candidates stopped at the parser")


if __name__ == "__main__":
    main()
