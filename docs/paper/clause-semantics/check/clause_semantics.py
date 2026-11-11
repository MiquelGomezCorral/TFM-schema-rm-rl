"""Clause semantics check: what each IBM template means hard, soft and recurrent soft.

Compiles every template alone (one clause, no goal) hard, soft with the recurrent soft penalty
off, and soft with it on. Walks the traces of `traces.json` through the real compiler's machines
with the real runtime, asserts the charge counts that file states, and writes `traces.txt` and
`graphs/` (SVG drawn by `app/scripts/render_rm.py`, plus the RM text). The four "eventually"
templates also run next to the stand-in hard goal `Existence(at_goal)`. No LLM calls: MONA runs
locally. A machine with no final state also judges the end of an episode the environment cuts
off: Response alone is played through `RewardMachineEnvironment` with and without that judgment.

Usage, from the repository root, inside RM_RL_env:
    PYTHONPATH=app python -W ignore docs/paper/clause-semantics/check/clause_semantics.py

Method: a charge is a step where the soft clause goes from not-violated to violated in the
reward layer's own product, never a match on -0.5. Rewards come from the runtime on the
reloaded RM text, and each must equal the price the layer gave that edge.
"""

import copy
import json
from collections import deque
from dataclasses import dataclass, field, replace
from functools import cache
from itertools import combinations
from pathlib import Path

from pylogics.syntax.ltl import Atomic

from scripts.render_rm import render_file
from src.arm_fm.runtime import RewardMachineEnvironment, RewardMachineRuntime
from src.compiler import (
    PaperRewardMachine,
    compile_dfas,
    evaluate_boolean_guard,
    materialize_proposal,
    parse_boolean_guard,
    parse_paper_reward_machine,
    reward_layer,
    serialize_reward_machine,
)
from src.compiler.reward_layer import ClauseState, _clause_labels, build_reward_machine
from src.config import Configuration, PriorityLevel
from src.engines.structured import SUPPORTED_TEMPLATES, ProposalSelection
from src.utils import dfa_text

HERE = Path(__file__).resolve().parent
README = HERE.parent / "README.md"
CONFIG = Configuration()
GOAL = ("Existence", ("at_goal",))
MINUS = chr(0x2212)
DASH = chr(0x2014)
# Each template with the DoorKey propositions of catalog-alone.json: x first, y second.
TEMPLATES = {
    "Existence": ("has_key",),
    "ExistenceTwo": ("door_open",),
    "Absence": ("key_lost",),
    "RespondedExistence": ("door_open", "has_key"),
    "Response": ("has_key", "door_open"),
    "Precedence": ("has_key", "door_open"),
    "ChainResponse": ("has_key", "door_open"),
    "NotCoExistence": ("has_key", "key_lost"),
}
# The templates whose DFA has a "broken for good" state: their soft machine changes with the switch.
REARMED = {"Absence", "Precedence", "ChainResponse", "NotCoExistence"}
GOALS = {"Existence", "ExistenceTwo"}
# RespondedExistence(x, y) has two ordered, stricter rules, written in its own letters:
# Precedence(y, x), the `y`-before version, and Response(x, y), the `y`-after version.
SPLIT_LETTERS = {"x": "door_open", "y": "has_key"}
SPLIT_RULES = {"Precedence": ("has_key", "door_open"), "Response": ("door_open", "has_key")}
SPLIT_HEADERS = {"Precedence": "`y`-before version", "Response": "`y`-after version"}
SOFT = ("soft-off", "soft-on")
COLUMNS = {
    "hard": "Hard",
    "soft-off": "Soft, recurrent off",
    "soft-on": "Soft, recurrent on (default)",
}
GOAL_COLUMNS = {"hard": "Hard", "soft-off": "Soft (recurrent off and on alike)"}
# Response alone, the time limit after the last step: total reward [hard, soft, without the end
# judgment]. The agent holds the key (x) and the door (y) opens or does not.
END_EPISODES = {"x y": (0, 0, -0.5), "- -": (0, 0, -0.5), "x - -": (-1.1, -0.6, -0.6)}
GOAL_TAGS = {"kept": "kept", "pending": "open", "late": "open, met after `g` (machine only)"}


# ======================================================================================
#                                      COMPILE
# ======================================================================================


