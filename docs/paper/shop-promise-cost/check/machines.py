"""Every machine the page draws: its task, clauses with their LTLf, switches, size and well pay. No model call.

Usage, from the repository root inside RM_RL_env:
    PYTHONPATH=app python -W ignore docs/paper/shop-promise-cost/check/machines.py

Reads the bundle copies in `evidence/bundles/` (and the committed forcing/lanes-rules bundle), copies
each `reward_machine.txt` to `graphs/<name>.rm`, and prints the task, every clause with its LTLf, the
recorded reward switches, the state and transition counts, the rewards on edges into the well and the
machine's md5. Checks that the rebuilt round 7 machine is the one round 7 trained, and that the three
shop-serve machines are the ones `evidence/sweeps.out` lists. Describes `graphs/shop-serve-no-fall-rule.rm`
(written by `no_fall_rule.py`, run it first) and the four shop levels' card answers. Writes everything
it prints to `evidence/machines.out`.
"""

import hashlib
import json
import shutil
from pathlib import Path

from src.arm_fm import load_bundle
from src.benchmark.declare_judge import ltlf_of
from src.compiler import parse_paper_reward_machine

ENTRY = Path(__file__).resolve().parent.parent
BUNDLES = ENTRY / "evidence" / "bundles"
SHOP_CARDS = Path("experiments/benchmark/shop/tasks.json")
SHOP_SERVE = Path("experiments/benchmark/shop/bundles/farm/shop-serve")
MACHINES = (
    (
        "r6-both-off",
        BUNDLES / "r6-both-off",
        "round 6 A, B and C: promise cost off, end judgment off",
    ),
    ("r6-promise", BUNDLES / "r6-promise", "round 6 D: promise cost on"),
    ("r6-end", BUNDLES / "r6-end", "round 6 E: end judgment on"),
    ("r7-b4-promise", BUNDLES / "r7-b4-promise", "round 7 B4: promise cost on, cooking step"),
    ("r7-b8b-promise", BUNDLES / "r7-b8b-promise", "round 7 B8b: promise cost on"),
    (
        "shop-serve-both-off",
        BUNDLES / "shop-serve-both-off",
        "today's shop-serve: both off (the probe)",
    ),
    (
        "shop-serve-promise-before",
        BUNDLES / "shop-serve-promise-before",
        "shop-serve, promise on, before the fix",
    ),
    (
        "shop-serve-promise-after",
        BUNDLES / "shop-serve-promise-after",
        "shop-serve, promise on, after the fix",
    ),
    (
        "shop-serve-fetch-promise",
        BUNDLES / "shop-serve-fetch-promise",
        "shop-serve + paid fetch step, promise on",
    ),
    (
        "lanes-rules",
        Path("experiments/benchmark/forcing/bundles/farm/lanes-rules"),
        "committed forcing/lanes-rules",
    ),
)
# The sweeps.out line naming the same machine (built from the card by plan_pay.py levels).
SWEEP_NAMES = {
    "shop-serve-both-off": "bundles-before/shop-serve-pc-off/reward_machine.txt",
    "shop-serve-promise-before": "bundles-before/shop-serve-pc-on/reward_machine.txt",
    "shop-serve-promise-after": "bundles-after/shop-serve-pc-on/reward_machine.txt",
}
LEVELS = ("shop-serve", "shop-full", "shop-quiet-first", "shop-boil")
SWITCHES = ("reward_promise_cost", "reward_end_judgment", "reward_well", "step_limit", "gamma")


def md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8"), usedforsecurity=False).hexdigest()


def clause_lines(clauses) -> list[str]:
    return [
        f"     {p:4} {t}({', '.join(n)}): {ltlf_of((t, tuple(n), p))['readable']}"
        for t, n, p in clauses
    ]


