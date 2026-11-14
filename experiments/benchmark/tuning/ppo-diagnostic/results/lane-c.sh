#!/usr/bin/env bash
# Lane C of the PPO diagnostic: the exploration variants on the s07 base (coordinator's extra).
# Starts when lane A is done, so no more than four runs train at once. Seeds 1 and 2 first,
# seed 4 last (cut it first if time runs out).
cd "$(dirname "$0")/../.."
while pgrep -f "outputs/ppo-diagnostic/lane-a.sh" >/dev/null; do sleep 30; done
experiments/benchmark/scripts/train.sh tuning/ppo-diagnostic/s07x-p1 --parallel 2 --max-ram-gb 7.5
experiments/benchmark/scripts/train.sh tuning/ppo-diagnostic/s07x-p3 --parallel 2 --max-ram-gb 7.5
