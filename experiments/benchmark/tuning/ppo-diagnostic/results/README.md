# PPO diagnostic results

Small outputs of the diagnostic, copied out of the git-ignored `outputs/` so the numbers stay with the scripts. No model
weights, no run curves.

- `runs.csv`, `variants.csv`, `tables.md`, `cards.json`: what `analyze.py` reported, per run and per variant.
- `runs/bench__ppo-diag-*/seed*/summary.json`: the final evaluation of every finished run (61 files).
- `episode-facts/`, `random-agent/`, `reset-check-*.txt`: outputs of `episode_facts.py`, `random_agent.py` and the
  reset check.
- `lane-{a,b,c,d}.sh`, `logs/`, `fix1/`: how the runs were launched (suites `../<suite>/runs.yaml`, one `train.sh` call each, run
  from the repository root, not from this folder) and their logs.

Rerun (repository root, inside `RM_RL_env`, training only, no LLM call): launch the suites as in `lane-*.sh`, then
`PYTHONPATH=app python experiments/benchmark/tuning/ppo-diagnostic/analyze.py --out <folder>`,
`episode_facts.py` and `random_agent.py` (each writes under `outputs/ppo-diagnostic/` by default). The run folders
(`outputs/runs/bench__ppo-diag-*`, 237 MB with weights) are not kept; they rerun.
