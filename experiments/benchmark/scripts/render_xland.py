"""Write the XLand family's rulesets, environment pages and card task texts, with no model call.

Usage (repository root, `RM_RL_env`):
    PYTHONPATH=app python experiments/benchmark/scripts/render_xland.py --export <medium_1m_v3 file>
    PYTHONPATH=app python experiments/benchmark/scripts/render_xland.py

`--export` copies the five medium-1m rulesets of the ARM-FM paper's Figure 9 (padding kept, so a
reset seed gives xminigrid's own layout) and the three Figure 10 rulesets rebuilt by hand into
`app/src/arm_fm/custom_envs/xland_rulesets.json`. The second form writes, per ruleset,
`experiments/benchmark/envs/xland-<ruleset>/environment.md` (facts) and `environment-code.md`
(implementation), and prints each card's task text. The paper gives ruleset ids, not task text,
so the text is reconstructed: rendered from the goal and the rules that make the goal's tile.
"""

import argparse
import json
from pathlib import Path

import numpy as np
from xminigrid.benchmarks import load_benchmark_from_path

from src.arm_fm.custom_envs import xland_env as xl
from src.arm_fm.custom_envs.xland import ENV_ID
from src.arm_fm.environments import make_environment

RULESETS_FILE = Path("app/src/arm_fm/custom_envs/xland_rulesets.json")
ENVS = Path("experiments/benchmark/envs")
FIGURE_9 = (197, 212, 260, 859, 594)  # ARM-FM paper Figure 9: the 1-, 3- and 5-task sets
TRACE_SEED = 1  # the reset seed of each page's example trace
# Figure 10's rules are only partly visible in the paper; these follow its state texts: A picks up
# a blue key to make an orange star and holds it, B holds a blue star to make a blue pyramid and
# stands with it to the right, C (unseen in training) picks up a blue key to make that pyramid.
FIGURE_10 = {
    "figure10-a": {
        "goal": ("AgentHold", "orange star"),
        "rules": [("TileNear", "blue key", "purple ball", "orange star")],
        "init": ["blue key", "purple ball", "orange pyramid"],
    },
    "figure10-b": {
        "goal": ("AgentNearRight", "blue pyramid"),
        "rules": [("AgentHold", "blue star", "blue pyramid")],
        "init": ["blue star", "purple ball", "orange pyramid"],
    },
    "figure10-c": {
        "goal": ("AgentNearRight", "blue pyramid"),
        "rules": [("AgentHold", "blue key", "blue pyramid")],
        "init": ["blue key", "purple ball", "orange pyramid"],
    },
}
GOAL_IDS = {"AgentHold": 1, "AgentNear": 3, "AgentNearRight": 12}
RULE_IDS = {"AgentHold": 1, "AgentNear": 2, "TileNear": 3}

# Plain words for each grid side: where a tile on that side of the agent is, and where the agent
# stands relative to such a tile.
SIDE_OF_AGENT = tuple(
    f"on the cell {side}" for side in ("above", "to the right of", "below", "to the left of")
)
# "on the map": xminigrid's sides are grid sides, whatever way the agent faces.
SIDE_PHRASE = tuple(
    f"one tile {side} on the map"
    for side in ("above you", "to your right", "below you", "to your left")
)
STAND_PHRASE = tuple(
    f"directly {side}" for side in ("below", "to the left of", "above", "to the right of")
)
TILE_SIDE = tuple(
    f"directly {side}" for side in ("above", "to the right of", "below", "to the left of")
)


# ======================================================================================
#                                       EXPORT
# ======================================================================================


def encode_tile(name: str) -> list[int]:
    color, kind = name.split(" ")
    return [xl.TILE_NAMES.index(kind), xl.COLOR_NAMES.index(color)]


