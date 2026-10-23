"""Start-merge live check: the compiler's RM must equal the old RM with its duplicate start removed.

Usage, from the repo root (RM_RL_env python, PYTHONPATH=app):
  python start_merge_check.py expect <before_dir> <svg_dir>    # draw before / expected graphs
  python start_merge_check.py compare <before_dir> <after_dir> <svg_dir>   # check and draw what we got

"Expected" = the before RM, minus its start state when the start is never re-entered and its rows
match its idle successor's on every input (same destination, same reward); the idle successor
becomes the start. Two RMs are "the same" when walking both from their starts on every input
sequence gives the same rewards, the same final / well states, at every step (checked by pairing
states input by input).
"""

import itertools
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from src.compiler import paper_to_structure
from src.compiler.rm_format import parse_paper_reward_machine
from src.utils import (
    render_elements_html,
    render_elements_svg,
    reward_machine_to_elements,
)

NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass
class Machine:
    states: list[str]
    initial: str
    finals: set[str]
    wells: set[str]
    edges: list[tuple[str, str, str, float]]  # source, guard, destination, reward


def load(path: Path) -> Machine:
    rm = parse_paper_reward_machine(path.read_text())
    edges = [(t.source, t.condition, t.destination, round(t.reward, 6)) for t in rm.transitions]
    return Machine(
        list(rm.states),
        rm.initial_state,
        set(rm.final_states),
        set(getattr(rm, "rejecting_states", ()) or ()),
        edges,
    )


def holds(guard: str, valuation: dict[str, bool]) -> bool:
    if guard.strip() in ("", "true"):
        return True
    expr = guard.replace("!", " not ").replace("&", " and ").replace("|", " or ")
    expr = NAME.sub(
        lambda m: m.group(0) if m.group(0) in ("and", "or", "not") else f"v[{m.group(0)!r}]", expr
    )
    return eval(expr, {}, {"v": valuation})  # noqa: S307 - guards come from our own RM files


def props(machine: Machine) -> list[str]:
    return sorted({n for _, g, _, _ in machine.edges for n in NAME.findall(g)} - {"true"})


def valuations(names: list[str]) -> list[dict[str, bool]]:
    return [
        dict(zip(names, bits, strict=True))
        for bits in itertools.product([False, True], repeat=len(names))
    ]


def step(machine: Machine, state: str, valuation: dict[str, bool]) -> tuple[str, float]:
    for source, guard, destination, reward in machine.edges:
        if source == state and holds(guard, valuation):
            return destination, reward
    return state, 0.0


def expected_merge(machine: Machine) -> tuple[Machine, str]:
    start, names = machine.initial, props(machine)
    idle = step(machine, start, dict.fromkeys(names, False))[0]
    if idle == start:
        return machine, "start loops on an idle step: nothing to merge"
    if any(destination == start for _, _, destination, _ in machine.edges):
        return machine, "start is re-entered: left as is"
    for valuation in valuations(names):
        here, there = step(machine, start, valuation), step(machine, idle, valuation)
        if here != there:
            return machine, f"start differs from {idle} on {valuation}: left as is"
    kept = [idle, *(state for state in machine.states if state not in (start, idle))]
    name = {state: f"u{index}" for index, state in enumerate(kept)}
    edges = [(name[s], g, name[d], r) for s, g, d, r in machine.edges if s != start]
    merged = Machine(
        list(name.values()),
        name[idle],
        {name[s] for s in machine.finals},
        {name[s] for s in machine.wells},
        edges,
    )
    return merged, f"merged {start} into {idle} (renamed {idle} -> u0)"


def same(a: Machine, b: Machine) -> tuple[bool, str]:
    names = sorted(set(props(a)) | set(props(b)))
    pairs, todo = {a.initial: b.initial}, [(a.initial, b.initial)]
    while todo:
        sa, sb = todo.pop()
        if (sa in a.finals) != (sb in b.finals) or (sa in a.wells) != (sb in b.wells):
            return False, f"{sa}/{sb}: final or well differs"
        for valuation in valuations(names):
            (da, ra), (db, rb) = step(a, sa, valuation), step(b, sb, valuation)
            if abs(ra - rb) > 1e-6:
                return False, f"{sa}/{sb} on {valuation}: reward {ra} vs {rb}"
            if da in pairs:
                if pairs[da] != db:
                    return False, f"{sa}/{sb} on {valuation}: goes to {da} vs {db}"
            else:
                pairs[da] = db
                todo.append((da, db))
    return True, "same rewards and endings on every input"


def text(machine: Machine) -> str:
    """The machine in the paper RM format the compiler writes."""

    def names(states):
        return ", ".join(state for state in machine.states if state in states)

    lines = [
        "REWARD_MACHINE:",
        f"STATES: {', '.join(machine.states)}",
        f"INITIAL_STATE: {machine.initial}",
        f"FINAL_STATES: {names(machine.finals)}",
    ]
    if machine.wells:
        lines.append(f"REJECTING_STATES: {names(machine.wells)}")
    lines += ["DEFAULT_REWARD: 0", "TRANSITION_FUNCTION:"]
    lines += [f"({s}, {g}) -> {d}" for s, g, d, _ in machine.edges]
    lines += ["REWARD_FUNCTION:"] + [
        f"({s}, {g}, {d}) -> {r:g}" for s, g, d, r in machine.edges if r
    ]
    return "\n".join(lines) + "\n"


def svg(machine: Machine, path: Path) -> None:
    """Draw the machine with the repo's RM generator (SVG and live HTML) and keep its text beside them."""
    rm_text = text(machine)
    path.with_suffix(".rm").write_text(rm_text)
    elements = reward_machine_to_elements(paper_to_structure(parse_paper_reward_machine(rm_text)))
    path.write_text(render_elements_svg(elements))
    path.with_suffix(".html").write_text(render_elements_html(elements))


def main() -> None:
    mode, before_dir = sys.argv[1], Path(sys.argv[2])
    after_dir = Path(sys.argv[3]) if mode == "compare" else None
    svg_dir = Path(sys.argv[-1])
    svg_dir.mkdir(parents=True, exist_ok=True)
    passed = total = 0
    for path in sorted(before_dir.glob("*.rm")):
        before = load(path)
        expected, how = expected_merge(before)
        if mode == "expect":
            svg(before, svg_dir / f"{path.stem}.before.svg")
            svg(expected, svg_dir / f"{path.stem}.expected.svg")
            print(f"{path.stem}: {len(before.states)} -> {len(expected.states)} states; {how}")
            continue
        total += 1
        got_path = after_dir / path.name
        if not got_path.exists():
            print(f"FAIL {path.stem}: no RM written")
            continue
        got = load(got_path)
        ok, why = same(expected, got)
        ok = ok and len(got.states) == len(expected.states)
        passed += ok
        svg(got, svg_dir / f"{path.stem}.got.svg")
        print(
            f"{'PASS' if ok else 'FAIL'} {path.stem}: expected {len(expected.states)} states, "
            f"got {len(got.states)}; {why}"
        )
    if mode == "compare":
        print(f"{passed}/{total} RMs match the expected merge")


if __name__ == "__main__":
    main()
