# Lanes tune rounds

Worktree `/home/turbotowerlnx/orca/workspaces/TFM-schema-rm-rl/tp-lanes-tune` (branch MiquelGomezCorral/tp-lanes-tune,
uncommitted, tooling in `outputs/lt/`). Base config = E3 `e3-lanes-live-2x` (16 envs x 256 steps, 16 minibatches,
10 epochs, lr 1e-3 annealed, clip 0.1 (also value clip), ent 0.01, gamma 0.99, lambda 0.95, one-hot, RM reward only),
plus `eval_frequency: 50000` (eval only; E3 used 10000). Judge: `outputs/lt/lt_judge.py` = test-rl --judge, 100 greedy
episodes, seeds 2000000+; metrics checked against E3 2x (same numbers).

Baseline (E3 2x, 3M): top 0.88/0.80/0.91, side 16.8/16.2/16.8, plants 0.13/0.10/0.18, RM -28.4/-35.5/-25.6.
Targets: top >= 0.88, side <= 5.5, plants <= 0.2, RM >= scripted guard -17.06, on 3/3 seeds.

## R1 (started 20:05)

Hypothesis: the critic cannot fit returns of size ~30-96 because the value clip is 0.1 in absolute return units
(`ppo_clip_coef` also clips the value; EV ends 0.65), and 3M steps with lr annealed to 0 stop training while it is still
improving (top-lane guard only learned between 0.75M and 3M). Bad advantages + early stop leave it at "guard the top".
Variants (3 seeds each):
- `vl`: `ppo_clip_vloss: false`.
- `vlent`: `vl` + entropy 0.01 -> 0.001 over 3M (sampled policy is far worse than greedy; less noise may make side trips safe).
- `vl6m`: `vl` + 6M steps.
- `base6m`: E3 settings + 6M steps (length control).

R1 result (20:07, early stop): every value-clip-off run (vl, vlent, vl6m; 9/9) collapsed to entropy 0.00 within
30k-120k steps and froze as an idle agent (eval RM -98.3). Killed (my PIDs). Reading: without the clip the critic
chases returns of -96 through the shared conv trunk (one trunk for actor and critic, `ppo.py:97`), the trunk features
grow and the actor logits blow up. The 0.1 value clip was what kept the policy alive, at the price of a critic that can
move only 0.1 return units per update (EV ends 0.65). So the scale of the reward (-96 vs -1) against a shared net is
the problem, not the clip itself. `base6m` (E3 settings, 6M) keeps running as the length control.
Next: scale the reward PPO trains on (code: `ppo_reward_scale`, 2 lines), so values are ~1 and the clip is no longer
binding.

## R2 (started 20:07)

Hypothesis: with the training reward scaled down (top -0.96 or -9.6, side -0.01 or -0.1) the critic fits without
blowing up the shared trunk, advantages get better, and the agent moves past top-only guarding.
Change: new setting `ppo_reward_scale` (training reward only; logged and judged returns unscaled;
`app/src/arm_fm/ppo.py` collect, `app/src/config/config.py`). Variants, 3M:
- `rs01`: scale 0.1. - `rs001`: scale 0.01. - `rs001vl`: scale 0.01 + value clip off.

## Handoff (20:11, outgoing agent -> xhigh agent)

**Running (all mine, leave them; 12 trainings, ~850-1500 steps/s each at 20:10):**
- Supervisors (`outputs/lt/lt_run.py`, systemd scopes `lt-R1`, `lt-R2`): pid 1663429 (LT_QUEUE=outputs/lt/queue-R1.json),
  pid 1672792 (queue-R2.json). Each judges its queue automatically when all its runs end:
  `outputs/lt/lt_judge.py` -> `outputs/lt/judge-queue-R1.out` / `judge-queue-R2.out`. Supervisor log
  `outputs/lt/logs/supervisor.log`, run logs `outputs/lt/logs/<run>.log`. R1's queue also lists the 9 killed vl* runs: the
  judge prints "no finished run" for them, expected.
