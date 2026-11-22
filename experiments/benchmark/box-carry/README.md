# Box-carry suite

The box cards of the templates and complex suites, with an environment where the agent starts
holding the box and the box falls by itself. On the original cards trained agents never pick the
box up, so the box rule ("whenever the box falls, pick it up again") never triggers and the card
passes by doing nothing. Here the environment provides the pickup (`carry: true`, facts in
`../envs/service-room-carry/environment.md`) and the first fall comes at a seeded step from 2 to 8,
so every episode meets it, whatever the agent does: the box cannot be dropped before that fall, and
the fall turns the agent to face the box, so a pickup on the very next move is always possible.

10 cards. Seven, one per original, ids `<original id>-carry`: `tpl-chain-response-{1,2,3}-{goal,nogoal}-carry`
and `cx-box-carry`. The task wording, the clauses, the paraphrases and the `train` flags are those of
the originals; none of the originals asks for the box to be picked up first, so no part was dropped.
Trained: `tpl-chain-response-1-goal-carry`, `tpl-chain-response-1-nogoal-carry`, `cx-box-carry`.

Three more change only the world: `tpl-chain-response-1-goal-carry-noturn` (`fall_turn: none`)
and `tpl-chain-response-1-goal-carry-backturn` (`fall_turn: side`, user, 2026-11-21), and
`tpl-chain-response-1-goal-carry-half` (`fall_turn: half`, user, 2026-11-22). On every other card
the fall turns the agent to face the box. With `none` the box lands on a side drawn from the seed
(front, right, back or left; a blocked side takes the next free one clockwise) and the agent keeps
its direction, so the next move can pick the box up only when it landed in front. With `side` a box
to the right or left turns the agent to face it, and a box behind turns the agent to its right or
left, one turn short. With `half` the landing is drawn as with `none`, and a fair coin turns the
agent either to face the box or to have it on its right, one turn short. So the world can force a
missed next-move pickup: a break of the box rule after such a fall is the world's doing, not the
machine's. Same task, clauses and plans as `tpl-chain-response-1-goal-carry` (the `none` and `half`
copies leave out the plan that walks straight to the exit), no paraphrases, and no bundle of their
own: `bundle_of` names that card, so `run-suite` trains them on its machine and `generate-suite`
skips them. The copies have no plan check of their own; their machine is checked through
`tpl-chain-response-1-goal-carry`. They train from `runs-fall-turn.yaml` (FARM only, seeds 1 to 3,
1.5M steps: 9 runs); `runs.yaml` lists its 3 cards in `only`, so its 27 runs stay as they were.
Both files name suite `box-carry`, so one driver runs at a time.

How often the next move can pick the box up (measured 2026-11-22 over reset seeds 0 to 999, falls
whose box lies in front of the agent right after the fall; "solve" is the solving policy, which
waits in the start corner, "walk" an agent that walks to the exit and picks the box up whenever it
lies on the floor):

| `fall_turn` | solve | walk |
| --- | --- | --- |
| `face` | 100% | 100% |
| `side` | 100% | 77% |
| `none` | 71% | 41% |
| `half` | 52% | 53% |

The corner walls send blocked back and left draws to the front, so a rule tied to the landing side
depends on where the agent waits; the coin of `half` does not.

Plans: the solving policy waits in place for each fall and picks the box up. Wrong plans: ignoring
the fall (`ignore: ["box_fall"]`), waiting for the fall and then walking to the exit without the box,
doing nothing for the whole episode (the exploit the suite closes: it now fails the rule), and a
late pickup on the ChainResponse cards: waiting nine moves, past the move after the fall, then going
on as the solving policy does (it breaks the box rule only).

Learner: PPO s07, chosen by the user for every thesis run on 2026-11-12; the `learner: dqn` lines in the original suites' `runs.yaml` are stale.

## Contents

- `tasks.json`: the cards.
- `runs.yaml`: which cards, arms, seeds and steps `run-suite` trains.
- `runs-fall-turn.yaml`: the 9 FARM runs of the three world-setting cards.
- `bundles/<arm>/<card-id>/`: the generated machines (made by `generate-suite`).

Reproduce: `python app/main.py trace-bank --tasks experiments/benchmark/box-carry/tasks.json --output <dir>`
and `python experiments/benchmark/scripts/check_service_room_carry.py` (`PYTHONPATH=app`).