def encode_figure10(spec: dict) -> dict[str, list]:
    """The xminigrid encodings of a hand-built ruleset: goal of 5, rules of 7, tiles of 2."""
    kind, tile = spec["goal"]
    goal = [GOAL_IDS[kind], *encode_tile(tile), 0, 0]
    rules = []
    for kind, *tiles in spec["rules"]:
        row = [RULE_IDS[kind], *(value for tile in tiles for value in encode_tile(tile))]
        rules.append(row + [0] * (7 - len(row)))
    return {"goal": goal, "rules": rules, "init_tiles": [encode_tile(t) for t in spec["init"]]}


def export(data_file: Path) -> None:
    benchmark = load_benchmark_from_path(str(data_file))
    rulesets = {}
    for number in FIGURE_9:
        ruleset = benchmark.get_ruleset(number)
        rulesets[f"medium-1m-{number}"] = {
            "goal": np.asarray(ruleset.goal).tolist(),
            "rules": np.asarray(ruleset.rules).tolist(),
            "init_tiles": np.asarray(ruleset.init_tiles).tolist(),
        }
    rulesets |= {name: encode_figure10(spec) for name, spec in FIGURE_10.items()}
    # One line per encoding row, so a diff shows which rule changed.
    blocks = [
        f'  "{name}": {{\n'
        + ",\n".join(
            f'    "{field}": [{", ".join(json.dumps(row) for row in rows)}]'
            if field != "goal"
            else f'    "goal": {json.dumps(rows)}'
            for field, rows in ruleset.items()
        )
        + "\n  }"
        for name, ruleset in rulesets.items()
    ]
    RULESETS_FILE.write_text("{\n" + ",\n".join(blocks) + "\n}\n", encoding="utf-8")
    print(f"wrote {len(rulesets)} rulesets to {RULESETS_FILE}")


# ======================================================================================
#                                     TASK TEXT
# ======================================================================================


def article(name: str) -> str:
    return f"an {name}" if name[0] in "aeiou" else f"a {name}"


def chain(ruleset: xl.Ruleset) -> list[xl.Rule]:
    """The rules that make the goal's tile, first to last; each step makes what the next needs."""
    steps: list[xl.Rule] = []
    need = ruleset.goal_tile
    while need not in ruleset.init_tiles:
        rule = next((r for r in ruleset.rules if r.product == need and r not in steps), None)
        if rule is None:
            break
        steps.insert(0, rule)
        absent = [tile for tile in rule.inputs if tile not in ruleset.init_tiles]
        if not absent:
            break
        need = absent[0]
    return steps


def rule_step(rule: xl.Rule, carried: bool = False) -> str:
    """One rule as an instruction; ``carried``: a holding rule put its input in the pocket."""
    names = [xl.tile_name(tile) for tile in rule.inputs]
    product = article(xl.tile_name(rule.product))
    if rule.kind == xl.RULE_HOLD:
        return f"pick up the {names[0]} to turn it into {product}"
    if rule.kind == xl.RULE_NEAR:
        face = f"put the {names[0]} down, face it" if carried else f"face the {names[0]}"
        return f"{face} and step forward to turn it into {product}"
    if rule.kind in xl.RULE_NEAR_SIDE and carried:
        return f"put the {names[0]} down {SIDE_PHRASE[rule.side]} to turn it into {product}"
    if rule.kind in xl.RULE_NEAR_SIDE:
        stand = STAND_PHRASE[rule.side]
        return (
            f"stand {stand} the {names[0]}, facing it, and step forward to turn it into {product}"
        )
    if rule.kind == xl.RULE_TILE_NEAR:
        return f"pick up the {names[0]} and put it down next to the {names[1]} to make {product}"
    raise ValueError(f"rule kind {rule.kind} has no task wording")


def goal_step(ruleset: xl.Ruleset) -> str:
    name = xl.tile_name(ruleset.goal_tile)
    if ruleset.goal_kind == xl.GOAL_HOLD:
        return f"pick up the {name}"
    if ruleset.goal_kind == xl.GOAL_NEAR:
        return f"step forward with the {name} next to you"
    return f"stand so that the {name} is {SIDE_PHRASE[ruleset.goal_side]}"


