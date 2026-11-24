"""Build ``data.json`` and the share plot of the clause-choice entry from its evidence copies.

Every number comes from ``evidence/tables.md``, the full output of ``check/clause_choice.py``; the
95% Wilson intervals are computed again here and checked against the printed ones. The per-card
fold-outs take the task, the answers in LTLf, the picks and the chosen machines from the same file
and ``evidence/rm/``. The learning section takes its rows and counts from
``evidence/learning-by-level.json`` (``check/learning_by_level.py``).

Usage, from the repository root inside RM_RL_env:
    PYTHONPATH=app python -W ignore docs/paper/clause-choice/check/build_page.py
"""

import io
import json
import math
import re
from collections import Counter
from pathlib import Path

import matplotlib as mpl
from clause_choice import PROMPT_FORM
from matplotlib.figure import Figure
from matplotlib.ticker import PercentFormatter

ENTRY = Path(__file__).resolve().parents[1]
TABLES = (ENTRY / "evidence/tables.md").read_text()
LEARNING = json.loads((ENTRY / "evidence/learning-by-level.json").read_text())
# Static SVGs, not a Plotly file: plotly.js embedded is 4.8 MB, over the repo's 1 MB file limit.
PLOT = ENTRY / "plots/choice-shares"
Z95 = 1.959964
COUNT = re.compile(r"(\d+)/(\d+) = \d+% \[(\d+)%, (\d+)%\]")

# == Palette of the artifact pages (figures skill, plotly/example.py) ==
PALETTE = {
    "light": {
        "card": "#ffffff",
        "text": "#1d1d1f",
        "line": "#5b5b66",
        "series": [
            "#2f5bd3",
            "#d96f00",
            "#1f7a4d",
            "#b3261e",
            "#b03a9a",
            "#1b7f8c",
            "#6b52c0",
            "#8a6d3b",
        ],
    },
    "dark": {
        "card": "#1d1d21",
        "text": "#ececf0",
        "line": "#b9b9c4",
        "series": [
            "#8fb0ff",
            "#ffa24d",
            "#5fd394",
            "#ff8a80",
            "#e58ad2",
            "#5ccfdc",
            "#b9a2ff",
            "#d8b56b",
        ],
    },
}
AGREE_ROWS = (
    ("Level case, 3 runs", "levels, one case at one level (3 runs)"),
    ("Level case, low to max", "levels, one case over low to max (12 runs)"),
    ("FARM wordings, listed answers", "FARM, one card's wordings (answers listed before)"),
    ("FARM wordings, all cards", "FARM, one card's wordings (all cards)"),
)
FORM_ROWS = (
    ("FARM final run", "FARM final run"),
    ("Levels: none", "levels: none"),
    ("Levels: low to max", "levels: low to max"),
)
EXPECT_ROWS = (
    ("Levels, all", "levels: all"),
    ("FARM, listed answers", "FARM final run, answers listed before it"),
    ("FARM, all", "FARM final run, all"),
)


# ======================================================================================
#                                   READ THE TABLES
# ======================================================================================
def wilson(successes: int, trials: int) -> tuple[float, float]:
    """95% Wilson score interval of a proportion."""
    share = successes / trials
    scale = 1 + Z95**2 / trials
    center = (share + Z95**2 / (2 * trials)) / scale
    half = Z95 / scale * math.sqrt(share * (1 - share) / trials + Z95**2 / (4 * trials**2))
    return max(0.0, center - half), min(1.0, center + half)


def count(cell: str) -> tuple[int, int]:
    """The k/n of a printed 'k/n = p% [lo%, hi%]' cell, after checking its interval again."""
    k, n, low, high = map(int, COUNT.search(cell).groups())
    assert [round(100 * bound) for bound in wilson(k, n)] == [low, high], cell
    return k, n


def section(title: str) -> str:
    return TABLES.split(f"## {title}\n", 1)[1].split("\n## ", 1)[0]


def table_rows(text: str) -> list[list[str]]:
    """Every markdown table row in ``text`` (header and separator included) as cells."""
    return [
        [cell.strip() for cell in line.strip("|").split("|")]
        for line in text.splitlines()
        if line.startswith("|")
    ]


