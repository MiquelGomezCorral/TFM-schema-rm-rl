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
from itertools import groupby
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
THINKING_SERIES = {  # model of levels.csv: (name in the legend, colour, pgfplots mark); one each per model
    "DeepSeek V4.1 Flash + GLM 5.3 Flash": ("Default pair", draw.ARM_COLOR["farm"], "*"),
    "Haiku 5.5": ("Haiku 5.5", "plotModelB", "square*"),
    "GPT-6 Luna": ("GPT-6 Luna", "plotModelC", "triangle*"),
}
THINKING_LABELS = {  # (series, level): (anchor, hang, shift in pt); see draw.fig_thinking
    ("Default pair", "none"): ("north west", "point", (3, -1)),
    ("Default pair", "low"): ("north", "low", (5, -2)),
    ("Default pair", "medium"): ("north", "low", (0, -2)),
    ("Default pair", "high"): ("south", "point", (0, 5)),
    ("Default pair", "max"): ("east", "point", (-6, 0)),
    ("Haiku 5.5", "low"): ("south east", "point", (-3, 3)),
    ("Haiku 5.5", "medium"): ("south", "high", (0, 2)),
    ("Haiku 5.5", "high"): ("south", "high", (8, 2)),
    ("Haiku 5.5", "max"): ("south", "point", (0, 5)),
    ("GPT-6 Luna", "none"): ("east", "point", (-8, 0)),
    ("GPT-6 Luna", "low"): ("east", "point", (-5, 0)),
    ("GPT-6 Luna", "medium"): ("west", "point", (6, 0)),
    ("GPT-6 Luna", "high"): ("west", "point", (6, 0)),
    ("GPT-6 Luna", "max"): ("west", "point", (6, 0)),
}
OPEN_WHERE = {  # "where" of open-models.csv: (name in the legend, colour); plotFarm stays FARM's
    "cluster": ("on the cluster", "plotModelB"),
    "local": ("on the PC", "plotModelC"),
}
# leads of the writer (results-notes.md section 9), printed against the recomputed values, never asserted
LEADS_RIGHT, LEADS_MEDIAN = (105, 134, 136, 138, 138), (4, 12, 18, 20, 88)
DRAFT_GROUPS = {  # learned FARM / ARM-FM / no RM per group, as the Results draft states them
    "step-by-step": (11, 8, 3),
    "no goal": (14, 4, 9),
    "with a goal": (15, 17, 10),
    "shop": (3, 0, 1),
}
ARMFM_DATA = records.REPO / "docs/paper/armfm-baseline-results/data"  # the CSVs of its build.py
ARMFM_LABELS = {  # task labels of Figures 6 and 7, the same as the baseline entry's previews
    "armfm-doorkey-5x5": "DoorKey\\\\5$\\times$5",
    "armfm-doorkey-5x5-fixed": "DoorKey\\\\5$\\times$5 fixed",
    "armfm-doorkey-8x8-fixed": "DoorKey\\\\8$\\times$8 fixed",
    "armfm-doorkey-16x16": "DoorKey\\\\16$\\times$16",
    "armfm-doorkey-16x16-fixed": "DoorKey\\\\16$\\times$16 fixed",
    "armfm-unlock-to-unlock": "UnlockToUnlock",
    "xland-x1-197": "X1\\\\(197)",
    "xland-x2-212": "X2\\\\(212)",
    "xland-x3-260": "X3\\\\(260)",
    "xland-x4-859": "X4\\\\(859)",
    "xland-x5-594": "X5\\\\(594)",
    "xland-zc": "ZC",
}
GROUP_LABEL = {
    "all": "all tasks",
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
        panel("Soft rules only, no goal ({} tasks)", True),
        panel("With a goal or a hard rule ({} tasks): no idle plan", False),
    ]
    xmax = 28
    assert (
        max(max(d[a]["high"] for a in ("farm", "arm-fm", "no-rm") if d[a]) for d in drawn.values())
        < xmax
    )
    figure("fig-res-soft", draw.fig_soft(panels, xmax))


# ========= Figure 4: right machines per thinking level, per model =========
def is_beaten(row, rows):
    """Another row is no slower, has no fewer right RMs, and is better in at least one of the two."""
    return any(
        other["median_s"] <= row["median_s"]
        and other["right"] >= row["right"]
        and (other["median_s"] < row["median_s"] or other["right"] > row["right"])
        for other in rows
    )