@dataclass(frozen=True)
class Machine:
    """One compiled Reward Machine and what a walk needs from the layer's own product."""

    text: str
    paper: PaperRewardMachine
    names: tuple[str, ...]  # every proposition of the proposal
    product: reward_layer._Product
    initial: str  # the product state the walk starts from
    priced: list  # (edge, reward) pairs the layer priced
    clause: int  # index of the template's clause
    inert: bool


@dataclass(frozen=True)
class Step:
    labels: str
    state: str
    reward: float
    charged: bool
    ended: str  # "", "final" or "well"


@dataclass
class Report:
    """What the sections write: the traces.txt lines, the problems, the asserted counts."""

    out: list[str] = field(default_factory=list)
    bad: list[str] = field(default_factory=list)
    asserted: int = 0


def selection(pattern: str, propositions: tuple[str, ...], priority: str) -> ProposalSelection:
    template_class, _ = SUPPORTED_TEMPLATES[pattern]
    return ProposalSelection(
        normalized_clause=f"{pattern}({', '.join(propositions)})",
        pattern=pattern,
        propositions=propositions,
        priority=PriorityLevel(priority),
        template=template_class(*(Atomic(name) for name in propositions)),
    )


def build_captured(dfas: list[dict], soft: list[bool], recurrent: bool):
    """Run `build_reward_machine` once and keep the product and the priced edges it used.

    The numeric RM renumbers states, so the clause labels of a step are only recoverable from
    the layer's own product: wrap its two private stages and read what they receive and return.
    """
    captured = {}
    clause_product, structure = reward_layer._clause_product, reward_layer._structure

    def wrapped_product(*args, **kwargs):
        captured["product"] = clause_product(*args, **kwargs)
        return captured["product"]

    def wrapped_structure(*args, **kwargs):
        captured["initial"], captured["priced"] = args[0], args[1]
        return structure(*args, **kwargs)

    reward_layer._clause_product, reward_layer._structure = wrapped_product, wrapped_structure
    try:
        result = build_reward_machine(copy.deepcopy(dfas), soft, recurrent_soft_penalty=recurrent)
    finally:
        reward_layer._clause_product, reward_layer._structure = clause_product, structure
    return result, captured


@cache
def compile_machines(
    pattern: str, propositions: tuple[str, ...], with_goal: bool, formula: str = ""
) -> tuple[dict[str, Machine], dict]:
    """The template hard and soft (penalty off, on), alone or next to the hard stand-in goal.

    A `formula` (flat LTLf syntax) replaces the template's own, so a variant a reader may expect
    compiles through the same MONA path; `pattern` then only lends its propositions.
    Returns the machines by version and the template's LTLf, MONA DFA and DFA state labels.
    """
    machines, info = {}, {}
    for priority in ("hard", "soft"):
        companion = [selection(*GOAL, "hard")] if with_goal else []
        proposal = materialize_proposal(
            f"{pattern} {priority}", [*companion, selection(pattern, propositions, priority)]
        )
        if formula:
            last = replace(proposal.clauses[-1], ltlf_formula=formula)
            proposal = replace(proposal, clauses=(*proposal.clauses[:-1], last))
        dfas = compile_dfas(proposal, CONFIG)
        soft = [clause.priority is PriorityLevel.SOFT for clause in proposal.clauses]
        names = tuple(dict.fromkeys(n for clause in proposal.clauses for n in clause.propositions))
        info = {
            "ltlf": proposal.clauses[-1].ltlf_formula,
            "dfa": dfa_text(dfas[-1]),
            "labels": {s: label.value for s, label in sorted(_clause_labels(dfas[-1]).items())},
        }
        for recurrent in (False, True):
            result, captured = build_captured(dfas, soft, recurrent)
            text = serialize_reward_machine(result.reward_machine)
            version = ("soft-on" if recurrent else "soft-off") if priority == "soft" else "hard"
            if version == "hard" and recurrent:
                if text != machines["hard"].text:
                    raise ValueError(f"{pattern} hard compiles differently with the penalty on")
                continue
            machines[version] = Machine(
                text,
                parse_paper_reward_machine(text, propositions=names),
                names,
                captured["product"],
                captured["initial"],
                captured["priced"],
                len(proposal.clauses) - 1,
                bool(result.inert_soft_clauses),
            )
    return machines, info


# ======================================================================================
#                                        WALK
# ======================================================================================


