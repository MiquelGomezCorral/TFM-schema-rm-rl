# Which answer FARM picks when a card allows several (2026-11-22)

Packet: `clause-choice-packet.md`. Read-only: no model call, no training. Script:
`tools/clause_choice.py`; its full output is `clause-choice/tables.md` (every bundle and run, every
wording) plus `clause-choice/choices.json` and one RM per chosen answer in `clause-choice/rm/`.

## Short answer

- **Not random:** one wording gives one answer, 51 of 52 three-run cells agree (a coin flip: 27%).
- **No pull toward `expect`:** it wins 84/153 right level runs, 55% [47%, 63%], against 50%.
- **Tendency:** on ordered tasks the prompt's chain form wins 12/12 bundles and 137/138 runs,
  whichever side the card lists it on; on "not both" and soft-order tasks the wording picks.
- **Rewording changed it** on all 5 such cards with 4 wordings (8 of 24 bundles took the
  alternative, one run each). The thinking level did not: low to max pick the same.
- **Pricing:** the generator never sees prices; the critic does, and once moved a pick partly over
  reward (`tpl-precedence-soft-1-goal~p2`).

## Details

- **Repeats.** All 11 level cases gave one answer on every right run from low to max (12 runs each).
  The final run's `expect` share is 24/36, 67% [50%, 80%], but that set mixes in six alternatives
  taken from it (caveat below).
- **Ordered tasks.** The prompt's form is the last step's `Existence` plus the `Precedence`s
  (`app/src/prompts/compiler-rm/reward-ltlf-creator.system.md:31-36, 41, 62-63`). Cards list it as
  `expect` on 2 cards and as `also_ok` on 7, so `expect` there just reflects the card author's side.
- **Wording cards.** 9 cards, 24 bundles; 8 took the alternative, each from its own wording, and
  the other wordings of the same card took `expect`. Each of those 8 wordings ran once.
- **Thinking level.** Low, medium, high and max give the same pick on every right run (18/33
  `expect` each); none adds 11 wrong runs and one flip (S1, run 3).
- **Pricing.** The generator prompt says "Do not output formulas, rewards"
  (`reward-ltlf-creator.system.md:89`) and shows none. The critic sees the priced machine but is
  told not to judge reward magnitudes (`reward-machine-critic.system.md:17-20`). It switched one
  pick between listed answers: `tpl-precedence-soft-1-goal~p2`, E to A, because the commanded move
  "needs its own Existence" and the soft order alone "gives no reward for moving the ball". The
  data has no price variation to test more.

## What was measured

- **Two sets, never mixed.** (1) The final-run FARM bundles (freeze `809dfe3`, max thinking,
  generator deepseek-v4.1-flash, critic glm-5.3-flash): 36 bundles of 15 card entries with a
  non-empty `also_ok` (`pilot/base-unlock-pickup` counted apart from `base/`). (2) The
  thinking-level benchmark at the freeze (`docs/paper/level-benchmark-freeze/records/`): 11 of its
  46 cases are such cards, 3 runs at each of 5 levels, 165 runs.
- **Matching follows the repo scorer.** `clause_status` (`app/src/benchmark/rm_facts.py:133`)
  decides right or wrong; the script only names which answer it accepted, in its order: `expect`
  (forced clauses optional), then each `also_ok` exactly, then the MONA same-task check. All 189
  right answers matched exactly; none needed MONA. A run the scorer rejects, or a failed run, is
  `none` (12, all at none or low).
- **Cards.** Today's cards. The four local-soft cards (S1-S4) exist only in the level run's
  snapshot (`evidence/cards/`), so they come from there.
- **Random baseline.** Each right answer a uniform pick among the card's listed answers (1/2, or
  1/3 for `tpl-not-co-existence-1-goal`). Compared on the `expect` share (two-sided binomial) and on
  how often repeated runs agree (one-sided binomial against the chance of agreeing).

**Caveat: six alternatives came from these bundles.** On 2026-11-22 Miquel accepted the readings
of 8 final-run bundles and added them as `also_ok`, six new answers on six cards
(`docs/paper/wrong-clauses-at-max/`: 7 in `evidence/wrong-bundles.json`, plus
`tpl-not-co-existence-1-goal~p2`). They are marked "added after" below. Those cards entered this
set because a wording disagreed, so the final run overstates how often wordings split. The level benchmark ran before the ruling; only W2a
(`tpl-precedence-1-nogoal`) is such a card there, and it never took the added answer.

