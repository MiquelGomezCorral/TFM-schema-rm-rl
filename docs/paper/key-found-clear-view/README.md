# `key_found` needs a clear view (9 of 50 layouts → 0)

Date: 2026-11-12. The real KeyCorridor environment and the real reference labeler; no provider call, no model
call, no training.

## What it shows

On KeyCorridor (`MiniGrid-KeyCorridorS6R3-v0`) the proposition `key_found` means "the agent has located the
key". The benchmark's reference labeler, which is the yardstick the judge compares generated labeling against,
first read that as "the key lies inside the 7×7 box in front of the agent". A wall or a closed door between
the agent and the key does not hide it from that box, so `key_found` was already true on step 1 although the
agent could not see the key. On layouts with seeds 1 to 50 that happened in **9 of 50** (seeds 2, 3, 13, 18,
30, 33, 37, 41 and 44).

Now `key_found` latches only when the agent's own view contains the key: the reference labeler reads
`env.gen_obs()["image"]`, which stops at walls and closed doors, and generated labeling can read the same
thing, so both pipelines and the judge use one definition. The environment's facts file states the
clear-view reading.

| 50 layouts, one no-op step, then `key_found` | Before (`69b64db`) | After (`a77709b`) |
| --- | --- | --- |
| Layouts where `key_found` is true at step 1 | 9 | 0 |
| of which the agent's view does not contain the key | **9** | **0** |
| Solving plan runs that succeed (find, take, unlock, drop, pick up the ball) | 50 / 50 | 50 / 50 |
| Runs where the matching key is held before `key_found` | 0 | 0 |

So the unseen `key_found` goes away without making the solving plan fail or changing the order of events.

## Task, formula and machine

The card whose rule uses `key_found` is `cx-sequence` on KeyCorridor: "Find the key, pick it up, open the
locked door, go into the room, and then pick up the ball." Clauses, all hard:

- `Precedence(key_found, has_matching_key)`: `(((~has_matching_key) U key_found) | (G (~has_matching_key)))`
- `Precedence(has_matching_key, target_door_open)`
- `Precedence(target_door_open, target_room_entered)`
- `Precedence(target_room_entered, target_picked_up)`
- `Existence(target_picked_up)`: `(F target_picked_up)`

The machine is the one the compiler builds from these clauses (`check/compile_cards.py`), 7 states, not model
output: [interactive graph](graphs/cx-sequence.html), [SVG](graphs/cx-sequence.svg).

<details>
<summary>RM text</summary>

[`graphs/cx-sequence.rm.txt`](graphs/cx-sequence.rm.txt) holds the full machine with its rewards.

</details>

## Evidence

- `check/before-69b64db.json`, `check/after-a77709b.json`: the script's counts on each tree. They
  reproduce the card-fix-2 report's "9 → 0" and its "solve 50/50".
- The per-seed list of the nine layouts comes from the reviewer's `mechanics.py` run (its `visibility`
  rows); this entry's script prints counts only.

## Files

- `check/key_view_check.py`: the check (one no-op step, then compare `key_found` with whether the agent sees
  a key; then the solving plan on 50 layouts). `check/compile_cards.py`: builds the card machine.
- `check/before-69b64db.json`, `check/after-a77709b.json`.
- `graphs/`: the `cx-sequence` machine (HTML, SVG, RM text), drawn with `render-rm --html`.

## Rerun

From the repository root, inside `RM_RL_env`. The before tree is a copy of `69b64db`:

```bash
COPY=$(mktemp -d); git archive 69b64db app experiments | tar -x -C "$COPY"
(cd "$COPY" && PYTHONPATH=app python -W ignore "$OLDPWD"/docs/paper/key-found-clear-view/check/key_view_check.py)
PYTHONPATH=app python -W ignore docs/paper/key-found-clear-view/check/key_view_check.py
```

Each prints `key_found_without_view` (9 before, 0 after). No LLM call.

## Code

`app/src/benchmark/reference_labels.py` (`key_seen` now reads `env.gen_obs()["image"]`), the
`environment.md` / `environment-code.md` pair of `experiments/benchmark/envs/minigrid-key-corridor/`. Commit
`fb36d17` (`feat(benchmark): apply card fixes F1-F7 ...`), merged into the wave as `6149c47`.

## Gaps

- The check covers KeyCorridor only, 50 layouts, one step. It does not measure how often a language model's
  labeling gets this wrong.
- `has_matching_key` before `key_found` is 0 in both trees on these 50 layouts of the solving plan only.
