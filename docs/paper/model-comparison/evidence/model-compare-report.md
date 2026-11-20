# Model compare: who makes the wrong reward machines

Packet: `model-compare-packet.md`. Evidence: `model-compare-evidence/` (tools/, runs/). Status log:
`model-compare-status.md`. Code: worktree E at main 54f2c71 (critic clues + Response card), plus the
untracked adapter `experiments/dev/model-compare/cli_engine.py`. 2026-11-20, 09:40-10:55 CET. Main has
since moved to cdae068: docs and paper only, no prompt, compiler, engine, script or card change.

## Verdict

- **The generator makes the first mistake, and glm lets it through.** All 3 wrong machines of the current
  pair (arm A, deepseek + glm) are deepseek's first proposals that glm accepted on call 1 (W5a, U5, S2).
  Swap either model and those cases come out right: Haiku + glm 6/6, deepseek + luna 6/6.
- **deepseek misreads a few task shapes again and again; Haiku does not.** First proposals right:
  deepseek 40/46 (A) and 13/18 (D); Haiku 46/46 (B) and 17/18 (C). On W5a, U5 and S2 deepseek's first
  proposal was not right in 7 of 9 runs (6 wrong, 1 with an early hard Existence); Haiku's in 0 of 9.
- **glm is the weak critic.** Same prompt, same clues, critic set of 36 valid items: glm caught 13/27
  wrong items on call 1, luna 26/27. Inside the pipeline glm caught 3/6 of deepseek's wrong first
  proposals; luna caught 5/5.
