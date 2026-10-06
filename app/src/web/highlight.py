"""Light syntax colouring for the read-only pipeline outputs.

Every token gets one class from the shared palette, so JSON data, DFA listings and
Reward Machine text read the same way in the web panel and stay dependency-free.
"""

from __future__ import annotations

import re

from dash import html

from src.utils import PipelineStep

# ======================================================================================
#                                     TOKEN SETS
# ======================================================================================

_JSON_TOKENS = (
    ("key", r'"(?:[^"\\]|\\.)*"(?=\s*:)', "text-accent"),
    ("string", r'"(?:[^"\\]|\\.)*"', "text-success"),
    ("number", r"-?\d+(?:\.\d+)?", "text-text"),
    ("keyword", r"\b(?:true|false|null)\b", "text-[#fda4af]"),
)
_DFA_TOKENS = (
    ("label", r"^[a-z_]+(?=:)", "text-accent"),
    ("number", r"-?\d+", "text-text"),
)
_RM_TOKENS = (
    ("header", r"^[A-Za-z_]+(?=:)", "text-accent font-bold"),
    ("state", r"\bu\d+\b", "text-accent"),
    ("arrow", r"->", "text-muted"),
    ("reward", r"-?\d+(?:\.\d+)?$", "text-success"),
)
_PYTHON_TOKENS = (
    (
        "keyword",
        r"\b(?:def|return|not|and|or|None|True|False|any|all)\b",
        "text-[#fda4af]",
    ),
    ("function", r"\b[A-Za-z_]\w*(?=\()", "text-accent"),
    ("string", r'"[^"]*"', "text-success"),
)
_FORMATS = {
    PipelineStep.GENERATE: _JSON_TOKENS,
    PipelineStep.LTLF: _JSON_TOKENS,
    PipelineStep.DFA: _DFA_TOKENS,
    PipelineStep.REWARD_MACHINE: _RM_TOKENS,
    PipelineStep.STATE_DESCRIPTIONS: _JSON_TOKENS,
    PipelineStep.LABELING: _PYTHON_TOKENS,
    PipelineStep.EMBEDDINGS: _JSON_TOKENS,
    PipelineStep.TASK_CRITIC: _JSON_TOKENS,
    PipelineStep.RM_CRITIC: _JSON_TOKENS,
}


# ======================================================================================
#                                     PUBLIC API
# ======================================================================================


def highlight_step(step: PipelineStep, text: str) -> list[object]:
    """Return Dash children for one step output with its format's colouring."""
    return _highlight(text, _FORMATS[step])


# ======================================================================================
#                                     TOKENIZING
# ======================================================================================


def _highlight(text: str, tokens: tuple[tuple[str, str, str], ...]) -> list[object]:
    """Split text into coloured spans, leaving every unmatched slice untouched."""
    pattern = re.compile(
        "|".join(f"(?P<{name}>{expression})" for name, expression, _ in tokens),
        re.MULTILINE,
    )
    classes = {name: class_name for name, _, class_name in tokens}

    children: list[object] = []
    cursor = 0
    for match in pattern.finditer(text):
        if match.start() > cursor:
            children.append(text[cursor : match.start()])
        children.append(html.Span(match.group(), className=classes[match.lastgroup]))
        cursor = match.end()
    if cursor < len(text):
        children.append(text[cursor:])
    return children