def tables(text: str) -> list[dict]:
    """The markdown tables in ``text`` as page table blocks."""
    blocks, current = [], []
    for line in [*text.splitlines(), ""]:
        if line.startswith("|"):
            current.append(line)
        elif current:
            rows = table_rows("\n".join(current))
            blocks.append({"type": "table", "columns": rows[0], "rows": rows[2:]})
            current = []
    return blocks


def summary_numbers() -> dict:
    expect = {
        row[0]: (*count(row[4]), float(row[5].rstrip("%")) / 100)
        for row in table_rows(section("Expect share among right answers"))[2:]
    }
    form = {
        row[0]: (count(row[1]), count(row[2]))
        for row in table_rows(section("Ordered tasks: the prompt's form"))[2:]
    }
    agree = {}
    for line in section("Do repeated runs agree?").splitlines():
        found = re.match(
            r"- (.+?): (.+?) groups agree; a uniform pick would make (\d+)% agree", line
        )
        if found:
            agree[found[1]] = (*count(found[2]), int(found[3]) / 100)
    return {"expect": expect, "form": form, "agree": agree}


# ======================================================================================
#                                        PLOT
# ======================================================================================
def bar(k: int, n: int) -> dict:
    """Share and Wilson error lengths; max(0, ...) absorbs a 1e-16 float overshoot at 0% or 100%."""
    low, high = wilson(k, n)
    return {"x": k / n, "minus": max(0.0, k / n - low), "plus": max(0.0, high - k / n)}


def draw(numbers: dict, theme: str) -> Figure:
    """Three panels of shares with Wilson intervals, chance as diamonds, in one page theme."""
    agree, form, expect = numbers["agree"], numbers["form"], numbers["expect"]
    agree_labels = [f"{label} ({agree[key][0]}/{agree[key][1]})" for label, key in AGREE_ROWS]
    form_labels = [
        f"{label} ({form[key][0][0]}/{form[key][0][1]}, {form[key][1][0]}/{form[key][1][1]})"
        for label, key in FORM_ROWS
    ]
    expect_labels = [f"{label} ({expect[key][0]}/{expect[key][1]})" for label, key in EXPECT_ROWS]
    panels = (  # title, row labels, bar groups (counts, palette index, legend), chance shares
        (
            "Same answer across runs",
            agree_labels,
            [([agree[key][:2] for _, key in AGREE_ROWS], 0, "runs agree")],
            [agree[key][2] for _, key in AGREE_ROWS],
        ),
        (
            "Ordered tasks: form vs expect",
            form_labels,
            [
                ([form[key][0] for _, key in FORM_ROWS], 0, "the prompt's form"),
                ([form[key][1] for _, key in FORM_ROWS], 2, "expect"),
            ],
            None,
        ),
        (
            "Right answers that are expect",
            expect_labels,
            [([expect[key][:2] for _, key in EXPECT_ROWS], 2, "expect")],
            [expect[key][2] for _, key in EXPECT_ROWS],
        ),
    )
    colors = PALETTE[theme]
    fig = Figure(figsize=(5.2, 7.4), layout="constrained")  # narrow: labels stay legible on a phone
    axes = fig.subplots(3, 1, sharex=True, height_ratios=[4, 3.4, 3])
    for ax, (title, labels, groups, chance) in zip(axes, panels, strict=True):
        width = 0.8 / len(groups)
        for g, (counts, index, legend) in enumerate(groups):
            points = [bar(k, n) for k, n in counts]
            offset = (g - (len(groups) - 1) / 2) * width
            ax.barh(
                [i + offset for i in range(len(points))],
                [p["x"] for p in points],
                height=width * 0.95,
                color=colors["series"][index],
                label=legend,
                xerr=[[p["minus"] for p in points], [p["plus"] for p in points]],
                error_kw={"ecolor": colors["text"], "capsize": 2.5, "elinewidth": 1},
            )
        if chance:
            ax.scatter(
                chance,
                range(len(chance)),
                marker="D",
                s=28,
                color=colors["series"][1],
                zorder=3,
                label="a uniform pick (chance)",
            )
        ax.set_yticks(range(len(labels)), labels)
        ax.invert_yaxis()
        ax.set_title(title, loc="left", fontsize=10)
        ax.set_xlim(0, 1.02)
        ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
        ax.grid(axis="x", color=colors["line"], alpha=0.25)
        ax.set_axisbelow(True)
        ax.set_facecolor("none")
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    axes[2].set_xlabel("Share, with 95% Wilson interval")
    legend = {}  # label: handle, first one wins; blue = runs agree or the prompt's form
    for ax in axes:
        for handle, label in zip(*ax.get_legend_handles_labels(), strict=True):
            legend.setdefault(label, handle)
    names = {"runs agree": "runs agree / the prompt's form"}
    order = ("runs agree", "expect", "a uniform pick (chance)")
    fig.legend(
        [legend[label] for label in order],
        [names.get(label, label) for label in order],
        loc="outside upper left",
        ncols=2,
        frameon=False,
    )
    return fig


