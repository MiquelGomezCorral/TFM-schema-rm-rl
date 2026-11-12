"""Trace records, the trace bank, and the replay of the bank through generated bundles.

A trace record is one episode: the actions, the reference labels after each step and the env
rewards. ``run_trace_bank`` runs every card plan in the real env and checks the judge's verdicts
against what the card promises. ``replay_traces`` plays the traces the bank's ``summary.json``
lists through each bundle's own labeling and Reward Machine, checks the machine against the
judge (R43) and compares the bundle's propositions with the reference labels.
"""

import html
import json
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from itertools import accumulate
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.arm_fm.artifacts import ArtifactBundle, load_bundle
from src.arm_fm.environments import make_environment, terminated_with_reward
from src.arm_fm.runtime import RewardMachineEnvironment, RewardMachineRuntime
from src.compiler.rm_format import PaperRewardMachine

from .cards import Card, CardError, CardFile, card_header, select_cards
from .declare_judge import HARD, HOLDS, Judgment, as_clause, judge_trace
from .plans import PlanError, Rollout, run_plan
from .reference_labels import NoReferenceLabelerError, labeler_for

SERIES = ("#2f5bd3", "#d96f00", "#1f7a4d", "#b3261e", "#b03a9a", "#1b7f8c", "#6b52c0", "#8a6d3b")
SOLVE, HARD_BREAK, SOFT_BREAK = "solve", "hard-break", "soft-break"
# Shown on every replay page: the two arms end an episode differently (R47).
ASYMMETRY_NOTE = (
    "Time-limit asymmetry: FARM machines charge open items at any episode end; "
    "ARM-FM machines get 0 at the time limit."
)
PAGE_STYLE = (
    "body{font:15px/1.5 system-ui,sans-serif;max-width:1100px;margin:1rem auto;padding:0 16px}"
    "pre{overflow-x:auto;background:#f4f4f4;padding:8px}li{margin:.2rem 0}"
)
PENALTY_NOTE = "Benchmark runs set `time_limit_penalty` to 0; -0.5 is the reproduction default."
# The one text that says what judge.json's ``rm_return`` sums (the replay page shows it too).
RM_RETURN_DEFINITION = (
    "rm_return sums the wrapper's info['rm_reward'] over the episode: the RM transition rewards "
    "plus the end charge (machines with an end judgment) or the run's time_limit_penalty "
    "(machines without one). With reward_source 'both' the trained reward also adds the env "
    "reward, which rm_return leaves out."
)
CURVE_NOTE = (
    "Curves are the machine's reward per step, from the trace replayed through the bundle: the "
    "transition rewards plus the end charge of a machine with an end judgment; the time-limit "
    f"penalty of a machine without one is left out. {RM_RETURN_DEFINITION}"
)


# ======================================================================================
#                                     TRACE RECORDS
# ======================================================================================


@dataclass(frozen=True)
class TraceRecord:
    """One episode of a card in the trace-record contract (plan traces and agent traces).

    ``terminated`` and ``truncated`` are the env's own flags. ``rm_stopped`` is an optional field,
    an approved amendment of the trace-record contract (round 1 of S5): true when a Reward Machine
    ended an agent episode before the env did. It is written only when true and read as false
    when absent, so records without it stay valid.
    """

    suite: str
    card_id: str
    plan: str
    source: str  # "plan" or "agent"
    gym_id: str
    env_kwargs: dict[str, Any]
    layout: str | None
    layout_seed: int | None
    reset_seed: int
    actions: list[int]
    labels: list[dict[str, bool]]
    env_rewards: list[float]
    terminated: bool
    truncated: bool
    rm_stopped: bool = False

    @property
    def key(self) -> str:
        """The file stem of a plan trace: ``<plan>-s<seed>``."""
        return f"{self.plan}-s{self.reset_seed}"

    @property
    def env_success(self) -> bool:
        """The env paid at the end of a terminated episode."""
        return terminated_with_reward(
            self.terminated, self.env_rewards[-1] if self.env_rewards else 0.0
        )

    def to_dict(self) -> dict[str, Any]:
        """The record as JSON; ``rm_stopped`` is written only when set, so other records are unchanged."""
        data = asdict(self)
        if not self.rm_stopped:
            del data["rm_stopped"]
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TraceRecord":
        required = [name for name in cls.__dataclass_fields__ if name != "rm_stopped"]
        return cls(
            **{name: data[name] for name in required}, rm_stopped=data.get("rm_stopped", False)
        )


