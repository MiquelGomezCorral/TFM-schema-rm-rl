"""Static check of the ARM-FM machines that farmed reward during development (hack register H3-H7, H9, H12).

Per card: the machine text the runs trained on (saved from commit ecf6ca99 in ``evidence/machines/``), today's frozen
machine, whether the two texts are equal, and the loops of each that pay more than zero. The loop test is the one of
``docs/paper/reward-loops-and-rounds/check/pay_cycles.py`` (copied here: importing that file reruns its check). The laps
are listed as the development slices' ``cycles.py`` did: simple cycles, rewards summed once round, undiscounted.
Reads the saved old texts, today's bundles and ``reward-loops-and-rounds/evidence/bundles.json``; writes
``evidence/machines/<card>.today.txt``, ``evidence/cycles.json`` and ``evidence/same-as-today.txt``.
Run: python docs/paper/dev-reward-farming/check/old_machines.py (from the repo root).
"""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parents[1] / "evidence"
MACHINES = EVIDENCE / "machines"
OLD_COMMIT = "ecf6ca99"
BENCH = "experiments/benchmark"
BUNDLE_LIST = REPO / "docs/paper/reward-loops-and-rounds/evidence/bundles.json"
FROZEN = {row["path"]: row for row in json.loads(BUNDLE_LIST.read_text(encoding="utf-8"))}
# register row and bundle path (under experiments/benchmark) of each machine as trained
CARDS = [
    ("H3", "base/bundles/arm-fm/base-doorkey"),
    ("H4", "templates/bundles/arm-fm/tpl-precedence-1-goal"),
    ("H5", "templates/bundles/arm-fm/tpl-chain-response-1-goal"),
    ("H6", "templates/bundles/arm-fm/tpl-existence-two-1-nogoal"),
    ("H7", "templates/bundles/arm-fm/tpl-existence-two-1-goal"),
    ("H9", "templates/bundles/arm-fm/tpl-responded-existence-1-nogoal"),
    ("H12", "shop/bundles/arm-fm/shop-serve"),
    ("H12", "shop/bundles/arm-fm/shop-full"),
]
# H12 ran on unmerged code with `rm_ends_episode: false`: its final states did not end the episode
FINALS_CONTINUE = {"H12"}
# World events, as in pay_cycles.py: the world schedules at most two box falls and two siren rings per episode
WORLD = re.compile(r"(?<![!\w])(box_fell|siren_ringing|siren_rang|ring\w*)\b")


def parse(text):
    """Return the start state, final states, transitions and rewards of a machine text (pay_cycles.py)."""
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


def live_edges(initial, finals, trans, pay):
    """Edges among states reachable from the start without passing a final, with their reward."""
    edges = [(s, lab, d, pay.get((s, lab, d), 0.0)) for s, lab, d in trans if s not in finals]
    seen, todo = {initial}, [initial]
    while todo:
        u = todo.pop()
        for s, _, d, _ in edges:
            if s == u and d not in seen:
                seen.add(d)
                todo.append(d)
    return [e for e in edges if e[0] in seen and e[2] not in finals], seen


def has_paying_loop(edges, states):
    """Bellman-Ford for a cycle with a positive reward sum (pay_cycles.py:paying_loop)."""
    gain = dict.fromkeys(states, 0.0)
    for _ in range(len(states)):
        improved = False
        for s, _, d, r in edges:
            if gain[s] + r > gain[d] + 1e-9:
                gain[d] = gain[s] + r
                improved = True
        if not improved:
            return False
    return True


def paying_laps(edges):
    """Simple cycles with a positive reward sum, as 'states (guard of the closing edge) = +pay' (cycles.py)."""
    states = sorted({e[0] for e in edges} | {e[2] for e in edges})
    order = {s: i for i, s in enumerate(states)}
    laps = set()

    def walk(start, node, path, total):
        for s, lab, d, r in edges:
            if s != node:
                continue
            if d == start:
                laps.add((" -> ".join([*path, start]), round(total + r, 4), lab))
            elif order[d] > order[start] and d not in path:
                walk(start, d, [*path, d], total + r)

    for s in states:
        walk(s, s, [s], 0.0)
    # shortest laps first: the two-state pickup-and-drop loops the register names
    positive = sorted(
        (lap for lap in laps if lap[1] > 1e-9),
        key=lambda lap: (lap[0].count("->"), -lap[1], lap[0]),
    )
    return [f"{p} ({g}) = +{t:g}" for p, t, g in positive]


