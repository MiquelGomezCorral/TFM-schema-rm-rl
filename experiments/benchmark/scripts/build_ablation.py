"""Build the ablation bundles of complex cards from their FARM bundles, then check them.

Usage (repository root, `RM_RL_env`):
    PYTHONPATH=app python experiments/benchmark/scripts/build_ablation.py CARD [CARD ...] \
        [--variants progress well ...] [--check-only] [--root experiments/benchmark]

For each card and variant it runs `ablate-rm` on `<root>/complex/bundles/farm/<card>` and writes
`<root>/ablation/bundles/<card>/off-<variant>/`. Variants default to every switch in `OFF_PARTS`
(`progress`, `well`, `soft_break`, `soft_pending`, `end_judgment`, `recurrent_soft_penalty`). An
existing `off-<variant>` folder is kept, not rebuilt: delete it to rebuild it. Only
`recurrent_soft_penalty` calls a model (it writes the state descriptions again) and needs the local
embedding server on 127.0.0.1:8934; run the script through `dotenv -f .env run --no-override --`
when you build it, and leave it out of `--variants` otherwise.

Then it checks every `off-<variant>` of each card and prints one line each: `labeling.py` byte-equal
to the source's, the bundle loads and validates complete, the machine is not "too simple", the text
changed (unless the manifest says the switch is a no-op for this machine), the state descriptions
and embeddings were remade (only when the states changed), and the manifest names the switch.
`--check-only` skips the build. The exit code is 1 when a build or a check failed.
"""

import argparse
from pathlib import Path

from scripts.ablate_rm import OFF_PARTS, ablate_rm, skeleton
from src.arm_fm import ArtifactBundle
from src.benchmark.early_end import machine_too_simple
from src.config import Configuration


def build(source: Path, destinations: dict[str, Path]) -> list[str]:
    """Run `ablate-rm` for each variant whose folder is missing; return the variants that failed."""
    failed = []
    for variant, destination in destinations.items():
        if destination.exists():
            print(f"{destination.name}: kept (already built)")
        elif not ablate_rm(Configuration(bundle=source), variant, destination):
            failed.append(variant)
    return failed


def check(variant: str, bundle_dir: Path, source_dir: Path) -> tuple[dict, list[str]]:
    """The facts about one ablation bundle against its source, and what is wrong with it."""
    labeling_equal = (bundle_dir / "labeling.py").read_bytes() == (
        source_dir / "labeling.py"
    ).read_bytes()
    row = {"labeling_equal": labeling_equal}
    problems = [] if labeling_equal else ["labeling.py differs from the source"]
    try:
        bundle = ArtifactBundle.load(bundle_dir)
        bundle.validate(require_complete=True)
    except Exception as error:  # report any load or validation failure as text
        return row | {"validate": "FAIL"}, [*problems, f"{type(error).__name__}: {error}"]
    source = ArtifactBundle.load(source_dir)
    ablation = bundle.manifest.effective_settings.get("ablation", {})
    changed = (bundle_dir / "reward_machine.txt").read_text(encoding="utf-8") != (
        source_dir / "reward_machine.txt"
    ).read_text(encoding="utf-8")
    states_changed = skeleton(bundle.reward_machine) != skeleton(source.reward_machine)
    row |= {
        "validate": "ok",
        "text_changed": changed,
        "no_op": ablation.get("no_op"),
        "states_changed": states_changed,
        "descriptions_remade": bundle.state_descriptions != source.state_descriptions,
        "embeddings_remade": bundle.embeddings != source.embeddings,
    }
    expected = {  # what `ablate-rm` does: remake both only when the states or transitions changed
        "descriptions_remade": states_changed,
        "embeddings_remade": states_changed and bool(source.embeddings),
    }
    problems += [
        f"{key} is {row[key]}, expected {want}"
        for key, want in expected.items()
        if row[key] != want
    ]
    if reason := machine_too_simple(bundle.reward_machine):
        problems.append(f"too simple: {reason}")
    if ablation.get("off") != variant:
        problems.append(f"manifest says off={ablation.get('off')!r}")
    if changed == bool(ablation.get("no_op")):
        problems.append("text change and manifest no_op disagree")
    return row, problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("cards", nargs="+", help="complex card ids, e.g. cx-rules-only")
    parser.add_argument("--variants", nargs="+", choices=list(OFF_PARTS), default=list(OFF_PARTS))
    parser.add_argument("--check-only", action="store_true", help="do not build, only check")
    parser.add_argument(
        "--root",
        type=Path,
        default=Configuration.WORKSPACE_PATH / "experiments/benchmark",
        help="folder of suites (default: this checkout's experiments/benchmark)",
    )
    args = parser.parse_args()

    failures = 0
    for card in args.cards:
        source = args.root / "complex/bundles/farm" / card
        destinations = {
            v: args.root / "ablation/bundles" / card / f"off-{v}" for v in args.variants
        }
        if not args.check_only:
            failures += len(build(source, destinations))
        for variant, destination in destinations.items():
            if not destination.is_dir():
                print(f"{card}\toff-{variant}\tMISSING")
                failures += 1
                continue
            row, problems = check(variant, destination, source)
            print(f"{card}\toff-{variant}\t{row}\t{'; '.join(problems) or 'ok'}")
            failures += bool(problems)
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
