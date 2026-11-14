# Forced-start suite

Two cards of the templates suite whose rule can pass untested, with an environment that starts the
episode with the rule's trigger already true. On the originals, trained agents never reach the
trigger (seed 1: no-RM judged success 1.00, non-empty 0.00 on both), so doing nothing passes the
rule. Here the environment provides the trigger, so doing nothing fails it:

| Card | Environment (facts) | Start | Rule |
|---|---|---|---|
| `tpl-response-1-nogoal-forced` | `../envs/minigrid-blocked-unlock-pickup-cleared/` | the ball starts away from the door: `blocker_moved` is true at the first step; hands empty, key reachable, door locked | `Response(blocker_moved, has_door_key)` |
| `tpl-responded-existence-1-nogoal-forced` | `../envs/minigrid-unlock-pickup-key-held/` | the agent starts holding the matching key: `has_door_key` is true at the first step; `drop` does nothing on the first step | `RespondedExistence(has_door_key, door_open)` |

The environment enforces the start, not the machine (`app/src/arm_fm/forced_starts.py`; the plain
ids `MiniGrid-BlockedUnlockPickup-v0` and `MiniGrid-UnlockPickup-v0` are untouched). The task
wording, the clause, the paraphrases and the `train` flags are those of the originals
(`tpl-response-1-nogoal`, `tpl-responded-existence-1-nogoal`), which stay as they are. Ids are
`<original id>-forced`: "forced" there means the forced start, not the card field `forced` (the
clauses the world guarantees).

The wording stays the originals' on purpose, so a forced-start card differs from its original only
in the start. That includes the second card, whose NL says "pick up the key" while the agent now
starts holding it.

Plans: the solving plan takes the key (first card) or opens the door (second card). Wrong plans: doing
nothing (the exploit the suite closes: it now fails the rule), plus one plan per card that gets close
and still breaks the rule.

Learner: PPO s07, chosen by the user for every thesis run on 2026-11-12.

## Contents

- `tasks.json`: the cards.
- `runs.yaml`: which cards, arms, seeds and steps `run-suite` trains.
- `bundles/<arm>/<card-id>/`: the generated machines (made by `generate-suite`).

Reproduce: `python app/main.py trace-bank --tasks experiments/benchmark/forced-start/tasks.json --output <dir>`
and `python experiments/benchmark/scripts/check_forced_starts.py` (`PYTHONPATH=app`).
