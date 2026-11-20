# Shape fix: the proposal shape named in the generator prompt (2026-11-20)

Packet: `shape-fix-packet.md`. Worktree `tp-llm-loop2` (on top of the loop 2 changes, not committed).
Evidence: `shape-fix-evidence/` (tools copied from loop 2, `runs/{max,high,none}/A`, `case-sets.txt`,
`creator-prompt-vs-main.diff`, `runs/none/explain.json` and the wrong machines' `.rm` files).
Pair: deepseek-v4.1-flash generator, glm-5.3-flash critic, same level, OpenCode.

## Result in short

- **No short first proposals left in this run.** 0 of 72 finished runs at `max` and `high` (22 in
  loop 2 on the same cases: 14 at max, 8 at high). One run per case, so "0" means "not seen", not
  "impossible".
- **First proposals right:** max 26/26 finished (was 12 on the same 26), high 46/46 (was 37/46).
- **Cheaper where it finishes.** Critic calls per run 1.00 at max (was 1.54 on the same 26) and 1.02 at
  high (1.22). Median wall per run: max 88 s (179), high 35 s (48). Median generator output: max 2292
  tokens (4618), high 1734 (2404).
- **No wrong machine at max or high.** 26/26 and 46/46 right.
- **One regression: W5a at `max` ended with no machine.** Its first generator call timed out at the
  600 s SDK limit six times in a row; the round's 3600 s cap killed the run. At `high`, W5a timed out
  once, then answered in 29 s. No other case timed out. Loop 2: 0 W5a timeouts in 10 generator calls
  (254 s at max). Cause not known yet (see "W5a timeouts").
- **`none`: 7/10 right, 3 wrong** (S3, U5, W5a). The same three were wrong at `none` before
  (model-compare run, old prompts, 6/10). LLM side, not the fix: see below.
- **Side gain: `normalized_clause` now holds words.** Loop 2 wrote a formula there in 242 of 481
  clauses ("Precedence(blocker_moved, has_door_key)"); this slice 0 of 223. The tagger and both
  labeling prompts read that field as "the requirement expressed in natural language".

## The change

`app/src/prompts/compiler-rm/reward-ltlf-creator.system.md:82-87`, one sentence replaced:

```diff
-Return only JSON matching the caller-provided schema. Do not output formulas, rewards,
+Return only one JSON object of this shape, with one entry per clause:
+`{"clauses": [{"normalized_clause": "<the requirement this clause covers, in natural language>",
+"pattern": "<template>", "propositions": ["a", "b"], "priority": "hard"}]}`. `pattern` is a
+template name from the table, `propositions` holds its arguments in order (one for a unary
+template), `priority` is `hard` or `soft`. Do not output formulas, rewards,
 states, transitions, explanations, or fields not requested by that schema.
```

Checked against the real schema (`app/src/engines/structured.py:67-104`): top key `clauses`; each
clause has `normalized_clause` (string), `pattern` (template enum per arity), `propositions` (declared
ids, count = arity), `priority` (`hard`/`soft`, `PriorityLevel` in `app/src/config/config.py:20-24`),
in that order, no other fields. The prompt's template table has an "Arguments" column
(`declare-templates.md:4`), which "its arguments in order" points to. The system prompt is filled by
`str.replace` (`app/src/prompts/loaders.py:72-76`), so the braces are safe.

**One word change from the tested text.** The replay used `"<the task words this clause covers>"`.
The tagger defines the field as "the requirement expressed in natural language"
(`reward-machine-tagger.system.md:28`), and the labeling generator and reviewer list it the same way.
"Task words" reads as a verbatim quote, a narrower meaning, so the placeholder now says "the
requirement this clause covers, in natural language". The rounds below test this final text.

The next sentence still says "that schema"; it now points at the shape above. Left as tested.

## Other prompts and `response_format`

Only three prompts go out with `response_format: json_schema` (`_request_structured`,
`app/src/engines/generic_engine.py:194`):

| prompt | schema | fields named in the prompt |
| --- | --- | --- |
| `compiler-rm/reward-ltlf-creator.system.md` | `proposal_schema` | now yes (this fix); before, none |
| `compiler-rm/reward-machine-critic.system.md` | `critic_schema` | yes: `accepted`, `feedback` (line 245, and eight examples) |
| `compiler-rm/labeling-reviewer.system.md` | `critic_schema` | yes: `accepted`, `feedback` (line 65) |

The ARM-FM and labeling generators do not use `response_format` at all: they go through
`request_text` and state their output in the prompt. `arm_fm/rm_generator.user.md:13` ("Return
only:" the RM text format), `arm_fm/labeling_generator.user.md:19` and
`compiler-rm/labeling-generator.system.md:97-99` (Python definitions), `arm_fm/description_generator`
(`user.md:10`: a JSON object with exactly the state keys), `arm_fm/rm_critic` and `labeling_critic`
(`accepted`, `feedback`, also shown as JSON in their user prompts), `reward-machine-tagger.system.md:121`
(a JSON array of strings). **No other prompt leaves its output fields unnamed.** Nothing changed there.

## Rounds against loop 2

One run per case. Same tools, cards and scorer as loop 2 (`level_stats.py`, with a `--cases` filter
added so the loop 2 rows cover the same cases). "Short first" = a first proposal that is not right and
has fewer clauses than the card's smallest right answer.

| round | runs | right | wrong | no machine | first right | short first | catch@1 | false alarms | critic calls/run | wall s per run, median (total) | gen output tokens med / max | gen call timeouts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| loop 2 max, 26 cases | 26 | 26 | 0 | 0 | 12/26 | 14 | 14/14 | 0/26 | 1.54 | 179 (4470) | 4618 / 19975 | 0 |
| **shape max, 26 cases** | 26 | 26 | 0 | 0 | **26/26** | **0** | 0/0 | 0/26 | **1.00** | **88 (2460)** | **2292 / 12335** | 0 |
| loop 2 max, W5a | 1 | 1 | 0 | 0 | 1/1 | 0 | - | 0/1 | 1 | 302 | 31662 | 0 |
| **shape max, W5a** | 1 | 0 | 0 | **1** | - | - | - | - | 0 | **3600 (killed)** | - | **5 logged + 1 killed** |
| loop 2 high, 46 | 46 | 46 | 0 | 0 | 37/46 | 8 | 9/9 | 1/47 | 1.22 | 48 (2553) | 2404 / 7705 | 0 |
| **shape high, 46** | 46 | 46 | 0 | 0 | **46/46** | **0** | 0/0 | 1/47 | **1.02** | **35 (2336)** | **1734 / 7949** | 1 (W5a) |
| none before, 10 | 10 | 6 | 4 | 0 | 5/10 | 2 | 1/5 | 0/6 | 1.10 | 6 (74) | not logged | 0 |
| **shape none, 10** | 10 | **7** | **3** | 0 | **7/10** | 2 | 0/3 | 1/8 | 1.10 | 6 (71) | 177 / 225 | 0 |

The 26 max cases are the 27 below without W5a, shown on its own line so its killed run does not hide
in a median. The high total includes W5a's 600 s timeout. The two "short" at `none` are not the
one-clause cut: S3 and W5a hold fewer clauses because the generator left clauses out (next section).
Full `level_stats.py` rows (reasoning tokens, critic tokens) are reproducible from the run folders.

- **max** cases: the 22 short in either loop (G6, G7, G9, O5, O8, S1, S2, S3, U1, U2, U5, U6, W1a,
  W1b, W2b, W3a, W4a, W4b, W5a, W5b, W6, C1) plus 5 passing ones drawn with seed 20261120 (O2, O6, G1,
  G3, G5). **none** cases (same seed): W4a, W5a, C2, U5, O5, O6, O8, G11, S3, S4.
- **The `none` baseline is weaker.** Loop 2 never ran `none`. The row "before" is the model-comparison
  run (`model-compare-evidence/runs/r1/A`, old prompts, scored with the audited cards); its logs hold
  no token counts.
- **Catch on call 1 is 0/0 at max and high** because no first proposal was wrong.
- **False alarms.** High G9: the critic asks for `Precedence(door_open, at_goal)` after a
  "whenever" rule followed by "Then reach the goal", the same G9/G12 pattern loop 2 reported; the card
  accepts both, so it only cost one round. None O6: the first proposal listed
  `Precedence(has_key, door_open)` twice; the scorer compares sets and calls it right, the critic asked
  to drop the duplicate. That is a fair rejection, not a real false alarm.
- **Critic tokens at max** sit at the 4,096 reasoning cap (median now 4096), as loop 2 saw.

## Wrong machines (all at `none`)

The pipeline compiled each set faithfully (LTLf below matches the clauses). The generator picked the
wrong clauses and the glm critic at `none` accepted them on call 1. All three are the same mistakes the
`none` run made before this loop, so the shape fix did not cause them. **Side: LLM.**

- **S3** (`local-soft/soft-door-box`). NL: "Open the door, then, if possible, pick up the box in the
  other room." Got: Existence(door_open), Existence(target_picked_up)~s. Missing: the soft
  Precedence(door_open, target_picked_up) the prompt's chain rule asks for ("a soft last step keeps
  `Precedence(b, c)`"). LTLf: `(Fdoor_open)`, `(Ftarget_picked_up)`. RM:
  `shape-fix-evidence/runs/none/A/S3-r1.rm`. Before: the identical set.
- **U5** (`complex/cx-goal-one-rule~p3`). NL: "Open the door, then take the box from the other
  room; try not to drop the key while the door is still closed." Got: Existence(door_open),
  Existence(target_picked_up), Precedence(door_open, target_picked_up), Precedence(door_open,
  key_lost)~s. Card: soft Absence(key_lost). Its notes (S2 2026-11-19) reject
  Precedence(door_open, key_lost) on purpose: it allows opening the door, closing it again and dropping
  the key. LTLf: `(Fdoor_open)`, `(Ftarget_picked_up)`,
  `(((~target_picked_up)Udoor_open)|(G(~target_picked_up)))`, `(((~key_lost)Udoor_open)|(G(~key_lost)))`
  (soft). RM: `shape-fix-evidence/runs/none/A/U5-r1.rm`. Before: the same soft Precedence.
- **W5a** (`complex/cx-goal-many-rules`). NL: "Move the ball away from the door before you take the
  key. Try not to drop the key while the door is still closed. Whenever you are holding the key, try
  to have the door open at that moment or open it afterwards. Then open the door with the key and pick
  up the box in the other room." Got: Existence(door_open) in place of Precedence(has_door_key,
  door_open) and Precedence(door_open, target_picked_up), the loop 2 "Existence in place of
  Precedence" gap. LTLf: `(((~has_door_key)Ublocker_moved)|(G(~has_door_key)))`, `(~(Fkey_lost))`
  (soft), `(G(has_door_key->(Fdoor_open)))` (soft), `(Fdoor_open)`, `(Ftarget_picked_up)`. RM:
  `shape-fix-evidence/runs/none/A/W5a-r1.rm`. Before: the same, plus Existence(has_door_key).

No wording retry. These are not caused by the change under test, and `none` is not a candidate default.
A fix for them would be a `none`-level rule change, outside this slice. No case was wrong twice.

## W5a timeouts

- **max** (`runs/max/A/W5a-r1.*`): generator attempts at 14:10, 14:20, 14:30, 14:40, 14:50 and 15:00,
  each `APITimeoutError` after 600 s; the sixth was killed by the 3600 s run cap. No proposal, no
  critic call, no machine.
- **high** (`runs/high/A/W5a-r1.*`): one 600 s timeout, then a 29 s answer (2,197 output tokens, 1,873
  of them reasoning), accepted on the first critic call, right.
- **Everything else:** 0 timeouts in 81 other runs.
- **Before:** loop 2 made ten W5a generator calls across levels (46-299 s), 0 timeouts. Its max call
  was the longest of the sweep: 31,662 output tokens in 254 s.

Six timeouts in a row on one case, against none on 26 others at the same level, is not chance; the new
text and W5a's long task interact somehow. **Side: not found.** A timeout logs no tokens, so it is open
whether deepseek writes past 600 s (a reasoning or content loop) or the provider stalls. One guess
worth testing first: `normalized_clause` is now free natural language, and a constrained decoder can
loop inside a free string (the diagnosis saw long blank runs in that field). A streaming replay of the
logged W5a request at `max` would show which, in one or two calls. Not run: it needs a streaming
client the tools do not have, and the packet allows no edit without evidence. No wording retry.

Practical cost: at `max`, `PROVIDER_RETRIES` = 10 means one such case holds a slot for up to 100
minutes. At `high` it cost 600 s once.

## Budget

83 runs and 175 OpenCode calls of 100 / 260 (no judge calls). By round: max 27 runs, 58 calls (57
logged, W5a's five timeouts among them, plus the killed sixth); high 46 runs, 95 calls; none 10 runs,
22 calls. `budget.py` prints 82 / 174: it skips the killed W5a record and its unlogged
call.

Guard: 240 calls (20 below 260) and 90 runs. The plan alone needed 83 runs, so a run guard at 80
would have cut 3 of the planned runs; the run cap of 100 still held. The guard never fired.

## Paper candidates

Named here; nothing copied to `docs/paper/`.

- **Invisible output schema under thinking, before and after.** The 26 hardest cases at `max` that
  finished: short first proposals 14 to 0, first proposals right 12/26 to 26/26, critic calls per run
  1.54 to 1.00, median wall 179 to 88 s; and 46 cases at `high`: 8 to 0 short, 37/46 to 46/46 first
  right, median wall 48 to 35 s. The W5a timeouts belong in the same entry as the open cost. With the diagnosis (`short-proposal-report.md`: 0/46 short at `none`, 7, 8, 8, 14 of
  46 at low to max; the replays with quoted reasoning) it is one finding: a constrained-decoding
  provider that hides the schema from the model, plus a prompt that never names the fields.
  Evidence: `shape-fix-evidence/runs/{max,high}`, `llm-loop2-evidence/runs/f-{max,high}`.
- **Formula text in `normalized_clause`:** 242/481 before, 0/223 after. Small, but it is the input
  the tagger and labeling prompts read as natural language.

## Checks and files

- Changed: `app/src/prompts/compiler-rm/reward-ltlf-creator.system.md` (lines 82-87) only.
- `pre-commit run --files` on it: passed. `python -m unittest tests.test_prompts`: 6 passed.
- Evidence-only tool change: `shape-fix-evidence/tools/level_stats.py` takes `--cases`.

## Notes

- **Decision records: no change.** Prompt wording only; `docs/decisions/` has no record on the
  creator's output line or on structured outputs (grep for `response_format`, `json_schema`,
  "structured output", "caller-provided": no hits).
- **Gaps:** one run per case and level; `medium` and `low` not rerun with the fix (the packet did not
  ask); the `none` baseline uses older prompts; the W5a timeout cause is open.
