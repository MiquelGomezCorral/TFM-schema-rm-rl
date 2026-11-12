"""Live check of the service room: schedules, events, determinism, observation and GIFs.

Usage (from the repository root):
    PYTHONPATH=app python experiments/benchmark/scripts/check_service_room.py --out <dir>
    [--seeds 50]

Plays the scripted policy on event seeds 1..N for the four configurations (siren only, box only,
both, neither), plus the wrong-trace variants (``ignore=["siren"]`` on the siren configurations,
``ignore=["box_fall"]`` on the box ones). Writes ``summary.json`` and two GIFs per configuration to
``--out`` and exits non-zero when an expectation fails. It also runs the truth table of
``environment-code.md`` through the labeling loader and compares it with ``reference_labels`` on
scripted and on seeded random-action episodes.
"""

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from minigrid.core.actions import Actions
from minigrid.core.constants import COLOR_TO_IDX, OBJECT_TO_IDX
from minigrid.wrappers import ImgObsWrapper
from PIL import Image, ImageDraw

from scripts.test_rl import FONT, FRAME_MS, LAST_FRAME_MS, LINE_HEIGHT, MIN_WIDTH, RENDERERS
from src.arm_fm.environments import make_environment
from src.arm_fm.runtime import load_labeling_functions
from src.arm_fm.service_room import (
    ENV_ID,
    FIRST_RING_LAST,
    RINGING_COLOR,
    SILENT_COLOR,
    START,
    START_DIR,
    SWITCH_POS,
    cells_of_type,
    reference_labels,
    scripted_policy,
)
from src.models.environment import EnvironmentDescription

ENV_FILE = Path(__file__).resolve().parents[1] / "envs" / "service-room" / "environment.md"
CODE_FILE = ENV_FILE.with_name("environment-code.md")
TABLE_ROW = re.compile(r"^\| `([a-z_]+)` \| `(.+)` \|$", re.MULTILINE)  # | id | expression |
CONFIGS = {
    "siren": {"siren": True, "box": False, "require": ["siren_silent"]},
    "box": {"siren": False, "box": True, "require": ["holding_box"]},
    "both": {"siren": True, "box": True, "require": ["siren_silent", "holding_box"]},
    "neither": {"siren": False, "box": False, "require": []},
}
COUNT_KEYS = ("planned", "fired", "skipped")
GIFS_PER_CONFIG = 2
MIN_EXIT_MOVES = 6
EXIT_MOVES = 10  # layout pin: START to EXIT_POS in the plain room; a layout change must update it
TABLE_SEEDS = 3  # scripted episodes whose every step the truth table is compared on
RANDOM_LIMITS = (8, 8, 60, 60, 60)  # step limits of the seeded random-action episodes; 8 cuts early
UNSEEDED_EPISODES = 5


# ======================================================================================
#                                       ONE EPISODE
# ======================================================================================
def run_episode(
    kwargs: dict, seed: int | None, ignore: tuple = (), frames: list | None = None
) -> dict:
    """Play the scripted policy to the end; ``frames`` collects captioned pictures when given."""
    env = make_environment(ENV_ID, **kwargs)
    _, reset_info = env.reset(seed=seed)
    base = env.unwrapped
    episode = {
        "seed": seed,
        "event_seed": reset_info["event_seed"],
        "actions": [],
        "labels": [],
        "events": [],
        "fall_checks": [],
    }
    if frames is not None:
        frames.append(_frame(base, kwargs, seed, ["reset"]))

    done = False
    while not done:
        action = scripted_policy(env, ignore)
        _, reward, terminated, truncated, info = env.step(action)
        labels = reference_labels(env)
        episode["actions"].append(action)
        episode["labels"].append(labels)
        episode["events"].append(info["events"])
        if labels["box_fell"]:  # after a fall the hands are empty and the box lies next to us
            episode["fall_checks"].append(not labels["holding_box"] and _box_is_adjacent(base))
        done = terminated or truncated
        if frames is not None:
            tail = [f"reward {reward:.3f}"] if done else []
            frames.append(_frame(base, kwargs, seed, [f"step {base.step_count}", *tail]))
    env.close()

    toggles = sum("toggle" in events for events in episode["events"])
    episode.update(
        terminated=bool(terminated),
        reward=float(reward),
        steps=len(episode["actions"]),
        counts=base.event_counts,
        toggles=toggles,
    )
    return episode


