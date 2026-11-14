"""Tools of the transfer experiment: the shuffled-embedding control and the product machine.

A policy trained on several machines reads the language embedding of the current RM state. To
test it on a machine it never trained on, two controls help: permute the embeddings among the
machine's states (``embedding_permutation``) and run the product of two training machines, whose
states carry the training texts joined (``build_product_bundle``). Both are for evaluation only.
"""

import ast
import copy
import itertools
import json
import random
import re
from collections import deque
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.compiler import PaperRewardMachine, RuntimeTransition, parse_paper_reward_machine
from src.compiler.reward_machine import EndJudgment, evaluate_boolean_guard, parse_boolean_guard
from src.compiler.rm_format import serialize_paper_reward_machine
from src.config import Configuration

from .artifacts import ArtifactBundle, BundleManifest, load_bundle
from .evaluation import (
    EMBEDDING_IDENTITY,
    EmbeddingCache,
    EmbeddingSettings,
    embed_descriptions_over_http,
)
from .runtime import load_labeling_functions

MAX_GUARD_PROPOSITIONS = 14  # the product walks every valuation of the guards' propositions


# ======================================================================================
#                                 SHUFFLED-MEANING CONTROL
# ======================================================================================


def embedding_permutation(embeddings: Mapping[str, Sequence[float]], seed: int) -> dict[str, str]:
    """A seeded derangement of the states: ``state -> the state whose embedding it takes``.

    No state keeps its own embedding, so the control always breaks the meaning of every state.

    Raises:
        ValueError: With fewer than two states, where no derangement exists.
    """
    states = sorted(embeddings)
    if len(states) < 2:
        raise ValueError("shuffling embeddings needs a machine with at least two states")
    rng = random.Random(f"shuffle-embeddings-{seed}")
    while True:
        shuffled = states[:]
        rng.shuffle(shuffled)
        if all(own != other for own, other in zip(states, shuffled, strict=True)):
            return dict(zip(states, shuffled, strict=True))


# ======================================================================================
#                                    PRODUCT MACHINE
# ======================================================================================


@dataclass(frozen=True)
class _Branch:
    """One outcome of a machine state: the valuations (a bitmask) that take it, and where it goes."""

    guard: str
    mask: int
    destination: str
    reward: float


def _branches(
    machine: PaperRewardMachine, state: str, names: tuple[str, ...], valuations: list[dict]
) -> list[_Branch]:
    """The runtime's choice in ``state`` as a partition of ``valuations``.

    The first matching ordinary transition wins, ``else`` takes the rest, and a state with no
    ``else`` stays put for free. Each guard is rewritten to exclude the earlier ones it overlaps,
    so the branches are exclusive and their guards say exactly when each one fires. A final or
    rejecting state is frozen: it stays put for free whatever its transitions say.
    """
    full = (1 << len(valuations)) - 1
    if state in machine.final_states or state in machine.rejecting_states:
        return [_Branch("true", full, state, 0.0)]
    ordinary = [
        (item, parse_boolean_guard(item.condition, names))
        for item in machine.transitions
        if item.source == state and not item.is_else
    ]
    masks = [
        sum(
            1 << index
            for index, value in enumerate(valuations)
            if evaluate_boolean_guard(guard, value)
        )
        for _, guard in ordinary
    ]
    branches: list[_Branch] = []
    seen = 0
    for position, ((item, _), mask) in enumerate(zip(ordinary, masks, strict=True)):
        taken = mask & ~seen
        if taken:
            clash = [j for j in range(position) if mask & masks[j]]
            guard = _and([item.condition, *(f"!{_paren(ordinary[j][0].condition)}" for j in clash)])
            branches.append(_Branch(guard, taken, item.destination, float(item.reward)))
        seen |= mask
    rest = full & ~seen
    if rest:
        fallback = next(
            (item for item in machine.transitions if item.source == state and item.is_else), None
        )
        guard = _and(
            f"!{_paren(item.condition)}" for (item, _), m in zip(ordinary, masks, strict=True) if m
        )
        destination, reward = (
            (state, 0.0) if fallback is None else (fallback.destination, fallback.reward)
        )
        branches.append(_Branch(guard, rest, destination, float(reward)))
    return branches


