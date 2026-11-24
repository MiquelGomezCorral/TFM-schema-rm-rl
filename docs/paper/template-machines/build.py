r"""The 16 machines of the thesis appendix "IBM template examples": each IBM template compiled alone, hard and soft.

The clause is the whole proposal, with no goal added and no language model: the template's LTLf (``ltlf_of``),
the MONA DFA (``flat_tool.compile_dfa``) and the reward layer (``build_reward_machine``) at the default reward
switches, which are the frozen pipeline's (``RewardSwitches`` takes them from ``Configuration``). Stops with a
ValueError, and writes nothing, when a machine breaks one of the checks of ``problems``. Writes
``data/machines.json`` and, in ``paper/images/templates/``, one TikZ file per machine and ``all.tex`` (the two
figures the appendix inputs). The drawing style is the Results figures' (``draw_machines.py``): double ring =
final, grey = the well, the arrow colour follows the reward sign, rewards on the edges.

Run from the repository root, in RM_RL_env with MONA on PATH:
env PYTHONPATH=app:docs/paper/results-figures python -P -W ignore docs/paper/template-machines/build.py
"""

import json
import re
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

from draw_machines import arrow_colour, reward_text
from flat_tool import compile_dfa

from src.compiler import parse_paper_reward_machine, serialize_reward_machine
from src.compiler.reward_layer import (
    ClauseState,
    RewardSwitches,
    build_reward_machine,
    clause_labels,
)
from src.config import Configuration
from src.utils import ltlf_of, pretty_ltlf

ENTRY = Path(__file__).resolve().parent
IMAGES = ENTRY.parents[2] / "paper/images/templates"
SETTINGS = ("hard", "soft")
GOALS = (
    "Existence",
    "ExistenceTwo",
)  # the two goal templates: hard, they give the machine its final state
PROGRESS, COMPLETION = Configuration.PROGRESS_REWARD, Configuration.TASK_COMPLETION_REWARD
WELL, SOFT_BREAK = Configuration.WELL_REWARD, Configuration.soft_break_cost
# What a machine alone may pay: nothing (the default reward), one progress step back or forward, one soft break, the
# completion (with the last progress step) and the well. The hard ceiling and the end judgment only change a machine
# that mixes in soft rules and a goal, or that switches the judgment on.
ALLOWED_REWARDS = {0.0, PROGRESS, -PROGRESS, -SOFT_BREAK, COMPLETION, COMPLETION + PROGRESS, WELL}


@dataclass(frozen=True)
class Entry:
    """One template clause: its propositions, an illustrative task for each setting and its LTLf in TeX."""

    name: str
    propositions: tuple[str, ...]
    hard_task: str
    soft_task: str
    formula: str  # the thesis table's formula, with <a> and <b> for the propositions


# Illustrative tasks, written by hand (not generated), as in the October template catalogue; the DoorKey
# propositions are has_key, door_open, key_lost and at_goal. The order is that of Table tab:templates.
ENTRIES = (
    Entry(
        "Existence",
        ("has_key",),
        "Pick up the key.",
        "Pick up the key if you can.",
        r"\mathrm{F}\,<a>",
    ),
    Entry(
        "ExistenceTwo",
        ("door_open",),
        "Open the door at two different moments.",
        "Ideally, open the door at two different moments.",
        r"\mathrm{F}\,(<a> \land \mathrm{X}\,\mathrm{F}\,<a>)",
    ),
    Entry(
        "Absence",
        ("key_lost",),
        "Never lose the key.",
        "Try not to lose the key.",
        r"\neg\,\mathrm{F}\,<a>",
    ),
    Entry(
        "RespondedExistence",
        ("door_open", "has_key"),
        "If you ever open the door, you must also hold the key at some point.",
        "If you open the door, it would be good to also hold the key at some point.",
        r"\mathrm{F}\,<a> \rightarrow \mathrm{F}\,<b>",
    ),
    Entry(
        "Response",
        ("has_key", "door_open"),
        "Whenever you pick up the key, open the door afterwards.",
        "Whenever you pick up the key, preferably open the door afterwards.",
        r"\mathrm{G}\,(<a> \rightarrow \mathrm{F}\,<b>)",
    ),
    Entry(
        "Precedence",
        ("has_key", "door_open"),
        "Do not open the door before you have the key.",
        "Preferably, do not open the door before you have the key.",
        r"(\neg<b>\ \mathrm{U}\ <a>) \lor \mathrm{G}\,\neg<b>",
    ),
    Entry(
        "ChainResponse",
        ("has_key", "door_open"),
        "Right after you pick up the key, open the door.",
        "Ideally, open the door right after you pick up the key.",
        r"\mathrm{G}\,(<a> \rightarrow \mathrm{X}\,<b>)",
    ),
    Entry(
        "NotCoExistence",
        ("has_key", "key_lost"),
        "Do not both pick up the key and lose it in the same episode.",
        "Preferably, do not both pick up the key and lose it in the same episode.",
        r"\mathrm{F}\,<a> \rightarrow \neg\,\mathrm{F}\,<b>",
    ),
)
FIGURES = (ENTRIES[:5], ENTRIES[5:])  # two figures: eight rows do not fit a page


