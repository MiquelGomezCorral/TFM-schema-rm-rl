#!/usr/bin/env bash
# Judge finished shop-ground-up runs (greedy + sampled) and print the summary table.
# Usage: judge.sh <r1|r2|r3|r4|dry|all|run name> [...] [--episodes N] [--no-sampled] [--force]
# Runs from the worktree with the RM_RL_env python; writes only into the run folders (see judge.py).
set -eu
R="$(cd "$(dirname "$0")" && pwd)"
W="${SGU_WORKTREE:-/home/turbotowerlnx/orca/workspaces/TFM-schema-rm-rl/tp-shop-ground-up}"
E=/home/turbotowerlnx/miniconda3/envs/RM_RL_env/bin
cd "$W"
OMP_NUM_THREADS=2 PYTHONPATH=app exec "$E/python" "$R/judge.py" "$@"