def _paren(guard: str) -> str:
    """``guard`` ready to sit inside a larger one: bare when it is one (negated) name."""
    return guard if re.fullmatch(r"!?\w+", guard) else f"({guard})"


def _and(guards: Iterable[str]) -> str:
    """The conjunction of ``guards``; ``true`` for none."""
    parts = [guard for guard in guards if guard != "true"]
    if len(parts) < 2:
        return "".join(parts) or "true"
    return " & ".join(_paren(guard) for guard in parts)


def _pair_kind(first: PaperRewardMachine, second: PaperRewardMachine, pair: tuple[str, str]) -> str:
    """``rejecting`` when either part is, ``final`` when both are, else ``going`` (rejecting wins).

    A rejecting pair ends the episode with no end charge, so the open promises of its other part
    are not charged: the same as a single run that ends on its rejecting state.
    """
    one, other = pair
    if one in first.rejecting_states or other in second.rejecting_states:
        return "rejecting"
    return "final" if one in first.final_states and other in second.final_states else "going"


def _check_combinable(first: PaperRewardMachine, second: PaperRewardMachine) -> None:
    """Refuse the pairs the runtime could not read as one machine (see ``product_machine``)."""
    one, other = first.judgment, second.judgment
    if (one is None) != (other is None):
        raise ValueError(
            "only one machine has an end judgment (an ARM-FM and a FARM machine?): the runtime "
            "charges either its failed rewards or the time-limit penalty at the episode end, "
            "so the two cannot be merged"
        )
    if first.default_reward != second.default_reward:
        raise ValueError(
            f"the machines declare different default rewards: {first.default_reward!r} "
            f"vs {second.default_reward!r}"
        )
    if one is not None and other is not None:
        rewards = (one.hard_failed_reward, one.soft_failed_reward)
        if rewards != (other.hard_failed_reward, other.soft_failed_reward):
            raise ValueError(
                f"the machines' failed rewards differ (hard, soft: {rewards} vs "
                f"{(other.hard_failed_reward, other.soft_failed_reward)}); "
                "one end judgment cannot charge both"
            )


def _product_judgment(
    first: PaperRewardMachine,
    second: PaperRewardMachine,
    pairs: Mapping[str, tuple[str, str]],
    ended: Collection[str],
) -> EndJudgment | None:
    """The end judgment of the product: each part's open promises add up.

    The runtime charges, when the environment ends an episode the machine did not, the failed
    rewards of the promises open in the state. For a pair that is the sum over the parts, as if
    both machines ran on the episode (a final part has none open). A pair with no promise open in
    either part is accepting. Final and rejecting pairs end the episode and are listed in neither.
    """
    if first.judgment is None or second.judgment is None:
        return None
    parts = [
        (
            {str(state): (hard, soft) for state, hard, soft in machine.judgment.pending},
            {str(state) for state in machine.judgment.accepting},
        )
        for machine in (first, second)
    ]
    accepting: list[str] = []
    pending: list[tuple[str, int, int]] = []
    for name, pair in pairs.items():
        if name in ended:
            continue
        open_promises = [
            pend[state] for (pend, _), state in zip(parts, pair, strict=True) if state in pend
        ]
        if open_promises:
            pending.append(
                (name, sum(h for h, _ in open_promises), sum(s for _, s in open_promises))
            )
        else:
            accepting.append(name)
    return EndJudgment(
        accepting=tuple(accepting),
        pending=tuple(pending),
        hard_failed_reward=first.judgment.hard_failed_reward,
        soft_failed_reward=first.judgment.soft_failed_reward,
    )


