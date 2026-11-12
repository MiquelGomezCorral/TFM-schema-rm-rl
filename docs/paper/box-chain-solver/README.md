# Box chain: the solving plan now solves it (74 misses → 0)

Date: 2026-11-12. The real event room, the real plan runner and the real judge; no provider call, no model
call, no training.

## What it shows

The event-room cards with a falling box ("whenever the box falls, pick it up again on your very next move")
come with a solving plan, and the benchmark trusts that plan: it must pass the card's own judge. An
independent card review (card-fix-2) played every event-room card's plan on seeds 1 to 50 and found that the
plan **missed the card's own rule in 74 of 600 runs**, all on the six `ChainResponse` cards (the rule that
the very next move after a fall is the pickup). A direct walk to the exit, ignoring the box, also passed
8 cards.

Two changes close both. The scripted policy now waits holding the box until every planned fall has fired, so
the box lands in the free cell in front of the agent. And the box cards now ask for the box at the exit:
"Carry the box to the exit" adds the clause `Response(at_exit, holding_box)`, so a direct exit fails.

| Same sweep, 12 event-room cards × 50 seeds = 600 solving runs | Before (`69b64db`) | After (`a77709b`) |
| --- | --- | --- |
| Runs where the card's own solving plan fails the card's own judge | **74** | **0** |
| of which `tpl-chain-response-1-*` / `-3-*` (10 per card) | 40 | 0 |
| of which `tpl-chain-response-2-*` (17 per card) | 34 | 0 |
| Cards a direct walk to the exit passes on all 50 seeds | **8** | **1** |

The one card still passed by a direct exit after the fix is `tpl-absence-3-nogoal` ("Never flip the wall
switch."). That is expected: it forbids only the switch, and the box is in none of its clauses.

The cards changed together with the solver, so the 74 → 0 is the pair, not the solver alone: before, the
chain goal card read "Reach the exit. Each time the box falls, your very next move must pick it up again."
(`ChainResponse(box_fell, holding_box)`, `Existence(at_exit)`); after, "Carry the box to the exit. Each time
the box falls, your very next move must pick it up again." with the extra clause.

## Task, formula and machine

The machines are not model output: each is the Reward Machine the compiler builds from the card's clauses
(`check/compile_cards.py`), the card's reference machine. Graphs are interactive (drag a state, click an
edge); the RM text is in the fold-outs.

**`cx-box`** (hard clauses): "Carry the box to the exit, and whenever the box falls, pick it up again."

- `Response(box_fell, holding_box)`: `(G (box_fell -> (F holding_box)))`
- `Existence(at_exit)`: `(F at_exit)`
- `Response(at_exit, holding_box)`: `(G (at_exit -> (F holding_box)))`

Machine (5 states): [interactive graph](graphs/cx-box.html), [SVG](graphs/cx-box.svg),
[RM text](graphs/cx-box.rm.txt).

**`tpl-chain-response-2-goal`** (the card with 17 misses before): "Carry the box to the exit. Each time the box
falls, your very next move must pick it up again."

- `ChainResponse(box_fell, holding_box)`: `(G (box_fell -> (X holding_box)))`
- `Existence(at_exit)`: `(F at_exit)`
- `Response(at_exit, holding_box)`: `(G (at_exit -> (F holding_box)))`

Machine (7 states): [interactive graph](graphs/tpl-chain-response-2-goal.html),
[SVG](graphs/tpl-chain-response-2-goal.svg), [RM text](graphs/tpl-chain-response-2-goal.rm.txt).

<details>
<summary>RM text (cx-box, transitions)</summary>

```text
(u0, !at_exit&box_fell&!holding_box) -> u1
(u0, at_exit&!box_fell&!holding_box) -> u2
(u0, at_exit&!box_fell&holding_box) -> u3
(u0, at_exit&box_fell&!holding_box) -> u4
(u0, at_exit&box_fell&holding_box) -> u3
(u1, !at_exit&holding_box) -> u0
(u1, at_exit&!holding_box) -> u4
(u1, at_exit&holding_box) -> u3
(u2, !box_fell&holding_box) -> u3
(u2, box_fell&!holding_box) -> u4
(u2, box_fell&holding_box) -> u3
(u4, holding_box) -> u3
```

Full text with rewards: [`graphs/cx-box.rm.txt`](graphs/cx-box.rm.txt).

</details>

## Evidence

- `check/before-69b64db.json`, `check/after-a77709b.json`: per card, 50 runs, solve misses, direct-exit
  passes, first misses (seed and verdicts, for example seed 10 `broken@11` on `tpl-chain-response-1-goal`).
- Before is the tree of commit `69b64db` (the wave before the card fixes); after is `a77709b`. The script
  was run on each tree and reproduced the card-fix-2 report's 74 and its 8 → 1.

## Files

- `check/box_chain_sweep.py`: the sweep (derived from the reviewer's event sweep and the coder's
  `box_check.py`). `check/compile_cards.py`: builds the card machines.
- `check/before-69b64db.json`, `check/after-a77709b.json`.
- `graphs/`: the two machines (HTML, SVG, RM text), drawn with `render-rm --html`.

## Rerun

From the repository root, inside `RM_RL_env`. The before tree is a copy of `69b64db`:

```bash
COPY=$(mktemp -d); git archive 69b64db app experiments | tar -x -C "$COPY"
(cd "$COPY" && PYTHONPATH=app python -W ignore "$OLDPWD"/docs/paper/box-chain-solver/check/box_chain_sweep.py before.json)
PYTHONPATH=app python -W ignore docs/paper/box-chain-solver/check/box_chain_sweep.py after.json
PYTHONPATH=app python -W ignore docs/paper/box-chain-solver/check/compile_cards.py <output dir> cx-box tpl-chain-response-2-goal
```

The sweeps end with `total: 74 solve misses over 600 runs on 12 cards` and `total: 0 solve misses over 600
runs on 12 cards`. No LLM call.

## Code

`_fall_pending` and the policy in `app/src/arm_fm/service_room.py`; the six `tpl-chain-response-*` cards and
`cx-box` in `experiments/benchmark/templates/tasks.json` and `complex/tasks.json`. Commit `fb36d17`
(`feat(benchmark): apply card fixes F1-F7 ...`), merged into the wave as `6149c47`.

## Gaps

- This is the scripted solving plan, not an agent; no agent was trained on these cards.
- The 74 → 0 changes the cards as well as the solver (see above); the sweep cannot separate the two.
- No bundle has been generated for these cards yet, so the machines are the compiler's reference machines,
  not a pipeline's output.
