# Reward Machine execution

## Intent

Give both generation modes the same step semantics so comparisons change RM generation
without changing how labels, transitions, and rewards are interpreted.

## Current decisions

- Supply the complete valuation of declared propositions once per environment step.
  Document whether each proposition is a persistent condition or a one-step event.
- Negation means false now. A moment-of-loss event needs its own explicit definition;
  it is not automatically equivalent to an absent possession condition.
- Evaluate outgoing guards only from the old RM state, select one transition, and update
  the RM exactly once per environment step. Do not reevaluate from the destination state.
- A guard depends only on propositions it mentions. Ignore irrelevant propositions and
  use an implicit zero-reward self-loop when no guard matches.
- Baseline RM text retains the paper's per-state `else` self-loop convention. Compiler
  bundle text omits `else` rows and declares a zero default reward; unmatched valuations
  use the same implicit zero-reward self-loop in both modes.
- Expect disjoint ordinary guards. If several match, select the first stored transition
  and emit a warning. An `else` row applies only when no ordinary guard matches.
- Reset the RM and episode-local labeling memory on environment reset.

## Protected invariants

- Simultaneous true propositions never cause multiple RM updates in one environment step.
- Do not enumerate every proposition combination or retain irrelevant conditions merely
  to make transitions explicit.
- Do not reject overlapping guards solely because they overlap, silently reorder them,
  or treat `else` as a competing ordinary guard.
- A proposition that no longer matters to task progress may become false without changing
  the RM state or reward unless that state's guards explicitly depend on it.

## Rationale and tradeoffs

Complete valuations support possession, loss, and penalties without forcing every RM state
to model irrelevant cases. Exactly one update follows the chosen paper semantics. Ordered
first-match execution makes overlap deterministic and visible while avoiding rejection of
otherwise usable artifacts; disjoint guards remain the intended output.

## Enforcement

Review-only until `app/src/arm_fm/runtime.py` and `tests/test_arm_fm.py` implement and check
these contracts. The existing compiler representation alone does not enforce runtime steps.

## History

- 2026-09-18: Confirmed complete valuations, relevant guards, implicit self-loops, ordered
  overlap handling with warnings, and exactly one RM update per environment step.
- 2026-09-21: Kept published-style `else` rows for baseline output while making
  compiler output's implicit self-loop and zero default reward explicit.
