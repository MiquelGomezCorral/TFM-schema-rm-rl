"""Build the level benchmark page: score the runs, compile the shown machines, write data.json.

Usage, from the repository root inside RM_RL_env with MONA on PATH (no model call):

    env -C docs/paper/level-benchmark-freeze/check CC_ROOT=$PWD PYTHONPATH=$PWD/app \
        python -W ignore build_page.py

Every run in `records/<level>/` is scored with `chain_score.classify`, the scorer behind
`stats.md`, against the copied cards in `evidence/cards/`. The clauses of each shown run are
compiled with the repository's compiler (MONA, the default reward switches, the level's step
limit), and the script stops if a compiled machine differs from the record's `machine` text.
It writes `graphs/<name>.rm`, `.svg` and `.html` (the code of `render-rm --html`) and
`data.json`; the artifacts skill's `fill.py` turns `data.json` into `index.html`.
"""

import json
import statistics
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import cases
import chain_score
import loopcrit
from flat_tool import compile_dfa

from scripts.render_rm import render_file
from src.arm_fm.environments import gym_step_limit
from src.compiler import serialize_reward_machine
from src.compiler.reward_layer import RewardSwitches, build_reward_machine
from src.utils import ltlf_of

ENTRY = Path(__file__).resolve().parent.parent
LEVELS = ("none", "low", "medium", "high", "max")
ORDER = [*cases.CASES, *cases.UNSEEN, *cases.EXTRA]
GROUPS = {
    "W": "Cases that were once wrong (W)",
    "C": "Controls (C, CX)",
    "U": "Unseen cases (U)",
    "O": "Ordered tasks (O)",
    "G": "Guard cards (G)",
    "S": "Soft last step (S)",
}
GRAPH_HEIGHT = 520
DRAW_LIMIT = 500  # transitions
LTLF_TITLE = "Task, clauses, LTLf and RM text"

# The wrong runs at `none`, grouped by mistake: one reader's grouping (this entry's), checked
# below to cover every run the scorer does not call right. The first run of each is drawn.
NONE_KINDS = [
    {
        "title": "A soft ban read as an order",
        "text": '"Try not to drop the key while the door is still closed" became soft '
        "`Precedence(door_open, key_lost)`, no drop before the door has opened, where the card "
        'has soft `Absence(key_lost)`. Since the until prompt fix only "until `a`" is an order; '
        'a "while ... still closed" condition the event already holds folds into `Absence` '
        "(`until-prompt-fix/`).",
        "runs": [
            "W4b-r3",
            "O1-r2",
            "O1-r3",
            "U5-r1",
            "U5-r3",
            "U6-r2",
            "W5a-r2",
            "W5a-r3",
            "W6-r1",
            "W6-r3",
        ],
    },
    {
        "title": "A stated order dropped",
        "text": 'The task says "then", "first" or "after that", and the answer has no clause for '
        'that order: two "must happen" rules where the card has an order (G1, O4), or the step '
        "after a rule left without its order (G9, G12, S4).",
        "runs": [
            "G1-r2",
            "G7-r1",
            "G9-r1",
            "G9-r2",
            "G9-r3",
            "G12-r1",
            "G12-r2",
            "G12-r3",
            "O4-r2",
            "S4-r1",
            "S4-r2",
            "S4-r3",
        ],
    },
    {
        "title": "An order the task does not state",
        "text": "Two sentences with no order word became an order where the card has two "
        '"must happen" rules. G4 orders the key count before the door, which the user\'s '
        "2026-11-21 ruling says a count does not take.",
        "runs": ["G2-r1", "G2-r2", "G3-r1", "G3-r2", "G4-r2"],
    },
    {
        "title": "An order on the wrong step",
        "text": '"First move the ball off the door, then take the key" became ball before door '
        "(`Precedence(blocker_moved, door_open)`) instead of ball before key "
        "(`Precedence(blocker_moved, has_door_key)`).",
        "runs": ["O8-r2", "O8-r1"],
    },
    {
        "title": '"Never both" read as a plain ban',
        "text": '"Never both drop the key while the door is still closed and open the door" '
        "became `Absence(key_lost)`; the card has `NotCoExistence(key_lost, door_open)`.",
        "runs": ["G11-r3"],
    },
    {
        "title": "An extra step in a chain of promises",
        "text": 'In the shop, "take their order, get food from the pantry, prepare it" became '
        "two promises (order, then food in hand; food in hand, then prepared) where the card "
        "has one (order, then prepared).",
        "runs": ["W4a-r3"],
    },
    {
        "title": "Accepted by the scorer, not counted right (form A)",
        "text": 'The set passes the card only with a "must happen" rule on an earlier step of '
        "the chain. The scorer calls this form A and counts it apart from right and wrong. "
        "O2-r3 also repeats one clause.",
        "runs": ["O3-r1", "O2-r3"],
    },
]
# The critic's reason, in short, for the six wrong runs at low and medium (full text on the page).
CRITIC_SHORT = {
    "G11": 'Read `key_lost` as already holding "while the door is still closed", asked for a '
    'plain ban, and read "and open the door" as a command, asking for it as a hard goal.',
    "G4": "Asked for the order key before door, as a stated order; the user's 2026-11-21 ruling "
    "says a count takes no order.",
    "G9": "Called `Response(has_key, at_goal)` an added requirement: no sentence says the goal "
    "must come after holding the key.",
}


