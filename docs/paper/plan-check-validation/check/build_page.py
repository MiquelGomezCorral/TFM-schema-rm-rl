"""Build the plan-check validation page: draw the shown machines and write data.json.

Usage, from the repository root inside RM_RL_env (no model call):

    env PYTHONPATH=$PWD/app python docs/paper/plan-check-validation/check/build_page.py

It reads `evidence/` (truth, the per-phase results `collect.py` wrote, the verdict changes
`compare.py` wrote, the bundle copies in `copies.tar.gz`) and `check/spec.json` (the mutant
edits). Each shown
machine's `reward_machine.txt` is copied to `graphs/<id>.rm` and drawn with the code of
`render-rm --html` (`.svg` and `.html`). The artifacts skill's `fill.py` turns `data.json` into
`index.html`.
"""

import ast
import json
import tarfile
from collections import Counter
from pathlib import Path

from scripts.render_rm import render_file
from src.utils import ltlf_of

ENTRY = Path(__file__).resolve().parent.parent
EVIDENCE = ENTRY / "evidence"
CARDS = ENTRY.parent.parent.parent / "experiments" / "benchmark"
SETS = {
    "1-right-final": "Set 1 · right final FARM",
    "2-wrong-past": "Set 2 · wrong past FARM",
    "3-arm-fm": "Set 3 · ARM-FM",
    "4-mutant": "Set 4 · mutants",
}
GRAPH_HEIGHT = 480
FOLD_TITLE = "Task, clauses, LTLf, check and RM text"
FIX, BEFORE = "029d82c", "e6c3acb"  # plan-check code of phase 2 and phase 1

EXAMPLES = [  # one per set, all on the card tpl-precedence-1-goal
    "farm/tpl-precedence-1-goal",
    "farm/tpl-precedence-1-goal~lbO8r1",
    "arm-fm/tpl-precedence-1-goal",
    "farm/tpl-precedence-1-goal~m-dropped-order",
]
BLIND_SPOTS = [  # (title, machines, caught elsewhere by)
    (
        "A soft break on every step costs more than a hard break",
        ["farm/cx-rules-only~prefreeze", "farm/cx-goal-many-rules~prefreeze"],
        "check-pay-order (supplementary)",
    ),
    (
        "An added goal the solve reaches anyway",
        ["farm/tpl-chain-response-3-nogoal~prefreeze"],
        "the clause scorer (mismatch)",
    ),
    (
        "A no-goal machine that ends the shift early",
        ["arm-fm/shop-siren"],
        "the hand read only (supplementary)",
    ),
    (
        "A well edge that pays more than the solve",
        ["farm/tpl-precedence-1-goal~m-well-pays"],
        "construction only",
    ),
    (
        "A fact that fires late but in the right order",
        ["farm/base-doorkey~m-fact-late"],
        "the labeling replay",
    ),
]
FLIPS = [
    "farm/tpl-existence-soft-1-goal",
    "farm/tpl-existence-two-soft-1-nogoal",
    "farm/tpl-precedence-soft-2-goal",
    "arm-fm/tpl-existence-soft-1-goal",
]
LOOSE = [
    "arm-fm/tpl-response-soft-1-goal",
    "farm/tpl-existence-soft-1-goal~m-soft-pays-more",
    "farm/tpl-absence-soft-1-goal~m-soft-pays-more",
    "farm/tpl-existence-two-soft-1-nogoal~m-rule-costs",
]
UNCLEAR = "farm/tpl-responded-existence-1-goal~prefreeze"
CAUGHT_KINDS = [  # (text in the first problem, what the check saw); first match wins
    ("before the agent acts", "The machine ends the episode before the agent acts"),
    ("does not end in the well", "A hard rule broken for good stays out of the well"),
    ("reaches the final", "A plan that breaks a hard rule still finishes"),
    ("enters the well", "The solving plan falls into the well"),
    ("not the final", "The solving plan never finishes"),
    ("ends owing", "The solving plan never finishes"),
    ("pays nothing", "A soft break costs nothing"),
    ("not less than the solving plan", "A wrong plan pays as much as the solve"),
]


