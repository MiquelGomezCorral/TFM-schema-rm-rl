# Short first proposals under thinking: report (2026-11-20)

Packet: `short-proposal-packet.md`. Evidence: `short-proposal-evidence/` (scanners, `probe.py`, `probes/*.json`
with full raw responses and reasoning text, `probes/ledger.txt`). Early note for the running loop:
`short-proposal-finding.md`. Read-only: nothing changed in the repository or any worktree.

## Answer

- **Side: pipeline.** The generator is never shown the output shape. The app sends the proposal schema only
  as `response_format: json_schema` (`app/src/engines/provider_engines.py:158-160`). The creator prompts never
  name a field (`clauses`, `normalized_clause`, `pattern`: 0 times). They only say "Return only JSON matching
  the caller-provided schema" (`app/src/prompts/compiler-rm/reward-ltlf-creator.system.md:82`).
- **The model guesses another shape.** OpenCode does not put the schema in deepseek's context. It enforces
  the schema by constrained decoding of the content. With thinking on, deepseek plans its answer in the
  reasoning, guesses `{"clauses":[{"template", "arguments", "priority"}]}`, and the grammar then forces
  `normalized_clause`, `pattern` and `propositions`. Under that clash the content often closes the list after
  the first clause. At `none` there is no plan to clash with (0/46). More thinking, more shorts: loop2 low
  7/46, medium 8/46, high 8/46, max 14/46; 36 of those 37 are one clause.
- **Confirmed by a fix test.** Same cases, sent at the same moment: the original prompt gave 3/4 short; with
  the output shape named in the prompt, 0/5 short, all 5 right (exact). Under the original prompt's rate,
  getting 0/5 has p ≈ 0.05 (Fisher, one-sided). The mechanism check is cleaner: 9 of 10 original-prompt
  replays say in their reasoning that the schema is not shown. None of the 5 fixed ones does.
- **Smallest fix:** one sentence in `reward-ltlf-creator.system.md:82` (text below). No engine change.

## Pipeline causes ruled out

| suspect | finding |
|---|---|
| Wrong JSON object parsed | The app runs `json.loads` on all of `message.content` (`structured.py:205`, `parse_proposal`). Extra text would fail to parse. The adapter logs that same string; its first-object extraction (`_json_object`) runs only for the CLI engines. |
| Token limit or `finish_reason` cut | No `max_tokens` is sent. `finish_reason` was `stop` in all 15 replays. Text tokens (completion minus reasoning) are 38-77, which matches the one-clause content. A cut would leave invalid JSON. |
| Reasoning and content mixed | One choice per reply. Reasoning arrives in its own `reasoning_content` field; the content is the answer. |
| Schema lets one clause through | It does (`minItems: 1`, `structured.py:98-103`), and it must, because some cards have one-clause answers. It permits the short list but does not cause it. |
| Retry path with a shorter prompt | Every short first call had the same system length (14,608) and user length as full runs of the same case. 0 errors and 0 refused sends before it. Short and full runs ran side by side in the same seconds. |
| Provider cap on thinking | Not for deepseek: its reasoning reaches 31K at max, and shorts sit at 0.7K-14K. The glm critic stops at exactly 4,096 reasoning tokens (26 calls at max, 1 at high), but every such reply parsed. That is unrelated to this problem. |

## Evidence per run (loop 1, the 10 medium shorts)

Every request: system 14,608 chars, the same `declare_proposal` schema, `reasoning_effort=medium`, no
`max_tokens`, one call, no resends. `finish_reason` and the reasoning text were not logged in the loop; the
replays below supply them. "Kept" is the only clause the content held: always the task's first clause.

| run | kept (got / card minimum) | reasoning tok | text tok | user chars | marks in the reply | full run, same case |
|---|---|---|---|---|---|---|
| m1 O5-r1 | Existence(at_exit) (1/2) | 1,110 | 48 | 6,825 | none | m1 O5-r2: 2 clauses, 1,594 reasoning |
| m1 U6-r1 | Absence(target_picked_up) (1/3) | 2,537 | 48 | 5,908 | none | b4 U6-r1: 3 clauses, 1,618 |
| m1 U6-r2 | Absence(target_picked_up) (1/3) | 1,774 | 45 | 5,908 | `"normalized_clause":"x"      ,` | b4 U6-r1 |
| b4 O5-r1 | Existence(at_exit) (1/2) | 1,346 | 47 | 6,825 | none | m1 O5-r2 |
| b4 S2-r1 | Precedence(has_key, door_open) (1/2) | 2,993 | 77 | 4,776 | `"normalized_clause": "template"`, long blank runs | m1 S2-r1, r2: 4 clauses |
| b4 U1-r1 | Existence(at_exit) (1/3) | 2,710 | 42 | 6,851 | `"test" ,` | none at medium |
| b4 U2-r1 | ChainResponse(box_fell, holding_box) (1/2) | 4,537 | 53 | 6,878 | none | replay U2-fix: 2 |
| b4 W1b-r1 | Existence(at_exit) (1/3) | 3,847 | 61 | 6,857 | none | replays W1b-fix-a, b: 3 |
| b4 W2b-r1 | ChainResponse(box_fell, holding_box) (1/2) | 3,557 | 43 | 7,257 | text = `ChainResponse` | replay W2b-orig: 2 |
| b4 W3a-r1 | ChainResponse(box_fell, holding_box) (1/2) | 3,785 | 62 | 6,884 | none | replay W3a-fix: 2 |