def task_text(ruleset: xl.Ruleset) -> str:
    """The card task: the chain's steps, then the goal, joined by "then"."""
    rules = chain(ruleset)
    held = [False] + [before.kind == xl.RULE_HOLD for before in rules[:-1]]
    steps = [rule_step(rule, carried) for rule, carried in zip(rules, held, strict=True)]
    text = ", then ".join([*steps, goal_step(ruleset)])
    return upper_first(text) + "."


def upper_first(text: str) -> str:
    return text[0].upper() + text[1:]


# ======================================================================================
#                                    FACTS PAGE
# ======================================================================================


def rule_fact(rule: xl.Rule) -> str:
    names = [xl.tile_name(tile) for tile in rule.inputs]
    first, second = article(names[0]), article(names[-1])  # second: tile-pair rules only
    product = article(xl.tile_name(rule.product))
    if rule.kind == xl.RULE_HOLD:
        return (
            f"holding rule: a `pickup` while the pocket holds {first} turns it into {product} in "
            f"the pocket. Picking up {first} fires it at once, so the pocket never shows {first}."
        )
    if rule.kind == xl.RULE_NEAR:
        return (
            f"agent-next-to rule: a `forward` with {first} on any of the four cells beside the "
            f"agent turns each such {names[0]} into {product}, also when the move is blocked."
        )
    if rule.kind in xl.RULE_NEAR_SIDE:
        return (
            f"agent-side rule: a `forward` or `putdown` with {first} {SIDE_OF_AGENT[rule.side]} "
            f"the agent turns it into {product}, also when the action does nothing else."
        )
    if rule.kind == xl.RULE_TILE_NEAR:
        return (
            f"tile-pair rule: a `putdown` that leaves {first} beside {second}, or {second} beside "
            f"{first}, turns the neighbour into {product} and leaves floor where the tile was "
            "put; both inputs are used up."
        )
    side = TILE_SIDE[rule.side]
    return (
        f"side tile-pair rule: a `putdown` that leaves {second} {side} {first} (either one put "
        f"down) turns the other into {product} and leaves floor where the tile was put; both "
        "inputs are used up."
    )


def goal_fact(ruleset: xl.Ruleset) -> str:
    name = article(xl.tile_name(ruleset.goal_tile))
    if ruleset.goal_kind == xl.GOAL_HOLD:
        return f"a `pickup` while the pocket holds {name} (also when the pickup takes nothing)"
    if ruleset.goal_kind == xl.GOAL_NEAR:
        return f"a `forward` with {name} on any of the four cells beside the agent"
    side = SIDE_OF_AGENT[ruleset.goal_side]
    return f"a `forward` or `putdown` with {name} {side} the agent"


def proposition_rows(ruleset: xl.Ruleset) -> list[tuple[str, str, str]]:
    """(id, true when, declaration) per proposition, in the env page's order."""
    rows = []
    for tile in ruleset.products():
        name = xl.tile_name(tile)
        rows.append(
            (
                f"{xl.tile_id(tile)}_made",
                f"a rule turned a tile into {article(name)} on this step",
                f"A rule turned a tile into {article(name)} on this step.",
            )
        )
    for tile in ruleset.pickup_inputs():
        name = xl.tile_name(tile)
        rows.append(
            (
                f"{xl.tile_id(tile)}_picked_up",
                f"this step's `pickup` took {article(name)} from the grid into the empty pocket",
                f"The agent picked up {article(name)} from the grid on this step.",
            )
        )
    rows.append(
        (
            ruleset.goal_event(),
            f"the goal fired on this step: {goal_fact(ruleset)}; the episode ends on this step",
            f"The goal fired on this step ({goal_step(ruleset)}).",
        )
    )
    return rows