def make_record(suite: str, card: Card, plan: str, source: str, rollout: Rollout) -> TraceRecord:
    """The record of ``rollout``, an episode of ``card``'s env."""
    env = card.env
    return TraceRecord(
        suite=suite,
        card_id=card.id,
        plan=plan,
        source=source,
        gym_id=env["gym_id"],
        env_kwargs=dict(env.get("env_kwargs") or {}),
        layout=env.get("layout"),
        layout_seed=env.get("layout_seed"),
        reset_seed=rollout.reset_seed,
        actions=rollout.actions,
        labels=rollout.labels,
        env_rewards=rollout.env_rewards,
        terminated=rollout.terminated,
        truncated=rollout.truncated,
        rm_stopped=rollout.rm_stopped,
    )


def write_json(path: Path, value: object, indent: int | None = None) -> Path:
    """Write ``value`` as JSON (compact unless ``indent`` is set), creating the folder."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")
    return path


def load_bank(folder: Path) -> tuple[dict[str, Card], list[TraceRecord]]:
    """The cards and plan traces a ``trace-bank`` run lists in its ``summary.json``.

    A card is rebuilt from the clauses the summary holds, so the judge needs no card file; only
    the traces the summary lists are read, never stale files left in the folder.

    Raises:
        CardError: If the summary or a listed trace cannot be read.
    """
    folder = Path(folder)
    try:
        listed = json.loads((folder / "summary.json").read_text(encoding="utf-8"))["cards"]
        cards = {item["id"]: _summary_card(item) for item in listed}
        records = [
            TraceRecord.from_dict(json.loads((folder / run["file"]).read_text(encoding="utf-8")))
            for item in listed
            for run in item["runs"]
            if "file" in run
        ]
    except (OSError, ValueError, LookupError, TypeError) as error:
        raise CardError(f"cannot read the trace bank {folder}: {error!r}") from error
    return cards, records


def _summary_card(item: Mapping[str, Any]) -> Card:
    """A card with the task and clauses of one ``summary.json`` card entry."""
    return Card(
        id=item["id"],
        env={},
        task=item["task"],
        expect=tuple(as_clause(entry["clause"]) for entry in item["expect"]),
        also_ok=tuple(
            tuple(as_clause(entry["clause"]) for entry in option) for option in item["also_ok"]
        ),
    )


# ======================================================================================
#                                       TRACE BANK
# ======================================================================================


def run_trace_bank(
    card_file: CardFile, output: Path, ids: list[str] | None, seed: int
) -> dict[str, Any]:
    """Run every plan of the chosen cards, write the trace records and ``summary.json``.

    A card with contract problems is reported and not run. ``seed`` is the run seed, the reset
    seed of a card with neither event seeds nor a layout seed.

    Raises:
        CardError: If an id in ``ids`` is not in the card file.
    """
    selected = select_cards(card_file, ids)
    cards = [
        _bank_card(card_file.suite, card, output, seed, card_file.problems.get(card.id))
        for card in selected
    ]
    runs = [run for card in cards for run in card["runs"]]
    summary = {
        "suite": card_file.suite,
        "card_problems": card_file.problems,
        "chain_response_review": card_file.chain_response_ids,
        "totals": {
            "cards": len(cards),
            "cards_with_problems": sum(1 for card in selected if card.id in card_file.problems),
            "cards_not_run": sum(1 for card in cards if "not_run" in card),
            "cards_without_plans": sum(
                1 for card in cards if "not_run" not in card and not card["runs"]
            ),
            "runs": len(runs),
            "runs_ok": sum(1 for run in runs if run["ok"]),
        },
        "cards": cards,
    }
    write_json(output / "summary.json", summary, indent=2)
    return summary


def _plans_of(card: Card) -> list[tuple[str, Sequence[Mapping[str, Any]], list[int] | None]]:
    """``(name, steps, breaks)`` of each plan; ``breaks`` is None for the solving plan."""
    plans = [("solve", card.solve, None)] if card.solve else []
    return plans + [
        (f"wrong-{index}", plan.get("steps") or (), plan.get("breaks") or [])
        for index, plan in enumerate(card.wrong)
    ]


def _bank_card(
    suite: str, card: Card, output: Path, seed: int, problems: list[str] | None
) -> dict[str, Any]:
    if problems:
        return {**card_header(card), "runs": [], "not_run": problems}
    runs = [
        _bank_plan(suite, card, plan, reset_seed, output)
        for reset_seed in card.reset_seeds(seed)
        for plan in _plans_of(card)
    ]
    return {**card_header(card), "runs": runs}


def _bank_plan(
    suite: str,
    card: Card,
    plan: tuple[str, Sequence[Mapping[str, Any]], list[int] | None],
    seed: int,
    output: Path,
) -> dict[str, Any]:
    name, steps, breaks = plan
    entry: dict[str, Any] = {"plan": name, "seed": seed}
    try:
        rollout = run_plan(card.env, steps, seed)
    except (PlanError, NoReferenceLabelerError) as error:
        return {**entry, "ok": False, "problems": [f"cannot run: {error}"]}
    record = make_record(suite, card, name, "plan", rollout)
    judgment = judge_trace(card.expect, rollout.labels)
    problems = _plan_problems(card, judgment, record, breaks)
    path = write_json(output / card.id / f"{record.key}.json", record.to_dict())
    return {
        **entry,
        "ok": not problems,
        "problems": problems,
        "steps": len(record.actions),
        "terminated": record.terminated,
        "truncated": record.truncated,
        "env_success": record.env_success,
        "judged_success": judgment.success,
        "verdicts": judgment.to_dict()["verdicts"],
        "file": str(path.relative_to(output)),
    }


def _plan_problems(
    card: Card, judgment: Judgment, record: TraceRecord, breaks: list[int] | None
) -> list[str]:
    """What a plan promises and the trace did not do."""
    problems = []
    verdicts = [verdict.text for verdict in judgment.verdicts]
    if breaks is None:
        if not judgment.success:
            problems.append(f"the solving plan is not judged success: {verdicts}")
        if card.goal and not record.env_success:
            problems.append("a goal card's solving plan must end terminated with env reward > 0")
    elif sorted(judgment.failed()) != sorted(breaks):
        problems.append(f"clauses not holding {judgment.failed()}, the plan promises {breaks}")
    if card.env_reward_matches and record.env_success != judgment.success:
        problems.append(
            f"env_reward_matches: env success {record.env_success}, judged {judgment.success}"
        )
    return problems


# ======================================================================================
#                                 REPLAY THROUGH A BUNDLE
# ======================================================================================


def read_manifest(folder: Path) -> dict[str, Any]:
    """The raw ``manifest.json`` of a bundle folder, or ``{}`` when absent or cut mid-write.

    For readers that must work on a bundle ``load_bundle`` rejects, such as a failed one.
    """
    try:
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return manifest if isinstance(manifest, dict) else {}


def ablation_settings(folder: Path) -> dict[str, Any]:
    """The ``ablate-rm`` settings in the manifest (``off``, ``no_op``); ``{}`` for other bundles."""
    settings = read_manifest(folder).get("effective_settings")
    ablation = settings.get("ablation") if isinstance(settings, dict) else None
    return ablation if isinstance(ablation, dict) else {}


@dataclass(frozen=True)
class BundleRef:
    """A bundle ``<bundles>/<arm>/<card-id>[~p<k>]/`` or an ablation's ``<card-id>/off-<switch>/``.

    ``ablation`` tells the layouts apart: the bundle's manifest records ``ablate-rm`` settings. Then
    the first folder (``arm``) is the card, not an arm. ``key`` is the relative path either way.
    """

    arm: str
    name: str
    path: Path
    ablation: bool = False

    @property
    def card_id(self) -> str:
        return self.arm if self.ablation else self.name.split("~", 1)[0]

    @property
    def key(self) -> str:
        return f"{self.arm}/{self.name}"

    @property
    def rm_path(self) -> Path:
        return self.path / "reward_machine.txt"


@dataclass
class Replay:
    """A trace played through one bundle: its own propositions, RM states and rewards per step."""

    rm_states: list[str]  # the initial state, then the state after each step
    valuations: list[dict[str, bool]]
    rewards: list[float]
    error: str = ""


def find_bundles(folder: Path) -> list[BundleRef]:
    """The bundle folders (symlinks included) one level below each arm folder."""
    return [
        BundleRef(arm.name, bundle.name, bundle, ablation=bool(ablation_settings(bundle)))
        for arm in sorted(Path(folder).iterdir())
        if arm.is_dir()
        for bundle in sorted(arm.iterdir())
        if (bundle / "manifest.json").is_file()
    ]


def load_machine_bundle(ref: BundleRef) -> ArtifactBundle | str:
    """The bundle of ``ref`` when it loads and holds a Reward Machine, else why it cannot be used."""
    try:
        bundle = load_bundle(ref.path)
    except Exception as error:  # a bundle on disk can fail to load in any way; that is its result
        return f"{type(error).__name__}: {error}"
    if bundle.reward_machine is None:
        return "the bundle has no reward machine"
    return bundle


def world_agreement(record: TraceRecord) -> dict[str, Any]:
    """Rebuild the env of ``record`` and check the replayed reference labels equal the recorded."""
    env = make_environment(record.gym_id, **record.env_kwargs)
    terminated = truncated = False
    try:
        env.reset(seed=record.reset_seed)
        labeler = labeler_for(record.gym_id, env)
        for index, action in enumerate(record.actions):
            _, reward, terminated, truncated, _ = env.step(action)
            same = labeler.labels(env.unwrapped) == record.labels[index] and math.isclose(
                float(reward), record.env_rewards[index]
            )
            early_end = (terminated or truncated) and index < len(record.actions) - 1
            if not same or early_end:
                return {"agree": False, "first_difference": index + 1}
    except NoReferenceLabelerError as error:
        return {"agree": False, "first_difference": None, "error": str(error)}
    finally:
        env.close()
    ends_alike = (terminated, truncated) == (record.terminated, record.truncated)
    return {"agree": ends_alike, "first_difference": None if ends_alike else len(record.actions)}


def replay_in_bundle(bundle: ArtifactBundle, record: TraceRecord) -> Replay:
    """Play ``record``'s actions through the bundle's own labeling and Reward Machine.

    The RM never ends the episode (``terminate_on_rm=False``), so every trace plays to its last
    action. The wrapper charges the machine's end judgment where the env ends the episode; a
    trace that stops before that gets the same charge once at its last step, so the rewards do
    not depend on where the trace stops. A labeling that crashes ends the replay with ``error``.
    """
    machine = bundle.reward_machine
    env = make_environment(record.gym_id, **record.env_kwargs)
    replay = Replay([machine.initial_state], [], [])
    try:
        wrapped = RewardMachineEnvironment(
            env, RewardMachineRuntime(machine), bundle.labeling_source, terminate_on_rm=False
        )
        wrapped.reset(seed=record.reset_seed)
        env_ended = False
        for action in record.actions:
            _, _, terminated, truncated, info = wrapped.step(action)
            replay.rm_states.append(info["rm_state"])
            replay.valuations.append(info["valuation"])
            replay.rewards.append(_step_reward(machine, wrapped, info))
            env_ended = terminated or truncated
            if env_ended:
                break
        if machine.judgment is not None and replay.rewards and not env_ended:
            replay.rewards[-1] += machine.judgment.end_charge(replay.rm_states[-1])
    except Exception as error:  # generated labeling code can fail in any way; that is a result
        replay.error = f"{type(error).__name__}: {error}"
    finally:
        env.close()
    return replay


def _step_reward(
    machine: PaperRewardMachine, wrapped: RewardMachineEnvironment, info: Mapping[str, Any]
) -> float:
    """The RM reward of the step.

    A machine with no end judgment gets the time-limit penalty from the wrapper, so its raw
    transition reward is used instead (R43 asks about the machine, not the wrapper).
    """
    if machine.judgment is not None:
        return float(info["rm_reward"])
    return float(wrapped.execution_evidence[-1]["reward"])


# ======================================================================================
#                          MACHINE CHECK AND LABEL AGREEMENT
# ======================================================================================


def trace_class(judgment: Judgment) -> str:
    """``solve`` (all clauses hold), ``soft-break`` (only soft ones fail) or ``hard-break``."""
    if not judgment.success:
        return HARD_BREAK
    return SOFT_BREAK if judgment.failed() else SOLVE


def machine_accepts(machine: PaperRewardMachine, rm_states: Sequence[str]) -> bool:
    """The first final or rejecting state reached decides, as it stops a training episode.

    With neither reached, a machine with an end judgment accepts when it ends in an accepting state.
    """
    for state in rm_states[1:]:  # the initial state is the reset, not a step
        if state in machine.final_states:
            return True
        if state in machine.rejecting_states:
            return False
    accepting = machine.judgment.accepting if machine.judgment else ()
    return rm_states[-1] in accepting


def check_row(
    machine: PaperRewardMachine, record: TraceRecord, judgment: Judgment, replay: Replay
) -> dict[str, Any]:
    """R43 on one trace: solves accepted, hard breaks not, soft breaks pay at or after the break."""
    kind = trace_class(judgment)
    accepted = machine_accepts(machine, replay.rm_states)
    negative = [step for step, reward in enumerate(replay.rewards, start=1) if reward < 0]
    soft_steps = [
        len(record.actions) if verdict.step is None else verdict.step
        for verdict in judgment.verdicts
        if verdict.status != HOLDS and verdict.clause[2] != HARD
    ]
    first_soft = min(soft_steps, default=None)
    if replay.error:
        ok = False
    elif kind == SOLVE:
        ok = accepted
    elif kind == HARD_BREAK:
        ok = not accepted
    else:
        ok = any(step >= first_soft for step in negative)
    return {
        "trace": f"{record.card_id}/{record.key}",
        "class": kind,
        "steps": len(record.actions),
        "accepted": accepted,
        "first_soft_break": first_soft,
        "negative_reward_steps": negative[:5],
        "error": replay.error,
        "ok": ok,
    }


def machine_check(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The R43 verdict of one bundle over its rows."""
    return {
        "passed": bool(rows) and all(row["ok"] for row in rows),
        "checked": len(rows),
        "failed": [row["trace"] for row in rows if not row["ok"]],
        "rows": list(rows),
    }