@dataclass(frozen=True)
class Run:
    """One scored run record."""

    level: str
    name: str  # <case>-r<k>
    case: str
    record: dict
    verdict: str  # right / accepted / wrong
    first: str | None  # the first candidate's verdict, None when no candidate was judged


def load_runs() -> dict[str, list[Run]]:
    runs = {}
    for level in LEVELS:
        runs[level] = []
        for path in sorted((ENTRY / "records" / level).glob("*-r[0-9].json")):
            case = path.stem.rsplit("-r", 1)[0]
            record = json.loads(path.read_text())
            judged = list(loopcrit.verdicts(record))
            first = verdict_of(case, judged[0][0]) if judged else None
            verdict = chain_score.classify(case, record)[0]
            runs[level].append(Run(level, path.stem, case, record, verdict, first))
    return runs


def verdict_of(case: str, clauses: list[dict]) -> str:
    stored = [[c["pattern"], c["propositions"], c["priority"]] for c in clauses]
    return chain_score.classify(case, {"status": "accepted", "clauses": stored})[0]


def clause_text(clause) -> str:
    pattern, names, priority = clause
    return f"{priority} {pattern}({', '.join(names)})"


def short(clause) -> str:
    pattern, names, priority = clause
    return f"{pattern}({', '.join(names)}){'' if priority == 'hard' else ' soft'}"


def set_text(clauses) -> str:
    return ", ".join(f"`{short(c)}`" for c in clauses)


def ltlf_lines(clauses) -> str:
    return "\n".join(f"{clause_text(c)}: {ltlf_of(c[0], list(c[1]))}" for c in clauses)


def as_clauses(record: dict) -> list[tuple]:
    return [(p, tuple(n), priority) for p, n, priority in record["clauses"]]


def compile_machine(clauses: list[tuple], card) -> str:
    """The machine the pipeline builds from these clauses, at the defaults and the level's limit."""
    dfas = [compile_dfa(ltlf_of(pattern, list(names))) for pattern, names, _ in clauses]
    soft = [priority == "soft" for _, _, priority in clauses]
    limit = gym_step_limit(card.env["gym_id"], **card.env.get("env_kwargs", {}))
    built = build_reward_machine(dfas, soft, RewardSwitches(step_limit=limit))
    return serialize_reward_machine(built.reward_machine)


def transitions(text: str) -> int:
    lines = text.splitlines()
    return lines.index("REWARD_FUNCTION:") - lines.index("TRANSITION_FUNCTION:") - 1


def machine_facts(text: str) -> str:
    field = {
        line.split(":")[0]: line.split(":", 1)[1].strip()
        for line in text.splitlines()
        if ": " in line
    }
    states = field["STATES"].count(",") + 1
    final = field.get("FINAL_STATES") or "none"
    rejecting = field.get("REJECTING_STATES") or "none"
    return (
        f"{states} states, {transitions(text)} transitions · final {final}, rejecting {rejecting}"
    )


def draw(name: str, run: Run) -> str:
    """Compile the run's clauses, check the text against the record and draw it; returns the text."""
    card = cases.card_of(run.case)
    text = compile_machine(as_clauses(run.record), card)
    if text != run.record["machine"]:
        raise SystemExit(f"{run.level}/{run.name}: compiled machine differs from the record")
    rm_path = ENTRY / "graphs" / f"{name}.rm"
    drawn = rm_path.with_suffix(".html").exists() and rm_path.read_text() == text
    rm_path.write_text(text)
    # Layout of a machine past DRAW_LIMIT transitions runs for minutes and its page passes 1 MB.
    if not drawn and transitions(text) <= DRAW_LIMIT:
        render_file(rm_path, rm_path.with_suffix(".svg"), html=True)
    return text