# ======================================================================================
#                                    COMPILE AND CHECK
# ======================================================================================
def tex_proposition(name):
    return "\\texttt{" + name.replace("_", "\\_") + "}"


def formula_tex(entry):
    """The thesis table's formula of the template, with the clause's propositions."""
    text = entry.formula.replace("<a>", tex_proposition(entry.propositions[0]))
    return text.replace("<b>", tex_proposition(entry.propositions[-1]))


def plain(tex):
    """A TeX formula as the pipeline writes its LTLf, without parentheses and spaces."""
    for old, new in (
        ("\\neg", "~"),
        ("\\land", "&"),
        ("\\lor", "|"),
        ("\\rightarrow", "->"),
        ("\\mathrm{", ""),
        ("\\texttt{", ""),
        ("\\_", "_"),
    ):
        tex = tex.replace(old, new)
    return re.sub(r"[\\,{}()\s]", "", tex)


def problems(entry, dfa, layer, paper, soft):
    """What looks wrong with one compiled machine; empty when it is the machine the pipeline should write."""
    found = []
    well = bool(paper.rejecting_states)
    breakable = ClauseState.VIOLATED in clause_labels(dfa).values()
    odd = {t.reward for t in paper.transitions} - ALLOWED_REWARDS
    if odd:
        found.append(f"rewards the config does not give: {sorted(odd)}")
    if any(t.reward != WELL for t in paper.transitions if t.destination in paper.rejecting_states):
        found.append("an edge into the well that does not pay the well charge")
    if soft and well:
        found.append("a soft machine with a well")
    if (
        not soft and well != breakable
    ):  # a clause with no violated state cannot send a run to the well
        found.append(
            f"hard machine: well is {well} but the clause can be broken for good is {breakable}"
        )
    if (
        layer.hard_goal != (not soft and entry.name in GOALS)
        or bool(paper.final_states) != layer.hard_goal
    ):
        found.append(f"final states {paper.final_states} against hard_goal {layer.hard_goal}")
    if layer.inert_soft_clauses:
        found.append("a soft clause that never changes a reward")
    return found


def compile_entry(entry):
    """The raw LTLf, the DFA and, per setting, the reward layer's result and the parsed machine text."""
    raw = ltlf_of(entry.name, entry.propositions)
    assert plain(formula_tex(entry)) == re.sub(r"[()\s]", "", raw), (entry.name, raw)
    dfa = compile_dfa(raw)
    machines = {}
    for setting in SETTINGS:
        layer = build_reward_machine([dfa], [setting == "soft"], RewardSwitches())
        text = serialize_reward_machine(layer.reward_machine)
        paper = parse_paper_reward_machine(text)
        found = problems(entry, dfa, layer, paper, setting == "soft")
        if found:
            raise ValueError(f"{entry.name} {setting}: {'; '.join(found)}\n{text}")
        machines[setting] = (text, paper)
    return raw, dfa, machines


