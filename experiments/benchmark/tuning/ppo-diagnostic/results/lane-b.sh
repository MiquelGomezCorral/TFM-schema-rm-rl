#!/usr/bin/env bash
# Lane B of the PPO diagnostic: the exploration variants, DoorKey without the Reward Machine, then
# seed 4 of the main runs. Two runs at once; seeds 1 and 2 first, seed 4 last (cut it first if
# time runs out).
cd "$(dirname "$0")/../.."
experiments/benchmark/scripts/train.sh tuning/ppo-diagnostic/explore-p1 --parallel 2 --max-ram-gb 7.5
experiments/benchmark/scripts/train.sh tuning/ppo-diagnostic/doorkey --parallel 2 --max-ram-gb 7.5
experiments/benchmark/scripts/train.sh tuning/ppo-diagnostic/explore-p2 --parallel 2 --max-ram-gb 7.5
experiments/benchmark/scripts/train.sh tuning/ppo-diagnostic/explore-p3 --parallel 2 --max-ram-gb 7.5
experiments/benchmark/scripts/train.sh tuning/ppo-diagnostic/main-p3 --parallel 2 --max-ram-gb 7.5
