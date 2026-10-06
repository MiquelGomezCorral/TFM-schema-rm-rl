"""Load and render the packaged prompts in ``compiler-rm/`` and ``arm_fm/``."""

from importlib.resources import files
from string import Template
from typing import Literal

PromptFamily = Literal["compiler", "arm_fm"]
PromptAgent = Literal[
    "creator",
    "ltlf_reviewer",
    "rm_tagger",
    "rm_reviewer",
    "labeling_generator",
    "labeling_reviewer",
    "rm_generator",
    "rm_critic",
    "labeling_critic",
    "description_generator",
]
PromptKind = Literal["system", "user"]

# Per family: its folder, each agent's file stem, and the fields a user prompt may leave empty.
PROMPTS = {
    "compiler": {
        "directory": "compiler-rm",
        "files": {
            "creator": "reward-ltlf-creator",
            "ltlf_reviewer": "reward-ltlf-reviewer",
            "rm_tagger": "reward-machine-tagger",
            "rm_reviewer": "reward-machine-reviewer",
            "labeling_generator": "labeling-generator",
            "labeling_reviewer": "labeling-reviewer",
        },
        "optional": {"case_specific", "history", "state_descriptions"},
    },
    "arm_fm": {
        "directory": "arm_fm",
        "files": {
            "rm_generator": "rm_generator",
            "rm_critic": "rm_critic",
            "labeling_generator": "labeling_generator",
            "labeling_critic": "labeling_critic",
            "description_generator": "description_generator",
        },
        "optional": {"history", "api"},
    },
}


def read_prompt(family: PromptFamily, agent: PromptAgent, kind: PromptKind = "system") -> str:
    """Load one packaged prompt file as stripped UTF-8 text."""
    prompts = PROMPTS[family]
    if agent not in prompts["files"]:
        raise ValueError(f"Unknown {family} prompt agent: {agent}")

    name = f"{prompts['files'][agent]}.{kind}.md"
    path = files(__package__).joinpath(prompts["directory"], name)
    return path.read_text(encoding="utf-8").strip()


def render_prompt(family: PromptFamily, agent: PromptAgent, **values: str) -> str:
    """Render one user prompt, rejecting empty values for required template fields.

    A field is required when the template references it and the family does not list it
    as optional. Blank optional values render as the ``None.`` sentinel.
    """
    template = Template(read_prompt(family, agent, "user"))
    optional = PROMPTS[family]["optional"]

    rendered: dict[str, str] = {}
    for name in template.get_identifiers():
        value = values.get(name, "").strip()
        if not value and name not in optional:
            raise ValueError(f"{name} must be nonempty")
        rendered[name] = value or "None."
    return template.substitute(rendered)
