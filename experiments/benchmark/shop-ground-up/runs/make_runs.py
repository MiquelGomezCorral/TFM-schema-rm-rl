"""Write the run configs, ``runs.json`` and ``README.md`` of the shop-ground-up runs.

Usage:
    python make_runs.py                                  rounds 1 and 2 (without the winner runs), dry runs
    python make_runs.py --winner step2-chain:P2          also the three round-2 runs of the round-1 winner
    python make_runs.py --winner step2-chain:P2 --second-pset P4

Each run is one ``train-rl`` config in ``configs/<run>.yaml``: ``experiments/benchmark/configs/ppo.yaml``
of the worktree, the run's PPO set, the card's environment and the run's machine (the fields
``run-suite`` writes, plus ``rm_state_encoding``). Run names are ``sgu-<round>-<machine>-<pset>-<oh|emb>-s<seed>`` (no-RM: ``sgu-<round>-norm-<pset>-s<seed>``);
a warm start (``init_from``) adds ``-ws``.
"""

import argparse
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import yaml
from sgu import CARDS, CONFIGS, HERE, WORKTREE

BUNDLES = WORKTREE / "experiments/benchmark/shop-ground-up/bundles"
DRY_BUNDLE = BUNDLES / "step2-chain"
BASE_CONFIG = WORKTREE / "experiments/benchmark/configs/ppo.yaml"

# The two cards of the shop ladder: step 2 (order then deliver) and step 3 (the full shop).
CARD_OF_STEP = {"step2": "shop-order-deliver", "step3": "shop-serve-only"}
# Bundle name -> (run-name token, step). The bundles are built into BUNDLES by slice 2.
MACHINES = {
    "step2-chain": ("step2chain", "step2"),
    "step2-generated": ("step2gen", "step2"),
    # The final generator prompt's own machine (try armA3-step2-1).
    "step2-a3": ("step2a3", "step2"),
    # Hand copy of step2-a3 for the cause test: only u4's end charge differs (-3 at the cut, not -1).
    "step2-a3-ladder": ("step2a3ladder", "step2"),
    # step3-ground without the prepare stage: +1 per agent stage, no charges (is the compiled pay shape the problem?).
    "step2-ground": ("step2ground", "step2"),
    # Scale-only copies (scale versus shape): step2-a3 with every pay x10, step2-ground with every pay x0.1.
    "step2-a3-x10": ("step2a3x10", "step2"),
    "step2-ground-x01": ("step2groundx01", "step2"),
    # Scale test 2: step2-generated (the model's own step-2 machine) with every pay and failed reward x10.
    "step2-generated-x10": ("step2genx10", "step2"),
    "step3-ground": ("step3ground", "step3"),
    "step3-h2": ("step3h2", "step3"),
    "step3-chain4-fixed": ("step3chain4fixed", "step3"),
    "step3-chain4-fixed-noend": ("step3chain4fixednoend", "step3"),
    "step3-generated": ("step3gen", "step3"),
    # The final generator prompt's step-3 machine (try armA3-step3-1) and its x10 copy.
    "step3-a3": ("step3a3", "step3"),
    "step3-a3-x10": ("step3a3x10", "step3"),
    "dry-bundle": ("standin", "step2"),  # step2-chain, dry runs only
    "no-rm-step2": ("norm", "step2"),
    "no-rm-step3": ("norm", "step3"),
}
NO_RM = {"no-rm-step2", "no-rm-step3"}
# No end judgment: the runtime charges a flat time_limit_penalty (default -0.5) at the cut, so these
# runs set it to 0. Every machine with an end judgment ignores time_limit_penalty (runtime.py:224-226).
NO_END = {"step3-chain4-fixed-noend"}
# PPO sets: (ppo_clip_coef, gamma, ppo_learning_rate). ppo_ent_coef is 0.01 everywhere.
PSETS = {
    "P0": (0.1, 0.99, 1e-3),
    "P1": (0.2, 0.995, 1e-3),
    "P2": (0.2, 0.995, 3e-4),
    "P3": (0.2, 0.999, 1e-3),
    "P4": (0.2, 0.999, 3e-4),
}
ENT_COEF = 0.01
EVAL_FREQUENCY = 50_000
STEPS = {"r1": 2_000_000, "r2": 5_000_000, "r3": 2_000_000, "cont": 10_000_000, "dry": 4096}
# Round 1's finished step-2 embedding run: the weights round 3's warm start (``-ws``) begins from.
STEP2_EMBEDDING_RUN = (
    WORKTREE / "outputs/runs/sgu-r1-step2gen-p1-emb-s1/seed1-20261117T013552-920749"
)
# Round 2's 5M step-3 learners (machine, PPO set) -> run folder under outputs/runs; round 3's ``-cont`` run
# of each starts from that folder's weights and trains 10M more steps (15M in all).
CONTINUED = {
    ("step3-ground", "P1"): "sgu-r2-step3ground-p1-oh-s1/seed1-20261117T022045-980497",
    ("step3-h2", "P1"): "sgu-r2-step3h2-p1-oh-s1/seed1-20261117T022409-984803",
    ("step3-ground", "P3"): "sgu-r2-step3ground-p3-oh-s1/seed1-20261117T022751-988381",
}


