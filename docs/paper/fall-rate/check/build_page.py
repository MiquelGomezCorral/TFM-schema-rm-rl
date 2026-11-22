"""Build ``data.json`` and the rate plot of the fall-rate entry from its evidence copies.

Rates come from ``evidence/table.md`` (written by ``check/fall_half_rates.py``), the trained runs of
the earlier fall series from their judge files (``evidence/judge/``), clauses and tasks from the
box-carry cards, and the machines from ``graphs/`` (copies of the committed bundles, checked here).

Usage, from the repository root inside RM_RL_env:
    PYTHONPATH=app python -W ignore docs/paper/fall-rate/check/build_page.py
"""

import io
import json
import math
import re
from pathlib import Path

import matplotlib as mpl
from matplotlib.figure import Figure
from matplotlib.ticker import PercentFormatter

from src.benchmark import load_cards
from src.utils import ltlf_of, pretty_ltlf

ENTRY = Path(__file__).resolve().parents[1]
ROOT = ENTRY.parents[2]
CARDS = ROOT / "experiments/benchmark/box-carry/tasks.json"
BUNDLES = ROOT / "experiments/benchmark/box-carry/bundles"
TEMPLATES_BUNDLE = ROOT / "experiments/benchmark/templates/bundles/farm/tpl-chain-response-1-goal"
# Static SVGs, not a Plotly file: plotly.js embedded is 4.8 MB, over the repo's 1 MB file limit.
PLOT = ENTRY / "plots/pickable-falls"
Z95 = 1.96  # as in fall_half_rates.py, so the recomputed intervals match its table
CELL = re.compile(r"(\d+)/(\d+) = [\d.]+% \[([\d.]+)%, ([\d.]+)%\]")
WORLDS = ("face", "side", "none", "half", "right (rejected)", "templates")
CARD_OF_WORLD = {
    "face": "tpl-chain-response-1-goal-carry",
    "side": "tpl-chain-response-1-goal-carry-backturn",
    "none": "tpl-chain-response-1-goal-carry-noturn",
    "half": "tpl-chain-response-1-goal-carry-half",
}
ARM_NAMES = {"farm": "FARM", "arm-fm": "ARM-FM", "no-rm": "no-RM"}

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
AGENTS = (("solve", "solving plan", 0), ("walk", "walker", 1))  # name, legend, palette index


def wilson(successes: int, trials: int) -> tuple[float, float]:
    """95% Wilson score interval of a proportion."""
    share = successes / trials
    scale = 1 + Z95**2 / trials
    center = (share + Z95**2 / (2 * trials)) / scale
    half = Z95 / scale * math.sqrt(share * (1 - share) / trials + Z95**2 / (4 * trials**2))
    return max(0.0, center - half), min(1.0, center + half)


def interval(successes: int, trials: int) -> str:
    low, high = wilson(successes, trials)
    return f"{successes}/{trials} = {successes / trials:.1%} [{low:.1%}, {high:.1%}]"


# ======================================================================================
#                                        RATES
# ======================================================================================
def count(cell: str) -> tuple[int, int]:
    """``k/n`` of one table cell, after checking its printed interval against Wilson."""
    k, n, low, high = CELL.fullmatch(cell.strip()).groups()
    k, n = int(k), int(n)
    assert [f"{v:.1%}" for v in wilson(k, n)] == [f"{low}%", f"{high}%"], cell
    return k, n


def rates() -> list[dict]:
    rows = []
    for line in (ENTRY / "evidence/table.md").read_text().splitlines()[2:]:
        world, agent, seeds, falls, episodes = (cell.strip() for cell in line.strip("|").split("|"))
        rows.append(
            {
                "world": world,
                "agent": agent,
                "seeds": seeds,
                "falls": count(falls),
                "episodes": count(episodes),
            }
        )
    assert {row["world"] for row in rows} == set(WORLDS), rows
    return rows


def reset(rows: list[dict], world: str, agent: str) -> dict:
    return next(
        r for r in rows if (r["world"], r["agent"], r["seeds"]) == (world, agent, "reset 0-999")
    )


