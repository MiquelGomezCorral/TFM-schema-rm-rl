"""One table of every training run under a runs root. Read-only on the runs, no provider call.

Usage (repository root, `RM_RL_env`):
    PYTHONPATH=app python experiments/benchmark/scripts/results_table.py --out <dir> \
        [--runs-root outputs/runs] [--results judged.jsonl ...]

Reads `<runs-root>/bench__<suite>__<card>__<arm>__ppo/seed<k>-*/` for seeds 1 to 3 and writes
`<out>/tables.csv` (one row per card x arm x seed) and `<out>/tables.md` (the table, what the new
judge changed against `judge.v1.json`, cards that do not learn, and each card's NL task, LTLf and
Reward Machine files). Safe to rerun; it overwrites both files.

Where each column comes from:
- judge columns: the run's `judge.json` (`judged`, `raw judged`, `non-empty`, untested rules, the
  reward split) and its `judge.v1.json`, when the run was judged again, for the change report;
- training eval: `summary.json` (final greedy and sampled success, wall time), `eval.csv` (the first
  step with greedy or sampled success of at least 0.8), `train.csv` and `episodes.csv` (the last 300k
  steps: entropy, explained variance, success, and the share of episodes that lap a cycle of the RM);
- flags: a machine that is too simple, episodes that cannot start, a positive reward cycle in the
  run's ARM-FM machine (from `cycles.py`, read from the bundle in the run's `config.yaml`), farming
  (the RM path laps in at least half of the last-300k-step episodes), a shared no-RM run, and a
  judge that crashed (a `failed` line in a `--results` file written by `judge_runs.py --rejudge`).

A card "does not learn" when all three seeds end below 0.2 greedy success (the no-RM arm: all 0 on a
card an RM arm solves). A card without a goal is expected to end at 0 when its rules hold.
"""

import argparse
import csv
import json
import re
from functools import cache
from pathlib import Path

from cycles import positive_cycles

from scripts.aggregate_suite import judge_columns
from scripts.run_suite import RUNS_PATH
from src.benchmark.declare_judge import ltlf_of
from src.compiler.rm_format import parse_paper_reward_machine

ARM_ORDER = {"no-rm": 0, "arm-fm": 1, "farm": 2}
SEEDS = (1, 2, 3)
TAIL_STEPS = 300_000
LEARNED_LEVEL = 0.2
SUCCESS_LEVEL = 0.8
NO_VALUE = chr(0x2013)  # an en dash, the placeholder of the earlier tables
DRIFT_KEYS = (  # the judge's test-episode means that a new judge must leave as they were
    "mean_env_success", "mean_hard_breaks", "mean_soft_breaks", "mean_hard_open", "mean_soft_open",
    "mean_env_return", "mean_rm_return", "mean_length",
)  # fmt: skip


