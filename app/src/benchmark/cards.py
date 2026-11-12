"""Task cards: load a card file, check it against the card contract, describe a card.

A card fixes one benchmark task before generation: the wording both pipelines receive, the
clauses the judge evaluates, and the plans that make solving and wrong traces. The contract
is in ``docs/decisions/benchmark/thesis-benchmark.md`` and the testing plan.
"""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.config import Configuration
from src.models import EnvironmentDescription, EnvironmentValidationError

from .declare_judge import LTLF_DISPLAY, Clause, ClauseError, as_clause, describe_clauses

CONTRACT_KEYS = (
    "id",
    "env",
    "task",
    "goal",
    "template",
    "status",
    "expect",
    "also_ok",
    "env_reward_matches",
    "train",
    "plans",
    "event_seeds",
    "paraphrases",
    "notes",
)
ENV_KEYS = ("description", "family", "gym_id", "env_kwargs", "layout", "layout_seed", "observation")
FORBIDDEN_WORDING = re.compile(r"right away|immediately|countdown|within \d+ steps?", re.IGNORECASE)
# Plan step -> the keys it needs besides ``do``.
PLAN_STEPS = {
    "pickup": ("obj",),
    "toggle": ("obj",),
    "goto": ("obj",),
    "drop": (),
    "wait": ("n",),
    "policy": ("name",),
}


class CardError(ValueError):
    """A card file cannot be read or a card lacks what every card needs."""


@dataclass(frozen=True)
class Card:
    """One task card; ``solve`` and ``wrong`` are its plans (lists of step dicts)."""

    id: str
    env: Mapping[str, Any]
    task: str
    expect: tuple[Clause, ...]
    goal: bool = False
    template: str | None = None
    status: str = "draft"
    also_ok: tuple[tuple[Clause, ...], ...] = ()
    env_reward_matches: bool = False
    train: bool = False
    solve: tuple[Mapping[str, Any], ...] = ()
    wrong: tuple[Mapping[str, Any], ...] = ()
    event_seeds: tuple[int, ...] = ()
    paraphrases: tuple[str, ...] = ()
    notes: str = ""

    @property
    def all_clauses(self) -> list[Clause]:
        """Every clause the card names: the expected ones and those of each ``also_ok`` option."""
        return [*self.expect, *(clause for option in self.also_ok for clause in option)]

    @property
    def uses_chain_response(self) -> bool:
        return self.template == "ChainResponse" or any(
            clause[0] == "ChainResponse" for clause in self.all_clauses
        )

    def reset_seeds(self, run_seed: int) -> list[int]:
        """Seeds the plans run on: the event seeds, else the layout seed (else ``run_seed``)."""
        if self.event_seeds:
            return list(self.event_seeds)
        layout_seed = self.env.get("layout_seed")
        return [run_seed if layout_seed is None else layout_seed]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Card":
        """Build a card; raises ``CardError`` when ``id``, ``env``, ``task`` or ``expect`` fail."""
        try:
            plans = data.get("plans") or {}
            return cls(
                id=str(data["id"]),
                env=dict(data["env"]),
                task=str(data["task"]),
                expect=tuple(as_clause(clause) for clause in data["expect"]),
                goal=bool(data.get("goal", False)),
                template=data.get("template"),
                status=str(data.get("status", "draft")),
                also_ok=tuple(
                    tuple(as_clause(clause) for clause in option)
                    for option in data.get("also_ok") or ()
                ),
                env_reward_matches=bool(data.get("env_reward_matches", False)),
                train=bool(data.get("train", False)),
                solve=tuple(plans.get("solve") or ()),
                wrong=tuple(plans.get("wrong") or ()),
                event_seeds=tuple(data.get("event_seeds") or ()),
                paraphrases=tuple(data.get("paraphrases") or ()),
                notes=str(data.get("notes", "")),
            )
        except (AttributeError, KeyError, TypeError, ValueError, ClauseError) as error:
            name = data.get("id", "?") if isinstance(data, Mapping) else "?"
            raise CardError(f"card {name}: {type(error).__name__}: {error}") from error


@dataclass(frozen=True)
class CardFile:
    """The cards of one suite file and the contract problems found, by card id."""

    suite: str
    cards: tuple[Card, ...]
    problems: dict[str, list[str]] = field(default_factory=dict)

    @property
    def chain_response_ids(self) -> list[str]:
        """Cards a human reviews: ChainResponse only fits where the response can come next step."""
        return [card.id for card in self.cards if card.uses_chain_response]