def constraints(ruleset: xl.Ruleset) -> list[str]:
    """Orders the rules force: a tile that is not an initial object exists only once made."""
    made = set(ruleset.products())
    lines = []

    def needs(event: str, tile: xl.Tile, why: str) -> None:
        if tile not in ruleset.init_tiles and tile in made:
            lines.append(
                f"- `{event}` cannot become true before `{xl.tile_id(tile)}_made`: {why} only "
                f"exists once a rule makes it."
            )

    for rule in ruleset.rules:
        if [r for r in ruleset.rules if r.product == rule.product] == [rule]:
            for tile in rule.inputs:
                why = f"the rule needs {article(xl.tile_name(tile))}, which"
                needs(f"{xl.tile_id(rule.product)}_made", tile, why)
    for tile in ruleset.pickup_inputs():
        needs(f"{xl.tile_id(tile)}_picked_up", tile, article(xl.tile_name(tile)))
    needs(ruleset.goal_event(), ruleset.goal_tile, article(xl.tile_name(ruleset.goal_tile)))
    return lines


def same_step_facts(ruleset: xl.Ruleset) -> list[str]:
    """Events this ruleset always fires together."""
    lines = []
    goal = ruleset.goal_tile
    for rule in ruleset.rules:
        if rule.kind == xl.RULE_HOLD:
            lines.append(
                f"- `{xl.tile_id(rule.inputs[0])}_picked_up` and `{xl.tile_id(rule.product)}_made` "
                "are true on the same step: the holding rule fires on the pickup itself."
            )
        beside = rule.kind == xl.RULE_NEAR or rule.kind in xl.RULE_NEAR_SIDE
        goal_beside = ruleset.goal_kind == xl.GOAL_NEAR or (
            ruleset.goal_side is not None and ruleset.goal_side == rule.side
        )
        if rule.product == goal and beside and goal_beside:
            lines.append(
                f"- A `forward` that makes {article(xl.tile_name(goal))} beside the agent fires "
                f"the goal on the same step, so `{xl.tile_id(goal)}_made` and `{ruleset.goal_event()}` "
                "come together then."
            )
    return lines


def example_trace(name: str) -> tuple[list[str], int, float]:
    """The scripted policy's episode on the trace seed: numbered lines, steps, reward."""
    env = make_environment(ENV_ID, ruleset=name)
    env.reset(seed=TRACE_SEED)
    lines, quiet, steps, reward, done = [], 0, 0, 0.0, False
    while not done:
        action = xl.scripted_policy(env)
        _, reward, terminated, truncated, _ = env.step(action)
        steps += 1
        done = terminated or truncated
        true = [key for key, value in xl.reference_labels(env).items() if value]
        if not true:
            quiet += 1
            continue
        if quiet:
            lines.append(f"{quiet} {'step' if quiet == 1 else 'steps'} of turning and moving")
            quiet = 0
        named = ", ".join(f"`{key}`" for key in true)
        lines.append(f"`{xl.ACTION_NAMES[action]}` (step {steps}): {named} true")
    env.close()
    if not terminated:  # a goal step always names its event, so no quiet run is left over
        raise RuntimeError(
            f"{name}: the scripted policy did not reach the goal on seed {TRACE_SEED}"
        )
    lines[-1] += " [episode terminated]"
    return [f"{number}. {line}" for number, line in enumerate(lines, 1)], steps, float(reward)


