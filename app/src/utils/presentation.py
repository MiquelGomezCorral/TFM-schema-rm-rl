"""The one format every shown result follows: task, IBM clauses with their LTLf, Reward Machine.

The rule (user's, recorded in the project decisions): whenever a result is shown, the page
carries (1) the natural-language task, (2) the IBM clauses with their LTLf, (3) the Reward
Machine. When the clauses were hand-picked and no real task exists, a hand-written task is
shown and marked illustrative. Anything added to the real clauses, LTLf or RM for presentation
is stated and shown, never silent. ``docs/EXPERIMENTS.md`` ("Present the results") says how to
build a page; ``app/scripts/present_results.py`` does it from real runs.

Everything here is a pure function over text and plain dicts shaped for the artifacts page
engine (gallery items, ``details`` fold-outs, table rows). Nothing reads or writes files.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from pylogics.syntax.ltl import Atomic

from src.compiler.ltlf import to_flat_syntax
from src.engines.structured import SUPPORTED_TEMPLATES

# One IBM clause: (pattern, propositions, priority), plus its raw LTLf when it was recorded
# by a real run. Without the fourth element the LTLf is computed with `ltlf_of`.
Clause = tuple[str, Sequence[str], str] | tuple[str, Sequence[str], str, str]

DETAILS_TITLE = "Task, clauses, LTLf and RM text"
_EMPTY_REWARDS = "# empty: every transition pays 0"
_INERT_SOFT = " (the soft clause is inert: it never changes a reward)"


@dataclass(frozen=True)
class Example:
    """One result to show: its task, its clauses and the Reward Machine text the compiler wrote.

    ``illustrative`` marks a hand-written task for clauses that came from no real task.
    ``inert_soft`` explains an empty ``REWARD_FUNCTION`` when a soft clause never changes a
    reward.
    """

    task: str
    clauses: Sequence[Clause]
    rm_text: str
    illustrative: bool = False
    inert_soft: bool = False


# ======================================================================================
#                                          LTLF
# ======================================================================================


def ltlf_of(pattern: str, propositions: Sequence[str]) -> str:
    """Return the raw LTLf string the pipeline gives this IBM clause.

    Same path as ``materialize_proposal``: the template class, ``to_ltlf()``, then the
    serializer FL-AT and MONA read.
    """
    template_class, _ = SUPPORTED_TEMPLATES[pattern]
    template = template_class(*(Atomic(name) for name in propositions))
    return to_flat_syntax(template.to_ltlf())


def pretty_ltlf(raw: str) -> str:
    """Add spaces for reading: ``(Fat_goal)`` becomes ``(F at_goal)``.

    The pipeline always gets the raw string; pages show both.
    """
    out = re.sub(r"(?<![A-Za-z_])([FGX])(?=[A-Za-z_(~])", r"\1 ", raw)
    out = re.sub(r"(?<![A-Za-z_])U(?=[A-Za-z_(~])", " U ", out)
    out = re.sub(r"\)U(?=[A-Za-z_(~])", ") U ", out)
    out = out.replace("&", " & ").replace("|", " | ").replace("->", " -> ")
    return re.sub(r"  +", " ", out)


def _label(pattern: str, propositions: Sequence[str]) -> str:
    return f"{pattern}({', '.join(propositions)})"


def _raw_ltlf(clause: Clause) -> str:
    return clause[3] if len(clause) > 3 else ltlf_of(clause[0], clause[1])


# ======================================================================================
#                                    THE CODE BLOCK
# ======================================================================================


def task_text(example: Example) -> str:
    """Return the task line of the fold-out, marked when the task was hand-written."""
    kind = "Task (illustrative, hand-written)" if example.illustrative else "Task"
    return f"**{kind}:** {example.task}"


def result_block(example: Example) -> str:
    """Return the code block: clauses, readable LTLf, raw LTLf and the compiler's RM text."""
    clauses = "\n".join(f"{_label(*clause[:2])}  [{clause[2]}]" for clause in example.clauses)
    readable = "\n".join(
        f"{_label(*clause[:2])}:\n - {pretty_ltlf(_raw_ltlf(clause))}" for clause in example.clauses
    )
    raw = "\n".join(f" - {_raw_ltlf(clause)}" for clause in example.clauses)
    return (
        f"# IBM clauses in the proposal\n{clauses}\n\n"
        f"# LTLf, one per clause\n{readable}\n\n"
        f"# Raw LTLf, as IBM writes it and MONA reads it\n{raw}\n\n"
        f"# RM text, as the compiler writes it\n{_rm_text_with_note(example)}"
    )


def _rm_text_with_note(example: Example) -> str:
    """The compiler's text; when no transition pays anything, say so under the empty function."""
    text = example.rm_text.rstrip("\n")
    if text.endswith("REWARD_FUNCTION:"):
        text += f"\n{_EMPTY_REWARDS}{_INERT_SOFT if example.inert_soft else ''}"
    return text


def result_card(
    src: str, caption: str, example: Example, *, height: int = 400, alt: str = ""
) -> dict:
    """Return one gallery item: the graph at ``src`` with the example's fold-out under it."""
    return {
        "src": src,
        "height": height,
        "alt": alt,
        "caption": caption,
        "details": {
            "title": DETAILS_TITLE,
            "text": task_text(example),
            "code": result_block(example),
        },
    }


# ======================================================================================
#                                  PIPELINE TABLE AND DFAS
# ======================================================================================


def pipeline_rows(versions: Sequence[tuple[str, str, Sequence[Clause]]]) -> list[list[str]]:
    """Return the rows of "What goes into the pipeline": version, task, clauses, readable LTLf.

    Each version is ``(label, task, clauses)``.
    """
    return [
        [
            label,
            task,
            "; ".join(f"`{_label(*clause[:2])}` {clause[2]}" for clause in clauses),
            "; ".join(f"`{pretty_ltlf(_raw_ltlf(clause))}`" for clause in clauses),
        ]
        for label, task, clauses in versions
    ]


def dfa_text(dfa: dict) -> str:
    """Return a ``compile_dfa`` result as sorted text: states, initial, accepting, transitions."""
    lines = [
        f"states: {', '.join(sorted(dfa['states']))}",
        f"initial: {dfa['initial_state']}",
        f"accepting: {', '.join(sorted(dfa['accepting_states']))}",
        "transitions:",
    ]
    lines += [
        f"  ({source}, {guard}) -> {target}"
        for (source, guard), target in sorted(dfa["transitions"].items())
    ]
    return "\n".join(lines)


def dfa_items(clauses: Sequence[tuple[str, Sequence[str], str, str]]) -> list[dict]:
    """Return one fold-out per clause: the pipeline compiles one MONA DFA per clause.

    Each clause is ``(pattern, propositions, raw LTLf, DFA text)``, the text from
    ``dfa_text`` or a run trace. The state count is read from its ``states:`` line.
    """
    items = []
    for pattern, propositions, raw, dfa in clauses:
        states_line = next(line for line in dfa.splitlines() if line.startswith("states:"))
        count = len(states_line.removeprefix("states:").split(","))
        label = _label(pattern, propositions)
        title = f"MONA DFA of `{label}`, LTLf `{pretty_ltlf(raw)}`, {count} states"
        text = f"# LTLf as IBM writes it: {raw}\n{dfa}"
        items.append({"title": title, "blocks": [{"type": "code", "text": text}]})
    return items
