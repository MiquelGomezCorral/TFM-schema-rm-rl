# IBM nl2ltl DECLARE Templates

IBM `nl2ltl` defines eight DECLARE templates in
`dependencies/nl2ltl/nl2ltl/declare/declare.py`.

See `docs/LTLF_TASK_LANGUAGE.md` for the non-expert language contract, the
teacher-proposed LTLf patterns, and the distinction between composite tasks and
multi-task training.

| Template | Arguments | Meaning | LTLf |
|---|---:|---|---|
| `Existence(a)` | 1 | `a` happens at least once. | `F(a)` |
| `ExistenceTwo(a)` | 1 | `a` happens at least twice. | `F(a & X(F(a)))` |
| `Absence(a)` | 1 | `a` never happens. | `!F(a)` |
| `RespondedExistence(a, b)` | 2 | If `a` happens, `b` must happen somewhere, before or after it. | `F(a) -> F(b)` |
| `Response(a, b)` | 2 | Every occurrence of `a` must eventually be followed by `b`. | `G(a -> F(b))` |
| `Precedence(a, b)` | 2 | `b` cannot occur unless `a` has occurred. | `(!b U a) \| G(!b)` |
| `ChainResponse(a, b)` | 2 | Every occurrence of `a` must be immediately followed by `b`. | `G(a -> X(b))` |
| `NotCoExistence(a, b)` | 2 | `a` and `b` cannot both occur. | `F(a) -> !F(b)` |

## Operators

| Operator | Meaning |
|---|---|
| `F` | Eventually |
| `G` | Always |
| `X` | Next step |
| `U` | Until |
| `!` | Not |
| `&` | And |
| `\|` | Or |
| `->` | Implies |

## Current Pipeline Support

| Template | Current use |
|---|---|
| `Existence` | Supported. Uses IBM's `to_ltlf()` directly. |
| `ExistenceTwo` | Supported. Uses IBM's `to_ltlf()` directly. |
| `Precedence` | Supported as the selected pattern, but the final formula is built by `schema-rm-rl` for inferred `soft` or `hard` ordering. |
| `Absence` | Not executable in V1 because its reward and violation behavior is not defined yet. |
| `RespondedExistence` | Not executable in V1 because its reward and violation behavior is not defined yet. |
| `Response` | Not executable in V1 because its reward and violation behavior is not defined yet. |
| `ChainResponse` | Not executable in V1 because its reward and violation behavior is not defined yet. |
| `NotCoExistence` | Not executable in V1 because its reward and violation behavior is not defined yet. |

Each IBM template also provides:

- `to_ltlf()`: construct its future-time LTLf formula.
- `to_ppltl()`: construct its past-time temporal formula.
- `to_english()`: return a human-readable explanation.
