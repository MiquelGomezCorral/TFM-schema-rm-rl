#!/usr/bin/env bash
# One SLURM job of cluster_runs.py (runs on tensor): check out the pinned commit, then train every
# runs file in <job dir>/runs/ with its own run-suite driver, all at once. The runner packed at
# most <slots> runs into the job and one runs file per suite name (run-suite locks per suite).
# Usage (sbatch): job.sh <job dir> <commit> <slots>
set -euo pipefail

job_dir="$(realpath "$1")"  # run-suite runs from the clone, so the runs files need full paths
commit="$2"
slots="$3"
repo="$job_dir/repo"

# A resubmitted job keeps its clone: run-suite skips the finished runs and restarts the others.
# The clone is built under another name and renamed when complete, so a half clone is never reused.
if [ ! -d "$repo" ]; then
    rm -rf "$repo.part"
    git clone --quiet --shared --no-checkout "$HOME/tfm/repo" "$repo.part"
    git -C "$repo.part" checkout --quiet --detach "$commit"
    mv "$repo.part" "$repo"
fi

export PATH="$HOME/tfm/venv/bin:$PATH"
export PYTHONPATH=app
echo "job ${SLURM_JOB_ID:-} on $(hostname), CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-}"
nvidia-smi --query-gpu=index,name,memory.used,utilization.gpu --format=csv

pids=()
for runs in "$job_dir"/runs/*.yaml; do
    log="$job_dir/$(basename "$runs" .yaml).log"
    env -C "$repo" python app/main.py run-suite --suite "$runs" --parallel "$slots" > "$log" 2>&1 &
    pids+=("$!")
done

status=0
for pid in "${pids[@]}"; do
    wait "$pid" || status=1
done
# run-suite plans a run whose bundle is no-data or pending, never queues it, and still exits 0.
if grep -E '^(no-data|pending) ' "$job_dir"/*.log; then
    echo "error: the runs above were not trained (bundle no-data or pending at $commit)"
    status=1
fi
exit "$status"
