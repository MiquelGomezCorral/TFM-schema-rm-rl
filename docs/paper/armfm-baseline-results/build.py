r"""Rebuild the ARM-FM baseline results (option B) from the raw run folders.

Reads only the judge files and run configs under ``outputs/runs/bench__*``, the training log of one run,
``experiments/benchmark/{armfm-paper,xland}/tasks.json`` and the machines the runs name. Writes
``data/test*.csv`` (one per test), ``results.md`` (one table per test), ``cards.md`` (task, LTL and both
machines of every card) and ``figures/fig-*.tex`` (pgfplots, the palette and helpers of
``results-figures/``). Stops with an AssertionError when a cell lacks exactly seeds 1, 2 and 3, a judge names
the wrong card or machine, or an ablation run differs from the default run in more than its one setting.
One cell group is counted instead: DoorKey 16x16 fixed has 8 training runs for FARM and ARM-FM (suites
``armfm-paper`` and ``armfm-paper-rerun``) and 3 for no RM, scored as runs judged successful with a Wilson
interval.

Run from the repository root, in RM_RL_env:
env PYTHONPATH=app:docs/paper/results-figures python -P docs/paper/armfm-baseline-results/build.py
"""

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean, stdev

import draw  # docs/paper/results-figures: TeX helpers and arm colours of the Results figures
import yaml
from scipy.stats import binomtest, t

from src.utils import ltlf_of, pretty_ltlf

ENTRY = Path(__file__).resolve().parent
REPO = ENTRY.parents[2]
RUNS = REPO / "outputs/runs"
BENCH = REPO / "experiments/benchmark"
DATA, FIGURES = ENTRY / "data", ENTRY / "figures"
SEEDS = (1, 2, 3)
T975 = t.ppf(0.975, len(SEEDS) - 1)  # Student t, n - 1 = 2 degrees of freedom
ARMS = ("farm", "arm-fm", "no-rm")
TRANSFER_PREFIX = {
    "farm": "farm",
    "arm-fm": "arm-fm",
    "no-rm": "card",
}  # seed*/transfer/<prefix>-<card>
PAPER_CARDS = (
    "armfm-doorkey-5x5",
    "armfm-doorkey-5x5-fixed",
    "armfm-doorkey-8x8-fixed",
    "armfm-doorkey-16x16",
    "armfm-doorkey-16x16-fixed",
    "armfm-unlock-to-unlock",
)
FIXED_CARD = "armfm-doorkey-16x16-fixed"  # counted as runs judged successful, not averaged per seed
ORIGINAL_SUITE = "armfm-paper"
FIXED_SUITES = {  # suite: seeds of the fixed card's training runs; no RM has only the original suite
    ORIGINAL_SUITE: (1, 2, 3),
    "armfm-paper-rerun": (4, 5, 6, 7, 8),
}
SINGLE_CARDS = ("xland-x1-197", "xland-zc")
MIXES = ("xland-mix3", "xland-mix5")
ZERO_SHOT = ("xland-zab", "xland-zc")  # trained on the mix ZA+ZB, judged on the unseen ZC
ABLATIONS = {  # variant: (run folder, the one run-config setting it changes against the default)
    "default": ("bench__xland__xland-mix5__arm-fm__ppo", {}),
    "no embeddings": (
        "bench__xland-mix5-noemb__xland-mix5__arm-fm__ppo-noemb",
        {"rm_state_encoding": "none"},
    ),
    "no RM reward": (
        "bench__xland-mix5-normreward__xland-mix5__arm-fm__ppo",
        {"reward_source": "env_rm_state"},
    ),
}
STUCK_RUN = ("bench__armfm-paper__armfm-doorkey-16x16-fixed__farm__ppo", 3)  # (run, seed) recounted
DOORKEY16_LIMIT = 2560  # MiniGrid DoorKey-16x16 max_steps (10 x 16 x 16)
ARM_SERIES = {  # key: (legend name, bar fill)
    "farm": ("FARM", f"fill={draw.ARM_COLOR['farm']}"),
    "arm-fm": ("ARM-FM", f"fill={draw.ARM_COLOR['arm-fm']}"),
    "no-rm": ("no RM", f"fill={draw.ARM_COLOR['no-rm']}"),
}
VARIANT_SERIES = {
    "default": ("default", "fill=plotArm"),
    "no embeddings": ("no embeddings", "fill=plotArmLight"),
    "no RM reward": ("no RM reward", "fill=plotArm!45!black"),
}
LABELS = {
    "armfm-doorkey-5x5": "DoorKey\\\\5x5",
    "armfm-doorkey-5x5-fixed": "DoorKey\\\\5x5 fixed",
    "armfm-doorkey-8x8-fixed": "DoorKey\\\\8x8 fixed",
    "armfm-doorkey-16x16": "DoorKey\\\\16x16",
    "armfm-doorkey-16x16-fixed": "DoorKey\\\\16x16 fixed",
    "armfm-unlock-to-unlock": "Unlock-\\\\ToUnlock",
    "xland-x1-197": "X1\\\\(197)",
    "xland-x2-212": "X2\\\\(212)",
    "xland-x3-260": "X3\\\\(260)",
    "xland-x4-859": "X4\\\\(859)",
    "xland-x5-594": "X5\\\\(594)",
    "xland-zc": "ZC",
}
NUMBERS = ("seed1", "seed2", "seed3", "mean", "ci_low", "ci_high")
COLUMN_NAMES = {
    "card": "Card",
    "mix": "Mix",
    "trained_on": "Trained on",
    "steps": "Steps",
    "episodes": "Judged episodes",
}


