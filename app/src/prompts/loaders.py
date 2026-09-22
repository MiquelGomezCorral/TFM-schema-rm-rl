"""Load and render the packaged prompts.

Prompt text lives beside this module in ``compiler-rm/`` and ``arm_fm/``. This is
the single entry point for resolving and rendering both families; the two role
registries stay separate so each family can evolve on its own.
"""

from collections.abc import Mapping
from importlib.resources import files
from string import Template
from typing import Literal


COMPILER_DIRECTORY = "compiler-rm"
COMPILER_PROMPTS = {
    "creator": "reward-ltlf-creator",
    "ltlf_reviewer": "reward-ltlf-reviewer",
    "rm_reviewer": "reward-machine-reviewer",
}
COMPILER_OPTIONAL_FIELDS = frozenset({"case_specific", "history"})

ARM_FM_DIRECTORY = "arm_fm"
ARM_FM_ROLES = frozenset(
    {
        "rm_generator",
        "rm_critic",
        "labeling_generator",
        "labeling_critic",
        "description_generator",
    }
)
ARM_FM_OPTIONAL_FIELDS = frozenset({"history", "api"})

PROMPT_KINDS = frozenset({"system", "user"})

PromptAgent = Literal["creator", "ltlf_reviewer", "rm_reviewer"]
PromptKind = Literal["system", "user"]


def read_prompt(agent: PromptAgent, kind: PromptKind = "system") -> str:
    """Load a packaged compiler prompt by role and kind."""
    if agent not in COMPILER_PROMPTS:
        raise ValueError(f"Unknown prompt agent: {agent}")
    return _read(COMPILER_DIRECTORY, f"{COMPILER_PROMPTS[agent]}.{_checked_kind(kind)}.md")


def read_user_prompt(agent: PromptAgent, **values: str) -> str:
    """Render the compiler user prompt selected by ``agent``."""
    return _render(read_prompt(agent, "user"), values, COMPILER_OPTIONAL_FIELDS)


def read_arm_fm_prompt(role: str, kind: str = "system") -> str:
    """Load one ARM-FM prompt file by role and kind."""
    if role not in ARM_FM_ROLES:
        raise ValueError(f"Unknown ARM-FM prompt role: {role}")
    return _read(ARM_FM_DIRECTORY, f"{role}.{_checked_kind(kind)}.md")


def render_prompt(role: str, **values: str) -> str:
    """Render one ARM-FM user prompt with its required fields checked."""
    return _render(read_arm_fm_prompt(role, "user"), values, ARM_FM_OPTIONAL_FIELDS)


def _checked_kind(kind: str) -> str:
    if kind not in PROMPT_KINDS:
        raise ValueError(f"Unknown prompt kind: {kind}")
    return kind


def _read(directory: str, name: str) -> str:
    """Read one packaged prompt file as stripped UTF-8 text."""
    return files(__package__).joinpath(directory, name).read_text(encoding="utf-8").strip()


def _render(text: str, values: Mapping[str, str], optional: frozenset[str]) -> str:
    """Substitute template identifiers and reject empty required values.

    A field is required when the template references it and ``optional`` does not
    allow it. Missing or blank values render as the ``None.`` sentinel.
    """
    template = Template(text)
    rendered: dict[str, str] = {}
    for name in template.get_identifiers():
        value = values.get(name, "").strip()
        if not value and name not in optional:
            raise ValueError(f"{name} must be nonempty")
        rendered[name] = value or "None."
    return template.substitute(rendered)
