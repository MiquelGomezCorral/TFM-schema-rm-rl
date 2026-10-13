Unary templates take one proposition `a`:

- `Existence(a)`: `a` is true at least once. This is a goal.
- `ExistenceTwo(a)`: `a` is true at two different time steps. This is a goal.
- `Absence(a)`: `a` is never true. This is a rule.

Binary templates take two propositions `a`, `b`, in this order:

- `RespondedExistence(a, b)`: if `a` ever happens, `b` also happens at some time,
  before, with, or after `a`. It holds when `a` never happens.
- `Response(a, b)`: every time `a` happens, `b` happens on that step or later. It holds
  when `a` never happens.
- `Precedence(a, b)`: `b` does not happen before `a` has happened; `b` on the same step
  as the first `a` is fine. It also holds when neither happens, and when only `a`
  happens. It does not require `a` or `b` by itself, but `Existence(b)` together with
  `Precedence(a, b)` forces `a` to happen too.
- `ChainResponse(a, b)`: every time `a` happens, `b` happens on the very next step. An
  `a` on the last step of an episode fails it.
- `NotCoExistence(a, b)`: `a` and `b` never both happen during the episode, in either
  order.

Only `Existence` and `ExistenceTwo` ask for something to happen. Every other template is
a rule that holds when nothing happens.

<!-- priorities -->

- `hard`: the task requires it. A hard goal must be reached before the task is finished,
  and a hard rule that is broken for good fails the task. This is the default.
- `soft`: the task only prefers it, with wording such as "if possible", "preferably",
  "ideally", "try to", or "when you can". A soft clause never decides whether the task is
  finished; breaking it costs reward and honoring it earns a little.