def product_machine(
    first: PaperRewardMachine, second: PaperRewardMachine
) -> tuple[PaperRewardMachine, dict[str, tuple[str, str]]]:
    """The product of two RMs over one labeling, with the pair each product state stands for.

    Both machines read the same valuation. A product state is a pair of states, named ``u0``,
    ``u1`` ... in the order a walk from the initial pair finds them; a transition moves both at
    once and pays the sum of their rewards. Only the reachable pairs are built. The rules a
    compiler (FARM) machine adds are kept as the runtime reads them:

    - A part that reaches a final state stays there (it is frozen) while the other goes on.
    - A pair is final when both parts are final, and rejecting when either part is. Both end the
      episode, so they have no outgoing transition. A rejecting pair pays no end charge: the
      other part's open promises are not charged, as in a single run that ends on rejecting.
    - The end judgment charges the sum of both parts' open promises (``_product_judgment``); both
      machines must have one, with the same failed rewards, or neither.

    Raises:
        ValueError: If the machines declare different default rewards, only one has an end
            judgment or their failed rewards differ, or the guards mention more propositions
            than the truth-table walk allows.
    """
    _check_combinable(first, second)
    names = tuple(dict.fromkeys((*first.propositions, *second.propositions)))
    used = tuple(
        name for name in names if name in {*first.used_propositions, *second.used_propositions}
    )
    if len(used) > MAX_GUARD_PROPOSITIONS:
        raise ValueError(
            f"the guards mention {len(used)} propositions; the product allows {MAX_GUARD_PROPOSITIONS}"
        )
    valuations = [
        dict.fromkeys(names, False) | dict(zip(used, values, strict=True))
        for values in itertools.product((False, True), repeat=len(used))
    ]

    start = (first.initial_state, second.initial_state)
    order: dict[tuple[str, str], str] = {start: "u0"}
    queue = deque([start])
    rows: list[RuntimeTransition] = []
    while queue:
        pair = queue.popleft()
        if _pair_kind(first, second, pair) != "going":
            continue  # the episode ends here: no transition leaves it
        groups: dict[tuple[tuple[str, str], float], list[str]] = {}
        for one in _branches(first, pair[0], names, valuations):
            for other in _branches(second, pair[1], names, valuations):
                if not one.mask & other.mask:
                    continue
                key = ((one.destination, other.destination), round(one.reward + other.reward, 9))
                groups.setdefault(key, []).append(_and([one.guard, other.guard]))
        # The group that stays put for free takes ``else``, last: the others cover the rest exactly.
        for (destination, reward), guards in sorted(
            groups.items(), key=lambda g: g[0] == (pair, 0.0)
        ):
            if destination not in order:
                order[destination] = f"u{len(order)}"
                queue.append(destination)
            stay = (destination, reward) == (pair, 0.0)
            condition = (
                "else" if stay else " | ".join(_paren(g) if len(guards) > 1 else g for g in guards)
            )
            rows.append(RuntimeTransition(order[pair], condition, order[destination], reward))
    pairs = {name: pair for pair, name in order.items()}
    kinds = {name: _pair_kind(first, second, pair) for name, pair in pairs.items()}
    machine = PaperRewardMachine(
        states=tuple(pairs),
        initial_state="u0",
        transitions=tuple(rows),
        final_states=tuple(name for name, kind in kinds.items() if kind == "final"),
        propositions=names,
        default_reward=first.default_reward,
        rejecting_states=tuple(name for name, kind in kinds.items() if kind == "rejecting"),
        judgment=_product_judgment(
            first, second, pairs, {name for name, kind in kinds.items() if kind != "going"}
        ),
    )
    return machine, pairs


# ======================================================================================
#                                    PRODUCT BUNDLE
# ======================================================================================


def _same_embedding_identity(first: ArtifactBundle, second: ArtifactBundle) -> dict[str, Any]:
    """The embedding settings both bundles share.

    Raises:
        ValueError: If they differ, since vectors from two settings do not live in one space.
    """
    one = first.manifest.effective_settings.get("embedding") or {}
    other = second.manifest.effective_settings.get("embedding") or {}
    differing = [key for key in EMBEDDING_IDENTITY if one.get(key) != other.get(key)]
    if differing:
        raise ValueError(
            "the bundles were embedded with different settings: "
            + ", ".join(f"{key} {one.get(key)!r} vs {other.get(key)!r}" for key in differing)
        )
    return dict(one)


