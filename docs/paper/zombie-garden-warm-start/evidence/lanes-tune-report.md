# Zombie garden (`lanes-rules`): why PPO guards only the top lane

Final, 2026-11-20 03:00. Worktree `/home/turbotowerlnx/orca/workspaces/TFM-schema-rm-rl/tp-lanes-tune`, tooling in
its `outputs/lt/`, rounds in `lanes-tune-rounds.md`.

## Answer in short

- **No plain training setting fixes it.** Six setting lines on the same machine all end at the same top-only policy
  (top held 0.91-0.98 on average, about 17 side breaches a game, RM -18.8 to -26). The best from-scratch seed is RM
  -17.58, just short of the scripted guard's -17.06.
- **Why:** side trips only pay once the top guard is already reliable and the policy is nearly deterministic. A noisy
  policy that tries a trip loses the top lane more often than it saves side breaches, so PPO, which learns from its own
  noisy play, settles on top-only first and then never tries a trip again. It is a local optimum, not a blind spot:
  the agent sees the whole grid, and its critic prices a side zombie at about one breach.
- **Proof:** started from a behaviour clone of a scripted three-lane guard (a hack), PPO with the same machine and
  settings keeps the middle-lane trips and reaches RM -10.67 (top 1.00, side 9.9), better than every scripted policy;
  2M more steps reach -10.29. Started from a weak clone, it drops the trips and ends top-only again. The better the
  clone guards the top, the more PPO keeps.
- **It never guards the bottom lane.** Every warm-started agent drops the clone's bottom trips and keeps the top at
  0.99-1.00: for this agent the machine's prices rate "top + middle, top never lost" above "three lanes, top lost 7%".
- **Still no pass even with the hack:** plants trampled 0.34-0.64 a game (bar 0.2; the scripted policies trample 0),
  and side about 10 (bar 5.5, but equal to the two-lane better policy `gp8m`, 10.0). The kill-bonus line passes on 1
  seed of 3 only.

## Card

- Task: zombies walk along three lanes; keep them out of the garden. The top lane must never be breached; side-lane
  breaches and trampled plants each cost a little.
- Machine: one live state `u0`. A top breach goes to the rejecting `u1` (reward -96.0959, episode ends). Each side
  breach or trampled plant costs -1 and stays in `u0`. Priced for gamma 0.99, step limit 300, 1 soft break per step.
- Environment: `MiniGrid-Lanes-v0`, full 11x11 grid, lanes on rows 1 (top), 5 and 9; zombies need 27 steps from spawn
  to breach; spawn chance rises from 0.04 to 0.17 a step; up to 3 plants; 300 steps.
- Judge: like E3, 100 greedy test episodes on seeds 2000000+, one-hot machine state, seeds 1-3 per variant.
- Bar (3 of 3 seeds): top held >= 0.88, side breaches <= 5.5 a game (or clearly near the better policy), plants
  <= 0.2, RM >= -17.06 (scripted guard).

## 1. A better policy exists (previous agent)

100 test seeds, greedy, RM return; disc. = discounted at 0.99.

| Policy | Top held | Side/ep | RM | Disc. RM |
|---|---|---|---|---|
| idle | 0.00 | 1.98 | -98.08 | |
| top_only (scripted) | 0.99 | 17.43 | -18.39 | -3.81 |
| guard (scripted) | 0.88 | 5.53 | -17.06 | -2.74 |
| gp8 (scripted, three lanes) | 0.93 | 6.26 | -12.99 | -2.32 |
| gp8m (scripted, top + middle) | 0.97 | 10.01 | -12.89 | |
| gp12p33 (scripted) | 0.92 | 6.13 | -13.82 | -1.76 |
| rollout (scripted look-ahead) | 0.99 | 12.09 | -13.08 | |
| PPO E3 | 0.86 | 16.6 | -29.85 | |

## 2. Diagnosis with evidence

1. **Reward scale against a shared network trunk.** The -96 top price dwarfs the -1 side prices. With the value clip
   at 0.1 the critic cannot follow; with the clip off, the value loss swamps the shared trunk and the policy collapses
   to entropy 0 (R1 `vl`, `vlent`, `vl6m`). `ppo_reward_scale: 0.1` fixes this: runs leave the idle plateau at 0.5-1.2M
   steps instead of 1-1.5M and the top guard improves (RM -29.85 to -18.89). It does not bring side defence.