def machine_record(entry, raw, dfa, setting, machine):
    """One machine as JSON; ``machine`` is its RM text with the parsed machine."""
    text, paper = machine
    return {
        "clause": f"{entry.name}({', '.join(entry.propositions)})",
        "setting": setting,
        "task": entry.hard_task if setting == "hard" else entry.soft_task,
        "ltlf": raw,
        "ltlf_spaced": pretty_ltlf(raw),
        "dfa_states": len(dfa["states"]),
        "states": list(paper.states),
        "initial": paper.initial_state,
        "final": list(paper.final_states),
        "rejecting": list(paper.rejecting_states),
        "transitions": [
            {
                "source": t.source,
                "guard": t.condition,
                "destination": t.destination,
                "reward": t.reward,
            }
            for t in paper.transitions
        ],
        "rm_text": text,
    }


# ======================================================================================
#                                        LABELS
# ======================================================================================
def join_cubes(cubes):
    """Join guards that differ in one proposition (``a&b`` and ``a&!b`` become ``a``); same meaning, one label."""
    cubes = [dict(cube) for cube in cubes]
    joined = True
    while joined:
        joined = False
        for first, second in combinations(cubes, 2):
            differing = [name for name in first if first[name] != second.get(name)]
            if first.keys() == second.keys() and len(differing) == 1:
                cubes.remove(first)
                cubes.remove(second)
                cubes.append({name: value for name, value in first.items() if name != differing[0]})
                joined = True
                break
    return cubes


def guard_cube(guard):
    """``!door_open&has_key`` as ``{"door_open": False, "has_key": True}``."""
    literals = [literal.strip() for literal in guard.split("&")]
    assert all(re.fullmatch(r"!?[a-z_]+", literal) for literal in literals), guard
    return {literal.lstrip("!"): not literal.startswith("!") for literal in literals}


def guard_tex(cube):
    """The literals of a guard joined by AND, one per line: a label stays narrow, as in the thesis machines."""
    if not cube:
        return "$\\top$"
    literals = [
        tex_proposition(name) if value else "\\neg\\," + tex_proposition(name)
        for name, value in cube.items()
    ]
    lines = [f"${literal} \\land$" for literal in literals[:-1]] + [f"${literals[-1]}$"]
    return " \\\\ ".join(lines)


def arrow_label(pay_by_guard):
    """The label of one arrow: per reward, its joined guards with the reward, one line each."""
    by_reward = {}
    for guard, reward in pay_by_guard:
        by_reward.setdefault(reward, []).append(guard_cube(guard))
    lines = [
        f"{guard_tex(cube)} / {reward_text(reward)}"
        for reward, cubes in sorted(by_reward.items())
        for cube in join_cubes(cubes)
    ]
    return " \\\\[2pt] ".join(lines)