def run_code(name: str, run: Run, text: str) -> str:
    """The fold-out text: task, the run's clauses with LTLf, the card's when they differ, RM text."""
    card = cases.card_of(run.case)
    clauses = as_clauses(run.record)
    code = f"# Task (NL)\n{run.record['task']}\n\n# Clauses and LTLf (run {run.name})\n"
    code += ltlf_lines(clauses) + "\n\n"
    if sorted(clauses) != sorted(card.expect):
        code += f"# Card answer and LTLf (card {card.id})\n{ltlf_lines(card.expect)}\n\n"
    if transitions(text) > DRAW_LIMIT:
        return code + f"# RM text\nIn graphs/{name}.rm: {machine_facts(text)}, too large to draw."
    return code + f"# RM text (graphs/{name}.rm)\n{text}"


def graph_item(name: str, run: Run, verdict_line: str) -> dict:
    card = cases.card_of(run.case)
    text = draw(name, run)
    code = run_code(name, run, text)
    return {
        "src": f"graphs/{name}.html",
        "height": GRAPH_HEIGHT,
        "alt": f"Reward Machine {name}",
        "caption": f"**`{name}`** · {card.env['gym_id']} · {machine_facts(text)}\n"
        f"Task: *{run.record['task']}* {verdict_line}",
        "details": {
            "title": LTLF_TITLE,
            "text": f"Run record `records/{run.level}/{run.name}.json` (field `machine`), compiled "
            "again here from its clauses: the same text.",
            "code": code,
        },
    }


def tone(right: int, runs: int) -> str:
    if right == runs:
        return "ok"
    return "warn" if right >= 0.95 * runs else "bad"


def stats_calls() -> dict[str, int]:
    """Model calls per level from `stats.md` (the call logs), to check the records' counts."""
    calls = {}
    for line in (ENTRY / "stats.md").read_text().splitlines()[2:]:
        cells = [c.strip() for c in line.strip("|").split("|")]
        gen, critic = cells[9].split("+")
        calls[cells[0]] = int(gen) + int(critic)
    return calls


def level_row(level: str, runs: list[Run], logged: int) -> list:
    n = Counter(r.verdict for r in runs)
    first = sum(r.first == "right" for r in runs)
    walls = [r.record["wall_s"] or 0 for r in runs]
    calls = sum(r.record["calls"] or 0 for r in runs)
    if calls != logged:
        raise SystemExit(f"{level}: records count {calls} calls, the call logs {logged}")
    return [
        f"`{level}`",
        str(len(runs)),
        {
            "text": f"{n['right']} ({100 * n['right'] / len(runs):.0f}%)",
            "tone": tone(n["right"], len(runs)),
        },
        str(n["wrong"]),
        str(n["accepted"]),
        f"{first} of {len(runs)}",
        f"{statistics.median(walls):.0f} s",
        f"{calls:,}",
        f"{sum(walls):,.0f} s",
    ]


def levels_section(runs: dict[str, list[Run]]) -> dict:
    logged = stats_calls()
    rows = [level_row(level, runs[level], logged[level]) for level in LEVELS]
    return {
        "id": "levels",
        "title": "Right machines per thinking level",
        "intro": "46 task cases, 3 runs each, at every thinking level of both models: 138 runs a "
        "level, 690 in all. A run is right when its final clause set is the card's answer or one "
        "of the answers the card also accepts (the next section says exactly how).",
        "blocks": [
            {
                "type": "table",
                "columns": [
                    "thinking",
                    "runs",
                    "right",
                    "wrong",
                    "form A",
                    "first answer right",
                    "median time per run",
                    "model calls",
                    "total time",
                ],
                "rows": rows,
            },
            {
                "type": "list",
                "items": [
                    "**Form A**: the scorer accepts the set but does not count it right (a "
                    '"must happen" rule on an earlier step of an ordered task).',
                    "**First answer right**: the generator's first answer, before any critic "
                    "feedback, scored the same way.",
                    "**Time**: from the start of generation to the accepted machine, per run; 8 "
                    "runs went at once, beside 12 to 23 RL trainings, so it is not a clean speed "
                    "measure. **Model calls**: generator plus critic requests, counted in the run "
                    "records; they equal the call logs' counts in `stats.md`.",
                ],
            },
        ],
    }


