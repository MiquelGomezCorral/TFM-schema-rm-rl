# L1.4 live test: real CLI, user's flow (close wave, test id L14)

Result: PASS, 3/3 runs.

## Commands
Run from worktree `TFM-schema-rm-rl-rule-only` (HEAD `a56bbed`, branch `feat/rule-only-rewards`), 3 runs in parallel (N = 1..3):
`LIVE_OUT=$E/runN PYTHONPATH=app dotenv -f <main>/.env run --no-override -- python -W ignore -B .../compiler-ibm-flat/samples/run_cli.py generate-rm --environment examples/arm-fm/minigrid-doorkey/environment.md --task "$(cat $L/samples/l1_4-task.txt)" --model deepseek-v4.1-flash --output l1_4-runN.rm --trace-dir $E/runN/traces --steps-report $E/runN/steps.md`

Environment: conda `RM_RL_env`, Python 3.13. Sample: `samples/l1_4-task.txt`. One LLM generation per run, `deepseek-v4.1-flash`. `.env` not read.

## Expected
No hard goal clause; empty `FINAL_STATES:`; trigger edge negative, fix edge positive; no "inert"/"no reward effect" warning; `ACCEPTING_STATES:` and `PENDING_PROMISES:` present.

## Observed (all 3 runs exit 0)
| Run | Reviewed clause | Trigger edge | Fix edge | FINAL_STATES | ACCEPTING / PENDING |
|---|---|---|---|---|---|
| 1 | Response, hard: key lost → key picked up again | -0.1 | +0.1 | empty | present |
| 2 | same shape (`Whenever you drop the key, pick it up again`) | -0.1 | +0.1 | empty | present |
| 3 | same shape (`...must pick it up again at some later step`) | -0.1 | +0.1 | empty | present |

- RM text (all 3): STATES u0, u1; ACCEPTING_STATES u0; `PENDING_PROMISES: u1: hard 1, soft 0`.
- Only warning line in each run: "Rule-only task: no hard goal clause, so the machine has no final state; progress is paid toward the states where no clause is pending, and episodes end on a well, the environment's end, or the time limit". No inert or no-reward-effect warning.
- The clause is a Response (rule), not a goal, so no hard goal clause is expected.

## Evidence
- `run1/`, `run2/`, `run3/`: `exit.txt`, `stdout.txt`, `steps.md`, `steps-svgs/`, `traces/`, `outputs/RMs/l1_4-runN.rm`, `logs/`.

## Side effects and cleanup
- Outputs written under `E/runN/`, plus the README's named `logs/` and `models/` in the worktree (both Git-ignored).
- No background processes left; each run ended on its own. No product code, samples or decision records edited. No Git actions.

## Gaps
- No goal-clause (final-state) machine was tested; that is out of L1.4's scope.

Memory candidates: none