def save_figures(numbers: dict) -> None:
    """Write the light and the dark SVG; the caption is a claim, so assert it first."""
    agree, form, expect = numbers["agree"], numbers["form"], numbers["expect"]
    level_k, level_n, _ = agree["levels, one case at one level (3 runs)"]
    assert level_k / level_n > 0.9, agree
    assert form["levels: low to max"][0][0] == form["levels: low to max"][0][1], form
    k, n, _ = expect["levels: all"]
    assert wilson(k, n)[0] < 0.5 < wilson(k, n)[1], expect["levels: all"]
    PLOT.parent.mkdir(exist_ok=True)
    for theme, suffix in (("light", ""), ("dark", "-dark")):
        colors = PALETTE[theme]
        style = {
            "svg.fonttype": "none",  # real text: small files, the page's font
            "font.family": "sans-serif",
            "font.size": 9.5,
            "text.color": colors["text"],
            "axes.edgecolor": colors["line"],
            "axes.labelcolor": colors["text"],
            "xtick.color": colors["text"],
            "ytick.color": colors["text"],
        }
        svg = io.StringIO()
        with mpl.rc_context(style):
            draw(numbers, theme).savefig(
                svg, format="svg", transparent=True, metadata={"Date": None}
            )
        # matplotlib ends path lines with a space; the repo's trailing-whitespace hook would edit it
        lines = svg.getvalue().splitlines()
        Path(f"{PLOT}{suffix}.svg").write_text("\n".join(line.rstrip() for line in lines) + "\n")


# ======================================================================================
#                                      PER CARD
# ======================================================================================
def card_item(text: str) -> dict:
    header, body = text.split("\n", 1)
    key = header.strip().strip("`")
    task = re.search(r'^Task: "(.*)"$', body, re.MULTILINE)[1]
    answers, machines = [], []
    for found in re.finditer(r"^- (\w) = ([^:]+): (.*)\. RM: `([^`]+)`$", body, re.MULTILINE):
        letter, name, clauses, rm = found.groups()
        chosen = rm.endswith(".txt")
        answers.append([letter, name, clauses, "chosen" if chosen else "never chosen"])
        if chosen:
            stem = Path(rm).stem
            machines.append(
                {
                    "src": f"graphs/{stem}.html",
                    "height": 380,
                    "caption": f"{letter} = {name.split(' (')[0]}: the machine of the run that wrote it.",
                    "details": {
                        "title": "RM text",
                        "code": (ENTRY / "evidence/rm" / f"{stem}.txt").read_text(),
                    },
                }
            )
    picks = body.split("RM: `", 1)[1]
    letters = sorted(
        {
            row[2]
            for block in tables(picks)
            if block["columns"][0] == "FARM bundle"
            for row in block["rows"]
        }
    )
    return {
        "title": key,
        "preview": f"FARM {'/'.join(letters)}" if letters else "levels only",
        "blocks": [
            {"type": "text", "text": f"**Task:** {task}"},
            {
                "type": "table",
                "heading": "The card's answers, in LTLf",
                "columns": ["", "Answer", "Clauses (LTLf)", "Machine"],
                "rows": answers,
            },
            *tables(picks),
            {"type": "gallery", "width": 490, "items": machines},
        ],
    }