- R1 `base6m` (E3 settings, 6M): s1 pid 1669741, s2 1670276, s3 1670920; dirs `/home/turbotowerlnx/orca/workspaces/TFM-schema-rm-rl/tp-lanes-tune/outputs/runs/lt-R1-base6m-s{1,2,3}/seed*`;
  ~290k at 20:10, expected end ~21:50-22:10 (+3 min final test, + judge).
- R2 (3M, `ppo_reward_scale`): rs01 s1/s2/s3 pids 1672793/1673251/1673471; rs001 1674207/1674799/1675455; rs001vl
  1675705/1675937/1676157; dirs `/home/turbotowerlnx/orca/workspaces/TFM-schema-rm-rl/tp-lanes-tune/outputs/runs/lt-R2-<variant>-s<seed>/seed*`; 60k-176k at 20:10, expected end ~21:05-21:25.
- Progress: `python outputs/lt/lt_status.py outputs/lt/queue-R2.json [--log N]` (last train row: step, entropy, EV, sps,
  last eval RM greedy/sampled). Kill only by PID after checking cmdline contains the run's yaml name.

**Judged so far:** nothing of R1/R2 (no run finished). Step 1 is done (table below, scripted, `outputs/lt/policies.py`,
100 test seeds, own RM sum checked against E3 numbers: idle and guard match E3 exactly; `lt_judge.metrics` reproduces E3 2x):

| Policy (sees full grid) | Top held | Side/ep | Plants/ep | Kills/ep | Len | RM return | Disc. RM (g 0.99) |
|---|---|---|---|---|---|---|---|
| idle | 0.00 | 1.98 | 0 | 0 | 79 | -98.08 | -47.67 |
| top_only (only top-lane zombies) | 0.99 | 17.43 | 0 | 9.6 | 299 | -18.39 | -3.81 |
| guard (forcing_envs scripted) | 0.88 | 5.53 | 0 | 20.4 | 289 | -17.06 | -2.74 |
| gp8 (top first, side only if route <= 8) | 0.93 | 6.26 | 0 | 20.3 | 292 | **-12.99** | -2.32 |
| gp8m (top first, middle lane only if route <= 8) | 0.97 | 10.01 | 0 | 17.5 | 298 | -12.89 | -2.25 |
| gp12p33 (route <= 12, wait at (3,3)) | 0.92 | 6.13 | 0 | 20.8 | 295 | -13.82 | **-1.76** |
| rollout(gp8), H30 K3, futures redrawn | 0.99 | 12.09 | 0.03 | 14.1 | 300 | -13.08 | -2.22 |
| PPO E3 3M (mean 3 seeds) | 0.86 | 16.6 | 0.14 | 8.7 | 288 | -29.85 | ~-5.5 |
Conclusion: a better policy exists and uses only what the agent observes (full grid; gp* need no hidden state). PPO is
not even a good top-only guard (-29.9 vs scripted top_only -18.4); best scripted -12.9 (+30% over top_only, +57% over PPO).
Other gp variants in `policies.py` (names gp{3,5,8,12,99}[p33|p53][m]). A rollout run with H60 K6 was stopped unfinished
(CPU needed by training).

**Diagnosis so far (helper brief + R1):** RM reward only (kill +1 not trained), no reward/obs normalisation, shared conv
trunk for actor and critic (`ppo.py:97`), value clip = `ppo_clip_coef` 0.1 in absolute return units, returns ~30-96;
EV ends 0.65; E3 sat at the idle plateau (-98) until 0.75-1.1M and was still improving at 3M while lr annealed to 0; no
entropy collapse in E3 (ent 0.5-0.9), sampled policy much worse than greedy (-49..-64 vs -25..-35). R1: value clip off ->
entropy 0 in <120k steps, 9/9 (killed). The RM one-hot is constant [1,0] (u1 terminal). 56% of E3 wall time was
eval (now `eval_frequency: 50000`).

