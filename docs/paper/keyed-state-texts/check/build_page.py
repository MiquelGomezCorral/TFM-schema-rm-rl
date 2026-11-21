"""Build data.json of the page from the evidence; `fill.py` of the artifacts skill renders it. No model call.

Run from the repository root, inside RM_RL_env:

    PYTHONPATH=app python -W ignore docs/paper/keyed-state-texts/check/build_page.py
"""

import json
from collections import Counter
from pathlib import Path

from src.arm_fm import load_bundle
from src.compiler.rm_format import machine_view
from src.config import Configuration
from src.utils import Example, result_card

ENTRY = Path(__file__).resolve().parent.parent
EVIDENCE = ENTRY / "evidence"
ROUNDS = ("1", "2", "3")
TONES = {"right": "ok", "half right": "warn", "wrong": "bad"}
CUT = 90

BUNDLES = {
    "tpl-response-1-goal": {
        "title": "2. tpl-response-1-goal: three stored texts sit one state off",
        "level": "MiniGrid UnlockPickup, templates benchmark",
        "intro": (
            "The stored texts of u4, u5 and u6 are rotated by one: u4 holds u5's text, u5 holds u6's and u6 "
            "holds u4's. So the final state u4 reads as a duty still pending, and u6, where the door must "
            "still be opened, claims success. The keyed tagger puts every text on its own state in all three "
            "rounds."
        ),
    },
    "tpl-precedence-1-goal": {
        "title": "3. tpl-precedence-1-goal: two states claim the task is done",
        "level": "MiniGrid BlockedUnlockPickup, templates benchmark",
        "intro": (
            "Stored u1 holds the content of u6 (ball moved, box held), and u8 and u10 say every requirement "
            "is met although neither is final. The keyed tagger's texts sit on their own state in all three "
            "rounds. In round 1, u1 and u10 add that picking up the box ends the episode, a claim about the "
            "level the machine does not make (half right); rounds 2 and 3 do not repeat it."
        ),
    },
    "shop-serve": {
        "title": "4. shop-serve: seven stored texts drop or mix up a duty",
        "level": "Shop, shop-serve level, stored build",
        "intro": (
            "The machine has no final state and one well, u14: a fallen portion not picked up on the next "
            "move. Seven stored texts drop or mix up a duty, most often the food still to prepare. The keyed "
            "tagger's 17 texts name the duties of their own state in all three rounds. This is the stored "
            "build of main `5284fff` (hard charge -1, promise rows), not today's shop-serve machine; the "
            "re-tag described this stored machine."
        ),
    },
}

PLAIN_WORDS = (
    'A Reward Machine tracks where the agent is in a task: each state is a stage, such as "key taken, '
    'door still closed". A model, the state tagger, writes one short text per state, and training turns '
    "each text into the state embedding the agent reads. A state that carries another state's text tells "
    "the agent the wrong stage. The tagger used to answer with a plain list of texts, and the code gave the "
    "first text to the first state, the second to the second, and so on. Nothing checked that a text was "
    "about its state, and the list of states to describe carried no role."
)


# ======================================================================================
#                                       READING
# ======================================================================================


def state_lines(rm_text: str) -> dict[str, str]:
    """Each state's line of the tagger's state list: role, owed stages, a shortest way in."""
    Configuration.MACHINE_PROMPT_MAX_CHARS = 0
    view = machine_view(rm_text)
    listed = view.split("STATE_LIST:\n", 1)[1]
    return dict(line.split(": ", 1) for line in listed.splitlines() if line.strip())


def load(name: str) -> dict:
    folder = EVIDENCE / "bundles" / name
    rm_text = (folder / "reward_machine.txt").read_text(encoding="utf-8")
    records = {}
    for number in ROUNDS:
        path = EVIDENCE / f"round-{number}" / f"bundles-{name}.json"
        records[number] = json.loads(path.read_text(encoding="utf-8"))
    return {
        "bundle": load_bundle(folder),
        "rm_text": rm_text,
        "lines": state_lines(rm_text),
        "records": records,
    }


def verdict(verdicts: dict, column: str, state: str) -> tuple[str, str]:
    table = verdicts["stored"] if column == "stored" else verdicts["new"][column]
    word, why = table.get(state, ["right", ""])
    return word, why


def chip(word: str, why: str) -> dict:
    return (
        {"text": word, "tone": TONES[word], "title": why}
        if why
        else {"text": word, "tone": TONES[word]}
    )