def letters_of(propositions: tuple[str, ...], with_goal: bool) -> dict[str, str]:
    """Map the letters of a trace to propositions: x first, y second, g the stand-in goal."""
    letters = dict(zip("xy", propositions, strict=False))
    return {**letters, "g": "at_goal"} if with_goal else letters


def tokens_of(letters: dict[str, str]) -> list[str]:
    """Every step a trace can take: none (`-`), then each non-empty set of the letters."""
    return ["-"] + [
        "".join(group)
        for size in range(1, len(letters) + 1)
        for group in combinations(letters, size)
    ]


def valuation_of(machine: Machine, letters: dict[str, str], token: str) -> dict[str, bool]:
    true_names = {letters[char] for char in token if char != "-"}
    return {name: name in true_names for name in machine.names}


def walk(machine: Machine, letters: dict[str, str], trace: str) -> list[Step]:
    """Walk `trace` through the machine; an episode stops at its final or its well."""
    runtime = RewardMachineRuntime(machine.paper)
    labels = machine.product.labels
    alphabet = sorted(machine.product.alphabet)
    state = machine.initial
    steps = []
    for token in trace.split():
        valuation = valuation_of(machine, letters, token)
        step = runtime.step(valuation)
        destination, priced_reward = next(
            (edge.destination, reward)
            for edge, reward in machine.priced
            if edge.source == state
            and evaluate_boolean_guard(parse_boolean_guard(edge.guard, alphabet), valuation)
        )
        if abs(step.reward - priced_reward) > 1e-9:
            raise ValueError(f"Runtime and product disagree on {trace!r} at {token!r}")
        # a destination outside the labels is the well
        after = labels[destination][machine.clause] if destination in labels else None
        charged = labels[state][machine.clause] is not ClauseState.VIOLATED and (
            after is ClauseState.VIOLATED
        )
        ended = (
            "final"
            if runtime.state in machine.paper.final_states
            else "well"
            if runtime.state in machine.paper.rejecting_states
            else ""
        )
        steps.append(Step(token, runtime.state, round(step.reward, 9) + 0.0, charged, ended))
        state = destination
        if ended:
            break
    return steps


def move(machine: Machine, letters: dict[str, str], state: str, token: str):
    """One runtime step from a given RM state."""
    runtime = RewardMachineRuntime(machine.paper)
    runtime.state = state
    return runtime.step(valuation_of(machine, letters, token))


def witnesses(machine: Machine, letters: dict[str, str]) -> dict[str, str]:
    """The shortest trace that first reaches each RM state, for the legends."""
    found = {machine.paper.initial_state: ""}
    queue = deque(found)
    while queue:
        source = queue.popleft()
        for token in tokens_of(letters):
            destination = move(machine, letters, source, token).destination
            if destination not in found:
                found[destination] = f"{found[source]} {token}".strip()
                queue.append(destination)
    return found


def charges(steps: list[Step]) -> int:
    return sum(step.charged for step in steps)


def total(steps: list[Step]) -> float:
    return round(sum(step.reward for step in steps), 9) + 0.0


class CutOffEnvironment:
    """Plays the given valuations, then the time limit ends the episode on the last step."""

    def __init__(self, valuations: list[dict[str, bool]]) -> None:
        self.valuations = valuations
        self.current: dict[str, bool] = {}
        self.index = 0

    def reset(self, **_kwargs):
        self.index = 0
        return 0, {}

    def step(self, _action):
        self.current = self.valuations[self.index]
        self.index += 1
        return 0, 0.0, False, self.index == len(self.valuations), {}


def cut_off_total(machine: PaperRewardMachine, valuations: list[dict[str, bool]]) -> float:
    """The episode total through the wrapper, with the time limit after the last valuation."""
    labeling = {name: (lambda env, name=name: env.current[name]) for name in machine.propositions}
    environment = RewardMachineEnvironment(
        CutOffEnvironment(valuations), RewardMachineRuntime(machine), labeling
    )
    environment.reset()
    return round(sum(environment.step(0)[1] for _ in valuations), 9) + 0.0


# ======================================================================================
#                                       OUTPUT
# ======================================================================================


def number(value: float) -> str:
    return f"{value + 0.0:g}".replace("-", MINUS)


def end_note(steps: list[Step]) -> str:
    return f"ends at step {len(steps)} ({steps[-1].ended})" if steps[-1].ended else "no end"


