"""Recount the Lanes training runs of the lanes-spacing entry into ``evidence/runs.json``.

One record per finished run (a folder with a ``judge.json``) of the two main cards (``lanes-guard``,
``lanes-rules``) and of the two cards the page leaves out, in the counted world (lane spacing 4:
suites ``forcing`` and ``templates``) and in the two closer-lane worlds (spacing 2 and 1: suite
``lanes-spacing``). The arms are FARM (``farm``), FARM with the world's kill reward added
(``farm-both``, the main cards only, suite ``lanes-both``), no reward machine (``no-rm``) and ARM-FM
(``arm-fm``, the left-out card ``tpl-existence-two-5-nogoal`` only). Runs are read from
``outputs/runs/bench__<suite>__<card>__<arm>__ppo/<run>/``; folders with a dot in the name are
skipped. Each record holds the judge's means recounted from its 100 test episodes, the events of
those episodes counted from the saved per-step labels (``agent-traces/``, nothing is replayed), and
the run's settings (``config.yaml``).

Usage, from the repository root inside RM_RL_env:
    python -I docs/paper/lanes-spacing/check/collect.py
"""

import json
from collections import Counter
from pathlib import Path

import yaml

ENTRY = Path(__file__).resolve().parents[1]
ROOT = ENTRY.parents[2]
RUNS = ROOT / "outputs/runs"
OUT = ENTRY / "evidence/runs.json"
SPACINGS = (4, 2, 1)  # lane spacing; 4 is the counted world
MAIN_CARDS = ("lanes-guard", "lanes-rules")
LEFT_OUT_CARDS = ("tpl-absence-soft-1-nogoal", "tpl-existence-two-5-nogoal")
ARMS = ("farm", "farm-both", "no-rm", "arm-fm")
EVENTS = ("top_breach", "side_breach", "plant_trampled", "zombie_killed")
EPISODES = 100
# Config keys that differ between runs by design: world, method, run, code and machine. Every
# other key must be the same in all runs of the entry.
OWN_KEYS = (
    "exp_name",
    "yaml_config_name",
    "seed",
    "layout_seed",
    "env_kwargs",
    "reward_source",
    "bundle",
    "time_limit_penalty",
    "git_head",
    "device",
)


def suite_and_card(base: str, spacing: int, arm: str) -> tuple[str, str]:
    """The suite and the card id a base card trained under at one lane spacing, for one arm."""
    if arm == "farm-both":  # one suite holds all three spacings, copies named as in lanes-spacing
        return "lanes-both", base if spacing == 4 else f"{base}-spacing{spacing}"
    if spacing == 4:
        return ("forcing" if base in MAIN_CARDS else "templates"), base
    return "lanes-spacing", f"{base}-spacing{spacing}"


def run_folders(suite: str, card: str, arm: str) -> list[Path]:
    """The run folders of one card and arm, in run order; none when the arm never ran it."""
    method = "farm" if arm == "farm-both" else arm  # the suite name tells the two FARM sets apart
    group = RUNS / f"bench__{suite}__{card}__{method}__ppo"
    if not group.is_dir():
        return []
    return [p for p in sorted(group.glob("seed*-*")) if "." not in p.name and p.is_dir()]


def trained_in(folder: Path) -> Path:
    """The folder whose agent this run judges: its own, or the owner of a shared no-RM run."""
    shared = folder / "shared-run.json"
    return Path(json.loads(shared.read_text())["owner_folder"]) if shared.exists() else folder


