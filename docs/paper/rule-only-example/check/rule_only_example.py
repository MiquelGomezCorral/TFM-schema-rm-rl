"""Rule-only example: recompute one FARM bundle's clauses, machine, edge pays and a trace.

Rebuilds the bundle's Reward Machine from its stored clauses (LTLf, MONA, FL-AT, reward layer) and
asserts it equals the stored `reward_machine.txt`. Then, with the real runtime, it reads off the
clauses with their LTLf, the pay of every case of every state (split into progress and the soft
break or well charge, by rebuilding the same machine with the progress part off), a short trace
(`trace.json`) and the card's recorded plan traces. Every trace step is also checked against the
layer's own numeric transitions. Writes `evidence/` and draws the graph with
`app/scripts/render_rm.py`. No model call: MONA runs locally.

Usage, from the repository root, inside RM_RL_env, on the frozen code (see the README):
    PYTHONPATH=<copy of 809dfe3>/app python -W ignore \
        docs/paper/rule-only-example/check/rule_only_example.py

Method: every number comes from the frozen reward layer or runtime. The README pastes the tables
of `evidence/`, and the script fails when one differs.
"""

import argparse
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, replace
from itertools import combinations, product
from pathlib import Path

import src
from scripts.ablate_rm import _build, _recorded_switches, _stored_task
from scripts.render_rm import render_file
from src.arm_fm import ArtifactBundle, load_bundle
from src.arm_fm.runtime import RewardMachineRuntime
from src.compiler import (
    CompilationResult,
    PaperRewardMachine,
    Proposal,
    RewardSwitches,
    compile_dfas,
    evaluate_boolean_guard,
    parse_boolean_guard,
    serialize_paper_reward_machine,
)
from src.compiler.reward_layer import clause_labels, hard_break_charge
from src.config import Configuration

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BUNDLE = ROOT / "experiments/benchmark/complex/bundles/farm/cx-rules-only"
PLAN_TRACES = ROOT / "experiments/benchmark/complex/traces/cx-rules-only"
FREEZE = "809dfe3"

Valuation = tuple[bool, ...]  # one value per proposition, in `Rebuilt.names` order
Cube = tuple[bool | None, ...]  # None: the proposition does not matter


# ======================================================================================
#                                      REBUILD
# ======================================================================================
@dataclass(frozen=True)
class Rebuilt:
    """What the frozen code builds from the clauses a bundle stores."""

    bundle: ArtifactBundle
    proposal: Proposal
    dfas: tuple[dict, ...]
    switches: RewardSwitches
    result: CompilationResult
    machine: PaperRewardMachine
    no_progress: PaperRewardMachine  # the same machine with the progress part off

    @property
    def names(self) -> tuple[str, ...]:
        return self.machine.used_propositions


def rebuild(bundle_dir: Path) -> Rebuilt:
    """Rebuild the bundle's machine and its progress-off twin, and check both against the bundle."""
    CONFIG = Configuration()
    CONFIG.bundle = bundle_dir
    bundle = load_bundle(bundle_dir)
    environment, proposal = _stored_task(CONFIG, bundle)
    dfas = tuple(compile_dfas(proposal, CONFIG))
    switches = _recorded_switches(bundle)
    result, machine = _build(environment, proposal, dfas, switches)

    stored = serialize_paper_reward_machine(bundle.reward_machine)
    assert serialize_paper_reward_machine(machine) == stored
    assert result.text == (bundle_dir / "reward_machine.txt").read_text(encoding="utf-8")
    assert result.reward_machine.final_state is None, "not a rule-only machine"
    assert machine.judgment is None, "the machine judges the end of an episode"

    # The progress-off twin must keep the stored states, or the split of a pay is not per state.
    unmerged = replace(switches, minimize_machine=False)
    assert (
        serialize_paper_reward_machine(_build(environment, proposal, dfas, unmerged)[1]) == stored
    )
    twin = replace(unmerged, reward_progress=False)
    no_progress = _build(environment, proposal, dfas, twin)[1]
    assert no_progress.states == machine.states
    return Rebuilt(bundle, proposal, dfas, switches, result, machine, no_progress)