def draw(rows: list[dict], theme: str) -> Figure:
    """Grouped bars with Wilson intervals, per world and agent, in one page theme."""
    colors = PALETTE[theme]
    fig = Figure(figsize=(4.8, 6.2), layout="constrained")  # narrow: labels stay legible on a phone
    axes = fig.subplots(2, 1, sharex=True)
    titles = ("Falls the next move can pick up", "Episodes where every fall could be picked up")
    for ax, key, title in zip(axes, ("falls", "episodes"), titles, strict=True):
        for agent, label, index in AGENTS:
            points = [reset(rows, world, agent)[key] for world in WORLDS]
            shares = [k / n for k, n in points]
            bounds = [wilson(k, n) for k, n in points]
            ax.barh(
                [i + (0.2 if index else -0.2) for i in range(len(WORLDS))],
                shares,
                height=0.38,
                color=colors["series"][index],
                label=label,
                xerr=[  # max(0, ...): at 100% the float upper bound can sit 1e-16 below
                    [max(0.0, s - low) for s, (low, _) in zip(shares, bounds, strict=True)],
                    [max(0.0, high - s) for s, (_, high) in zip(shares, bounds, strict=True)],
                ],
                error_kw={"ecolor": colors["text"], "capsize": 2.5, "elinewidth": 1},
            )
        ax.set_yticks(range(len(WORLDS)), WORLDS)
        ax.invert_yaxis()
        ax.set_title(title, loc="left", fontsize=10.5)
        ax.set_xlim(0, 1.02)
        ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
        ax.grid(axis="x", color=colors["line"], alpha=0.25)
        ax.set_axisbelow(True)
        ax.set_facecolor("none")
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    axes[1].set_xlabel("Share over reset seeds 0-999, with 95% Wilson interval")
    fig.legend(
        *axes[0].get_legend_handles_labels(), loc="outside upper left", ncols=2, frameon=False
    )
    return fig


def save_figures(rows: list[dict]) -> None:
    """Write the light and the dark SVG; the caption is a claim, so assert it first."""
    for world in WORLDS:
        shares = [k / n for k, n in (reset(rows, world, a)["falls"] for a, _, _ in AGENTS)]
        near_half = all(abs(share - 0.5) < 0.03 for share in shares)
        assert near_half == (world == "half"), (world, shares)
    PLOT.parent.mkdir(exist_ok=True)
    for theme, suffix in (("light", ""), ("dark", "-dark")):
        colors = PALETTE[theme]
        style = {
            "svg.fonttype": "none",  # real text: small files, the page's font
            "font.family": "sans-serif",
            "font.size": 10,
            "text.color": colors["text"],
            "axes.edgecolor": colors["line"],
            "axes.labelcolor": colors["text"],
            "xtick.color": colors["text"],
            "ytick.color": colors["text"],
        }
        svg = io.StringIO()
        with mpl.rc_context(style):
            draw(rows, theme).savefig(svg, format="svg", transparent=True, metadata={"Date": None})
        # matplotlib ends path lines with a space; the repo's trailing-whitespace hook would edit it
        lines = svg.getvalue().splitlines()
        Path(f"{PLOT}{suffix}.svg").write_text("\n".join(line.rstrip() for line in lines) + "\n")


def rate_table(rows: list[dict]) -> dict:
    body = [
        [r["world"], r["agent"], r["seeds"], interval(*r["falls"]), interval(*r["episodes"])]
        for world in WORLDS
        for r in rows
        if r["world"] == world
    ]
    return {
        "type": "table",
        "columns": [
            "World",
            "Agent",
            "Seeds",
            "Pickable falls [95% CI]",
            "Episodes, every fall pickable [95% CI]",
        ],
        "rows": body,
    }


# ======================================================================================
#                                  TASK, LTL, MACHINES
# ======================================================================================
def machine_text(arm: str) -> tuple[str, int, int]:
    text = (ENTRY / "graphs" / f"carry-{arm}.rm").read_text()
    committed = BUNDLES / arm / "tpl-chain-response-1-goal-carry/reward_machine.txt"
    assert text == committed.read_text(), f"graphs/carry-{arm}.rm is not the committed machine"
    states = next(line for line in text.splitlines() if line.startswith("STATES:"))
    body = text.split("TRANSITION_FUNCTION:")[1].split("REWARD_FUNCTION:")[0]
    return text, len(states.split(",")), sum(line.startswith("(") for line in body.splitlines())


def machine_blocks(arm: str, caption: str) -> list[dict]:
    text, states, transitions = machine_text(arm)
    return [
        {
            "type": "figure",
            "src": f"graphs/carry-{arm}.html",
            "height": 480,
            "caption": f"{caption} {states} states, {transitions} transitions. Drag a state, click an edge for its cases.",
        },
        {
            "type": "details",
            "items": [{"title": "RM text", "blocks": [{"type": "code", "text": text}]}],
        },
    ]