@dataclass
class Run:
    name: str
    round: str
    machine: str  # a MACHINES key or "dry-bundle"
    step: str
    pset: str
    encoding: str  # one-hot, embedding or none (no-RM)
    steps: int
    seed: int
    bundle: str | None = None
    init_from: str | None = None  # a finished PPO run folder whose weights the run starts from

    @property
    def card(self) -> str:
        return CARD_OF_STEP[self.step]

    @property
    def config(self) -> Path:
        return CONFIGS / f"{self.name}.yaml"


def make_run(rnd: str, machine: str, pset: str, encoding: str = "one-hot", seed: int = 1) -> Run:
    token, step = MACHINES[machine]
    no_rm = machine in NO_RM
    tag = "" if no_rm else "-emb" if encoding == "embedding" else "-oh"
    bundle = DRY_BUNDLE if rnd == "dry" else BUNDLES / machine
    return Run(
        f"sgu-{rnd}-{token}-{pset.lower()}{tag}-s{seed}",
        rnd,
        machine,
        step,
        pset,
        "none" if no_rm else encoding,
        STEPS[rnd],
        seed,
        None if no_rm else str(bundle),
    )


def round1() -> list[Run]:
    """Plan step 9: 11 runs on step 2, seed 1, 2M steps."""
    runs = [
        make_run("r1", machine, pset)
        for machine in ("step2-chain", "step2-generated")
        for pset in ("P1", "P2", "P3", "P4")
    ]
    runs += [
        make_run("r1", "step2-generated", "P0"),
        make_run("r1", "step2-generated", "P1", "embedding"),
        make_run("r1", "no-rm-step2", "P1"),
    ]
    return runs


def round2(winner: tuple[str, str] | None, second_pset: str) -> list[Run]:
    """Plan step 11, 5M steps; ``--winner`` (round 1's result) adds that machine's runs.

    Those are seeds 2 and 3, plus an embedding run for any winner other than step2-generated at P1.
    """
    runs = [
        make_run("r2", machine, "P1")
        for machine in (
            "step3-ground",
            "step3-h2",
            "step3-chain4-fixed",
            "step3-chain4-fixed-noend",
        )
    ]
    runs += [
        make_run("r2", machine, second_pset) for machine in ("step3-ground", "step3-chain4-fixed")
    ]
    runs += [make_run("r2", "step3-generated", "P1"), make_run("r2", "no-rm-step3", "P1")]
    if winner:
        machine, pset = winner
        runs += [make_run("r2", machine, pset, seed=seed) for seed in (2, 3)]
        # Round 1's embedding A/B ran on step2-generated at P1; any other winner needs its own.
        if (machine, pset) != ("step2-generated", "P1"):
            runs.append(make_run("r2", machine, pset, "embedding"))
    return runs


def round3() -> list[Run]:
    """Plan steps 13-14, by result: the final generator prompt's step-2 machine, then step-3 runs.

    The step-2 machine and its ladder copy run at P1 for 2M, and so do the hand machine step2-ground (seeds 1-3)
    and the three scale copies step2-a3-x10, step2-ground-x01 and step2-generated-x10 (seeds 1-3 each).
    The eight step-3 runs take 5M: step3-ground seeds 2 and 3,
    its embedding run, step3-chain4-fixed (embedding) warm-started from round 1's step-2
    embedding learner, step3-h2 seeds 2 and 3 (one-hot), and step3-a3 with its x10 copy (seed 1, one-hot).
    Three more continue round 2's step-3 learners for 10M steps (``-cont``).
    """
    warm = make_run("r3", "step3-chain4-fixed", "P1", "embedding")
    long_runs = [
        make_run("r3", "step3-ground", "P1", seed=2),
        make_run("r3", "step3-ground", "P1", seed=3),
        make_run("r3", "step3-ground", "P1", "embedding"),
        replace(warm, name=f"{warm.name}-ws", init_from=str(STEP2_EMBEDDING_RUN)),
        make_run("r3", "step3-h2", "P1", seed=2),
        make_run("r3", "step3-h2", "P1", seed=3),
        make_run("r3", "step3-a3", "P1"),
        make_run("r3", "step3-a3-x10", "P1"),
    ]
    continued = []
    for (machine, pset), folder in CONTINUED.items():
        run = make_run("r3", machine, pset)
        source = WORKTREE / "outputs/runs" / folder
        continued.append(
            replace(run, name=f"{run.name}-cont", steps=STEPS["cont"], init_from=str(source))
        )
    return [
        make_run("r3", "step2-a3", "P1"),
        make_run("r3", "step2-a3-ladder", "P1"),
        *(make_run("r3", "step2-ground", "P1", seed=seed) for seed in (1, 2, 3)),
        *(
            make_run("r3", machine, "P1", seed=seed)
            for machine in ("step2-a3-x10", "step2-ground-x01", "step2-generated-x10")
            for seed in (1, 2, 3)
        ),
        *(replace(run, steps=STEPS["r2"]) for run in long_runs),
        *continued,
    ]