LAYOUT = (
    "A 13 x 13 grid with a grey wall border and a wall cross on row 6 and column 6, so four rooms "
    "of 5 x 5 free cells. Each of the four wall arms has one door at a random place along the "
    "arm, closed and not locked, of a random color among red, green, blue, purple, yellow and "
    "grey. Every initial object lands on its own random floor cell in any room; so does the "
    "agent, with a random facing and an empty pocket. All free cells connect through the four "
    "doors. The layout, the doors and the start change with every reset; the ruleset does not."
)
ACTIONS = (
    "Actions: `forward`, `turn_right` (clockwise), `turn_left`, `pickup`, `putdown`, `toggle`; "
    "there is no `done`. The agent sees the 5 x 5 cells in front of it (walls hide nothing), what "
    "it carries and which way it faces; it never sees the rules or the goal."
)
READING = (
    "Every proposition is an event: true only on the step its action fires, false on every "
    'other step, also while the made tile stays in the world. This file reads "made" as the step '
    'a rule changes a tile, so a rule that fires again makes its event true again, and "picked '
    'up" as the step the tile leaves the grid for the pocket. Up, right, down and left are sides '
    "of the grid (up is the row above), whatever way the agent faces."
)
MECHANICS = [
    "- Forward: onto floor, goal tiles and open doors only; a wall, a closed door or any object "
    "blocks it and the agent stays, but the step still counts as `forward` for rules and the "
    "goal. Turns change only the facing and fire no rule and no goal.",
    "- Pickup: the facing cell must hold a ball, square, pyramid, key, hex or star, and the "
    "pocket must be empty; the cell becomes floor. Goal tiles, doors and walls cannot be picked "
    "up. The pocket holds one tile.",
    "- Putdown: needs a full pocket and floor in the facing cell; a goal tile, a door, a wall or "
    "an object blocks it.",
    "- Toggle: opens a closed door and closes an open one. No door is locked.",
    "- Rules run after every action, in the order listed, each on the grid the one before left, "
    "so two rules can fire in one step. A tile a rule uses up comes back only if a rule makes it "
    "again, so a rule can make the goal unreachable.",
]


def title(name: str) -> str:
    if name.startswith("figure10-"):
        return f"XLand-MiniGrid ruleset Figure 10 {name[-1].upper()}"
    return f"XLand-MiniGrid ruleset {name.rpartition('-')[2]}"


def facts_page(name: str, ruleset: xl.Ruleset, trace: tuple[list[str], int, float]) -> str:
    lines, steps, reward = trace
    rules = [f"  {i}. {upper_first(article(rule_fact(r)))}" for i, r in enumerate(ruleset.rules, 1)]
    objects = ", ".join(
        article(f"{xl.tile_name(tile)} tile" if tile[0] == xl.GOAL_TILE else xl.tile_name(tile))
        for tile in ruleset.init_tiles
    )
    rows = proposition_rows(ruleset)
    first = chain(ruleset)
    return "\n".join(
        [
            f"# {title(name)}",
            "",
            "## Environment",
            "",
            LAYOUT,
            "",
            "This world's ruleset:",
            f"- Goal: {goal_fact(ruleset)}.",
            "- Rules, in the order they run after every action:",
            *rules,
            f"- Initial objects: {objects}.",
            "",
            ACTIONS,
            "",
            "## Objective and episode boundary",
            "",
            f"The episode ends on the step the goal fires: {goal_fact(ruleset)}. The reward is "
            "then `1 - 0.9 * (steps taken / 507)`, otherwise 0. The step limit is 507 steps; at "
            "step 507 without the goal the episode ends with reward 0. No step follows the goal.",
            "",
            "## Proposition semantics",
            "",
            "| id | kind | true when |",
            "|---|---|---|",
            *(f"| `{pid}` | event | {when} |" for pid, when, _ in rows),
            "",
            READING,
            "",
            "## Constraints",
            "",
            *(constraints(ruleset) or ["- None beyond the rules above."]),
            "",
            "## What the agent can and cannot do",
            "",
            *MECHANICS,
            *same_step_facts(ruleset),
            "",
            "## Example trace",
            "",
            f"One real episode that reaches the goal: {steps} steps, reward {reward:.4f}.",
            "",
            *lines,
            "",
            "## Propositions",
            *(f"- `{pid}`: {text}" for pid, _, text in rows),
            "",
            "## Example tasks",
            "",
            f"- {upper_first(goal_step(ruleset))}.",
            *([f"- {upper_first(rule_step(first[0]))}, then reach the goal."] if first else []),
            "",
        ]
    )