def build_fig_thinking():
    levels = records.thinking_levels()
    print("thinking, right:", [r["right"] for r in levels], "leads", LEADS_RIGHT)
    print("thinking, median s:", [r["median_s"] for r in levels], "leads", LEADS_MEDIAN)
    # API models only: the cluster models' times come from one GPU running 8 RMs at once (author to decide)
    rows = [r for r in records.final_model_levels() if r["model"] in THINKING_SERIES]
    assert all(r["runs"] == 138 for r in levels + rows), "every drawn level has all 138 runs"
    pipeline = [r for r in rows if THINKING_SERIES[r["model"]][0] == "Default pair"]
    assert [(r["level"], r["right"], r["median_s"]) for r in pipeline] == [
        (r["level"], r["right"], round(r["median_s"], 2)) for r in levels
    ], "levels.csv and the records disagree on the frozen pipeline"
    table = []
    for row in rows:
        row["series"], row["colour"], row["mark"] = THINKING_SERIES[row["model"]]
        row["beaten"] = is_beaten(row, rows)
        table.append(
            rounded(
                {
                    "model": row["series"],
                    "level": row["level"],
                    "right": row["right"],
                    "n": row["runs"],
                    "wilson_low": row["low"],
                    "wilson_high": row["high"],
                    "median_seconds": row["median_s"],
                    "beaten": row["beaten"],
                }
            )
        )
    unbeaten = sorted((r for r in rows if not r["beaten"]), key=lambda r: r["median_s"])
    print(f"thinking, {len(rows)} points drawn; not beaten, by time:")
    for r in unbeaten:
        print(f"  {r['series']}, {r['level']}: {r['right']}/{r['runs']} at {r['median_s']} s")
    write_csv("thinking", table)
    figure("fig-res-thinking", draw.fig_thinking(rows, THINKING_LABELS))


# ========= Figure 4b: right machines per open-weight model and level, one column per model =========
def build_fig_open_models():
    memory = records.open_model_memory()
    rows = [r for r in records.final_model_levels() if r["model"] in memory]
    assert {r["model"] for r in rows} == set(memory), "every open-weight model has a final level"
    assert all(r["runs"] == 138 for r in rows), "every drawn level has all 138 runs"
    for row in rows:
        where, row["weights"] = memory[row["model"]]
        row["series"], row["colour"] = OPEN_WHERE[where]
    rows.sort(key=lambda r: (r["weights"], records.LEVELS.index(r["level"])))
    figure("fig-res-open-models", draw.fig_open_models(rows))


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


# ========= Figures 6 and 7: the ARM-FM paper's tasks =========
def armfm_groups(csv_name):
    """[(first row of the group, {arm: cell})] of one baseline CSV, a group per card (and mix)."""
    groups = {}
    with (ARMFM_DATA / f"{csv_name}.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            cell = {
                "mean": float(row["mean"]),
                "low": float(row["ci_low"]),
                "high": float(row["ci_high"]),
            }
            if row.get("runs"):  # the counted DoorKey 16x16 fixed rows
                cell["count"] = (int(row["successes"]), int(row["runs"]))
            else:
                cell["runs"] = [float(row[f"seed{seed}"]) for seed in (1, 2, 3)]
            groups.setdefault((row.get("mix"), row["card"]), (row, {}))[1][row["arm"]] = cell
    return list(groups.values())


def sections_of(headings):
    """[(first, last, heading)], 1-based, over runs of groups that share a heading."""
    sections, first = [], 1
    for heading, same in groupby(headings):
        last = first + len(list(same)) - 1
        sections.append((first, last, heading))
        first = last + 1
    return sections


def build_fig_armfm():
    paper = armfm_groups("test1-armfm-paper")
    xland = armfm_groups("test2-xland-single") + armfm_groups("test3-xland-mixes")
    assert [len(paper), len(xland)] == [6, 10], (len(paper), len(xland))
    assert all(len(cells) == 3 for _, cells in paper + xland), "three arms per task"
    steps = [f"{int(row['steps']) / 1e6:g}M steps" for row, _ in paper]
    mixes = [
        f"{row['mix'].removeprefix('xland-mix')}-task mix" if row.get("mix") else "single tasks"
        for row, _ in xland
    ]
    for name, groups, headings in (
        ("fig-res-armfm-paper", paper, steps),
        ("fig-res-armfm-xland", xland, mixes),
    ):
        labelled = [(ARMFM_LABELS[row["card"]], cells) for row, cells in groups]
        figure(name, draw.fig_armfm(labelled, sections_of(headings)))


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


if __name__ == "__main__":  # importing the module builds nothing, so one builder can run alone
    DATA.mkdir(exist_ok=True)
    FIGURES.mkdir(exist_ok=True)
    built = build_fig_built()
    build_fig_learned()
    build_fig_soft()
    build_fig_thinking()
    build_fig_open_models()
    build_fig_machines()
    build_fig_armfm()
    write_thesis_preamble()
    print(
        "built",
        {
            arm: (r["built"], r["asked"], round(r["low"], 4), round(r["high"], 4))
            for arm, r in built.items()
        },
    )
    print("all assertions passed")