def task_blocks(cards: dict) -> list[dict]:
    card = cards[CARD_OF_WORLD["face"]]
    for world, card_id in CARD_OF_WORLD.items():  # the world copies change the world only
        copy = cards[card_id]
        assert (copy.task, copy.expect) == (card.task, card.expect), card_id
        assert copy.env["env_kwargs"].get("fall_turn", "face") == world, card_id
    manifest = json.loads((BUNDLES / "farm" / card.id / "manifest.json").read_text())
    stored = sorted(json.dumps(clause) for clause in manifest["generation"]["clauses"])
    assert stored == sorted(json.dumps([t, list(names), p]) for t, names, p in card.expect), card.id
    templates = (TEMPLATES_BUNDLE / "reward_machine.txt").read_text()
    assert templates == (ENTRY / "graphs/carry-farm.rm").read_text(), (
        "the templates machine differs"
    )
    clauses = [
        [f"{t}({', '.join(names)}) {priority}", f"`{pretty_ltlf(ltlf_of(t, list(names)))}`"]
        for t, names, priority in card.expect
    ]
    return [
        {"type": "text", "text": f"**Task (all five worlds):** {card.task}"},
        {"type": "table", "columns": ["Clause (the card's answer)", "LTLf"], "rows": clauses},
        {
            "type": "text",
            "text": "The box rule is the `ChainResponse`: right after `box_fell`, the next step must have "
            "`holding_box`. The four carry worlds are copies of one card that change only `fall_turn`, and all "
            "of them train on the machines of `tpl-chain-response-1-goal-carry`. The templates card "
            "`tpl-chain-response-1-goal` has the same task and a byte-identical FARM machine.",
        },
        *machine_blocks(
            "farm",
            "The FARM machine: +1 for the exit without the box, 12 with it, -10 or -11 for a missed pickup.",
        ),
        *machine_blocks(
            "arm-fm",
            "The ARM-FM machine: it pays 0.1 for each pickup after a fall and 1 for the exit with the box.",
        ),
    ]


# ======================================================================================
#                               TRAINED RUNS (EARLIER SERIES)
# ======================================================================================
def run_rows(cards: dict) -> list[list]:
    """One row per card and arm; asserts the counts the page's prose quotes."""
    worlds = {card_id: world for world, card_id in CARD_OF_WORLD.items()}
    rows, seen = [], {}
    for folder in sorted(
        (ENTRY / "evidence/judge").iterdir(), key=lambda f: (f.name.split("__")[2], f.name)
    ):
        _, _, card_id, arm, _ = folder.name.split("__")
        passed, held = [], []
        for run in sorted(folder.iterdir()):
            judge = json.loads((run / "judge.json").read_text())
            box = next(
                i for i, e in enumerate(judge["expect"]) if e["clause"][0] == "ChainResponse"
            )
            episodes = judge["per_episode"]
            assert len(episodes) == judge["episodes"] == 100, run
            passed.append(sum(e["judged_success"] for e in episodes))
            assert passed[-1] / 100 == judge["mean_judged_success"], run
            held.append(sum(e["verdicts"][box] == "holds" for e in episodes))
        perfect = sum(p == 100 for p in passed)
        seen[(worlds[card_id], arm)] = (perfect, held)
        low, high = wilson(perfect, len(passed))
        rows.append(
            [
                f"`{card_id}`",
                worlds[card_id],
                ARM_NAMES[arm],
                " / ".join(str(p) for p in passed),
                " / ".join(str(h) for h in held),
                f"{perfect} of {len(passed)} [{low:.0%}, {high:.0%}]",
            ]
        )
    assert {row[0].strip("`") for row in rows} <= set(cards), rows
    perfect = {key: value[0] for key, value in seen.items()}
    expected = {
        ("face", "farm"): 3,
        ("face", "arm-fm"): 3,
        ("face", "no-rm"): 3,
        ("side", "farm"): 3,
        ("none", "farm"): 0,
    }
    assert perfect == expected, perfect
    assert seen[("none", "farm")][1] == [78, 78, 78], seen[("none", "farm")]
    return rows