def count_line(counts: Counter) -> str:
    parts = [f"{counts[word]} {word}" for word in TONES if counts[word]]
    return ", ".join(parts)


# ======================================================================================
#                                       SECTIONS
# ======================================================================================


def bundle_section(name: str, data: dict, verdicts: dict) -> dict:
    bundle, records, lines = data["bundle"], data["records"], data["lines"]
    machine = bundle.reward_machine
    first = records["1"]["states"]
    final = f"final {', '.join(machine.final_states)}" if machine.final_states else "no final"
    well = f"well {', '.join(machine.rejecting_states)}"
    caption = (
        f"**`{name}`** · {BUNDLES[name]['level']} · {len(machine.states)} states, "
        f"{len(machine.transitions)} transitions · {final}, {well}\nTask: *{bundle.manifest.task}*"
    )
    example = Example(bundle.manifest.task, bundle.manifest.generation["clauses"], data["rm_text"])
    card = result_card(
        f"graphs/{name}.html",
        caption,
        example,
        height=520,
        alt=f"Reward Machine {name}: {len(machine.states)} states",
    )

    # == The per-state table, stored against round 1 ==
    rows, reasons = [], []
    for row in first:
        state = row["state"]
        stored_word, stored_why = verdict(verdicts, "stored", state)
        new_word, new_why = verdict(verdicts, "1", state)
        rows.append(
            [
                state,
                lines[state],
                row["old"],
                chip(stored_word, stored_why),
                row["new"],
                chip(new_word, new_why),
            ]
        )
        if stored_why:
            reasons.append(f"**{state}, stored: {stored_word}.** {stored_why}")
        if new_why:
            reasons.append(f"**{state}, new (round 1): {new_word}.** {new_why}")
    table = {
        "type": "table",
        "heading": "Each state's text: stored (old tagger, as committed) and new (keyed tagger, round 1)",
        "columns": [
            "state",
            "role, owed stages, a shortest way in (`state_list.py`)",
            "stored text",
            "verdict",
            "new text, round 1",
            "verdict",
        ],
        "rows": rows,
    }

    # == Rounds 2 and 3, folded ==
    items = []
    for number in ROUNDS[1:]:
        counts = Counter(
            verdict(verdicts, number, row["state"])[0] for row in records[number]["states"]
        )
        round_rows = [
            [row["state"], row["new"], chip(*verdict(verdicts, number, row["state"]))]
            for row in records[number]["states"]
        ]
        items.append(
            {
                "title": f"Round {number}: {count_line(counts)}",
                "text": f"`evidence/round-{number}/bundles-{name}.json`",
                "blocks": [
                    {
                        "type": "table",
                        "columns": ["state", "new text", "verdict"],
                        "rows": round_rows,
                    }
                ],
            }
        )

    blocks = [
        {"type": "gallery", "width": 490, "items": [card]},
        table,
        {"type": "list", "heading": "Why each text that is not right", "items": reasons},
        {"type": "details", "heading": "The texts of rounds 2 and 3", "items": items},
    ]
    return {
        "id": name,
        "title": BUNDLES[name]["title"],
        "intro": BUNDLES[name]["intro"],
        "blocks": blocks,
    }


def fix_section(response: dict) -> dict:
    record = response["records"]["1"]
    roles = {row["state"]: row["role"] for row in record["states"]}
    reply = json.loads(record["last_reply"])
    cut = {state: text[:CUT] + " ..." for state, text in reply.items()}
    code = (
        "# Nodes to tag: the request for tpl-response-1-goal (one request for all 7 states)\n"
        f"{json.dumps(roles)}\n\n"
        f"# The reply, round 1 (each text cut to its first {CUT} characters on this page)\n"
        f"{json.dumps(cut, indent=1)}"
    )
    rows = [
        [
            "the states to describe",
            'an ordered list of ids: `["u0", "u1", ...]`',
            "each id with its role: `final`, `rejecting` or `in progress`",
        ],
        [
            "the reply",
            "a JSON list of texts, in the list's order",
            "a JSON object keyed by state id",
        ],
        ["how a text reaches its state", "by its place in the list", "by its key"],
        [
            "what is refused",
            "a list of the wrong length",
            "a missing, repeated or unknown id, and a text that only repeats a role word; the reply schema allows no other key",
        ],
    ]
    return {
        "id": "fix",
        "title": "1. The defect and the fix",
        "blocks": [
            {
                "type": "callout",
                "tone": "bad",
                "title": "The defect",
                "text": (
                    "A reply with one text per state always passed, whatever state each text was written for. "
                    "On tpl-response-1-goal the texts of u4, u5 and u6 are rotated by one, so each sits on "
                    "another of the three states. Nothing failed, since the count matched."
                ),
            },
            {
                "type": "table",
                "heading": "The tagger request and reply, before and after commit `6539207`",
                "columns": ["", "before", "after"],
                "rows": rows,
            },
            {"type": "code", "heading": "The keyed request and reply, as recorded", "text": code},
            {
                "type": "text",
                "text": (
                    "Code (commit `6539207`, merge `ba918a9`): the reply schema `state_descriptions_schema` "
                    "(`app/src/engines/structured.py:126`), the parser `parse_state_descriptions` and "
                    "`_refuse_repeated_keys` (`app/src/engines/structured.py:184`), the request "
                    "`describe_states` (`app/src/engines/generic_engine.py:112`), the roles `_state_roles` "
                    '(`app/scripts/generate_rm.py:552`), and the prompt\'s "Nodes to tag" and "Output" '
                    "(`app/src/prompts/compiler-rm/reward-machine-tagger.system.md:85` and `:123`). The role "
                    "words `STATE_FINAL`, `STATE_REJECTING` and `STATE_IN_PROGRESS` have one owner in "
                    "`src.engines`."
                ),
            },
        ],
    }


