# ARM-FM rewards on transitions the machine never declared

Date: 2026-11-12, from the LI.2 event-room smoke (2026-11-12 05:20 to 05:25 CET). Two cards, one
model pair (generator `deepseek-v4.1-flash`, critic `glm-5.3-flash`): a data point, not a rate.

## What it shows

ARM-FM asks the model to write the whole machine: a `TRANSITION_FUNCTION` and a `REWARD_FUNCTION`.
On the two event-room cards, 3 of its 6 attempts never reached the critic. Our parser stopped them
with `Reward refers to nonexistent transition`: the reward section pays a self-loop (`(u1, box_fell,
u1)`) that the transition section never declares. The other 3 attempts parsed, and the critic
rejected them. With three attempts per card, neither card produced an accepted machine
(`pipeline-failed`, "no data").

The authors' code does not stop on such a row. It stores the row and never pays it
(`~/src/llms-rm-rl/src/rm/reward_machine.py`, read on 2026-11-12). We kept our parser's rule and the
error goes back to the model as the next ARM-FM round (user decision, 2026-11-12;
`docs/decisions/arm-fm/rm-execution.md`). The three attempts below are therefore a rule we added, not
a shared behaviour.

## The cards

| Card | Natural-language task | LTL (the card's expected clauses) |
| --- | --- | --- |
| `cx-siren` | Go to the exit, and whenever the siren rings, turn it off. | `F at_exit` (hard Existence) and `G (siren_ringing -> F switch_toggled)` (hard Response) |
| `cx-box` | Go to the exit, and whenever the box falls, pick it up again. | `F at_exit` and `G (box_fell -> F holding_box)` |

ARM-FM compiles no clauses: the model writes the machine directly, so the LTL above is what FARM
compiled for the same cards and what the judge checks, not something ARM-FM saw.

## The three attempts our parser stopped

None of these parse, so each is shown as text. The marked line is the reward row the parser names.

**`cx-siren`, attempt 2**:

```text
REWARD_MACHINE:
STATES: u0, u1
INITIAL_STATE: u0
FINAL_STATES: u0
TRANSITION_FUNCTION:
(u0, at_exit & !siren_ringing) -> u1
(u0, else) -> u0
(u1, else) -> u1
REWARD_FUNCTION:
(u0, at_exit & !siren_ringing, u1) -> 1.0
(u0, switch_toggled & siren_ringing, u0) -> 0.1
(u0, switch_toggled & !siren_ringing, u0) -> 0.1     <-- named by the parser; no such transition
```

The row above it (`switch_toggled & siren_ringing`) is undeclared too; the parser reports one row at a
time.

**`cx-siren`, attempt 3**:

```text
REWARD_MACHINE:
STATES: u0, u1, u2
INITIAL_STATE: u0
FINAL_STATES: u2
TRANSITION_FUNCTION:
(u0, siren_ringing & at_exit) -> u0
(u0, siren_ringing) -> u1
(u0, at_exit) -> u2
(u0, else) -> u0
(u1, switch_toggled & !siren_ringing & at_exit) -> u2
(u1, switch_toggled & !siren_ringing) -> u0
(u1, at_exit) -> u1
(u1, else) -> u1
(u2, switch_toggled) -> u2
(u2, else) -> u2
REWARD_FUNCTION:
(u1, siren_ringing, u1) -> 0.05                      <-- named by the parser; u1 only loops on at_exit and else
(u1, switch_toggled & !siren_ringing & at_exit, u2) -> 0.95
(u0, at_exit, u2) -> 0.95
(u1, switch_toggled & !siren_ringing, u0) -> 0.3
```

**`cx-box`, attempt 1**:

```text
REWARD_MACHINE:
STATES: u0, u1, u2
INITIAL_STATE: u0
FINAL_STATES: u2
TRANSITION_FUNCTION:
(u0, at_exit) -> u2
(u0, holding_box) -> u1
(u0, else) -> u0
(u1, at_exit) -> u2
(u1, else) -> u1
(u2, else) -> u2
REWARD_FUNCTION:
(u0, at_exit, u2) -> 1.0
(u1, at_exit, u2) -> 1.0
(u0, holding_box, u1) -> 0.2
(u1, box_fell, u1) -> 0.1                            <-- named by the parser; u1 has no box_fell transition
```

## The three attempts the critic rejected

These parse. The critic's full reasons are in `check/attempts/<card>/attempts.json`, in short:
`cx-siren` attempt 1 pays the exit and ignores the siren; `cx-box` attempt 2 has an exit transition
that can be taken with the box lying fallen; `cx-box` attempt 3 pays the exit from `u1` less (0.5)
than from `u0`, which the critic calls inconsistent.

## Evidence

- `check/attempts/{cx-siren,cx-box}/attempts.json`: the generation record of all six attempts
  (status, candidate text, parser error or critic feedback).
- `check/parse_attempts.py` parses the six candidates with the current parser and prints
  `3 of 6 candidates stopped at the parser`, with the same three errors.
- The LI.2 run itself: FARM completed both cards (replay 6/6 each); ARM-FM `pipeline-failed` on both,
  also after one extra try on `cx-siren`.

## Limits

Two cards, one generator model, three attempts each. The 3 of 6 is a count of what happened, not an
estimate of how often ARM-FM writes this kind of row. Whether the authors' own runs would have paid
more with our parser's rule relaxed is not tested: ARM-FM and FARM on the event room wait for the
10-attempt rerun (correction C3).

## Rerun

From the repository root, inside `RM_RL_env`, no LLM call:

```bash
PYTHONPATH=app python -W ignore docs/paper/li2-undeclared-reward-rows/check/parse_attempts.py
```

## Code

`_with_rewards` in `app/src/compiler/rm_format.py` raises the error; the retry loop that feeds it back
is `app/src/arm_fm/generation.py` (the `except Exception` branch of the attempt loop). The decision is
in `docs/decisions/arm-fm/rm-execution.md`. Wave head when this copy was made: `7ae1157`.