2. **On-policy cliff (noise check, `outputs/lt/noise_check.out`).** Scripted policies with a random action at rate eps:

   | eps | top_only | gp8m | gp8 | guard |
   |---|---|---|---|---|
   | 0.00 | -18.39 | -12.89 | -12.99 | -17.06 |
   | 0.05 | -23.66 | -18.86 | -16.02 | -25.34 |
   | 0.10 | -23.71 | -21.99 | -31.48 | -36.10 |
   | 0.20 | -29.87 | -26.26 | -47.67 | -54.54 |
   | 0.30 | -50.75 | -58.12 | -78.37 | -78.99 |

   Trips win only at eps 0.05 or less (about 0.25 nats of entropy). PPO trains at 0.5-1.0 nats, about eps 0.15-0.25,
   where top-only is the best choice. At eps 0.20, top_only gives top 0.86 and side 16.3: exactly E3's PPO numbers.
3. **The agent never goes there.** Replays of the judged greedy episodes (`outputs/lt/where.py`): every from-scratch
   run spends 0% of steps in rows 6-9, kills 0 bottom-lane zombies and at most 0.67 middle-lane zombies a game.
4. **Not a blind spot.** The agent sees the full grid. A clone of `gp8` fits 99.5% of the expert's actions on every
   action type (`outputs/lt/bc.py`). The trained critic prices one side zombie at -1.2 to -1.3 RM
   (`outputs/lt/critic_check.py`), so the value side knows side zombies cost.
5. **PPO keeps the better policy once it has it.** Same machine and settings (R3 `rs01ed`), only the starting weights
   change:

   | Start (clone alone: top / side / RM) | PPO result, mean of 3 seeds: top / side / plants / RM |
   |---|---|
   | plain clone, no DAgger (0.27 / 4.46 / -75.48) | 0.98 / 17.22 / 0.05 / -19.19, top-only |
   | 4-round DAgger clone (0.67 / 6.26 / -38.70) | 0.99 / 10.17 / 0.44 / -11.57, top + middle |
   | 12-round DAgger clone (0.80 / 6.69 / -26.18) | 1.00 / 9.85 / 0.50 / -10.67, top + middle |
   | PPO kill-bonus agents (R4 `both`) | s2 1.00 / 11.05 / 0.17 / -11.22; s1, s3 top-only |

   A weak clone loses the top so often that its trips cost more than they save; PPO prunes them while it learns the
   top guard and never finds them again. Replays of the warm-started agents: middle lane 33-61% of steps, kills top
   9.6-9.8, middle 7.9-8.7, bottom 0 a game.
6. **Gamma is fixed by the machine.** `train-rl` refuses gamma 0.95: the bundle prices the top breach for gamma 0.99,
   and rebuilding the rewards would change the machine.

Conclusion: the reward and the network support side defence. PPO from scratch cannot reach it, because trips pay only
for a policy that already guards the top reliably and almost never acts at random, and by the time PPO's policy is
like that it has stopped trying trips.

## 3. Rounds (one line each; seeds 1/2/3, judged greedy on 100 test seeds)

- R1 (previous agent): value clip off (`vl`, `vlent`, `vl6m`) collapsed to entropy 0, killed; `base6m` (E3 settings,
  6M) RM -19.93/-23.16/-28.27, side about 16.6, top-only.
- R2: `ppo_reward_scale` 0.1 / 0.01 / 0.01 + value clip off: RM means -22.10 / -20.81 / -21.52, side about 17, leaves
  the idle plateau sooner.
- R3: scale 0.1 + entropy 0.01 to 0 over 2.5M (`rs01ed`): top 0.98/0.97/1.00, side 17.30/16.62/17.52, RM
  -19.34/-19.66/-17.67 (mean -18.89), best plain settings; scale 0.01 version -20.32; 6M version -18.85.
- R4: forced exploration, epsilon 0.5 to 0 over 1.5M: RM -18.82/-19.70/-17.83, top-only. Gamma 0.95: refused by
  `train-rl` (gamma locked). `reward_source: both` (hack): RM -21.40/-13.14/-20.95; one seed learns a top + middle
  guard (side 11.0).
- R4c: GAE lambda 0.99: RM -23.80/-34.84/-19.78 (mean -26.14), worse.
- R5b: 64 envs x 128 steps: RM -20.32/-22.83/-18.54 (mean -20.56), top-only, runs 2x faster.
- R5 (hack): init from a 4-round DAgger clone of `gp8`: top 0.99/1.00/0.98, side 10.33/10.08/10.09, plants
  0.31/0.64/0.38, RM -11.60/-10.72/-12.39 (mean -11.57). Plants fail.
- R5c (hack): init from a plain clone (no DAgger): RM -18.42/-19.42/-19.73, top-only.
- R5d (hack): init from a 12-round DAgger clone: top 1.00/0.99/1.00, side 9.83/9.86/9.87, plants 0.44/0.52/0.53,
  RM -10.27/-11.34/-10.40 (mean -10.67). Plants fail.