## Expect share among right answers

| set | cards | generations | right | expect [95% Wilson CI] | uniform | p |
|---|---|---|---|---|---|---|
| FARM final run, all | 15 | 36 | 36 | 24/36 = 67% [50%, 80%] | 48% | 0.03 |
| FARM final run, answers listed before it | 9 | 15 | 15 | 11/15 = 73% [48%, 89%] | 50% | 0.12 |
| FARM final run, an answer added from it | 6 | 21 | 21 | 13/21 = 62% [41%, 79%] | 47% | 0.19 |
| levels: none | 8 | 33 | 22 | 12/22 = 55% [35%, 73%] | 50% | 0.83 |
| levels: low | 8 | 33 | 32 | 18/32 = 56% [39%, 72%] | 50% | 0.6 |
| levels: medium | 8 | 33 | 33 | 18/33 = 55% [38%, 70%] | 50% | 0.73 |
| levels: high | 8 | 33 | 33 | 18/33 = 55% [38%, 70%] | 50% | 0.73 |
| levels: max | 8 | 33 | 33 | 18/33 = 55% [38%, 70%] | 50% | 0.73 |
| levels: all | 8 | 165 | 153 | 84/153 = 55% [47%, 63%] | 50% | 0.26 |

The final run's 67% (p = 0.03) mixes in the six added alternatives; without them it is 11/15,
p = 0.12.

## Ordered tasks: the prompt's form

The prompt's order rules (`reward-ltlf-creator.system.md:31-36, 41, 62-63`): the last step's
`Existence` plus one `Precedence` per pair, no `Existence` a hard `Precedence` already forces, and
a hard `Precedence` before a step that is only preferred. Which answer is that form is my reading
per card (`PROMPT_FORM` in the script).

| set | prompt's form [95% CI] | expect [95% CI] |
|---|---|---|
| FARM final run | 12/12 = 100% [76%, 100%] | 8/12 = 67% [39%, 86%] |
| levels: none | 18/19 = 95% [75%, 99%] | 9/19 = 47% [27%, 68%] |
| levels: low to max | 119/119 = 100% [97%, 100%] | 60/119 = 50% [42%, 59%] |

The one miss: S1 at none, run 3, wrote the soft order the card lists as `expect`.

## Do repeated runs agree?

| groups | agree [95% CI] | chance under a uniform pick | p (one-sided) |
|---|---|---|---|
| levels: one case at one level (3 runs) | 51/52 = 98% [90%, 100%] | 27% | 8e-28 |
| levels: one case over low to max (12 runs) | 11/11 = 100% [74%, 100%] | 0.05% | 1e-36 |
| FARM: one card's 4 wordings, answers listed before | 2/2 | 12% | 0.016 |
| FARM: one card's 4 wordings, all cards | 2/7 = 29% [8%, 64%] | 11% | 0.18 |

Only 1 of the 11 level cases (W2a) is a wording card; the other 10 are ordered cards.

## Per card

E = `expect`, A = `also_ok[0]`, B = `also_ok[1]`, X = wrong or failed. LTL is the pipeline's LTLf;
"(soft)" marks a soft clause. Level cells count the right runs over all 5 levels (15 runs per
case). RM files are in `clause-choice/rm/`, one per chosen answer.

### Ordered cards (the prompt's form wins)