# ======================================================================================
#                                       INPUTS
# ======================================================================================


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def key_of(row: dict) -> str:
    return f"{row['arm']}/{row['name']}"


def by_key(rows: list[dict]) -> dict[str, dict]:
    keyed = {key_of(row): row for row in rows}
    assert len(keyed) == len(rows), "arm/name must name one machine"
    return keyed


AFTER = by_key(read_json(EVIDENCE / "phase2-results.json"))
EARLIER = by_key(read_json(EVIDENCE / "phase1-results.json"))
REASONS = read_json(EVIDENCE / "phase2-reasons.json")
SPEC = by_key(read_json(ENTRY / "check" / "spec.json"))


def copy_of(row: dict) -> str:
    return f"copies/{row['set']}/{row['suite']}/{row['arm']}/{row['name']}"


def bundle_text(row: dict, name: str) -> str:
    """One file of a bundle copy, read from the archive that keeps the copies byte-exact."""
    with tarfile.open(EVIDENCE / "copies.tar.gz") as archive:
        member = archive.extractfile(f"{copy_of(row)}/{name}")
        assert member is not None, f"{copy_of(row)}/{name} is not a file"
        return member.read().decode("utf-8")


def record_of(row: dict, phase: str) -> dict:
    folder = EVIDENCE / "records" / phase / row["set"] / row["suite"] / row["arm"]
    return read_json(folder / f"{row['name']}.plan_check.json")


def clauses_of(manifest: dict) -> list | None:
    clauses = manifest.get("generation", {}).get("clauses")
    return ast.literal_eval(clauses) if isinstance(clauses, str) else clauses


# ======================================================================================
#                                    MACHINE CARDS
# ======================================================================================


def machine_facts(text: str) -> str:
    field = {
        line.split(":")[0]: line.split(":", 1)[1].strip()
        for line in text.splitlines()
        if ": " in line or line.endswith(":")
    }
    lines = text.splitlines()
    moves = lines.index("REWARD_FUNCTION:") - lines.index("TRANSITION_FUNCTION:") - 1
    states = field["STATES"].count(",") + 1
    final = field.get("FINAL_STATES") or "none"
    well = field.get("REJECTING_STATES") or "none"
    return f"{states} states, {moves} transitions · final {final}, well {well}"


def draw(slug: str, text: str) -> None:
    rm_path = ENTRY / "graphs" / f"{slug}.rm"
    drawn = rm_path.with_suffix(".html").exists() and rm_path.read_text() == text
    rm_path.write_text(text)
    if not drawn:
        render_file(rm_path, rm_path.with_suffix(".svg"), html=True)


def source_text(row: dict) -> str:
    marked = [
        source.replace("hand-read", "hand read (supplementary)", 1) for source in row["sources"]
    ]
    return "; ".join(marked)


def verdict_text(row: dict) -> str:
    return "pass" if row["verdict"] == "pass" else f"FAIL, {row['first_problem']}"


def edit_lines(key: str) -> list[str]:
    lines = []
    for edit in SPEC[key].get("edits", []):
        if "function" in edit:
            lines.append(f"{edit['file']}, {edit['function']}(env) now returns: {edit['body']}")
        else:
            lines.append(f"{edit['file']}: {edit['old'].strip()!r} -> {edit['new'].strip()!r}")
    return lines


