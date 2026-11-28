# Train an agent

Back to the [main page](../README.md).

`train-rl` trains one DQN agent, with or without an RM. Each run is one YAML file under
`configs/`, and the seed is given on the command line:

```bash
python app/main.py train-rl --config minigrid-unlock-pickup/rm-task1-symbolic.yaml --seed 1
```

Run it from the root of the repository. The full experiment, from the environment description
to the comparison of methods, is in [docs/EXPERIMENTS.md](../docs/EXPERIMENTS.md).

## What the agent is rewarded with

The `reward_source` field of the config decides it:

| Value | Reward |
| --- | --- |
| `rm` (default) | Only the reward of the RM |
| `both` | The reward of the environment plus the reward of the RM |
| `env` | Only the reward of the environment, with no RM |

With an RM, each step runs the labelling functions, moves the RM once, and feeds the agent's
network the embedding of the current RM state.

## What a run with an RM needs

A **bundle**: a folder with the RM, its labelling functions and its state embeddings. Bundles
live under `outputs/bundles/` and the config points to one with `bundle`. `labeling_bundle` can
take the labelling functions from another bundle that has the same propositions.

## The configs

`configs/minigrid-unlock-pickup/` is a good place to start:

- **Smoke runs** (`smoke-*.yaml`): 20,000 steps, to check that everything works.
- **Full runs** (`sparse-symbolic`, `rm-task1-symbolic`, `rm-task4-symbolic`): 300,000 steps.

`layout: fixed` uses the same map in every episode. `layout: procedural` tests on maps the
agent has not seen.

## What a run writes

A folder `outputs/runs/<name>/seed<seed>-<time>-<pid>/` with the config, the training and
evaluation tables (`train.csv`, `episodes.csv`, `eval.csv`), `summary.json` and the trained
network `q_network.pt`. To compare seeds or configs, start several runs side by side.

## Which environments

`train-rl` works with registered MiniGrid environments. Another family of environments needs
its own adapter.
