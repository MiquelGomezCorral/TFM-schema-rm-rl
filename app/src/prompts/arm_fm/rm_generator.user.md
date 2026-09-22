Environment and documented API:
${environment}

Task:
${task}

Available environment API (the only legal observation surface):
${api}

Previous attempts and feedback:
${history}

Return only:
REWARD_MACHINE:
STATES: u0, ...
INITIAL_STATE: u0
FINAL_STATES: uN
TRANSITION_FUNCTION:
(u0, event) -> u1
(u0, else) -> u0
REWARD_FUNCTION:
(u0, event, u1) -> 0.1

Declare every accepting state in `FINAL_STATES`. Include one per-state `else` self-loop
for valuations not covered by ordinary guards. Do not output Markdown fences, comments,
or explanations.
