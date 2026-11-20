# Short first proposals under thinking: pipeline cause, confirmed (2026-11-20)

Full write-up: `short-proposal-report.md`. Evidence: `short-proposal-evidence/`.

## Cause

The generator never sees the output schema. The app sends the proposal schema only as
`response_format: json_schema` (`app/src/engines/provider_engines.py:158-160`). The creator prompts never name
a field: `clauses`, `normalized_clause` and `pattern` appear 0 times. They say only "Return only JSON
matching the caller-provided schema" (`app/src/prompts/compiler-rm/reward-ltlf-creator.system.md:82`) and
"Return only the schema-constrained proposal" (`reward-ltlf-creator.user.md:16`). OpenCode does not show the
schema to deepseek. It enforces the schema by constrained decoding of the content.

- At `none` the model writes the content straight away, inside the forced keys: nothing to conflict with (0/46).
- With thinking it plans the answer first, guesses another shape (`template`, `arguments`), and the grammar
  then forces other keys. The content drifts and often closes the list after the first clause. The more it
  thinks, the more often this happens: loop2 low 7/46, medium 8/46, high 8/46, max 14/46.

The critic is not affected: its prompt shows its output shape in eight JSON examples
(`reward-machine-critic.system.md:185-243`).

## Evidence

- Replays of logged first requests (`short-proposal-evidence/probes/*.json`, deepseek at medium): 9 of 10
  original-prompt replies say in their reasoning that the schema is not shown, and plan
  `{"clauses":[{"template": ..., "arguments": [...], "priority": ...}]}`. W3a-orig: "So two clauses:
  1. ChainResponse(box_fell, holding_box) — hard 2. Response(at_exit, holding_box) — hard ... The schema isn't
  shown explicitly but presumably: {"clauses": [{"template": ..., "arguments": [...]}]} ... Let me use
  "template", "arguments", "priority" keys." Its content held only clause 1.
- Yet every content has the schema's exact keys in schema order. Only server-side constrained decoding can
  produce keys the model never saw.
- Short replies carry the model's own words in the one free-text field: `"normalized_clause": "I need to
  write a JSON object, not this."` (loop2 max W3a), `"template"` (the key it wanted, b4 S2), `"x"`, `"test"`,
  `"error"`, `"..."`.
- **Fix test, same moment, same cases (box-carry, short in 5/6 b4 runs):** original prompt 3/4 short
  (W1b, W3a, U2; W2b full). Prompt naming the shape 0/5 short, all 5 scored right (exact). No fixed reply
  mentions a missing schema, and every `normalized_clause` holds real task words.
- Ruled out: wrong JSON object parsed (`json.loads` of all of `message.content`, `structured.py:205`; the
  adapter logs that same string); token cut (no `max_tokens` sent, `finish_reason` `stop` in all 15 replays,
  text tokens 38-77 match the short content); reasoning mixed into content (separate `reasoning_content`, one
  choice); retry or shorter prompt (same system and user length as full runs, 0 errors, 0 resends).

## Smallest fix

In `app/src/prompts/compiler-rm/reward-ltlf-creator.system.md:82`, replace "Return only JSON matching the
caller-provided schema." with (the exact text tested, `short-proposal-evidence/fix-shape.json`):

    Return only one JSON object of this shape, with one entry per clause:
    `{"clauses": [{"normalized_clause": "<the task words this clause covers>", "pattern": "<template>",
    "propositions": ["a", "b"], "priority": "hard"}]}`. `pattern` is a template name from the table,
    `propositions` holds its arguments in order (one for a unary template), `priority` is `hard` or `soft`.
