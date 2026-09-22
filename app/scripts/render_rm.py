"""Render paper-format Reward Machines to static SVG graphs.

The drawing lives in ``src.web.svg`` and is shared with the web app's graph
export, so both produce the same picture. Without node positions this script
lays the states out itself.

Usage:
    python app/scripts/render_rm.py rm.txt
    python app/scripts/render_rm.py rm.txt -o graph.svg
    python app/scripts/render_rm.py many_rms.txt -o graphs/
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.arm_fm import PaperRewardMachine, parse_paper_reward_machine
from src.compiler.reward_machine import (
    RewardMachineStructure,
    Transition,
    states_without_path_to_final,
)
from src.web.svg import render_elements_svg
from src.web.visualization import reward_machine_to_elements


# ======================================================================================
#                                   PUBLIC API
# ======================================================================================

def render_reward_machine(text: str) -> str:
    """Return a standalone SVG document for one paper-format Reward Machine."""
    machine = parse_paper_reward_machine(text, require_final_states=True)
    return render_structure_svg(paper_to_structure(machine))


def render_structure_svg(structure: RewardMachineStructure) -> str:
    """Return a standalone SVG document for one numeric Reward Machine structure."""
    return render_elements_svg(reward_machine_to_elements(structure))


def render_file(path: str | Path, output: str | Path | None = None) -> list[Path]:
    """Render every Reward Machine in a text file and return the written paths."""
    source = Path(path)
    blocks = _split_machines(source.read_text(encoding="utf-8"))
    if not blocks:
        raise ValueError(f"No REWARD_MACHINE block found in {source}")

    targets = _output_paths(source, Path(output) if output is not None else None, len(blocks))
    written: list[Path] = []
    for block, target in zip(blocks, targets, strict=True):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_reward_machine(block), encoding="utf-8")
        written.append(target)
    return written


# ======================================================================================
#                                 INPUT EXTRACTION
# ======================================================================================

def _split_machines(text: str) -> list[str]:
    """Split text into REWARD_MACHINE blocks, ignoring surrounding Markdown."""
    blocks: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            blocks.append("\n".join(current))

    for raw in text.splitlines():
        if raw.strip() == "" or raw.lstrip().startswith(("---", "#")):
            flush()
            current.clear()
            continue

        header = raw.find("REWARD_MACHINE:")
        if header != -1:
            flush()
            current = [raw[header:].rstrip()]
            continue

        if not current:
            continue

        if "<" in raw:
            current.append(raw.split("<", 1)[0].rstrip())
            flush()
            current.clear()
            continue

        current.append(raw.rstrip())

    flush()
    return [block for block in blocks if block.strip()]


def _output_paths(source: Path, output: Path | None, count: int) -> list[Path]:
    """Resolve one target path per machine from the CLI output argument."""
    if output is not None and output.suffix.lower() == ".svg":
        if count > 1:
            raise ValueError("A single .svg output cannot hold several Reward Machines")
        return [output]

    directory = output if output is not None else source.parent
    if count == 1:
        return [directory / f"{source.stem}.svg"]
    return [directory / f"{source.stem}-{index:02d}.svg" for index in range(1, count + 1)]


# ======================================================================================
#                                 RM CONVERSION
# ======================================================================================

def paper_to_structure(machine: PaperRewardMachine) -> RewardMachineStructure:
    """Convert a parsed paper Reward Machine into the app's numeric structure."""
    if len(machine.final_states) != 1:
        raise ValueError("The graph renderer needs exactly one FINAL_STATES entry")

    names = list(machine.states)
    index = {name: position for position, name in enumerate(names)}
    final_state = index[machine.final_states[0]]
    transitions = tuple(
        Transition(
            index[transition.source],
            index[transition.destination],
            (transition.condition,),
            transition.reward,
        )
        for transition in machine.transitions
    )
    edges = ((transition.source, transition.destination) for transition in transitions)
    return RewardMachineStructure(
        states=tuple(range(len(names))),
        initial_state=index[machine.initial_state],
        final_state=final_state,
        rejecting_states=tuple(
            sorted(states_without_path_to_final(range(len(names)), edges, final_state))
        ),
        transitions=transitions,
    )


# ======================================================================================
#                                       CLI
# ======================================================================================

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="render_rm",
        description="Render paper-format Reward Machines from a text file to static SVG.",
    )
    parser.add_argument("input", type=Path, help="Text or Markdown file with REWARD_MACHINE blocks")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output .svg file, or a directory when the input holds several machines",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        written = render_file(args.input, args.output)
    except (OSError, ValueError) as error:
        raise SystemExit(f"render_rm: {error}") from error
    for target in written:
        print(target)


if __name__ == "__main__":
    main()
