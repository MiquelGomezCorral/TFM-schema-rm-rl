"""State check before a zero-shot test: do the test machine's states look like the training ones?

For each test (and product) machine, it lists the states and their descriptions, the nearest
training state of every test state by cosine similarity of the embeddings, and a 2-D PCA figure
of all states (the paper's Fig. 11b). It warns when the machines were embedded with other
settings or a test machine has more states than any training machine.

Usage:
    python app/main.py state-check \
        --train experiments/benchmark/complex/bundles/arm-fm/cx-siren \
        --train experiments/benchmark/complex/bundles/arm-fm/cx-box \
        --test <bundle> --product <product bundle> --output outputs/state-check/shop

Writes ``state-check.json`` (full), ``state-check.md`` (the short tables) and
``state-check.html`` (the figure, one self-contained file) into ``--output``.
"""

from collections.abc import Sequence
from pathlib import Path

from src.arm_fm.state_check import check_states, markdown_table, write_state_check


def state_check(
    train: Sequence[Path], test: Sequence[Path], product: Sequence[Path], output: Path
) -> None:
    """Check the test and product machines against the training machines; write the three files.

    Raises:
        ValueError: If a bundle has no embeddings, there is no training or test machine, or the
            embedding sizes differ.
    """
    result = check_states(train, test, product)
    paths = write_state_check(result, output)
    print(markdown_table(result))
    print("wrote " + ", ".join(str(path) for path in paths))