def dry_runs() -> list[Run]:
    """Three 4096-step runs on the evidence bundle: one-hot P1, embedding P1, no-RM P1."""
    return [
        make_run("dry", "dry-bundle", "P1"),
        make_run("dry", "dry-bundle", "P1", "embedding"),
        make_run("dry", "no-rm-step2", "P1"),
    ]


# ======================================================================================
#                                       CONFIGS
# ======================================================================================


def build_config(run: Run) -> dict:
    """The ``train-rl`` config of a run, in the shape ``run-suite`` writes plus the encoding."""
    card = json.loads((CARDS / f"{run.card}.json").read_text(encoding="utf-8"))
    env = card["env"]
    clip, gamma, learning_rate = PSETS[run.pset]
    config = yaml.safe_load(BASE_CONFIG.read_text(encoding="utf-8"))
    config.update(
        ppo_clip_coef=clip,
        gamma=gamma,
        ppo_learning_rate=learning_rate,
        ppo_ent_coef=ENT_COEF,
        eval_frequency=EVAL_FREQUENCY,
        exp_name=run.name,
        env_family=env["family"],
        gym_id=env["gym_id"],
        env_kwargs=env["env_kwargs"],
        observation=env["observation"],
        layout=env["layout"],
        layout_seed=env["layout_seed"],
        total_timesteps=run.steps,
        success="env",
    )
    if run.init_from:
        config["init_from"] = run.init_from
    if run.round == "dry":
        config.update(final_eval_episodes=10, eval_episodes=5)  # a short final check
    if run.bundle is None:
        config["reward_source"] = "env"
        return config

    config.update(
        reward_source="rm", bundle=run.bundle, rm_state_encoding=run.encoding.replace("-", "_")
    )
    if run.machine in NO_END:
        config["time_limit_penalty"] = 0.0
    return config


def write_configs(runs: list[Run]) -> None:
    CONFIGS.mkdir(exist_ok=True)
    current = {run.config.name for run in runs}
    for old in CONFIGS.glob("*.yaml"):  # a winner run of an earlier --winner is dropped
        if old.name not in current:
            old.unlink()
    for run in runs:
        header = f"# {run.name}: {run.machine}, {run.step}, {run.pset}, {run.encoding}, seed {run.seed}\n"
        text = yaml.safe_dump(build_config(run), sort_keys=False)
        run.config.write_text(header + text, encoding="utf-8")


# ======================================================================================
#                                        README
# ======================================================================================