# ======================================================================================
#                                      CLAUSES
# ======================================================================================
def unwrap(text: str) -> str:
    """Drop one pair of parentheses that encloses the whole text."""
    depth = 0
    for position, char in enumerate(text):
        depth += (char == "(") - (char == ")")
        if depth == 0 and position < len(text) - 1:
            return text
    return text[1:-1] if text.startswith("(") else text


def readable(flat: str) -> str:
    """The FL-AT formula in standard notation: ``(~(Fa))`` becomes ``¬(F a)``."""
    spaced = re.sub(r"([FGX])(?=[(a-z_])", r"\1 ", flat)
    return unwrap(spaced.replace("~", "¬").replace("->", " → "))


def clause_rows(built: Rebuilt) -> list[dict]:
    """One row per clause: its sentence, template, LTLf and DFA."""
    rows = []
    for number, (clause, dfa) in enumerate(zip(built.proposal.clauses, built.dfas, strict=True), 1):
        rows.append(
            {
                "number": number,
                "sentence": clause.normalized_clause,
                "template": clause.pattern,
                "propositions": list(clause.propositions),
                "priority": str(clause.priority),
                "ltlf_flat": clause.ltlf_formula,
                "ltlf": readable(clause.ltlf_formula),
                "dfa_states": len(dfa["states"]),
                "dfa_accepting": sorted(dfa["accepting_states"]),
                "dfa_labels": {s: str(label) for s, label in sorted(clause_labels(dfa).items())},
            }
        )
    return rows


def pay_unit(value: float) -> str:
    """A pay with at most three decimals: ``-100.694``, ``+1``, ``0``."""
    text = f"{value:+.3f}".rstrip("0").rstrip(".")
    return "0" if text in {"+0", "-0"} else text


def table(headers: list[str], rows: list[list[str]]) -> str:
    """A Markdown table."""
    lines = [f"| {' | '.join(headers)} |", f"|{'---|' * len(headers)}"]
    lines += [f"| {' | '.join(row)} |" for row in rows]
    return "\n".join(lines)


def clause_table(rows: list[dict]) -> str:
    return table(
        ["#", "Sentence", "Template", "Priority", "LTLf"],
        [
            [
                str(row["number"]),
                row["sentence"],
                f"`{row['template']}({', '.join(row['propositions'])})`",
                row["priority"],
                f"`{row['ltlf']}`",
            ]
            for row in rows
        ],
    )


# ======================================================================================
#                                     EDGE PAYS
# ======================================================================================
@dataclass(frozen=True)
class Outcome:
    """What the runtime does with one valuation in one state."""

    destination: str
    pay: float
    fired: bool  # False: no transition matches, the machine stays and pays 0


def outcomes(
    machine: PaperRewardMachine, names: tuple[str, ...], state: str
) -> dict[Valuation, Outcome]:
    """Where each full valuation of ``names`` takes the machine from ``state``, and what it pays."""
    runtime = RewardMachineRuntime(machine, propositions=names)
    result = {}
    for bits in product((False, True), repeat=len(names)):
        runtime.state = state
        step = runtime.step(dict(zip(names, bits, strict=True)))
        result[bits] = Outcome(step.destination, step.reward, step.transition is not None)
    return result


def covered(cube: Cube, bits: Valuation) -> bool:
    return all(want is None or want == have for want, have in zip(cube, bits, strict=True))


