"""Step-1 previous valuation all false: the plain latch rows of the four benchmark pages.

Reads every executable row of "Truth conditions in code" out of each page (plain form, no
`"name" in prev` guard), loads it in the labeling sandbox with a fresh RewardMachineRuntime and
compares each step with the reference labeler on seeds 1 to 50. Scenarios per layout: the solving
plan, a plan that drops the key (three pages), a seeded random walk.

KeyCorridor rows that need the locked door's color or cell (`L`, `dx`, `dy`) get them as literals
read from the layout at reset, as the page says labeling code keeps them for the episode.

usage (repository root):
  PYTHONPATH=app python outputs/wave-tests/prev-false/prev_false_pages.py <label> [runtime_file]

`runtime_file` loads a RewardMachineRuntime from that file instead (the base-revision copy).
"""

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

import numpy as np

from src.arm_fm.environments import make_environment
from src.benchmark.cards import load_cards
from src.benchmark.plans import run_plan
from src.benchmark.reference_labels import labeler_for
from src.compiler import parse_paper_reward_machine

OUT = Path(__file__).parent
LABEL = sys.argv[1]
if len(sys.argv) > 2:
    spec = importlib.util.spec_from_file_location("runtime_under_test", sys.argv[2])
    runtime_module = importlib.util.module_from_spec(spec)
    sys.modules["runtime_under_test"] = runtime_module  # dataclasses looks the module up here
    spec.loader.exec_module(runtime_module)
else:
    from src.arm_fm import runtime as runtime_module
RewardMachineRuntime = runtime_module.RewardMachineRuntime
load_labeling_functions = runtime_module.load_labeling_functions

ENVS = Path("experiments/benchmark/envs")
BASE = {c.id: c for c in load_cards(Path("experiments/benchmark/base/tasks.json")).cards}
COMPLEX = {c.id: c for c in load_cards(Path("experiments/benchmark/complex/tasks.json")).cards}
RANDOM_STEPS = 200
SEEDS = range(1, 51)

DROP_KEY = [{"do": "pickup", "obj": "key"}, {"do": "drop"}, {"do": "wait", "n": 2}]
PAGES = {
    "minigrid-doorkey": (
        BASE["base-doorkey"],
        [
            {"do": "pickup", "obj": "key"},
            {"do": "toggle", "obj": "door:locked"},
            {"do": "goto", "obj": "goal"},
        ],
        None,
    ),
    "minigrid-unlock-pickup": (
        BASE["base-unlock-pickup"],
        [
            {"do": "pickup", "obj": "key"},
            {"do": "toggle", "obj": "door:locked"},
            {"do": "drop"},
            {"do": "pickup", "obj": "box"},
        ],
        None,
    ),
    "minigrid-blocked-unlock-pickup": (
        BASE["base-blocked-unlock-pickup"],
        [
            {"do": "pickup", "obj": "ball"},
            {"do": "drop"},
            {"do": "pickup", "obj": "key"},
            {"do": "toggle", "obj": "door:locked"},
            {"do": "drop"},
            {"do": "pickup", "obj": "box"},
        ],
        None,
    ),
    # target_door_open is described, not an expression; the other four rows are executable.
    "minigrid-key-corridor": (
        COMPLEX["cx-sequence"],
        COMPLEX["cx-sequence"].solve,
        ("key_found", "has_matching_key", "target_room_entered", "target_picked_up"),
    ),
}


def machine_for(propositions):
    """A two-state machine that knows every proposition, so the runtime evaluates them all."""
    last = propositions[-1]
    return parse_paper_reward_machine(
        f"""REWARD_MACHINE:
STATES: u0, u1
INITIAL_STATE: u0
FINAL_STATES: u1
TRANSITION_FUNCTION:
(u0, {last}) -> u1
(u0, else) -> u0
(u1, else) -> u1
REWARD_FUNCTION:
(u0, {last}, u1) -> 1
""",
        propositions=tuple(propositions),
        require_final_states=True,
    )


def read_page(name, only):
    """The table rows ``{id: expression}`` and the shorthand ``{letter: row id}`` of a page."""
    text = (ENVS / name / "environment-code.md").read_text()
    section = text.split("## Truth conditions in code", 1)[1].split("\n## ", 1)[0]
    rows = dict(re.findall(r"^\| `(\w+)` \| `([^`]+)`", section, re.M))
    if only:
        rows = {row: rows[row] for row in only}
    shorthand = {}
    for pair in re.finditer(
        r"`(\w)` and `(\w)` stand for the `(\w+)` and `(\w+)` expressions", section
    ):
        shorthand[pair.group(1)], shorthand[pair.group(2)] = pair.group(3), pair.group(4)
    return rows, shorthand


