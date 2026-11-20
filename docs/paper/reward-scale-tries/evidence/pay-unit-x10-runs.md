  arrival -0.3, failed rewards -1/-0.5) serves 0 at 2M, but its copy with every pay and failed reward x10 learns
  (seeds 1-3 judged 18.15, 18.15, 12.42 greedy served/ep; 18.15 is the shop's best on those seeds). The hand +1-per-stage machine learns at x1
  and at x0.1 (16.08, 15.72, 17.59). So the compiler's pay magnitude, not the chain's clause structure, stops its machines under
  PPO P1 (clip 0.2, gamma 0.995, lr 1e-3, entropy 0.01). Mechanism not proven; note a compiled full service nets 0,
  so its only signal is avoiding the end charges.
- 2026-11-17 08:17: `step2-generated` x10 learns step 2 on seeds 1-3 (18.15 each), where x1 learned on seed 1 only.
  Step 3 is different: the A3 step-3 try (`step3-a3`) serves 0 at x1 and at x10 by 2.3M. Every episode stops in the
  arrived state (return -14 at x10): taking the order raises the cut charge (-23), so the agent never orders. Scale
  fixes step 2; step 3 also needs the cut charge to fall with each stage (test running).
- 2026-11-17 09:00 shop PPO gotcha: all 16 envs run fixed 600-step episodes in lockstep, so the time-limit cut and its
  end charge land in the same iterations (about 43% of them). Split value_loss and explained_variance by cut and
  no-cut iterations; unsplit EV (about 0.97) hides cut iterations at EV 0.11. A large end charge with a time-blind
  critic is advantage noise; on the A3 step-3 machine at x10 the policy flips between never ordering and picking up,
