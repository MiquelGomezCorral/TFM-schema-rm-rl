"""Copy a round's call logs without the prompts, so the entry keeps them small.

Every ``<case>-r<k>.calls.jsonl`` in SRC is written to DEST with the same name and every field but
``system``, ``user`` and ``schema`` (the prompts: about 95% of the bytes). ``round_table.py`` reads
only the kept fields (stage, wall_s, error, provider, reply usage).

Usage: python slim_calls.py SRC_DIR DEST_DIR
"""

import json
import sys
from pathlib import Path

PROMPT_FIELDS = {"system", "user", "schema"}


def main() -> None:
    source, dest = Path(sys.argv[1]), Path(sys.argv[2])
    for path in sorted(source.glob("*-r*.calls.jsonl")):
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        slim = [{k: v for k, v in row.items() if k not in PROMPT_FIELDS} for row in rows]
        (dest / path.name).write_text("".join(json.dumps(row) + "\n" for row in slim))
        print(path.name, len(rows), "calls")


if __name__ == "__main__":
    main()
