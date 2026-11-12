#!/usr/bin/env bash
# Judge every finished run of a suite that has no judge.json, then aggregate the suite.
# Usage: experiments/benchmark/scripts/evaluate.sh <suite> [--dry-run]
# --dry-run prints the commands instead of running them. Results: outputs/results/<suite>/.
# A failed judge is logged and the loop goes on; the suite is still aggregated, then the script
# exits 1. The interpreter is the RM_RL_env one; set PYTHON to use another
# (default: ~/miniconda3/envs/RM_RL_env/bin/python).
set -euo pipefail

suite="${1:?usage: evaluate.sh <suite> [--dry-run]}"
dry_run="${2:-}"
cd "$(dirname "$0")/../../.."
python_bin="${PYTHON:-$HOME/miniconda3/envs/RM_RL_env/bin/python}"
export PYTHONPATH=app
judge_failures=0

run() {
    if [[ "$dry_run" == "--dry-run" ]]; then
        echo "$@"
    else
        "$@"
    fi
}

for summary in outputs/runs/bench__"${suite}"__*/seed*/summary.json; do
    [[ -f "$summary" ]] || continue
    folder="$(dirname "$summary")"
    [[ -f "$folder/judge.json" ]] && continue
    if ! run "$python_bin" app/main.py test-rl --run "$folder" --judge "$(dirname "$folder")/card.json"; then
        echo "judge failed: $folder" >&2
        judge_failures=$((judge_failures + 1))
    fi
done

run "$python_bin" app/main.py aggregate-suite \
    --suite "experiments/benchmark/${suite}/runs.yaml" --output "outputs/results/${suite}"

if ((judge_failures > 0)); then
    echo "$judge_failures judge call(s) failed" >&2
    exit 1
fi