README = """# shop-ground-up runs (rounds 1 to 3)

Generated by `make_runs.py` (do not edit; rerun it). Plan: `plans/shop-ground-up-20261116/plan.md`, steps 8-13.
One run = one `train-rl` config in `configs/`, started from the worktree `{worktree}`.

Names: `R={here}`, `E=/home/turbotowerlnx/miniconda3/envs/RM_RL_env/bin`.
Environment: step 2 = card `shop-order-deliver` (`order_needed` true, `cooking_needed` false); step 3 = card
`shop-serve-only` (the full shop); both `max_steps` 600, `slip_chance` 0, `siren` false (`cards/`).
Everything not listed below comes from `experiments/benchmark/configs/ppo.yaml` (16 envs, 256 steps, 16 minibatches,
10 epochs, `ppo_vf_coef` 0.5, `ppo_gae_lambda` 0.95, greedy eval), `eval_frequency` 50000, CUDA as in the earlier shop runs.

## PPO sets

| set | `ppo_clip_coef` | `gamma` | `ppo_learning_rate` | `ppo_ent_coef` |
|---|---|---|---|---|
{psets}

## Changes after the packet

- Round 2 uses `step3-chain4-fixed` and `step3-chain4-fixed-noend` where the plan names `step3-chain4` and
  `step3-chain4-noend` (the literal step-3 chain fails the plan check: it never ends accepting). The two literal
  bundles get no runs.
- The `-noend` run sets `time_limit_penalty: 0`: a machine with no end judgment gets a flat -0.5 at the cut
  (`app/src/arm_fm/runtime.py:224-226`). Every other run leaves it at the default; they all have an end judgment, which
  ignores `time_limit_penalty`.
- Every RM run name ends in `-oh` (one-hot machine state) or `-emb` (text embedding, `rm_state_encoding: embedding`) before
  the seed, so the two are never mixed in a table (decision record: one-hot runs are never pooled with embedding runs).
  No-RM runs use `reward_source: env` and no bundle.
- Run names: `sgu-<round>-<machine>-<pset>-<oh|emb>-s<seed>`, no-RM `sgu-<round>-norm-<pset>-s<seed>`; machine tokens: {tokens}.
- A name ending in `-ws` is a warm start: its config sets `init_from` to the finished run folder
  `{warm_start}` (round 1's step-2 embedding run); train-rl loads its `agent.pt`, with a fresh optimizer and schedules.
- Round 3: `step2-a3` and its hand copy `step2-a3-ladder` (cut charge -3.3 / -2.2 / -1.1 / 0 after the arrival, order,
  pickup, serve; every pay and edge as in `step2-a3`) run 2M steps, and so do the three `step2-ground` runs (seeds 1-3;
  hand machine: +1 per agent stage, +2 for the order with food in hand, no negative pay, end charge 0), and so do the six
  scale-copy runs (seeds 1-3 each): `step2-a3-x10` is `step2-a3` with every pay and both failed rewards x10, `step2-ground-x01` is
  `step2-ground` with every pay x0.1; states and edges as in their sources; the three `step3-ground` runs (seeds 2 and 3 one-hot, seed 1 embedding) and the
  `-ws` run take 5M.
- Round 3, scale test 2 (do the compiler's pay magnitudes stop the generated machines): `step2-generated-x10` is
  `step2-generated` (the model's own step-2 machine) with every pay and both failed rewards x10 (seeds 1-3, 2M);
  `step3-a3` is generator try `armA3-step3-1` as written (the final prompt's step-3 machine) and `step3-a3-x10` its x10 copy
  (seed 1 each, 5M); states and edges as in their sources.
- A name ending in `-cont` continues a finished round-2 step-3 run (same machine, PPO set, encoding, seed): `init_from`
  is that 5M run's folder, so it loads its `agent.pt` (fresh optimizer and schedules) and trains 10M more steps, 15M in all.
- Bundles are read from `{bundles}/<name>`.

## Commands

Start from anywhere; every tool runs the worktree code by itself. Paths below are the folder this README sits in.

```bash
E=/home/turbotowerlnx/miniconda3/envs/RM_RL_env/bin
R={here}
$E/python $R/make_runs.py                          # (re)write configs/, runs.json and this README

# Round 1 (11 runs, 2M steps, seed 1)
$E/python $R/scheduler.py r1                       # starts the runs, at most 11 alive, prints each run folder
$E/python $R/watch.py r1                           # one table: step, served per episode, stages, eval, entropy, EV
$E/python $R/watch.py r1 --early                   # the same for the first 100k steps (early vs late stage counts)
$R/judge.sh r1                                     # greedy + sampled judge, 100 episodes, then the summary table

# Round 2 (5M steps): the winner runs need round 1's result first
$E/python $R/make_runs.py --winner <step2 machine>:<P1..P4> [--second-pset P3]
$E/python $R/scheduler.py r2
$E/python $R/watch.py r2
$R/judge.sh r2

# Round 3 (by result; 2M, 5M or 10M steps, see the table)
$E/python $R/scheduler.py r3
$E/python $R/watch.py r3
$R/judge.sh r3
```

- `scheduler.py` takes `r1`, `r2`, `r3`, `dry` or run names; it skips a run that is alive or has a finished folder, refuses a run
  whose bundle is incomplete (needs `manifest.json`, `reward_machine.txt`, `labeling.py`, `state_descriptions.json`,
  `embeddings.json`), waits while 11 of its runs are alive or free RAM is under 8 GB, and writes `pids/<run>.pid` and
  `logs/<run>.log`. Runs start in their own session, so they outlive the shell that started them.
- `watch.py` also takes run names and `--window N` (steps, default 100000). Both `watch.py` and `judge.sh` look for run
  folders under `{worktree}/outputs/runs`, or under `$SGU_RUNS_ROOT` when it is set.
- `judge.sh` also takes run names, `--episodes N`, `--no-sampled` and `--force` (rejudge). It judges only
  finished runs, on the run's own card, and writes only into the run folder (`judge.json`, `judge-<card>.json`,
  `judge-sampled-<card>.json`, `agent-traces/`, `sampled/`, `test.json`).
- Stop one run (only one this tool started): first check that `ps -o args= -p $(cat $R/pids/<run>.pid)` names that run's
  config (a pid file outlives its run, and the pid may be reused), then `kill` that pid. Nothing here kills anything by itself.
- Run one scheduler at a time: it takes no lock, so two at once can start the same run twice or pass the cap. To add
  runs, stop the waiting scheduler (its runs live in their own sessions and keep going) and start one with every
  remaining name; it skips runs that are alive or finished.
- A run that dies has no `summary.json` (train-rl cannot resume): move its folder aside and start the run again.

## Runs

{tables}
"""


