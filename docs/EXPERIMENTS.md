# Running experiments

How to take one environment from a description to a comparison of three agents:

- **No RM** (`sparse`): DQN on the environment's own reward.
- **Compiler RM** (`compiler`): DQN with a Reward Machine built by this repository's compiler.
- **Paper RM** (`paper`): DQN with a Reward Machine written by an LLM the way ARM-FM does it.

Every step names its command, what it reads and what it writes. Run everything from the repository root
inside the `RM_RL_env` Conda environment with `PYTHONPATH=app`.

```bash
conda activate RM_RL_env
export PYTHONPATH=app
```

## The pipeline at a glance

All the commands can be ran with the interface of `app/main.py` as

```

python app/main.py --<command> --<parameters>

```

| Step | Command | Reads | Writes |
| --- | --- | --- | --- |
| 1. Describe the environment | (you write it) | — | `examples/arm-fm/<env>/environment.md`, `tasks.md` |
| 2. Compiler bundle | `generate-larm --mode compiler` | `environment.md`, task text | `outputs/bundles/<Env>-<n>/` |
| 3. Paper bundle | `generate-larm --mode arm-fm` + `embed-larm` | `environment.md`, task text | `outputs/bundles/<Env>-paper-<n>/` |
| 4. Check the bundles | `render-rm`, a real-environment probe | bundle | SVGs, probe output |
| 5. Configs for the 3 agents | (you write them) | bundles | `configs/<env>/<wave>/{sparse,compiler,paper}.yaml` |
| 6. Train | `train-rl` | config | `outputs/runs/<exp_name>/seed<N>-<UTC>-<pid>/` |
| 7. Test on unseen maps | `test-rl` | run folder | `<run>/test.json`, `<run>/gifs/` |
| 8. Compare | `notebooks/rl_results.ipynb`, exported to HTML | run folders | plots, tables, GIFs, `outputs/reports/<name>.html` |

A bundle is one folder holding everything the RM agent needs: the Reward Machine
(`reward_machine.txt`), the labeling functions (`labeling.py`), one description per RM state
(`state_descriptions.json`), their embeddings (`embeddings.json`) and how it was made (`manifest.json`).
Bundles, runs and reports live under `outputs/` and are never committed.

## 0. One-time setup

- **LLM provider.** Copy `example.env` to `.env` and set `LLM_PROVIDER` plus that provider's key and

models. The compiler reads `<PROVIDER>_MODEL_GENERATOR` and `<PROVIDER>_MODEL_CRITIC` (falling back to
  `<PROVIDER>_MODEL`); `--model` on the command line wins over both. Project decision: generate with the
  small models only, `deepseek-v4.1-flash` as generator and `glm-5.3-flash` as critic.

- **Embedding server.** State descriptions are embedded by a local `llama-server` running a nomic

embedding model on `LLAMA_SERVER_PORT` (default 8934); `python app/app.py` prints the exact start command.
  Start it before any step that embeds.

- **MONA** must be on `PATH` (the compiler checks RMs with it).
- **New kind of environment only.** MiniGrid and BabyAI ids work as they are. An environment that is not

a registered Gymnasium id of a supported family needs an adapter in `app/src/arm_fm/custom_envs/`
  (static import; see `craftium_diamond.py` or `babyai_mission.py`). Everything else is plug-and-play.

## 1. Describe the environment

Create `examples/arm-fm/<env>/environment.md`. It is the only thing the generator LLMs know about the
environment, so it must say everything they need to write a correct Reward Machine and correct labeling code,
and nothing else. Leave out gym ids, URLs, provenance and implementation history: they cost tokens and give
the model nothing to use.

Required shape. Every command rejects a file without `## Propositions`; every command that generates
labeling or trains also rejects one without `## Labeling API`:

