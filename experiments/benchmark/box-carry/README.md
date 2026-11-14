# Box-carry suite

The box cards of the templates and complex suites, with an environment where the agent starts
holding the box and the box falls by itself. On the original cards trained agents never pick the
box up, so the box rule ("whenever the box falls, pick it up again") never triggers and the card
passes by doing nothing. Here the environment provides the pickup (`carry: true`, facts in
`../envs/service-room-carry/environment.md`) and the first fall comes at a seeded step from 2 to 8,
so every episode meets it, whatever the agent does: the box cannot be dropped before that fall, and
the fall turns the agent to face the box, so a pickup on the very next move is always possible.

7 cards, one per original, ids `<original id>-carry`: `tpl-chain-response-{1,2,3}-{goal,nogoal}-carry`
and `cx-box-carry`. The task wording, the clauses, the paraphrases and the `train` flags are those of
the originals; none of the originals asks for the box to be picked up first, so no part was dropped.
Trained: `tpl-chain-response-1-goal-carry`, `tpl-chain-response-1-nogoal-carry`, `cx-box-carry`.

Plans: the solving policy waits in place for each fall and picks the box up. Wrong plans: ignoring
the fall (`ignore: ["box_fall"]`), waiting for the fall and then walking to the exit without the box,
and doing nothing for the whole episode (the exploit the suite closes: it now fails the rule).

Learner: PPO s07, chosen by the user for every thesis run on 2026-11-12; the `learner: dqn` lines in the original suites' `runs.yaml` are stale.

## Contents

- `tasks.json`: the cards.
- `runs.yaml`: which cards, arms, seeds and steps `run-suite` trains.
- `bundles/<arm>/<card-id>/`: the generated machines (made by `generate-suite`).

Reproduce: `python app/main.py trace-bank --tasks experiments/benchmark/box-carry/tasks.json --output <dir>`
and `python experiments/benchmark/scripts/check_service_room_carry.py` (`PYTHONPATH=app`).