def prime_cubes(minterms: set[Valuation]) -> set[Cube]:
    """Every prime implicant of a set of valuations (Quine-McCluskey merging)."""
    cubes: set[Cube] = set(minterms)
    primes: set[Cube] = set()
    while cubes:
        merged: set[Cube] = set()
        used: set[Cube] = set()
        for first, second in combinations(sorted(cubes, key=str), 2):
            differ = [i for i, (a, b) in enumerate(zip(first, second, strict=True)) if a != b]
            if len(differ) == 1 and None not in (first[differ[0]], second[differ[0]]):
                merged.add(tuple(None if i == differ[0] else a for i, a in enumerate(first)))
                used |= {first, second}
        primes |= cubes - used
        cubes = merged
    return primes


def cover(minterms: set[Valuation]) -> list[Cube]:
    """A short list of cubes that holds exactly ``minterms`` (greedy over the prime implicants)."""
    primes = sorted(prime_cubes(minterms), key=str)
    chosen: list[Cube] = []
    left = set(minterms)
    while left:
        best = max(primes, key=lambda cube: sum(covered(cube, bits) for bits in left))
        chosen.append(best)
        left = {bits for bits in left if not covered(best, bits)}
    width = len(next(iter(minterms)))
    every = product((False, True), repeat=width)
    held = {bits for bits in every if any(covered(cube, bits) for cube in chosen)}
    assert held == minterms, "the cubes do not hold exactly the valuations"
    return chosen


def guard_text(cubes: list[Cube], names: tuple[str, ...]) -> str:
    """The cubes as a guard: literals joined by ``&``, cubes by ``or``, ``!`` for a false value."""
    parts = [
        " & ".join(
            ("" if want else "!") + name
            for name, want in zip(names, cube, strict=True)
            if want is not None
        )
        for cube in sorted(cubes, key=str)
    ]
    return " or ".join(f"({part})" for part in parts) if len(parts) > 1 else parts[0]


@dataclass(frozen=True)
class PayGroup:
    """The cases of one state that go to the same state and pay the same."""

    source: str
    destination: str
    pay: float
    progress: float  # the pay of the full machine minus that of the progress-off twin
    charge: float  # the pay of the progress-off twin: a soft break or the well charge
    cases: int  # how many of the full valuations of the used propositions
    fired: bool
    guard: str


def pay_groups(built: Rebuilt) -> list[PayGroup]:
    """Every case of every live state (all valuations of the used propositions), grouped by outcome."""
    machine, names = built.machine, built.names
    groups: dict[tuple, list[Valuation]] = defaultdict(list)
    for state in machine.states:
        if state in machine.rejecting_states:
            continue  # the episode ends in the well
        full = outcomes(machine, names, state)
        rest = outcomes(built.no_progress, names, state)
        for bits, outcome in full.items():
            assert rest[bits].destination == outcome.destination, "progress changes the target"
            assert rest[bits].fired == outcome.fired, "progress changes which cases fire"
            pays = (round(outcome.pay, 9), round(rest[bits].pay, 9))
            groups[state, outcome.destination, *pays, outcome.fired].append(bits)

    def reading_order(item: tuple[tuple, list[Valuation]]) -> tuple:
        (state, destination, pay, _, _), _ = item
        # per state: stays, then moves, then the well; the best pay first
        return (
            state,
            destination in machine.rejecting_states,
            destination != state,
            destination,
            -pay,
        )

    result = []
    for (state, destination, pay, charge, fired), cases in sorted(
        groups.items(), key=reading_order
    ):
        guard = guard_text(cover(set(cases)), names) if fired else "else"
        progress = round(pay - charge, 9)
        result.append(PayGroup(state, destination, pay, progress, charge, len(cases), fired, guard))
    return result


def what_happens(group: PayGroup, machine: PaperRewardMachine) -> str:
    """Name the parts of a pay: the well, a soft rule breaking, a promise opening or kept."""
    if group.destination in machine.rejecting_states:
        return "hard rule broken: the well"
    parts = []
    if group.charge < 0:
        parts.append("a soft rule breaks")
    if group.progress < 0:
        parts.append("a promise opens")
    if group.progress > 0:
        parts.append("a promise is kept")
    return " and ".join(parts) or "nothing"


