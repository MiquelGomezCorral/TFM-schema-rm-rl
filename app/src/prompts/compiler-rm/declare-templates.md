Every template takes declared propositions `a` (and `b`) in the order shown. The last
column is the LTLf formula IBM's nl2ltl builds for it.

| Template | Arguments | Kind | Meaning | IBM LTLf |
| --- | --- | --- | --- | --- |
| `Existence` | `a` | goal | `a` is true at least once. | `(Fa)` |
| `ExistenceTwo` | `a` | goal | `a` is true at two different time steps. | `(F(a&(X(Fa))))` |
| `Absence` | `a` | rule | `a` is never true. | `(~(Fa))` |
| `RespondedExistence` | `a`, `b` | rule | If `a` ever happens, `b` also happens at some time: before, with, or after `a`. It holds when `a` never happens. | `((Fa)->(Fb))` |
| `Response` | `a`, `b` | rule | Every time `a` happens, `b` happens on that step or later. It holds when `a` never happens. | `(G(a->(Fb)))` |
| `Precedence` | `a`, `b` | rule | `b` does not happen before `a` has happened; `b` on the same step as the first `a` is fine. It also holds when neither happens, and when only `a` happens. It does not require `a` or `b` by itself, but `Existence(b)` together with `Precedence(a, b)` forces `a` to happen too. | `(((~b)Ua)\|(G(~b)))` |
| `ChainResponse` | `a`, `b` | rule | Every time `a` happens, `b` happens on the very next step. An `a` on the last step of an episode fails it. | `(G(a->(Xb)))` |
| `NotCoExistence` | `a`, `b` | rule | `a` and `b` never both happen during the episode, in either order. | `((Fa)->(~(Fb)))` |

In the `Precedence` formula, `\|` stands for `|`; the backslash only escapes the table.

Only goals (`Existence`, `ExistenceTwo`) ask for something to happen. Every rule holds when
nothing happens.

Pick the template from the task's own wording:

| Wording in the task | Template |
| --- | --- |
| a command: "eventually", "make sure `a` happens", "reach `a`", "do `a`" (never the condition of an "if") | `Existence(a)` |
| "twice", "at two different moments" | `ExistenceTwo(a)` |
| "never", "do not ever" | `Absence(a)` |
| "if `a` (ever) happens, `b` must also happen", "`a` means `b` too / as well", "... before or after `a`" (`b` may come first) | `RespondedExistence(a, b)` |
| "whenever / every time / each time / if / when / should `a`, `b` must happen", "`b` afterwards / later / at that moment" | `Response(a, b)` |
| "after", "only after", "not before", "never `b` before `a`", "first `a`, then `b` is allowed" | `Precedence(a, b)`, plus `Existence(b)` when `b` is required |
| "do not `b` until / unless `a`", "do not `b` while `a` has not happened yet" (still closed, still off) | First read `b`'s description. When it already holds the condition (an event defined as "lost before `a` happened"), the ban is plain `Absence(b)`. Otherwise `Precedence(a, b)`: the ban ends once `a` has happened. A bare "never `b`" stays `Absence(b)` |
| "carry / bring `c` to `a`", "reach `a` with / holding `c`" | `Existence(a)` + `Response(a, c)`; `Existence(c)` alone lets `c` be held anywhere |
| "whenever `a`: do `b`, then `c`, then `d`" | `Response(a, b)`, `Response(b, c)`, `Response(c, d)`: each step follows the one before it, never all from `a`; a step that is only a lasting condition ("fetch the item", `holding_x`) gets no clause |
| a command "do `a` before `b`", "do `a`, then `b`", "first `a`, then `b`" | `Existence(a)` + `Precedence(a, b)`; when `b` is also commanded, `Existence(b)` + `Precedence(a, b)`, which already forces `a` |
| a listed sequence "`a`, `b`, `c`, and then `d`" | `Existence` of the last event and `Precedence` between each consecutive pair, which already force the earlier events; no order between events the list does not relate |
| "right after", "immediately after", "in the very next step" | `ChainResponse(a, b)` |
| "never both", "not both during the episode" | `NotCoExistence(a, b)` |

