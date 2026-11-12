# Published Reward Machines

## `CRAFT-RM-1`

Appendix A.9 prints the following RM:

```text
REWARD_MACHINE:
STATES: u0, u1, u2, u3
INITIAL_STATE: u0
TRANSITION_FUNCTION:
(u0, get_wood) -> u1
(u0, else) -> u0
(u1, get_stone) -> u2
(u1, else) -> u1
(u2, get_iron) -> u3
(u2, else) -> u2
(u3, get_diamond) -> u4
(u3, else) -> u3
REWARD_FUNCTION:
(u0, get_wood, u1) -> 0.25
(u0, get_stone, u1) -> 0.5
(u0, get_iron, u1) -> 0.75
(u0, get_diamond, u1) -> 1.25
```

Source: paper Appendix A.9, `docs/ARM-FM/ARM-FM.md`.

This published block is internally inconsistent: `u4` is used but not declared, and
the last three reward entries name transitions different from those in the transition
function. Preserve it as evidence; do not use it as a validated oracle.