**Current best hypothesis:** the reward scale (-96 per top breach, value targets ~100) against a shared actor-critic
trunk is the root: the critic either is choked by the 0.1 value clip (E3) or blows up the trunk (clip off). Scaling the
training reward (R2) should give a usable critic; then length (base6m tells whether 3M is simply too short) and the
entropy level (sampled top breaches make side trips look risky) are next.

**Code change (uncommitted, worktree):** `ppo_reward_scale: float = 1.0` in `app/src/config/config.py` (after
`ppo_vf_coef`), and `reward = reward * CONFIG.ppo_reward_scale` in `PPORunner.collect` (`app/src/arm_fm/ppo.py`, after the
reward tensor is built, before timeout bootstrap). Not a hack (standard reward scaling), but list it in the report.

**Exact next step:** when R2 ends (~21:10-21:25), read `outputs/lt/judge-queue-R2.out` (or run
`PYTHONPATH=app python outputs/lt/lt_judge.py outputs/lt/queue-R2.json`), write the R2 result here. Then R3 (up to 9
free slots until base6m ends): take the best scale and test, 3 seeds each, e.g. `<best>` + 6M steps, `<best>` + entropy
decay 0.01->0.001 (`ppo_ent_coef_start`, `ppo_ent_coef`, `ppo_ent_decay_steps`), `<best>` + lr 3e-4. Make a round with
`python outputs/lt/make_round.py R3 'name:{json overrides}' ...`, launch with
`LT_QUEUE=outputs/lt/queue-R3.json LT_MAX_MINE=<free slots> PYTHONPATH=app nohup systemd-run --user --scope --unit=lt-R3 -- <python> outputs/lt/lt_run.py > outputs/lt/logs/sup-R3.out 2>&1 &`
(run alone, not inside an && chain). Hacks kept in reserve: `reward_source: both` (adds the +1 per kill env reward).
RM graph already drawn: `outputs/lt/svgs/lanes-rules.{svg,html}` (render-rm --html), for the hub page.

## Continuation (xhigh agent, from 20:12)

Adopted the 12 runs (all alive at 20:12, pids as in the handoff).

**Diagnosis check: the on-policy cliff (20:24).** `outputs/lt/noise_check.py` (-> `noise_check.out`): each scripted
policy takes a uniform random action with probability eps, same 100 test seeds, same machine.

| eps | top_only RM | gp8m RM | gp8 RM | guard RM | gp8 top held |
|---|---|---|---|---|---|
| 0.00 | -18.39 | -12.89 | **-12.99** | -17.06 | 0.93 |
| 0.05 | -23.66 | -18.86 | **-16.02** | -25.34 | 0.91 |
| 0.10 | -23.71 | **-21.99** | -31.48 | -36.10 | 0.75 |
| 0.20 | -29.87 | **-26.26** | -47.67 | -54.54 | 0.58 |
| 0.30 | **-50.75** | -58.12 | -78.37 | -78.99 | 0.25 |

Side trips pay only while the policy is nearly deterministic: at eps 0.10 the two-lane guard is already worse than
top-only, at 0.20 it loses 18 RM. eps 0.05/0.10/0.20/0.30 is entropy about 0.25/0.45/0.76/1.03 nats; E3 PPO ended at
entropy 0.5-0.9. PPO is on-policy: it optimises the sampled policy, and for that policy staying top is right (cliff
walking: SARSA keeps the safe path). Noisy top_only at eps 0.20 gives top 0.86, side 16.3, RM -29.87: the E3 PPO numbers
(0.86, 16.6, -29.85). So the fix to test is sharpening the policy during training (entropy bonus to 0), after the critic
fix of R2.

## R3 (queued 21:12, starts as R2 slots free; supervisor pid 1891556, unit lt-R3, E3_MAX_TOTAL=12)

