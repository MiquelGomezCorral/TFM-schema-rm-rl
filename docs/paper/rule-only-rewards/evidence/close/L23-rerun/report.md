# L2.3 critic-failure diagnosis and one rerun (close wave)

Worktree HEAD `a56bbed`, git status clean. Rerun: PASS, one generation, no retry. Failure cause: partly proven, see end.

## Failed run (disk only, no LLM call)
1. **Reasoning.** One shared field `Configuration.reasoning="none"` (`config.py:207`, `--reasoning` default `main.py:131`) feeds both engines (`generate.log:9-10`). The first critic call sent `none`, the provider answered 400, `_create_completion` (`provider_engines.py:173-202`) resent `low` and kept `self.reasoning="low"` on that engine (`generate.log:69`). The labeling critic is the same instance (`generate_rm.py:351`, `generation.py:547`), so by code it sent `low`. The request itself was not logged. The rerun confirms it (call 5: low before, low sent).
2. **Reply shape.** Path: `_generate_labeling` (`generate_rm.py:341`) → `_refine_labeling` (`generation.py:560`, 3 rounds: generator, AST check, critic) → `review_labeling` (`generic_engine.py:127`) → `_request_chat_completions` (`provider_engines.py:147`) → `completion_text` (`structured.py:205`) → `parse_critic` json.loads (`structured.py:131-137`), which wrote the message. Empty content is rejected before it: `structured.py:211-213` raises "returned no structured proposal" and `errors.py:40-41` passes it through unchanged, so the last reply was **non-empty**. Whitespace-led and cut-off JSON are ruled out by "(char 0)". Left: text whose first character is not a JSON start (a fence, prose, thinking text). Finish reason, token counts, length and which of those: **not recorded**.
3. **Same each time?** **Not recorded.** Only `attempts[-1]` is named (`generate_rm.py:355-358`). `bundle/attempts.json` is `[]`. Failed rounds keep `error=str(error)` only, `raw_response` is always "" (`generation.py:554,590`). Rounds 1-2 may have been AST failures, critic rejections or the same parse failure. Timing (16.9 s for 3 rounds, the rerun's one round took 4.3 s) fits 3 full generator+critic rounds, not proof.

## Rerun (`E=$L/evidence/close/L23-rerun/`, 10:12-10:13, `PYTHONPATH=app`, README Slice 2 commands)
- Runner `capture_run.py`: wraps `OpenCodeEngine._create_completion`, appends one line per call to `critic-calls.jsonl`, then `runpy`-runs `app/main.py` as `__main__` (it has no `main()`; same args as README step 2). Checked offline on fake replies first; no tracked file edited.
- 1 embeddings server: `/health` was down, started, ok (PID 1988957). 2 generate: exit 0 in 15 s, accepted on attempt 1, labeling accepted on round 1; `reward_machine.txt` has `ACCEPTING_STATES: u0` and `PENDING_PROMISES: u1: hard 1, soft 0`. 3 train: exit 0. 4 test: exit 0, `exit_rate` 1.0, `rm_accept_rate` 1.0 (1 episode). 5 replay: exit 0, 33/33 PASS. 6 llama stopped by PID, `/health` down; own `outputs/runs/l2-3-smoke/` deleted.

## Rerun (1)-(3) from `critic-calls.jsonl` (5 calls)
1. Critic calls: compile critic `none`→`low` (1.65 s, 88 tokens, 31 reasoning tokens, separate `reasoning_content` field of 115 chars, stop). Labeling critic `low`→`low`: finish stop, 122 tokens, 0 reasoning tokens, no reasoning field, no refusal, 585 chars.
2. No bad reply. The labeling critic answered pretty-printed JSON starting `{\n"accepted": true,` (valid, no fence).
3. One labeling round, no retry needed.

## Cause
- Proven: `parse_critic` failed on the last of 3 labeling rounds; the content was non-empty and did not start with JSON. The critic ran at `low` after the forced switch. Cannot be a max-token cut-off of JSON.
- `low` alone does not break it: two `low` calls in the rerun returned clean JSON (n=1, so intermittent not excluded).
- Unproven: the bad text, rounds 1-2, intermittent vs candidate-dependent (the critic prompt embeds varying generated code), truncation of reasoning-only text. A repeat sweep with `capture_run.py` would settle it. Product gap: no raw critic reply is kept on `CriticValidationError` (outside this packet's bounds).
- Side effects (Git-ignored): `logs/run-20261027T091233.699722Z.log`, `models/state_embeddings/bundle/` overwritten. Nothing left running.

Memory candidates: (a) `capture_run.py` logs reply shape per OpenCode call, reusable for any critic failure. (b) Critic and generator share one `reasoning` field; glm-5.3-flash always ends at `low`. (c) L2.3 generate now takes about 15 s, not 1 min.
