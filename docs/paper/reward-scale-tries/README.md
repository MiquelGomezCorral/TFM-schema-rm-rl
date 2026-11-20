# Reward scale tries

A list, not a result page. Every size or scale of a reward we changed to make a machine learn, what
the task did, and where the numbers are. Dates are 2026. Sources marked `evidence/` are copies of the
working notes in `.git/agent-memory/` (outside the repository); the others are in this repository.
For the lanes card (`lanes-rules`) the task, LTLf and RM are in `../zombie-garden-warm-start/`.

- **Whole-unit pay, x10 (17 Nov).** Stage 1, soft break 5, finish 10, well -10, time-limit
  penalty -5, instead of 0.1, 0.5, 1, -1, -0.5. Task: shop step 2, compiled chain `step2-a3`. At x1
  it serves 0 at 2M steps; its x10 copy learns on 3 of 3 seeds (18.15, 18.15 and 12.42 served per
  episode; 18.15 is the best on those seeds). A hand-written +1-per-stage machine learns at x1 and at
  x0.1 (16.08, 15.72, 17.59), so the compiler's pay size stopped the compiled machine, not its clause
  structure. Mechanism not proven. User decision 2026-11-17, in the code since commit `deff802`.
  Sources: `evidence/pay-unit-x10-runs.md`, `evidence/pay-unit-x10-decision.md`,
  `../../decisions/arm-fm/rm-execution.md:256`.
- **x10, generated machine.** Task: shop step 2 as the generator writes it (`step2-generated`). x10
  learns on seeds 1 to 3 (18.15 each); x1 learned on seed 1 only. Same note as the line above.
- **x10, shop step 3 and box carry.** Step 3 (`step3-a3`, 16 states) serves 0 at x1 and at x10 by
  2.3M steps: ordering raises the end charge (-23), so the agent never orders. Scale fixes step 2, not
  step 3. Box carry ("pick it up at once", B6): learned on 6 of 6 runs at x1 and at x10.
  Sources: `evidence/pay-unit-x10-runs.md`, `evidence/pay-unit-x10-ledger.md`.
- **Soft break size S 5, 2.5, 1 and hard break flat or ceiling (19 Nov).** Task: the zombie garden
  `lanes-rules` (the soft breaks repeat, hard top lane). 6 arms, 3 seeds each, 100 greedy episodes,
  promise cost off (the summary counts 24 runs with the fear card `cx-goal-many-rules`, where nothing
  learned: the key is never held). "Held" is the share of episodes with no top breach.
  - S 5, flat hard -10 (the default before): held 0.00, 0.80 side breaches a game; the guard pays
    -23.25 against -10 for ignoring the top lane, so ignoring is cheaper.
  - S 2.5, flat: held 0.00 (idle-like).
  - S 1, flat: held 0.42 (0.33 to 0.53), 10.64 side breaches.
  - S 1, ceiling (hard break -96.1): held 0.56 (0.34 to 0.96), 13.95 side breaches; best recurrent
    arm, the only one that passes the pay-order check, wide spread over seeds.
  - S 2.5, ceiling (hard break -238.7): held 0.00, 3.82 side breaches, idle-like.
  - S 2.5, charged once (reference, not used): held 0.87 (0.87 to 0.88), 16.38 side breaches.
  - Reading: the soft size matters more than flat against ceiling; S 2.5 or more collapses to idle.
    The default since 19 Nov is S 1 with the ceiling.
  Sources: `evidence/e2-summary.md`, `../../decisions/arm-fm/rm-execution.md:261` (pay-ceiling
  entry).
- **Soft break size plan (18 Nov).** The plan was S 2.5, then 2, 1.5, 1 from the S 5 of the x10 pay.
  Only 5, 2.5 and 1 were run (the line above). Source: `evidence/soft-break-size-plan.md`.
- **Shop step 2 at x10, five arms (18 Nov).** Task: shop step 2 (`step2-a3-x10`), 2M steps, 3 seeds
  per arm. A base: 0 served. B value clip 0.1: 0. C value clip off: 0. D promise cost on: 11.1 to
  12.2 served, 3 of 3 learn. E end judgment on: 12.4 to 18.2, 3 of 3 learn. The shop needs a signal
  at the time-limit cut; the clip does not decide learning. The PPO clip stays 0.2. Source:
  `evidence/shop-arms-round6.md`.
- **`ppo_reward_scale` 0.1 and 0.01 (19 to 20 Nov).** A multiplier on the reward PPO trains on (logged
  returns stay unscaled). Task: `lanes-rules` (top breach -96 against -1 side prices). Unscaled PPO:
  RM -29.85, and -23.79 at 6M steps. Scale 0.1: -22.10; scale 0.01: -20.81; 0.01 with value clip off:
  -21.52; 0.1 with entropy decay (round R3): -18.89, the best plain line; 0.01 with decay: -20.32;
  0.1 with decay at 6M: -18.85. It leaves the idle plateau at 0.5 to 1.2M steps instead of 1 to 1.5M
  and improves the top guard; no setting brings side defence. The two-line change is uncommitted in
  worktree `tp-lanes-tune`. Sources: `../zombie-garden-warm-start/evidence/lanes-tune-report.md:54-58`
  and `:97-102`, `../zombie-garden-warm-start/evidence/ppo_reward_scale.diff`.
- **Value clip off, with the -96 price (19 Nov).** Task: `lanes-rules`. `ppo_clip_vloss: false` loses
  all randomness within 120k steps on 9 of 9 runs (actor and value share one network and returns reach
  96); the 0.1 value clip keeps it alive. Source: `evidence/value-clip-lanes.md`.