Hypothesis: the on-policy cliff (noise check above). PPO keeps entropy 0.3-1.2 (R2 at 2.6M: rs01 0.3-0.6, rs001 0.9-1.2),
a noise level at which side trips lose, so it stays top-only. Decaying the entropy bonus to 0 sharpens the sampled
policy below the crossover (eps ~0.05, entropy ~0.25), and side trips start to pay inside PPO's own estimates.
Change: entropy bonus 0.01 -> 0 linearly (`ppo_ent_coef_start: 0.01`, `ppo_ent_coef: 0.0`). Variants, seeds 1-3:
- `rs01ed`: scale 0.1, decay over 2.5M, 3M. - `rs001ed`: scale 0.01, decay over 2.5M, 3M.
- `rs01ed6m`: scale 0.1, decay over 5M, 6M.

### R2 result (judged 21:23, `outputs/lt/judge-queue-R2.out`)

| Run | Top held | Side/ep | Plants/ep | Kills/ep | RM | Disc. RM |
|---|---|---|---|---|---|---|
| rs01 s1/s2/s3 | 0.94/0.96/0.94 | 16.8/17.3/16.5 | 0.12/0.10/0.16 | 9.1/9.1/9.7 | -22.66/-21.21/-22.44 | -4.72/-4.12/-3.96 |
| rs001 s1/s2/s3 | 0.97/0.96/0.96 | 17.2/17.2/17.1 | 0.09/0.13/0.17 | 9.1/9.3/9.3 | -20.18/-21.19/-21.06 | -4.14/-3.89/-4.09 |
| rs001vl s1/s2/s3 | 0.93/0.97/0.97 | 17.0/17.3/17.3 | 0.14/0.20/0.08 | 9.0/9.1/9.2 | -23.91/-20.42/-20.24 | -4.63/-4.04/-4.21 |

Conclusion: reward scaling fixes the critic side: it leaves the idle plateau at 0.5-1.2M instead of 1-1.5M and gives a
reliable top guard on 9/9 seeds (top 0.93-0.97 vs E3 0.80-0.91; RM -20.2..-23.9 vs E3 -25.6..-35.5), close to scripted
top_only (0.99, -18.39). Side breaches stay at top_only level (16.5-17.3 vs 17.43): no side defence at all. Final
entropy 0.3-0.6 (rs01) and 0.9-1.1 (rs001): above the crossover, as the cliff predicts. Best scale 0.01 (-20.81 mean);
value clip off adds nothing at that scale. Next: R3 (already running) sharpens the policy.

### R1 base6m result (judged 22:46, `outputs/lt/judge-queue-R1.out`): length control, E3 settings at 6M

| Run | Top held | Side/ep | Plants/ep | Kills/ep | RM | Disc. RM |
|---|---|---|---|---|---|---|
| base6m s1/s2/s3 | 0.97/0.93/0.88 | 16.95/16.26/16.65 | 0.10/0.17/0.09 | 9.2/9.7/8.6 | -19.93/-23.16/-28.27 | -4.68/-4.44/-5.33 |

Where the agent is (`outputs/lt/where.py`, replay of the 100 judged traces): top row 74-80% of steps, rows 6-9 0%;
kills per episode in the middle lane 0.00/0.63/0.00, bottom lane 0. R2 rs001-s1 and rs01-s2: middle and bottom kills 0.00.
Conclusion: 6M steps at E3 settings reach what scaling reaches at 3M (a better top guard) and still no side defence.
Length alone is not the fix.

## R4 (started 22:47 with 3 runs, all 9 from 22:57; supervisor unit lt-R4b)

Hypothesis: the agent never visits the states where a side trip starts (replay: rows 6-9 never, middle kills ~0), so
PPO has no data to learn trips, sharp policy or not. More early state coverage, or a shorter horizon that makes a trip
worth more against the top risk, should give it that data and that incentive.
Base for all: R3 `rs01ed` (scale 0.1, entropy 0.01 -> 0 over 2.5M, 3M). Variants, seeds 1-3:
- `eps`: + forced random start `ppo_epsilon_start: 0.5` -> 0 over 1.5M (behaviour = mixture with uniform; PPO's
  ratio uses the mixture, plain setting).
- `g95`: + `gamma: 0.95` (a top breach 27 steps out weighs 0.25 instead of 0.76; pay order still holds: soft stream
  bound 1/(1-0.95) = 20 < 96).