def card_items() -> tuple[list[dict], list[dict]]:
    ordered, wording = [], []
    for text in section("Per card").split("\n### ")[1:]:
        item = card_item(text)
        (ordered if item["title"].split("/")[1] in PROMPT_FORM else wording).append(item)
    return ordered, wording


# ======================================================================================
#                                  LEARNING BY LEVEL
# ======================================================================================
def learning_blocks() -> list[dict]:
    """The learning table, its two splits and the caveats, from ``evidence/learning-by-level.json``."""
    rows, counts = LEARNING["rows"], LEARNING["summary"]
    blocked, other = counts["by_level"]["in"], counts["by_level"]["out"]
    assert blocked[0] == 0 and other[1] == 0, counts["by_level"]  # the text says none and all
    table = [
        [
            f"`{row['card']}`",
            row["level"],
            row["letter"] + (" (added after)" if row["added_after"] else ""),
            ", ".join(f"{value:.2f}" for value in row["judged_success"])
            + (" (soft only)" if row["soft_only"] else ""),
            {
                "text": "learned" if row["learned"] else "not learned",
                "tone": "ok" if row["learned"] else "bad",
            },
            row["arm_fm"],
            "Ordered cards" if row["card"].split("/")[1] in PROMPT_FORM else "Wording cards",
        ]
        for row in sorted(rows, key=lambda row: (row["blocked"], row["card"]))
    ]
    without = counts["by_level_without_soft_only"]
    arms = counts["not_learned_other_arms"]

    def commits(learned: bool) -> str:
        found = Counter(
            head for row in rows if row["learned"] == learned for head in row["trained_on"]
        )
        return ", ".join(f"`{head}` ({n})" for head, n in sorted(found.items()))

    return [
        {
            "type": "table",
            "columns": [
                "Card",
                "Level",
                "Answer",
                "Judged success per seed",
                "FARM",
                "ARM-FM",
                "Task, LTLf, RM in",
            ],
            "rows": table,
        },
        {
            "type": "text",
            "text": f"**By level.** On other levels {other[0]} of {sum(other)} rows learned; on BlockedUnlockPickup "
            f"{blocked[0]} of {sum(blocked)} did (Fisher's exact p = {counts['by_level']['p']:.3f}). "
            f"**By answer.** {counts['later_listed_learned']} of the {counts['later_listed']} rows whose RM matched a "
            f"later-listed answer learned, {counts['first_listed_learned']} of the "
            f"{counts['trained_rows'] - counts['later_listed']} that matched the first-listed one "
            f"(p = {counts['by_answer']['p']:.2f}): no pattern.",
        },
        {
            "type": "callout",
            "tone": "warn",
            "title": "One learned row rests on the idle agent",
            "text": f"`{counts['soft_only_learned_rows'][0]}` (soft not-both, no goal) has only soft rules, so its "
            "verdict compares the agents' soft-rule breaks with an idle plan's instead of a goal "
            "(`docs/paper/soft-breaks-vs-idle/`). Without it the split is "
            f"{without['out'][0]} of {sum(without['out'])} against {without['in'][0]} of "
            f"{sum(without['in'])}, p = {without['p']:.3f}.",
        },
        {
            "type": "callout",
            "tone": "warn",
            "title": "The study is not independent",
            "text": f"{counts['cards_with_added_answer']} of the {counts['card_entries']} cards "
            f"({counts['trained_cards_with_added_answer']} of them trained) got an accepted answer only after their "
            f"RMs were read (see Gaps); {counts['rows_matching_added_answer']} of the {counts['trained_rows']} rows "
            "match one of those answers (marked in the table).",
        },
        {
            "type": "callout",
            "tone": "warn",
            "title": f"Only {counts['trained_rows']} of the {counts['trained_rows'] + counts['trained_rows_outside']} "
            "trained rows",
            "text": f"The other {counts['trained_rows_outside']} trained rows are outside the study: their cards list "
            "one answer. The statement holds for these rows only.",
        },
        {
            "type": "callout",
            "tone": "info",
            "title": "A pattern over nine rows, not a cause",
            "text": f"Across all 60 rows FARM learned {counts['blocked_level_farm_rows']['learned']} of "
            f"{sum(counts['blocked_level_farm_rows'].values())} on BlockedUnlockPickup, so the level does not block "
            f"learning by itself. For the {sum(not row['learned'] for row in rows)} not-learned rows, ARM-FM learned "
            f"{arms['arm_fm']} of them and no-RM {arms['no_rm']}. The level is also tangled with the code the runs "
            f"trained on (`config.yaml` `git_head`): the not-learned rows on {commits(False)}, the learned rows on "
            f"{commits(True)}. `app/` is the same at `809dfe3` and `e6c3acb`; `029d82c` differs only in "
            "`app/src/benchmark/plan_check.py` and `traces.py` (`git diff --stat`; the runs' trees were marked "
            "dirty, so this is the commit, not the exact files). The runs do not say which part of the level or "
            "the machine stops FARM there.",
        },
    ]


