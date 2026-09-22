# Finish DoorKey bundles with one consistent RM output

## Implementation

- In the compiler-to-paper adapter, map numeric states to `u0`, `u1`, … consistently across transitions, final states, and descriptions. Preserve topology, guard order, and rewards.
- Let `generate-larm --mode compiler` receive the accepted compiler result in memory without writing an intermediate `.rm`. Each experiment task retains one RM file: its bundle’s `reward_machine.txt`.
- Require `FINAL_STATES` in newly generated baseline RMs through the baseline prompt, critic, and acceptance check. Keep the paper’s `else` style. Do not rewrite published source artifacts or change episode termination.
- In compiler paper-format output, state `DEFAULT_REWARD: 0` explicitly and teach the parser this compiler-only header. Unmatched valuations remain implicit self-loops; no `else` rows are generated.
- Resume the four-task run. Diagnose `dk-b` against the task’s historical acquisition semantics before adjusting its prompt or critic; retain failed feedback. Generate `dk-c`, embed each successful bundle as soon as it is ready, then run semantic checks and the previously planned training once all required bundles are complete. Report any remaining provider or model blocker instead of claiming completion.

## Verification

- Round-trip baseline and compiler RMs; check `u` naming, finals, default reward, unchanged transition behavior, and exactly one RM update per environment step.
- Confirm compiler experiment runs create no second `.rm` and keep one `reward_machine.txt` per bundle.
- Run one real embedding probe, then verify one finite normalized embedding per state and bundle completeness. Exercise DoorKey labeling/RM scenarios before attempting training.

## Decisions to record

- Update `docs/decisions/arm-fm/reproduction-boundary.md`: baseline gains an explicit final-state header as a documented reconstruction extension; both modes share downstream embedding/training; experiment bundles have one paper-layout RM output.
- Update `docs/decisions/arm-fm/rm-execution.md`: baseline retains the published `else` convention; compiler omits `else`, declares default reward zero, and relies on the existing implicit zero-reward self-loop.
- Update `docs/decisions/arm-fm/task-and-rm-identity.md`: compiler state renaming happens only at the shared artifact boundary. `docs/decisions/index.md` needs no new link because all three records already exist.
- Keep the previous live-validation plan’s eight-bundle and two-training-checkpoint targets; do not record this run’s failures as architecture decisions.