```markdown
# <Environment name>

## Environment

What the world looks like: rooms, objects and their colours, what is random in each episode and what is fixed,
what the agent sees, the actions and what each one does (including the ones that do nothing), what the agent
can carry, what blocks movement, the step limit.

## Objective and episode boundary

What counts as success for each task, how the environment detects it, when an episode terminates and when it
only truncates. Say plainly when the environment cannot judge a task (then RM acceptance counts as the
success: `success: rm` in the config; the RM's final and rejecting states end every RM run anyway).

## Proposition semantics

How each proposition is computed: from the live environment, once per step. Say which ones are conditions
(true while something holds) and which are one-step events (true only on the step something happens), what
"next to", "in a corner", "inside a room" mean exactly, and the edge cases (a carried object is not on the
grid, a door is not a wall, ...).

## Labeling API

The exact attributes and calls the labeling code may read, with types and meaning: positions, directions,
grid access, object attributes, inventory, counters, plus any hint on how to use them (for example how to scan
the grid safely). This section is the only thing the labeling generators know about the runtime: there is no
built-in default, not even for MiniGrid. Name nothing that does not exist on the real env.

## Propositions
- `snake_case_id`: One line: what is true when this proposition holds.
- `another_event`: Event: on this step ...

## Example tasks

- One task per line, in the words you will pass to the generators.
```

Rules that came from real failures:

- **Propositions are the vocabulary.** The RM can only talk about what is listed. If a task needs

"the box is in a corner", declare a proposition for it; the labeling code then computes it, even when the
  environment itself could never tell.

- **Events need the previous step.** Anything like "placed", "opened", "entered" must be defined against the

previous valuation, or it fires every step after the first time.

- **Say what identifies an object.** In KeyCorridor the first labeling matched the locked door by the mission

colour, which is wrong in most layouts; the door is found by its position. Describe the facts that pick out
  each object.

- **Write the tasks next to it.** `tasks.md` lists each task with a short id (`KC-1`, `BA-M2`) and its text;

`tasks.json` holds the same texts for scripted runs.

The best models to copy are `examples/arm-fm/babyai-chosen-mission/environment.md` (objects, events,
corners), `examples/arm-fm/minigrid-key-corridor/environment.md` (a standard MiniGrid `## Labeling API`) and
`examples/arm-fm/craftium-diamond/environment.md` (inventory and milestones).

## 2. Generate the compiler bundle (compiler RM + labeling + descriptions + embeddings)

```bash
python app/main.py generate-larm --mode compiler \
  --environment examples/arm-fm/<env>/environment.md \
  --task "<task text>" \
  --bundle outputs/bundles/<Env>-1 \
  --embeddings
```

One command does the whole compiler path: the LLM picks the clauses, the compiler builds the RM, one critic
checks the clauses against the task and the RM, then the state descriptions and the labeling functions are
generated and the descriptions are embedded. `--no-critic` turns the critic off (a warning says every result is
then accepted unchecked).

To look at a compiler RM alone, without a bundle, use `generate-rm` (it also draws SVGs):

```bash
python app/main.py generate-rm --environment examples/arm-fm/<env>/environment.md \
  --task "<task text>" --output <name> --svg
```

## 3. Generate the paper bundle (ARM-FM RM + descriptions + embeddings)

```bash
python app/main.py generate-larm --mode arm-fm \
  --environment examples/arm-fm/<env>/environment.md \
  --task "<task text>" \
  --bundle outputs/bundles/<Env>-paper-1 \
  --model deepseek-v4.1-flash
python app/main.py embed-larm --bundle outputs/bundles/<Env>-paper-1 --embedding-server
```

`--mode arm-fm` prints nothing while it works; wait for the bundle folder. The paper agent reuses the compiler
bundle's labeling (`labeling_bundle` in its config), so both RM agents see exactly the same propositions and
differ only in the Reward Machine.

## 4. Check the bundles before training

- **Draw the RMs:** `python app/main.py render-rm --rm-file outputs/bundles/<Env>-1/reward_machine.txt --svg-dir outputs/svgs/<Env>-1`

(same for the paper bundle). Read them: does every path to acceptance do the task, and only the task?

- **Probe the labeling in the real environment.** Play a few scripted or hand-picked action sequences and

print the propositions each step. A labeling critic can accept wrong code; a probe catches it in minutes.
  Do this before spending hours of training.

- **If generation fails:** check `.git/agent-memory/known-errors.md` (provider errors) and the trace under

`outputs/traces/`.

## 5. Choose the network and the observation

The DQN network is fixed per environment family; you choose it through `observation` in the config:

- `observation: symbolic` (MiniGrid/BabyAI default): the 7x7x3 symbolic view through a small CNN