def _page_of(bundle: ArtifactBundle) -> str | None:
    return bundle.manifest.inputs.get("environment_markdown")


def _merged_labeling(first: str, second: str) -> str:
    """The two labeling sources as one module: each function once, a shared name only if the same.

    Raises:
        ValueError: If a function name has two different bodies.
    """
    merged = ast.parse(first)
    known = {node.name: ast.dump(node) for node in merged.body if isinstance(node, ast.FunctionDef)}
    for node in ast.parse(second).body:
        if isinstance(node, ast.FunctionDef) and node.name in known:
            if known[node.name] != ast.dump(node):
                raise ValueError(f"the labelings define {node.name} differently")
            continue
        merged.body.append(node)
    return ast.unparse(merged)


def build_product_bundle(
    first_dir: str | Path,
    second_dir: str | Path,
    output_dir: str | Path,
    CONFIG: Configuration,
) -> dict[str, Any]:
    """Write the product of two bundles' machines as a bundle of its own and describe it.

    The product states are pairs; each pair's description is the two descriptions the policy
    saw in training, joined by a space, and is embedded with the settings both bundles share
    (same server, model and revision). The labeling is the first bundle's, else the second's,
    else both merged (FARM bundles label only their own propositions), whichever covers both
    machines' propositions first. The result also holds ``product.json`` with the pair of
    every product state.

    Returns:
        The content of ``product.json``.

    Raises:
        ValueError: If the bundles differ in environment, embedding settings or proposition
            meaning, the machines cannot be combined (``product_machine``), or no labeling
            covers both.
    """
    first, second = load_bundle(first_dir), load_bundle(second_dir)
    for bundle in (first, second):
        bundle.validate(require_complete=True)
    if first.manifest.environment != second.manifest.environment:
        raise ValueError(
            f"the bundles belong to different environments: {first.manifest.environment!r} "
            f"vs {second.manifest.environment!r}"
        )
    settings = _same_embedding_identity(first, second)
    meanings = {**second.manifest.proposition_semantics, **first.manifest.proposition_semantics}
    conflicts = [
        name
        for name, text in second.manifest.proposition_semantics.items()
        if first.manifest.proposition_semantics.get(name, text) != text
    ]
    if conflicts:
        raise ValueError(f"the bundles define {', '.join(conflicts)} differently")

    machine, pairs = product_machine(first.reward_machine, second.reward_machine)
    descriptions = {
        name: f"{first.state_descriptions[a]} {second.state_descriptions[b]}"
        for name, (a, b) in pairs.items()
    }
    embedding = EmbeddingSettings(
        model=settings["model"],
        model_revision=settings["model_revision"],
        tokenizer_revision=settings["tokenizer_revision"],
        extraction=settings["extraction"],
        normalize=bool(settings["normalize"]),
        device=settings["device"],
    )
    server = copy.copy(CONFIG)  # replace() would reload the YAML over CONFIG
    server.embedding_endpoint = settings["endpoint"]
    vectors = embed_descriptions_over_http(
        descriptions,
        server,
        settings=embedding,
        context=settings.get("context", ""),
        cache=EmbeddingCache(),
    )
    pages = {_page_of(first), _page_of(second)}
    manifest = BundleManifest(
        task=f"{first.manifest.task} {second.manifest.task}",
        environment=first.manifest.environment,
        proposition_semantics={
            name: meanings[name] for name in machine.propositions if name in meanings
        },
        provenance={"product_of": [str(first_dir), str(second_dir)]},
        stage_status=dict.fromkeys(
            ("reward_machine", "labeling", "descriptions", "embeddings"), "complete"
        ),
        inputs={
            "task": f"{first.manifest.task} {second.manifest.task}",
            **(
                {"environment_markdown": pages.pop()}
                if len(pages) == 1 and None not in pages
                else {}
            ),
        },
        effective_settings={"embedding": settings, "mode": "product"},
        rm_mode=first.manifest.rm_mode,
    )
    problems: list[str] = []
    sources = {"first": first.labeling_source, "second": second.labeling_source}
    try:  # FARM bundles label only their own machine's propositions: both are needed
        sources["both merged"] = _merged_labeling(first.labeling_source, second.labeling_source)
    except ValueError as error:
        problems.append(str(error))
    for which, source in sources.items():
        product = ArtifactBundle(manifest, machine, source, descriptions, vectors)
        try:
            load_labeling_functions(source, product.labeling_propositions)
            product.validate(require_complete=True)
            break
        except ValueError as error:
            problems.append(f"{which} labeling: {error}")
    else:
        raise ValueError("no labeling covers both machines: " + "; ".join(problems))
    # Rebuild from the saved text: what the policy will load is what must parse. The compared
    # machine is the product as built, judgment and rejecting states included.
    if (
        parse_paper_reward_machine(
            serialize_paper_reward_machine(machine), propositions=machine.propositions
        )
        != machine
    ):
        raise ValueError("the product machine does not survive being written and read back")
    product.save(output_dir, overwrite=CONFIG.overwrite)
    record = {
        "first": str(first_dir),
        "second": str(second_dir),
        "states": {
            name: {"first": a, "second": b, "description": descriptions[name]}
            for name, (a, b) in pairs.items()
        },
    }
    (Path(output_dir) / "product.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    return record


# ======================================================================================
#                                     PRODUCT CARD
# ======================================================================================


def _merge_env_kwargs(first: Mapping[str, Any], second: Mapping[str, Any]) -> dict[str, Any]:
    """Setup flags OR-ed, lists joined; any other value must match."""
    merged = dict(first)
    for key, value in second.items():
        if key not in merged or merged[key] == value:
            merged[key] = value
        elif isinstance(value, bool) and isinstance(merged[key], bool):
            merged[key] = merged[key] or value
        elif isinstance(value, list) and isinstance(merged[key], list):
            merged[key] = [*merged[key], *(item for item in value if item not in merged[key])]
        else:
            raise ValueError(f"the cards set env_kwargs {key!r} to {merged[key]!r} and {value!r}")
    return merged


def read_card(path: Path) -> dict[str, Any]:
    """The raw card of a one-card file: a bare card, ``{"card": ...}`` or ``{"cards": [one]}``."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("cards"), list):
        if len(data["cards"]) != 1:
            raise ValueError(f"{path}: expected one card, found {len(data['cards'])}")
        return data["cards"][0]
    return data.get("card", data)


def product_card(first: Mapping[str, Any], second: Mapping[str, Any]) -> dict[str, Any]:
    """A card that holds both cards' rules, for the judge to score the product machine.

    The environment is the first card's with the setup flags merged (``siren`` and ``box`` both on,
    both ``require`` lists); ``expect`` is both cards' clauses. The solving and wrong plans do not
    carry over, as they were written for one card.

    Raises:
        ValueError: If the cards differ in environment page, gym id or layout, set one setup key
            to two values, or use ``also_ok`` (alternatives do not combine).
    """
    for key in ("description", "family", "gym_id", "layout", "layout_seed", "observation"):
        if first["env"].get(key) != second["env"].get(key):
            raise ValueError(f"the cards differ in env.{key}")
    if first.get("also_ok") or second.get("also_ok"):
        raise ValueError("cards with also_ok alternatives cannot be combined")
    card = copy.deepcopy(dict(first))
    card["id"] = f"{first['id']}+{second['id']}"
    card["task"] = f"{first['task']} {second['task']}"
    card["env"]["env_kwargs"] = _merge_env_kwargs(
        first["env"]["env_kwargs"], second["env"]["env_kwargs"]
    )
    card["expect"] = [*first["expect"], *(c for c in second["expect"] if c not in first["expect"])]
    card.update(template=None, goal=False, plans={}, paraphrases=[], train=False, forced=[])
    card["notes"] = f"Product of {first['id']} and {second['id']}."
    return card
