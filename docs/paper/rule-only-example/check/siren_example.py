"""Shop-siren example: rebuild the FARM bundle's two-state machine and walk a ring-then-toggle trace.

Rebuilds the machine of card `shop-siren` from its stored clause with `rule_only_example.rebuild`
(the repository's compiler; fails unless it equals the stored `reward_machine.txt`) and asserts its
states, its two transitions and their pays. Then it walks a 6-step episode through the real
`RewardMachineRuntime`, checks the card's plan check and the judged results of the final run's six
runs (3 FARM, 3 no-RM), and draws the graph with `render_file`, which `render-rm --html` calls.
No model call, no training (MONA runs locally). Writes `evidence/shop-siren-*` and
`evidence/graph/shop-siren.*`.

Usage, from the repository root, inside RM_RL_env, in the checkout that holds `outputs/runs/`
(git-ignored):
    PYTHONPATH=app python -W ignore docs/paper/rule-only-example/check/siren_example.py
"""

import json
from pathlib import Path

import yaml
from rule_only_example import clause_rows, clause_table, rebuild, trace_table, walk

import src
from scripts.render_rm import render_file
from src.compiler import RuntimeTransition

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BUNDLE = ROOT / "experiments/benchmark/shop/bundles/farm/shop-siren"
PLAN_CHECK = BUNDLE.parent / "shop-siren.plan_check.json"
RUNS = ROOT / "outputs/runs"
EVIDENCE = HERE.parent / "evidence"

STATES = ("u0", "u1")
TRANSITIONS = (
    RuntimeTransition("u0", "siren_ringing&!switch_toggled", "u1", -1.0),
    RuntimeTransition("u1", "switch_toggled", "u0", 1.0),
)
JUDGED = {"farm": [1.0, 1.0, 1.0], "no-rm": [0.0, 0.0, 1.0]}  # seeds 1 to 3

# One ring answered, then a second one answered: labels true, state after, pay, note.
TRACE = [
    ((), "u0", 0.0, "the shop is quiet, nothing happens"),
    (("siren_ringing",), "u1", -1.0, "the siren starts ringing: the promise opens"),
    (("siren_ringing",), "u1", 0.0, "the agent walks to the switch, the siren still rings"),
    (
        ("switch_toggled",),
        "u0",
        1.0,
        "the agent toggles the switch, the siren stops: the promise is kept",
    ),
    (("siren_ringing",), "u1", -1.0, "the siren rings again: the promise opens"),
    (("switch_toggled",), "u0", 1.0, "the agent toggles the switch again: the promise is kept"),
]


def check_plan_check() -> None:
    """The recorded plan runs: the solving plan ends in u0 paying 0, every wrong plan in u1 at -1."""
    runs = json.loads(PLAN_CHECK.read_text(encoding="utf-8"))["runs"]
    assert len(runs) == 12 and not any(run["problems"] for run in runs)
    for run in runs:
        want = ("u0", 0.0) if run["kind"] == "solve" else ("u1", -1.0)
        assert (run["end_state"], run["pay"][0]) == want, f"{run['plan']} seed {run['seed']}"


def judged_runs() -> list[dict]:
    """The judged success of each of the six final-run runs, and the FARM runs' RM state encoding."""
    rows = []
    for arm, expected in JUDGED.items():
        folder = RUNS / f"bench__shop__shop-siren__{arm}__ppo"
        if arm == "farm":
            run_config = yaml.safe_load((folder / "run-config.yaml").read_text(encoding="utf-8"))
            assert run_config["bundle"] == str(BUNDLE.relative_to(ROOT)), "another bundle"
        for seed, want in zip((1, 2, 3), expected, strict=True):
            (judge,) = folder.glob(f"seed{seed}-*/judge.json")
            data = json.loads(judge.read_text(encoding="utf-8"))
            assert data["mean_judged_success"] == want, f"{arm} seed {seed} differs"
            row = {
                "arm": arm,
                "seed": seed,
                "run": judge.parent.name,
                "episodes": data["episodes"],
                "mean_judged_success": data["mean_judged_success"],
            }
            if arm == "farm":  # the no-RM arm has no machine state to encode
                config = yaml.safe_load((judge.parent / "config.yaml").read_text(encoding="utf-8"))
                assert config["rm_state_encoding"] == "embedding"
                row["rm_state_encoding"] = "embedding"
            rows.append(row)
    return rows


def main() -> None:
    built = rebuild(BUNDLE)
    machine = built.machine
    assert machine.states == STATES
    assert machine.initial_state == "u0"
    assert machine.final_states == () and machine.rejecting_states == ()
    assert machine.default_reward == 0
    assert machine.transitions == TRANSITIONS
    assert all(edge.reward == 0 for edge in built.no_progress.transitions), "a pay is not progress"

    code = Path(src.__file__).parent.parent
    where = code.relative_to(ROOT) if code.is_relative_to(ROOT) else "a copy outside the repository"
    report = [f"code: {where}", f"bundle: {BUNDLE.relative_to(ROOT)}"]
    report.append("rebuilt machine equals the stored reward_machine.txt: OK")
    report.append("2 states u0, u1, initial u0, no final state, default reward 0: OK")
    report.append(
        "(u0, siren_ringing&!switch_toggled) -> u1 pays -1, (u1, switch_toggled) -> u0 pays +1: OK"
    )
    report.append("both pays are the progress part: the progress-off machine pays 0 everywhere: OK")

    names = machine.used_propositions
    steps = [{name: name in labels for name in names} for labels, *_ in TRACE]
    walked = walk(machine, names, steps)
    assert [(step.destination, step.pay) for step in walked] == [
        (to, pay) for _, to, pay, _ in TRACE
    ]
    assert walked[-1].total == 0, "a ring answered pays back its charge"
    trace = trace_table(walked, [note for *_, note in TRACE])
    report.append(f"trace of {len(walked)} steps through the real runtime, total 0: OK")

    check_plan_check()
    report.append(
        "plan check, 12 runs: solving plan ends in u0 paying 0, wrong plans in u1 at -1: OK"
    )
    rows = judged_runs()
    report.append("judged success, FARM 1.0 1.0 1.0 and no-RM 0.0 0.0 1.0 (100 episodes each): OK")
    report.append("the FARM runs trained with rm_state_encoding: embedding: OK")

    graph = EVIDENCE / "graph"
    graph.mkdir(parents=True, exist_ok=True)
    rm_file = graph / "shop-siren.rm"
    rm_file.write_text(
        (BUNDLE / "reward_machine.txt").read_text(encoding="utf-8"), encoding="utf-8"
    )
    drawn = render_file(rm_file, graph / "shop-siren.svg", html=True)
    report.append("graph: " + ", ".join(path.name for path in drawn))

    clauses = clause_table(clause_rows(built))
    tables = {"shop-siren-clauses": clauses, "shop-siren-trace": trace}
    for name, text in tables.items():
        (EVIDENCE / f"{name}.md").write_text(text + "\n", encoding="utf-8")
    (EVIDENCE / "shop-siren-results.json").write_text(
        json.dumps(rows, indent=1) + "\n", encoding="utf-8"
    )
    readme = (HERE.parent / "README.md").read_text(encoding="utf-8")
    stale = [name for name, text in tables.items() if text not in readme]
    assert not stale, f"README tables differ from the evidence: {stale}"
    report.append("README tables equal the evidence tables: OK")
    (EVIDENCE / "shop-siren-check-output.txt").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    print("\n".join(report))


if __name__ == "__main__":
    main()