# ======================================================================================
#                                         PAGE
# ======================================================================================
def build() -> dict:
    cards = {card.id: card for card in load_cards(CARDS).cards}
    rows = rates()
    save_figures(rows)

    def falls(world: str, agent: str) -> str:
        return interval(*reset(rows, world, agent)["falls"])

    return {
        "eyebrow": "Paper entry · box-carry fall worlds · 2026-11-22",
        "title": "How often the next move can pick up a fallen box",
        "subtitle": "The box-carry task says: whenever the box falls, pick it up on your very next move. That is "
        "only possible when the box lands right in front of the agent. Each world decides this differently, so "
        "the same rule is easy in one world and half luck in another. The half world, added on 2026-11-22, is "
        "the only one where about half the falls can be picked up for both test agents.",
        "sections": [
            {
                "id": "summary",
                "title": "In short",
                "blocks": [
                    {
                        "type": "list",
                        "items": [
                            f"**face: always.** The fall turns the agent to the box: {falls('face', 'solve')} for "
                            f"the solving plan and {falls('face', 'walk')} for a walker.",
                            f"**half: about one in two, for both.** A fair coin turns the agent to the box or one turn "
                            f"short: {falls('half', 'solve')} and {falls('half', 'walk')}.",
                            f"**none and side depend on where the agent stands.** The intended 25% and 75% hold only "
                            f"on open floor. In the start corner, walls send three landings in four to the front: "
                            f"none gives {falls('none', 'solve')} for the waiting solving plan and "
                            f"{falls('none', 'walk')} for the walker; side gives {falls('side', 'solve')} and "
                            f"{falls('side', 'walk')}.",
                            f"**The rule first asked for was rejected.** Turning only for a box at the right gave "
                            f"{falls('right (rejected)', 'solve')} and {falls('right (rejected)', 'walk')}, far "
                            f"from half, for the same wall reason.",
                            "**What the agents learned (earlier series, 3 seeds).** On face every arm solved all "
                            "test episodes on 3 of 3 seeds; FARM solved side 3 of 3 and none 0 of 3. On none "
                            "FARM's agent drops the box after the first fall and walks out for the safe +1.",
                        ],
                    },
                    {
                        "type": "figure",
                        "src": "plots/pickable-falls.svg",
                        "dark": "plots/pickable-falls-dark.svg",
                        "alt": "Grouped bars of pickable falls and of all-pickable episodes per world, "
                        "for the solving plan and the walker, with 95% Wilson intervals.",
                        "source": "check/build_page.py",
                        "caption": "Only the half world puts both agents near 50%; face gives 100%, and the corner "
                        "start pushes none and side above the intended 25% and 75%. Bars: reset seeds 0-999, "
                        "with 95% Wilson intervals.",
                    },
                ],
            },
            {
                "id": "measure",
                "title": "What was measured",
                "blocks": [
                    {
                        "type": "list",
                        "items": [
                            "**Pickable fall.** Right after the fall, the box lies in the cell the agent faces, so "
                            "the very next move can be a pickup. Per world and agent: the share of pickable falls, "
                            "and the share of episodes with a fall where every fall was pickable (the best score "
                            "an agent can get on the box rule).",
                            "**Two scripted agents, no learning.** `solve` is the cards' solving plan: it waits in "
                            "place for each fall, in the start corner on the carry cards. `walk` takes the shortest "
                            "route to the exit and picks the box up whenever it lies on the floor.",
                            "**Seeds.** The plan checker's event seeds 1-3, the judge's 100 test seeds "
                            "2000000-2000099, and reset seeds 0-999. One reset seed fixes the whole fall schedule, "
                            "so every number reruns exactly.",
                            "**Worlds.** The carry card's world (box in hand, `max_steps` 200) under `fall_turn` "
                            "face, side, none and half; `right (rejected)`, played as none plus a turn toward a box "
                            "that lands at the agent's right; and the templates world of "
                            "`tpl-chain-response-1-goal`, where the box starts on the floor and the agent never "
                            "turns.",
                            "**Intervals.** 95% Wilson, z = 1.96. The one or two falls of an episode count as "
                            "independent trials, so the fall intervals are a little narrow; the episode intervals "
                            "have no such issue.",
                            "**Code.** `app/src/arm_fm/service_room.py:8-22` states the four rules, `:127` makes "
                            "face the default and `_fall` (`:259-280`) applies them.",
                        ],
                    },
                ],
            },
            {
                "id": "rates",
                "title": "Every rate",
                "intro": "Every world, agent and seed set. Cells read pickable/total = share [95% CI].",
                "collapsed": True,
                "blocks": [rate_table(rows)],
            },
            {
                "id": "task",
                "title": "The task, its LTL and its machines",
                "blocks": task_blocks(cards),
            },
            {
                "id": "runs",
                "title": "What the agents learned in the earlier fall series",
                "intro": "Trained PPO runs, 3 seeds each, judged on the 100 test episodes. These ran before the "
                "half world existed.",
                "blocks": [
                    {
                        "type": "table",
                        "columns": [
                            "Card",
                            "World",
                            "Arm",
                            "Test episodes passed (per seed)",
                            "Box rule held (per seed)",
                            "Seeds passing all 100 [95% CI]",
                        ],
                        "rows": run_rows(cards),
                    },
                    {
                        "type": "text",
                        "text": "On none, FARM's agent keeps the box only for the first fall. It picks the box up "
                        "when it landed in front, which happened on 78 of the 100 test episodes, then drops it and "
                        "walks out empty-handed. Drop does nothing before the first fall, and falls skip an agent "
                        "that carries nothing, so it avoids every later fall. The exit-with-box rule stays open "
                        "and no test episode passes. The machine pays +1 for that exit, which no fall can take "
                        "away, against 12 for leaving with the box. On side the fall turns the agent toward the "
                        "box, and the agent carries it out on every episode.",
                    },
                ],
            },
            {
                "id": "checks",
                "title": "Checks",
                "blocks": [
                    {
                        "type": "list",
                        "items": [
                            "**Reruns on main `881b22d`.** `fall_half_rates.py` gave a byte-identical table and the "
                            "same digest on all 13,200 episodes.",
                            "**The half rule changed no old world.** Against the code before it (`029d82c`, "
                            "`evidence/before-029d82c/`), 11,000 shared episodes of face, none, side, right "
                            "(rejected) and templates, 0 changed.",
                            "**Half shares the draws of none and side.** Draws, first landing cell and step are "
                            "equal on reset seeds 0-999 (1000 of 1000); the coin came up heads on 51.9% of first "
                            "falls.",
                            "**The templates walker's misses.** 338 of 1,219 falls over reset seeds 0-999: 251 at "
                            "(4, 6) facing the bottom wall and 87 at (5, 6) facing the exit cell.",
                        ],
                    },
                ],
            },
            {
                "id": "limits",
                "title": "Limits",
                "blocks": [
                    {
                        "type": "list",
                        "items": [
                            "The rates come from two scripted agents, not from trained ones. A trained agent can "
                            "stand elsewhere and see other rates on none and side.",
                            "Three seeds per trained run, so a 3 of 3 still has a wide interval (44% to 100%).",
                            "Not here: the trainings on the half world and the ARM-FM and no-RM runs on side and "
                            "none. They finished on 2026-11-22 after these sources, and the Test 2 count owns them.",
                        ],
                    },
                ],
            },
            {
                "id": "files",
                "title": "Files and rerun",
                "blocks": [
                    {
                        "type": "list",
                        "items": [
                            "`evidence/table.md`, `falls.json`, `digests.json`: the rates, every fall (step, agent "
                            "cell, direction, what lies in front) and one digest per episode.",
                            "`evidence/before-029d82c/`: the same three files on the code before the half rule.",
                            "`evidence/fall-half.md`: the source note, with its own worktree paths.",
                            "`evidence/judge/`: the 15 judge files of the earlier series.",
                            "`check/`: `fall_half_rates.py`, `compare_digests.py`, `same_landing.py`, "
                            "`missed_falls.py` and this page's `build_page.py`. `graphs/`: both machines.",
                        ],
                    },
                    {
                        "type": "code",
                        "text": "# from the repository root, RM_RL_env active; each line is one command\n"
                        "PYTHONPATH=app python -W ignore docs/paper/fall-rate/check/fall_half_rates.py --out docs/paper/fall-rate/evidence\n"
                        "python docs/paper/fall-rate/check/compare_digests.py docs/paper/fall-rate/evidence/before-029d82c/digests.json docs/paper/fall-rate/evidence/digests.json\n"
                        "PYTHONPATH=app python -W ignore docs/paper/fall-rate/check/same_landing.py\n"
                        "python docs/paper/fall-rate/check/missed_falls.py docs/paper/fall-rate/evidence/falls.json templates walk\n"
                        "PYTHONPATH=app python -W ignore docs/paper/fall-rate/check/build_page.py\n"
                        "python3 ~/.claude/skills/agent-artifacts/scripts/fill.py docs/paper/fall-rate/data.json docs/paper/fall-rate/index.html",
                    },
                ],
            },
        ],
    }


def main() -> None:
    out = ENTRY / "data.json"
    out.write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