The marks are the model's own words forced into the only free-text field. Loop2 has more of them:
`"I need to write a JSON object, not this."` (max W3a), `"error"` (max C1), `"x"` (max G6), `"..."`,
`", "`, `"OPEN_THE_DOOR"`. They are a symptom only: some full replies also put a bare template name there.

## Replays (15 OpenCode calls, deepseek at medium, cap 15)

`probe.py` resends the logged first request through the app's `OpenCodeEngine._create_completion` (same client
and request shape) and keeps the raw response. Two rounds, each sent at once.

| replay | prompt | clauses | scored | reasoning says the schema is missing | keys planned in reasoning |
|---|---|---|---|---|---|
| O5-a, b, c (m1 O5-r1 request) | original | 2, 2, 2 | full | a, b yes; c no | template, arguments (a, b) |
| U6-a, b, c (m1 U6-r1 request) | original | 3, 3, 3 | full | yes, yes, yes | template, arguments |
| W1b-orig | original | **1** | wrong | yes | template, arguments |
| W3a-orig | original | **1** | wrong | yes | template, arguments |
| U2-orig | original | **1** | wrong | yes | template, arguments |
| W2b-orig | original | 2 | right | yes | template, arguments, args, parameters |
| W1b-fix-a, b | shape named | 3, 3 | right, right | no, no | none / the real keys |
| W3a-fix, U2-fix, W2b-fix | shape named | 2, 2, 2 | right ×3 | no ×3 | none / the real keys |

- **The reasoning holds the full plan; the content drops it.** W3a-orig ends: "So two clauses: 1.
  ChainResponse(box_fell, holding_box) — hard 2. Response(at_exit, holding_box) — hard ... The schema isn't
  shown explicitly but presumably: {"clauses": [{"template": "ChainResponse", "arguments": [...], "priority":
  "hard"}, ...]}. Let me use "template", "arguments", "priority" keys." Its content held only clause 1. U2-orig
  and W1b-orig also reach `Response(at_exit, holding_box)` in the reasoning and drop it in the content.
- **Thinking is wasted on guessing.** O5-b and U6-a spend part of their reasoning on the shape ("Could be
  fields 'type'?", "Potential schema uses 'params' or 'args'").
- **The answer recovers on the second call** because the critic's feedback names the missing clauses
  outright (b4 W1b, U2, S2 histories).

## Smallest fix

In `app/src/prompts/compiler-rm/reward-ltlf-creator.system.md:82`, replace "Return only JSON matching the
caller-provided schema." with the tested text (`short-proposal-evidence/fix-shape.json`):

    Return only one JSON object of this shape, with one entry per clause:
    `{"clauses": [{"normalized_clause": "<the task words this clause covers>", "pattern": "<template>",
    "propositions": ["a", "b"], "priority": "hard"}]}`. `pattern` is a template name from the table,
    `propositions` holds its arguments in order (one for a unary template), `priority` is `hard` or `soft`.

The critic needs nothing: its prompt already shows `{"accepted": ..., "feedback": ...}` in eight examples
(`reward-machine-critic.system.md:185-243`). An engine-side alternative, adding the schema JSON to every
structured request, is larger and touches every provider. It is not needed.

## How to confirm at scale

1. Apply the sentence in the loop's worktree. Rerun at `max`, the worst level (14/46 short), on the cases short
   in either loop: G6, G7, G9, O5, O8, S1, S2, S3, U1, U2, U5, U6, W1a, W1b, W2b, W3a, W4a, W4b, W5a, W5b, W6,
   C1. Add 4-5 random passing cases (shrinking-rounds rule).
   - Expect short first proposals near 0, and "first proposal right" up from 30/46.
   - Expect no case that was right to turn wrong.
   - Then one full 46-case run per level that thinks.
2. Optional, to see the mechanism in full runs: the adapter's `_metered`
   (`experiments/dev/model-compare/cli_engine.py:118-148`) logs only the reasoning length. Logging the text
   and `finish_reason` would let a scan count "schema not shown" in the reasoning per run.
3. Watch `none`: the fix adds 4 lines to the prompt and should not change it. Check a few `none` runs in the
   same rerun.

## Paper candidate

A failure mode with a measured fix. Under thinking, an invisible output schema makes deepseek drop clauses
(0/46 at none; 7, 8, 8, 14 of 46 at low to max). Naming the shape in the prompt turns 3/4 short into 0/5
short, all right, with quoted reasoning. Inputs: `short-proposal-evidence/probes/`, `fix-shape.json`, both
loops' `runs/`.