def pay_table(groups: list[PayGroup], machine: PaperRewardMachine) -> str:
    def state(name: str) -> str:
        return f"{name} (well)" if name in machine.rejecting_states else name

    return table(
        ["From", "When", "To", "Pay", "Progress", "Break or well", "What happens"],
        [
            [
                group.source,
                f"`{group.guard}`" if group.fired else "else",
                state(group.destination),
                pay_unit(group.pay),
                pay_unit(group.progress),
                pay_unit(group.charge),
                what_happens(group, machine),
            ]
            for group in groups
        ],
    )


def edge_table(built: Rebuilt) -> str:
    """The stored transitions as the layer wrote them, each pay split into its two parts."""
    twins = {(t.source, t.condition): t for t in built.no_progress.transitions}
    rows = []
    for edge in built.machine.transitions:
        twin = twins[edge.source, edge.condition]
        assert twin.destination == edge.destination
        rows.append(
            [
                edge.source,
                f"`{edge.condition}`",
                edge.destination,
                pay_unit(edge.reward),
                pay_unit(edge.reward - twin.reward),
                pay_unit(twin.reward),
            ]
        )
    return table(["From", "Guard", "To", "Pay", "Progress", "Break or well"], rows)


# ======================================================================================
#                                       TRACES
# ======================================================================================
@dataclass(frozen=True)
class TraceStep:
    number: int
    labels: tuple[str, ...]  # the machine's propositions that are true
    source: str
    destination: str
    pay: float
    total: float


def walk(
    machine: PaperRewardMachine, names: tuple[str, ...], steps: list[dict[str, bool]]
) -> list[TraceStep]:
    """Run label sets through the real runtime; the episode stops in the well."""
    runtime = RewardMachineRuntime(machine, propositions=names)
    walked, total = [], 0.0
    for number, labels in enumerate(steps, start=1):
        step = runtime.step(labels)
        total = round(total + step.reward, 9)
        true_names = tuple(name for name in names if labels.get(name))
        walked.append(
            TraceStep(number, true_names, step.source, step.destination, step.reward, total)
        )
        if step.destination in machine.rejecting_states:
            break
    return walked


def layer_step(built: Rebuilt, source: str, labels: tuple[str, ...]) -> tuple[str, float]:
    """The layer's own numeric transition for one step: the first whose guard holds, else stay at 0."""
    structure = built.result.reward_machine
    alphabet = built.machine.propositions
    valuation = {name: name in labels for name in alphabet}
    state = structure.states[int(source[1:])]
    for item in structure.transitions:
        guard = parse_boolean_guard("&".join(item.condition) or "true", alphabet)
        if item.source == state and evaluate_boolean_guard(guard, valuation):
            return f"u{structure.states.index(item.destination)}", item.reward
    return source, 0.0


def check_against_layer(built: Rebuilt, walked: list[TraceStep]) -> None:
    """Each step's state and pay must equal the layer's own numeric transition for that step."""
    for step in walked:
        destination, pay = layer_step(built, step.source, step.labels)
        assert destination == step.destination, f"step {step.number}: state differs"
        assert abs(pay - step.pay) < 1e-9, f"step {step.number}: pay differs"


def trace_table(walked: list[TraceStep], notes: list[str]) -> str:
    rows = [
        [
            str(step.number),
            ", ".join(f"`{name}`" for name in step.labels) or "none",
            f"{step.source} -> {step.destination}",
            pay_unit(step.pay),
            pay_unit(step.total),
            notes[step.number - 1],
        ]
        for step in walked
    ]
    return table(["Step", "Labels true", "State", "Pay", "Total", "What happens"], rows)