- `both`: + `reward_source: both` (+1 env reward per kill on top of the machine) - **hack, diagnostic only**: if a
  kill bonus makes it defend side lanes, the blocker is exploration/credit, not capacity or observation.

### R3 result, 3M variants (judged 22:58, `outputs/lt/judge-queue-R3a.out`; rs01ed6m still running, ends ~00:50)

| Run | Top held | Side/ep | Plants/ep | Kills/ep | RM | Disc. RM | Middle kills/ep (replay) |
|---|---|---|---|---|---|---|---|
| rs01ed s1/s2/s3 | 0.98/0.97/1.00 | 17.30/16.62/17.52 | 0.12/0.16/0.15 | 9.7/10.1/9.5 | -19.34/-19.66/**-17.67** | -3.74/-3.81/-3.71 | 0.19/0.67/0.00 |
| rs001ed s1/s2/s3 | 0.95/0.97/0.99 | 17.12/17.36/17.42 | 0.18/0.15/0.09 | 9.0/9.3/9.4 | -22.10/-20.39/-18.47 | -4.35/-4.00/-3.83 | 0.00 (s1) |

Conclusion: sharpening works for what the agent already does: rs01ed is the best top guard so far (top 0.97-1.00,
RM mean -18.89, s3 -17.67 beats scripted top_only -18.39 and nears scripted guard -17.06). It does not create side
defence: side 16.6-17.5, rows 6-9 never visited, middle kills 0-0.67/ep (only near the start cell, which is in the
middle lane). So the cliff is real but not the only blocker: the trips are never tried. Next: R4 (exploration and
horizon), already running.

R4 change at 23:11: `g95` cannot run. train-rl refuses it: the bundle prices the hard break for gamma 0.99
("prices the hard break for gamma 0.99, step limit 300 and 1 soft breaks per step, but this run has gamma 0.95 ...;
run rebuild-rewards"). Rebuilding changes the machine's rewards, which the task forbids, so gamma is fixed at 0.99 for
this machine (finding, not a failure of the idea). Its 3 slots went to:
- `R4c-lam99`: R3 `rs01ed` + `ppo_gae_lambda: 0.99` (credit: a side breach lands 10-30 steps after the trip
  decision; with lambda 0.95 the advantage keeps (0.99*0.95)^25 = 0.21 of it, with 0.99 it keeps 0.61). Started 23:11.

**Shrinking-rounds rule (user, 23:37) applied here.** Cases = the 3 seeds of the card. No seed has passed yet, so each
new variant runs on all 3 failing seeds; once a variant passes some seeds, the next round reruns only its failing
seeds plus the passing ones as regression checks (3 seeds is fewer than 4-5); when all 3 pass, one confirming rerun of
all 3. Runs started so far: R1 12 (9 killed early), R2 9, R3 9, R4 12 (3 refused at start) = 42. Plan: running now 12
(R3 6m 3, R4 eps 3, both 3, lam99 3); R5 <= 9; R6 <= 9; confirmation 3 if a winner. Loop total <= 63, far under 1000.

## R5 - can PPO keep a better policy? (diagnostic, a hack)
Hypothesis: top-only is a local optimum PPO cannot explore out of; the objective itself prefers trips at low noise
(noise check: at eps 0.05, gp8 -16.0 vs top_only -23.7). If PPO starts from a policy that already makes side trips,
the same machine and settings keep the trips and repair the top lane. If the trips vanish again, the problem is the
objective under PPO's own noise, not exploration.
How: `outputs/lt/bc.py` clones the scripted `gp8` into the PPO network (behaviour cloning + 4 DAgger rounds, seeds
3000000+, critic fitted to scaled discounted RM returns). Clone on the 100 test seeds, greedy: top 0.67, side 6.26,
plants 0.73, RM -38.70 (round 0: top 0.33 side 5.42; train accuracy 99.5% on every action). So the network and the
image are enough to represent side defence (side 6.3 vs PPO 16-17); its top failures are DAgger covariate shift.
Variant `bcft` = R3 rs01ed + `init_from: outputs/lt/bc-gp8`, 3M, seeds 1-3, started 00:26. Hack: init from a
scripted-policy clone. A 12-round DAgger clone (`bc-gp8-12`) is being built in the background.

### R4 results (3M, judged like E3: 100 greedy test episodes, seeds 2000000+)
| variant | top held s1/s2/s3 | side/ep | plants/ep | RM s1/s2/s3 (mean) |
|---|---|---|---|---|
| eps (rs01ed + epsilon 0.5->0 over 1.5M) | 0.98/0.97/0.99 | 16.72/16.67/16.68 | 0.18/0.15/0.19 | -18.82/-19.70/-17.83 (-18.79) |
| both (rs01ed + reward_source both, HACK) | 0.95/0.98/0.96 | 16.55/11.02/17.01 | 0.05/0.20/0.10 | -21.40/-13.14/-20.95 (-18.50) |
| g95 | refused at start (gamma locked by the machine's pricing) | | | |
Replay (where.py): eps-s1 rows top 0.45 / 2-4 0.36 / mid 0.19 / 6-9 0.00, kills top 9.34 mid 0.65 bottom 0.
both-s2 rows top 0.11 / 2-4 0.42 / mid 0.47 / 6-9 0.00, kills top 9.18 mid 6.64 bottom 0: with the env's +1 kill
reward one seed learns a two-lane guard (sits in the middle lane, runs up for top zombies) and beats the scripted
guard on RM (-13.14 vs -17.06), but never covers the bottom lane (side 11.0 > 5.5). The other two seeds stay top-only.
Verdict: forced uniform exploration does nothing (same top-only policy, RM equal to rs01ed). A dense, immediate kill
signal can pull PPO off the plateau sometimes (1 of 3), which points at credit/signal strength, not representation.
Not a pass, and `both` is a hack (it trains on env reward the machine does not define).

### R3 6M result (rs01ed6m: rs01ed, 6M, entropy 0.01->0 over 5M)
top 0.96/0.99/1.00, side 16.57/17.43/17.52, plants 0.09/0.08/0.06, RM -20.50/-18.47/-17.58 (mean -18.85).
Replay: top row 74-81%, rows 6-9 0%, middle kills 0.59/0/0. Twice the training gives the same top-only policy:
more steps alone do not help. s3 (RM -17.58, top 1.00) is the best top-only PPO so far, still short of guard -17.06.

## R5b - bigger batch of parallel episodes (plain setting)
Hypothesis: the trip signal (+1 RM per breach avoided, 0.1 scaled) is buried under the -96 top-breach advantages after
per-minibatch normalization; 64 parallel envs (x 128 steps, batch 8192 instead of 4096) give 4x more episodes per update
and twice the batch, so rare accidental trips average in more often and the noise drops.
Variant `n64` = rs01ed + ppo_num_envs 64, ppo_num_steps 128. 3M, seeds 1-3, started 00:38.

### Diagnosis check: does the critic see side zombies? (`outputs/lt/critic_check.py`)
Greedy play of trained top-only agents on 30 test seeds; least-squares fit of the critic value (unscaled, RM units)
and of the realised discounted RM return on the number of side-lane zombies alive (plus top-lane count):
- rs01ed6m-s3: critic -1.16 per side zombie (realised -0.49), corr(V, G) 0.17, 9000 states.
- rs01ed-s1: critic -1.31 per side zombie (realised -0.77), corr(V, G) 0.38, 8979 states.
The critic does price a side zombie at about one breach (-1). So the value side is not blind; what is missing is a
policy that ever tries a trip at low noise. Low corr(V, G) shows how noisy single returns are (rare -96 breaches).

### R4c result (lam99: rs01ed + gae_lambda 0.99, 3M)
top 0.93/0.81/0.98, side 16.94/16.33/17.47, plants 0.13/0.25/0.39, RM -23.80/-34.84/-19.78 (mean -26.14).
Replay: rows 6-9 0%, middle kills 0.01-0.05. Longer credit makes it worse (noisier advantages, slower top guard); no
side defence. Credit horizon is not the blocker (fits the critic check: the critic already prices side zombies).

### R5 early (bcft, PPO from the gp8 clone): greedy eval RM at about 0.8M: -12.9 / -13.4 / -13.6 (all 3 seeds beat the
guard's -17.06). Sampled soft cost per held episode stays about 12 (top-only PPO: 16.6-17.0). PPO keeps and improves the
side trips when it starts with them.
## R5c - does a weak warm start suffice? (hack, diagnostic)
`bcftd0` = rs01ed + init_from `bc-gp8-d0` (plain behaviour cloning on 120 expert episodes, no DAgger; clone alone:
top 0.27, side 4.46, plants 0.87, RM -75.48). Started 00:49, seeds 1-3, 3M.

### R5 mid-run (01:08)
- bcft (clone after 4 DAgger rounds): sampled soft cost per held episode 12.8 -> 12.1 -> 11.4 at 0.5/1.0/1.5M, held 0.91.
  Trips survive and the top guard repairs.
- bcftd0 (plain BC clone, top 0.27): soft per held episode 16.7 at 0.5M and 16.5 at 1.0M, held 1.00 - PPO dropped the
  trips while it learned the top guard. A weak warm start is not enough: trips that come with frequent top breaches
  are pruned, and once pruned PPO never tries them again (on-policy cliff, seen directly).
- n64: top-only (soft per held episode 16.8 at 2M). It runs 2x faster (1250 sps vs 650) but learns the same thing.
## R5d - dose-response of the warm start (hack, diagnostic)
`bcft12` = rs01ed + init_from `bc-gp8-12` (12 DAgger rounds; clone alone: top 0.80, side 6.69, plants 0.27,
RM -26.18). Predicts: at least as many trips kept as bcft. Started 01:08, seeds 1-3, 3M.

### R5b result (n64: 64 envs x 128 steps, 3M)
top 0.97/0.94/0.99, side 17.26/16.88/17.42, plants 0.18/0.18/0.16, RM -20.32/-22.83/-18.54 (mean -20.56).
Top-only again. Bigger batch of parallel episodes does not surface trips. Plain-setting lines tried without side
progress: reward scale (R2), entropy decay (R3), 2x length (R3 6M), forced epsilon exploration (R4), lambda 0.99 (R4c),
64 envs (R5b). Gamma is locked by the machine's pricing.

### R5 result (bcft: PPO from the 4-round DAgger clone of gp8, same machine and settings as R3 rs01ed, 3M)
| seed | top held | side/ep | plants/ep | kills/ep | RM |
|---|---|---|---|---|---|
| s1 | 0.99 | 10.33 | 0.31 | 17.5 | -11.60 |
| s2 | 1.00 | 10.08 | 0.64 | 18.2 | -10.72 |
| s3 | 0.98 | 10.09 | 0.38 | 17.7 | -12.39 |
| mean | 0.99 | 10.17 | 0.44 | 17.8 | -11.57 |
Replay: the agent lives in the middle lane (rows: mid 47-61%, top 22-38%, 2-4 14-20%, 6-9 0-1%), runs up for every
top zombie and kills the middle ones (top 9.6-9.8, middle 7.9-8.4, bottom 0 kills/ep). A two-lane guard, like the
scripted gp8m (top 0.97, side 10.01, RM -12.89) but better on RM: the best RM of any policy here, scripted ones included
(gp8 -12.99, rollout -13.08, guard -17.06). PPO dropped the clone's bottom-lane trips: they are 8 rows from the top and
cost top safety (clone top 0.67-0.80); the RM rates top 0.99 + two lanes above top 0.93 + three lanes.
Against the bar: top >= 0.88 yes; RM >= -17.06 yes; side 10.2 is not <= 5.5 but matches the two-lane better policy
gp8m (10.0); plants 0.31-0.64 > 0.2: FAIL on all 3 seeds. And it rests on a hack (scripted-policy clone as init).
## R6 - continue the fine-tuned agents at zero entropy (hack line)
Hypothesis: the trampled plants (-1 each) are residual path noise; 2M more steps per seed from its own R5 weights, with
entropy 0 and lr 3e-4, remove them without losing the two-lane guard.
Variant `cont`: init_from lt-R5-bcft-sN (per seed), ent 0, lr 3e-4 annealed, 2M. Started 01:55.
Shrinking-rounds count: all 3 seeds fail (plants), so all 3 rerun. Runs started so far: 54 + 3 = 57.

### R5c result (bcftd0: PPO from the plain BC clone, no DAgger, 3M)
top 0.99/0.98/0.97, side 17.42/17.45/16.80, plants 0.04/0.05/0.05, RM -18.42/-19.42/-19.73 (mean -19.19).
Top-only again: a clone that loses the top lane 73% of the time hands PPO trips that cost top breaches, so PPO prunes
them while it learns the top guard, and never finds them again. The warm start works only when the clone already
holds the top lane well enough (R5 clone 0.67) for trips to pay.

## R6b - env kill reward first, then the machine alone (hack line, no scripted policy)
Hypothesis: the R4 `both` runs (RM + the env's own +1 per kill) are a warm start that needs no hand-written expert.
Continued on the machine reward alone, a run that already guards two lanes (both-s2) keeps them, as bcft did; runs
that are top-only (s1, s3) stay top-only. Variant `bothrm`: init_from lt-R4-both-sN (per seed), reward_source rm,
ent 0, lr 3e-4 annealed, 2M. Started 02:18. Runs started so far: 60.

### R5d result (bcft12: PPO from the 12-round DAgger clone, 3M)
top 1.00/0.99/1.00, side 9.83/9.86/9.87, plants 0.44/0.52/0.53, kills 18.3-18.4, RM -10.27/-11.34/-10.40 (mean -10.67).
Replay: middle lane 33-61% of steps, rows 6-9 0-2%; kills top 9.7, middle 8.6-8.7, bottom 0. Same two-lane guard as R5,
a bit better (best RM of the loop). Dose-response holds: plain clone -> top-only (-19.19); 4-round clone -> -11.57;
12-round clone -> -10.67. PPO drops the clone's bottom-lane trips every time and keeps the top lane at 0.99-1.00: for
this agent the machine's prices favour top + middle over three lanes (gp8, three lanes: -12.99). The bar's side <= 5.5
and plants <= 0.2 ask for more than the RM rewards here. Plants fail on all 3 seeds.

### R6 result (cont: R5 agents + 2M at entropy 0, lr 3e-4)
top 1.00/1.00/1.00, side 9.85/9.74/10.08, plants 0.34/0.51/0.36, RM -10.19/-10.25/-10.44 (mean -10.29).
Best RM of the loop, but plants barely move (0.44 -> 0.40) and side stays at the two-lane level. The scripted
policies trample 0 plants, so about 0.4 RM a game is still left on the table; more on-policy training does not find it.
Plants fail on all 3 seeds.

### R6b result (bothrm: R4 both agents + 2M on the machine reward alone, entropy 0, lr 3e-4)
top 0.98/1.00/0.99, side 16.60/11.05/16.79, plants 0.07/0.17/0.09, RM -18.59/-11.22/-17.84 (mean -15.88).
As predicted: the seed that had learned a two-lane guard with the kill bonus (s2) keeps it on the machine reward alone
(RM -11.22, plants 0.17, side 11.05 near gp8m's 10.0); the top-only seeds stay top-only. The machine keeps a two-lane
guard once one exists, whatever produced it; it cannot make PPO find one. 1 of 3 seeds: no pass.

## Stop (03:00)
Six rounds (R1-R6) done. Plain-setting lines (scale, entropy decay, 2x length, epsilon, lambda, 64 envs; gamma locked)
all end top-only. The hack lines show why and reach RM -10.29, but none passes the bar on 3 of 3 seeds (plants on the
clone line, seeds on the kill-bonus line). No hypothesis left that a plain setting could test inside the rules.
Runs started in the loop: 60 (9 killed early by the previous agent). Report: lanes-tune-report.md.
