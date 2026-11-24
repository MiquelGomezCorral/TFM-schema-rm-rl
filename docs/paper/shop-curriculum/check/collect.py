"""Recount the shop training runs from their raw folders into ``evidence/runs.json``.

One record per finished run (a folder with a ``judge.json``) of every PPO suite named, read from
``outputs/runs/bench__<suite>__<card>__<arm>__ppo/<run>/``: the judge's means (recounted from its
100 episodes), the world switches (``stages.csv``), the run's settings (``config.yaml``) and a
training curve (``episodes.csv``, mean orders served per training episode in 100,000-step bins).
The arm is ``farm`` except for the no-reward-machine suite (``ARMS``). Folders with a dot in the
name are skipped. Only the cards of the two rungs of the entry are kept (``ENTRY_CARDS``: the plain
card and its curriculum, back-fall, grow and size copies); the other ladder rungs, such as the siren
cards, have their own task and machine and are not part of it.

Usage, from the repository root inside RM_RL_env:
    python -I docs/paper/shop-curriculum/check/collect.py [SUITE ...]
"""

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

ENTRY = Path(__file__).resolve().parents[1]
ROOT = ENTRY.parents[2]
RUNS = ROOT / "outputs/runs"
OUT = ENTRY / "evidence/runs.json"
SUITES = (
    "shop-ladder-std",
    "shop-ladder",
    "shop-ladder-noslip",
    "shop-curriculum",
    "shop-size",
    "shop-size-std",
    "shop-grow",
    "shop-size-reward",
)
ENTRY_CARDS = re.compile(r"shop-ladder-(order-)?deliver(-curriculum(-back)?|-grow|-[357]x[357])?")
ARMS = {"shop-size-reward": "no-rm"}  # every other suite is FARM
# the no-reward-machine runs are kept at 7x7 only, the size the grow runs end in
SUITE_CARDS = {"shop-size-reward": re.compile(r"shop-ladder-(order-)?deliver-7x7")}
SERVE_WINDOW = 100  # training episodes in the curriculum's switch rule
SERVE_TARGET = 10  # mean orders served over that window
BIN = 100_000  # steps per curve point
TAIL = 1_000_000  # the last steps of a run, for where its training episodes end
CONFIG_KEYS = ("gamma", "ppo_clip_coef", "total_timesteps", "env_kwargs", "env_stages", "bundle")


def rejecting_states(bundle: str) -> list[str]:
    """The machine's ``REJECTING_STATES`` (its -10 well), read from the bundle the run trained on."""
    text = (ROOT / bundle / "reward_machine.txt").read_text()
    line = next(x for x in text.splitlines() if x.startswith("REJECTING_STATES:"))
    return [state.strip() for state in line.split(":")[1].split(",") if state.strip()]


