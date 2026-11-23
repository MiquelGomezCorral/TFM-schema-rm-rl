r"""Recompute every number of the Results figures from the records, assert the totals, write the figures.

Reads the records through ``records.py``, stops with an AssertionError when one disagrees with the totals
of the final results, then writes ``data/*.csv`` (the numbers each figure draws) and ``figures/fig-res-*.tex``
(pgfplots and TikZ, sized for ``\textwidth``, colours from ``figures/fig-palette.tex``) and
``figures/thesis-preamble.tex`` (the thesis preamble's colour and TikZ lines, for ``figures/preview.tex``).
The MONA figure of the FARM chapter has its own script, ``mona_listing.py``.

Run from the repository root, in RM_RL_env:
env CC_ROOT=$PWD PYTHONPATH=app:.git/agent-memory/artifacts/final-results:docs/paper/level-benchmark-freeze/check:docs/paper/results-figures \
    python -P -W ignore docs/paper/results-figures/make_figures.py
"""

import csv
from pathlib import Path

import draw
import draw_machines
import records
from records import b

ENTRY = Path(__file__).resolve().parent
DATA, FIGURES = ENTRY / "data", ENTRY / "figures"
THESIS = records.REPO / "paper/plantillatfg.tex"
ASKED, FARM_BUILT, ARMFM_BUILT, ROWS = 266, 265, 152, 60
LEARNED_TOTALS = {"farm": 43, "arm-fm": 29, "no-rm": 23}
EXAMPLES = {  # the Results chapter's three example cards: (suite, card id)
    "DoorKey": ("base", "base-doorkey"),
    "Blocked box": ("templates", "tpl-not-co-existence-soft-1-goal"),
    "Box carry": ("box-carry", "cx-box-carry"),
}
THINKING_LABELS = {  # level: (anchor, label position in axis units or None, text lines); see draw.fig_thinking
    "none": ("north west", None, 2),
    "low": ("south east", (11.0, 97.8), 1),
    "medium": ("north", (17.6, 94.0), 2),
    "high": ("south west", (21.5, 100.0), 1),
    "max": ("north", (88.1, 96.4), 2),
}
# leads of the writer (results-notes.md section 9), printed against the recomputed values, never asserted
LEADS_RIGHT, LEADS_MEDIAN = (105, 134, 136, 138, 138), (4, 12, 18, 20, 88)
DRAFT_GROUPS = {  # learned FARM / ARM-FM / no RM per group, as the Results draft states them
    "step-by-step": (11, 8, 3),
    "no goal": (14, 4, 9),
    "with a goal": (15, 17, 10),
    "shop": (3, 0, 1),
}
GROUP_LABEL = {
    "all": "all rows",
    "step-by-step": "step-by-step",
    "no goal": "no goal",
    "with a goal": "with a goal",
    "shop": "the shop",
}
# Thesis preamble ranges the preview needs, taken verbatim from paper/plantillatfg.tex: (first line's
# start, last line's start); a single line has both equal.
PREAMBLE_RANGES = (
    ("\\usepackage{pgfplots}", "\\usepackage{pgfplots}"),
    ("\\pgfplotsset{compat=1.18}", "\\pgfplotsset{compat=1.18}"),
    ("\\usepgfplotslibrary{groupplots}", "\\usepgfplotslibrary{groupplots}"),
    ("\\usetikzlibrary{positioning,", "\\usetikzlibrary{positioning,"),
    ("\\colorlet{farmLLM}", "\\colorlet{farmLLM}"),
    ("\\colorlet{farmRM}", "\\colorlet{farmRM}"),
    ("\\colorlet{farmFinal}", "\\colorlet{farmFinal}"),
    ("farm graph/.style=", "farm graph/.style="),
    ("\\lstset{", "}"),
    ("\\colorlet{rmTitle}", "\\newcommand\\rmnum"),
    ("\\lstdefinelanguage{rmtext}", "xleftmargin="),
)