def rounds_section(datas: dict, verdicts: dict) -> dict:
    rows = []
    for name, data in datas.items():
        cells = [name, str(len(data["records"]["1"]["states"]))]
        for column in ("stored", *ROUNDS):
            counts = Counter(
                verdict(verdicts[name], column, row["state"])[0]
                for row in data["records"]["1"]["states"]
            )
            tone = (
                "ok"
                if counts["right"] == sum(counts.values())
                else ("bad" if counts["wrong"] else "warn")
            )
            cells.append({"text": count_line(counts), "tone": tone})
        calls = sum(len(data["records"][number]["calls"]) for number in ROUNDS)
        warnings = sum(len(data["records"][number]["warnings"]) for number in ROUNDS)
        cells.append(f"{calls} calls, {warnings} warnings")
        rows.append(cells)
    return {
        "id": "rounds",
        "title": "5. Three rounds, the same placement each time",
        "blocks": [
            {
                "type": "table",
                "heading": "Verdicts per bundle (`evidence/state-texts.out`)",
                "columns": [
                    "bundle",
                    "states",
                    "stored",
                    "round 1",
                    "round 2",
                    "round 3",
                    "model calls",
                ],
                "rows": rows,
            },
            {
                "type": "list",
                "items": [
                    "**Model:** deepseek-v4.1-flash at max thinking over OpenCode, the only provider run live.",
                    "**Attempts:** round 1 allowed 3 attempts per request (`RETAG_ATTEMPTS`), rounds 2 and 3 one. "
                    "Every round needed one request per bundle; none was refused.",
                    "**Verdict standard:** right, the role and the owed steps match the state; half right, they "
                    "match but the text adds a claim the machine does not support; wrong, the text describes "
                    "another state or the wrong duties. The fix worker judged the new texts and the wrong stored "
                    "ones; this entry added the two half-right stored texts of tpl-precedence-1-goal (u5, u6). "
                    "One reader, no second judge (`evidence/verdicts.json`).",
                ],
            },
        ],
    }