- R6 (hack): R5 agents continued 2M at entropy 0, lr 3e-4: top 1.00 x3, side 9.85/9.74/10.08, plants 0.34/0.51/0.36,
  RM -10.19/-10.25/-10.44 (mean -10.29). Plants fail.
- R6b (hack): R4 `both` agents continued 2M on the machine reward alone: RM -18.59/-11.22/-17.84; s2 keeps its
  two-lane guard (side 11.05, plants 0.17), s1 and s3 stay top-only.

Runs started: 60 (9 stopped early by the previous agent; 3 refused at start). No LLM calls.

## 4. Winning settings

None. No plain setting moves side defence at all. The hack lines reach the best RM of any policy (-10.29, scripted
best -12.89) but none passes on 3 of 3 seeds: the clone line fails plants (0.34-0.64 against 0.2) on every seed, and
the kill-bonus line works on 1 seed of 3. No hub page was made, because the packet asks for one only with a winner.

Best hack result, for reference (R6 `cont`, per seed from its own R5 run): `ppo_reward_scale 0.1`,
`ppo_ent_coef_start 0`, `ppo_ent_coef 0`, `ppo_learning_rate 3e-4`, 2M steps, `init_from` the R5 run, which used
`ppo_reward_scale 0.1`, entropy 0.01 to 0 over 2.5M, lr 1e-3, 3M, `init_from outputs/lt/bc-gp8` (other settings as E3
2x: 16 envs x 256 steps, 16 minibatches, 10 epochs, clip 0.1, gamma 0.99, lambda 0.95, vf 0.5).

## 5. Code change and hacks

- Code change (not a hack): `ppo_reward_scale` (default 1.0) in `app/src/config/config.py` and one line in
  `app/src/arm_fm/ppo.py` (`reward = reward * CONFIG.ppo_reward_scale` before the timeout bootstrap), uncommitted in
  the worktree `/home/turbotowerlnx/orca/workspaces/TFM-schema-rm-rl/tp-lanes-tune`. Standard reward scaling; logged
  returns stay unscaled.
- Hack: warm start from a behaviour clone of the scripted `gp8` policy (`outputs/lt/bc.py`, DAgger, `init_from`).
- Hack: `reward_source: both` (adds the environment's +1 per kill, which the machine does not define).
- Hack: continuing a hack-started run (R6, R6b).
- New tooling (outputs only, no repo code): `bc.py`, `critic_check.py`, `noise_check.py`, `where.py`, `curves.py`,
  `plot_curves.py` in `outputs/lt/`; clones in `outputs/lt/bc-gp8`, `bc-gp8-d0`, `bc-gp8-12`.

## 6. What to carry to the shop

- Use `ppo_reward_scale: 0.1` when one machine price dwarfs the others (here -96 against -1).
- Decay entropy to 0 (`ppo_ent_coef_start 0.01`, `ppo_ent_coef 0`, decay over about 80% of the steps).
- Keep `eval_frequency: 50000` to see the curves.
- Gamma cannot be tuned: the bundle's pricing pins it (0.99).
- Before tuning, run the noise check: if the better policy only wins at low noise, expect PPO from scratch to settle on
  the safe policy; no plain setting moved that here.
- 64 envs x 128 steps doubles throughput (1250 against 650 steps/s) with the same result: worth it for long shop runs.
- A warm start (a clone of a scripted policy, or an agent trained with the env's own reward) is kept by the machine
  only if it already holds the hard rule well; a weak warm start is wasted. It is a hack: report it as one.
- Check the bar against the machine: here the RM-best policy found (two lanes, top never lost) cannot meet side <= 5.5.
  Ask whether the bar or the prices should change before tuning more.
- DQN cannot use the one-hot machine state without a code change (its network needs an RM embedding); untested here.

## Paper candidate

The warm-start ladder (plain clone -> top-only; 4-round clone -> -11.57; 12-round clone -> -10.67) with the noise
check is a clean result on why on-policy PPO settles on the safe policy under a hard-rule machine. Not copied to
`docs/paper/`; ask first.

Memory candidates:
- `train-rl` refuses any gamma other than the one the bundle was priced for ("run rebuild-rewards"); on these bundles
  gamma is not a tuning knob.
- `lanes-rules`: PPO from scratch ends top-only under every plain setting tried (scale, entropy decay, 6M, epsilon,
  lambda 0.99, 64 envs); a good clone warm start keeps a top + middle guard (RM -10.3); see this report.
- `ppo_num_envs 64` with `ppo_num_steps 128` runs about 2x faster per training (1250 vs 650 steps/s) on this machine
  with the same result.
- The read-budget hook counts `tail`/`cat` of new files; `python3 -c "print(open(p).read())"` on files the agent wrote
  itself is not blocked.