# ========= Raw files =========
def seed_folders(run, seeds=SEEDS):
    """{seed: folder} of one run; folders with a '.' in the name (interrupted copies) are skipped."""
    folders = {}
    for folder in sorted(run.glob("seed*-*")):
        if "." in folder.name or not folder.is_dir():
            continue
        seed = int(folder.name.split("-")[0].removeprefix("seed"))
        assert seed not in folders, f"{run.name}: two seed {seed} folders"
        folders[seed] = folder
    assert tuple(sorted(folders)) == seeds, f"{run.name}: seeds {sorted(folders)}, not {seeds}"
    return folders


def run_config(run):
    return yaml.safe_load((run / "run-config.yaml").read_text(encoding="utf-8"))


def trained_bundles(run):
    """The machines a run trained on, as repository paths (none for no-RM)."""
    config = run_config(run)
    entries = config.get("task_bundles") or [config]
    return [Path(e["bundle"]) for e in entries if e.get("bundle")]


def judge_score(path, card, arm):
    """(judged success, judged episodes, machine path) of one judge file, checked against card and arm."""
    judge = json.loads(path.read_text(encoding="utf-8"))
    assert judge["id"] == card, (path, judge["id"])
    bundle = judge["rm_bundle"]
    if arm == "no-rm":
        assert bundle is None, (path, bundle)
    else:
        bundle = Path(
            bundle
        )  # own judges store it absolute, transfer judges relative to the repository
        bundle = bundle.relative_to(REPO) if bundle.is_absolute() else bundle
        assert bundle.parent.name == arm, (path, bundle)
    return judge["mean_judged_success"], judge["episodes"], bundle


def members(run):
    return sorted(p.stem for p in (run / "members").glob("*.json"))


def transfer_scores(run, arm, cards):
    """{card: {seed: score}} of a mix run judged per card, each with the arm's own machine of that card."""
    expected = sorted(f"{TRANSFER_PREFIX[arm]}-{card}" for card in cards)
    out = {card: {} for card in cards}
    for seed, folder in seed_folders(run).items():
        found = sorted(p.name for p in (folder / "transfer").iterdir())
        assert found == expected, (folder, found, expected)
        for card in cards:
            score = judge_score(
                folder / "transfer" / f"{TRANSFER_PREFIX[arm]}-{card}/judge.json", card, arm
            )
            assert score[2] is None or score[2].name == card, (folder, card, score[2])
            out[card][seed] = score
    return out