In an "if `a` ..." sentence, only "`b` also / too / as well" or "before or after" means
`RespondedExistence`; any other "`b` must" is `Response`. The event of an "if / whenever / each time" condition is
not a goal: it gets no `Existence`. An unconditional "do `a` at some point" is `Existence(a)`.
"Next step" always means `ChainResponse`.

`Response(a, b)` needs `b` at or after the last step `a` is true. When `a` is a condition that
lasts (`holding_x`) and `b` a one-step event, it never closes if `b` happens while `a` still
holds. In a chain, skip a step that is only such a condition and link the events around it:
"whenever `a`: take `b`, fetch `x`, do `c`, then `d`" is `Response(a, b)`, `Response(b, c)`,
`Response(c, d)`, with nothing for the fetch.

Worked examples, with neutral identifiers:

- "Do `b` only after `a`", "Do `a`, then `b`": `Existence(b)` hard and `Precedence(a, b)`
  hard, not `Precedence` alone, which requires nothing. Together they already force `a`, so
  leave out `Existence(a)`.
- "If `a` happens, `b` should also happen at some point": `RespondedExistence(a, b)` hard,
  not `Response(a, b)`, because the wording does not put `b` after `a`.
- "Whenever `a` happens, `b` must happen in the very next step": `ChainResponse(a, b)` hard,
  not `Response`.
- "Carry `c` to `g`": `Existence(g)` and `Response(g, c)`, both hard. `Existence(g)` alone
  lets the agent reach `g` without `c`; `Existence(c)` lets it hold `c` anywhere.
- "If `a` happens, `c` must hold" or "if `a` happens, `b` must have happened first":
  `Response(a, c)` or `Precedence(b, a)` hard, and nothing else. `a` is a condition, not a
  goal: an `Existence(a)` would force the agent to reach it.
- "Do not `b` while `a` has not happened yet" ("while the gate is still shut", "until `a`"):
  first read the description of `b`. If it already contains that condition (`b` is "dropped
  while the gate is shut"), the ban is `Absence(b)`: no `Precedence`. Otherwise it is
  `Precedence(a, b)`, so the clause keeps the condition the task states. "Try not to" makes
  it soft.
- "Do `c`, and preferably `b` right after `a`": `Existence(c)` hard and
  `ChainResponse(a, b)` soft. Do not add a `Precedence` or any other order rule the task
  never states.
- "Do `a`, `b`, and then `c`": `Existence(c)` hard with `Precedence(a, b)` and
  `Precedence(b, c)` hard; the chain forces `a` and `b`. Do not add `Precedence(a, c)`; the
  chain already implies it.

<!-- priorities -->

Every clause is `hard` or `soft`. The priority never changes what the template means.

- `hard`: the task requires it. A hard goal must be reached before the task is finished,
  and a hard rule that is broken for good fails the task. This is the default.
- `soft`: the task only prefers it, with wording such as "if possible", "preferably",
  "ideally", "try to", "when you can", or "it would be nice". A soft clause never decides
  whether the task is finished; breaking it costs reward and keeping it costs nothing.

Choose `soft` only when the task words the clause as a preference. Without such a cue,
"never", "must", "before", "then", and "only after" are hard. A clause scoped by a
preference cue is soft even when it contains "never" or "must": "if possible, never do `c`"
is a soft `Absence(c)`, and "preferably reach `a`" is a soft `Existence(a)`.

Mark a clause hard or soft on its own wording, not on the rest of the task. Tasks may mix
both, and each clause of one task gets its own priority. A preference cue scopes the phrase
or requirement it modifies, not the whole sentence and not the task: in "Reach `g`, and
ideally `b` right after `a`" the cue covers only "`b` right after `a`", so `Existence(g)` is
hard and `ChainResponse(a, b)` is soft, with no hard order clause.