def labeling_source(rows, shorthand, layout_literals):
    """One function per row: the page's shorthand names are defined from their rows, then the row."""
    prelude = ['    prev = env.episode_memory["previous_valuation"]']
    prelude += [f"    {letter} = {rows[row]}" for letter, row in shorthand.items()]
    if "dx" in "".join(rows.values()) and not layout_literals:
        door = '[(x, y) for x in range(env.width) for y in range(env.height) for c in [env.grid.get(x, y)] if c is not None and c.type == "door"][0]'
        prelude += [f"    door = {door}", "    dx = door[0]", "    dy = door[1]"]
    if layout_literals:
        prelude += [
            "    ax, ay = env.agent_pos",
            *(f"    {k} = {v!r}" for k, v in layout_literals.items()),
        ]
    return "\n".join(
        f"def {row}(env):\n" + "\n".join(prelude) + f"\n    return {expression}\n"
        for row, expression in rows.items()
    )


def locked_door(env):
    """(color, x, y) of the locked door, read at reset before any step can unlock it."""
    grid = env.unwrapped.grid
    for x in range(env.unwrapped.width):
        for y in range(env.unwrapped.height):
            cell = grid.get(x, y)
            if cell is not None and cell.type == "door" and cell.is_locked:
                return cell.color, x, y
    raise RuntimeError("no locked door")


class Page(NamedTuple):
    """One environment page: its card, executable rows, shorthand, machine and whether it is KeyCorridor."""

    card: object
    rows: dict
    shorthand: str
    machine: object
    corridor: bool


def compare(page, seed, kind, plan):
    """Replay one scenario; returns (steps, error, mismatches, key_lost_fired)."""
    card, rows, shorthand, machine, corridor = page
    env = make_environment(card.env["gym_id"], **(card.env.get("env_kwargs") or {}))
    try:
        env.reset(seed=seed)
        literals = None
        if corridor:
            color, dx, dy = locked_door(env)
            literals = {"L": color, "dx": dx, "dy": dy}
        functions = load_labeling_functions(labeling_source(rows, shorthand, literals), tuple(rows))
        reference = labeler_for(card.env["gym_id"], env)
        runtime = RewardMachineRuntime(machine)
        runtime.reset()
        if kind == "random":
            generator = np.random.default_rng(seed)
            actions = (int(generator.integers(0, 7)) for _ in range(RANDOM_STEPS))
        else:
            actions = iter(run_plan(card.env, plan, seed).actions)
        steps, mismatches, fired = 0, [], 0
        for step, action in enumerate(actions, 1):
            _, _, terminated, truncated, _ = env.step(action)
            expected = reference.labels(env.unwrapped)
            try:
                actual = runtime.evaluate_labeling(env, functions)
            except Exception as error:  # the sandbox's or runtime's own failure is the evidence
                return (
                    steps,
                    f"step {step}: {type(error).__name__}: {error}"[:200],
                    mismatches,
                    fired,
                )
            steps += 1
            fired += bool(expected.get("key_lost"))
            for name, value in actual.items():
                if name in expected and value != expected[name]:
                    mismatches.append({"step": step, "proposition": name})
            if terminated or truncated:
                break
        return steps, None, mismatches, fired
    finally:
        env.close()


def main():
    report = {}
    for name, (card, solve, only) in PAGES.items():
        rows, shorthand = read_page(name, only)
        machine = machine_for(tuple(rows))
        corridor = name == "minigrid-key-corridor"
        scenarios = {"solve": solve, "random-walk": None}
        if not corridor:
            scenarios = {"solve": solve, "drop-key": DROP_KEY, "random-walk": None}
        page = {"rows": rows, "scenarios": {}}
        for scenario, plan in scenarios.items():
            runs = errors = plan_failures = steps = fired = 0
            error_samples, mismatches = [], []
            for seed in SEEDS:
                try:
                    done, error, found, hit = compare(
                        Page(card, rows, shorthand, machine, corridor),
                        seed,
                        "random" if plan is None else "plan",
                        plan,
                    )
                except Exception as error:  # a plan that cannot run is counted, not hidden
                    plan_failures += 1
                    error_samples.append(f"seed {seed}: plan {type(error).__name__}: {error}"[:200])
                    continue
                runs += 1
                steps, fired = steps + done, fired + hit
                mismatches += [{"seed": seed, **m} for m in found]
                if error:
                    errors += 1
                    error_samples.append(f"seed {seed}: {error}")
            page["scenarios"][scenario] = {
                "layouts_run": runs,
                "plan_failures": plan_failures,
                "steps": steps,
                "key_lost_true_steps": fired,
                "error_runs": errors,
                "mismatch_steps": len(mismatches),
                "error_samples": error_samples[:2],
                "mismatch_samples": mismatches[:3],
            }
        report[name] = page
    (OUT / f"pages-{LABEL}.json").write_text(json.dumps(report, indent=2) + "\n")
    for name, page in report.items():
        print(f"== {name}: rows {list(page['rows'])}")
        for scenario, row in page["scenarios"].items():
            print(f"   {scenario:12} {row}")


main()