# ========= Numbers =========
def over_seeds(scores):
    """Seed values, mean and 95% t interval over seeds 1-3 (clipped to [0, 1]), plus the judged machine."""
    values = [scores[seed][0] for seed in SEEDS]
    episodes = {score[1] for score in scores.values()}
    bundles = {score[2] for score in scores.values()}
    assert len(episodes) == 1 and len(bundles) == 1, (episodes, bundles)
    mean = fmean(values)
    half = T975 * stdev(values) / len(values) ** 0.5
    numbers = dict(zip(NUMBERS[:3], values, strict=True))
    numbers |= {"mean": mean, "ci_low": max(0.0, mean - half), "ci_high": min(1.0, mean + half)}
    return {"episodes": episodes.pop(), **numbers}, bundles.pop()


class Machines:
    """Card -> arm -> the one machine its runs trained or were judged on."""

    def __init__(self):
        self.of = defaultdict(dict)

    def add(self, card, arm, bundle):
        if bundle is None:
            return
        assert self.of[card].setdefault(arm, bundle) == bundle, (card, arm, bundle)


def counted_row(card, arm, machines):
    """Test 1, fixed-map card: runs judged successful over all its training runs, Wilson 95% interval.

    The judge plays the one map once, so every run scores 0 or 1. All runs share one run config
    (bar the experiment name), one judged machine and one episode count.
    """
    judged = []  # (suite, judge score) per training run
    configs = []
    for suite, seeds in FIXED_SUITES.items():
        if arm == "no-rm" and suite != ORIGINAL_SUITE:
            continue
        run = RUNS / f"bench__{suite}__{card}__{arm}__ppo"
        configs.append(run_config(run) | {"exp_name": None})
        for folder in seed_folders(run, seeds).values():
            score = judge_score(folder / "judge.json", card, arm)
            assert arm == "no-rm" or [score[2]] == trained_bundles(run), (folder, score[2])
            judged.append((suite, score))
    assert all(config == configs[0] for config in configs), (card, arm, "run configs differ")
    scores = [score[0] for _, score in judged]
    assert set(scores) <= {0.0, 1.0}, (card, arm, scores)
    episodes = {score[1] for _, score in judged}
    bundles = {score[2] for _, score in judged}
    assert len(episodes) == 1 and len(bundles) == 1, (episodes, bundles)
    machines.add(card, arm, bundles.pop())
    successes = int(sum(scores))
    original = [s for (suite, _), s in zip(judged, scores, strict=True) if suite == ORIGINAL_SUITE]
    interval = binomtest(successes, len(scores)).proportion_ci(method="wilson")  # 95% by default
    return {
        "card": card,
        "arm": arm,
        "steps": configs[0]["total_timesteps"],
        "episodes": episodes.pop(),
        "mean": successes / len(scores),
        "ci_low": interval.low,
        "ci_high": interval.high,
        "runs": len(scores),
        "successes": successes,
        "original_successes": int(sum(original)),
        "run_scores": " ".join(f"{s:.0f}" for s in scores),
    }


def own_judge_rows(suite, cards, machines):
    """Tests 1 and 2: each run's own judge, one row per card and arm."""
    rows = []
    for card in cards:
        for arm in ARMS:
            if card == FIXED_CARD:
                rows.append(counted_row(card, arm, machines))
                continue
            run = RUNS / f"bench__{suite}__{card}__{arm}__ppo"
            scores = {
                seed: judge_score(folder / "judge.json", card, arm)
                for seed, folder in seed_folders(run).items()
            }
            numbers, bundle = over_seeds(scores)
            assert [bundle] == trained_bundles(run) or arm == "no-rm", (run, bundle)
            machines.add(card, arm, bundle)
            steps = run_config(run)["total_timesteps"]
            rows.append({"card": card, "arm": arm, "steps": steps, **numbers})
    return rows


