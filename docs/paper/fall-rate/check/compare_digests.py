"""Compare two ``digests.json`` files of ``fall_half_rates.py`` on the episodes both contain.

Usage: python compare_digests.py <before/digests.json> <after/digests.json>
"""

import json
import sys
from pathlib import Path

before = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
after = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
shared = sorted(before.keys() & after.keys())
changed = [key for key in shared if before[key] != after[key]]
worlds = sorted({key.split("/")[0] for key in shared})
print(f"{len(shared)} shared episodes ({', '.join(worlds)}), {len(changed)} changed {changed[:5]}")