def label_agreement(
    pairs: Iterable[tuple[TraceRecord, Replay]], propositions: Sequence[str]
) -> dict[str, Any]:
    """Per-proposition agreement of the bundle's labeling with the reference labels.

    Names are matched by equality; the others are listed, never guessed.
    """
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    reference: set[str] = set()
    for record, replay in pairs:
        reference |= {name for step in record.labels for name in step}
        for labels, valuation in zip(record.labels, replay.valuations, strict=False):
            for name in valuation.keys() & labels.keys():
                counts[name][0] += valuation[name] == labels[name]
                counts[name][1] += 1
    return {
        "propositions": {name: {"agree": a, "total": t} for name, (a, t) in sorted(counts.items())},
        "unmatched_bundle": sorted(set(propositions) - reference),
        "unmatched_reference": sorted(reference - set(propositions)),
    }


# ======================================================================================
#                                     REPLAY DRIVER
# ======================================================================================


def replay_traces(traces: Path, bundles: Path, output: Path) -> dict[str, Any]:
    """Replay the traces of a trace bank through every bundle; write step files, a page per card.

    The judge reads the clauses in the bank's ``summary.json`` and replays only the traces it
    lists; a bundle only supplies the labeling and RM to test. A bundle that cannot be replayed
    is an error result, never a crash: the summary is always written.

    Raises:
        CardError: If the bank's ``summary.json`` or a listed trace cannot be read.
    """
    cards, records = load_bank(traces)
    by_card: dict[str, list[TraceRecord]] = defaultdict(list)
    for record in records:
        by_card[record.card_id].append(record)

    world = {f"{r.card_id}/{r.key}": world_agreement(r) for r in records}
    results = {}
    # card -> bundle -> trace -> cumulative RM reward, of the bundles that replayed
    series: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(dict)
    for ref in find_bundles(bundles):
        card = cards.get(ref.card_id)
        if card is None or not by_card[ref.card_id]:
            results[ref.key] = {"error": f"no card or traces for {ref.card_id!r}"}
            continue
        results[ref.key], curves = _replay_bundle(ref, card, by_card[ref.card_id], output)
        if "error" not in results[ref.key]:
            series[ref.card_id][ref.key] = curves

    plots = {
        card_id: _write_plot(cards[card_id], curves, results, output)
        for card_id, curves in series.items()
    }
    summary = {
        "suite": records[0].suite if records else "",
        "cards": {card_id: card_header(cards[card_id]) for card_id in series},
        "world_agreement": world,
        "bundles": results,
        "plots": plots,
    }
    write_json(output / "replay-summary.json", summary, indent=2)
    return summary