def check(text, finals_end):
    """Paying-loop verdict, its laps, and whether a loop pays without a world event."""
    initial, finals, trans, pay = parse(text)
    if not finals_end:
        finals = set()
    edges, states = live_edges(initial, finals, trans, pay)
    verdict = has_paying_loop(edges, states)
    laps = paying_laps(edges)
    assert verdict == bool(laps), "the two loop tests disagree"
    agent_edges = [e for e in edges if not WORLD.search(e[1])]
    return {
        "paying_loop": verdict,
        "pays_without_world_event": has_paying_loop(agent_edges, states),
        "paying_laps": len(laps),
        "laps": laps[:10],  # today's shop-full has thousands when its finals do not end the episode
    }


def both_rules(text):
    """The check when final states end the episode (the rule of every run but H12) and when they do not."""
    return {"finals_end": check(text, True), "finals_continue": check(text, False)}


def frozen_status(path):
    row = FROZEN.get(path)
    if row is None:
        return "not in the frozen set"
    trained = "trained in the final run" if row["trained"] else "not trained in the final run"
    return f"{row['status']}, {trained}"


def verdict_text(result):
    laps = "; ".join(result["laps"][:3])
    return f"yes ({laps})" if result["paying_loop"] else "no"


def card_line(out):
    run_rule = "finals_end" if out["final_states_end_episode"] else "finals_continue"
    as_run = "" if out["final_states_end_episode"] else " (final states do not end the episode)"
    same = "the same text" if out["same_text"] else "a different text"
    text = (
        f"{out['row']} {out['card']}: today's frozen machine ({out['today_path']}, "
        f"{out['today_status']}) is {same}.\n"
        f"    then, as trained{as_run}: {verdict_text(out['old'][run_rule])}\n"
        f"    today, final states end the episode: {verdict_text(out['today']['finals_end'])}\n"
    )
    if not out["final_states_end_episode"]:
        text += f"    today, final states do not end the episode: {verdict_text(out['today'][run_rule])}\n"
    return text


results = []
for row, old_rel in CARDS:
    card = Path(old_rel).name
    finals_end = row not in FINALS_CONTINUE
    old_text = (MACHINES / f"{card}.{OLD_COMMIT}.txt").read_text(encoding="utf-8")
    # the frozen shop bundles live in bundles-freeze/; the old folder still holds the 2026-11-14 text
    today_path = f"{BENCH}/{old_rel.replace('shop/bundles/', 'shop/bundles-freeze/')}"
    today_text = (REPO / today_path / "reward_machine.txt").read_text(encoding="utf-8")
    (MACHINES / f"{card}.today.txt").write_text(today_text, encoding="utf-8")
    results.append(
        {
            "row": row,
            "card": card,
            "old_path": f"{BENCH}/{old_rel}",
            "old_commit": OLD_COMMIT,
            "today_path": today_path,
            "today_status": frozen_status(today_path),
            "final_states_end_episode": finals_end,
            "same_text": old_text == today_text,
            "old": both_rules(old_text),
            "today": both_rules(today_text),
        }
    )
lines = [card_line(out) for out in results]

(EVIDENCE / "cycles.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
header = (
    f"Then = the machine text at commit {OLD_COMMIT} (what the runs trained on); today = the frozen bundle.\n"
    "Paying loop = a cycle of reachable states whose rewards sum above zero (check/old_machines.py);\n"
    "shortest laps first, at most three. H12 ran with final states not ending the episode\n"
    "(rm_ends_episode: false, unmerged); every other run and the final run end it at a final state.\n\n"
)
(EVIDENCE / "same-as-today.txt").write_text(header + "\n".join(lines), encoding="utf-8")
print(header + "\n".join(lines))