(3 conv layers 16-32-64, kernel 2). Fast and the one all our results use.

- `observation: pixels`: 4 stacked 84x84 grayscale frames through the Nature DQN CNN. MiniGrid is rendered at
  8 px per tile and resized to 84x84 with OpenCV, as the authors do (`opencv-python-headless` is pinned).

With an RM, the RM state's embedding goes through a small MLP (d → d/4 → d/4) and is joined with the image
features; then one hidden layer of 512 and one output per action. Craftium uses PPO (`algorithm: ppo`) with
the same Nature CNN on 84x84 frames.

A new environment needs a new encoder only when its observation is neither of these. Add it in the adapter
(`make_encoder` in `RunEnvironment`); the training loops do not change.

## 6. Train, validation and test sets

All three are sets of reset seeds; the maps are generated from them.

| Set | Seeds | Used for |
| --- | --- | --- |
| Train | the run seed (`--seed N`); a procedural run seeds only its first reset | learning |
| Validation | `eval_seed_base + i`, default 1,000,000 + i | periodic and final evaluation inside `train-rl`, choosing settings |
| Test | 2,000,000 + i (`test-rl --seed-base`) | the final, unseen check; never used to pick settings |

`layout: procedural` gives a new map every episode (this is what "unseen scenarios" means). `layout: fixed`
replays one map (`layout_seed`) every episode; its test is the same map, so it only checks the learned route.

## 7. Write the three configs

One YAML per agent under `configs/<env>/<wave>/`. They differ only in the RM lines:

```yaml
# sparse.yaml
exp_name: <env>-sparse
gym_id: MiniGrid-KeyCorridorS6R3-v0
env_family: minigrid
observation: symbolic
layout: procedural
reward_source: env
total_timesteps: 1500000
learning_starts: 20000
eval_frequency: 25000
learning_rate: 1.0e-4
buffer_size: 1000000
gamma: 0.9
tau: 1.0
target_network_frequency: 2500
batch_size: 128
start_e: 1.0
end_e: 0.05
exploration_fraction: 0.2
train_frequency: 4
eval_episodes: 10
final_eval_episodes: 100
eval_epsilon: 0.0
success_threshold: 0.9
```

```yaml
# compiler.yaml: same as sparse, plus
exp_name: <env>-compiler
reward_source: rm          # the default; `both` adds the environment reward
bundle: outputs/bundles/<Env>-1
```

```yaml
# paper.yaml: same as sparse, plus
exp_name: <env>-paper
reward_source: rm          # the default; `both` reproduces the authors' env + RM sum
bundle: outputs/bundles/<Env>-paper-1
labeling_bundle: outputs/bundles/<Env>-1
```

Other keys you may need:

- `env_kwargs: {...}`: arguments for `gym.make` (for example a BabyAI mission).
- `success: rm`: RM acceptance counts as the success, for tasks the environment cannot judge. Every RM run ends
  its episode on the RM's declared final or rejecting state, on the environment's end, or at the time limit
  (-0.5 RM reward); `reward_source: rm | env | both` (default `rm`) picks the reward.
- `task_bundles:`: one agent trained on several tasks, one drawn per episode (see

`configs/babyai-chosen-mission/wave3/compiler-multi.yaml`).

- `algorithm: ppo` and `ppo_*` keys: PPO instead of DQN (see `configs/craftium-diamond/wave3/`).

Settings that worked on MiniGrid (wave 2): `gamma` 0.9 (0.99 left greedy policies stuck in no-op loops),
`batch_size` 128 (needed for the no-RM agent on procedural maps), `learning_starts` 20000, `end_e` 0.05.
Start there and tune per environment on validation only. Smoke test any new config first with a short
`total_timesteps` (20k-50k) to check that it runs.

## 8. Train

One process per run, three seeds per agent, all in parallel:

```bash
for agent in sparse compiler paper; do
  for seed in 1 2 3; do
    nohup python app/main.py train-rl --config <env>/<wave>/$agent.yaml --seed $seed \
      > outputs/runs/$agent-$seed.log 2>&1 &
  done
done
```

Each run writes `outputs/runs/<exp_name>/seed<N>-<UTC>-<pid>/`:

