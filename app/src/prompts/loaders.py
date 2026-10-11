"""Load and render the packaged prompts in ``compiler-rm/`` and ``arm_fm/``.

Prompt files describe the MiniGrid labeling API by default. Two marker comments flag the text
an environment's own ``## Labeling API`` replaces; ``<!-- /name -->`` closes each one:

- ``<!-- labeling-api -->`` wraps the API listing; it becomes the declared text. Use it in
  system prompts only, because user prompts are templates and take ``${api}``.
- ``<!-- minigrid-only -->`` wraps MiniGrid-specific wording; it is dropped, or swapped for the
  text after an inner ``<!-- other -->``.

Without a declared API the markers vanish and the default text stays byte for byte. A declared
API also becomes the ``${api}`` value of user prompts, so both always carry the same text.
"""

import re
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

LABELING_REGION = re.compile(
    r"<!-- (labeling-api|minigrid-only) -->(.*?)(?:<!-- other -->(.*?))?<!-- /\1 -->",
    re.DOTALL,
)

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


def read_prompt(
    family: PromptFamily,
    agent: PromptAgent,
    kind: PromptKind = "system",
    labeling_api: str | None = None,
) -> str:
    """Load one packaged prompt file as stripped UTF-8 text.

    ``labeling_api`` is the environment's declared labeling API. When given, it replaces the
    marked MiniGrid regions; when ``None`` the MiniGrid default text is kept unchanged.
    """
    prompts = PROMPTS[family]
    if agent not in prompts["files"]:
        raise ValueError(f"Unknown {family} prompt agent: {agent}")

    name = f"{prompts['files'][agent]}.{kind}.md"
    path = files(__package__).joinpath(prompts["directory"], name)
    return _swap_labeling_regions(path.read_text(encoding="utf-8").strip(), labeling_api)


def render_prompt(
    family: PromptFamily,
    agent: PromptAgent,
    *,
    labeling_api: str | None = None,
    **values: str,
) -> str:
    """Render one user prompt, rejecting empty values for required template fields.

    A field is required when the template references it and the family does not list it
    as optional. Blank optional values render as the ``None.`` sentinel. ``labeling_api``
    swaps the marked MiniGrid regions as in :func:`read_prompt` and overrides ``api``.
    """
    template = Template(read_prompt(family, agent, "user", labeling_api))
    optional = PROMPTS[family]["optional"]
    if labeling_api is not None:
        values = {**values, "api": labeling_api}

    rendered: dict[str, str] = {}
    for name in template.get_identifiers():
        value = values.get(name, "").strip()
        if not value and name not in optional:
            raise ValueError(f"{name} must be nonempty")
        rendered[name] = value or "None."
    return template.substitute(rendered)


def _swap_labeling_regions(text: str, labeling_api: str | None) -> str:
    """Strip the region markers, or swap each region when an environment declares its API."""

    def swap(match: re.Match[str]) -> str:
        kind, default, other = match.groups()
        if labeling_api is None:
            return default
        return labeling_api if kind == "labeling-api" else other or ""

    return LABELING_REGION.sub(swap, text)