def mix_rows(mix, arm, run, machines):
    """One row per member card of a mix run, judged with the arm's own machine of that card."""
    cards = members(run)
    steps = run_config(run)["total_timesteps"]
    rows = []
    for card, scores in transfer_scores(run, arm, cards).items():
        numbers, bundle = over_seeds(scores)
        machines.add(card, arm, bundle)
        rows.append({"mix": mix, "card": card, "arm": arm, "steps": steps, **numbers})
    for bundle in trained_bundles(run):
        machines.add(bundle.name, arm, bundle)
    return rows


def test3_rows(machines):
    rows = []
    for mix in MIXES:
        cards = {arm: members(RUNS / f"bench__xland__{mix}__{arm}__ppo") for arm in ARMS}
        assert len({tuple(c) for c in cards.values()}) == 1, (mix, cards)
        for arm in ARMS:
            rows += mix_rows(mix, arm, RUNS / f"bench__xland__{mix}__{arm}__ppo", machines)
    return rows


def test4_rows(machines):
    mix, card = ZERO_SHOT
    rows = []
    for arm in ARMS:
        run = RUNS / f"bench__xland__{mix}__{arm}__ppo"
        assert members(run) == ["xland-za", "xland-zb"], members(run)
        numbers, bundle = over_seeds(transfer_scores(run, arm, [card])[card])
        machines.add(card, arm, bundle)
        for trained in trained_bundles(run):
            machines.add(trained.name, arm, trained)
        steps = run_config(run)["total_timesteps"]
        rows.append(
            {
                "trained_on": "+".join(members(run)),
                "card": card,
                "arm": arm,
                "steps": steps,
                **numbers,
            }
        )
    return rows


def test5_rows(machines):
    default = run_config(RUNS / ABLATIONS["default"][0])
    rows = []
    for variant, (folder, change) in ABLATIONS.items():
        run = RUNS / folder
        config = run_config(run)
        differs = {
            k: config.get(k)
            for k in config.keys() | default.keys()
            if config.get(k) != default.get(k)
        }
        differs.pop("exp_name", None)
        assert differs == change, (variant, differs)
        for row in mix_rows("xland-mix5", "arm-fm", run, machines):
            rows.append({"variant": variant, **row})
    return rows


def stuck_recount():
    """Training episodes of one run: how many ran to the step limit, and the machine state each ended in."""
    run, seed = STUCK_RUN
    folder = seed_folders(RUNS / run)[seed]
    with (folder / "episodes.csv").open(newline="", encoding="utf-8") as handle:
        episodes = list(csv.DictReader(handle))
    timed_out = sum(
        e["exited"] == "False" and int(e["length"]) == DOORKEY16_LIMIT for e in episodes
    )
    ended = Counter(e["final_rm_state"] for e in episodes)
    return {
        "run": run,
        "seed": seed,
        "episodes": len(episodes),
        "timed_out": timed_out,
        "ended_in": ended,
    }


