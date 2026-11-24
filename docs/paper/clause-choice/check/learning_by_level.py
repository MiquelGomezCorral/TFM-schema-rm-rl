"""Does a trained row learn with its level or with the answer its RM matches?

Takes the 15 card entries of the final run that list more than one answer (``clause_choice.py``) and
keeps the ones among the 60 trained rows. For each: the level (the card's gym id), the listed answer
the trained RM matches, whether that answer was listed before the RMs were read, and the learned
verdict of FARM's agents. The verdict is the final-results builder's (``outcome``, ``seed_learned``):
at least two seeds pass at 0.8 judged success, a soft-only card is compared with an idle agent
instead. The trained RM is the bundle each judge.json names (``rm_bundle``), matched to the
generation ``clause_choice.farm_rows`` reads from the bundle's manifest.

Writes ``evidence/learning-by-level.json`` (read by ``build_page.py``) and ``.md``.

Run from the repository root, inside RM_RL_env (no model call):
env PYTHONPATH=app:.git/agent-memory/artifacts/final-results python -W ignore
docs/paper/clause-choice/check/learning_by_level.py
"""

import contextlib
import io
import json
from collections import Counter
from pathlib import Path

from clause_choice import LETTERS, farm_rows, snapshot_options
from scipy.stats import fisher_exact

from src.config import Configuration

with contextlib.redirect_stdout(io.StringIO()):  # the builder prints its report on import
    import build_results as b

EVIDENCE = Path(__file__).resolve().parents[1] / "evidence"
BLOCKED = "MiniGrid-BlockedUnlockPickup-v0"  # the level where a ball blocks the door


def level_name(gym_id: str) -> str:
    return gym_id.removeprefix("MiniGrid-").removesuffix("-v0")


def is_added(option, card_id: str) -> bool:
    """True when an ``also_ok`` option was not listed at the level run, before the RMs were read."""
    return Counter(option) not in snapshot.get(card_id, [])


def trained_on(suite: str, card_id: str) -> list[str]:
    """The code commits (config.yaml ``git_head``) FARM's PPO runs of a card trained on."""
    folders = [
        f
        for s, c, arm, learner, f in b.JUDGED
        if (s, c, arm, learner) == (suite, card_id, "farm", "ppo")
    ]
    return sorted(
        {
            line.split(": ", 1)[1][:7]
            for folder in folders
            for line in (folder / "config.yaml").read_text(encoding="utf-8").splitlines()
            if line.startswith("git_head:")
        }
    )


def fisher(rows: list[dict], in_group) -> dict:
    """Learned / not learned for the rows in a group and outside it, and Fisher's exact p (two-sided)."""
    parts = ([r for r in rows if in_group(r)], [r for r in rows if not in_group(r)])
    table = [
        [sum(r["learned"] for r in part), sum(not r["learned"] for r in part)] for part in parts
    ]
    return {"in": table[0], "out": table[1], "p": round(float(fisher_exact(table).pvalue), 4)}


# ========= The 15 card entries, and the trained rows among them =========
rows_all, cards = farm_rows(Configuration())
# the ARM-FM baseline suites (xland, armfm-paper) were generated after the freeze, outside the 15 cards
cards = {key: card for key, card in cards.items() if key.split("/")[0] not in b.BASELINE_SUITES}
generation = {Path(r["rm_path"]).parent: r for r in rows_all}
snapshot = snapshot_options()  # the cards' also_ok options before the final run's RMs were read

rows, with_added = [], 0
for key, card in sorted(cards.items()):
    suite, card_id = key.split("/")
    with_added += any(is_added(option, card_id) for option in card.also_ok)
    if not b.trained(suite, card_id, "farm"):
        continue
    judges = b.old.seeds(suite, card_id, "farm")
    bundles = {Path(j["rm_bundle"]) for j in judges}
    assert len(bundles) == 1, f"{key}: seeds trained on different RMs"
    answer = generation[bundles.pop()]["answer"]
    assert answer != "none", f"{key}: the trained RM matches no listed answer"
    rows.append(
        {
            "card": key,
            "level": level_name(b.tasks(suite)[card_id]["env"]["gym_id"]),
            "blocked": b.tasks(suite)[card_id]["env"]["gym_id"] == BLOCKED,
            "answer": answer,
            "letter": LETTERS[answer],
            "later_listed": answer != "expect",
            "added_after": answer != "expect"
            and is_added(
                card.also_ok[int(answer.removeprefix("also_ok[").removesuffix("]"))], card_id
            ),
            "judged_success": [round(j["mean_judged_success"], 2) for j in judges],
            "seeds_passing": sum(b.seed_learned(suite, card_id, j) for j in judges),
            "soft_only": bool(judges[0].get("soft_only")),
            "trained_on": trained_on(suite, card_id),
            "learned": b.outcome(suite, card_id, "farm") == b.LEARNED,
            "arm_fm": b.outcome(suite, card_id, "arm-fm"),
            "no_rm": b.outcome(suite, card_id, "no-rm"),
        }
    )

