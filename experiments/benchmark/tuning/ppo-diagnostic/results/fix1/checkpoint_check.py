"""Scratch check for fix round 1: greedy numbers of a saved single-card PPO checkpoint.

Seed 1 of bench__ppo-diag-main__base-unlock-pickup__farm__s07, three repetitions of ten episodes,
once with greedy-only evaluate() and once with evaluate_with_sampled(). Read-only: writes nothing.
Run from the repo root: PYTHONPATH=app python experiments/benchmark/tuning/ppo-diagnostic/results/fix1/checkpoint_check.py
(needs the run folder with `agent.pt`, which is not kept: rerun the suite first)
"""

from dataclasses import fields
from pathlib import Path

import torch
import yaml

from src.arm_fm.environments import make_run_environment
from src.arm_fm.ppo import evaluate, evaluate_with_sampled, load_ppo_agent
from src.config import Configuration

RUN = Path("outputs/runs/bench__ppo-diag-main__base-unlock-pickup__farm__s07")
FIELDS = ("exit_rate", "mean_length", "mean_env_return", "mean_rm_return")

directory = next(RUN.glob("seed1-*"))
saved = yaml.safe_load((directory / "config.yaml").read_text(encoding="utf-8"))
names = {item.name for item in fields(Configuration)}
CONFIG = Configuration(
    **{**{k: v for k, v in saved.items() if k in names}, "yaml_config_name": None}
)
run = make_run_environment(CONFIG)
agent = load_ppo_agent(directory / "agent.pt", run, torch.device("cpu"))
agent.eval()

for label, call in (("greedy only", evaluate), ("greedy + sampled", evaluate_with_sampled)):
    for repetition in range(3):
        row = call(CONFIG, run, agent, 10)
        print(label, repetition, {name: row[name] for name in FIELDS})