def _box_is_adjacent(base) -> bool:
    ax, ay = base.agent_pos
    return any(abs(x - ax) + abs(y - ay) == 1 for x, y in cells_of_type(base, "box"))


def _frame(base, kwargs: dict, seed: int, notes: list[str]) -> Image.Image:
    """The room under caption lines: configuration, seed, the step's events and the state."""
    labels = reference_labels(base)
    events = [name for name in ("ring", "toggle", "fall") if name in base.events_this_step]
    state = []
    if kwargs["siren"]:
        state.append("siren RINGING" if labels["siren_ringing"] else "siren silent")
    if kwargs["box"]:
        state.append("box in hands" if labels["holding_box"] else "box on the floor")
    lines = [
        f"service room · require {kwargs['require'] or 'nothing'} · seed {seed}",
        f"{' · '.join(notes)} · events: {', '.join(events) or 'none'}",
        " · ".join(state) or "plain room",
    ]
    picture = RENDERERS["minigrid"](base)
    canvas = Image.new("RGB", (MIN_WIDTH, picture.height + LINE_HEIGHT * len(lines) + 8), "white")
    canvas.paste(picture, ((canvas.width - picture.width) // 2, canvas.height - picture.height))
    draw = ImageDraw.Draw(canvas)
    for number, text in enumerate(lines):
        draw.text((6, 4 + LINE_HEIGHT * number), text, fill="black", font=FONT)
    return canvas


# ======================================================================================
#                                       SUMMARIES
# ======================================================================================
def summarise(episodes: list[dict]) -> dict:
    """Counts over a batch of episodes: success, reward, steps, events and toggles."""
    counts = {
        kind: {key: sum(e["counts"][kind][key] for e in episodes) for key in COUNT_KEYS}
        for kind in ("ring", "fall")
    }
    rewards = [e["reward"] for e in episodes]
    return {
        "episodes": len(episodes),
        "solved": sum(e["terminated"] and e["reward"] > 0 for e in episodes),
        "reward": {"min": min(rewards), "mean": float(np.mean(rewards)), "max": max(rewards)},
        "steps_mean": float(np.mean([e["steps"] for e in episodes])),
        "event_counts": counts,
        "toggles": sum(e["toggles"] for e in episodes),
        "toggle_ring_mismatches": [
            e["seed"] for e in episodes if e["toggles"] != e["counts"]["ring"]["fired"]
        ],
        "falls_checked": sum(len(e["fall_checks"]) for e in episodes),
        "falls_failing_checks": sum(not ok for e in episodes for ok in e["fall_checks"]),
    }


def shows_a_reaction(episode: dict, kwargs: dict) -> bool:
    """A ring answered by a toggle and/or a fall followed by a new pickup, as the config allows."""
    flat = [name for events in episode["events"] for name in events]
    held = [labels["holding_box"] for labels in episode["labels"]]
    fall_step = next((i for i, e in enumerate(episode["events"]) if "fall" in e), None)
    rings = not kwargs["siren"] or ("ring" in flat and "toggle" in flat)
    falls = not kwargs["box"] or (fall_step is not None and any(held[fall_step + 1 :]))
    return rings and falls


# ======================================================================================
#                                       THE CHECKS
# ======================================================================================
class Report:
    """Named expectations; ``failed`` lists the ones that did not hold."""

    def __init__(self) -> None:
        self.checks: list[dict] = []

    def expect(self, name: str, ok: bool, detail: object = "") -> None:
        self.checks.append({"name": name, "ok": bool(ok), "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail != "" else ""))

    @property
    def failed(self) -> list[str]:
        return [check["name"] for check in self.checks if not check["ok"]]


def check_config(name: str, kwargs: dict, seeds: range, report: Report, out: Path) -> dict:
    episodes = [run_episode(kwargs, seed) for seed in seeds]
    summary = {"kwargs": kwargs, "scripted": summarise(episodes)}
    scripted, counts = summary["scripted"], summary["scripted"]["event_counts"]
    for kind, enabled in (("ring", kwargs["siren"]), ("fall", kwargs["box"])):
        fired, planned = counts[kind]["fired"], counts[kind]["planned"]
        report.expect(
            f"{name}: {kind}s {'fire' if enabled else 'never exist'}",
            fired > 0 if enabled else planned == fired == 0,
            counts[kind],
        )
    report.expect(
        f"{name}: the policy exits with reward > 0 in every episode",
        scripted["solved"] == len(episodes),
        f"{scripted['solved']}/{len(episodes)}, reward {scripted['reward']}",
    )
    report.expect(
        f"{name}: toggles equal fired rings in every episode (no blind toggling)",
        not scripted["toggle_ring_mismatches"],
        f"{scripted['toggles']} toggles, mismatching seeds {scripted['toggle_ring_mismatches']}",
    )
    report.expect(
        f"{name}: after each fall the hands are empty and the box is next to the agent",
        scripted["falls_failing_checks"] == 0,
        f"{scripted['falls_checked']} falls checked",
    )
    replays = [run_episode(kwargs, e["seed"]) for e in episodes]
    different = [
        a["seed"]
        for a, b in zip(episodes, replays, strict=True)
        if (a["actions"], a["labels"]) != (b["actions"], b["labels"])
    ]
    summary["determinism"] = {"replayed": len(replays), "different_seeds": different}
    report.expect(f"{name}: the same seed twice gives identical actions and labels", not different)

    summary["ignore"] = {}
    for reaction, enabled in (("siren", kwargs["siren"]), ("box_fall", kwargs["box"])):
        if enabled:
            summary["ignore"][reaction] = check_wrong_trace(name, kwargs, seeds, reaction, report)
    summary["gifs"] = write_gifs(name, kwargs, episodes, out, report)
    return summary


def check_wrong_trace(name: str, kwargs: dict, seeds: range, reaction: str, report: Report) -> dict:
    episodes = [run_episode(kwargs, seed, (reaction,)) for seed in seeds]
    summary = summarise(episodes)
    if reaction == "siren":  # the first ring comes before the exit can be reached
        wrong = [e["seed"] for e in episodes if e["reward"] != 0]
        check, ok, detail = (
            f"{name}: ignore='siren' earns reward 0 in every episode",
            not wrong,
            f"seeds with reward > 0: {wrong}",
        )
    else:  # a fall that fired leaves the box behind; a fall that did not changes nothing
        wrong = [
            e["seed"] for e in episodes if (e["reward"] == 0) != (e["counts"]["fall"]["fired"] > 0)
        ]
        fired = summary["event_counts"]["fall"]["fired"]
        check, ok, detail = (
            f"{name}: ignore='box_fall' earns reward 0 exactly when a fall fired, and a fall fired",
            not wrong and fired > 0,
            f"{fired} falls fired, inconsistent seeds {wrong}",
        )
    report.expect(check, ok, detail)
    return summary


def write_gifs(name: str, kwargs: dict, episodes: list[dict], out: Path, report: Report) -> list:
    """Replay the first episodes that show the reaction; the policy is deterministic."""
    chosen = [e["seed"] for e in episodes if shows_a_reaction(e, kwargs)][:GIFS_PER_CONFIG]
    files = []
    for seed in chosen:
        frames: list[Image.Image] = []
        run_episode(kwargs, seed, frames=frames)
        path = out / f"{name}-seed{seed}.gif"
        durations = [FRAME_MS] * (len(frames) - 1) + [LAST_FRAME_MS]
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=durations, loop=0)
        files.append(path.name)
    report.expect(f"{name}: GIFs written for episodes that show the reaction", bool(files), files)
    return files


def check_observation(report: Report) -> dict:
    """The switch cell the agent faces is encoded differently while the siren rings."""
    env = ImgObsWrapper(make_environment(ENV_ID, siren=True, require=["siren_silent"]))
    env.reset(seed=1)
    base = env.unwrapped
    base.agent_pos, base.agent_dir = (SWITCH_POS[0] + 1, SWITCH_POS[1]), 2  # facing the switch
    silent = env.observation(base.gen_obs())
    ringing = silent  # stays equal to the silent view if the siren never starts
    for _ in range(FIRST_RING_LAST):
        observation, *_, info = env.step(Actions.done)
        if "ring" in info["events"]:
            ringing = observation
            break
    env.step(Actions.toggle)
    toggled = env.observation(base.gen_obs())

    changed = np.argwhere((silent != ringing).any(axis=-1)).tolist()
    front = [base.agent_view_size // 2, base.agent_view_size - 2]  # the cell in front of the agent
    wall = OBJECT_TO_IDX["wall"]
    expected_silent = [wall, COLOR_TO_IDX[SILENT_COLOR], 0]
    expected_ringing = [wall, COLOR_TO_IDX[RINGING_COLOR], 0]
    result = {
        "changed_cells": changed,
        "silent_encoding": silent[front[0], front[1]].tolist(),
        "ringing_encoding": ringing[front[0], front[1]].tolist(),
    }
    report.expect(
        "observation: only the switch cell changes while ringing, as a wall in another colour",
        changed == [front]
        and result["silent_encoding"] == expected_silent
        and result["ringing_encoding"] == expected_ringing,
        result,
    )
    report.expect("observation: toggling restores the silent encoding", (toggled == silent).all())
    return result


def _table_episodes():
    """Named reset environments with their action rule: scripted ones, then seeded random ones."""
    for seed in range(1, TABLE_SEEDS + 1):
        env = make_environment(ENV_ID, **CONFIGS["both"])
        env.reset(seed=seed)
        yield f"scripted-{seed}", env, scripted_policy
    env = make_environment(ENV_ID, max_steps=EXIT_MOVES + 1)  # exit reached on the limit step
    env.reset(seed=1)
    yield "scripted-limit", env, scripted_policy
    for seed, limit in enumerate(RANDOM_LIMITS, start=1):  # states the scripted runs never reach
        env = make_environment(ENV_ID, **CONFIGS["both"], max_steps=limit)
        env.reset(seed=seed)
        env.action_space.seed(seed)
        yield f"random-{seed}", env, lambda env: env.action_space.sample()


def check_truth_table(report: Report, code_text: str) -> dict:
    """Run each expression of the code file's truth table like the labeling stage does."""
    section = code_text.split("## Truth conditions in code")[1].split("\n## ")[0]
    rows = TABLE_ROW.findall(section)
    source = "".join(f"def {name}(env):\n    return {expression}\n\n" for name, expression in rows)
    labeling = load_labeling_functions(source, [name for name, _ in rows])
    seen, mismatches, steps, cut = set(), [], 0, 0
    for name, env, choose in _table_episodes():
        done = False
        while not done:
            _, _, terminated, truncated, _ = env.step(choose(env))
            table = {label: bool(read(env.unwrapped)) for label, read in labeling.items()}
            steps += 1
            done = terminated or truncated
            seen |= {label for label, value in table.items() if value}
            if table != reference_labels(env):
                mismatches.append((name, env.unwrapped.step_count))
        cut += bool(truncated)
    report.expect(
        "truth table: environment-code.md expressions equal reference_labels on every step",
        not mismatches and seen == set(labeling) and cut > 0,
        f"{steps} steps, {cut} cut at the step limit, mismatches {mismatches[:3]}, "
        f"each label true somewhere: {sorted(seen)}",
    )
    return {"steps": steps, "cut": cut, "mismatches": mismatches, "true_somewhere": sorted(seen)}


def check_event_seed(report: Report) -> dict:
    """Resets report the event seed used; an unseeded episode replays from it."""
    firsts = [run_episode(CONFIGS["both"], None) for _ in range(UNSEEDED_EPISODES)]
    replays = [run_episode(CONFIGS["both"], first["event_seed"]) for first in firsts]
    same = [
        (a["actions"], a["events"]) == (b["actions"], b["events"])
        for a, b in zip(firsts, replays, strict=True)
    ]
    seeds = [first["event_seed"] for first in firsts]
    report.expect(
        "event seed: unseeded resets vary and a given seed is reported back",
        len(set(seeds)) > 1 and run_episode(CONFIGS["both"], 7)["event_seed"] == 7,
        seeds,
    )
    report.expect("event seed: replaying the reported seed gives the same episode", all(same))
    return {"unseeded_event_seeds": seeds, "replays_equal": same}


def _pick_drop_pick(late: int) -> tuple[list, int, int]:
    """Pick the box up, drop it, pick it up again ``late`` steps after the first fall is due.

    Returns the events of the last pick-up step and the fall counts fired and skipped by then.
    """
    env = make_environment(ENV_ID, box=True)
    env.reset(seed=1)
    base = env.unwrapped
    for action in [Actions.forward] * 3 + [Actions.right, Actions.pickup]:  # face the box, take it
        env.step(action)
    # The due step is not public: the pickup sets it to this step plus the first drawn delay.
    due = base.step_count + base._fall_delays[0]
    env.step(Actions.drop)
    while base.step_count < due + late - 1:
        env.step(Actions.done)
    events = env.step(Actions.pickup)[-1]["events"]
    return events, base.event_counts["fall"]["fired"], base.event_counts["fall"]["skipped"]


def check_repick_and_dodge(report: Report) -> dict:
    """A pick-up on the due step falls on that step; one step later the fall was dodged."""
    on_due, dodged = _pick_drop_pick(0), _pick_drop_pick(1)  # (events, fired, skipped)
    report.expect(
        "box: a pick-up on the due step makes it fall on that step",
        on_due == (["fall"], 1, 0),
        on_due,
    )
    report.expect(
        "box: a drop kept past the due step dodges the fall", dodged == ([], 0, 1), dodged
    )
    return {"on_due_step": on_due, "one_step_late": dodged}


def check_geometry_and_files(report: Report) -> dict:
    """The exit is far from the start, and the env files load with the five propositions."""
    episode = run_episode(CONFIGS["neither"], seed=1)
    moves = episode["actions"].count(Actions.forward)
    report.expect(
        f"geometry: the exit is at least {MIN_EXIT_MOVES} moves from the start {START}",
        moves >= MIN_EXIT_MOVES,
        f"{moves} forward moves, start facing {START_DIR}",
    )
    report.expect(
        f"geometry: the shortest route is exactly {EXIT_MOVES} forward moves", moves == EXIT_MOVES
    )
    description = EnvironmentDescription.from_file(ENV_FILE, code=True)
    labels = list(episode["labels"][0])
    report.expect(
        "env files: environment.md and environment-code.md load and declare the five labels",
        list(description.proposition_ids) == labels and description.labeling_api is not None,
        list(description.proposition_ids),
    )
    return {"forward_moves": moves, "propositions": list(description.proposition_ids)}


# ======================================================================================
#                                          MAIN
# ======================================================================================
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True, help="folder for summary.json and GIFs")
    parser.add_argument("--seeds", type=int, default=50, help="event seeds 1..N per configuration")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    report = Report()
    seeds = range(1, args.seeds + 1)
    summary = {"seeds": args.seeds, "configs": {}}
    for name, kwargs in CONFIGS.items():
        summary["configs"][name] = check_config(name, kwargs, seeds, report, args.out)
    summary["observation"] = check_observation(report)
    summary["geometry_and_files"] = check_geometry_and_files(report)
    summary["truth_table"] = check_truth_table(report, CODE_FILE.read_text(encoding="utf-8"))
    summary["event_seed"] = check_event_seed(report)
    summary["repick_and_dodge"] = check_repick_and_dodge(report)
    summary["checks"], summary["failed"] = report.checks, report.failed
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")

    if report.failed:
        sys.exit(f"{len(report.failed)} checks failed: {report.failed}")
    print(f"all {len(report.checks)} checks passed; summary and GIFs in {args.out}")


if __name__ == "__main__":
    main()