def write_csv(name, rows):
    with (DATA / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def figure(name, text):
    (FIGURES / f"{name}.tex").write_text(text, encoding="utf-8")


def rounded(row):
    return {
        key: round(value, 4) if isinstance(value, float) else value for key, value in row.items()
    }


# ========= Figure 1: machines built =========
def build_fig_built():
    counts = records.built_counts()
    farm, armfm = counts["farm"], counts["arm-fm"]
    assert farm["asked"] == armfm["asked"] == ASKED, (farm, armfm)
    assert ASKED - farm["not built"] == FARM_BUILT and ASKED - armfm["not built"] == ARMFM_BUILT, (
        counts
    )
    assert (farm["first"], farm["rejected"], farm["not built"]) == (262, 3, 1), farm
    assert (
        armfm["first"],
        armfm["rejected"],
        armfm["invalid"],
        armfm["both"],
        armfm["not built"],
    ) == (132, 19, 1, 0, 114), armfm
    rows, table = {}, []
    for arm, c in counts.items():
        built = c["asked"] - c["not built"]
        low, high = b.wilson_ci(built, c["asked"])
        further = built - c["first"]
        detail = f"{c['rejected']} after a critic rejection, {c['invalid']} after an invalid output"
        rows[arm] = {
            "asked": c["asked"],
            "first": c["first"],
            "further": further,
            "not_built": c["not built"],
            "built": built,
            "low": low,
            "high": high,
            "detail": detail,
        }
        table.append(
            rounded(
                {
                    "arm": arm,
                    "asked": c["asked"],
                    "built_first": c["first"],
                    "built_further": further,
                    "further_after_critic_rejection": c["rejected"],
                    "further_after_invalid_output": c["invalid"],
                    "not_built": c["not built"],
                    "built": built,
                    "built_share": built / c["asked"],
                    "wilson_low": low,
                    "wilson_high": high,
                }
            )
        )
    write_csv("built", table)
    figure("fig-res-built", draw.fig_built(rows))
    return rows


# ========= Figure 2: rows learned =========
def build_fig_learned():
    rows = records.learned_rows()
    assert len(rows) == ROWS, len(rows)
    counts = records.learned_counts(rows)
    known = {b.LEARNED, b.NOT_LEARNED, b.FAILED}
    assert all(set(c) <= known for c in counts.values()), {
        key: dict(c) for key, c in counts.items()
    }
    assert {arm: counts["all", arm][b.LEARNED] for arm in b.ARMS} == LEARNED_TOTALS, counts
    assert [sum(counts[g, "farm"].values()) for g in records.GROUPS] == [60, 11, 15, 23, 11], counts
    table = []
    for group in records.GROUPS:
        for arm in b.ARMS:
            c = counts[group, arm]
            n = sum(c.values())
            low, high = b.wilson_ci(c[b.LEARNED], n)
            table.append(
                rounded(
                    {
                        "group": group,
                        "arm": arm,
                        "n": n,
                        "learned": c[b.LEARNED],
                        "not_learned": c[b.NOT_LEARNED],
                        "not_built": c[b.FAILED],
                        "learned_share": c[b.LEARNED] / n,
                        "wilson_low": low,
                        "wilson_high": high,
                    }
                )
            )
    for group, expected in DRAFT_GROUPS.items():
        got = tuple(counts[group, arm][b.LEARNED] for arm in b.ARMS)
        print(
            f"Results draft, {group}: draft {expected}, records {got}",
            "ok" if got == expected else "DIFFERS",
        )
    write_csv("learned", table)
    plot = [
        {
            "group": r["group"],
            "arm": r["arm"],
            "n": r["n"],
            "learned": r["learned"],
            "not_learned": r["not_learned"],
            "not_built": r["not_built"],
            "low": r["wilson_low"],
            "high": r["wilson_high"],
        }
        for r in table
    ]
    figure("fig-res-learned", draw.fig_learned(plot, list(records.GROUPS), GROUP_LABEL))


# ========= Figure 3: soft breaks per judged episode =========
def build_fig_soft():
    rows, checked = records.soft_rows(), records.soft_record()
    assert len(rows) == 20 and {(r["suite"], r["card"]) for r in rows} == set(checked), len(rows)
    assert all(r["soft_only"] == (r["idle"] is not None) for r in rows), (
        "idle plan only on soft-only cards"
    )
    assert sum(r["idle"] is not None for r in rows) == 8, "idle plan on 8 soft-only cards"
    table, drawn = [], {}
    for row in rows:
        key = (row["suite"], row["card"])
        assert row["idle"] == checked[key]["idle"], key
        drawn[key] = {
            "label": row["card"].removeprefix("tpl-"),
            "idle": row["idle"],
            "soft_only": row["soft_only"],
        }
        for arm in b.ARMS:
            runs = row[arm]
            if (
                arm != "arm-fm"
            ):  # FARM and no RM are cross-checked against the checked record of soft-breaks-vs-idle
                assert [v for _, v in runs] == [
                    x["soft_break_count"] for x in checked[key][arm]["runs"]
                ], (key, arm)
            line = {
                "suite": row["suite"],
                "card": row["card"],
                "soft_only": row["soft_only"],
                "arm": arm,
                "idle_plan": row["idle"],
                "seed1": "",
                "seed2": "",
                "seed3": "",
                "mean": "",
                "ci_low": "",
                "ci_high": "",
            }
            if runs is None:
                assert arm == "arm-fm" and row["outcome_armfm"] == b.FAILED, (key, arm)
                drawn[key][arm] = None
            else:
                values = [v for _, v in runs]
                assert len(values) == 3, (key, arm, values)
                mean, low, high = records.over_seeds(values)
                drawn[key][arm] = {"mean": mean, "low": low, "high": high, "seeds": values}
                line |= {f"seed{seed}": value for seed, value in runs} | {
                    "mean": mean,
                    "ci_low": low,
                    "ci_high": high,
                }
            table.append(rounded(line))
    write_csv("soft", table)

    def panel(title, soft_only):
        found = sorted(
            (d for d in drawn.values() if d["soft_only"] == soft_only),
            key=lambda d: (-d["farm"]["mean"], d["label"]),
        )
        return title.format(len(found)), found

    panels = [
        panel("Soft rules only, no goal ({} cards)", True),
        panel("With a goal or a hard rule ({} cards): no idle plan", False),
    ]
    xmax = 28
    assert (
        max(max(d[a]["high"] for a in ("farm", "arm-fm", "no-rm") if d[a]) for d in drawn.values())
        < xmax
    )
    figure("fig-res-soft", draw.fig_soft(panels, xmax))


# ========= Figure 4: right machines per thinking level =========
def build_fig_thinking():
    levels = records.thinking_levels()
    table = []
    for row in levels:
        assert row["runs"] == 138, row
        row["low"], row["high"] = b.wilson_ci(row["right"], row["runs"])
        table.append(
            rounded(
                {
                    "level": row["level"],
                    "runs": row["runs"],
                    "right": row["right"],
                    "share": row["right"] / row["runs"],
                    "wilson_low": row["low"],
                    "wilson_high": row["high"],
                    "median_seconds": row["median_s"],
                }
            )
        )
    print("thinking, right:", [r["right"] for r in levels], "leads", LEADS_RIGHT)
    print("thinking, median s:", [r["median_s"] for r in levels], "leads", LEADS_MEDIAN)
    write_csv("thinking", table)
    figure("fig-res-thinking", draw.fig_thinking(levels, THINKING_LABELS))


# ========= Figure 5: the example machines =========
def build_fig_machines():
    machines, table = {}, []
    for card, (suite, name) in EXAMPLES.items():
        for arm in ("farm", "arm-fm"):
            machine = machines[card, arm] = records.merged_arrows(b.bundle_root(suite, arm) / name)
            for arrow in machine["arrows"]:
                table.append(
                    {
                        "card": card,
                        "arm": arm,
                        "source": arrow["source"],
                        "target": arrow["target"],
                        "transitions": arrow["count"],
                        "reward": draw_machines.arrow_label(arrow).replace("$", ""),
                        "colour": draw_machines.arrow_colour(arrow["rewards"]),
                    }
                )
    write_csv("machines", table)
    figure("fig-res-ex-machines", draw_machines.fig_machines(machines))


# ========= The preview's lines of the thesis preamble =========
def write_thesis_preamble():
    thesis = THESIS.read_text(encoding="utf-8").splitlines()
    out = [
        f"% Lines of {THESIS.relative_to(records.REPO)}, extracted by make_figures.py; do not edit."
    ]
    for first, last in PREAMBLE_RANGES:
        starts = [i for i, line in enumerate(thesis) if line.strip().startswith(first)]
        assert len(starts) == 1, f"{first!r} is not exactly once in {THESIS}"
        end = next(i for i in range(starts[0], len(thesis)) if thesis[i].strip().startswith(last))
        block = "\n".join(thesis[starts[0] : end + 1])
        out.append(f"\\tikzset{{\n{block}\n}}" if first.startswith("farm graph") else block)
    (FIGURES / "thesis-preamble.tex").write_text("\n".join(out) + "\n", encoding="utf-8")


DATA.mkdir(exist_ok=True)
FIGURES.mkdir(exist_ok=True)
built = build_fig_built()
build_fig_learned()
build_fig_soft()
build_fig_thinking()
build_fig_machines()
write_thesis_preamble()
print(
    "built",
    {
        arm: (r["built"], r["asked"], round(r["low"], 4), round(r["high"], 4))
        for arm, r in built.items()
    },
)
print("all assertions passed")