def curve(rows: list[dict]) -> list[list]:
    """``[bin start step, episodes, mean env return]`` per 100,000-step bin of training episodes."""
    bins: dict[int, list[float]] = {}
    for row in rows:
        bins.setdefault(int(row["global_step"]) // BIN, []).append(float(row["env_return"]))
    return [[b * BIN, len(v), round(sum(v) / len(v), 4)] for b, v in sorted(bins.items())]


def first_serving(rows: list[dict]) -> dict:
    """Step of the first served order, and of the first time the last 100 episodes average 10.

    Without the siren the env pays 1 per served order, so ``env_return`` is the orders served.
    """
    returns = [float(r["env_return"]) for r in rows]
    steps = [int(r["global_step"]) for r in rows]
    first = next((s for s, x in zip(steps, returns, strict=True) if x > 0), None)
    window = next(
        (
            steps[i]
            for i in range(SERVE_WINDOW - 1, len(returns))
            if sum(returns[i - SERVE_WINDOW + 1 : i + 1]) / SERVE_WINDOW >= SERVE_TARGET
        ),
        None,
    )
    return {"first_serve_step": first, "first_window_mean_10_step": window}


def first_episodes_served(rows: list[dict]) -> float:
    """Mean orders served over the run's first 100 training episodes (``env_return``, as above)."""
    first = [float(r["env_return"]) for r in rows[:SERVE_WINDOW]]
    assert len(first) == SERVE_WINDOW
    return round(sum(first) / SERVE_WINDOW, 4)


def after_last_switch(rows: list[dict], stages: list[dict]) -> dict | None:
    """Training episodes after the last world switch: how many, mean served, share serving none."""
    if not stages:
        return None
    start = int(stages[-1]["global_step"])
    served = [float(r["env_return"]) for r in rows if int(r["global_step"]) > start]
    return {
        "from_step": start,
        "episodes": len(served),
        "mean_env_return": round(sum(served) / len(served), 4),
        "no_serve_share": round(sum(x == 0 for x in served) / len(served), 4),
    }


def where_episodes_end(rows: list[dict], well: list[str]) -> dict:
    """Share of training episodes ending in the well and the commonest end state, early and late."""
    first = [r for r in rows if int(r["global_step"]) <= BIN]
    last_step = max(int(r["global_step"]) for r in rows)
    last = [r for r in rows if int(r["global_step"]) > last_step - TAIL]
    out = {}
    for name, part in (("first_100k", first), ("last_1m", last)):
        end = Counter(r["final_rm_state"] for r in part).most_common(1)[0]
        out[name] = {
            "episodes": len(part),
            "mean_env_return": round(sum(float(r["env_return"]) for r in part) / len(part), 4),
            "well_share": round(sum(r["final_rm_state"] in well for r in part) / len(part), 4),
            "commonest_end_state": end[0],
            "commonest_end_share": round(end[1] / len(part), 4),
        }
    return out


def record(folder: Path, suite: str, card: str, arm: str) -> dict:
    """Everything the page uses from one finished run folder."""
    judge = json.loads((folder / "judge.json").read_text())
    summary = json.loads((folder / "summary.json").read_text())
    config = yaml.safe_load((folder / "config.yaml").read_text())
    episodes = judge["per_episode"]
    rows = list(csv.DictReader((folder / "episodes.csv").open()))
    stages_file = folder / "stages.csv"
    stages = list(csv.DictReader(stages_file.open())) if stages_file.exists() else []
    # Recount the judge's means from its episodes; the page quotes the recounts.
    judged = sum(e["judged_success"] for e in episodes)
    served = sum(e["served_count"] for e in episodes)
    assert len(episodes) == judge["episodes"] == 100, folder
    assert judged / 100 == judge["mean_judged_success"], folder
    assert round(served / 100, 2) == judge["mean_served_count"], folder
    machine = config["bundle"]  # none in the no-reward-machine arm
    assert (machine is None) == (arm == "no-rm"), folder
    well = rejecting_states(machine) if machine else []
    final_eval = summary["final_eval"]
    return {
        "suite": suite,
        "card": card,
        "arm": arm,
        "run": folder.name,
        "judge_card": judge["id"],
        "judge_bundle": judge["rm_bundle"] and judge["rm_bundle"].removeprefix(f"{ROOT}/"),
        "judged_episodes": len(episodes),
        "judged_passed": judged,
        "mean_judged_success": judged / 100,
        "mean_served": round(served / 100, 4),
        "judged_no_serve": sum(e["served_count"] == 0 for e in episodes),
        "hard_breaks": sum(e["hard_breaks"] for e in episodes),
        "soft_breaks": sum(e["soft_breaks"] for e in episodes),
        "hard_open": sum(e["hard_open"] for e in episodes),
        # Without the siren the env pays 1 per served order, so the curve's env return is orders served.
        "env_return_is_served": all(e["env_return"] == e["served_count"] for e in episodes),
        "steps": summary["total_env_steps"],
        "git_head": config["git_head"][:8]
        + ("-dirty" if config["git_head"].endswith("dirty") else ""),
        **first_serving(rows),
        "first_100_served": first_episodes_served(rows),
        "world_stage": summary.get("world_stage"),
        "world_final_stage": summary.get("world_final_stage"),
        "final_eval_rm_return": final_eval.get("mean_rm_return"),
        # the run's own 100-episode evaluation at the end: greedy actions, then sampled actions
        "final_eval_served": final_eval["mean_env_return"],
        "final_eval_sampled_served": final_eval.get("sampled_mean_env_return"),
        "config": {key: config.get(key) for key in CONFIG_KEYS}
        | {"bundle": machine and machine.removeprefix(f"{ROOT}/")},  # no home-folder path
        "stages": [
            {
                "step": int(s["global_step"]),
                "stage": int(s["stage"]),
                "served": float(s["mean_served"]),
                "caught": float(s["caught_share"]) if s["caught_share"] else None,
            }
            for s in stages
        ],
        "after_last_switch": after_last_switch(rows, stages),
        "well_states": well,
        "ends": where_episodes_end(rows, well) if machine else None,
        "curve": curve(rows),
    }


def collect(suites: tuple[str, ...]) -> dict:
    runs, skipped = [], []
    for suite in suites:
        arm = ARMS.get(suite, "farm")
        wanted = SUITE_CARDS.get(suite, ENTRY_CARDS)
        for folder in sorted(RUNS.glob(f"bench__{suite}__*__{arm}__ppo")):
            if "." in folder.name:
                continue
            card = folder.name.split("__")[2]
            if not wanted.fullmatch(card):
                continue
            for run in sorted(folder.glob("seed*-*")):
                if "." in run.name or not run.is_dir():
                    continue
                if (run / "judge.json").exists():
                    runs.append(record(run, suite, card, arm))
                else:
                    skipped.append(f"{suite}/{card}/{run.name}")
    return {"suites": list(suites), "runs": runs, "skipped_without_judge": skipped}


if __name__ == "__main__":
    suites = tuple(sys.argv[1:]) or SUITES
    OUT.write_text(json.dumps(collect(suites), indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {OUT}")
