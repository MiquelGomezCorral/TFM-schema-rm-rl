# Chain prompt loop status (worktree tp-chain-prompt, branch MiquelGomezCorral/tp-chain-prompt)

- 2026-11-19 20:10 CET: started; worktree created from main 0389b0b; tools copied to outputs/chain-loop/tools.
- 20:20: card tpl-existence-1-goal: chain form primary, per-step Existence also_ok (plan-trace check 0 mismatches; trace-bank 3/3).
- 20:22: v0 (n6 prompts on main) launched on the new ordered cases O1-O8 x3 and guard G1-G12 x1.
- 20:23: v0 first try: 16 parallel runs hit provider 429 "Rate limit exceeded" (10 reruns in 2 s); requeued, run at parallel 6-8.
- 20:25: tool fix: gen_one.py now passes the level (gym_id, env_kwargs, step_limit); without it every soft-clause
  candidate fails with "the hard ceiling prices repeating soft breaks over the level's step limit" (pay-default merge).
- 20:29: v0 complete (42 cases x3 = 126 runs, 2 min at parallel 8). Scorer: forced-order closure and logically
  redundant Existence rules added.
- 20:31: v1 launched (generator chain rule, template row, critic example and goal sentence).
- 20:36: v1 scored (chain 61.9%, wrong 13); v2 launched (generator last check + exception note, critic redundancy rejection).
- 20:41: v2 scored (chain 64.3%, wrong 12; W1b/W2b flagged); v3 launched (goal bullet: only the last ordered step is a goal; 'do a' row; any-order join example).
- 20:46: v3 scored (chain 66.7%, wrong 24; U2/U4 flagged); v4 launched (critic rejection example for a redundant Existence; generator as v3).
- 20:51: v4 scored (chain 88.1%, wrong 15; U2/U4 flagged); v5 launched (revert v3 'do a' row; carry row: an 'if you reach a' condition gets Response(a, c) alone).
- 20:56: v5 scored (chain 66.7%, wrong 19); v6 launched (critic goal check: the chain forces earlier steps; 'do a' row restored; 'b too' with or without 'must' is RespondedExistence).
- 21:01: v6 scored (chain 76.2%, wrong 11, none lost); v7 launched (generator: no Precedence for steps the task does not name; Precedence row: forcing runs down a chain).
- 21:05: v7 scored (chain 76.2%, wrong 13; v6+v7 none lost). 90% unreachable with one version left; v7 replicate launched (runs r4-r6).
- 21:10: v7 replicate scored (v7 x6: chain 75.0%, wrong 10.7%; v6+v7 pooled 75.4%, none lost). Loop stopped at the version limit; report written.
- 21:28: fix round from the v7 diff review (P1 soft last step, P2a one "lone" definition, P2b critic optional change + card note, P3 stale note and wraps). New soft-last-step cases S1-S4 (local cards, new wording) on v7 prompts: 17/24 right, 7 wrong (mostly the soft goal made hard). v8 edits applied; tests.test_prompts OK; v8 confirmation round launched (42 cases + S1-S4, 6 runs each).
- 21:40: v8 scored (42 cases x 6: chain 77.4% vs v7 75.0%, wrong 26 vs 27; S1-S4 wrong 3/24 vs 7/24 on v7). Flagged vs v7 x6: U5 3/6, G10 2/6. Running 6 more runs of U5, G10, W6, U6, W4a, W3a to separate noise from cause.
- 21:44: v8 with 12 runs on the dropped cases: U5 7/12 and G10 6/12 lost vs v6+v7 (8/9, 7/9); W6 5/12 (was 9/9). Traces: the critic read "the one optional change" as optional and accepted redundant sets; the generator put Existence on the first step more often. v9 edits (critic exception wording, tighter lone definition) applied; v9 round launched (42 cases + S1-S4, 6 runs).
- 22:01: v9 scored: worse than v8 (chain 65.5%, W6 1/6, U5 3/6, W4a 3/6; S wrong 7/24). Running a control: v7 prompts again on W6, U5, G10 (v7c, 6 runs) to tell prompt cause from model drift. W6 never wrote the soft ban as Precedence on v6/v7 (18/18 Absence) but does on v8/v9 about half the time.
- 22:03: v7c control (v7 prompts, 6 runs): W6 4/6, U5 5/6, G10 3/6; no Precedence(door_open, key_lost) on v7 (0/24 with v6/v7). So G10 is drift or noise; the W6/U5 soft-ban-as-order is caused by the v8 lone list item "a step ordered before an event the task never commands". v10 = v8 minus that item; full round launched (42 cases + S1-S4, 6 runs).
- 22:18: v10 scored: none lost vs v6+v7+v7c, wrong 29/252 (v7 27), but ordered chain 65.5% (v7 75.0%); S wrong 8/24. The soft goal made hard fell from 5/24 (v7s) to 1/24 (v8s, v10s). v8 and v10 differ by one sentence yet chain moved 77 -> 65, so a same-hour control: v7 prompts on the 14 ordered cases + S1-S4 (v7n, 6 runs).
- 22:27: v7n control (same hour): ordered chain 59/84 = 70.2% (v10 55/84), S wrong 8/24 (v10s 8). The soft ban as soft Precedence(door_open, key_lost): v7 family 3/90 final sets, v8 5/54, v9 8/36, v10 9/36. v11 = v10 with a hard Precedence in the two new examples; screening on W4b, W5a, O1, U5, W6, U6, S1-S4 (6 runs).
- 22:34: v11 screening: soft-ban-as-order 1/36 (v10 9/36); none lost on the 6 key_lost cases; S wrong 6/24 (S1: 3 soft goal made hard, 1 has_key left unforced). Running the other 36 cases on v11 (6 runs) for the full regression check.
- 22:48: v11 final (none lost, chain 81.0%, S wrong 6/24). Report, rounds, examples and final diff updated. Live prompts = v11; no runs left.