def shape_lines(machine) -> list[str]:
    well = set(machine.rejecting_states)
    into_well = [t for t in machine.transitions if t.destination in well and t.source not in well]
    return [
        f"   {len(machine.states)} states, {len(machine.transitions)} transitions, "
        f"final {list(machine.final_states)}, rejecting {list(machine.rejecting_states)}",
        f"   {len(into_well)} edges into the well, rewards {sorted({t.reward for t in into_well})}",
    ]


def bundle_lines(name: str, path: Path, role: str, sweep_md5: dict) -> list[str]:
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    settings = manifest.get("effective_settings") or {}
    text = (path / "reward_machine.txt").read_text(encoding="utf-8")
    lines = [
        f"== {name}: {role}",
        f"   bundle: {path.relative_to(ENTRY) if path.is_absolute() else path}",
    ]
    lines.append(f"   task: {manifest['task']}")
    lines.append("   clauses:")
    lines += clause_lines(manifest["generation"]["clauses"])
    lines.append("   switches: " + ", ".join(f"{key} {settings.get(key)}" for key in SWITCHES))
    lines += shape_lines(load_bundle(path).reward_machine)
    lines.append(f"   md5 {md5(text)}")
    if name in SWEEP_NAMES:
        same = sweep_md5[SWEEP_NAMES[name]] == md5(text)
        lines.append(f"   the same machine as sweeps.out {SWEEP_NAMES[name]}: {same}")
    shutil.copyfile(path / "reward_machine.txt", ENTRY / "graphs" / f"{name}.rm")
    lines.append(f"   wrote graphs/{name}.rm")
    return lines


def no_fall_rule_lines() -> list[str]:
    manifest = json.loads((SHOP_SERVE / "manifest.json").read_text(encoding="utf-8"))
    clauses = [c for c in manifest["generation"]["clauses"] if c[0] != "ChainResponse"]
    text = (ENTRY / "graphs" / "shop-serve-no-fall-rule.rm").read_text(encoding="utf-8")
    props = sorted({p for _, names, _ in clauses for p in names})
    lines = [
        "== shop-serve-no-fall-rule: the committed shop-serve without its fall rule, end judgment off",
        f"   bundle: {SHOP_SERVE} minus hard ChainResponse(food_fell, holding_food) (no_fall_rule.py)",
        f"   task: {manifest['task']}",
        "   clauses:",
        *clause_lines(clauses),
    ]
    lines += shape_lines(parse_paper_reward_machine(text, propositions=props))
    lines.append(f"   md5 {md5(text)}")
    return lines


def level_lines() -> list[str]:
    cards = {
        card["id"]: card for card in json.loads(SHOP_CARDS.read_text(encoding="utf-8"))["cards"]
    }
    lines = [f"== the four shop levels' card answers ({SHOP_CARDS}), built by plan_pay.py levels"]
    for level in LEVELS:
        card = cards[level]
        lines += [
            f"   {level} ({card['env']['gym_id']}): {card['task']}",
            *clause_lines(card["expect"]),
        ]
    return lines


def main() -> None:
    sweep_md5 = {}
    for row in (ENTRY / "evidence" / "sweeps.out").read_text(encoding="utf-8").splitlines():
        if row and not row.startswith("#"):
            digest, name = row.split()
            sweep_md5[name] = digest
    lines = []
    for name, path, role in MACHINES:
        lines += bundle_lines(name, path, role, sweep_md5)
    trained = (BUNDLES / "r7-b8b-promise" / "reward_machine.txt").read_text(encoding="utf-8")
    rebuilt = (BUNDLES / "r7-b8b-rebuilt" / "reward_machine.txt").read_text(encoding="utf-8")
    lines.append(
        f"== r7-b8b-rebuilt (the regression's bundle) has round 7 B8b's machine text: {trained == rebuilt}"
    )
    lines += no_fall_rule_lines()
    lines += level_lines()
    text = "\n".join(lines) + "\n"
    (ENTRY / "evidence" / "machines.out").write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
