"""Copy a pay-order sweep file without its per-step traces and machine text, so the entry keeps it small.

Keeps per row the key fields ``compare.py`` reads (``name`` or ``suite``/``card``/``answer``, ``ok``,
``summary``) plus the clause set and the small pay fields; drops ``traces``, ``idle``, ``plan_*`` and
``text`` (the chain sweep is 6 MB with them, about 0.1 MB without).

Usage: python slim_sweep.py SWEEP.jsonl OUT.jsonl
"""

import json
import sys
from pathlib import Path

DROP = {"traces", "idle", "text"}


def main() -> None:
    rows = [json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines() if line.strip()]
    slim = [
        {k: v for k, v in row.items() if k not in DROP and not k.startswith("plan_")}
        for row in rows
    ]
    Path(sys.argv[2]).write_text("".join(json.dumps(row) + "\n" for row in slim))
    print(len(slim), "rows")


if __name__ == "__main__":
    main()
