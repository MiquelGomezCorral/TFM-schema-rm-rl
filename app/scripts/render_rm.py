"""Render paper-format Reward Machines to static SVG graphs.

The drawing lives in ``src.utils.svg`` and is shared with the web app's graph
export, so both produce the same picture. Without node positions this script
lays the states out itself.

Usage:
    python app/main.py render-rm --rm-file rm.txt
    python app/main.py render-rm --rm-file rm.txt --svg-dir graph.svg
    python app/main.py render-rm --rm-file many_rms.txt --svg-dir graphs/
"""

from pathlib import Path

from src.compiler import paper_to_structure, parse_paper_reward_machine
from src.config import Configuration
from src.utils import render_structure_svg

# ======================================================================================
#                                   PUBLIC API
# ======================================================================================


def render_rm(CONFIG: Configuration) -> None:
    """Render every Reward Machine in ``CONFIG.rm_file`` to SVG under ``CONFIG.svg_dir``."""
    if CONFIG.rm_file is None:
        raise ValueError("render-rm requires --rm-file")
    for target in render_file(CONFIG.rm_file, CONFIG.svg_dir):
        print(target)


def render_reward_machine(text: str) -> str:
    """Return a standalone SVG document for one paper-format Reward Machine."""
    machine = parse_paper_reward_machine(text, require_final_states=True)
    return render_structure_svg(paper_to_structure(machine))


def render_file(source: Path, output: Path) -> list[Path]:
    """Render every Reward Machine in a text file and return the written paths.

    ``output`` is one ``.svg`` file for a single machine, otherwise a directory.
    """
    blocks = _split_machines(source.read_text(encoding="utf-8"))
    if not blocks:
        raise ValueError(f"No REWARD_MACHINE block found in {source}")

    targets = _output_paths(source, output, len(blocks))
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


def _output_paths(source: Path, output: Path, count: int) -> list[Path]:
    """Resolve one target path per machine from the output file or directory."""
    if output.suffix.lower() == ".svg":
        if count > 1:
            raise ValueError("A single .svg output cannot hold several Reward Machines")
        return [output]

    if count == 1:
        return [output / f"{source.stem}.svg"]
    return [output / f"{source.stem}-{index:02d}.svg" for index in range(1, count + 1)]