def rule_source(rule: xl.Rule) -> str:
    kinds = {1: "AgentHoldRule", 2: "AgentNearRule", 3: "TileNearRule"}
    if rule.kind in xl.RULE_NEAR_SIDE or rule.kind in xl.RULE_TILE_NEAR_SIDE:
        side = xl.SIDES[rule.side].capitalize()
        return f"{'AgentNear' if rule.kind in xl.RULE_NEAR_SIDE else 'TileNear'}{side}Rule"
    return kinds[rule.kind]


def goal_source(ruleset: xl.Ruleset) -> str:
    if ruleset.goal_kind == xl.GOAL_HOLD:
        return "AgentHoldGoal"
    if ruleset.goal_kind == xl.GOAL_NEAR:
        return "AgentNearGoal"
    return f"AgentNear{xl.SIDES[ruleset.goal_side].capitalize()}Goal"


def truth_expressions(ruleset: xl.Ruleset) -> dict[str, str]:
    """Each proposition's labeling expression over the env's Labeling API, in page order."""
    truth = {
        f"{xl.tile_id(tile)}_made": f'"{xl.tile_name(tile)}" in env.products_made'
        for tile in ruleset.products()
    }
    truth |= {
        f"{xl.tile_id(tile)}_picked_up": f'env.picked_up == "{xl.tile_name(tile)}"'
        for tile in ruleset.pickup_inputs()
    }
    truth[ruleset.goal_event()] = "env.goal_reached"
    return truth


