#!/usr/bin/env bash
# Lane D of the PPO diagnostic: seeds 3 and 21 of the exploration variants on the s07 base.
# Starts when lane B is done and the seed 1 and 2 runs of lane C have begun.
cd "$(dirname "$0")/../.."
while pgrep -f "outputs/ppo-diagnostic/lane-b.sh" >/dev/null; do sleep 30; done
until ls -d outputs/runs/bench__ppo-diag-s07x__* >/dev/null 2>&1; do sleep 30; done
experiments/benchmark/scripts/train.sh tuning/ppo-diagnostic/s07x-p2 --parallel 2 --max-ram-gb 7.5
