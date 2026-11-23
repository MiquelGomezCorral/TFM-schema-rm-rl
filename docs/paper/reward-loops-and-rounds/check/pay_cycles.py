"""Static check: which built machines of the frozen set have a loop that pays more than zero.

A loop is a cycle of transitions among states reachable from the start without passing a final state
(the episode ends at a final). Its pay is the sum of the REWARD_FUNCTION rewards on its transitions
(missing = 0), undiscounted. Bellman-Ford as in app/src/compiler/reward_layer.py:806. Static only: it does
not ask whether the world can produce the loop's labels again.
Reads ``evidence/bundles.json`` (from ``bundle_list.py``), writes ``evidence/pay_cycles.json``.
Run: python docs/paper/reward-loops-and-rounds/check/pay_cycles.py (from the repo root).
"""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parents[1] / "evidence"
BUNDLES = json.loads((EVIDENCE / "bundles.json").read_text(encoding="utf-8"))
MACHINE = {
    (r["arm"], r["suite"], r["bundle"]): REPO / r["path"] / "reward_machine.txt" for r in BUNDLES
}


def parse(text):
    head, _, rest = text.partition("TRANSITION_FUNCTION:")
    trans_text, _, reward_text = rest.partition("REWARD_FUNCTION:")
    initial = re.search(r"INITIAL_STATE:\s*(\w+)", head).group(1)
    finals = set(re.findall(r"\w+", re.search(r"FINAL_STATES:(.*)", head).group(1)))
    trans = []
    for line in trans_text.splitlines():
        m = re.match(r"^\((\w+),\s*(.+)\)\s*->\s*(\w+)\s*$", line.strip())
        if m:
            trans.append((m.group(1), m.group(2).strip(), m.group(3)))
    pay = {}
    for line in reward_text.splitlines():
        m = re.match(r"^\((\w+),\s*(.+),\s*(\w+)\)\s*->\s*(\S+)\s*$", line.strip())
        if m:
            pay[(m.group(1), m.group(2).strip(), m.group(3))] = float(m.group(4))
    return initial, finals, trans, pay


def paying_loop(text):
    initial, finals, trans, pay = parse(text)
    edges = [(s, d, pay.get((s, lab, d), 0.0), lab) for s, lab, d in trans if s not in finals]
    seen, todo = {initial}, [initial]
    while todo:
        u = todo.pop()
        for s, d, _, _ in edges:
            if s == u and d not in seen:
                seen.add(d)
                todo.append(d)
    edges = [e for e in edges if e[0] in seen and e[1] not in finals]
    gain = dict.fromkeys(seen, 0.0)
    for _ in range(len(seen)):
        improved = False
        for s, d, r, _ in edges:
            if gain[s] + r > gain[d] + 1e-9:
                gain[d] = gain[s] + r
                improved = True
        if not improved:
            return None
    selfs = [f"({s}, {lab}) +{r}" for s, d, r, lab in edges if s == d and r > 1e-9]
    return selfs or ["multi-state loop"]


out = {}
for arm in ("farm", "arm-fm"):
    hits, built = [], 0
    for row in BUNDLES:
        if row["arm"] != arm or row["status"] != "complete":
            continue
        rm = MACHINE[(arm, row["suite"], row["bundle"])]
        if not rm.exists():
            continue
        built += 1
        loop = paying_loop(rm.read_text())
        if loop:
            name = row["bundle"]
            hits.append(
                {
                    "suite": row["suite"],
                    "bundle": name,
                    "loop": loop[:3],
                    "trained_card": "~p" not in name and row["trained"],
                }
            )
    out[arm] = {"built": built, "with_paying_loop": len(hits), "hits": hits}
    print(
        arm,
        "built",
        built,
        "with a paying loop",
        len(hits),
        "of them trained",
        sum(h["trained_card"] for h in hits),
    )


# Which loops need a world event? box_fell and siren_ringing come from the world's seeded schedule
# (app/src/arm_fm/service_room.py: at most two falls and two rings per episode; a drop is not a fall).
# A loop that pays only through an edge needing one of them is capped by the world, not farmable.
WORLD = re.compile(r"(?<![!\w])(box_fell|siren_ringing|siren_rang|ring\w*)\b")


def agent_loop(text):
    initial, finals, trans, pay = parse(text)
    keep = [(s, lab, d) for s, lab, d in trans if not WORLD.search(lab)]
    rebuilt = "INITIAL_STATE: {}\nFINAL_STATES: {}\nTRANSITION_FUNCTION:\n{}\nREWARD_FUNCTION:\n{}\n".format(
        initial,
        ", ".join(sorted(finals)) or "none",
        "\n".join(f"({s}, {lab}) -> {d}" for s, lab, d in keep),
        "\n".join(
            f"({s}, {lab}, {d}) -> {pay[(s, lab, d)]}" for s, lab, d in keep if (s, lab, d) in pay
        ),
    )
    return paying_loop(rebuilt)


for arm in ("arm-fm",):
    for h in out[arm]["hits"]:
        rm = MACHINE[(arm, h["suite"], h["bundle"])]
        h["agent_only_loop"] = bool(agent_loop(rm.read_text()))
    print(
        arm,
        "loops an agent can repeat without a world event:",
        sum(h["agent_only_loop"] for h in out[arm]["hits"]),
        [h["bundle"] for h in out[arm]["hits"] if h["agent_only_loop"]],
    )
(EVIDENCE / "pay_cycles.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