def plan_trace_table(built: Rebuilt) -> str:
    """The card's recorded plan traces (real environment labels): the steps that move or pay."""
    rows = []
    for path in sorted(PLAN_TRACES.glob("*.json")):
        labels = json.loads(path.read_text(encoding="utf-8"))["labels"]
        walked = walk(built.machine, built.names, labels)
        check_against_layer(built, walked)
        events = [step for step in walked if step.pay or step.source != step.destination]
        moves = "; ".join(
            f"{step.number}: {step.source} -> {step.destination} ({pay_unit(step.pay)})"
            for step in events
        )
        rows.append([f"`{path.stem}`", str(len(walked)), moves, pay_unit(walked[-1].total)])
    return table(["Plan trace", "Steps", "Steps where the machine moves or pays", "Total"], rows)


# ======================================================================================
#                                        MAIN
# ======================================================================================
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bundle", type=Path, default=BUNDLE)
    parser.add_argument("--trace", type=Path, default=HERE / "trace.json")
    parser.add_argument("--out", type=Path, default=HERE.parent / "evidence")
    args = parser.parse_args()

    built = rebuild(args.bundle)
    machine, names, settings = built.machine, built.names, built.switches
    code = Path(src.__file__).parent.parent
    where = code.relative_to(ROOT) if code.is_relative_to(ROOT) else "a copy outside the repository"
    report = [f"code: {where}", f"bundle: {args.bundle.relative_to(ROOT)}"]
    report.append("rebuilt machine equals the stored reward_machine.txt: OK")

    trace = json.loads(args.trace.read_text(encoding="utf-8"))
    steps = [{name: name in step for name in names} for step in trace["steps"]]
    walked = walk(machine, names, steps)
    check_against_layer(built, walked)
    assert len(walked) == len(trace["notes"]), "one note per trace step"
    report.append(f"trace of {len(walked)} steps equals the layer's own transitions: OK")

    well_charge = hard_break_charge(
        settings.soft_break_cost, settings.gamma, settings.step_limit, settings.soft_breaks_per_step
    )
    well_pays = {e.reward for e in machine.transitions if e.destination in machine.rejecting_states}
    assert well_pays == {round(well_charge, 9)}, f"well pays {well_pays}, charge {well_charge}"
    report.append(f"every edge into the well pays hard_break_charge = {well_charge:.9f}: OK")

    clauses, groups = clause_rows(built), pay_groups(built)
    tables = {
        "clauses": clause_table(clauses),
        "edge-pays": pay_table(groups, machine),
        "edge-pays-full": edge_table(built),
        "trace": trace_table(walked, trace["notes"]),
        "plan-traces": plan_trace_table(built),
    }
    report.append("plan traces equal the layer's own transitions: OK")

    graph = args.out / "graph"
    graph.mkdir(parents=True, exist_ok=True)
    rm_file = graph / "cx-rules-only.rm"
    rm_file.write_text(
        (args.bundle / "reward_machine.txt").read_text(encoding="utf-8"), encoding="utf-8"
    )
    drawn = render_file(rm_file, graph / "cx-rules-only.svg", html=True)
    report.append("graph: " + ", ".join(path.name for path in drawn))

    for name, text in tables.items():
        (args.out / f"{name}.md").write_text(text + "\n", encoding="utf-8")
    result = {
        "freeze_commit": FREEZE,
        "bundle_commit": built.bundle.manifest.provenance["stamp"]["commit"],
        "task": built.proposal.task,
        "states": list(machine.states),
        "initial": machine.initial_state,
        "rejecting": list(machine.rejecting_states),
        "final": list(machine.final_states),
        "settings": asdict(settings),
        "well_charge": well_charge,
        "clauses": clauses,
        "pay_groups": [asdict(group) for group in groups],
        "trace": [asdict(step) for step in walked],
    }
    (args.out / "result.json").write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")

    readme = HERE.parent / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        stale = [n for n, block in tables.items() if n != "edge-pays-full" and block not in text]
        assert not stale, f"README tables differ from the evidence: {stale}"
        report.append("README tables equal the evidence tables: OK")
    (args.out / "check-output.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))


if __name__ == "__main__":
    main()