def cell(steps: list[Step], index: int) -> str:
    if index >= len(steps):
        return DASH
    step = steps[index]
    end = f" ({step.ended})" if step.ended else ""
    return f"{step.state}{end}, {number(step.reward)}"


def total_cell(steps: list[Step], count_charges: bool) -> str:
    if not count_charges:
        return number(total(steps))
    count = charges(steps)
    return f"{number(total(steps))} ({count} charge{'' if count == 1 else 's'})"


def trace_table(trace: str, walks: dict[str, list[Step]], columns: dict[str, str]) -> str:
    """One Markdown table: a row per step, a column per version, a total row.

    Soft columns of the alone traces count their charges; the with-goal tables do not.
    """
    count = columns is COLUMNS
    lines = [
        "| Step | Labels | " + " | ".join(columns.values()) + " |",
        "|---|---|" + "---|" * len(columns),
    ]
    for index, token in enumerate(trace.split()):
        cells = " | ".join(cell(walks[v], index) for v in columns)
        lines.append(f"| {index + 1} | `{token}` | {cells} |")
    totals = " | ".join(total_cell(walks[v], count and v != "hard") for v in columns)
    return "\n".join([*lines, f"| **Total** | | {totals} |"])


def summary_table(walks: dict[str, dict[str, list[Step]]]) -> str:
    """One row per trace: how the hard episode goes, and the soft total with its charges."""
    lines = ["| Trace | " + " | ".join(COLUMNS.values()) + " |", "|---|---|---|---|"]
    for trace, per_version in walks.items():
        hard = per_version["hard"]
        cells = [f"{number(total(hard))}, {end_note(hard)}"]
        cells += [total_cell(per_version[v], True) for v in SOFT]
        lines.append(f"| `{trace}` | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def goal_summary_table(walks: dict) -> str:
    """One row per trace next to the goal: the rule when `g` arrives, hard and soft end."""
    lines = [
        "| Trace | Rule when `g` arrives | Hard | " + GOAL_COLUMNS["soft-off"] + " |",
        "|---|---|---|---|",
    ]
    for trace, (tag, per_version) in walks.items():
        cells = [
            f"{number(total(per_version[v]))}, {end_note(per_version[v])}" for v in GOAL_COLUMNS
        ]
        lines.append(f"| `{trace}` | {GOAL_TAGS[tag]} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def exit_table(machines: dict[str, Machine], letters: dict[str, str], walks: dict) -> str:
    """Where the broken state goes on each next step, with the switch off and on."""
    broken = {s.state for per in walks.values() for v in SOFT for s in per[v] if s.charged}
    (state,) = broken  # one broken state in both machines, or this fails loudly
    lines = ["| Next step | " + " | ".join(COLUMNS[v] for v in SOFT) + " |", "|---|---|---|"]
    for token in tokens_of(letters):
        moves = [move(machines[v], letters, state, token) for v in SOFT]
        cells = [f"{m.destination}, {number(round(m.reward, 9))}" for m in moves]
        lines.append(f"| `{token}` | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def split_table(rows: dict[str, dict[str, tuple[int, int]]]) -> str:
    """Charges, recurrent on / off, of RespondedExistence and of its two ordered rules."""
    headers = [SPLIT_HEADERS[name] for name in SPLIT_RULES]
    lines = ["| Trace | RespondedExistence | " + " | ".join(headers) + " |", "|---|---|---|---|"]
    for trace, row in rows.items():
        pairs = (row["RespondedExistence"], *(row[name] for name in SPLIT_RULES))
        lines.append(f"| `{trace}` | " + " | ".join(f"{on} / {off}" for on, off in pairs) + " |")
    return "\n".join(lines)


def draw(machines: dict[str, Machine], stem: str, graphs: Path) -> dict[str, str]:
    """Write `<stem>.<name>.rm` and `.svg` once per distinct machine; return version -> file stem."""
    groups: dict[str, list[str]] = {}
    for version, machine in machines.items():
        groups.setdefault(machine.text, []).append(version)
    stems = {}
    for text, versions in groups.items():
        if len(versions) == 2 and versions != list(SOFT):
            raise ValueError(f"{stem}: unexpected machines shared by {versions}")
        name = {1: versions[0], 2: "soft", 3: "all"}[len(versions)]
        rm_path = graphs / f"{stem}.{name}.rm"
        rm_path.write_text(text, encoding="utf-8")
        render_file(rm_path, rm_path.with_suffix(".svg"))
        stems.update(dict.fromkeys(versions, rm_path.stem))
    return stems


def machine_section(machines: dict[str, Machine], letters: dict, stems: dict) -> list[str]:
    out = []
    for version, machine in machines.items():
        legend = "\n".join(
            f"{state} first reached by `{path or 'start'}`"
            for state, path in witnesses(machine, letters).items()
        )
        out += [
            f"#### {COLUMNS[version]} (graph graphs/{stems[version]}.svg)",
            f"final {machine.paper.final_states or '-'}, well {machine.paper.rejecting_states or '-'}",
            legend,
            "```",
            machine.text.strip(),
            "```",
        ]
    return out


# ======================================================================================
#                                       CHECKS
# ======================================================================================


def check_alone(pattern: str, machines: dict[str, Machine], walks: dict, expected: dict, bad: list):
    """The asserted charges, the hard end of each irreparable rule, and that no soft rule is inert."""
    off, on = machines["soft-off"], machines["soft-on"]
    if (off.text != on.text) != (pattern in REARMED):
        bad.append(f"{pattern}: the soft machines differ with the switch: {off.text != on.text}")
    if pattern not in GOALS and machines["hard"].paper.final_states:
        bad.append(f"{pattern} alone: a hard rule alone must not have a final")
    if off.inert or on.inert:
        bad.append(f"{pattern}: no soft rule alone may be inert (progress or a break pays it)")
    for trace, per_version in walks.items():
        hard, soft_off, soft_on = (per_version[v] for v in ("hard", *SOFT))
        got, wanted = [charges(soft_on), charges(soft_off)], expected[trace]
        if wanted is not None and got != wanted:
            steps = {v: [(s.state, s.reward) for s in w] for v, w in per_version.items()}
            bad.append(
                f"{pattern} {trace!r}: charges on/off {got}, expected {wanted}; steps {steps}"
            )
        first_charge = next((i for i, s in enumerate(soft_off) if s.charged), None)
        hard_well = next((i for i, s in enumerate(hard) if s.ended == "well"), None)
        if pattern in REARMED and first_charge != hard_well:
            bad.append(
                f"{pattern} {trace!r}: hard well at {hard_well}, first soft charge at {first_charge}"
            )
        if hard_well is not None and hard[-1].reward != CONFIG.WELL_REWARD:
            bad.append(f"{pattern} {trace!r}: the well must pay {CONFIG.WELL_REWARD}")
        if pattern not in REARMED and hard_well is not None:
            bad.append(f"{pattern} {trace!r}: a repairable rule alone must never reach the well")


def check_goal(pattern: str, walks: dict, bad: list) -> None:
    """Soft ends at the goal step and pays 0.5 less when the rule is open; hard waits for the rule.

    The progress term is potential-based, so every full run pays the same total once the rule is
    kept; a rule still open at the finish costs `SOFT_PENDING_AT_FINISH_REWARD` more.
    """
    kept_total = next(total(w["soft-off"]) for tag, w in walks.values() if tag == "kept")
    for trace, (tag, per_version) in walks.items():
        soft, hard = per_version["soft-off"], per_version["hard"]
        goal_step = next(i for i, token in enumerate(trace.split(), 1) if "g" in token)
        wanted = kept_total + (0.0 if tag == "kept" else CONFIG.SOFT_PENDING_AT_FINISH_REWARD)
        if len(soft) != goal_step or soft[-1].ended != "final" or abs(total(soft) - wanted) > 1e-9:
            bad.append(
                f"{pattern} {trace!r} soft: expected the final at step {goal_step} paying {wanted}"
            )
        if per_version["soft-on"] != soft:
            bad.append(f"{pattern} {trace!r}: the soft machines differ with the switch")
        hard_final = len(hard) if hard[-1].ended == "final" else None
        if hard_final != {"kept": goal_step, "late": len(trace.split()), "pending": None}[tag]:
            bad.append(f"{pattern} {trace!r} hard: finished at step {hard_final}, rule {tag!r}")


def check_goal_charges(pattern: str, walks: dict, report: Report) -> None:
    """The same traces next to the goal charge the same as alone."""
    propositions = TEMPLATES[pattern]
    machines, _ = compile_machines(pattern, propositions, with_goal=True)
    letters = letters_of(propositions, with_goal=True)
    for trace, per_version in walks.items():
        for version in SOFT:
            report.asserted += 1
            if charges(walk(machines[version], letters, trace)) != charges(per_version[version]):
                report.bad.append(f"{pattern} {trace!r} {version}: charges change next to the goal")


def readme_tables_match(out_text: str) -> list[str]:
    """Every README table that opens with Step, Trace or Next step must sit verbatim in the output."""
    starts = ("| Step |", "| Trace |", "| Next step |")
    return [
        f"README table not in traces.txt: {block.splitlines()[0]} / {block.splitlines()[2]}"
        for block in README.read_text(encoding="utf-8").split("\n\n")
        if block.startswith(starts) and block not in out_text
    ]


# ======================================================================================
#                                       SECTIONS
# ======================================================================================


def alone_section(report: Report, spec: dict, graphs: Path) -> None:
    """Each template alone: its machines, summary, one table per trace, and the broken-state exits."""
    for pattern, propositions in TEMPLATES.items():
        machines, info = compile_machines(pattern, propositions, with_goal=False)
        letters = letters_of(propositions, with_goal=False)
        stems = draw(machines, pattern, graphs)
        expected = spec["alone"][pattern]
        walks = {t: {v: walk(m, letters, t) for v, m in machines.items()} for t in expected}
        report.asserted += sum(wanted is not None for wanted in expected.values())
        check_alone(pattern, machines, walks, expected, report.bad)
        report.out += [
            f"\n## {pattern}",
            f"x = {propositions[0]}"
            + (f", y = {propositions[1]}" if len(propositions) > 1 else ""),
            f"LTLf {info['ltlf']}",
            f"MONA DFA (state labels {info['labels']})",
            "```",
            info["dfa"],
            "```",
            "### Machines",
            *machine_section(machines, letters, stems),
            "### Summary",
            summary_table(walks),
        ]
        if pattern in REARMED:
            check_goal_charges(pattern, walks, report)
            report.out += [f"### After a charge: {pattern}", exit_table(machines, letters, walks)]
        report.out.append("### Traces")
        for trace, per_version in walks.items():
            report.out += [f"#### {pattern}: {trace}", trace_table(trace, per_version, COLUMNS)]


def goal_section(report: Report, spec: dict, graphs: Path) -> None:
    """The four "eventually" templates next to the stand-in goal: kept against open at the finish."""
    for pattern, cases in spec["with_goal"].items():
        propositions = TEMPLATES[pattern]
        machines, _ = compile_machines(pattern, propositions, with_goal=True)
        letters = letters_of(propositions, with_goal=True)
        stems = draw(machines, f"{pattern}.goal", graphs)
        walks = {
            t: (tag, {v: walk(m, letters, t) for v, m in machines.items()}) for t, tag in cases
        }
        check_goal(pattern, walks, report.bad)
        report.asserted += len(cases)
        report.out += [
            f"\n## {pattern} with the goal Existence(at_goal)",
            "### Machines",
            *machine_section(machines, letters, stems),
            "### Summary",
            goal_summary_table(walks),
            "### Traces",
        ]
        for trace, (tag, per_version) in walks.items():
            report.out += [
                f"#### {pattern} with goal: {trace} ({tag})",
                trace_table(trace, per_version, GOAL_COLUMNS),
            ]


def split_section(report: Report, spec: dict) -> None:
    """RespondedExistence against its two ordered rules, Precedence(y, x) and Response(x, y)."""
    rules = {"RespondedExistence": TEMPLATES["RespondedExistence"], **SPLIT_RULES}
    machines = {
        name: compile_machines(name, props, with_goal=False)[0] for name, props in rules.items()
    }
    rows = {}
    for trace, wanted in spec["responded_existence_split"].items():
        # (charges recurrent on, charges recurrent off), in RespondedExistence's letters
        rows[trace] = {
            name: tuple(charges(walk(m[v], SPLIT_LETTERS, trace)) for v in reversed(SOFT))
            for name, m in machines.items()
        }
        if wanted is not None:
            report.asserted += 1
            if list(rows[trace]["Precedence"]) != wanted:
                got = rows[trace]["Precedence"]
                report.bad.append(f"split {trace!r}: Precedence(y, x) {got}, expected {wanted}")
        if rows[trace]["Response"] != (0, 0) or rows[trace]["RespondedExistence"] != (0, 0):
            report.bad.append(f"split {trace!r}: Response(x, y) or RespondedExistence charged")
    report.out += ["\n## RespondedExistence and its two ordered rules", split_table(rows)]


def chain_goal_section(report: Report, spec: dict, graphs: Path) -> None:
    """ChainResponse next to the goal: a break, or an obligation opened on the last step, costs 0.5."""
    props = TEMPLATES["ChainResponse"]
    machines, _ = compile_machines("ChainResponse", props, with_goal=True)
    letters = letters_of(props, with_goal=True)
    stems = draw(machines, "ChainResponse.goal", graphs)
    cases = spec["chain_with_goal"]
    walks = {t: {v: walk(m, letters, t) for v, m in machines.items()} for t, _, _ in cases}
    cost = {
        "clean": 0.0,
        "break": CONFIG.SOFT_BREAK_REWARD,
        "open": CONFIG.SOFT_PENDING_AT_FINISH_REWARD,
    }
    clean = {v: total(walks[cases[0][0]][v]) for v in SOFT}  # the first case is the clean finish
    report.out += [
        "\n## ChainResponse with the goal Existence(at_goal)",
        "### Machines",
        *machine_section(machines, letters, stems),
        "### Traces",
    ]
    for trace, kind, wanted in cases:
        report.asserted += 1
        got = [charges(walks[trace]["soft-on"]), charges(walks[trace]["soft-off"])]
        if got != wanted:
            report.bad.append(
                f"ChainResponse with goal {trace!r}: charges on/off {got}, expected {wanted}"
            )
        if any(abs(total(walks[trace][v]) - (clean[v] + cost[kind])) > 1e-9 for v in SOFT):
            report.bad.append(
                f"ChainResponse with goal {trace!r}: the finish must cost {cost[kind]} ({kind})"
            )
        report.out += [
            f"#### ChainResponse with goal: {trace} ({kind})",
            trace_table(trace, walks[trace], COLUMNS),
        ]


def doorkey_section(report: Report, spec: dict) -> None:
    """Real DoorKey episodes: NotCoExistence(has_key, key_lost) charges what Absence(key_lost) charges."""
    names = ("NotCoExistence", "Absence")
    machines = {n: compile_machines(n, TEMPLATES[n], with_goal=False)[0] for n in names}
    lines = [
        "| Trace | DoorKey episode | NotCoExistence(has_key, key_lost) | Absence(key_lost) |",
        "|---|---|---|---|",
    ]
    for episode in spec["doorkey_episodes"]:
        counts = {
            n: [
                charges(walk(machines[n][v], letters_of(TEMPLATES[n], False), episode[n]))
                for v in reversed(SOFT)
            ]
            for n in names
        }
        report.asserted += 1
        if not counts["NotCoExistence"] == counts["Absence"] == episode["charges"]:
            report.bad.append(
                f"DoorKey {episode['story']!r}: charges on/off {counts}, expected {episode['charges']}"
            )
        nce, absence = (" / ".join(map(str, counts[n])) for n in names)
        lines.append(
            f"| `{episode['NotCoExistence']}` | {episode['story']} | {nce} | `{episode['Absence']}`: {absence} |"
        )
    report.out += ["\n## DoorKey episodes: NotCoExistence against Absence", "\n".join(lines)]


def contrast_cell(walks: dict[str, list[Step]]) -> str:
    """How the hard episode goes, and the soft charges recurrent on / off."""
    hard = walks["hard"]
    on, off = charges(walks["soft-on"]), charges(walks["soft-off"])
    return f"{number(total(hard))}, {end_note(hard)}; charges {on} / {off}"


def end_section(report: Report) -> None:
    """Response alone, cut off by the time limit: what the end judgment charges for an open `y`."""
    pattern = "Response"
    machines, _ = compile_machines(pattern, TEMPLATES[pattern], with_goal=False)
    letters = letters_of(TEMPLATES[pattern], with_goal=False)
    lines = ["| Trace | Hard | Soft | Without the end judgment |", "|---|---|---|---|"]
    for trace, wanted in END_EPISODES.items():
        valuations = [valuation_of(machines["hard"], letters, token) for token in trace.split()]
        hard, soft = (cut_off_total(machines[v].paper, valuations) for v in ("hard", "soft-on"))
        without = {
            cut_off_total(replace(machines[v].paper, judgment=None), valuations)
            for v in ("hard", "soft-on")
        }
        report.asserted += len(wanted)
        if (hard, soft, *without) != wanted:  # both versions must agree without the judgment
            report.bad.append(f"{pattern} {trace!r}: totals {hard, soft, without} != {wanted}")
        lines.append(f"| `{trace}` | {number(hard)} | {number(soft)} | {number(min(without))} |")
    report.out += [f"\n## End of the episode: {pattern}", *lines]


def counter_section(report: Report, spec: dict, graphs: Path) -> None:
    """Raw LTLf variants a reader may expect, walked next to the template they get mistaken for."""
    for case in spec["counter_cases"]:
        name, like, formula = case["name"], case["like"], case["formula"]
        props = TEMPLATES[like]
        letters = letters_of(props, with_goal=False)
        variant, info = compile_machines(like, props, False, formula)
        real, _ = compile_machines(like, props, False)
        stems = draw(variant, f"Variant.{name}", graphs)
        lines = [f"| Trace | {like} | Variant {name} |", "|---|---|---|"]
        for trace, wanted in case["traces"].items():
            walks = {
                "real": {v: walk(m, letters, trace) for v, m in real.items()},
                "variant": {v: walk(m, letters, trace) for v, m in variant.items()},
            }
            for key in ("variant", "real"):
                report.asserted += 1
                got = [charges(walks[key]["soft-on"]), charges(walks[key]["soft-off"])]
                if got != wanted[key]:
                    report.bad.append(
                        f"variant {name} {trace!r} {key}: charges {got}, expected {wanted[key]}"
                    )
            for key, end in zip(("variant", "real"), wanted.get("ends", ()), strict=False):
                if walks[key]["hard"][-1].ended != end:
                    report.bad.append(
                        f"variant {name} {trace!r} {key}: hard episode must end in {end!r}"
                    )
            lines.append(
                f"| `{trace}` | {contrast_cell(walks['real'])} | {contrast_cell(walks['variant'])} |"
            )
        report.out += [
            f"\n## Variant {name}: {case['says']}",
            f"x = {props[0]}" + (f", y = {props[1]}" if len(props) > 1 else ""),
            f"LTLf {formula}",
            f"MONA DFA (state labels {info['labels']})",
            "```",
            info["dfa"],
            "```",
            "### Machines",
            *machine_section(variant, letters, stems),
            "### Contrast",
            "\n".join(lines),
        ]


def main() -> None:
    spec = json.loads((HERE / "traces.json").read_text(encoding="utf-8"))
    graphs = HERE / "graphs"
    graphs.mkdir(exist_ok=True)
    for stale in graphs.iterdir():  # the folder holds only this script's output
        stale.unlink()
    report = Report(
        out=[
            "# Clause semantics: every trace, walked through the real compiler and runtime",
            f"Rewards: soft break {number(CONFIG.SOFT_BREAK_REWARD)}, well {number(CONFIG.WELL_REWARD)}, "
            f"completion {number(CONFIG.TASK_COMPLETION_REWARD)}, "
            f"progress {number(CONFIG.PROGRESS_REWARD)} per step closer to the final (with none, to the "
            f"states where no rule is pending), "
            f"soft rule open at the finish {number(CONFIG.SOFT_PENDING_AT_FINISH_REWARD)}",
        ]
    )
    alone_section(report, spec, graphs)
    goal_section(report, spec, graphs)
    split_section(report, spec)
    chain_goal_section(report, spec, graphs)
    doorkey_section(report, spec)
    counter_section(report, spec, graphs)
    end_section(report)

    verdict = f"{report.asserted} asserted counts checked, {len(report.bad)} differ"
    text = "\n".join([*report.out, "", verdict]) + "\n"
    (HERE / "traces.txt").write_text(text, encoding="utf-8")
    problems = report.bad + (readme_tables_match(text) if README.exists() else [])
    for problem in problems:
        print("DIFF", problem)
    print(verdict)
    if problems:
        raise SystemExit(f"{len(problems)} problems, see above")
    print("OK: all assertions hold; wrote traces.txt and graphs/")


if __name__ == "__main__":
    main()