- `config.yaml`: every setting the run used.
- `episodes.csv`: one row per training episode (returns, length, exit, final RM state).
- `eval.csv`: one row per validation evaluation (exit rate, returns, RM acceptance).
- `train.csv`: losses and speed.
- `summary.json`: final validation result, steps to first success, run size and speed. A PPO run also lists
  `rm_states_visited`; for DQN read `final_rm_state` in `episodes.csv`.
- `q_network.pt` (DQN) or `agent.pt` (PPO): the final model.

Cost guide: a 1.5M-step MiniGrid RM run takes about an hour with 6 runs side by side on the RTX 5070 and up to
8 GB of RAM; a Craftium PPO run takes about 15 h per 10M steps and 9-13 GB of RAM.

## 9. Test on unseen maps

```bash
python app/main.py test-rl --run <exp_name> --episodes 100 --seed-base 2000000 --gifs 5
```

`--run` takes one run folder or an `exp_name` (every finished run under it). It rebuilds each run from its
`config.yaml` and final model, plays episode i on test seed 2,000,000 + i (DQN greedy, PPO sampling its policy)
and writes into each run folder:

- `test.json`: exit rate, returns, RM acceptance, the seeds, and one row per task for multi-task runs.
- `gifs/<i>.gif`: the first N test episodes, captioned with environment, agent, task, map seed, step, RM state

and solved or failed. A multi-task run cycles its tasks, so use N at least the number of tasks.

It runs on CPU and never changes the training files. A Craftium test is slow (minutes per episode): use
`--episodes 2 --gifs 1` for a quick look.

## 10. Compare the three agents

Open `notebooks/rl_results.ipynb`, set `EXP_NAMES` in the PARAMETERS cell to the `exp_name`s of one
environment (`None` loads every run), and run it. It groups the runs by environment and agent (`sparse`, `compiler`, `paper`) and shows:

- a training curve of the environment return (rolling mean over episodes, mean over seeds); the RM return is
  in `episodes.csv` but not plotted;
- validation curves (exit rate over steps);
- a table per environment: agent × seeds, with final validation exit rate, test exit rate, steps to first

success and RM states reached, plus mean ± std;

- the GIFs of each agent (`GIFS_PER_RUN` per run, default 2).

The agent is read from each run: `sparse` when `reward_source` is `env`, otherwise `compiler` or `paper` from the
bundle's `manifest.json`. Runs without a `test.json` show an empty test column.

The results page is the same notebook exported to a single HTML file:

```bash
jupyter nbconvert --to html --no-input --execute --ExecutePreprocessor.kernel_name=python3 \
  notebooks/rl_results.ipynb --output-dir outputs/reports --output <env>-<wave>
```

Set `EXP_NAMES` first and put it back to `None` afterwards. Open `outputs/reports/<env>-<wave>.html` in a
browser: the charts are interactive and the GIFs are embedded, so the single file (5-7 MB) can be shared.

## 11. Paper reproduction (ARM-FM Fig 6 and 7)

Goal: check, setting by setting, whether our pipeline reproduces the paper's DQN results. The settings are
DoorKey 5x5, 6x6, 8x8 and 16x16 (each with a fixed and a random layout), UnlockToUnlock, BlockedUnlockPickup and
KeyCorridor S6R3, at 300k steps and seeds 1, 2 and 3. Each setting has three agents:

- `sparse`: plain DQN.
- `authors`: our trainer on the authors' released Reward Machine, labeling, state descriptions and embeddings.
  It tests the trainer alone.
- `ours`: a bundle generated by our pipeline with the paper prompt profile (see "Generate the `ours` bundles"
  below), embedded with `nomic-embed-text`.

**Clone the authors' repository once.** The repository has no licence, so nothing from it is committed here;
the commands read the clone and write only under `outputs/`. The work used commit `9a38c4a`. Never run its code.

```bash
git clone https://github.com/roger-creus/llms-rm-rl ~/src/llms-rm-rl
```

**Import the released bundles**, one per environment (all DoorKey sizes share one):

```bash
for env in DoorKey UnlockToUnlock BlockedUnlockPickup KeyCorridorS6R3; do
  python app/main.py import-paper-bundle --reference ~/src/llms-rm-rl --env $env \
    --output outputs/bundles/paper-authors-$env
done
```

