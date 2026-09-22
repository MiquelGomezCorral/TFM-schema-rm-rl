Environment:
${environment}

Task:
${task}

Reward Machine:
${candidate}

Candidate labeling code:
${labeling}

The previous valuation is read-only complete episode memory from the preceding environment
step. Persistent propositions describe current state; event propositions may compare current
state with it. Predicates must not mutate the environment or episode memory.

Return JSON: {"accepted": true|false, "feedback": "..."}