# ========= Writing =========
def write_csv(name, rows):
    with (DATA / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = list(dict.fromkeys(key for row in rows for key in row))  # counted rows add columns
        writer = csv.DictWriter(handle, fieldnames=fields, restval="")
        writer.writeheader()
        writer.writerows(
            {k: round(v, 4) if isinstance(v, float) else v for k, v in row.items()} for row in rows
        )


def cell_text(row):
    if "runs" in row:
        detail = f"{row['successes']} of {row['runs']} runs"
    else:
        detail = ", ".join(f"{row[f'seed{s}']:.2f}" for s in SEEDS)
    return f"{row['mean']:.2f} [{row['ci_low']:.2f}, {row['ci_high']:.2f}] ({detail})"


def card_link(card):
    return f"[{card}](cards.md#{card})"


def by_place(rows, keys, series_key):
    """{values of ``keys``: {series value: row}}, in row order."""
    grouped = defaultdict(dict)
    for row in rows:
        grouped[tuple(row[k] for k in keys)][row[series_key]] = row
    return grouped


def column_text(key, value):
    if key == "card":
        return card_link(value)
    if key == "steps":
        return f"{value / 1e6:g}M"
    return str(value)


def table(rows, keys, series, series_key="arm"):
    """Markdown table: one line per value of ``keys`` (columns of the row), one column per series."""
    names = [series[s][0] for s in series]
    lines = [
        "| " + " | ".join([*(COLUMN_NAMES[k] for k in keys), *names]) + " |",
        "|" + "---|" * (len(keys) + len(names)),
    ]
    for cells in by_place(rows, keys, series_key).values():
        first = next(iter(cells.values()))
        shown = [column_text(k, first[k]) for k in keys] + [cell_text(cells[s]) for s in series]
        lines.append("| " + " | ".join(shown) + " |")
    notes = ["Cells: mean [95% CI over the 3 seeds, Student t, n - 1 = 2] (seeds 1, 2, 3)."]
    if any("runs" in row for row in rows):
        notes.append(
            "DoorKey 16x16 fixed cells: share of training runs judged successful [95% Wilson interval] "
            "(runs judged successful of training runs)."
        )
    return [*notes, "", *lines]


def fig_bars(groups, series, sections, narrow=False):
    """One tikzpicture of grouped bars: groups [(tick label, {series: row})], sections [(first, last, title)]."""
    step = 0.27
    offsets = {key: (i - (len(series) - 1) / 2) * step for i, key in enumerate(series)}
    half, cap = 0.11, 0.04
    body = []
    for name, style in series.values():
        body += [draw.swatch(f"{style}, draw={draw.FILL_OUTLINE}"), f"\\addlegendentry{{{name}}}"]
    body += [
        "\\addlegendimage{only marks, mark=*, mark size=1.6pt, mark options={fill=black, draw=white, line width=0.4pt}}",
        "\\addlegendentry{one seed}",
        "\\addlegendimage{black, line width=0.6pt}",
        "\\addlegendentry{95\\% $t$ interval}",
    ]
    has_counted = any("runs" in row for _, cells in groups for row in cells.values())
    if has_counted:
        body += [
            "\\addlegendimage{black, dashed, line width=0.6pt}",
            "\\addlegendentry{95\\% Wilson interval}",
        ]
    for gx, (_, cells) in enumerate(groups, start=1):
        for key, row in cells.items():
            x = gx + offsets[key]
            style = f"{series[key][1]}, draw={draw.FILL_OUTLINE}"
            body.append(draw.box(x - half, 0, x + half, row["mean"], style))
            low, high = row["ci_low"], row["ci_high"]
            # a counted row (share of runs judged successful) has a Wilson whisker, a run count, no seed dots
            counted = "runs" in row
            if high > low:
                whisker = "black, line width=0.6pt"
                body += [
                    draw.line([(x, low), (x, high)], whisker + (", dashed" if counted else "")),
                    draw.line([(x - cap, low), (x + cap, low)], whisker),
                    draw.line([(x - cap, high), (x + cap, high)], whisker),
                ]
            if counted:
                label = f"{row['successes']}/{row['runs']}"
                body.append(draw.node(x, high + 0.015, label, "anchor=south, font=\\tiny"))
                continue
            for dx, seed in zip((-0.06, 0.0, 0.06), SEEDS, strict=True):
                body.append(
                    f"\\filldraw[fill=black, draw=white, line width=0.4pt] {draw.cs(x + dx, row[f'seed{seed}'])} circle (1.6pt);"
                )
    for first, last, title in sections:
        body.append(draw.node((first + last) / 2, 1.03, title, "anchor=south, font=\\scriptsize"))
        if first > 1:
            body.append(
                draw.line(
                    [(first - 0.5, 0), (first - 0.5, 1.16)], "black!40, dashed, line width=0.4pt"
                )
            )
    n = len(groups)
    labels = ",".join(f"{{{label}}}" for label, _ in groups)
    options = (
        f"height=6cm, xmin=0.45, xmax={n + 0.55}, ymin=0, ymax=1.16, "
        f"xtick={{{','.join(str(i) for i in range(1, n + 1))}}}, xticklabels={{{labels}}}, "
        "xticklabel style={align=center, font=\\scriptsize}, xtick style={draw=none}, "
        "ytick={0,0.2,0.4,0.6,0.8,1}, yticklabel style={/pgf/number format/fixed, /pgf/number format/precision=1}, "
        "ylabel={judged success}, ymajorgrids, major grid style={black!12}, "
        f"legend style={{at={{(0.5,1.03)}}, anchor=south, legend columns={3 if narrow or has_counted else 5}}}"
    )
    return draw.picture(options, body, left=1.6, right=7.0 if narrow else 0.0)


def groups_of(rows, keys, series_key="arm"):
    return [(LABELS[key[-1]], cells) for key, cells in by_place(rows, keys, series_key).items()]


def write_figures(tests):
    t1, t2, t3, t4, t5 = tests
    zero_shot = [
        ("ZC zero-shot\\\\(trained on ZA+ZB)", {r["arm"]: r for r in t4}),
        (
            "ZC trained on ZC\\\\(test 2, control)",
            {r["arm"]: r for r in t2 if r["card"] == "xland-zc"},
        ),
    ]
    figures = {
        "fig-armfm-paper": fig_bars(
            groups_of(t1, ["card"]), ARM_SERIES, [(1, 3, "1.5M steps"), (4, 6, "5M steps")]
        ),
        "fig-xland-single": fig_bars(groups_of(t2, ["card"]), ARM_SERIES, [], narrow=True),
        "fig-xland-mixes": fig_bars(
            groups_of(t3, ["mix", "card"]),
            ARM_SERIES,
            [(1, 3, "3-task mix, judged per card"), (4, 8, "5-task mix, judged per card")],
        ),
        "fig-xland-zero-shot": fig_bars(zero_shot, ARM_SERIES, [], narrow=True),
        "fig-mix5-ablations": fig_bars(
            groups_of(t5, ["card"], "variant"),
            VARIANT_SERIES,
            [(1, 5, "5-task mix, ARM-FM, judged per card")],
        ),
    }
    for name, text in figures.items():
        (FIGURES / f"{name}.tex").write_text(text, encoding="utf-8")


def fixed_map_note(t1):
    """Lines on the counted DoorKey 16x16 fixed row: how a run counts, and the first runs against all."""
    farm, arm_fm, no_rm = (next(r for r in t1 if "runs" in r and r["arm"] == arm) for arm in ARMS)
    first = len(FIXED_SUITES[ORIGINAL_SUITE])
    n, wins = farm["runs"], farm["successes"]
    # the wording below holds only while the full runs tie and the first runs put FARM behind
    assert (arm_fm["runs"], arm_fm["successes"]) == (n, wins), (farm, arm_fm)
    assert farm["original_successes"] < arm_fm["original_successes"], (farm, arm_fm)
    interval = f"{farm['mean']:.2f} [{farm['ci_low']:.2f}, {farm['ci_high']:.2f}]"
    return [
        f"**DoorKey 16x16 fixed, {n} training runs per method.** FARM and ARM-FM have {n} runs each: the first",
        f"{first} from suite `armfm-paper`, the other {n - first} from suite `armfm-paper-rerun` (same card, machines,",
        "`ppo.yaml` and 5M steps; runs file `experiments/benchmark/armfm-paper/runs-doorkey-fixed-seeds.yaml`).",
        f"No RM keeps its original {no_rm['runs']} runs ({no_rm['successes']} of {no_rm['runs']}). The judge plays the one map once, so a run",
        "counts as a success when that episode is judged solved (`mean_judged_success` = 1: goal reached, every",
        "expected clause holds) and scores 0 otherwise. The row counts such runs, with a 95% Wilson interval.",
        "",
        f"With the first {first} runs FARM looked worse on this map ({farm['original_successes']} of {first} against "
        f"{arm_fm['original_successes']} of {first});",
        f"with {n} runs both succeed {wins} times ({interval} each), so the gap was run-to-run variance on a hard",
        f"fixed layout. The card's task, LTL and both machines: [cards.md](cards.md#{FIXED_CARD}).",
    ]


def write_results(tests, stuck):
    t1, t2, t3, t4, t5 = tests
    lines = [
        "# ARM-FM baseline results (option B)",
        "",
        "Written by `build.py` from the raw run folders under `outputs/runs/`; do not edit. Score: the judge's",
        "`mean_judged_success` of each seed's run (share of judged episodes the judge counts as solved). Every cell",
        "has exactly seeds 1, 2 and 3, except the DoorKey 16x16 fixed row of test 1 (counted over runs, see there).",
        "The CI is over the 3 seeds: Student t with n - 1 = 2 degrees of freedom,",
        "clipped to [0, 1]. Every card's task, LTL and both machines: [cards.md](cards.md). The 22 generated",
        "machines (11 FARM, 11 ARM-FM) passed the B4 gate: [evidence/b4-gate.md](evidence/b4-gate.md).",
        "",
        "## Test 1: ARM-FM paper tasks (MiniGrid, suite `armfm-paper`)",
        "",
        "Each run judged by its own judge. A fixed-map card trains and is judged on its one map, so its judge",
        "plays 1 episode and scores 0 or 1.",
        "",
        *table(t1, ["card", "steps", "episodes"], ARM_SERIES),
        "",
        *fixed_map_note(t1),
        "",
        "One failed FARM `armfm-doorkey-16x16-fixed` run, recounted from its `episodes.csv`: all "
        f"{stuck['episodes']} training episodes ran",
        f"to the step limit ({DOORKEY16_LIMIT}) without reaching the goal, {stuck['ended_in']['u1']} in machine "
        f"state u1 (key held) and {stuck['ended_in']['u0']} in u0 (no key);",
        "none opened the door. Other FARM runs of the card solve the same map on the same machine: an",
        "exploration failure of this run, not a machine fault.",
        "",
        "## Test 2: XLand single tasks (suite `xland`)",
        "",
        *table(t2, ["card", "steps", "episodes"], ARM_SERIES),
        "",
        "## Test 3: XLand mixes, judged per member card",
        "",
        "One policy per mix and seed, judged on each member card; the machine arms with their own machine of that",
        "card.",
        "",
        *table(t3, ["mix", "card", "steps", "episodes"], ARM_SERIES),
        "",
        "## Test 4: zero-shot on ZC",
        "",
        "Trained on the mix ZA+ZB, judged on the unseen ZC (machine arms with their own ZC machine). The runs",
        "trained on ZC itself are in test 2.",
        "",
        *table(t4, ["trained_on", "card", "steps", "episodes"], ARM_SERIES),
        "",
        "## Test 5: ARM-FM ablations on the 5-task mix",
        "",
        "ARM-FM only, judged per member card with the ARM-FM machine. Default = the ARM-FM mix5 runs of test 3;",
        "no embeddings = `rm_state_encoding: none` (the machine pays, the policy does not see its state); no RM",
        "reward = `reward_source: env_rm_state` (the environment alone pays, the machine only feeds its state",
        "and ends no episode).",
        "",
        *table(t5, ["card", "steps", "episodes"], VARIANT_SERIES, "variant"),
        "",
    ]
    (ENTRY / "results.md").write_text("\n".join(lines), encoding="utf-8")


def tasks_by_card():
    out = {}
    for suite in ("armfm-paper", "xland"):
        cards = json.loads((BENCH / suite / "tasks.json").read_text(encoding="utf-8"))["cards"]
        out |= {card["id"]: card for card in cards}
    return out


def clause_lines(clauses):
    return [
        f"- {pattern}({', '.join(args)}) {priority}: `{pretty_ltlf(ltlf_of(pattern, args))}`"
        for pattern, args, priority in clauses
    ]


def world_text(env):
    ruleset = env["env_kwargs"].get("ruleset")
    world = f"`{env['gym_id']}`" + (f", ruleset `{ruleset}`" if ruleset else "")
    if env["layout"] == "fixed":
        return f"{world}, one fixed map (layout seed {env['layout_seed']})"
    return f"{world}, a new map each episode"


def write_cards(machines, appears):
    tasks = tasks_by_card()
    shown = {}
    lines = [
        "# Cards of the ARM-FM baseline",
        "",
        "Written by `build.py`; do not edit. Per card: the task in plain words (`tasks.json`), the card's expected",
        "clauses with their LTLf, any other accepted reading, and the FARM and ARM-FM machines its runs trained or",
        "were judged on (`reward_machine.txt`, verbatim). No-RM runs use no machine.",
    ]
    for card in appears:
        task = tasks[card]
        lines += [
            "",
            f"## {card}",
            "",
            f"**Task:** {task['task']}",
            "",
            f"**World:** {world_text(task['env'])}.",
        ]
        lines += [
            "",
            f"**Results:** {'; '.join(appears[card])}.",
            "",
            "**LTL** (expected clauses):",
        ]
        lines += clause_lines(task["expect"])
        for number, reading in enumerate(task["also_ok"], start=1):
            lines += ["", f"**Also accepted, reading {number}:**", *clause_lines(reading)]
        for arm, name in (("farm", "FARM"), ("arm-fm", "ARM-FM")):
            bundle = machines.of[card][arm]
            if bundle in shown:
                lines += [
                    "",
                    f"**{name} machine:** the one of [{shown[bundle]}](#{shown[bundle]}) (`{bundle}`).",
                ]
                continue
            shown[bundle] = card
            text = (REPO / bundle / "reward_machine.txt").read_text(encoding="utf-8").rstrip()
            lines += [
                "",
                f"**{name} machine** (`{bundle}/reward_machine.txt`):",
                "",
                "```text",
                text,
                "```",
            ]
    (ENTRY / "cards.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def where_cards_appear(tests):
    """{card: [the tests that show it]}, cards in order of first appearance."""
    t1, t2, t3, t4, t5 = tests
    places = [(row["card"], "test 1") for row in t1]
    places += [(row["card"], "test 2") for row in t2]
    places += [(row["card"], f"test 3 ({row['mix']})") for row in t3]
    places += [(card, "test 4 (training mix)") for card in t4[0]["trained_on"].split("+")]
    places += [(row["card"], "test 4 (zero-shot target)") for row in t4]
    places += [(row["card"], "test 5") for row in t5]
    appears = defaultdict(list)
    for card, place in places:
        if place not in appears[card]:
            appears[card].append(place)
    return appears


# ========= Main =========
DATA.mkdir(exist_ok=True)
FIGURES.mkdir(exist_ok=True)
MACHINES = Machines()
TESTS = (
    own_judge_rows("armfm-paper", PAPER_CARDS, MACHINES),
    own_judge_rows("xland", SINGLE_CARDS, MACHINES),
    test3_rows(MACHINES),
    test4_rows(MACHINES),
    test5_rows(MACHINES),
)
STUCK = stuck_recount()
# u1 = key held; every door-open state lies past it, so u0 and u1 alone mean the door never opened
assert STUCK["timed_out"] == STUCK["episodes"] and set(STUCK["ended_in"]) <= {"u0", "u1"}, STUCK
CSV_NAMES = (
    "test1-armfm-paper",
    "test2-xland-single",
    "test3-xland-mixes",
    "test4-zero-shot-zc",
    "test5-mix5-ablations",
)
for csv_name, test_rows in zip(CSV_NAMES, TESTS, strict=True):
    write_csv(csv_name, test_rows)
write_results(TESTS, STUCK)
write_cards(MACHINES, where_cards_appear(TESTS))
write_figures(TESTS)
for csv_name, test_rows in zip(CSV_NAMES, TESTS, strict=True):
    print(csv_name)
    for row in test_rows:
        place = " ".join(str(row[k]) for k in ("variant", "mix", "card", "arm") if k in row)
        print(f"  {place}: {cell_text(row)}")
print("recount:", STUCK)
print("all assertions passed")
