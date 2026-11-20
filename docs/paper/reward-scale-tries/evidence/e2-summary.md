E2 pricing summary (2026-11-19 13:55, saved by root from a Sonnet read of e2-judge.out + e2-judge-ceiling.out;
24/24 runs, 3 seeds, 100 greedy eps; promise cost off in all arms)
lanes-rules: held (all hard held) mean (min-max) / side breaches/ep / plant / kills / idle share
- scripted idle 0.00/1.98; guard 0.88/5.53/0/20.4; ignore-top 0.00/0.01
- a-today flat S5: 0.00 / 0.80   (pays guard -23.25 < ignore-top -10 -> ignoring the top is cheaper)
- d flat S1: 0.42 (0.33-0.53) / 10.64 / 0.18 / 7.7
- e flat S2.5: 0.00 / 1.45
- c once S2.5 (reference, unused by the method): 0.87 (0.87-0.88) / 16.38
- b ceiling S1 (hard -96.1): 0.56 (0.34-0.96) / 13.95 / 0.15 / 6.7
- f ceiling S2.5 (hard -238.7): 0.00 / 3.82 (idle-like; return below scripted idle)
fear card cx-goal-many-rules: 0 everywhere (key never held), both arms flagged started = not started (0 = 0).
check-pay-order flags flat today/S1/S2.5 lanes (soft stream worse than a hard break); ceiling and once pass.
Reading: S matters more than ceiling vs flat; S2.5+ collapses to idle; ceiling S1 best recurrent arm and the only
recurrent one passing the pay order, but wide seed variance. keygift-soft (E1-rest): answers every key, 7.2
doors/ep vs idle 0, idle leaves the rule open at the cut -> learned by the activity check.
