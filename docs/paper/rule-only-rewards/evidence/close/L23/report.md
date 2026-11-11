# L2.3 live test, close wave (rule-only rewards), test id L23

Result: FAIL at step 2 (generation exit 1). Steps 3-5 not run: no bundle was written.

Environment: worktree `TFM-schema-rm-rl-rule-only`, HEAD `a56bbed` (`feat/rule-only-rewards`), `PYTHONPATH=app`,
`RM_RL_env`, provider `opencode`. Sample: `samples/l1_4-task.txt`.

Commands:
- Step 1: embeddings server by the README command; `/health` was down, then `{"status":"ok"}`. PID 1917439.
- Step 2: `generate-larm --mode compiler ... --bundle $E/bundle --embeddings --overwrite --model deepseek-v4.1-flash`,
  exit=1 (log: `$E/generate.log`).

Observed:
- Generator deepseek-v4.1-flash; critic glm-5.3-flash (product engine config, not passed by me).
- Proposal: one hard `Response(key_lost, has_key)`. Critic verdict: accepted True.
- RM before labeling: STATES u0, u1; INITIAL u0; FINAL_STATES empty; ACCEPTING_STATES: u0; PENDING_PROMISES: u1 hard 1, soft 0;
  u0 -(!has_key&key_lost)-> u1 pays -0.1; u1 -(has_key)-> u0 pays +0.1.
- Failure: "Labeling generation failed after 3 requests: Critic returned malformed structured output: Expecting value:
  line 1 column 1". No `reward_machine.txt` was written.

Not done: no retry (one-generation bound). Cause not verified: the failing call is the critic model at the labeling stage;
a second run would show whether it is intermittent.

Side effects: `logs/run-20261027T090457.337350Z.log` and possibly `models/state_embeddings/bundle/` (both ignored).
No `outputs/runs/l2-3-smoke/`. Git status clean.

Cleanup: embeddings server stopped by PID 1917439; `/health` down.

Memory candidates: the packet's "deepseek only" bound conflicts with the product default. The critic role runs
glm-5.3-flash on the opencode provider, and its labeling call failed on malformed JSON in this run.
