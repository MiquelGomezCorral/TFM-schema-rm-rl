"""Which generated machines end every episode at once ("too simple"). Read-only, no provider call.

Usage (repository root, `RM_RL_env`):
    PYTHONPATH=app python experiments/benchmark/scripts/check_too_simple.py \
        [--root experiments/benchmark] [--suite NAME ...] [--start-labels] [--output too-simple.json]

Reads every bundle under `<root>/<suite>/bundles/` (all suites, or the named ones) and runs the
judge's `machine_too_simple` on its Reward Machine:

- static (always): walks `else` rows and always-true guards from the start state.
- `--start-labels`: also evaluates the bundle's own labeling on the just-reset environment for
  seeds 1 to 20 (what the judge does on its test resets) and walks the machine holding that
  valuation. Needs the card in `<root>/*/tasks.json` (a `~p<k>` bundle uses its base card).

Prints the number of bundles checked and one line per flagged bundle or failed check; writes the
same rows to `--output` (`scanned`, `flagged`, `unreadable`). A flagged machine is not an error:
whether to train it is the judge's call. Safe to rerun; it overwrites `--output`.
"""

import argparse
import json
import traceback
from pathlib import Path

from src.arm_fm.artifacts import ArtifactBundle
from src.arm_fm.environments import make_environment
from src.arm_fm.runtime import RewardMachineEnvironment, RewardMachineRuntime
from src.benchmark.cards import load_cards
from src.benchmark.early_end import machine_too_simple
from src.benchmark.traces import find_bundles
from src.compiler.rm_format import parse_paper_reward_machine
from src.config import Configuration

SEEDS = range(1, 21)  # the judge's reset seeds for this check


def card_environments(root: Path) -> dict[str, dict]:
    """Card id -> its `env` spec (gym id and kwargs) over every `<root>/*/tasks.json`."""
    environments: dict[str, dict] = {}
    for tasks in sorted(root.glob("*/tasks.json")):
        for card in load_cards(tasks).cards:
            environments.setdefault(card.id, card.env)
    return environments


def start_labels(bundle: ArtifactBundle, env_spec: dict) -> dict[int, dict[str, bool]]:
    """The bundle's labeling valuation of the just-reset environment, per reset seed."""
    machine = bundle.reward_machine
    labels = {}
    for seed in SEEDS:
        env = make_environment(env_spec["gym_id"], **dict(env_spec.get("env_kwargs") or {}))
        try:
            runtime = RewardMachineRuntime(machine, propositions=bundle.labeling_propositions)
            wrapped = RewardMachineEnvironment(
                env, runtime, bundle.labeling_source, terminate_on_rm=False
            )
            wrapped.reset(seed=seed)
            fresh = RewardMachineRuntime(machine, propositions=bundle.labeling_propositions)
            labels[seed] = fresh.evaluate_labeling(wrapped.environment, wrapped.labeling)
        finally:
            env.close()
    return labels


def check_start_labels(path: Path, name: str, environments: dict[str, dict]) -> str | None:
    """The reason the bundle's machine is too simple on the labels at reset, or None."""
    card = path.parent.name if name.startswith("off-") else name.split("~")[0]
    if card not in environments:
        raise LookupError(f"card {card!r} is in no tasks.json")
    bundle = ArtifactBundle.load(path)
    return machine_too_simple(bundle.reward_machine, start_labels(bundle, environments[card]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=Configuration.WORKSPACE_PATH / "experiments/benchmark",
        help="folder of suites (default: this checkout's experiments/benchmark)",
    )
    parser.add_argument("--suite", nargs="+", help="only these suites (default: every suite)")
    parser.add_argument("--start-labels", action="store_true", help="also check with start labels")
    parser.add_argument("--output", type=Path, help="JSON file to write")
    args = parser.parse_args()

    environments = card_environments(args.root) if args.start_labels else {}
    suites = args.suite or sorted(path.parent.name for path in args.root.glob("*/bundles"))
    checked, no_machine, flagged, unreadable = 0, 0, [], []
    for suite in suites:
        for ref in find_bundles(args.root / suite / "bundles"):
            rel = str(ref.path.relative_to(args.root))
            if not ref.rm_path.is_file():
                no_machine += 1
                continue
            try:
                reasons = {
                    "static": machine_too_simple(
                        parse_paper_reward_machine(ref.rm_path.read_text(encoding="utf-8"))
                    )
                }
                if args.start_labels:
                    reasons["start labels"] = check_start_labels(
                        ref.path, ref.path.name, environments
                    )
            except (
                Exception
            ) as error:  # a bundle that does not load or label is a result, not a stop
                unreadable.append(
                    {
                        "file": rel,
                        "error": f"{type(error).__name__}: {error}"[:200],
                        "trace": traceback.format_exc()[-600:],
                    }
                )
                continue
            checked += 1
            flagged += [
                {"file": rel, "form": form, "reason": reason}
                for form, reason in reasons.items()
                if reason
            ]

    print(
        f"checked {checked} bundles ({no_machine} without a machine skipped); "
        f"flagged {len(flagged)}; unreadable {len(unreadable)}"
    )
    for item in flagged:
        print("TOO SIMPLE", item["file"], f"[{item['form']}]", "|", item["reason"])
    for item in unreadable:
        print("UNREADABLE", item["file"], "|", item["error"])
    if args.output:
        report = {
            "scanned": checked,
            "without_machine": no_machine,
            "flagged": flagged,
            "unreadable": unreadable,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
