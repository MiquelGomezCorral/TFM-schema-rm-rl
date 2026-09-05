"""Load and render the packaged LTLf proposal prompts."""

from importlib.resources import files
from string import Template
from typing import Literal

from src.config.config import PROMPT_NAMES


PROMPTS = PROMPT_NAMES
PromptAgent = Literal["creator", "ltlf_reviewer", "rm_reviewer"]
PromptKind = Literal["system", "user"]


def _read(name: str) -> str:
    return files(__package__).joinpath(name).read_text(encoding="utf-8").strip()


def read_prompt(agent: PromptAgent, kind: PromptKind = "system") -> str:
    """Load a packaged system or user prompt by role."""
    try:
        prompt_name = PROMPTS[agent]
    except KeyError as error:
        raise ValueError(f"Unknown prompt agent: {agent}") from error
    return _read(f"{prompt_name}.{kind}.md")


def read_user_prompt(agent: PromptAgent, **values: str) -> str:
    """Load and render the user prompt selected by ``agent``."""
    template = Template(read_prompt(agent, "user"))
    rendered_values = {}

    for name in template.get_identifiers():
        value = values.get(name, "").strip()
        if not value and name not in {"case_specific", "history"}:
            raise ValueError(f"{name} must be nonempty")
        rendered_values[name] = value or "None."
        
    return template.substitute(rendered_values)