# ======================================================================================
#                                        PAGE
# ======================================================================================
def build() -> dict:
    numbers = summary_numbers()
    save_figures(numbers)
    ordered, wording = card_items()
    k, n, _ = numbers["expect"]["levels: all"]
    low, high = wilson(k, n)
    agree_k, agree_n, agree_chance = numbers["agree"]["levels, one case at one level (3 runs)"]
    (form_k, form_n), _ = numbers["form"]["FARM final run"]
    (form_low_k, form_low_n), _ = numbers["form"]["levels: low to max"]
    learning = LEARNING["summary"]
    return {
        "eyebrow": "Paper entry · FARM clause choice · 2026-11-22, learning section 2026-11-24",
        "title": "Two right answers: the wording picks, not chance",
        "subtitle": "Some task cards accept more than one set of rules. We looked at which one the generator "
        "writes. Runs of one wording write the same answer, ordered tasks get the form the prompt teaches, and "
        "the card's first-listed answer gets no extra pull. Rewording the task is what moves the pick.",
        "sections": [
            {
                "id": "summary",
                "title": "In short",
                "blocks": [
                    {
                        "type": "list",
                        "items": [
                            f"**Not random.** One wording gives one answer: {agree_k} of {agree_n} three-run "
                            f"groups agree, where a coin flip among the listed answers would make {agree_chance:.0%} "
                            "agree.",
                            f"**No pull toward `expect`.** It wins {k} of {n} right level runs, {k / n:.0%} "
                            f"[{low:.0%}, {high:.0%}], against 50% for a uniform pick.",
                            f"**Ordered tasks get the prompt's form.** The prompt teaches the last step's "
                            f"`Existence` plus the `Precedence`s. That form wins {form_k} of {form_n} final-run "
                            f"bundles and {form_low_k} of {form_low_n} level runs from low to max, whichever side the "
                            "card lists it on.",
                            "**Rewording moves the pick, thinking does not.** On each of the 5 wording cards with "
                            "four wordings, one or more wordings took the other answer: 8 of the 24 wording-card "
                            "bundles, one run each. Low, medium, high and max pick the same on every right run.",
                            "**Pricing barely enters.** The generator never sees rewards. The critic does, and once "
                            "moved a pick partly over reward (`tpl-precedence-soft-1-goal~p2`).",
                            f"**Learning follows the level, not the answer.** Of the {learning['trained_rows']} "
                            "trained rows on these cards, "
                            f"{learning['by_level']['out'][0]} of {sum(learning['by_level']['out'])} learned on "
                            f"other levels and {learning['by_level']['in'][0]} of {sum(learning['by_level']['in'])} "
                            "on BlockedUnlockPickup; the answer the RM matched splits them "
                            f"{learning['later_listed_learned']} of {learning['later_listed']} (later-listed) and "
                            f"{learning['first_listed_learned']} of "
                            f"{learning['trained_rows'] - learning['later_listed']} (first-listed). Three caveats "
                            "below.",
                        ],
                    },
                    {
                        "type": "figure",
                        "src": "plots/choice-shares.svg",
                        "dark": "plots/choice-shares-dark.svg",
                        "alt": "Bars with 95% Wilson intervals: groups of runs that agree, the prompt's "
                        "order form against expect, and the share of expect, with chance as diamonds.",
                        "source": "check/build_page.py",
                        "caption": "Runs of one wording repeat their answer far above chance, the prompt's order "
                        "form wins on ordered tasks, and the share of `expect` stays at chance. Bars: share with its "
                        "95% Wilson interval; diamonds: the share a uniform pick among the card's listed answers "
                        "would give. Made 2026-11-22 from `evidence/tables.md`.",
                    },
                ],
            },
            {
                "id": "measured",
                "title": "What was measured",
                "blocks": [
                    {
                        "type": "list",
                        "items": [
                            "**Two sets, never mixed.** (1) The final-run FARM bundles (freeze `809dfe3`, max "
                            "thinking, generator deepseek-v4.1-flash, critic glm-5.3-flash): 36 bundles of 15 card "
                            "entries that list more than one answer. (2) The thinking-level benchmark at the freeze "
                            "(`docs/paper/level-benchmark-freeze/`): 11 of its 46 cases are such cards, 3 runs at "
                            "each of 5 levels, 165 runs.",
                            "**Matching follows the repo scorer.** `clause_status` "
                            "(`app/src/benchmark/rm_facts.py:133`) decides right or wrong; the script only names "
                            "which answer it accepted: `expect`, then each `also_ok`, then the MONA same-task check. "
                            "All 189 right answers matched exactly. A run the scorer rejects, or a failed run, is X "
                            "(12, all at none or low).",
                            "**The prompt's form is a hand reading** of the generator prompt's order rules "
                            "(`app/src/prompts/compiler-rm/reward-ltlf-creator.system.md:31-36, 41, 62-63`), one "
                            "answer per ordered card (`PROMPT_FORM` in `check/clause_choice.py`).",
                            "**Chance** gives each right answer a uniform pick among the card's listed answers (1/2, "
                            "or 1/3 for `tpl-not-co-existence-1-goal`); the tables add two-sided binomial p values.",
                        ],
                    },
                    {"type": "text", "text": "**Share of `expect` among right answers**"},
                    *tables(section("Expect share among right answers")),
                    {
                        "type": "text",
                        "text": "**Ordered tasks: the prompt's form against `expect`**",
                    },
                    *tables(section("Ordered tasks: the prompt's form")),
                    {
                        "type": "text",
                        "text": "The one miss: S1 at none, run 3, wrote the soft order the card lists as `expect`. "
                        "Cards list the prompt's form as `expect` on 2 ordered cards and as `also_ok` on 7, so the "
                        "`expect` share there only says which side the card author put it on.",
                    },
                    {
                        "type": "text",
                        "text": '**Pricing.** The generator prompt says "Do not output formulas, rewards" '
                        "(`reward-ltlf-creator.system.md:89`). The critic sees the priced machine but is told not "
                        "to judge reward magnitudes (`reward-machine-critic.system.md:17-20`). It switched one pick "
                        "between listed answers, `tpl-precedence-soft-1-goal~p2` from E to A, because the commanded "
                        'move "needs its own Existence" and the soft order alone "gives no reward for moving the '
                        'ball". The data has no price variation to test more.',
                    },
                ],
            },
            {
                "id": "gaps",
                "title": "Gaps",
                "blocks": [
                    {
                        "type": "callout",
                        "tone": "warn",
                        "title": "Six alternatives came from these bundles",
                        "text": "On 2026-11-22 the user accepted the readings of 8 final-run bundles and added six "
                        "new answers to six cards (`docs/paper/wrong-clauses-at-max/`). Those cards entered this set "
                        "because a wording disagreed, so the final run overstates how often wordings split: its "
                        "`expect` share is 24/36 with them and 11/15 without. The level benchmark ran before the "
                        "ruling; only W2a (`tpl-precedence-1-nogoal`) is such a card there, and it never took the "
                        "added answer.",
                    },
                    {
                        "type": "callout",
                        "tone": "warn",
                        "title": "Each reworded bundle ran once",
                        "text": "Whether the 8 alternative wordings repeat their pick is not checked: one run each. "
                        "Three reruns of those 8 wordings at max (24 model calls) would tell the wording from "
                        "chance. The pattern below is a reading of 8 single runs, not a tested rule.",
                    },
                    {
                        "type": "text",
                        "text": '**What the alternative wordings share.** "Try to <do x> before y" got an extra '
                        "soft `F x` on 4 of 4 action wordings (one through the critic); the one stated as a state "
                        '("preferably the ball is out of the way") did not. A "not both" split into two bans '
                        'when the second half reads as its own act ("... and open the door in the same run") or '
                        'when "both" sits on a list of places ("through both the top lane and the side lanes").',
                    },
                    {
                        "type": "text",
                        "text": "The script counts only final clauses. The critic rejected a first answer in 1 of 36 "
                        "bundles and 7 of 165 level runs; none of those 7 switched between two listed answers "
                        "(checked by hand).",
                    },
                ],
            },
            {
                "id": "learning",
                "title": "Learning follows the level, not the answer",
                "intro": "The 9 trained rows of the cards above that list more than one answer (the final run, FARM, "
                "PPO). A row is learned when at least 2 of its seeds pass at 0.8 judged success (the final "
                'results\' rule). E = `expect`, A = `also_ok[0]`; "added after" marks an answer listed only after the '
                "RMs were read. The answer is the one `check/clause_choice.py` matched for the bundle the runs "
                "trained on. Each card's task, its answers in LTLf and the machines the runs wrote are in the "
                "fold-out named in the last column, below.",
                "blocks": learning_blocks(),
            },
            {
                "id": "ordered",
                "title": "Ordered cards: the prompt's form wins",
                "collapsed": True,
                "intro": "E = `expect`, A = `also_ok[0]`, B = `also_ok[1]`, X = wrong or failed. FARM rows are the "
                "final run's bundles (main wording and paraphrases `~p1` to `~p3`); level cells hold one letter per "
                "run. Each chosen answer has its machine below, with its RM text.",
                "blocks": [{"type": "details", "items": ordered}],
            },
            {
                "id": "wording",
                "title": "Wording cards: the wording picks",
                "collapsed": True,
                "intro": 'Cards where both answers are plain readings of the task ("not both", soft orders). The '
                "FARM table shows which wording took which answer.",
                "blocks": [{"type": "details", "items": wording}],
            },
            {
                "id": "files",
                "title": "Files and rerun",
                "collapsed": True,
                "blocks": [
                    {
                        "type": "code",
                        "text": "# from the repository root, inside RM_RL_env (no model call)\n"
                        "# 1. the analysis again (rewrites evidence/; MONA on PATH for the same-task check)\n"
                        "PYTHONPATH=app python -W ignore docs/paper/clause-choice/check/clause_choice.py\n"
                        "# 1b. learning by level (evidence/learning-by-level.json, .md); reads outputs/runs\n"
                        "env PYTHONPATH=app:.git/agent-memory/artifacts/final-results python -W ignore "
                        "docs/paper/clause-choice/check/learning_by_level.py\n"
                        "# 2. the page and its plot from evidence/tables.md, evidence/rm/ and the learning json\n"
                        "PYTHONPATH=app python -W ignore docs/paper/clause-choice/check/build_page.py\n"
                        "python3 <agent-artifacts skill>/scripts/fill.py docs/paper/clause-choice/data.json "
                        "docs/paper/clause-choice/index.html\n"
                        "# 3. a machine graph\n"
                        "PYTHONPATH=app python app/main.py render-rm --rm-file docs/paper/clause-choice/evidence/rm/"
                        "<name>.txt --svg-dir docs/paper/clause-choice/graphs/<name>.svg --html",
                    }
                ],
            },
        ],
    }


if __name__ == "__main__":
    (ENTRY / "data.json").write_text(json.dumps(build(), indent=1) + "\n", encoding="utf-8")
    print("wrote", ENTRY / "data.json")