def fold_code(key: str, manifest: dict, slug: str, text: str) -> str:
    row, before = AFTER[key], EARLIER[key]
    code = f"# Task (NL)\n{manifest['task']}\n\n"
    clauses = clauses_of(manifest)
    if clauses is None:
        code += "# Clauses and LTLf\nNone: ARM-FM writes the machine straight from the task, so the bundle stores no clauses and has no LTL.\n\n"
    else:
        code += "# Clauses and LTLf (the bundle's manifest)\n"
        code += "\n".join(
            f"{priority} {pattern}({', '.join(names)}): {ltlf_of(pattern, names)}"
            for pattern, names, priority in clauses
        )
        code += "\n\n"
    if row["set"] == "4-mutant":
        code += "# Planted defect (check/spec.json)\n" + "\n".join(edit_lines(key)) + "\n\n"
    code += f"# Truth: {row['truth']}\n{source_text(row)}\n"
    code += f"{row['what']}\n\n" if row["what"] else "\n"
    code += f"# Plan check with the fix ({FIX}): {row['verdict']}\n"
    code += "".join(f"{problem}\n" for problem in row["problems"])
    if before["problems"] != row["problems"]:
        code += f"\n# Plan check before the fix ({BEFORE}): {before['verdict']}\n"
        code += "".join(f"{problem}\n" for problem in before["problems"])
    return code + f"\n# RM text (graphs/{slug}.rm)\n{text}"


def machine_item(key: str, note: str = "") -> dict:
    row = AFTER[key]
    manifest = json.loads(bundle_text(row, "manifest.json"))
    text = bundle_text(row, "reward_machine.txt")
    slug = f"{row['set'][0]}-{row['arm']}-{row['name'].replace('~', '_')}"
    draw(slug, text)
    caption = (
        f"**`{key}`** · {SETS[row['set']]} · {machine_facts(text)}\n"
        f"Task: *{manifest['task']}*\n"
        f"Truth: **{row['truth']}**. Check: **{verdict_text(row)}**."
    )
    return {
        "src": f"graphs/{slug}.html",
        "height": GRAPH_HEIGHT,
        "alt": f"Reward Machine {key}",
        "caption": caption + (f"\n{note}" if note else ""),
        "details": {
            "title": FOLD_TITLE,
            "text": f"Bundle copy `{copy_of(row)}` in `evidence/copies.tar.gz`; plan-check "
            "records under `evidence/records/`.",
            "code": fold_code(key, manifest, slug, text),
        },
    }


def gallery(items: list[dict]) -> dict:
    return {"type": "gallery", "width": 490, "items": items}


# ======================================================================================
#                                      SECTIONS
# ======================================================================================


def tally(rows: list[dict], name: str) -> Counter:
    return Counter(row["outcome"] for row in rows if name in ("all", row["set"]))


def chip(count: int, good: bool) -> dict | str:
    if count == 0:
        return "0"
    return {"text": str(count), "tone": "ok" if good else "bad"}


def count_table(rows: list[dict]) -> dict:
    lines = []
    for name in (*SETS, "all"):
        count = tally(rows, name)
        lines.append(
            [
                SETS.get(name, "All sets"),
                str(sum(count.values())),
                chip(count["true pass"], good=True),
                chip(count["FALSE FAIL"], good=False),
                chip(count["true fail"], good=True),
                chip(count["FALSE PASS"], good=False),
                str(count["not counted"]),
            ]
        )
    return {
        "type": "table",
        "columns": [
            "Set",
            "Machines",
            "Right · passes",
            "Right · fails",
            "Wrong · fails",
            "Wrong · passes",
            "Not counted",
        ],
        "rows": lines,
    }