| card | task (main wording) | answers in LTL | FARM final (main, p1, p2, p3) | levels | RM |
|---|---|---|---|---|---|
| `base/base-key-corridor` | "Explore the side rooms, find and acquire the key matching the locked target room, return to the corridor, open the target door, and pick up the designated object." | both: `((~has_matching_key) U key_found) \| G ~has_matching_key`; `((~target_door_open) U has_matching_key) \| G ~target_door_open`; `((~target_picked_up) U target_door_open) \| G ~target_picked_up`; `F target_picked_up`. E adds `F has_matching_key`, `F target_door_open` | A | - | `base__base-key-corridor__also_ok-0.txt` |
| `base/base-unlock-pickup` (and `pilot/`) | "Acquire the matching key, unlock the door, and pick up the designated box in the other room." | both: `((~door_open) U has_door_key) \| G ~door_open`; `((~target_picked_up) U door_open) \| G ~target_picked_up`; `F target_picked_up`. E adds `F has_door_key`, `F door_open` | A (base), A (pilot) | - | `base__base-unlock-pickup__also_ok-0.txt`, `pilot__base-unlock-pickup__also_ok-0.txt` |
| `complex/cx-goal-one-rule` | "Open the door and then pick up the box in the other room, and try not to drop the key while the door is still closed." | both: `((~target_picked_up) U door_open) \| G ~target_picked_up`; `F target_picked_up`; `~F key_lost` (soft). A adds `F door_open` | E, E, E, E | O1 (main) E 13; W4b (p2) E 14; U5 (p3) E 13 | `complex__cx-goal-one-rule__expect.txt` |
| `templates/tpl-existence-1-goal` | "Pick up the key, then reach the goal." | both: `((~at_goal) U has_key) \| G ~at_goal`; `F at_goal`. A adds `F has_key` | E, E, E, E | G1 (main) E 14; O4 (p2) E 14 | `templates__tpl-existence-1-goal__expect.txt` |
| `templates/tpl-existence-two-3-goal` | "Be holding the key on at least two different moves, open the door and reach the goal." | both: `F (has_key & X F has_key)`; `((~at_goal) U door_open) \| G ~at_goal`; `F at_goal`. E adds `F door_open` | A | G4 A 13 | `templates__tpl-existence-two-3-goal__also_ok-0.txt` |
| `local-soft/soft-key-goal` (S1) | "Grab the key, and after that get to the goal square if you can." | both: `F has_key`; `F at_goal` (soft). E: `((~at_goal) U has_key) \| G ~at_goal` soft; A: the same order hard | - | A 14, E 1 (none) | `local-soft__soft-key-goal__also_ok-0.txt`, `local-soft__soft-key-goal__expect.txt` |
| `local-soft/soft-key-door-goal` (S2) | "Pick up the key, then open the door, and then, ideally, walk onto the goal." | both: `F door_open`; `((~door_open) U has_key) \| G ~door_open`; `F at_goal` (soft). E: `((~at_goal) U door_open) \| G ~at_goal` soft; A: hard | - | A 15 | `local-soft__soft-key-door-goal__also_ok-0.txt` |
| `local-soft/soft-door-box` (S3) | "Open the door, then, if possible, pick up the box in the other room." | both: `F door_open`; `F target_picked_up` (soft). E: `((~target_picked_up) U door_open) \| G ~target_picked_up` soft; A: hard | - | A 15 | `local-soft__soft-door-box__also_ok-0.txt` |
| `local-soft/soft-key-door-box` (S4) | "Take the key, then open the door. After that, try to pick up the box in the other room." | both: `F door_open`; `((~door_open) U has_door_key) \| G ~door_open`; `F target_picked_up` (soft). E: `((~target_picked_up) U door_open) \| G ~target_picked_up` soft; A: hard | - | A 12 (X 3 at none) | `local-soft__soft-key-door-box__also_ok-0.txt` |

### Wording cards (the wording picks; the alternative's wording in the FARM cell)

