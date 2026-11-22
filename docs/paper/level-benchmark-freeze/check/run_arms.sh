#!/bin/bash
# One LLM-loop round. Usage: run_arms.sh ROUND CASES [ARMS] [REPS] [PARALLEL] [REASONING] [--labeling]
# Runs from worktree E with the credentials loaded by dotenv (never printed); log in runs/ROUND/round.log.
HERE=/home/turbotowerlnx/Documents/Master/TFM/TFM-schema-rm-rl/.git/agent-memory/plans/farm-final-20261119/until-fix
# until-fix: main's checkout unless the caller names a worktree (env CC_ROOT=<worktree> run_arms.sh ...).
export CC_ROOT=${CC_ROOT:-/home/turbotowerlnx/Documents/Master/TFM/TFM-schema-rm-rl}
mkdir -p "$HERE/runs/$1"
echo "cc_root=$CC_ROOT" >> "$HERE/runs/$1/round.log"
echo "start $(TZ=Europe/Madrid date +%H:%M:%S) cases=$2 arms=${3:-A,B,C,D} reasoning=${6:-none}" >> "$HERE/runs/$1/round.log"
/home/turbotowerlnx/miniconda3/envs/RM_RL_env/bin/dotenv -f /home/turbotowerlnx/Documents/Master/TFM/TFM-schema-rm-rl/.env run --no-override -- \
  /home/turbotowerlnx/miniconda3/envs/RM_RL_env/bin/python "$HERE/tools/run_arms.py" --round "$1" --cases "$2" \
  --arms "${3:-A,B,C,D}" --reps "${4:-1}" --parallel "${5:-8}" --reasoning "${6:-none}" "${@:7}" >> "$HERE/runs/$1/round.log" 2>&1
echo "done $(TZ=Europe/Madrid date +%H:%M:%S)" >> "$HERE/runs/$1/round.log"
