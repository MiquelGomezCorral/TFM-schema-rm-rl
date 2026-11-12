# Tasks

## Chosen missions

- `BA-M1` — Put the yellow ball next to the red key.
- `BA-M2` — Open the green door, then pick up the blue box.
- `BA-M3` — Move the purple box to a corner, then put the yellow ball next to the red key.

`BA-M1` and `BA-M2` have a native BabyAI verifier. `BA-M3` has none: the Reward Machine's
acceptance ends the episode (`success: rm`), and its score is RM acceptance, not independent
environment success.

## Evidence

Reconstructed, our own. The three missions and the `BabyAI-ChosenMission-v0` level were chosen
for the wave-3 smoke tests (2026-10-11), after the project owner's example: put a ball next
to the red key after moving the purple box to a corner. They are not in the ARM-FM paper or its
released artifacts, and no Reward Machine for them is published, so this directory has no
`reward-machines.md` or `task-rm-pairs.md`. The published BabyAI task is in
`../babyai-unlock-to-unlock/`.

- Level and mission verifiers: `app/src/arm_fm/custom_envs/babyai_mission.py`.
- Official BabyAI instructions it reuses:
  <https://github.com/Farama-Foundation/Minigrid/blob/master/minigrid/envs/babyai/core/verifier.py>.