def count_events(folder: Path, judge: dict) -> dict:
    """Events of the saved test episodes, counted from their labels, checked against the judge.

    A verdict ``broken@k`` of the judge must match the first step ``k`` (1-based) where the
    clause's event is true in the labels, and ``holds`` must match no such step.
    """
    totals: Counter = Counter()
    with_event: Counter = Counter()
    ends_on_top_breach = 0
    for episode in judge["per_episode"]:
        labels = json.loads((folder / episode["file"]).read_text())["labels"]
        assert len(labels) == episode["length"], (folder, episode["file"])
        for event in EVENTS:
            steps = [i for i, step in enumerate(labels) if step[event]]
            totals[event] += len(steps)
            with_event[event] += bool(steps)
            if event == "top_breach" and steps and steps[0] == len(labels) - 1:
                ends_on_top_breach += 1
        for verdict, clause in zip(episode["verdicts"], judge["expect"], strict=True):
            steps = [i for i, step in enumerate(labels) if step[clause["clause"][1][0]]]
            expected = f"broken@{steps[0] + 1}" if steps else "holds"
            assert verdict == expected, (folder, episode["file"], verdict, expected)
    return {
        "events_total": dict(totals),
        "episodes_with_event": dict(with_event),
        "episodes_ending_on_top_breach": ends_on_top_breach,
    }


def record(folder: Path, base: str, spacing: int, arm: str, *, traces: bool) -> dict:
    """Everything the page uses from one finished run folder."""
    suite, card = suite_and_card(base, spacing, arm)
    judge = json.loads((folder / "judge.json").read_text())
    summary = json.loads((folder / "summary.json").read_text())
    config = yaml.safe_load((folder / "config.yaml").read_text())
    episodes = judge["per_episode"]
    # Recount the judge's means from its episodes; the page quotes the recounts.
    judged = sum(e["judged_success"] for e in episodes)
    assert len(episodes) == judge["episodes"] == EPISODES, folder
    assert judged / EPISODES == judge["mean_judged_success"], folder
    owner = trained_in(folder)
    bundle, judge_bundle = config["bundle"], judge["rm_bundle"]
    return {
        "card": base,
        "spacing": spacing,
        "arm": arm,
        "suite": suite,
        "card_id": card,
        "run": folder.name,
        "index": int(folder.name.split("-")[0].removeprefix("seed")),
        "trained_in": f"{owner.parent.name}/{owner.name}",
        "judge_card": judge["id"],
        "judge_bundle": None
        if judge_bundle is None
        else str(judge_bundle).removeprefix(f"{ROOT}/"),
        "judged_passed": judged,
        "mean_judged_success": judged / EPISODES,
        "mean_length": sum(e["length"] for e in episodes) / EPISODES,
        "hard_breaks": sum(e["hard_breaks"] for e in episodes),
        "soft_breaks": sum(e["soft_breaks"] for e in episodes),
        "steps": summary["total_env_steps"],
        "reward_source": config["reward_source"],
        "time_limit_penalty": config["time_limit_penalty"],
        "bundle": None if bundle is None else str(bundle).removeprefix(f"{ROOT}/"),
        "env_kwargs": config["env_kwargs"],
        "device": config["device"],
        "git_head": config["git_head"][:8]
        + ("-dirty" if config["git_head"].endswith("dirty") else ""),
        "settings": {k: v for k, v in config.items() if k not in OWN_KEYS},
        **(count_events(folder, judge) if traces else {}),
    }


def collect() -> dict:
    """Every finished run of the entry's cards, plus the run folders that have no judge yet."""
    runs, skipped = [], []
    for base in (*MAIN_CARDS, *LEFT_OUT_CARDS):
        for spacing in SPACINGS:
            for arm in ARMS:
                suite, card = suite_and_card(base, spacing, arm)
                for folder in run_folders(suite, card, arm):
                    if (folder / "judge.json").exists():
                        runs.append(record(folder, base, spacing, arm, traces=base in MAIN_CARDS))
                    else:
                        skipped.append(f"{suite}/{card}/{arm}/{folder.name}")
    # One settings dict for the whole entry: the page lists the keys above as the ones that differ.
    settings = runs[0].pop("settings")
    for run in runs[1:]:
        assert run.pop("settings") == settings, run["run"]
    return {"settings": settings, "runs": runs, "skipped_without_judge": skipped}


if __name__ == "__main__":
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(collect(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