def summary_section() -> dict:
    rows, earlier = list(AFTER.values()), list(EARLIER.values())
    now, then = tally(rows, "all"), tally(earlier, "all")
    right = now["true pass"] + now["FALSE FAIL"]
    wrong = now["true fail"] + now["FALSE PASS"]
    passes = now["true pass"] + now["FALSE PASS"]
    return {
        "id": "summary",
        "title": "Summary",
        "blocks": [
            {
                "type": "list",
                "items": [
                    f"**{len(rows)} machines in four sets, judged without the plan check.** 16 right "
                    "final FARM machines, 15 wrong FARM machines from before the freeze, 16 ARM-FM "
                    "machines and 15 mutants (a right machine with one planted defect). The truth "
                    "comes from the clause scorer, the labeling replay, training results, the "
                    "user's rulings and, for mutants, the planted defect.",
                    f"**With the fix ({FIX}), every right machine passes ({now['true pass']} of "
                    f"{right}) and {now['true fail']} of {wrong} wrong machines fail.**",
                    f"**{now['FALSE PASS']} wrong machines pass: the check's blind spots.** In two "
                    "a soft break on every step costs more than one hard break, one adds a goal the "
                    "solve reaches anyway, one no-goal machine ends the shift early, one well edge "
                    "pays more than the solve, and one fact fires late but in the right order.",
                    f"**Before the fix ({BEFORE}), {then['FALSE FAIL']} right machines failed.** "
                    "Each prices a soft rule by paying less than the solve, which the user ruled "
                    "right on 2026-11-22 (D1). The fix flips those four and no other verdict.",
                    f"**{now['not counted']} machine is not counted.** `{UNCLEAR.split('/')[1]}` "
                    "misses a clause its hard goal makes redundant, so both readings are fair.",
                ],
            },
            {
                "type": "callout",
                "tone": "info",
                "title": "What it means",
                "text": "After the fix, a fail can be trusted: no right machine failed. A pass "
                f"alone cannot: {now['FALSE PASS']} of {passes} counted passes are wrong machines. "
                "Four of those six are flagged by another tool in this study (pay order, the "
                "scorer, the labeling replay); the other two only by construction or by hand.",
            },
        ],
    }


def results_section() -> dict:
    return {
        "id": "results",
        "title": "Right and wrong against pass and fail",
        "blocks": [
            {
                "type": "text",
                "text": "Right or wrong is the truth from the other sources; pass or fail is the "
                "plan check's verdict. Green counts are where they agree, red where they do not.",
            },
            {"type": "text", "text": f"**With the fix (plan-check code of {FIX})**"},
            count_table(list(AFTER.values())),
            {"type": "text", "text": f"**Before the fix (plan-check code of {BEFORE})**"},
            count_table(list(EARLIER.values())),
            {
                "type": "text",
                "text": "Both runs use the same 62 bundle copies and the cards of "
                f"{FIX}; only the plan-check code differs. A rerun from the packed copies with "
                f"the {FIX} code gave the same verdict and problem list for all 62.",
            },
        ],
    }


def examples_section() -> dict:
    task = AFTER[EXAMPLES[0]]["card"]
    return {
        "id": "examples",
        "title": "One task, four machines",
        "blocks": [
            {
                "type": "text",
                "text": f"Each set has a machine for the card `{task}`: move the ball away from "
                "the door before taking the key, then open the door and pick up the box. The "
                "right one passes. The three wrong ones fail on the same plan, wrong-0, which "
                "takes the key before moving the ball: each machine still lets it finish.",
            },
            gallery([machine_item(key) for key in EXAMPLES]),
        ],
    }


def caught_section() -> dict:
    groups: dict[str, list[str]] = {}
    for row in AFTER.values():
        if row["outcome"] != "true fail":
            continue
        kind = next(label for text, label in CAUGHT_KINDS if text in row["first_problem"])
        groups.setdefault(kind, []).append(f"`{key_of(row)}`")
    return {
        "id": "caught",
        "title": "What the check caught",
        "blocks": [
            {
                "type": "text",
                "text": f"The {sum(len(v) for v in groups.values())} wrong machines that fail, by "
                "the first problem the check reports.",
            },
            {
                "type": "table",
                "columns": ["What the check saw", "Machines", "Which"],
                "rows": [
                    [kind, str(len(names)), ", ".join(names)]
                    for kind, names in sorted(groups.items(), key=lambda item: -len(item[1]))
                ],
            },
        ],
    }


