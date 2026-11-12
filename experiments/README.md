# Experiments

Two areas, kept apart so development material never mixes with the thesis benchmark.

## `dev/`

Everything that used to live in `examples/`, moved, with the paths inside updated:

- `arm-fm/<env>/`: the environment catalogue (`environment.md`, `environment-code.md`, task lists,
  the paper's reward machines where published). Start with `arm-fm/README.md`.
- `multitaxi/`: the MultiTaxi environment description.
- `benchmark/`: the earlier held-out set of template tasks, used to check which clauses the compiler
  picks. It is not the thesis benchmark below.

## `benchmark/`

The thesis benchmark. Three arms get the same inputs and train on the same environments:

- **no RM:** the environment's own reward.
- **ARM-FM:** a fresh machine generated with our small models, trained on the RM reward only.
- **FARM:** the machine our compiler produces today, trained on the RM reward only.

Each suite is a folder of task cards (`tasks.json`) with the machines and traces made from them:

| Suite | What it holds |
| --- | --- |
| `base/` | The base paper's four MiniGrid tasks. |
| `templates/` | The eight DECLARE templates, with and without a goal. |
| `complex/` | Longer tasks, rule-only tasks, several rules, and rules that react to events. |

The supporting files sit beside the suites: `envs/` (the environment files the cards point to),
`configs/` (learner settings), `scripts/` (`generate.sh`, `train.sh`, `evaluate.sh`), `smoke/` and
`pilot/` (small test sets), `ablation/` (the ablation run settings and machines), and `REPRODUCE.md`,
which says how to rerun everything.

## What goes into Git

| Committed | Not committed |
| --- | --- |
| Reward machine bundles | Logs |
| Task cards and the closed-set list | Checkpoints and models |
| Trace records of the scripted plans | Run folders (`outputs/runs/`) |
| Result summaries (CSV and JSON) | Plotly HTML and GIFs |

Bundles are small text files, so each machine stays next to the code that made it. The heavy output of
training and evaluation goes under `outputs/`, which Git ignores.