# ========= Counts, tests and the three caveats =========
summary = {
    "card_entries": len(cards),
    "trained_rows": len(rows),
    "later_listed": sum(r["later_listed"] for r in rows),
    "later_listed_learned": sum(r["later_listed"] and r["learned"] for r in rows),
    "first_listed_learned": sum(not r["later_listed"] and r["learned"] for r in rows),
    "by_level": fisher(rows, lambda r: r["blocked"]),
    "by_answer": fisher(rows, lambda r: r["later_listed"]),
    "by_level_without_soft_only": fisher(
        [r for r in rows if not r["soft_only"]], lambda r: r["blocked"]
    ),
    "soft_only_learned_rows": [r["card"] for r in rows if r["soft_only"] and r["learned"]],
    "cards_with_added_answer": with_added,
    "trained_cards_with_added_answer": sum(
        any(is_added(o, c.id) for o in c.also_ok)
        for key, c in cards.items()
        if b.trained(*key.split("/"), "farm")
    ),
    "rows_matching_added_answer": sum(r["added_after"] for r in rows),
    "trained_rows_outside": len(b.TRAINABLE) - len(rows),
}
assert (summary["card_entries"], summary["trained_rows"], summary["later_listed"]) == (15, 9, 6), (
    summary
)

# Context, outside the nine: every FARM-trained row on the Blocked level, and the four not-learned
# rows for the other arms. Not part of the finding; it limits how far "follows the level" can be read.
level_rows = [
    b.outcome(suite, card_id, "farm")
    for suite, card_id in b.TRAINABLE
    if b.tasks(suite)[card_id]["env"]["gym_id"] == BLOCKED
]
summary["blocked_level_farm_rows"] = dict(
    Counter(o for o in level_rows if o in (b.LEARNED, b.NOT_LEARNED))
)
not_learned = [r for r in rows if not r["learned"]]
summary["not_learned_other_arms"] = {
    arm: sum(r[arm] == b.LEARNED for r in not_learned) for arm in ("arm_fm", "no_rm")
}

(EVIDENCE / "learning-by-level.json").write_text(
    json.dumps({"rows": rows, "summary": summary}, indent=1) + "\n", encoding="utf-8"
)

# ========= Readable copy =========
lines = [
    "# Learning by level on the trained rows with several accepted answers (generated by `check/learning_by_level.py`)",
    "",
    "E = `expect`, A = `also_ok[0]`. `added after`: the answer was listed only after the RMs were read.",
    "Judged success per seed; a row is learned when at least two seeds pass at 0.8 (a soft-only card:",
    "compared with an idle agent).",
    "",
    "| card | level | answer | judged success per seed | FARM | ARM-FM |",
    "|---|---|---|---|---|---|",
]
for r in sorted(rows, key=lambda r: (r["blocked"], r["card"])):
    answer = r["letter"] + (" (added after)" if r["added_after"] else "")
    seeds = ", ".join(f"{s:.2f}" for s in r["judged_success"]) + (
        " (soft only)" if r["soft_only"] else ""
    )
    verdict = "learned" if r["learned"] else "not learned"
    lines.append(
        f"| `{r['card']}` | {r['level']} | {answer} | {seeds} | {verdict} | {r['arm_fm']} |"
    )
for name, label, groups in (
    ("by_level", "Blocked level / other levels", ("on the Blocked level", "on other levels")),
    (
        "by_answer",
        "later-listed / first-listed answer",
        ("later-listed answer", "first-listed answer"),
    ),
):
    test = summary[name]
    lines += [
        "",
        f"**{label}.** Learned / not learned: {groups[0]} {test['in'][0]}/{test['in'][1]}, "
        f"{groups[1]} {test['out'][0]}/{test['out'][1]}; Fisher's exact p = {test['p']} (9 rows).",
    ]
lines += [
    "",
    "Without the soft-only row: learned / not learned on the Blocked level "
    f"{summary['by_level_without_soft_only']['in'][0]}/{summary['by_level_without_soft_only']['in'][1]}, "
    f"on other levels {summary['by_level_without_soft_only']['out'][0]}/"
    f"{summary['by_level_without_soft_only']['out'][1]}; Fisher's exact p = "
    f"{summary['by_level_without_soft_only']['p']} (8 rows).",
    f"Outside the nine: FARM's rows on the Blocked level, all 60 rows: {summary['blocked_level_farm_rows']}.",
    f"The {len(not_learned)} not-learned rows learned for the other arms: {summary['not_learned_other_arms']}.",
    f"Cards with an answer added after: {summary['cards_with_added_answer']} of {summary['card_entries']}, "
    f"{summary['trained_cards_with_added_answer']} of them trained; trained rows matching one: "
    f"{summary['rows_matching_added_answer']}.",
    f"Learned rows that rest on the idle comparison: {summary['soft_only_learned_rows']}.",
    "Code the runs trained on (config.yaml git_head): "
    + "; ".join(f"{r['card']} {','.join(r['trained_on'])}" for r in rows)
    + ".",
]
text = "\n".join(lines) + "\n"
(EVIDENCE / "learning-by-level.md").write_text(text, encoding="utf-8")
print(text, end="")
