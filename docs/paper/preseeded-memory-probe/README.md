# A probe that seeds the previous step hides the step-1 crash (0 of 50 → 50 of 50 runs)

Date: 2026-11-12. The real KeyCorridor environment, the real runtime and the real reference labeler; no provider
call, no model call, no training.

## What it shows

A labeling function may read the previous step's values (`prev`), for example to latch "the key has been seen".
The documentation of KeyCorridor gave this example for `key_found` (view part shortened): `prev["key_found"] or
any(cell[0] == 5 ... env.gen_obs()["image"] ...)`.

The first check of that example passed on 50 of 50 layouts. It handed the function a previous valuation it had
written itself (`{"key_found": False}`). The production runtime does not: at step 1 its previous valuation was
empty, so the same expression raised `KeyError: 'key_found'`. A strong review caught it by running the example
through a **fresh runtime** instead of a stand-in.

The same expression, three ways, on the solving plan of the `cx-sequence` card, seeds 1 to 50 (2,113 steps in
all):

| Run | Runtime before (`6149c47`) | Runtime now (`a77709b`) |
| --- | --- | --- |
| unguarded expression, previous valuation **seeded by hand** (the first check) | 0 errors, 0 mismatches, 2,113 steps | 0 errors, 0 mismatches, 2,113 steps |
| unguarded expression, **fresh runtime** | **50 of 50 runs fail at step 1**, `KeyError: 'key_found'`, 0 steps checked | 0 errors, 0 mismatches, 2,113 steps |
| guarded expression (`"key_found" in prev and ...`), fresh runtime | 0 errors, 0 mismatches, 2,113 steps | 0 errors, 0 mismatches, 2,113 steps |

Two fixes closed it, which is why the third row is the same on both trees:

1. The documentation example was guarded, so it works under either runtime (commit `28ae75e`).
2. The runtime now starts every episode with all propositions false in the previous valuation
   ([`../step1-previous-valuation/`](../step1-previous-valuation/README.md), commit `1a25106`), so the unguarded
   form works too.

The point for the method: a check that supplies the state the code is supposed to create hides exactly the bug
about that state. The rule is to rerun such a check through the production object, from its initial state.

## Task, formula and machine

- Natural-language task of the card the plan solves (`cx-sequence`): "Find the key, pick it up, open the locked
  door, go into the room, and then pick up the ball."
- The probe's formula is only about `key_found`: LTLf `F key_found` (`Existence(key_found)`), illustrative.
  The probe compares the proposition's value against the reference labeler at each step; the machine below is
  the toy one the script builds to start the runtime, not a card's machine (the card's own 7-state machine is in
  [`../key-found-clear-view/`](../key-found-clear-view/README.md)).
- Reward Machine: [interactive graph](graphs/probe-key-found.html), [SVG](graphs/probe-key-found.svg).

<details>
<summary>RM text</summary>

```text
REWARD_MACHINE:
STATES: u0, u1
INITIAL_STATE: u0
FINAL_STATES: u1
TRANSITION_FUNCTION:
(u0, key_found) -> u1
(u0, else) -> u0
(u1, else) -> u1
REWARD_FUNCTION:
(u0, key_found, u1) -> 1
```

</details>

## Evidence

- `check/before-6149c47.json`, `check/after-a77709b.json`: the table above, from `check/cold_start_vs_preseeded.py`
  run on each tree. Before is the wave without the step-1 change (`6149c47`); after is the freeze `a77709b`.
- `evidence/doc_cold_start-before.log` and `evidence/doc_cold_start-after.log`: the reviewer's original run
  (50 `KeyError` runs, 0 steps, against 0 errors in 2,113 steps), from `evidence/doc_cold_start.py` and
  `evidence/doc_example_check.py` (the seeded first check). Both read the example from the environment's
  documentation file, so they need the repository state they were written for.
- The rerun in `check/` reproduces the reviewer's numbers (50 runs failing; 2,113 steps).

## Files

- `check/cold_start_vs_preseeded.py`: the three runs (written for this entry; the expressions and the plan are
  the reviewer's).
- `check/before-6149c47.json`, `check/after-a77709b.json`; `graphs/` (probe machine); `evidence/` (original
  scripts and logs).

## Rerun

From the repository root, inside `RM_RL_env`. The before tree is a copy of `6149c47`:

```bash
COPY=$(mktemp -d); git archive 6149c47 app experiments | tar -x -C "$COPY"
(cd "$COPY" && PYTHONPATH=app python -W ignore "$OLDPWD"/docs/paper/preseeded-memory-probe/check/cold_start_vs_preseeded.py before.json)
PYTHONPATH=app python -W ignore docs/paper/preseeded-memory-probe/check/cold_start_vs_preseeded.py after.json
```

Compare `error_runs` of the second row (50 before, 0 after). No LLM call.

## Code

`RewardMachineRuntime.evaluate_labeling` in `app/src/arm_fm/runtime.py` (previous valuation default); the
`key_found` row of `experiments/benchmark/envs/minigrid-key-corridor/environment-code.md`. Commits `28ae75e`
(`fix(benchmark): guard first-step latch reads and count every candidate the generator returned`) and `1a25106`
(`feat(runtime): every proposition is false in the previous valuation at the first step`), merged into the wave as
`6149c47` and `50a7a96`.

## Gaps

- One card (`cx-sequence`), one proposition, 50 layouts. It shows the pre-seeded-memory effect on a single
  expression; it is not a survey of other labeling functions.
- The "runtime before" column is the wave state `6149c47`, which has the guarded documentation but not the
  runtime default. The unguarded documentation text was in commit `fb36d17`; the script runs that expression
  against `6149c47` to isolate the runtime.
- No language model was asked to write this function; whether it would write the unguarded form is not
  measured here.