def jload(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def read_rows(path: Path) -> list[dict]:
    try:
        with path.open(newline="", encoding="utf-8") as file:
            return list(csv.DictReader(file))
    except OSError:
        return []


def number(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def mean(values: list) -> float | None:
    values = [value for value in values if value is not None]
    return sum(values) / len(values) if values else None


def f2(value, digits: int = 2) -> str:
    if value is None:
        return NO_VALUE
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def thousands(step: int | None) -> str:
    return "never" if step is None else f"{step / 1000:.0f}k"


def laps(path: str) -> bool:
    """A state seen 3+ times in the episode's RM path: 2+ laps of a cycle."""
    states = path.split()
    return bool(states) and max(states.count(item) for item in set(states)) >= 3


def first_step_at(path: Path, column: str) -> int | None:
    """The first training step at which ``column`` of `eval.csv` reaches `SUCCESS_LEVEL`."""
    for row in read_rows(path):
        value = number(row.get(column))
        if value is not None and value >= SUCCESS_LEVEL:
            return int(float(row["global_step"]))
    return None


def tail(folder: Path, steps: int | None) -> dict:
    """Training means over the last `TAIL_STEPS`: episode success, lap share, entropy, variance."""
    cutoff = (steps or 0) - TAIL_STEPS
    episodes = [
        r for r in read_rows(folder / "episodes.csv") if int(float(r["global_step"])) >= cutoff
    ]
    updates = [r for r in read_rows(folder / "train.csv") if int(float(r["global_step"])) >= cutoff]
    return {
        "episodes": len(episodes),
        "success": mean([float(r["exited"] == "True") for r in episodes]),
        "laps": mean([float(laps(r.get("rm_path") or "")) for r in episodes]),
        "entropy": mean([number(r["entropy"]) for r in updates]),
        "explained_variance": mean([number(r["explained_variance"]) for r in updates]),
    }


def seed_folder(exp: Path, seed: int) -> Path | None:
    """The run folder of a seed: one that finished, else the last one started."""
    best = None
    for path in sorted(exp.glob(f"seed{seed}-*")):
        if "." in path.name or not path.is_dir():
            continue
        if best is None or (path / "summary.json").exists():
            best = path
    return best


def bundle_of(folder: Path) -> str | None:
    """The bundle folder the run trained on, from its `config.yaml`, or None (no-RM arm)."""
    try:
        text = (folder / "config.yaml").read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"^bundle: (.+)$", text, re.MULTILINE)
    return match.group(1) if match and match.group(1) != "null" else None


@cache
def machine_laps(bundle: str | None) -> tuple:
    """The positive reward cycles of the bundle's machine (empty: none, or no machine)."""
    machine = Path(bundle or "") / "reward_machine.txt"
    if not bundle or not machine.is_file():
        return ()
    return tuple(positive_cycles(parse_paper_reward_machine(machine.read_text(encoding="utf-8"))))


def split(judge: dict, prefix: str) -> str:
    total, pos, neg = (
        judge.get(f"mean_{prefix}_return{s}") for s in ("", "_positive", "_negative")
    )
    if total is None:
        return NO_VALUE
    return f"{total:.2f} (+{pos:.2f} / {neg:.2f})" if pos is not None else f"{total:.2f}"


def judge_file_state(judge: dict, old: dict, crashed: bool) -> str:
    if "machine_too_simple" not in judge:  # a failed row counts only while the folder is not judged
        if crashed:
            return "judge crashed, old judge kept" if judge else "judge crashed, no judge file"
        return "OLD format (not re-judged)" if judge else "none"
    return "re-judged (v1 kept)" if old else "judged new"


def flags_of(
    judge: dict, arm: str, cycles: tuple, farming: float | None, shared: str | None
) -> list:
    flags = []
    cannot = judge.get("mean_cannot_start")
    if judge.get("machine_too_simple"):
        flags.append("machine too simple")
    if cannot is not None and cannot > 0.5:
        flags.append(f"episodes cannot start {cannot:.2f}")
    elif cannot:
        flags.append(f"cannot-start share {cannot:.2f} (below 0.5)")
    if arm == "arm-fm" and cycles:
        flags.append("positive cycle in machine")
    if farming is not None and farming >= 0.5:
        flags.append(f"farming: RM path laps in {farming:.2f} of last-300k episodes")
    if shared:
        flags.append(f"shared no-RM run of {shared.replace('bench__', '')}")
    return flags


def drifted_keys(old: dict, judge: dict) -> list[str]:
    """The test-episode means of `DRIFT_KEYS` that differ between `judge.v1.json` and `judge.json`."""
    return [
        key
        for key in DRIFT_KEYS
        if old and key in old and abs((old[key] or 0) - (judge.get(key) or 0)) > 1e-9
    ]


def run_row(exp: Path, seed: int, folder: Path, card: dict, crashed: set) -> dict:
    """The row of one run folder: judge, training eval, curve and flags."""
    arm = exp.name.split("__")[3]
    summary, judge, old = (
        jload(folder / name) for name in ("summary.json", "judge.json", "judge.v1.json")
    )
    resources = jload(folder / "resources.json")
    shared = jload(folder / "shared-run.json").get("owner_exp_name")
    final = summary.get("final_eval", {})
    new_format = "machine_too_simple" in judge
    steps = summary.get("total_env_steps")
    curve = tail(folder, steps) if summary and arm != "no-rm" else {}
    cycles = machine_laps(bundle_of(folder)) if arm == "arm-fm" else ()
    state = judge_file_state(judge, old, str(folder) in crashed)
    flags = flags_of(judge, arm, cycles, curve.get("laps"), shared)
    if state.startswith("judge crashed"):
        flags.append(state)
    cols = judge_columns(folder) if new_format else {}
    return {
        "suite": exp.name.split("__")[1],
        "card": card["id"],
        "arm": arm,
        "seed": seed,
        "env": (card.get("env") or {})
        .get("gym_id", "?")
        .replace("MiniGrid-", "")
        .replace("-v0", ""),
        "goal": card.get("goal"),
        "run": "training" if not summary else "finished",
        "steps": steps or "",
        "wall_min": ((summary.get("wall_seconds") or resources.get("wall_time_s") or 0) / 60)
        or None,
        "step_greedy_0.8": first_step_at(folder / "eval.csv", "exit_rate") if summary else None,
        "step_sampled_0.8": first_step_at(folder / "eval.csv", "sampled_exit_rate")
        if summary
        else None,
        "judge_file": state,
        "judged": judge.get("mean_judged_success"),
        "raw_judged": judge.get("mean_raw_judged_success"),
        "non_empty": judge.get("mean_non_empty_success"),
        "untested_rules": cols.get("untested_rules", ""),
        "env_success_test": judge.get("mean_env_success"),
        "greedy_final": final.get("exit_rate"),
        "sampled_final": final.get("sampled_exit_rate"),
        "hard_breaks": judge.get("mean_hard_breaks"),
        "soft_breaks": judge.get("mean_soft_breaks"),
        "env_return_total_pos_neg": split(judge, "env") if new_format else NO_VALUE,
        "rm_return_total_pos_neg": split(judge, "rm")
        if new_format and arm != "no-rm"
        else NO_VALUE,
        "too_simple": judge.get("machine_too_simple"),
        "cannot_start_share": judge.get("mean_cannot_start"),
        "farming_laps": curve.get("laps"),
        "flags": "; ".join(flags),
        "old_judged": old.get("mean_judged_success"),
        "drift": drifted_keys(old, judge) if new_format else [],
        "path": str(folder),
        "shared_owner": shared or "",
        "exp": exp.name,
    }


def table_line(row: dict) -> str:
    run = row["run"] if not row["steps"] else f"{row['run']} {int(row['steps']) // 1000}k"
    untested = row["untested_rules"] or ("none" if row["non_empty"] is not None else NO_VALUE)
    wall = NO_VALUE if row["wall_min"] is None else f"{row['wall_min']:.0f}"
    breaks = f"{f2(row['hard_breaks'])} / {f2(row['soft_breaks'])}"
    return (
        f"| {row['suite']} | {row['card']} | {row['arm']} | {row['seed']} | {row['env']} | {run} "
        f"| {row['judge_file']} | {f2(row['judged'])} | {f2(row['raw_judged'])} "
        f"| {f2(row['non_empty'])} | {untested} | {f2(row['env_success_test'])} "
        f"| {f2(row['greedy_final'])} / {f2(row['sampled_final'])} "
        f"| {thousands(row['step_greedy_0.8'])} / {thousands(row['step_sampled_0.8'])} "
        f"| {breaks} | {row['env_return_total_pos_neg']} | {row['rm_return_total_pos_neg']} "
        f"| {wall} | {row['flags']} |"
    )


def change_report(table: list[dict]) -> dict[str, list[str]]:
    """What the new judge changed against `judge.v1.json`, in four lists plus the unjudged runs."""
    report = {"changed": [], "empty_pass": [], "first_empty": [], "not_rejudged": []}
    for r in table:
        label = f"{r['card']} / {r['arm']} / seed {r['seed']}"
        empty = (
            r["non_empty"] is not None
            and r["judged"] is not None
            and r["non_empty"] + 1e-9 < r["judged"]
        )
        untested = f"untested: {r['untested_rules'] or 'none listed'}"
        if r["judge_file"].startswith(("judge crashed", "OLD")):
            report["not_rejudged"].append(
                f"- {label}: {r['judge_file']}; judged now shown: {f2(r['judged'])}"
            )
        elif r["old_judged"] is not None and r["judged"] is not None:
            if abs(r["old_judged"] - r["judged"]) > 1e-9:
                why = []
                if r["too_simple"]:
                    why.append(
                        "machine too simple: the start state is final, episodes end at step 1"
                    )
                if r["cannot_start_share"]:
                    why.append(
                        f"cannot-start rule failed {r['cannot_start_share']:.2f} of the episodes"
                    )
                report["changed"].append(
                    f"- {label}: judged {r['old_judged']:.2f} -> {r['judged']:.2f} "
                    f"(raw {f2(r['raw_judged'])}); {'; '.join(why) or 'see judge.json'}"
                )
            elif empty:
                report["empty_pass"].append(
                    f"- {label}: judged {r['judged']:.2f} unchanged, non-empty {r['non_empty']:.2f}; {untested}"
                )
        elif r["judge_file"] == "judged new" and empty:
            report["first_empty"].append(
                f"- {label}: judged {r['judged']:.2f}, non-empty {r['non_empty']:.2f}; {untested}"
            )
    return report


def not_learning(table: list[dict]) -> list[str]:
    """Notes on the cards whose three seeds all ended below `LEARNED_LEVEL`, with the curve tail."""
    arms: dict[tuple, dict[str, list[dict]]] = {}
    for r in table:
        if r["greedy_final"] is not None:
            arms.setdefault((r["suite"], r["card"]), {}).setdefault(r["arm"], []).append(r)
    notes = []
    for (_, card), by_arm in arms.items():
        rm_solved = any(
            max(r["greedy_final"] for r in runs) >= LEARNED_LEVEL
            for arm, runs in by_arm.items()
            if arm != "no-rm"
        )
        for arm, runs in by_arm.items():
            greedy = [r["greedy_final"] for r in runs]
            stuck = (
                all(g == 0 for g in greedy) and rm_solved
                if arm == "no-rm"
                else all(g < LEARNED_LEVEL for g in greedy)
            )
            if len(runs) < len(SEEDS) or not stuck:
                continue
            note = (
                ""
                if runs[0]["goal"]
                else " (no goal: env success 0 is expected when the rules hold)"
            )
            notes.append(
                f"- **{card} / {arm}** greedy final {greedy}; judged success (rules, 100 unseen layouts) "
                f"{f2(mean([r['judged'] for r in runs]))}; goal={runs[0]['goal']}{note}"
            )
            notes += [curve_note(r) for r in runs]
    return notes


def curve_note(r: dict) -> str:
    curve = tail(Path(r["path"]), int(r["steps"] or 0))
    kind = "" if r["arm"] == "no-rm" else (
        " **reward farming**" if (curve["laps"] or 0) >= 0.5 else " no progress (no cycling)"
    )  # fmt: skip
    return (
        f"  - seed {r['seed']}:{kind} last 300k steps: RM path cycles in {f2(curve['laps'])} of episodes, "
        f"episode success {f2(curve['success'])} ({curve['episodes']} episodes), "
        f"entropy {f2(curve['entropy'])}, explained variance {f2(curve['explained_variance'])}"
    )


def card_sections(cards: dict, bundles: dict) -> str:
    nl = ["| card | goal | NL task | LTLf (each declared rule) |", "|---|---|---|---|"]
    rm = ["| card | RM files (`reward_machine.txt`, per arm) | card file |", "|---|---|---|"]
    for card_id in sorted(cards):
        card = cards[card_id]["card"]
        ltl = "<br>".join(
            f"`{c[0]}({', '.join(c[1])})` {c[2]}: `{ltlf_of(tuple(c))['readable']}`"
            for c in card.get("expect") or []
        )
        goal = "goal" if card.get("goal") else "no goal"
        nl.append(f"| {card_id} | {goal} | {card.get('task', '')} | {ltl} |")
        files = "; ".join(
            f"{arm}: `{path}/reward_machine.txt`"
            for arm, path in sorted(bundles.get(card_id, {}).items())
        )
        rm.append(
            f"| {card_id} | {files or 'no-RM arm only (no machine)'} | `{cards[card_id]['card_file']}` |"
        )
    return "\n".join(nl) + "\n\n" + "\n".join(rm)


def collect(runs_root: Path, crashed: set) -> tuple[list[dict], dict, dict]:
    """Every run row, the cards seen, and each card's bundle per arm."""
    table, cards, bundles = [], {}, {}
    for exp in sorted(runs_root.glob("bench__*__ppo")):
        card = jload(exp / "card.json")
        if not card:
            continue
        arm = exp.name.split("__")[3]
        cards.setdefault(card["id"], {"card": card, "card_file": str(exp / "card.json")})
        for seed in SEEDS:
            if (folder := seed_folder(exp, seed)) is None:
                continue
            table.append(run_row(exp, seed, folder, card, crashed))
            if bundle := bundle_of(folder):
                bundles.setdefault(card["id"], {})[arm] = bundle
    table.sort(key=lambda r: (r["suite"], r["card"], ARM_ORDER[r["arm"]], r["seed"]))
    return table, cards, bundles


def markdown(table: list[dict], cards: dict, bundles: dict, runs_root: Path) -> str:
    head = (
        "| suite | card | arm | seed | env | run | judge file | judged | raw judged | non-empty "
        "| untested rules (<50% activated) | env success (judge test) | greedy / sampled (final eval) "
        "| step greedy / sampled >= 0.8 | rule breaks hard / soft per episode | env return total (+ / -) "
        "| RM return total (+ / -) | wall min | flags |\n" + "|---" * 19 + "|"
    )
    report = change_report(table)
    drifted = [
        f"- {r['card']} / {r['arm']} / seed {r['seed']}: {', '.join(r['drift'])}"
        for r in table
        if r["drift"]
    ]
    rejudged = sum(r["judge_file"] == "re-judged (v1 kept)" for r in table)
    none_drifted = (
        "none: env success, hard and soft breaks, open items, env and RM return and length are equal "
        "in every re-judged run"
    )
    return (
        "# Every run, judged with the current judge\n\n"
        f"Runs root `{runs_root}`; one row per card x arm x seed ({len(table)} rows). Made by "
        "`experiments/benchmark/scripts/results_table.py` (read-only).\n\n"
        "- judged = judge's mean judged success after the cannot-start rule; raw judged = before it; non-empty = "
        "judged and every hard clause with a trigger activated.\n"
        "- env success (judge test) = the judge's 100 test episodes (greedy policy); greedy / sampled (final eval) "
        "= the training run's 100-episode final eval (`summary.json`).\n"
        "- reward split = mean per judged episode: total (positive part / negative part). Shared no-RM follower "
        "rows show the owner's training eval and their own judge columns.\n"
        "- flags: machine too simple; episodes cannot start (share above 0.5); positive cycle in the ARM-FM "
        "machine; farming (RM path laps in at least half of the last-300k-step training episodes); shared "
        "no-RM run; judge crashed.\n"
        "- A `judge crashed` row keeps its old-format judge.json (judged shown is the old judge's).\n\n"
        "## Table\n\n" + head + "\n" + "\n".join(table_line(r) for r in table) + "\n\n"
        "## What changed against judge.v1.json\n\n"
        f"Runs compared: {rejudged} re-judged with an old judge.json kept as judge.v1.json.\n\n"
        "### Judged success changed (old -> new)\n\n" + ("\n".join(report["changed"]) or "none") + "\n\n"
        "### Judged success unchanged, non-empty lower (empty pass shown beside)\n\n"
        + ("\n".join(report["empty_pass"]) or "none") + "\n\n"
        "### Empty passes in runs judged for the first time (no judge.v1.json to compare)\n\n"
        + ("\n".join(report["first_empty"]) or "none") + "\n\n"
        "### Other judge means that drifted (should be none)\n\n" + ("\n".join(drifted) or none_drifted) + "\n\n"
        "### Still on the old judge\n\n" + ("\n".join(report["not_rejudged"]) or "none") + "\n\n"
        "## Not learning candidates\n\n"
        "RM arm: 3 seeds all greedy final < 0.2; no-RM arm: all 0 on a card whose RM arm solves.\n\n"
        + ("\n".join(not_learning(table)) or "none") + "\n\n"
        "## Cards: NL task, LTLf, RM files\n\n" + card_sections(cards, bundles) + "\n"
    )  # fmt: skip


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, required=True, help="folder for tables.md, tables.csv")
    parser.add_argument("--runs-root", type=Path, default=RUNS_PATH, help="folder of bench__*")
    parser.add_argument("--results", type=Path, nargs="*", default=[], help="judge_runs.py JSONL")
    args = parser.parse_args()

    crashed = {
        row["folder"]
        for source in args.results
        if source.exists()  # `judge_runs.py --rejudge` writes none when it judged nothing
        for row in map(json.loads, source.read_text(encoding="utf-8").splitlines())
        if row["status"] == "failed"
    }
    table, cards, bundles = collect(args.runs_root, crashed)
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "tables.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, list(table[0]))
        writer.writeheader()
        writer.writerows({**row, "drift": ",".join(row["drift"])} for row in table)
    (args.out / "tables.md").write_text(
        markdown(table, cards, bundles, args.runs_root), encoding="utf-8"
    )
    print(f"{len(table)} rows from {args.runs_root}; wrote {args.out / 'tables.md'} and tables.csv")


if __name__ == "__main__":
    main()
