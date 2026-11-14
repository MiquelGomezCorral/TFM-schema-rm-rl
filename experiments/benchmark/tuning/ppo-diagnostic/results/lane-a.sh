#!/usr/bin/env bash
# Lane A of the PPO diagnostic: the s07 / s07-tuned runs with and without the Reward Machine.
# Two runs at once; seeds 1 and 2 first, then 3 and 21.
cd "$(dirname "$0")/../.."
experiments/benchmark/scripts/train.sh tuning/ppo-diagnostic/main-p1 --parallel 2 --max-ram-gb 7.5
experiments/benchmark/scripts/train.sh tuning/ppo-diagnostic/main-p2 --parallel 2 --max-ram-gb 7.5