def table(runs: list[Run]) -> str:
    lines = [
        "| run | machine | env | PPO set | encoding | steps | seed |",
        "|---|---|---|---|---|---|---|",
    ]
    for run in runs:
        clip, gamma, learning_rate = PSETS[run.pset]
        lines.append(
            f"| `{run.name}` | {run.machine} | {run.step} ({run.card}) "
            f"| {run.pset} ({clip} / {gamma} / {learning_rate:g}) | {run.encoding} | {run.steps:,} | {run.seed} |"
        )
    return "\n".join(lines)


def write_readme(rounds: dict[str, list[Run]], pending: bool) -> None:
    sections = [
        f"### Round 1 (plan step 9)\n\n{table(rounds['r1'])}",
        f"### Round 2 (plan step 11)\n\n{table(rounds['r2'])}",
    ]
    if pending:
        sections[1] += (
            "\n\nNot written yet: the three round-2 runs of the round-1 winner (seeds 2 and 3 at 5M; the embedding "
            "run, only when the winner is not `step2-generated` at P1). Run `make_runs.py --winner <machine>:<set>`."
        )
    sections.append(f"### Round 3 (plan steps 13-14, by result)\n\n{table(rounds['r3'])}")
    sections.append(
        f"### Dry runs (4096 steps, bundle `{DRY_BUNDLE.name}`)\n\n{table(rounds['dry'])}"
    )
    psets = "\n".join(
        f"| {name} | {clip} | {gamma} | {lr:g} | {ENT_COEF} |"
        for name, (clip, gamma, lr) in PSETS.items()
    )
    tokens = ", ".join(f"`{token}` = {machine}" for machine, (token, _) in MACHINES.items())
    text = README.format(
        worktree=WORKTREE,
        here=HERE,
        psets=psets,
        tokens=tokens,
        bundles=BUNDLES,
        warm_start=STEP2_EMBEDDING_RUN,
        tables="\n\n".join(sections),
    )
    (HERE / "README.md").write_text(text, encoding="utf-8")


# ======================================================================================
#                                         MAIN
# ======================================================================================


def parse_winner(text: str | None) -> tuple[str, str] | None:
    if text is None:
        return None
    machine, _, pset = text.partition(":")
    if MACHINES.get(machine, ("", ""))[1] != "step2" or pset not in PSETS:
        raise SystemExit(
            f"--winner takes <step2 bundle>:<P0..P4>, e.g. step2-chain:P1; got {text!r}"
        )
    return machine, pset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--winner", help="round-1 winner as <step2 bundle>:<PPO set>")
    parser.add_argument(
        "--second-pset", default="P3", choices=sorted(PSETS), help="round 2's second PPO set"
    )
    args = parser.parse_args()

    winner = parse_winner(args.winner)
    rounds = {
        "r1": round1(),
        "r2": round2(winner, args.second_pset),
        "r3": round3(),
        "dry": dry_runs(),
    }
    runs = [run for group in rounds.values() for run in group]
    names = [run.name for run in runs]
    if len(set(names)) != len(names):
        raise SystemExit("two runs share a name")

    write_configs(runs)
    (HERE / "runs.json").write_text(
        json.dumps(
            [{**asdict(run), "card": run.card, "config": str(run.config)} for run in runs], indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    write_readme(rounds, pending=winner is None)
    print(
        f"wrote {len(runs)} configs ({', '.join(f'{k} {len(v)}' for k, v in rounds.items())}), runs.json, README.md"
    )


if __name__ == "__main__":
    main()