Each bundle holds `reward_machine.txt` (events are the guard names), `labeling.py` (the authors' file as is),
`state_descriptions.json`, `embeddings.json` (their 1536-d `u*.npy`) and a manifest with
`provenance.generator: authors-released @ <commit>`. The released RM names no final state, and the importer keeps
it that way: the states that cannot be left are recorded only as our inference in
`generation.final_states_inferred`, because only declared finals end an episode and an inferred final can come
before the environment goal (UnlockToUnlock, KeyCorridorS6R3). The `ours` bundles go to `outputs/bundles/paper-ours-<Env>`.

**Generate the `ours` bundles**, one per environment (all DoorKey sizes share one). The paper profile reads the
authors' prompts from the clone at run time, as named by `examples/arm-fm/<env>/paper-sources.json`, and runs the
authors' loop: a generator and a critic talk for at most 3 rounds (the critic ends with "NO CHANGES NEEDED" or
"CHANGES REQUIRED"), first for the Reward Machine, then for the labeling functions. The generator names the events
itself, and the state descriptions use our own prompt because the authors' is unreleased. The generator is
`OPENCODE_MODEL_GENERATOR` (`deepseek-v4.1-flash`) and the critic `OPENCODE_MODEL_CRITIC` (`glm-5.3-flash`); only the
clone at commit `9a38c4a` is accepted.

```bash
for pair in minigrid-doorkey:DoorKey babyai-unlock-to-unlock:UnlockToUnlock \
            minigrid-blocked-unlock-pickup:BlockedUnlockPickup minigrid-key-corridor:KeyCorridorS6R3; do
  dir=${pair%%:*}; env=${pair##*:}
  python app/main.py generate-larm --mode paper --reference ~/src/llms-rm-rl \
    --paper-sources examples/arm-fm/$dir/paper-sources.json --bundle outputs/bundles/paper-ours-$env
  python app/main.py embed-larm --bundle outputs/bundles/paper-ours-$env --embedding-server
done
```

Each command makes 3 independent draws (`--draws`), saves them as `paper-ours-<Env>-draw1` to `-draw3` and copies the
first draw that passes the gates to `paper-ours-<Env>`. The gates: the RM parses, it has at least one event and does not start in a final state, the labeling loads for
the RM's events, and a scripted player (a planner that reads the grid and acts only through `env.step`) solves
every gating layout, with the RM ending in a final state and every event firing at least once. The gating layouts are
set per environment in `paper-sources.json` (`probe`): DoorKey and BlockedUnlockPickup use seeds 1-3 and three
held-out seeds; UnlockToUnlock and KeyCorridor gate on seed 1, the layout the runs use, and only report the others. A
final state is one with no exit except an `else` self-loop, which is our inference; the authors' RM text names none.
Where the last RM stage is the env's own success (DoorKey, BlockedUnlockPickup, UnlockToUnlock), `probe.max_final_lag`
is 3 and a draw fails when its final state is entered more than 3 steps before the env ends the episode (a misplaced
trigger); KeyCorridor sets none, because the authors' own RM ends before the ball is taken, so it only warns. The gates also
warn about colour names and integer literals in the labeling, which tie it to one layout. If no draw passes, the command fails and the draw folders stay for
inspection; run it again with `--overwrite` for one more set. The embedding server must run first (section 0).
The manifest records the models, the clone commit, the sources file, a hash of every prompt, every round and the
gate results. The state descriptions, the transcript framing of the conversation and the critic's candidate slot are
our reconstruction; for KeyCorridor the whole prompt is, because the authors released none.

**Configs** are `configs/paper-repro/<setting>/<agent>.yaml`, with the settings `doorkey-{5x5,6x6,8x8,16x16}-{fixed,random}`,
`unlock-to-unlock`, `blocked-unlock-pickup` and `key-corridor-s6r3`. They use pixels and ARM-FM Table 5;
`buffer_size` is 300000, the budget, which behaves like 1e6. A fixed layout is the run seed's map, except
UnlockToUnlock and KeyCorridor, which use `layout_seed: 1` because the released labeling hard-codes the colours of
that map. A random layout is `layout: procedural` with `eval_episodes: 3`, and DoorKey 16x16 random evaluates every
50k steps because a failing greedy episode lasts 2560 steps.

