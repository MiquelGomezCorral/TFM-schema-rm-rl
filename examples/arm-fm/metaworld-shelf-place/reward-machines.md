# Published Reward Machines

## `MW-RM-1`

Appendix A.9 publishes one generic RM for all reported Meta-World tasks:

```text
REWARD_MACHINE:
STATES: u0, u1, u2, u3, u4
INITIAL_STATE: u0
TRANSITION_FUNCTION:
(u0, near_object) -> u1
(u0, grasp_success) -> u2
(u0, else) -> u0
(u1, grasp_success) -> u2
(u1, not_near_object) -> u0
(u1, else) -> u1
(u2, not_grasp_success) -> u0
(u2, object_near_goal) -> u3
(u2, success) -> u4
(u2, else) -> u2
(u3, not_object_near_goal) -> u2
(u3, success) -> u4
(u3, else) -> u3
(u4, else) -> u4
REWARD_FUNCTION:
(u0, near_object, u1) -> 0.20
(u1, grasp_success, u2) -> 0.40
(u0, grasp_success, u2) -> 0.40
(u1, not_near_object, u0) -> -0.20
(u2, not_grasp_success, u0) -> -0.40
(u2, object_near_goal, u3) -> 0.80
(u3, not_object_near_goal, u2) -> -0.80
(u2, success, u4) -> 1.50
(u3, success, u4) -> 1.50
```

Source: paper Appendix A.9, `docs/ARM-FM/ARM-FM.md`.