def _replay_bundle(
    ref: BundleRef, card: Card, records: Sequence[TraceRecord], output: Path
) -> tuple[dict[str, Any], dict[str, list[float]]]:
    """Replay one card's traces through one bundle: its result and cumulative rewards per trace."""
    bundle = load_machine_bundle(ref)
    if isinstance(bundle, str):
        return {"error": bundle}, {}
    machine = bundle.reward_machine

    pairs, rows, curves = [], [], {}
    for record in records:
        replay = replay_in_bundle(bundle, record)
        judgment = judge_trace(card.expect, record.labels)
        pairs.append((record, replay))
        rows.append(check_row(machine, record, judgment, replay))
        curves[record.key] = list(accumulate(replay.rewards))
        write_json(
            output / "steps" / ref.arm / ref.name / f"{record.key}.json",
            _steps_file(ref, record, replay),
        )
    return {
        "arm": ref.arm,
        "card_id": ref.card_id,
        "rm_path": str(ref.rm_path),
        "propositions": list(machine.propositions),
        "machine_check": machine_check(rows),
        "label_agreement": label_agreement(pairs, machine.propositions),
    }, curves


def _steps_file(ref: BundleRef, record: TraceRecord, replay: Replay) -> dict[str, Any]:
    return {
        "bundle": ref.key,
        "trace": f"{record.card_id}/{record.key}",
        "error": replay.error,
        "steps": [
            {
                "step": index,
                "action": record.actions[index - 1],
                "reference": record.labels[index - 1],
                "propositions": replay.valuations[index - 1],
                "rm_state": replay.rm_states[index],
                "reward": replay.rewards[index - 1],
            }
            for index in range(1, len(replay.rewards) + 1)
        ],
    }