def load_cards(path: Path, root: Path = Configuration.WORKSPACE_PATH) -> CardFile:
    """Load a card file and check every card; ``env.description`` is read from ``root``.

    A card that cannot be built is left out and reported; any other contract violation is
    reported and the card stays.

    Raises:
        CardError: If the file is not a JSON object with a ``cards`` list.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CardError(f"cannot read card file {path}: {error}") from error
    if not isinstance(data, dict) or not isinstance(data.get("cards"), list):
        raise CardError(f"{path}: expected an object with a 'cards' list")

    cards, problems, propositions = [], {}, {}
    for index, raw in enumerate(data["cards"]):
        try:
            card = Card.from_dict(raw)
        except CardError as error:
            problems[f"#{index}"] = [str(error)]
            continue
        cards.append(card)
        found = check_card(card, raw, root, propositions)
        if found:
            problems[card.id] = found
    return CardFile(str(data.get("suite", "")), tuple(cards), problems)


def load_card(path: Path, root: Path = Configuration.WORKSPACE_PATH) -> tuple[str, Card]:
    """The suite and card of a run's ``card.json``: a bare card, ``{"card": ...}`` or a one-card file.

    The card is checked against the card contract like ``load_cards`` does (``env.description``
    is read from ``root``).

    Raises:
        CardError: If the file is unreadable, does not hold exactly one card, or the card breaks
            the contract.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CardError(f"cannot read card {path}: {error}") from error
    if isinstance(data, dict) and isinstance(data.get("cards"), list):
        if len(data["cards"]) != 1:
            raise CardError(f"{path}: expected one card, found {len(data['cards'])}")
        raw = data["cards"][0]
    else:
        raw = data.get("card", data) if isinstance(data, dict) else data
    card = Card.from_dict(raw)
    if problems := check_card(card, raw, root, {}):
        raise CardError(f"{path}: the card breaks the card contract: {'; '.join(problems)}")
    return str(data.get("suite", "")) if isinstance(data, dict) else "", card


def select_cards(card_file: CardFile, ids: list[str] | None) -> list[Card]:
    """The cards named by ``ids`` (all when empty), in file order.

    Raises:
        CardError: If an id is not in the file.
    """
    if not ids:
        return list(card_file.cards)
    unknown = sorted(set(ids) - {card.id for card in card_file.cards})
    if unknown:
        raise CardError(f"unknown card id(s): {', '.join(unknown)}")
    return [card for card in card_file.cards if card.id in ids]


def card_header(card: Card) -> dict[str, object]:
    """What every page or summary that shows a card result carries: task and clauses with LTLf."""
    return {
        "id": card.id,
        "task": card.task,
        "expect": describe_clauses(card.expect),
        "also_ok": [describe_clauses(option) for option in card.also_ok],
    }


# ======================================================================================
#                                   CONTRACT CHECKS
# ======================================================================================


def check_card(
    card: Card, raw: Mapping[str, Any], root: Path, propositions: dict[Path, tuple[str, ...]]
) -> list[str]:
    """Contract problems of one card; ``propositions`` caches each env file's declared names."""
    problems = [f"missing key {key!r}" for key in CONTRACT_KEYS if key not in raw]
    problems += [f"env lacks {key!r}" for key in ENV_KEYS if key not in card.env]
    if card.template is not None and card.template not in LTLF_DISPLAY:
        problems.append(f"unknown template {card.template!r}")

    # == Wording and propositions ==
    for text in (card.task, *card.paraphrases):
        if match := FORBIDDEN_WORDING.search(text):
            problems.append(f"forbidden wording {match.group(0)!r} in {text!r}")
    declared = _declared_propositions(card, root, propositions, problems)
    if declared is not None:
        used = {name for clause in card.all_clauses for name in clause[1]}
        problems += [
            f"proposition {name!r} is not in the env file" for name in sorted(used - set(declared))
        ]

    # == Plans ==
    problems += _plan_problems("solve", card.solve)
    for index, plan in enumerate(card.wrong):
        if not isinstance(plan, Mapping):
            problems.append(f"wrong-{index}: must be an object with 'steps' and 'breaks'")
            continue
        problems += _plan_problems(f"wrong-{index}", plan.get("steps"))
        breaks = plan.get("breaks")
        if not isinstance(breaks, list) or not all(
            isinstance(i, int) and 0 <= i < len(card.expect) for i in breaks
        ):
            problems.append(f"wrong-{index}: 'breaks' must list indices into expect")
    return problems


def _declared_propositions(
    card: Card, root: Path, cache: dict[Path, tuple[str, ...]], problems: list[str]
) -> tuple[str, ...] | None:
    description = card.env.get("description")
    if not description:
        return None
    path = root / description
    if path not in cache:
        try:
            cache[path] = EnvironmentDescription.from_file(path).proposition_ids
        except EnvironmentValidationError as error:
            problems.append(f"env description: {error}")
            return None
    return cache[path]


def _plan_problems(name: str, steps: Any) -> list[str]:
    if not isinstance(steps, list | tuple):
        return [f"{name}: steps must be a list"]
    problems = []
    for index, step in enumerate(steps):
        kind = step.get("do") if isinstance(step, Mapping) else None
        if not isinstance(kind, str) or kind not in PLAN_STEPS:
            problems.append(f"{name}[{index}]: unknown step {step!r}")
        elif missing := [key for key in PLAN_STEPS[kind] if key not in step]:
            problems.append(f"{name}[{index}]: {kind} needs {', '.join(missing)}")
        elif bad := _bad_field(kind, step):
            problems.append(f"{name}[{index}]: {kind} {bad}")
    return problems


def _bad_field(kind: str, step: Mapping[str, Any]) -> str | None:
    """What is wrong with the type of a field the step ``kind`` uses, if anything."""
    if kind in ("pickup", "toggle", "goto") and not isinstance(step["obj"], str):
        return "obj must be a string"
    if kind == "wait":
        count = step["n"]
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            return "n must be an integer of 0 or more"
    ignore = step.get("ignore", ())
    if kind == "policy" and not (
        isinstance(ignore, list | tuple) and all(isinstance(name, str) for name in ignore)
    ):
        return "ignore must be a list of strings"
    return None
