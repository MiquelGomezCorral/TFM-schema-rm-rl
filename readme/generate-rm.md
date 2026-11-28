# Generate a Reward Machine

Back to the [main page](../README.md).

```bash
python app/main.py generate-rm \
  --environment experiments/benchmark/envs/minigrid-doorkey/environment.md \
  --task "Reach the goal, ideally without ever losing the key." \
  --step-limit 640 \
  --output careful-key.rm
```

Run it from the root of the repository, with a provider set in `.env`
([engines](../app/src/engines/README.md)).

## What you give it

| Option | Meaning |
| --- | --- |
| `--environment` | The environment description ([how to write one](environment-files.md)) |
| `--task` | The task in plain language. Repeat it to build one RM per task |
| `--output` | A file name, not a path. Files go to `outputs/` |
| `--step-limit` | How many steps an episode lasts. `--gym-id` reads it from a registered environment instead |

A task can hold several requirements. The generator splits them into clauses, each with a hard
or soft priority. A clause is soft only when the task words it as a preference, with "if
possible", "preferably", "ideally" and the like.

## What you get

- **One RM per task.** With several tasks the files are numbered: `name-1.rm`, `name-2.rm`.
  Tasks are never joined into one RM.
- **Nothing, if a task fails.** No file is written unless every task is accepted.
- **A log.** Each run writes `logs/run-<time>.log` with the clauses, the verdict of the critic,
  the formulas, the automata and the RM. Keys, prompts and raw answers are not written.
- **A drawing**, with `--svg`: one SVG per RM in `outputs/svgs/` (or `--svg-dir`).

An existing file is never replaced unless you add `--overwrite`.

## Options you may want

| Option | Default | What it does |
| --- | --- | --- |
| `--attempts N` | 3 | How many RMs the generator may propose per task, from 1 to 10 |
| `--no-critic` | critic on | Accepts the first RM without review |
| `--reasoning` | `max` | Thinking level of both models: `none`, `low`, `medium`, `high` or `max` |
| `--model` | from `.env` | The model of the generator |
| `--no-recurrent-soft-penalty` | on | Penalises a broken soft rule once per episode, not at every new break |
| `--soft-break-cost` | 1.0 | What one soft break costs |
| `--no-hard-ceiling` | on | Keeps a flat penalty for breaking a hard rule. Then no step limit is needed |
| `--no-state-descriptions` | on | Skips the text that describes each RM state |
| `--labeling` | off | Also writes the MiniGrid labelling functions |
| `--embeddings` | off | Also embeds the state descriptions ([local server needed](embeddings.md)) |

`python app/main.py generate-rm --help` lists all of them.

## The RM file

```text
REWARD_MACHINE:
STATES: u0, u1
INITIAL_STATE: u0
FINAL_STATES: u1
DEFAULT_REWARD: 0
TRANSITION_FUNCTION:
(u0, !at_goal&key_lost) -> u0
(u0, at_goal&!key_lost) -> u1
(u0, at_goal&key_lost) -> u1
REWARD_FUNCTION:
(u0, !at_goal&key_lost, u0) -> -1
(u0, at_goal&!key_lost, u1) -> 11
(u0, at_goal&key_lost, u1) -> 10
```

- `TRANSITION_FUNCTION` lists the transitions. A case that is not listed keeps the RM in the
  same state with reward 0.
- `REWARD_FUNCTION` lists only the rewards that are not 0.
- The format is the one ARM-FM uses, so both methods write the same kind of file.

How the rewards are chosen is in [docs/COMPILER_REWARD_DESIGN.md](../docs/COMPILER_REWARD_DESIGN.md)
and in Chapter 3 of the thesis.