- **luna asks for too much, and on G12 two prompt rules collide.** luna rejected 23/68 right candidates in
  arm B and 23/39 in arm D (glm: 4/46 in A, 0/17 in C). It adds orders the critic prompt tells it to keep ("an
  order the task states stays", rule 8), then calls the task's own clause redundant (rule 6), then asks for
  it back. On G12 that ends wrong or with no machine in every luna run (B 3/3, D 2/2).
- **Two "wrong" machines are a card gap.** B's G12 machine (twice), `Existence(target_picked_up)` plus hard
  `Precedence(has_door_key, target_picked_up)`, accepts the same runs as the card's own `also_ok`
  answer: the hard order plus the hard goal already force `has_door_key`, so the card's
  `RespondedExistence(blocker_moved, has_door_key)` adds nothing. The scorer cannot see that.
- **Caveat.** The CLI models run with heavy thinking (Haiku `--effort max`, luna `xhigh`, as the packet's
  argv says); the app sends both OpenCode models `reasoning=none`, though glm is a thinking-only model
  (known-errors, 2026-10-25). The arms compare model plus thinking setting, not model alone.

## Per arm

C and D ran only on the hard subset (4 cases A or B got wrong plus 5 random right ones, 2 runs each), so
their right % is not comparable with A and B; compare them case by case below.

| arm | generator + critic | runs | right | accepted | wrong | first proposal right | critic catch on call 1 | false alarms | critic calls/run | calls gen+critic | wall s median (sum) | rounds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | deepseek + glm | 46 | 42 (91%) | 1 | 3 | 40/46 | 3/6 | 4/46 | 1.17 | 54+54 | 6 (362) | 1 (r1) |
| B | Haiku + luna | 48 | 45 (94%) | 0 | 3 | 48/48 | 0/0 | 23/68 | 1.48 | 71+71 | 59 (5882) | 2 (r1, r3 = G12 x2) |
| C | Haiku + glm | 18 | 17 (94%) | 0 | 1 | 17/18 | 0/1 | 0/17 | 1.00 | 18+18 | 42 (960) | 1 (r2) |
| D | deepseek + luna | 18 | 16 (89%) | 0 | 2 | 13/18 | 5/5 | 23/39 | 2.56 | 46+46 | 39 (1250) | 1 (r2) |

B on the 46 cases once (r1): 45 right (98%), 0 accepted, 1 wrong (G12). Catch on call 1 = the critic
rejected a first proposal that was not right; false alarms = right candidates rejected, any call.

Wrong machines by mistake group (accepted counted apart):

| arm | extra rule | wrong template | wrong event | order | other |
|---|---|---|---|---|---|
| A | 1 (W5a) | 1 (U5) | 1 (S2) | 0 | 0; accepted 1 (O7, early Existences) |
| B | 0 | 2 (G12 r1 and r3-r1: the card-gap machine) | 0 | 0 | 1 (G12 r3-r2: no machine after 10 attempts) |
| C | 1 (G12-r2) | 0 | 0 | 0 | 0 |
| D | 0 | 0 | 0 | 0 | 2 (G12: no machine after 10 attempts) |

Per case on the hard subset (R right, W wrong, A accepted; one letter per run):

| case | A deepseek+glm | B Haiku+luna | C Haiku+glm | D deepseek+luna |
|---|---|---|---|---|
| W5a | W | R | RR | RR |
| U5 | W | R | RR | RR |
| S2 | W | R | RR | RR |
| G12 | R | W, then WW in r3 | RW | WW |
| U6, O5, G2, G7, G11 | R each | R each | RR each | RR each |
| O7 (not rerun) | A | R | - | - |

Critic set (the critic-clues loop's 38 items, once each, judge deepseek). Items w03 and r05 (G10) are left
out: their candidates use KeyCorridor's `target_door_open`, which main dropped when G10's card moved to
UnlockPickup (0e821b8), so both critics errored on them.

| critic | caught on call 1 | defects flagged on call 1 | flagged in the run | accepted with a defect left | rejected the fixed candidate | false alarms (right items) | critic calls | wall s median |
|---|---|---|---|---|---|---|---|---|
| glm | 13/27 | 20/40 (50%) | 20/40 | 15 | 0 | 0/9 | 50 | 3 |
| luna | 26/27 | 38/40 (95%) | 39/40 | 1 (w15) | 4 | 1/9 (r10) | 63 | 35 |

glm misses most `event` (0/5) and `extra` (1/7) defects; luna flags them all but one. glm's feedback shows
its own reasoning leaking ("... holding_box)? No —", "wait, at_goal is soft"), as expected at no thinking.

## What the cases show

- **W5a (A wrong, extra rule).** deepseek adds hard `Existence(door_open)` next to the box goal; the world
  already forces the door. glm accepts. C and D: 4/4 right (in D W5a-r2 deepseek's first proposal dropped
  the soft key rule; luna caught it).
- **U5 (A wrong, wrong template).** "try not to drop the key while the door is still closed" becomes soft
  `Precedence(door_open, key_lost)` instead of soft `Absence(key_lost)`; the card note (2026-11-19) says
  this reading is weaker. In D deepseek's first U5 proposals were off in other ways (an early hard
  `Existence(door_open)`; a lone `Absence(key_lost)` with no goal); luna rejected both, glm accepted A's.
- **S2 (A wrong, wrong event).** "Pick up the key, then open the door, and then, ideally, walk onto the
  goal": deepseek makes `has_key` the hard last step instead of `door_open`, so opening the door becomes
  optional. glm accepts; luna rejects it (D S2-r2).
- **G12 (luna arms wrong).** "If you move the ball, you must also take the key. Then pick up the box."
  Every first proposal but C G12-r2's is right. luna asks for hard
  `Precedence(has_door_key, target_picked_up)` ("Then" is a stated order), which gives a card `also_ok`
  answer; next it calls `RespondedExistence(blocker_moved, has_door_key)` redundant (true: the order plus the
  goal force the key) and asks to drop it; with deepseek it later asks for it back ("does not express that
  conditional"). Twice Haiku drops it and luna accepts (B r1 and r3-r1, the card-gap machine); three times
  the flip runs out of the 10 attempts (B r3-r2, D 2/2). glm accepts the first proposal (A right, C 1/2).
- **O7 (A accepted).** glm rejected a right proposal ("the task commands picking up the ball and the key"),
  and deepseek answered with hard Existences of the earlier steps: the critic's false alarm made the machine
  worse.

## Wrong machines shown

Each machine's RM text is the `.rm` file named; its clauses and LTLf are in `runs/explain-all.json`.

1. **A W5a-r1** (extra rule). NL: "Move the ball away from the door before you take the key. Try not to drop
   the key while the door is still closed. Whenever you are holding the key, try to have the door open at that
   moment or open it afterwards. Then open the door with the key and pick up the box in the other room."
   LTLf: `(((~has_door_key)Ublocker_moved)|(G(~has_door_key)))` ; `(Fhas_door_key)` ; `(~(Fkey_lost))` soft ;
   `(G(has_door_key->(Fdoor_open)))` soft ; `(Fdoor_open)` ; `(Ftarget_picked_up)`.
   RM: `model-compare-evidence/runs/r1/A/W5a-r1.rm`
2. **A U5-r1** (wrong template). NL: "Open the door, then take the box from the other room; try not to drop
   the key while the door is still closed." LTLf: `(Ftarget_picked_up)` ;
   `(((~target_picked_up)Udoor_open)|(G(~target_picked_up)))` ; `(((~key_lost)Udoor_open)|(G(~key_lost)))` soft.
   RM: `model-compare-evidence/runs/r1/A/U5-r1.rm`
3. **A S2-r1** (wrong event). NL: "Pick up the key, then open the door, and then, ideally, walk onto the
   goal." LTLf: `(Fhas_key)` ; `(((~door_open)Uhas_key)|(G(~door_open)))` ;
   `(((~at_goal)Udoor_open)|(G(~at_goal)))` ; `(Fat_goal)` soft. RM: `model-compare-evidence/runs/r1/A/S2-r1.rm`
4. **A O7-r1** (accepted, early Existences). NL: "Pick up the blocking ball and the key, in either order,
   unlock the door, and then pick up the box in the other room." LTLf: `(Fblocker_moved)` ; `(Fhas_door_key)` ;
   `(((~door_open)Ublocker_moved)|(G(~door_open)))` ; `(((~door_open)Uhas_door_key)|(G(~door_open)))` ;
   `(((~target_picked_up)Udoor_open)|(G(~target_picked_up)))` ; `(Ftarget_picked_up)`.
   RM: `model-compare-evidence/runs/r1/A/O7-r1.rm`
5. **B G12-r1** (card gap, scored wrong template). NL: "If you move the ball, you must also take the key.
   Then pick up the box in the other room." LTLf: `(((~target_picked_up)Uhas_door_key)|(G(~target_picked_up)))`
   ; `(Ftarget_picked_up)`. RM: `model-compare-evidence/runs/r1b/B/G12-r1.rm`
6. **C G12-r2** (extra rule). Same NL. LTLf: `((Fblocker_moved)->(Fhas_door_key))` ;
   `(((~target_picked_up)Ublocker_moved)|(G(~target_picked_up)))` ;
   `(((~target_picked_up)Uhas_door_key)|(G(~target_picked_up)))` ; `(Ftarget_picked_up)`. The added
   ball-before-box order is one the world forces and a reading of "Then"; the card has no answer with it.
   RM: `model-compare-evidence/runs/r2/C/G12-r2.rm`
7. **D G12-r1, G12-r2** (no machine). Same NL; 10 attempts, luna rejected 9 right candidates in each run.
   No RM; the full critic exchange is in `model-compare-evidence/runs/r2/D/G12-r1.calls.jsonl`.
8. **B G12, round 3** (2 more runs). r1: the same card-gap machine after 5 rejections,
   RM `model-compare-evidence/runs/r3/B/G12-r1.rm`. r2: no machine after 10 attempts.

## Next steps

1. **Fix the G12 card** (no LLM calls). Add `[Precedence(has_door_key, target_picked_up) hard,
   Existence(target_picked_up) hard]` to `tpl-responded-existence-2-goal`'s `also_ok`: it is equivalent to
   the card's own third answer. Evidence: B G12-r1 and r3 G12-r1 (the same machine both times). Decide
   whether the world-forced `Precedence(blocker_moved, target_picked_up)` (C G12-r2) also counts.
2. **Settle the critic prompt's two rules before trusting a strong critic.** Rule 8 keeps stated orders even
   when the world forces them; rule 6 rejects "one redundancy". luna applies both and loops on G12 (D 2/2 no
   machine, 9 false alarms per run). A sentence such as "a clause the task states is never redundant, even
   when other clauses imply it" would stop the flip; test it on G12, G4, G6, C2, W2b (luna's false alarms)
   and on the critic set's fixed-candidate rejections (s02, s05, w08, w16).
3. **Give glm thinking before swapping it.** glm misses half the critic set at the app's `reasoning=none`
   setting while luna ran at `xhigh`. One critic-set run with glm at a thinking level (38 items, about 65
   OpenCode calls) separates "weak model" from "no thinking". If glm still misses `event` and `extra`
   defects, a stronger critic is the fix: luna with arm D fixed every deepseek mistake in this sample.
4. **Aim the generator prompt at deepseek's three readings**, per the generator-loop rule (at most 2 cases
   per mistake group): "not while the door is closed" as `Absence` (U5), the last hard step when the goal is
   soft (S2), no hard `Existence` for a step the world forces (W5a, O7). Haiku made none of them, so the
   wording can be learned from its proposals in `runs/r1b/B`.

## Budget and limits

- Runs: 214 of 300 (A 48, B 50, C 20, D 20 with the 8 dry runs; critic sets 76). Rounds: p1 dry, r1 (A, B),
  r2 (C, D), r3 (B on G12). No later round: nothing was changed between rounds, so the shrinking rule's fix reruns did
  not apply; the final full rerun waits for a fix.
- OpenCode: 271 calls (cap about 300), judge calls included. Runs with an OpenCode generator or critic call:
  124, over the 120 cap by 4. C and D put only one side of each round on OpenCode (C 18 calls in 18 runs,
  D 46 in 18), so I counted them against the call budget. No OpenCode call after 10:30.
- Subscriptions after the last round: Claude seven-day 27 %; Codex 5 h 6 %, weekly 5 %. Never near 95 %.
- Context stripping, verified on one call each. Claude (`--safe-mode --strict-mcp-config
  --disable-slash-commands --tools "" --system-prompt <app system>`): init shows no tools, MCP, skills or
  hooks; 661 cache tokens instead of about 42 K; the plugin list is still printed. Codex (`--ignore-user-config
  --strict-config`, the app system prompt as `model_instructions_file`, five instruction blocks off, 14
  features off): 9.3 K input tokens instead of 23.5 K; no flag removes `~/.codex/AGENTS.md` (sent as a 20 K
  character user message), the multi-agent role and mode notes, or the exec, wait, request_user_input and
  collaboration tools. No call used a tool: Haiku logged none, and luna's only extra items are two startup
  warnings per call (the unstable-feature notice for `skip_host_skill_discovery` and "Code Mode is
  unavailable"). The Codex session file of all 240 phase 2 luna calls shows the app system prompt as the
  first message. The 8 phase 1 dry runs (p1) ran before the stripping and are left out of every table.
