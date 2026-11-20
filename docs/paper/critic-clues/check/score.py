"""Score critic validation runs, pooled over repeats.

    python score.py LABEL [LABEL ...]        one summary row per label, then per-kind and per-item tables

Wrong items (with labelled defects):
  caught@1     runs whose first call rejects
  flag@1       defects flagged on the first call / defects
  flag@all     defects flagged within the run's calls / defects
  all-in       runs where every defect got flagged; calls = mean critic calls until then
  missed       runs the critic accepted with a defect left
  fixed-rej    runs where the critic rejected the fully fixed (right) candidate
  wrong-asks   changes asked that no defect covers, per rejecting call (judge's other_changes)
Right items: false alarm = the first call rejects.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent.parent / "evidence"


def load(label):
    rows = []
    for path in sorted((EVIDENCE / "runs" / label).glob("*-r*.json")):
        record = json.loads(path.read_text())
        if record.get("end") and record.get("calls") is not None:
            rows.append(record)
    return rows


def summary(rows):
    wrong = [r for r in rows if r["defects"]]
    right = [r for r in rows if not r["defects"]]
    defects = sum(r["defects"] for r in wrong) or 1
    all_in = [r for r in wrong if r["calls_to_all"]]
    rejecting = [c for r in wrong for c in r["calls"] if not c["accepted"] and "other_changes" in c]
    return {
        "runs": len(rows),
        "caught@1": f"{sum(r['rejected_first'] for r in wrong)}/{len(wrong)}",
        "flag@1": f"{100 * sum(r['flagged_first'] for r in wrong) / defects:.0f}%",
        "flag@all": f"{100 * sum(r['flagged_total'] for r in wrong) / defects:.0f}%",
        "all-in": f"{len(all_in)}/{len(wrong)}",
        "calls": f"{sum(r['calls_to_all'] for r in all_in) / max(1, len(all_in)):.2f}",
        "missed": f"{sum(r['end'] == 'accepted-with-defects' for r in wrong)}",
        "fixed-rej": f"{sum(r['end'] == 'false-alarm' for r in wrong)}",
        "wrong-asks": f"{sum(len(c['other_changes']) for c in rejecting) / max(1, len(rejecting)):.2f}",
        "false-alarm": f"{sum(r['rejected_first'] for r in right)}/{len(right)}",
        "errors": sum(1 for r in rows if r["end"] == "error"),
    }


def kinds(rows):
    out = defaultdict(lambda: [0, 0])
    for r in rows:
        for k in r.get("flagged_kinds", []):
            out[k][0] += 1
            out[k][1] += 1
        for k in r.get("missed_kinds", []):
            out[k][1] += 1
    return out


def per_item(rows):
    out = defaultdict(lambda: [0, 0, 0])  # flagged, defects (or false alarms, runs)
    for r in rows:
        cell = out[r["item"]]
        if r["defects"]:
            cell[0] += r["flagged_total"]
            cell[1] += r["defects"]
        else:
            cell[0] += int(r["rejected_first"])
            cell[1] += 1
        cell[2] += 1
    return out


def main() -> None:
    labels = sys.argv[1:]
    data = {label: load(label) for label in labels}
    keys = list(summary([]).keys())
    print("| label | " + " | ".join(keys) + " |")
    print("|---" * (len(keys) + 1) + "|")
    for label in labels:
        s = summary(data[label])
        print(f"| {label} | " + " | ".join(str(s[k]) for k in keys) + " |")
    print("\nflagged within the run, by defect kind")
    all_kinds = sorted({k for label in labels for k in kinds(data[label])})
    print("| kind | " + " | ".join(labels) + " |")
    for k in all_kinds:
        print(
            f"| {k} | "
            + " | ".join("{}/{}".format(*kinds(data[label]).get(k, [0, 0])) for label in labels)
            + " |"
        )
    print("\nper item: wrong = defects flagged/defects; right = false alarms/runs")
    items = sorted({i for label in labels for i in per_item(data[label])})
    print("| item | " + " | ".join(labels) + " |")
    for i in items:
        print(
            f"| {i} | "
            + " | ".join(
                "{}/{}".format(*per_item(data[label]).get(i, [0, 0, 0])[:2]) for label in labels
            )
            + " |"
        )


if __name__ == "__main__":
    main()