def code_page(name: str, ruleset: xl.Ruleset, trace: tuple[list[str], int, float]) -> str:
    _, steps, reward = trace
    origin = (
        "rebuilt by hand from the ARM-FM paper's Figure 10, whose rules are only partly visible"
        if name.startswith("figure10-")
        else f"ruleset {name.rpartition('-')[2]} of xminigrid's `medium-1m` benchmark, padding kept"
    )
    truth = [f"| `{key}` | `{value}` |" for key, value in truth_expressions(ruleset).items()]
    rule_classes = ", ".join(sorted({f"`rules.py:{rule_source(rule)}`" for rule in ruleset.rules}))
    return "\n".join(
        [
            f"# {title(name)}: code notes",
            "",
            "Addition to `environment.md`; read both. Facts live there; this file says where they "
            "come from and how code reads them.",
            "",
            "## Source and runtime",
            "",
            "- Source: `app/src/arm_fm/custom_envs/xland_env.py:XLandEnv`, a Gymnasium wrapper "
            "over the jitted `xminigrid` environment `XLand-MiniGrid-R4-13x13` "
            "<https://github.com/dunnolab/xland-minigrid>. Importing `src.arm_fm` registers the "
            "id; the wrapper module (and JAX, on CPU) loads only when an env is made.",
            f'- Gymnasium ID: `{ENV_ID}`, keyword argument `ruleset="{name}"`, read from '
            f"`app/src/arm_fm/custom_envs/xland_rulesets.json`: {origin}.",
            "- Runtime: `xminigrid==0.9.3` (with JAX), `gymnasium==1.3.0`, pinned in "
            "`requirements.txt`.",
            "- `reset(seed=s)` draws the layout from `jax.random.key(s)`, xminigrid's own layout "
            "for this ruleset; without a seed it draws one from the env's own random stream.",
            "- Observation: `(5, 5, 5)` uint8: xminigrid's 5 x 5 view (tile id, color id per "
            "cell), then the pocket's tile id, its color id and the facing on every cell.",
            "- `[code: file:function]` is under `xminigrid/` unless named otherwise. `[run: "
            "render]` is `experiments/benchmark/scripts/render_xland.py`, which wrote both files.",
            "",
            "## Truth conditions in code",
            "",
            "All read what the last step did; none reads the grid.",
            "",
            "| id | expression |",
            "|---|---|",
            *truth,
            "",
            "## Evidence",
            "",
            "- Environment, layout, doors and start: [code: `envs/xland.py:generate_four_rooms`, "
            "`XLandMiniGrid._generate_problem`].",
            f"- Environment, the rules and their actions: [code: {rule_classes}; "
            "`rules.py:check_rule` runs them in order].",
            f"- Objective, goal and reward: [code: `goals.py:{goal_source(ruleset)}`; "
            "`environment.py:Environment.step`; `envs/xland.py:XLandMiniGrid.default_params` sets "
            "`max_steps` to `3 * 13 * 13`].",
            "- Proposition semantics: [code: `xland_env.py:XLandEnv.step`: `products_made` from "
            "each rule's own replay in `_step`, `picked_up` from `pick_up`'s condition, "
            "`goal_reached` from the zero discount of a goal step].",
            "- Constraints: only rules create tiles; actions move a tile between grid and pocket "
            "or open and close doors [code: `core/actions.py`].",
            "- What the agent can and cannot do: [code: `core/actions.py:move_forward`, "
            "`pick_up`, `put_down`, `toggle`; `core/constants.py:WALKABLE`, `PICKABLE`, "
            "`FREE_TO_PUT_DOWN`; `core/grid.py:check_can_put`].",
            f"- Example trace: [run: render, reset seed {TRACE_SEED}, "
            f"`xland_env.py:scripted_policy`]: {steps} steps, reward {reward:.4f}.",
            "- Reference labeling: `xland_env.py:reference_labels` computes the expressions "
            "above; the benchmark's labeling check compares a bundle's labeling with it.",
            "",
            "## Labeling API",
            "",
            '- `env.last_action`: name of the last action (`"forward"`, `"turn_right"`, '
            '`"turn_left"`, `"pickup"`, `"putdown"`, `"toggle"`), `None` after reset.',
            '- `env.products_made`: tuple of tile names (`"<color> <kind>"`, for example '
            '`"blue pyramid"`), one per rule that fired on the last step, in rule order; empty '
            "when none fired.",
            "- `env.picked_up`: name of the tile the last step's `pickup` took from the grid, "
            "else `None`. A holding rule may already have changed it in the pocket.",
            "- `env.goal_reached`: `True` on the step the ruleset's goal fired (that step ends "
            "the episode), else `False`.",
            "- `env.pocket`: name of the carried tile, or `None`.",
            "- `env.agent_pos`: `(row, column)` of the agent. `env.agent_dir`: its facing, `0` up, "
            "`1` right, `2` down, `3` left.",
            '- `env.tiles`: tuple of rows, each a tuple of cell names (`"black floor"`, '
            '`"grey wall"`, `"red door_closed"`, `"blue pyramid"`, ...); read a cell as '
            "`env.tiles[row][column]`.",
            "",
            "Every proposition of this ruleset is an event of the last step: read it from "
            "`env.products_made`, `env.picked_up` or `env.goal_reached`, not from the grid.",
            "",
        ]
    )


def render_pages() -> None:
    for name in xl.RULESETS:
        ruleset = xl.Ruleset.decode(xl.RULESETS[name])
        trace = example_trace(name)
        folder = ENVS / f"xland-{name}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "environment.md").write_text(facts_page(name, ruleset, trace), encoding="utf-8")
        (folder / "environment-code.md").write_text(
            code_page(name, ruleset, trace), encoding="utf-8"
        )
        print(f"{name}: {task_text(ruleset)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--export", type=Path, help="medium-1m data file: write the rulesets JSON")
    args = parser.parse_args()
    if args.export:
        export(args.export)
    else:
        render_pages()


if __name__ == "__main__":
    main()