# ======================================================================================
#                                        DRAWING
# ======================================================================================
LEFT, WIDTH = (
    -0.95,
    7.45,
)  # every drawing has the same width, a little under half a text width (15 cm), so rows align
TOP, BOTTOM = 1.15, 0.85  # cm above the highest and below the lowest state: heading, arcs and loops
PAD = {
    "Absence": (0.85, 1.75)
}  # (below, above) where a loop or a long label needs more room than the default
# {template: {setting or "both": (positions in cm, {"src>dst": (to-options, label-options)})}}; the default arrow
# is straight with its label above, and a loop is drawn by the options of its entry
LAYOUT = {
    "Existence": {"both": ({"u0": (0, 0), "u1": (3.4, 0)}, {})},
    "ExistenceTwo": {
        "both": (
            {"u0": (0, 0), "u1": (3.05, 0), "u2": (6.1, 0)},
            {},
        )
    },
    "Absence": {
        "hard": ({"u0": (0, 0), "u1": (3.4, 0)}, {}),
        "soft": ({"u0": (0, 0)}, {"u0>u0": ("loop above", "above")}),
    },
    "RespondedExistence": {
        "both": (
            {"u0": (0, 0), "u1": (5.6, 0), "u2": (2.8, -2.2)},
            {
                "u0>u2": ("", "below left, pos=0.5"),
                "u2>u1": ("", "below right, pos=0.5"),
            },
        )
    },
    "Response": {
        "both": (
            {"u0": (0, 0), "u1": (3.4, 0)},
            {
                "u0>u1": ("bend left=25", "above"),
                "u1>u0": ("bend left=25", "below"),
            },
        )
    },
    "Precedence": {
        "hard": (
            {"u0": (0, 0), "u1": (3.4, 0), "u2": (3.4, -2.2)},
            {"u0>u2": ("", "below left, pos=0.5")},
        ),
        "soft": (
            {"u0": (0, 0), "u1": (3.4, 0)},
            {"u0>u0": ("loop below", "below")},
        ),
    },
    "ChainResponse": {
        "hard": (
            {"u0": (0, 0), "u1": (3.4, 0), "u2": (3.4, -2.2)},
            {
                "u0>u1": ("bend left=25", "above"),
                "u1>u0": ("bend left=25", "below"),
                "u1>u2": ("", "right"),
            },
        ),
        "soft": (
            {"u0": (0, 0), "u1": (3.4, 0)},
            {
                "u0>u1": ("bend left=25", "above"),
                "u1>u0": ("bend left=25", "below"),
            },
        ),
    },
    "NotCoExistence": {
        "hard": (
            {"u0": (0, 0), "u1": (2.8, 1.5), "u2": (2.8, -1.5), "u3": (5.6, 0)},
            {
                "u0>u1": ("", "above left, pos=0.5"),
                "u0>u2": ("", "below left, pos=0.5"),
                "u1>u3": ("", "above right, pos=0.5"),
                "u2>u3": ("", "below right, pos=0.5"),
            },
        ),
        "soft": (
            {"u0": (0, 0), "u1": (4.0, 1.9), "u2": (4.0, -1.9)},
            {
                "u0>u1": ("bend left=12", "above left, pos=0.6"),
                "u1>u0": ("bend left=12", "below right, pos=0.5"),
                "u0>u2": ("bend right=12", "below left, pos=0.6"),
                "u2>u0": ("bend right=12", "above right, pos=0.5"),
                "u0>u0": ("loop above", "above"),
            },
        ),
    },
}


def layout_of(name, setting):
    options = LAYOUT[name]
    return options.get(setting) or options["both"]


def frame_of(name):
    """The lowest and highest edge of the drawings of one template, shared by hard and soft so a row lines up."""
    heights = [y for setting in SETTINGS for _, y in layout_of(name, setting)[0].values()]
    below, above = PAD.get(name, (BOTTOM, TOP))
    return min(heights) - below, max(heights) + above


def machine_tex(name, setting, paper):
    """One ``tikzpicture`` for one machine: nodes of the thesis, one arrow per pair of states."""
    positions, shapes = layout_of(name, setting)
    low, high = frame_of(name)
    lines = [
        "\\begin{tikzpicture}[farm graph, every state/.style={minimum size=7mm, inner sep=1pt}, "
        "every edge/.style={draw}, thick]",
        f"\\path[use as bounding box] ({LEFT},{low:.2f}) rectangle ({LEFT + WIDTH:.2f},{high:.2f});",
        f"\\node[anchor=north west, font=\\small\\bfseries] at ({LEFT},{high:.2f}) {{{setting.capitalize()}}};",
    ]
    for state in paper.states:
        x, y = positions[state]
        options = ["state"]
        if state == paper.initial_state:
            options.append("initial")
        if state in paper.final_states:
            options.append("accepting")
        if state in paper.rejecting_states:
            options.append("fill=gray!30")
        lines.append(f"\\node[{', '.join(options)}] ({state}) at ({x:.2f},{y:.2f}) {{{state}}};")
    pairs = {}
    for transition in paper.transitions:
        pairs.setdefault((transition.source, transition.destination), []).append(
            (transition.condition, transition.reward)
        )
    for (source, target), pay in pairs.items():
        route, place = shapes.get(f"{source}>{target}", ("", "above"))
        colour = arrow_colour([reward for _, reward in pay])
        label = (
            f"node[{place}, align=center, font=\\scriptsize, fill=white, inner sep=1pt, text={colour}] "
            f"{{{arrow_label(pay)}}}"
        )
        if source == target:
            lines.append(f"\\path[->, {colour}] ({source}) edge[{route}] {label} ();")
        else:
            lines.append(f"\\draw[->, {colour}] ({source}) to[{route}] {label} ({target});")
    lines.append("\\end{tikzpicture}")
    return "\n".join(lines) + "\n"


