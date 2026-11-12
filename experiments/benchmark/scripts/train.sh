#!/usr/bin/env bash
# Train one benchmark suite; finished runs are skipped, interrupted ones restart from zero.
# Usage: experiments/benchmark/scripts/train.sh <suite> [run-suite flags]
#   e.g. train.sh pilot --parallel 8 --max-ram-gb 16 --time-box-min 50
#        train.sh base --dry-run
# <suite> is base, templates, complex, ablation or pilot. The interpreter is the RM_RL_env one;
# set PYTHON to use another (default: ~/miniconda3/envs/RM_RL_env/bin/python).
set -euo pipefail

suite="${1:?usage: train.sh <suite> [run-suite flags]}"
shift
cd "$(dirname "$0")/../../.."
PYTHONPATH=app exec "${PYTHON:-$HOME/miniconda3/envs/RM_RL_env/bin/python}" app/main.py run-suite \
    --suite "experiments/benchmark/${suite}/runs.yaml" "$@"
