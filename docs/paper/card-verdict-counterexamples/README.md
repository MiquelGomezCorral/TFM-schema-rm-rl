# What an independent card review found, and what is fixed (counting negatives 7 → 0)

Date: 2026-11-12. The real environments, the real plan runner and the real judge; no provider call, no model
call, no training.

## What it shows

Before any pipeline was scored on the 58 benchmark cards, a reviewer who had not seen the earlier audits or
any generated bundle gave every card a verdict by building physical counterexamples: runs that satisfy the
card's wording but fail its clauses, or the reverse. Verdicts (`evidence/verdicts.json`, frozen with
SHA-256 `915b814d…`, reviewed head `7ae1157`):

| Verdict | Cards |
| --- | --- |
| ok | 21 |
| weak (control with a stated limit) | 16 |
| unclear | 5 |
| wrong-expected | 8 |
| broken | 8 |
| wrong-env | 0 |

The 8 **broken** cards are the six `tpl-chain-response-*` cards (solver misses and a direct exit passing; see
[`../box-chain-solver/`](../box-chain-solver/README.md)) and the two counting cards below. The 8
**wrong-expected** cards are Response cards (see the last section).

### Counting negatives: 7 false negatives of 100 → 0

The two counting cards, `tpl-existence-two-2-nogoal` ("Be holding the matching key on at least two different
moves.") and `tpl-existence-two-3-nogoal`, each ship a "wrong" plan that must fail the card: pick the key up
and put it down at once. The drop helper turns or walks before it drops, so the key stayed held for several
labeled steps and the wrong plan satisfied "at least two moves".

| 2 cards × 50 layouts, the card's wrong plan | Before (`7ae1157`) | After (`a77709b`) |
| --- | --- | --- |
| Wrong plans that satisfy the count (false negatives) | **7** of 100 | **0** of 100 |
| `tpl-existence-two-2-nogoal` | 3 (seeds 14, 15, 20; key held 6, 6, 4 labeled steps) | 0 |
| `tpl-existence-two-3-nogoal` | 4 (seeds 4, 8, 26, 36; key held 2 labeled steps each) | 0 |

Fix: the wrong plan now ends at the first pickup, so the key is held for one labeled step, not two or more.
(Before, the plan was pickup then drop; after, pickup only.)

## Task, formula and machine

**`tpl-existence-two-2-nogoal`** on KeyCorridor: "Be holding the matching key on at least two different
moves."

- `ExistenceTwo(has_matching_key)` [hard]: `(F (has_matching_key & (X (F has_matching_key))))`

Machine (3 states, the compiler's reference machine, not model output):
[interactive graph](graphs/tpl-existence-two-2-nogoal.html), [SVG](graphs/tpl-existence-two-2-nogoal.svg),
[RM text](graphs/tpl-existence-two-2-nogoal.rm.txt).

**`tpl-response-3-nogoal`** on KeyCorridor (a card whose verdict is wrong-expected): "Once you have found the
key, the locked door must be open on the last step of the episode."

- `Response(key_found, target_door_open)` [hard]: `(G (key_found -> (F target_door_open)))`

Machine (2 states): [interactive graph](graphs/tpl-response-3-nogoal.html),
[SVG](graphs/tpl-response-3-nogoal.svg), [RM text](graphs/tpl-response-3-nogoal.rm.txt).

The graphs were drawn with `render-rm --html` from the RM text files, which `check/compile_cards.py` wrote.

<details>
<summary>RM text</summary>

Full machines with rewards: [`graphs/tpl-existence-two-2-nogoal.rm.txt`](graphs/tpl-existence-two-2-nogoal.rm.txt)
and [`graphs/tpl-response-3-nogoal.rm.txt`](graphs/tpl-response-3-nogoal.rm.txt).

</details>

## Response is still judged on states (open item, by design)

The reviewer's other finding is not fixed by the wave: Response is judged as "a `b` at or after the last `a`"
over **state** propositions. An event wording ("open the door after you pick up the key") and the state
reading differ when the state is later undone. The run of `check/counterexamples.py` on `a77709b` (the same
plans as the review) still gives:

| Case (plan) | Card | Judge | Event wording satisfied? |
| --- | --- | --- | --- |
| open the door, then close it again | `tpl-response-1-goal`, `-2-goal`, `-3-goal` | fails (`open_at_end`) | yes, the door was opened after the pickup |
| the same, no goal | `tpl-response-2-nogoal`, `tpl-response-3-nogoal` | fails (`open_at_end`) | yes |
| move the ball, pick up the key, put the key down | `tpl-response-1-nogoal` | fails (`open_at_end`) | yes |

These cases fail the judge as predicted. They are the base of to-do item 14 ("Response limitation"); the
decision whether to add event propositions or to reword the cards is open. Two more rows of the same run are
interpreted here: `cx-goal-many-rules` (judged success, with one clause `broken@29`) and
`base-blocked-unlock-pickup` (judged success, all four clauses hold, on a run the reviewer built as a
key-before-ball order); read them in `check/after-a77709b.counterexamples.out`.

The event sweep in the same run plays all 12 event-room cards on seeds 1 to 50: 600 runs, 0 solving-plan
failures (the 74 → 0 of the box-chain entry).

## Evidence

- `evidence/verdicts.json`: the 58 verdicts with finding and fix per card; `evidence/independence.json`: the
  source hashes, the reviewed head and the marker that earlier reports were not read. The file is the
  reviewer's frozen copy (its hash is in `independence.json`), so the `evidence` field of each verdict still
  names the reviewer's own scratch files, which are not copied here.
- `check/before-7ae1157.count_negatives.out`, `check/after-a77709b.count_negatives.out`: the counting check on
  each tree (runs, false negatives, seed list). `check/after-a77709b.counterexamples.out`: the counterexample
  cases on the freeze.
- `7ae1157` is the revised card tree the reviewer judged; `a77709b` is the pipeline freeze. The counting check
  was re-run on both for this entry and reproduced the review's 7 of 100.

## Files

- `check/count_negatives.py` (output folder as the first argument), `check/counterexamples.py` (same),
  `check/compile_cards.py` (card machines). The scripts are the reviewer's, with only the output path
  patched.
- `evidence/` and `graphs/` as above.

## Rerun

From the repository root, inside `RM_RL_env`. The before tree is a copy of `7ae1157`:

```bash
COPY=$(mktemp -d); git archive 7ae1157 app experiments | tar -x -C "$COPY"
(cd "$COPY" && PYTHONPATH=app python -W ignore "$OLDPWD"/docs/paper/card-verdict-counterexamples/check/count_negatives.py out-before)
PYTHONPATH=app python -W ignore docs/paper/card-verdict-counterexamples/check/count_negatives.py out-after
PYTHONPATH=app python -W ignore docs/paper/card-verdict-counterexamples/check/counterexamples.py out-after
```

Create the output folders first. `counterexamples.py` was run on the freeze only: on the `7ae1157` tree it
stopped with a plan error ("no reachable ball"). No LLM call.

## Code

The counting cards and their wrong plans in `experiments/benchmark/templates/tasks.json`; the plan runner in
`app/src/benchmark/plans.py`. Fix in commit `fb36d17` (`feat(benchmark): apply card fixes F1-F7 ...`), merged
into the wave as `6149c47`.

## Gaps

- Only the verdicts and counts shown here are the review's; the reviewer's full plan checks (a 32 MB file)
  are not copied.
- Counts are for seeds 1 to 50 per card; nothing is claimed for other seeds.
- Which cards of the 21 ok and 16 weak were later changed is not listed here; the table is the review's, not a
  re-judgment of the freeze.
- The Response cases still fail by design; no fix exists to compare against.