def probe_section(verdicts: dict) -> dict:
    probe = json.loads((EVIDENCE / "keyword_probe.json").read_text(encoding="utf-8"))
    rows, real = [], 0
    for hit in probe["hits"]:
        name = Path(hit["bundle"]).name
        is_real = (
            name in BUNDLES and verdicts[name]["stored"].get(hit["state"], ["right"])[0] == "wrong"
        )
        real += is_real
        mark = (
            {"text": "real", "tone": "bad"} if is_real else {"text": "false alarm", "tone": "muted"}
        )
        rows.append(
            [f"`{hit['bundle']}`", hit["state"], hit["role"], hit["match"], mark, hit["text"]]
        )
    summary = probe["summary"]
    texts = summary["non_final_texts"] + summary["final_texts"]
    wrong = sum(
        word == "wrong" for name in BUNDLES for word, _ in verdicts[name]["stored"].values()
    )
    assert real == 4 and len(rows) == 26, (real, len(rows))
    return {
        "id": "probe",
        "title": "6. A word search does not find the fault",
        "intro": (
            "A cheaper check was also tried: search every stored text for words that claim the task "
            "is done in a state that is not final, or that a duty is pending in the final state "
            "(`check/keyword_probe.py`, no model call). A negative result."
        ),
        "blocks": [
            {
                "type": "stats",
                "items": [
                    {
                        "value": f"{summary['bundles']}",
                        "label": f"stored bundles searched, {texts:,} texts",
                    },
                    {"value": f"{len(rows)}", "label": "hits"},
                    {"value": f"{real}", "label": "real hits, all four on this page"},
                    {"value": f"{len(rows) - real}", "label": "false alarms", "tone": "warn"},
                    {
                        "value": f"{wrong - real} of {wrong}",
                        "label": "wrong stored texts on this page it misses",
                        "tone": "bad",
                    },
                ],
            },
            {
                "type": "text",
                "text": (
                    'The false alarms are conditionals and negations, such as "once the box is held, the task '
                    'is complete" or "no order is pending". The four real hits are tpl-response-1-goal u4 and '
                    "u6 and tpl-precedence-1-goal u8 and u10. The search misses response u5, precedence u1 and "
                    "all seven of shop-serve's wrong texts: a text on the wrong state needs no completion word. "
                    "The stored bundles need a re-tag, not a word search."
                ),
            },
            {
                "type": "details",
                "items": [
                    {
                        "title": f"The {len(rows)} hits (`evidence/keyword_probe.json`)",
                        "text": "Real: the text is wrong by this page's verdicts. Every other hit was read by hand.",
                        "blocks": [
                            {
                                "type": "table",
                                "columns": ["bundle", "state", "role", "matched", "", "text"],
                                "rows": rows,
                            }
                        ],
                    }
                ],
            },
        ],
    }


def claim_section() -> dict:
    return {
        "id": "claim",
        "title": "What it shows",
        "blocks": [
            {"type": "callout", "tone": "info", "title": "In plain words", "text": PLAIN_WORDS},
            {
                "type": "stats",
                "items": [
                    {
                        "value": "13 of 37",
                        "label": "stored texts on three bundles that describe another state or the wrong duties",
                        "tone": "bad",
                    },
                    {
                        "value": "37 of 37",
                        "label": "new texts on their own state, in each of 3 rounds",
                        "tone": "ok",
                    },
                    {
                        "value": "2",
                        "label": "new texts of round 1 that add a claim the machine does not support; 0 in rounds 2 and 3",
                        "tone": "warn",
                    },
                    {"value": "9", "label": "model calls: one per bundle and round, none refused"},
                    {
                        "value": "22 of 26",
                        "label": "word-search hits over 379 stored bundles that are false alarms",
                        "tone": "warn",
                    },
                ],
            },
            {
                "type": "list",
                "items": [
                    "**The defect.** The tagger's texts reached their states by position. On tpl-response-1-goal "
                    "three texts sit one state off; on tpl-precedence-1-goal two states that are not final say the "
                    "task is done; on shop-serve seven texts drop or mix up a duty.",
                    "**The fix.** Commit `6539207` (merge `ba918a9`) sends each state's role beside it and keys the "
                    "reply by state id. A missing, repeated or unknown id is refused and asked again.",
                    "**Live result.** Three rounds of the three bundles with deepseek-v4.1-flash: every new text sits "
                    "on its own state. In round 1, tpl-precedence-1-goal has 11 right and 2 half right; the two add a "
                    "wrong claim about the level.",
                    "**Negative result.** A word search for completion and pending words finds 26 hits over 379 "
                    "stored bundles, 22 of them false alarms, and misses 9 of the 13 wrong stored texts here.",
                    "**Not done.** The stored bundles keep their old texts, and no training ran with the new ones, so "
                    "the effect on learning is not measured.",
                ],
            },
        ],
    }