def case_rows(runs: dict[str, list[Run]]) -> list[list]:
    rows = []
    for case in ORDER:
        per_level = {level: [r for r in runs[level] if r.case == case] for level in LEVELS}
        if not per_level["max"]:
            continue
        card = cases.card_of(case)
        answer = set_text(card.expect)
        if card.also_ok:
            answer += f" (+{len(card.also_ok)} other accepted)"
        cells = []
        for level in LEVELS:
            right = sum(r.verdict == "right" for r in per_level[level])
            cells.append({"text": f"{right}/{len(per_level[level])}", "tone": tone(right, 3)})
        rows.append([case, per_level["max"][0].record["task"], answer, *cells])
    return rows


def cases_section(runs: dict[str, list[Run]]) -> dict:
    return {
        "id": "cases",
        "title": "Every case: task, card answer and right runs per level",
        "intro": "The card answer is the card's `expect` set; the scorer also takes the answers "
        "the card lists as `also_ok`. A soft clause says *soft*; the rest are hard.",
        "blocks": [
            {
                "type": "table",
                "columns": ["case", "task", "card answer", *LEVELS],
                "rows": case_rows(runs),
            }
        ],
    }


def same_machines(level_runs: list[Run]) -> str:
    texts = {r.record["machine"] for r in level_runs}
    return "the 3 runs gave the same machine text" if len(texts) == 1 else f"{len(texts)} texts"


def per_level_counts(runs: dict[str, list[Run]], case: str) -> str:
    counts = []
    for level in LEVELS:
        mine = [r for r in runs[level] if r.case == case]
        counts.append(f"{level} {sum(r.verdict == 'right' for r in mine)}/{len(mine)}")
    return ", ".join(counts)


def machines_section(runs: dict[str, list[Run]]) -> dict:
    groups = {}
    for case in ORDER:
        mine = [r for r in runs["max"] if r.case == case]
        if not mine:
            continue
        line = f"Right per level: {per_level_counts(runs, case)}. At max {same_machines(mine)}."
        item = graph_item(f"{case.lower()}-max", mine[0], line)
        groups.setdefault(GROUPS[case.rstrip("0123456789ab")[0]], []).append(item)
    return {
        "id": "machines",
        "title": "The machine of every case",
        "intro": "One Reward Machine per case: the clauses of the case's first run at `max` (all "
        "right), compiled again with the frozen compiler and drawn with `render-rm --html`. Each "
        "compiled text equals the record's `machine`. Drag a state, click an edge for its cases, "
        "Ctrl + scroll to zoom; the fold-out under each graph has the task, the clauses with "
        "their LTLf and the RM text.",
        "blocks": [
            {
                "type": "gallery",
                "width": 490,
                "groups": [{"title": title, "items": items} for title, items in groups.items()],
            }
        ],
    }


def critic_rejections(run: Run) -> str:
    for item in run.record["trace"]:
        value = item["value"]
        verdict = json.loads(value) if isinstance(value, str) else value
        if item["step"] == "critic" and not verdict["accepted"]:
            return verdict["feedback"]
    return ""


def first_and_final(run: Run) -> tuple[str, str]:
    proposals = [json.loads(i["value"]) for i in run.record["trace"] if i["step"] == "generate"]
    first = [(c["pattern"], tuple(c["propositions"]), c["priority"]) for c in proposals[0]]
    return set_text(first), set_text(as_clauses(run.record))


def low_medium_section(runs: dict[str, list[Run]]) -> dict:
    wrong = [r for level in ("low", "medium") for r in runs[level] if r.verdict != "right"]
    if any(r.first != "right" for r in wrong):
        raise SystemExit("a low or medium wrong run had a wrong first answer")
    rows, feedback, drawn = [], [], {}
    for run in wrong:
        first, final = first_and_final(run)
        rows.append([f"{run.level} {run.name}", first, CRITIC_SHORT[run.case], final])
        feedback.append({"title": f"{run.level} {run.name}", "text": critic_rejections(run)})
        drawn.setdefault(run.record["machine"], []).append(run)
    items = []
    for same in drawn.values():
        names = ", ".join(f"{r.level} {r.name}" for r in same)
        line = f"Wrong, accepted on the second try: {names}."
        items.append(
            graph_item(f"{same[0].case.lower()}-{same[0].level}-{same[0].name[-2:]}", same[0], line)
        )
    return {
        "id": "low-medium",
        "title": f"The {len(wrong)} wrong runs at low and medium",
        "intro": "Every wrong run at `low` and `medium` started with a right first answer. The "
        "critic rejected it, the generator changed it as asked, and the critic accepted the new, "
        "wrong set. Four of the six are G9, at both levels. One more run, low W5a-r1, also had "
        "its right first answer rejected; it was right again on the third answer.",
        "blocks": [
            {
                "type": "table",
                "columns": [
                    "run",
                    "first answer (right)",
                    "why the critic rejected it",
                    "final answer (wrong)",
                ],
                "rows": rows,
            },
            {
                "type": "callout",
                "tone": "info",
                "title": "G9: a card reading the critic does not share",
                "text": 'G9 says "Whenever you are holding the key, the door must be open at that '
                'moment or opened afterwards. Then reach the goal." The card reads "Then" as an '
                "order from holding the key to the goal, `Response(has_key, at_goal)`; the critic "
                "reads it as after the door only. It is close to the open question in "
                '`stated-order-rule/`, whether "Then" after an if-rule orders the rule\'s steps.',
            },
            {
                "type": "details",
                "heading": "The critic's full reply on the right first answer",
                "items": feedback,
            },
            {"type": "gallery", "width": 490, "items": items},
        ],
    }


