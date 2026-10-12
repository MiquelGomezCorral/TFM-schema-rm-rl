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
  use an implicit zero-reward self-loop when no ordinary guard or explicit fallback applies.
- Baseline RM text retains the paper's per-state `else` self-loop convention. Compiler
  generation omits `else` rows and declares a zero default reward. Both modes apply
  an explicit `else` when present, otherwise the implicit zero-reward self-loop.
- Compiler imports accept explicit self-loops and `else` rows, including an `else`
  destination different from the source. Preserve their destinations and rewards;
  the fallback applies only when no ordinary guard matches.
- Expect disjoint ordinary guards. If several match, select the first stored transition
  and emit a warning. An `else` row applies only when no ordinary guard matches.
- Reset the RM and episode-local labeling memory on environment reset.
- Only declared final states accept the task. A declared rejecting state (`REJECTING_STATES`)
  marks an irreversible violation; RMs without that line (such as ARM-FM paper RMs) have none.
  States remember earlier events; a false proposition now does not erase recorded progress.
- Entering a final or rejecting state ends the episode, as do the environment's own termination
  and its time limit, for every RM-wrapped run. A truncated step that did not terminate adds -0.5
  to the RM reward.
- The learner reward follows the run's `reward_source`: `rm` (default) the RM reward only,
  `both` environment + RM reward, `env` no RM at all. `info["env_reward"]` always holds the raw
  environment reward and `info["rm_reward"]` the RM reward, including the time-limit penalty.
- App graphs, exported SVGs, and the standalone graph script share the same fallback
  display. Show explicit fallback edges with an `else` label. For every declared state
  without an outgoing `else`, draw a zero-reward self-loop labeled `else`, including
  accepting and rejecting states. An explicit `else` to another state suppresses that
  default loop; ordinary guarded self-loops do not.
- These graph defaults are display-only. Preserve explicit guards and rewards when
  grouping edges with the same source and destination. Do not enumerate valuations
  or analyze guard exhaustiveness to decide whether to show a default loop.
- App graphs and standalone SVGs use one deterministic top-down layout and shared
  sibling-label spacing. The app starts from those positions rather than a force
  layout. Self-loops appear on the right with horizontal labels below them; users
  may still pan, zoom, drag states, inspect transitions, and export their placement.

- The authors' released runtime chains every triggered event inside one step. Paper-reproduction
  runs keep our one-update rule. The authors apply `else` only when no event is true and none of
  their four released RMs rewards `else`; their stages need distinct actions, so the difference
  does not change those RMs (only UnlockToUnlock u4 can see two events at once, and both
  runtimes take the first listed one).

## Protected invariants

- Simultaneous true propositions never cause multiple RM updates in one environment step.
- Do not enumerate every proposition combination or retain irrelevant conditions merely
  to make transitions explicit.
- Do not reject overlapping guards solely because they overlap, silently reorder them,
  or treat `else` as a competing ordinary guard.
- A proposition that no longer matters to task progress may become false without changing
  the RM state or reward unless that state's guards explicitly depend on it.
- Graph fallback edges must not mutate the input machine, serialized output, or
  execution semantics. An explicit `else` destination and reward must remain intact.

## Rationale and tradeoffs

Complete valuations support possession, loss, and penalties without forcing every RM state
to model irrelevant cases. Exactly one update follows the chosen paper semantics. Ordered
first-match execution makes overlap deterministic and visible while avoiding rejection of
otherwise usable artifacts; disjoint guards remain the intended output.

Implicit zero-reward loops keep compiler text compact while explicit `else` remains
usable for imported paper-style machines and fallbacks to other states. Drawing these
defaults makes missing rows understandable, including final and rejecting sinks,
without expanding the machine or adding a guard-coverage calculation.

## Enforcement

- `app/src/arm_fm/runtime.py` owns guard evaluation, explicit fallback selection,
  zero-reward implicit loops, ordered overlap warnings, one update per step, episode termination
  on final or rejecting states, the time-limit penalty, and the reward source.
  `tests/test_arm_fm.py` checks the runtime contracts.
- `app/src/compiler/rm_format.py` owns the shared text parser and serializer; the compiler
  and the runtime both import it, and it never imports `src.arm_fm`.
  `tests/test_reward_machine_format.py` checks zero-reward progress, imported guards,
  explicit self-loops, and `else` fallbacks to other destinations.
- `app/src/utils/visualization.py` owns display-only fallback edges for the app and
  `app/scripts/render_rm.py`; `app/src/utils/svg.py` renders the shared elements.
  `tests/test_reward_machine_format.py` checks fallback destinations, rewards,
  visible SVG labels, and unchanged input transitions.
- `app/src/utils/visualization.py` owns layered positions and sibling-label offsets;
  it also shares loop dimensions with the SVG renderer. `app/src/web/components.py`
  selects Cytoscape's preset layout. `tests/test_web.py` checks initial app placement
  against the standalone SVG and keeps pan and zoom enabled.
- The meaning of event versus persistent propositions remains Review-only against
  each environment definition; runtime evaluation cannot establish that grounding.

## History

- 2026-09-18: Confirmed complete valuations, relevant guards, implicit self-loops, ordered
  overlap handling with warnings, and exactly one RM update per environment step.
- 2026-09-21: Kept published-style `else` rows for baseline output while making
  compiler output's implicit self-loop and zero default reward explicit.
- 2026-10-12: Recorded that paper-reproduction runs keep one update per step although the
  authors' runtime chains events.
- 2026-10-12: Added declared rejecting states, episode end on RM final or rejecting states and on
  the time limit (-0.5), and `reward_source` (default `rm`), following Toro Icarte et al. (JAIR
  2022), where reaching an RM terminal state ends the episode (user decisions).