def evidence_section() -> dict:
    rerun = (
        "E=docs/paper/keyed-state-texts\n"
        "# every state's texts and verdicts, the checks, and graphs/<name>.rm (writes evidence/state-texts.out)\n"
        "PYTHONPATH=app python -W ignore $E/check/state_texts.py\n"
        "for m in $E/graphs/*.rm; do PYTHONPATH=app python app/main.py render-rm --rm-file $m --svg-dir ${m%.rm}.svg --html; done\n"
        "# one machine's state list, as the tagger's request shows it\n"
        "PYTHONPATH=app python -W ignore $E/check/state_list.py $E/evidence/bundles/shop-serve/reward_machine.txt\n"
        "# the word search over every committed bundle\n"
        "python $E/check/keyword_probe.py . OUT.json\n"
        "# this page\n"
        "PYTHONPATH=app python -W ignore $E/check/build_page.py\n"
        "python3 ~/.claude/skills/agent-artifacts/scripts/fill.py $E/data.json $E/index.html\n"
        "# the live re-tag: one deepseek-v4.1-flash call per bundle over OpenCode, key from .env\n"
        "RETAG_ATTEMPTS=1 PYTHONPATH=app dotenv -f .env run --no-override -- python -W ignore $E/check/retag.py OUT_DIR \\\n"
        "  experiments/benchmark/templates/bundles/farm/tpl-response-1-goal \\\n"
        "  experiments/benchmark/templates/bundles/farm/tpl-precedence-1-goal \\\n"
        "  experiments/benchmark/shop/bundles/farm/shop-serve"
    )
    return {
        "id": "evidence",
        "title": "Evidence, rerun and code",
        "blocks": [
            {
                "type": "list",
                "items": [
                    "**Bundles:** `evidence/bundles/<name>/` (manifest, machine, labeling, stored state texts) for "
                    "the three bundles, as committed on main `5284fff`; `graphs/`, the three machines as live HTML, "
                    "SVG and RM text.",
                    "**Re-tag rounds:** `evidence/round-1/`, `round-2/`, `round-3/`, one JSON per bundle from "
                    "`check/retag.py`: every state's role, entry guards, new text, stored text, the model's raw "
                    "reply and the calls.",
                    "**Verdicts:** `evidence/verdicts.json`; `evidence/state-texts.out`, what `check/state_texts.py` "
                    "prints (it checks that each raw reply is keyed by exactly the machine's states and equals the "
                    "recorded texts, and that the recorded stored texts are the bundle's).",
                    "**Word search:** `evidence/keyword_probe.json`, from `check/keyword_probe.py`.",
                    "**Limits:** three bundles, one model, one provider (OpenCode); the verdicts are one reader's. "
                    "The re-tag wrote no bundle: the stored bundles keep their old texts until they are rebuilt. No "
                    "training ran with the new texts.",
                ],
            },
            {
                "type": "text",
                "text": "**Rerun (from the repository root in RM_RL_env; only `retag.py` calls a model)**",
            },
            {"type": "code", "text": rerun},
            {
                "type": "text",
                "text": (
                    "Code: commit `6539207` (merge `ba918a9`), `app/src/engines/structured.py`, "
                    "`app/src/engines/generic_engine.py`, `app/scripts/generate_rm.py`, "
                    "`app/src/prompts/compiler-rm/reward-machine-tagger.system.md`, with tests in "
                    "`tests/test_engines.py`, `tests/test_pipeline_orchestration.py` and `tests/test_prompts.py`. "
                    "Records: `docs/decisions/arm-fm/task-and-rm-identity.md` (reply shape) and "
                    "`docs/decisions/benchmark/thesis-benchmark.md` (pre-freeze prompt log)."
                ),
            },
        ],
    }


def main() -> None:
    verdicts = json.loads((EVIDENCE / "verdicts.json").read_text(encoding="utf-8"))["bundles"]
    datas = {name: load(name) for name in BUNDLES}
    sections = [claim_section(), fix_section(datas["tpl-response-1-goal"])]
    sections += [bundle_section(name, datas[name], verdicts[name]) for name in BUNDLES]
    sections += [rounds_section(datas, verdicts), probe_section(verdicts), evidence_section()]
    page = {
        "title": "Keyed state texts: each state's text now sits on its own state",
        "eyebrow": "state tagger · state embeddings · 3 bundles, 3 rounds · 2026-11-21",
        "subtitle": (
            "Every Reward Machine state carries a short text, and training builds the state embeddings from it. "
            "The state tagger answered with a bare list that the code matched to the states by position, so a "
            "text written for another state passed without an error: on three bundles, 13 of the 37 stored "
            "texts describe another state or the wrong duties. Commit `6539207` sends the tagger each state's "
            "role and keys the reply by state id; a missing, repeated or unknown id is refused. Re-tagged live "
            "three times with deepseek-v4.1-flash, every new text sits on its own state; 2 texts of round 1 add "
            "a claim the machine does not support. A word search over the 379 stored bundles finds 26 hits, 22 "
            "of them false alarms."
        ),
        "sections": sections,
    }
    (ENTRY / "data.json").write_text(
        json.dumps(page, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {ENTRY / 'data.json'}: {len(sections)} sections")


if __name__ == "__main__":
    main()