def diff_text(run: Run) -> str:
    given = Counter(as_clauses(run.record))
    expect = Counter(cases.card_of(run.case).expect)
    parts = []
    for label, clauses in (("added", given - expect), ("missing", expect - given)):
        for c in clauses.elements():
            parts.append(f"{label} `{short(c)}`: `{ltlf_of(c[0], list(c[1]))}`")
    return "; ".join(parts)


def kind_blocks(kind: dict, runs_by_name: dict[str, Run]) -> list[dict]:
    example, *rest = (runs_by_name[name] for name in kind["runs"])
    text = kind["text"]
    if rest:
        listed = "\n".join(f"- `{r.name}`: {diff_text(r)}" for r in rest)
        text += f"\n\nThe other {len(rest)}, against the card answer:\n{listed}"
    name = f"{example.case.lower()}-none-{example.name[-2:]}"
    line = f"Not right at none, against the card answer: {diff_text(example)}."
    blocks = [{"type": "text", "heading": f"{kind['title']} ({len(kind['runs'])})", "text": text}]
    machine = draw(name, example)
    if transitions(machine) <= DRAW_LIMIT:
        return [
            *blocks,
            {"type": "gallery", "width": 490, "items": [graph_item(name, example, line)]},
        ]
    blocks[0]["text"] += (
        f"\n\n`{example.name}`: {line} Its machine is not drawn: {machine_facts(machine)}."
    )
    return [*blocks, {"type": "code", "text": run_code(name, example, machine)}]


def none_section(runs: dict[str, list[Run]]) -> dict:
    not_right = {r.name: r for r in runs["none"] if r.verdict != "right"}
    grouped = [name for kind in NONE_KINDS for name in kind["runs"]]
    if sorted(grouped) != sorted(not_right):
        raise SystemExit("the mistake groups do not cover the not-right runs at none exactly")
    summary = [
        [kind["title"], str(len(kind["runs"])), ", ".join(kind["runs"])] for kind in NONE_KINDS
    ]
    blocks = [{"type": "table", "columns": ["mistake", "runs", "which"], "rows": summary}]
    for kind in NONE_KINDS:
        blocks.extend(kind_blocks(kind, not_right))
    return {
        "id": "none",
        "title": f"The {len(not_right)} runs not right at none, by mistake",
        "intro": "Without thinking the critic caught 19 of the 43 first answers that were not "
        "right, and the generator fixed some of them; these are the ones that stayed. Each group "
        "shows one run in full (task, LTLf it gave against the card's, its machine) and lists the "
        "others by the clauses they added or missed. The grouping is this entry's reading.",
        "blocks": blocks,
    }


def main() -> None:
    runs = load_runs()
    refused = [json.loads(p.read_text()) for p in sorted(ENTRY.glob("records/*/*.json.429"))]
    print(f"{len(refused)} rate-limited records kept, {sum(r['calls'] for r in refused)} requests")
    # The prose sections live in page_text.json; the sections with numbers are built here.
    prose = json.loads((ENTRY / "check" / "page_text.json").read_text())
    sections = [
        levels_section(runs),
        *prose["after_levels"],
        cases_section(runs),
        machines_section(runs),
        low_medium_section(runs),
        none_section(runs),
        *prose["after"],
    ]
    data = {**prose["head"], "sections": sections}
    (ENTRY / "data.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote data.json, {len(list((ENTRY / 'graphs').glob('*.rm')))} machines in graphs/")


if __name__ == "__main__":
    main()
