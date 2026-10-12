Environment and mission:
${environment}

Task:
${task}

Reward Machine:
${candidate}

Documented API:
${api}

Define exactly one predicate for every proposition declared in the environment description,
whether or not it appears in a Reward Machine guard.

Previous attempts and feedback:
${history}

Return only Python function definitions.

Each function must inspect only the documented snapshot interface. `env.episode_memory["previous_valuation"]`
is read-only and contains the complete valuation from the preceding environment step; use it
only for event propositions such as `key_lost`. Persistent propositions describe current state.
Predicates must not mutate the environment or episode memory. Do not define `else`.
Do not call `.get` on `env.episode_memory["previous_valuation"]`; use guarded bracket
access such as `env.episode_memory["previous_valuation"] and
env.episode_memory["previous_valuation"]["<proposition_id>"]`. Do not call another
generated predicate; inline its expression.
Every predicate must contain exactly one `return` statement and no assignments or
temporary names. Inline all current-state expressions and event checks; do not write
`prev = ...`, `cell = ...`, `x, y = ...`, or call another generated predicate.