def blind_spot_section() -> dict:
    groups = []
    for title, keys, caught in BLIND_SPOTS:
        groups.append(
            {
                "title": title,
                "note": f"Why it passes: {REASONS[keys[0]]} Caught elsewhere by: {caught}.",
                "items": [
                    machine_item(key, f"What is wrong: {AFTER[key]['what']}") for key in keys
                ],
            }
        )
    return {
        "id": "blind-spots",
        "title": "Blind spots: wrong machines that pass",
        "blocks": [
            {
                "type": "callout",
                "tone": "warn",
                "title": f"{len([k for _, keys, _ in BLIND_SPOTS for k in keys])} false passes",
                "text": "Each is wrong by a source outside the plan check, and the check passes "
                "it. The plans only see what a scripted run can reach: a pay order no plan "
                "plays, a goal the solve meets on the way, an early end of a no-goal shift, the "
                "pay on a well edge when the machine has a final state, a fact's timing.",
            },
            {"type": "gallery", "width": 490, "groups": groups},
        ],
    }


def flip_row(key: str) -> list:
    record = record_of(AFTER[key], "phase2")
    solves = {run["seed"]: run for run in record["runs"] if run["kind"] == "solve"}
    soft = next(run for run in record["runs"] if run["kind"] == "soft-break")
    solve = solves[soft["seed"]]
    return [
        f"`{key}`",
        {"text": "FAIL", "tone": "bad"},
        {"text": "pass", "tone": "ok"},
        f"{soft['plan']} ends {soft['end']} like the solve and pays {soft['pay'][0]} against "
        f"{solve['pay'][0]}, with no negative step",
    ]


def fix_section() -> dict:
    loose = REASONS["_right_verdict_doubtful_reason"]
    changes = read_json(EVIDENCE / "phase2-changes.json")
    return {
        "id": "fix",
        "title": "What the fix changed",
        "blocks": [
            {
                "type": "text",
                "text": "Before the fix a plan that breaks only soft rules passed only if some "
                "step paid a negative reward. The fix (`57a91cb`, merged in "
                f"`{FIX}`) also passes it when it ends where the solve on its layout ends and "
                "pays less than it, plain (`traces.priced_by_payout`). That is the user's ruling "
                f"D1 of 2026-11-22. It changed {len(changes)} of 62 verdicts, all from fail to "
                "pass, all right machines; no other problem list changed "
                "(`evidence/phase2-changes.json`).",
            },
            {
                "type": "table",
                "columns": ["Machine", "Before", "With the fix", "The soft break, seed 1"],
                "rows": [flip_row(key) for key in FLIPS],
            },
            gallery([machine_item(key) for key in FLIPS]),
            {
                "type": "text",
                "text": "**Right verdicts with a loose reason.** These wrong machines still fail "
                'after the fix, on "breaks only soft rules and pays nothing". The verdict is '
                "right; for the two `m-soft-pays-more` mutants the message understates it, "
                "since the break pays more than the solve. The ARM-FM machine was the risk named "
                "before the rerun (it could have turned into a false pass); it did not.",
            },
            gallery([machine_item(key, f"Reason: {loose[key]}") for key in LOOSE]),
        ],
    }


def unclear_section() -> dict:
    return {
        "id": "not-counted",
        "title": "Not counted (1)",
        "blocks": [
            {
                "type": "text",
                "text": f"The scorer calls its clauses a mismatch, and the check passes it. "
                f"{REASONS[UNCLEAR]} It stays out of every count above.",
            },
            gallery([machine_item(UNCLEAR)]),
        ],
    }