**Diagnostic runs.** `doorkey-5x5-fixed/authors-ls1k.yaml` and `sparse-ls1k.yaml` set `learning_starts: 1000`
instead of Table 5's 80,000. The paper's curves rise before step 80,000, so these show whether the figure's shape
appears when learning starts early. Run them for seeds 1-3; the notebook draws them but never judges them.

**Run order.** DoorKey 5x5 fixed (3 agents × 3 seeds), then 5x5 random. After a review of those results: 6x6 and 8x8
(fixed, random), UnlockToUnlock, BlockedUnlockPickup, KeyCorridor S6R3, and last 16x16. For each setting run seed 1
for every agent first, then seeds 2 and 3.

**RAM and pairing.** The replay buffer costs 56,478 bytes per step without an RM, 62.6 KB with a 768-d RM state and
68,771 bytes with the authors' 1536-d one (measured from the RSS slope between 20k and 40k steps). Projected RSS at 300k
steps, with the 1.9 GB base: about 18.8 GB for `sparse`, 20.6 GB for `ours` and 22.5 GB for `authors`. Run two at a
time on the 60 GB machine, **never two `authors` runs together**: pair an `authors` run with a `sparse` or `ours` run.

**Early kill.** A run may stop at 150k steps with no success in its last 50k only when the `authors` run of that
setting and seed already succeeds there, and never for `sparse`. Count the successes from `exited`:

```bash
python -c "import pandas as pd; e = pd.read_csv('<run folder>/episodes.csv'); print(e[e.global_step > e.global_step.max() - 50000].exited.sum())"
```

```bash
python app/main.py train-rl --config paper-repro/doorkey-5x5-fixed/authors.yaml --seed 1
python app/main.py test-rl --run paper-doorkey-5x5-fixed-authors --episodes 100
```

Runs land in `outputs/runs/paper-<setting>-<agent>/seed<N>-<UTC>-<pid>/`; `test-rl` adds `test.json` to each.

**Read the result** in the `PAPER COMPARISON` section of `notebooks/rl_results.ipynb`. It maps every run to a setting
(`gym_id` and `layout`) and an agent (`reward_source` and the bundle provenance), then compares it with
`examples/arm-fm/paper-dqn-targets.json`, the paper's values read by eye from the figures. Its first cell states the
rule: the outcome (`solved`, `partial`, `failed`) must match the paper's; the speed is the ratio of the RM crossing to the
`sparse` crossing, not absolute steps, because the paper's curves rise before Table 5's learning start; the greedy test
length is judged only where the paper solves. It lists every seed and gives one verdict per setting and agent
(`reproduced`, `outcome only`, `inconclusive`, `pending test` or `not reproduced`). Export the page as in section 10.
Settings without runs are skipped.

Known differences from the authors' code. Their RM chains every triggered event in one step; ours does one transition
per step. The released KeyCorridor and UnlockToUnlock labeling work only on layout seed 1 of our MiniGrid version.
The KeyCorridorS6R3 trace quotes the DoorKey mission, so that bundle's `task` text is the DoorKey one. The released
UnlockToUnlock RM sets `entered_goal_room` to `x < 5`, which fires before the ball is picked up on that layout, so its
+1.0 `got_ball` reward is not paid.

## Checklist for one environment

1. `environment.md` with all six sections, `tasks.md`, `tasks.json`.
2. Compiler bundle and paper bundle, both drawn and probed.
3. Three configs; a short smoke run of each.
4. Full runs: 3 agents × 3 seeds.
5. `test-rl` on all of them.
6. Notebook and HTML report.

## Where to look when something is off

| Question | Look at |
| --- | --- |
| What did the generator see and answer? | `outputs/traces/`, `outputs/bundles/<B>/raw_responses.json`, `attempts.json` |
| Which RM and propositions does a bundle use? | `outputs/bundles/<B>/reward_machine.txt`, `labeling.py`, `manifest.json` |
| Did the RM ever move during training? | `episodes.csv` (`final_rm_state`, `rm_return`); PPO also `summary.json` (`rm_states_visited`) |
| Is the agent learning? | `eval.csv` and the notebook's validation curves |
| Does it generalise? | `test.json` and the test column of the notebook table |
| Known setup or provider errors | `.git/agent-memory/known-errors.md`, `.agents/known-errors.md` |
