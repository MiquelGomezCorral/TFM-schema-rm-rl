# Lanes plant world (user, 2026-11-24)

The Lanes cards `lanes-guard` and `lanes-rules` in a new world, at lane spacing 4, 3 and 2. Every run uses these
`LanesEnv` options (`app/src/arm_fm/forcing_envs.py`, class docstring; all default to the world every stored card, bundle
and run used):

- `fixed_plants`: at each reset `3 * (lane_spacing - 1)` plants (9, 6, 3) on random free cells off the lanes, drawn from the
  episode seed; none sprouts; a trampled plant stays dead; a plant-free route joins the lanes.
- `end_on_top_breach`: the step with a `top_breach` event returns `terminated=True`.
- `plant_stun_steps: 2`: after the agent steps onto a plant its next 2 steps change neither its cell nor its facing,
  whatever the action. The agent's observation does not show the stun.
- `kill_reward` (default 1) and `breach_reward` (default 0): the env reward is
  `kill_reward * kills + breach_reward * breaches` (top and side).

The env Markdown (`experiments/benchmark/envs/minigrid-lanes/environment.md`, `environment-code.md`) is not edited, as the
lanes-spacing README says for the spacing option: the options are documented in the docstring and here.

## Groups and runs

7 groups x 3 seeds x 3 spacings = 63 trainings with `end_on_top_breach`, plus 27 no-RM trainings without it (the
`-noend` variant, user 2026-11-24: "try it both ways"): 90 trainings, 1.5M steps, PPO, the settings of `lanes-spacing`.
The cards are copies of the counted forcing cards (`tasks*.json` here; ids `lanes-guard-plants-spacing4` and
`lanes-guard-plants-noend-spacing4` and so on, `train: false`, `only` in the yamls), written by `make_cards.py` in the
evidence folder below.

FARM has no `-noend` runs: its machine's rejecting state ends the episode at the first top breach whatever
`end_on_top_breach` says (`terminate_on_rm`), so a `-noend` FARM run would train the same episodes as its twin
(review 2026-11-24: identical on 480 end/noend pairs). The FARM runs below serve both variants.

| Yaml | Suite | Group | Trainings |
|------|-------|-------|-----------|
| `runs-farm.yaml` | `lanes-plants` | FARM guard, FARM rules (`bundle_of` the counted FARM machines) | 18 |
| `runs-farm-both.yaml` | `lanes-plants-both` | FARM + kill reward (`reward_source: both`), guard and rules | 18 |
| `runs-no-rm-kill.yaml` | `lanes-plants-no-rm-kill` | no RM, env reward +1 per kill | 9 (18 rows, the rules card is judged on the guard run) |
| `runs-no-rm-penalty.yaml` | `lanes-plants-no-rm-penalty` | no RM, `kill_reward 0`, `breach_reward -1` (`tasks-penalty.json`) | 9 |
| `runs-no-rm-kill-penalty.yaml` | `lanes-plants-no-rm-kill-penalty` | no RM, `kill_reward 1`, `breach_reward -1` (`tasks-kill-penalty.json`) | 9 |
| `runs-no-rm-kill-noend.yaml` | `lanes-plants-no-rm-kill-noend` | as `runs-no-rm-kill.yaml`, play goes on after a top breach (`tasks-noend.json`) | 9 |
| `runs-no-rm-penalty-noend.yaml` | `lanes-plants-no-rm-penalty-noend` | as `runs-no-rm-penalty.yaml`, play goes on (`tasks-penalty-noend.json`) | 9 |
| `runs-no-rm-kill-penalty-noend.yaml` | `lanes-plants-no-rm-kill-penalty-noend` | as `runs-no-rm-kill-penalty.yaml`, play goes on (`tasks-kill-penalty-noend.json`) | 9 |

`exit_rate` in `eval.csv` (`terminated and env_reward > 0`) is not a success measure here: a top breach that also kills
counts as an exit. Read `judge.json`, or the `events_top_breach` column.

The checks, their scripts and evidence are in
`.git/agent-memory/plans/farm-final-20261119/shop-grid-20261124/lanes-penalty/`.
