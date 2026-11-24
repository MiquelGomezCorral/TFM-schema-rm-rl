# Lanes spacing suite

Eight side-test cards (4 cards x 2 worlds) on `MiniGrid-Lanes-v0` with the lanes closer together. They are not in the counted 60 (`train: false`; a runs file picks them with `only:`).

## The world option

`LanesEnv(lane_spacing=k)` (`app/src/arm_fm/forcing_envs.py`) is the row distance between neighbouring lanes. The width stays 11; the field is `2k + 1` rows tall. The default is 4, the counted world, and stays byte-identical to the code before the option. The option takes 1 to 4. Cards pass it through `env.env_kwargs: {"lane_spacing": k}`.

| `lane_spacing` | Grid (w x h) | Lane rows | Free rows between lanes | Agent start | Zombie entry |
|---|---|---|---|---|---|
| 4 (default) | 11 x 11 | 1, 5, 9 | 3 | (5, 5) facing left | right end of each lane (x = 9), about 29 per 300-step episode, the rate rising |
| 2 | 11 x 7 | 1, 3, 5 | 1 | (5, 3) facing left | same |
| 1 | 11 x 5 | 1, 2, 3 | 0 (lanes touch) | (5, 2) facing left | same |

The agent starts on the middle lane at every spacing. The zombie schedule, the walking rhythm (a cell every 3 steps, 27 steps to cross), the four events (`top_breach`, `side_breach`, `plant_trampled`, `zombie_killed`) and the idle breach steps are those of the default world. Only the geometry changes, so the scripted guard needs a shorter walk between lanes. At spacing 1 no cell is free off the lanes, so no plant ever sprouts and the plant rule cannot break.

## The cards

Each card copies a counted Lanes card (same task text, clauses, plans, `event_seeds`; no paraphrases) and sets `bundle_of: <suite>/<card-id>`. `run-suite` trains it on the borrowed machine and `generate-suite` skips it. This is valid because the Lanes labeling reads only `env.events_this_step`, so the machine is correct in any geometry.

| Card id (`-spacing2`, `-spacing1`) | Copy of | Task |
|---|---|---|
| `lanes-guard-spacing<k>` | `forcing/lanes-guard` | Never let a zombie through the top lane (hard). |
| `lanes-rules-spacing<k>` | `forcing/lanes-rules` | The same, then try not to let zombies through the other lanes and not to step on plants (soft). |
| `tpl-absence-soft-1-nogoal-spacing<k>` | `templates/tpl-absence-soft-1-nogoal` | Try not to let zombies through any lane (two soft Absence clauses, no goal). |
| `tpl-existence-two-5-nogoal-spacing<k>` | `templates/tpl-existence-two-5-nogoal` | Kill at least two zombies (hard ExistenceTwo, no goal). |

At most 4 cards per world: the two forcing cards (a hard top-lane rule, and a hard rule with two soft ones, the card where side lanes matter) and two template cards that borrowed FARM machines passed every FARM gate in both worlds. The other trained Lanes cards (`tpl-existence-two-soft-1-nogoal`, `tpl-precedence-soft-1-nogoal`) pass the same gates but were left out for the limit; `tpl-not-co-existence-soft-1-nogoal` fails the `plan_trace` gate in both worlds and does not train. Only `tpl-existence-two-5-nogoal` has an ARM-FM Lanes bundle that passes the ARM-FM gate.

The Lanes environment pages (`../envs/minigrid-lanes/`) are not edited: each bundle stores them in its manifest and `precheck.py` compares them. The option is documented here and in `forcing_envs.py`.

## FARM with the world reward added (`runs-farm-both.yaml`)

`runs-farm.yaml` trains on the machine's reward alone and `runs-no-rm.yaml` on the world's alone (+1 per zombie killed). `runs-farm-both.yaml` asks for both at once (user, 2026-11-23): FARM on `lanes-guard` and `lanes-rules` at spacing 4, 2 and 1, 3 seeds each, 18 runs. The one setting that differs from `runs-farm.yaml` is `reward_source: both`, which adds the world's reward to the machine's; learner, config, timesteps, seeds and bundles are the same. Spacing 4 uses the counted cards of the `forcing` suite and the other two spacings the copies above, all on the frozen `forcing` bundles. The suite is named `lanes-both` so no run folder or lock meets `lanes-spacing` or `forcing`.