| card | task (main wording) | answers in LTL | FARM final (main, p1, p2, p3) | levels | RM |
|---|---|---|---|---|---|
| `templates/tpl-not-co-existence-1-goal` | "Pick up the box in the other room, but never both drop the key while the door is still closed and open the door." | both: `F target_picked_up`. E: `(F key_lost) -> ~F door_open`; A: `~F key_lost`; B (added after): `~F key_lost`, `F door_open` | E, E, **B** ("You must not drop the key while the door is still closed and open the door in the same run."), E | - | `..._tpl-not-co-existence-1-goal__expect.txt`, `...__also_ok-1.txt` |
| `templates/tpl-not-co-existence-2-goal` | same text as 1-goal | both: `F target_picked_up`. E: `(F key_lost) -> ~F door_open`; A: `~F key_lost` | E | - | `templates__tpl-not-co-existence-2-goal__expect.txt` |
| `templates/tpl-not-co-existence-3-goal` | "Reach the goal, but never both drop the key while the door is still closed and open the door." | both: `F at_goal`. E: `(F key_lost) -> ~F door_open`; A: `~F key_lost` | E | - | `templates__tpl-not-co-existence-3-goal__expect.txt` |
| `templates/tpl-not-co-existence-3-nogoal` | "Never both take the matching key and get into the locked room." | E: `(F has_matching_key) -> ~F target_room_entered`; A: `~F target_room_entered` | E | - | `templates__tpl-not-co-existence-3-nogoal__expect.txt` |
| `templates/tpl-not-co-existence-soft-1-goal` | "Pick up the box in the other room, but try not to both drop the key while the door is still closed and open the door." | both: `F target_picked_up`. E: `(F key_lost) -> ~F door_open` (soft); A (added after): `~F key_lost` (soft) | **A** (main wording), E, E, E | - | `..._soft-1-goal__expect.txt`, `...__also_ok-0.txt` |
| `templates/tpl-not-co-existence-soft-1-nogoal` | "Try not to let zombies through both the top lane and the side lanes." | E: `(F top_breach) -> ~F side_breach` (soft); A (added after): `~F top_breach` (soft), `~F side_breach` (soft) | **A** (main wording), E, E, E | - | `..._soft-1-nogoal__expect.txt`, `...__also_ok-0.txt` |
| `templates/tpl-precedence-1-nogoal` | "If you reach the exit, you must have flipped the switch first." | both: `((~at_exit) U switch_toggled) \| G ~at_exit`. A (added after) adds `F at_exit` | E, **A** ("You may only reach the exit after you have flipped the switch."), E, E | W2a (main) E 15 | `templates__tpl-precedence-1-nogoal__expect.txt`, `...__also_ok-0.txt` |
| `templates/tpl-precedence-soft-1-goal` | "Pick up the box in the other room, and try to move the ball away from the door before you take the key." | both: `((~has_door_key) U blocker_moved) \| G ~has_door_key` (soft); `F target_picked_up`. A (added after) adds `F blocker_moved` (soft) | **A**, **A** ("try to clear the ball from the door"), **A** ("Try to move the ball off the door"; the generator wrote E, the critic asked for the soft `F blocker_moved`), E ("preferably the ball is out of the way of the door") | - | `templates__tpl-precedence-soft-1-goal__expect.txt`, `...__also_ok-0.txt` |
| `templates/tpl-precedence-soft-3-goal` | "Go to the exit, and try to have picked up the box before you get there." | both: `((~at_exit) U holding_box) \| G ~at_exit` (soft); `F at_exit`. A (added after) adds `F holding_box` (soft) | **A** | - | `templates__tpl-precedence-soft-3-goal__also_ok-0.txt` |

`...` stands for `templates__tpl-not-co-existence` or the card's own prefix; the exact names are in
`clause-choice/rm/`. Every wording of every bundle is in `clause-choice/tables.md`.

**What the alternative wordings share.** "Try to <do x> before y" got an extra soft `F x` on 4 of 4
action wordings (one through the critic); the one stated as a state ("preferably the ball is out of
the way") did not. A
"not both" split into two bans when the second half reads as its own act ("... and open the door in
the same run") or when "both" sits on a list of places ("through both the top lane and the side
lanes"). This is my reading of 8 single runs, not a tested rule.

## Rerun

From the repository root (RM_RL_env; MONA on PATH for the same-task check):

```
env PATH=/home/turbotowerlnx/miniconda3/envs/RM_RL_env/bin:/home/turbotowerlnx/.local/bin:/usr/bin:/bin PYTHONPATH=app python -W ignore .git/agent-memory/plans/farm-final-20261119/freeze-prep/tools/clause_choice.py
```

It rewrites `clause-choice/` (a few seconds). No model call.

## Not checked

- The script counts only final clauses. I checked the critic's changes by hand: it rejected a first
  answer in 1 of 36 bundles (`tpl-precedence-soft-1-goal~p2`, above) and 7 of 165 level runs (6 at
  none, 1 at low); none of those 7 switched between two listed answers.
- Whether each of the 8 alternative wordings repeats its pick: one run each. Three reruns of those
  8 wordings at max (24 model calls) would settle whether the wording or chance moved them.