def _write_plot(
    card: Card,
    curves: Mapping[str, Mapping[str, list[float]]],
    results: Mapping[str, Mapping[str, Any]],
    output: Path,
) -> str:
    """One self-contained page of a card, named ``<card-id>.html``.

    It shows the task, each clause with its LTLf, the time-limit asymmetry, the cumulative RM
    reward per bundle (a plot row per trace) and the RM text of every bundle in ``curves``.
    """
    trace_keys = sorted({key for bundle in curves.values() for key in bundle})
    figure = make_subplots(rows=len(trace_keys), cols=1, subplot_titles=trace_keys)
    for index, (bundle_key, bundle_curves) in enumerate(curves.items()):
        for row, trace_key in enumerate(trace_keys, start=1):
            curve = [0.0, *bundle_curves.get(trace_key, [])]  # step 0 is the reset, no reward yet
            figure.add_trace(
                go.Scatter(
                    x=list(range(len(curve))),
                    y=curve,
                    mode="lines",
                    name=bundle_key,
                    legendgroup=bundle_key,
                    showlegend=row == 1,
                    line={"color": SERIES[index % len(SERIES)]},
                ),
                row=row,
                col=1,
            )
    figure.update_layout(template="plotly_white", height=260 * len(trace_keys) + 80)
    figure.update_xaxes(title_text="step")
    figure.update_yaxes(title_text="cumulative RM reward")

    items = []
    for item in card_header(card)["expect"]:
        template, names, priority = item["clause"]
        label = f"{template}({', '.join(names)}) {priority}"
        items.append(
            f"<li>{html.escape(label)} <code>{html.escape(item['ltlf']['readable'])}</code></li>"
        )
    clauses = "".join(items)
    machines = "".join(
        f"<details open><summary>{html.escape(key)} "
        f"({html.escape(results[key]['rm_path'])})</summary>"
        f"<pre>{html.escape(Path(results[key]['rm_path']).read_text(encoding='utf-8'))}</pre>"
        "</details>"
        for key in curves
    )
    path = output / f"{card.id}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"<!doctype html><html><head><meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{html.escape(card.id)}</title><style>{PAGE_STYLE}</style></head><body>"
        f"<h1>{html.escape(card.id)}</h1><p>{html.escape(card.task)}</p><ul>{clauses}</ul>"
        f"<p><b>{html.escape(ASYMMETRY_NOTE)}</b> {html.escape(PENALTY_NOTE)}</p>"
        f"<p>{html.escape(CURVE_NOTE)}</p>"
        f"{figure.to_html(full_html=False, include_plotlyjs=True)}"
        f"<h2>Reward Machines</h2>{machines}</body></html>",
        encoding="utf-8",
    )
    return path.name
