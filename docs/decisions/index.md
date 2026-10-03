# Decision records

This is the router for durable decisions that preserve important product or architecture intent.
Records are grouped by product capability and then by a stable concern, so agents can read the
smallest relevant set before planning or reviewing a change.

- [ARM-FM catalogue and evidence](arm-fm/catalogue-and-evidence.md) — source coverage,
  evidence levels, reconstructed task bundles, and the environment artefact layout.
- [ARM-FM task and RM identity](arm-fm/task-and-rm-identity.md) — task boundaries,
  clause composition, shared RM text format, and compiler critic responsibilities.
- [ARM-FM reproduction boundary](arm-fm/reproduction-boundary.md) — complete baseline
  reconstruction, RM-only substitution, context boundaries, and reproduction limits.
- [ARM-FM RM execution](arm-fm/rm-execution.md) — complete valuations, relevant guards,
  ordered overlap handling, `else` fallbacks, graph defaults, and one update per step.
- [Run observability](generation/run-observability.md) — typed stage events, dual Run
  views, failure reasons, local diagnostics, retention, and secret exclusion.