def truth_section() -> dict:
    rows = list(AFTER.values())

    def using(text: str) -> int:
        return sum(any(text in source for source in row["sources"]) for row in rows)

    hand_only = [
        f"`{key_of(row)}`"
        for row in rows
        if all(source.startswith("hand-read") for source in row["sources"])
    ]
    return {
        "id": "truth",
        "title": "Where the truth comes from",
        "blocks": [
            {
                "type": "table",
                "columns": ["Source", "What it decides", "Machines"],
                "rows": [
                    [
                        "Clause scorer (`rm-facts`)",
                        "the bundle's clauses against the card's answer: exact, also_ok, "
                        "equivalent or mismatch. FARM only: ARM-FM stores no clauses",
                        str(using("scorer")),
                    ],
                    [
                        "Labeling replay (`repair-labeling --check-only`)",
                        "whether the bundle's facts fire where the suite's reference traces say; "
                        "the shop has no traces, so its freeze gate record stands in",
                        str(using("labeling")),
                    ],
                    [
                        "Training results",
                        "success with the machine against the no-RM baseline, where it trained",
                        str(using("trained")),
                    ],
                    [
                        "The user's rulings (2026-11-22)",
                        "D1 a soft rule priced by paying less is fine, D2 helper facts are "
                        "allowed, D3 no-goal machines are judged by pay, and the accepted readings",
                        str(using("ruling")),
                    ],
                    [
                        "Construction",
                        "each mutant's planted defect (`check/spec.json`)",
                        str(using("construction")),
                    ],
                    [
                        "**Supplementary:** `check-pay-order`",
                        "the pay order of soft-break streams against a hard break; it decides "
                        "the two pricing blind spots of set 2",
                        str(using("pay-order")),
                    ],
                    [
                        "**Supplementary:** hand read",
                        "an ARM-FM machine read against its task, since the scorer cannot judge "
                        f"it; the only source for {', '.join(hand_only)}",
                        str(using("hand-read")),
                    ],
                ],
            },
            {
                "type": "text",
                "text": "Truth was written in `evidence/truth.json` before the counted runs. "
                "Eight folders had been checked once before that file was written; every folder "
                "ran again after it, and only those later runs count.",
            },
        ],
    }


def method_section() -> dict:
    card = next(
        c
        for c in read_json(CARDS / "templates" / "tasks.json")["cards"]
        if c["id"] == "tpl-precedence-1-goal"
    )
    plans = json.dumps(card["plans"], separators=(", ", ": "))
    return {
        "id": "method",
        "title": "Method",
        "blocks": [
            {
                "type": "steps",
                "items": [
                    {
                        "title": "The card gives the plans",
                        "text": "One solve plan and wrong plans that each break named rules of the "
                        "card's answer (`breaks`, `why`). A machine with no final state also "
                        "gets an idle run that only waits.",
                    },
                    {
                        "title": "A search makes the moves",
                        "text": "Each step (pick up the ball, open the door, wait) becomes real "
                        "moves by a breadth-first search on the live grid over position and "
                        "facing (`app/src/arm_fm/probe.py:153`).",
                    },
                    {
                        "title": "The bundle plays them",
                        "text": "Every move goes through `env.step`, so the bundle's own labeling "
                        "makes the facts and its machine steps on them, on the card's seeds "
                        "(`app/src/benchmark/cards.py:91`). The episode stops at a final or "
                        "well state.",
                    },
                    {
                        "title": "Rules judge each end",
                        "text": "Where each plan stops and what it paid decide pass or fail; "
                        "the rules are below.",
                    },
                ],
            },
            {
                "type": "list",
                "items": [
                    "**The solve finishes.** It ends in a final state without entering the well; "
                    "a machine with no final state ends it with nothing owed.",
                    "**A hard break never finishes.** It must not reach a final state, and a hard "
                    "rule broken for good must end in the well.",
                    "**A soft break finishes but costs.** Some step pays a negative reward or, "
                    "since the fix, it ends where the solve ends and pays less.",
                    "**No final state: pay decides.** Every wrong plan, and an idle run that "
                    "breaks a rule, pays less than the solve on the same layout, plain and "
                    "discounted at the bundle's gamma.",
                    "**The agent gets to act.** A machine that ends the episode before the first "
                    "action fails.",
                ],
            },
            {
                "type": "text",
                "text": f"The plans of `{card['id']}` (`experiments/benchmark/templates/tasks.json`), "
                f"task: *{card['task']}*",
            },
            {"type": "code", "text": plans},
        ],
    }


