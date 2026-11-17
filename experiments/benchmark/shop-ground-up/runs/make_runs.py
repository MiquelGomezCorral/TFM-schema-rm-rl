"""Write the run configs, ``runs.json`` and ``README.md`` of the shop-ground-up runs.

Usage:
    python make_runs.py                                  rounds 1 and 2 (without the winner runs), dry runs
    python make_runs.py --winner step2-chain:P2          also the three round-2 runs of the round-1 winner
    python make_runs.py --winner step2-chain:P2 --second-pset P4

Each run is one ``train-rl`` config in ``configs/<run>.yaml``: ``experiments/benchmark/configs/ppo.yaml``
of the worktree, the run's PPO set, the card's environment and the run's machine (the fields
``run-suite`` writes, plus ``rm_state_encoding``). Run names are ``sgu-<round>-<machine>-<pset>-<oh|emb>-s<seed>`` (no-RM: ``sgu-<round>-norm-<pset>-s<seed>``).
"""

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml
from sgu import CARDS, CONFIGS, HERE, WORKTREE

BUNDLES = WORKTREE / "experiments/benchmark/shop-ground-up/bundles"
PLAN = Path("/home/turbotowerlnx/Documents/Master/TFM/TFM-schema-rm-rl/.git/agent-memory/plans")
DRY_BUNDLE = PLAN / "shop-ground-up-20261116/slice1-evidence/bundles/step2-chain"
BASE_CONFIG = WORKTREE / "experiments/benchmark/configs/ppo.yaml"

# The two cards of the shop ladder: step 2 (order then deliver) and step 3 (the full shop).
CARD_OF_STEP = {"step2": "shop-order-deliver", "step3": "shop-serve-only"}
# Bundle name -> (run-name token, step). The bundles are built into BUNDLES by slice 2.
MACHINES = {
    "step2-chain": ("step2chain", "step2"),
    "step2-generated": ("step2gen", "step2"),
    "step3-ground": ("step3ground", "step3"),
    "step3-h2": ("step3h2", "step3"),
    "step3-chain4-fixed": ("step3chain4fixed", "step3"),
    "step3-chain4-fixed-noend": ("step3chain4fixednoend", "step3"),
    "step3-generated": ("step3gen", "step3"),
    "dry-bundle": ("standin", "step2"),  # the slice-1 evidence bundle, dry runs only
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
STEPS = {"r1": 2_000_000, "r2": 5_000_000, "dry": 4096}


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
    note: str = ""

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
    """Plan step 11: 11 runs, 5M steps. The three winner runs need ``--winner`` (round 1's result)."""
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

README = """# shop-ground-up runs (rounds 1 and 2)

Generated by `make_runs.py` (do not edit; rerun it). Plan: `plans/shop-ground-up-20261116/plan.md`, steps 8-12.
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
- Bundles are read from `{bundles}/<name>` (the root copies them there at launch).

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

# Round 2 (11 runs, 5M steps): the winner runs need round 1's result first
$E/python $R/make_runs.py --winner <step2 machine>:<P1..P4> [--second-pset P3]
$E/python $R/scheduler.py r2
$E/python $R/watch.py r2
$R/judge.sh r2
```

- `scheduler.py` takes `r1`, `r2`, `dry` or run names; it skips a run that is alive or has a finished folder, refuses a run
  whose bundle is incomplete (needs `manifest.json`, `reward_machine.txt`, `labeling.py`, `state_descriptions.json`,
  `embeddings.json`), waits while 11 of its runs are alive or free RAM is under 8 GB, and writes `pids/<run>.pid` and
  `logs/<run>.log`. Runs start in their own session, so they outlive the shell that started them.
- `watch.py` also takes run names and `--window N` (steps, default 100000). Both `watch.py` and `judge.sh` look for run
  folders under `{worktree}/outputs/runs`, or under `$SGU_RUNS_ROOT` when it is set.
- `judge.sh` also takes run names, `--episodes N`, `--no-sampled` and `--force` (rejudge). It judges only
  finished runs, on the run's own card, and writes only into the run folder (`judge-<card>.json`, `judge-sampled-<card>.json`,
  `agent-traces/`, `sampled/`, `test.json`).
- Stop one run (only one this tool started): `kill $(cat $R/pids/<run>.pid)`. Nothing here kills anything by itself.
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
    sections.append(
        f"### Dry runs (4096 steps, evidence bundle `{DRY_BUNDLE.name}`)\n\n{table(rounds['dry'])}"
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
        tokens=f"{tokens}, `norm` = no-RM",
        bundles=BUNDLES,
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
    rounds = {"r1": round1(), "r2": round2(winner, args.second_pset), "dry": dry_runs()}
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