# ======================================================================================
#                                        FIGURES
# ======================================================================================
def row_caption(entry, same_machine):
    clause = f"{entry.name}(" + ", ".join(tex_proposition(p) for p in entry.propositions) + ")"
    text = (
        f"{clause}, ${formula_tex(entry)}$. Hard: ``{entry.hard_task}'' Soft: ``{entry.soft_task}''"
    )
    if same_machine:
        text += " The clause has no violated state, so hard and soft give the same RM."
    return text


def figure_tex(entries, number, same):
    rows = []
    for entry in entries:
        rows.append(
            "\\begin{subfigure}[t]{\\textwidth}\n\\centering\n"
            f"\\input{{images/templates/{entry.name}-hard.tex}}\\hfill"
            f"\\input{{images/templates/{entry.name}-soft.tex}}\n"
            f"\\caption{{{row_caption(entry, entry.name in same)}}}\n\\end{{subfigure}}\n"
        )
    names = ", ".join(entry.name for entry in entries)
    if number == 1:
        caption = (
            "The eight IBM templates, each compiled alone, hard on the left and soft on the right (1 of 2: "
            f"{names}). The clause is the whole task: nothing is added to the LTLf or to the RM. "
            "A double ring marks a final state and grey the rejecting well. An arrow carries the guard over "
            "the propositions and the reward, and joins the guards of the same pay; its colour follows the "
            "reward sign (green pays, red only costs, grey pays nothing or holds both signs). A stay that pays "
            "nothing is not drawn. A step toward finishing a clause pays $+1$ and one that owes more costs $-1$; "
            "finishing the task adds $+10$, entering the well costs $-10$ and each soft break $-1$."
        )
    else:
        caption = f"The eight IBM templates compiled alone, continued (2 of 2: {names}). Conventions as in Figure~\\ref{{fig:templates-alone-1}}."
    return (
        "\\begin{figure}[!htbp]\n\\centering\n"
        + "\\par\\medskip\n".join(rows)
        + f"\\caption[The eight IBM templates compiled alone ({number} of {len(FIGURES)})]{{{caption}}}\n"
        f"\\label{{fig:templates-alone-{number}}}\n\\end{{figure}}\n"
    )


def main():
    compiled = {
        entry.name: compile_entry(entry) for entry in ENTRIES
    }  # raises before anything is written
    IMAGES.mkdir(parents=True, exist_ok=True)
    records = []
    for entry in ENTRIES:
        raw, dfa, machines = compiled[entry.name]
        for setting, (text, paper) in machines.items():
            (IMAGES / f"{entry.name}-{setting}.tex").write_text(
                machine_tex(entry.name, setting, paper)
            )
            records.append(machine_record(entry, raw, dfa, setting, (text, paper)))
            print(
                f"{entry.name:19} {setting} {len(paper.states)} states, {len(paper.transitions)} transitions"
            )
    same = {name for name, (_, _, m) in compiled.items() if m["hard"][0] == m["soft"][0]}
    figures = [figure_tex(entries, number, same) for number, entries in enumerate(FIGURES, 1)]
    header = "% Generated by docs/paper/template-machines/build.py; do not edit.\n"
    (IMAGES / "all.tex").write_text(header + "\n".join(figures))
    (ENTRY / "data").mkdir(exist_ok=True)
    (ENTRY / "data/machines.json").write_text(
        json.dumps(records, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