def every_machine_section() -> dict:
    rows = []
    for key, row in AFTER.items():
        tone = {"true pass": "ok", "true fail": "ok", "not counted": "info"}.get(
            row["outcome"], "bad"
        )
        rows.append(
            [
                SETS[row["set"]].split(" · ")[0],
                f"`{key}`",
                row["truth"],
                source_text(row),
                EARLIER[key]["verdict"],
                row["verdict"],
                {"text": row["outcome"], "tone": tone},
                row["first_problem"] or "-",
            ]
        )
    return {
        "id": "every-machine",
        "title": "Every machine",
        "blocks": [
            {
                "type": "details",
                "items": [
                    {
                        "title": f"All {len(rows)} machines",
                        "preview": "truth, its sources, both verdicts and the deciding problem",
                        "blocks": [
                            {
                                "type": "table",
                                "columns": [
                                    "Set",
                                    "Machine",
                                    "Truth",
                                    "Truth from",
                                    f"Check {BEFORE}",
                                    f"Check {FIX}",
                                    "Outcome",
                                    "First problem with the fix",
                                ],
                                "rows": rows,
                            }
                        ],
                    }
                ],
            }
        ],
    }


def files_section() -> dict:
    return {
        "id": "files",
        "title": "Files and rerun",
        "blocks": [
            {
                "type": "list",
                "items": [
                    "`evidence/copies.tar.gz`: the 62 bundle copies the check ran on, without "
                    "embeddings and raw responses, with their labeling-replay records. Packed so "
                    "the hooks cannot reformat their `labeling.py` and every byte stays as checked.",
                    "`evidence/records/phase1/`, `phase2/`: every plan-check record, before and "
                    "with the fix; `phase*-results.json` and `phase*.md` join them with the truth.",
                    "`evidence/truth.json`, `truth-raw/`: the truth per machine and the scorer "
                    "and pay-order outputs behind it.",
                    "`check/`: `spec.json` and `build.py` (how each copy was made), "
                    "`run_checks.py`, `snapshot_records.py`, `compare.py`, `collect.py`, "
                    "`clause_diff.py`, `pay_order.py`, `export_code.py`, and this page's "
                    "`build_page.py`.",
                ],
            },
            {
                "type": "code",
                "text": "# from the repository root, in RM_RL_env with MONA on PATH; W is a scratch folder\n"
                "cp -r docs/paper/plan-check-validation/evidence W\n"
                "tar -xzf W/copies.tar.gz -C W\n"
                f"python docs/paper/plan-check-validation/check/export_code.py {FIX} W/code\n"
                "python docs/paper/plan-check-validation/check/run_checks.py W W/code/app W/logs\n"
                "python docs/paper/plan-check-validation/check/snapshot_records.py W W/records/again\n"
                "python docs/paper/plan-check-validation/check/compare.py W/records/phase2 W/records/again W/changes.json\n"
                "# expect: 0 of 62 copies changed; collect.py W phase2 rebuilds the table",
            },
        ],
    }


def main() -> None:
    data = {
        "eyebrow": "Plan check · four sets, 62 machines · 2026-11-22",
        "title": "Does the plan check pass right machines and fail wrong ones?",
        "subtitle": "The plan check plays a card's scripted plans through a bundle and judges "
        "where each run ends and what it paid. Here it is tested on machines whose rightness "
        "is known from other sources, before and after the soft-break fix.",
        "sections": [
            summary_section(),
            results_section(),
            examples_section(),
            blind_spot_section(),
            caught_section(),
            fix_section(),
            unclear_section(),
            truth_section(),
            method_section(),
            every_machine_section(),
            files_section(),
        ],
    }
    (ENTRY / "data.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(f"data.json written; {len(list((ENTRY / 'graphs').glob('*.html')))} graphs")


if __name__ == "__main__":
    main()
