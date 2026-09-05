# Natural-Language Task and LTLf Contract

## Purpose

The user writes ordinary task language. The language model grounds that language to a
closed set of environment propositions and temporal patterns. Deterministic code then
constructs the LTLf formula and Reward Machine (RM). The language model must not write
LTLf, invent propositions, or design RM states and transitions directly.

This separates three concepts that must not be conflated:

1. **Propositions** are Boolean facts emitted by the environment, such as
   `has_key` or `passenger_delivered`.
2. **Temporal patterns** define how proposition truth values must evolve over a finite
   trace, such as “eventually” or “always”.
3. **Natural-language paraphrases** are the unrestricted ways a non-expert may express
   one of those patterns.

## Proposition contract

The environment Markdown remains the sole owner of the proposition vocabulary. Each
proposition description must state exactly when the proposition is true. Two semantic
kinds are relevant:

- **Event proposition:** true only on the step where an event occurs, for example
  `passenger_picked_up`.
- **Condition proposition:** true on every step where a condition holds, for example
  `door_open`.

This distinction matters. “Always deliver the passenger” is not meaningful when
`passenger_delivered` is a one-step event, while “always keep the door closed” is
meaningful when `door_closed` is a condition. The current Markdown syntax does not
encode the kind, so the description and human review must establish it until explicit
metadata is justified.

## Temporal pattern catalogue

The catalogue defines semantics, not keywords. The examples are guidance for the
language model; matching must be based on meaning and grounded propositions rather
than exact wording.

| Pattern | Canonical LTLf | Meaning on a finite trace | Example ordinary language |
|---|---|---|---|
| `Existence(a)` | `F(a)` | `a` is true at least once. | “Make sure a happens”; “eventually reach a”; “at some point, do a”. |
| `ExistenceTwo(a)` | `F(a & X(F(a)))` | `a` is true at two distinct time points. | “Do a twice”; “repeat a”; “after doing a, do it again”. |
| `Always(a)` | `G(a)` | `a` is true at every time point. | “Always keep a true”; “a must hold throughout”; “never leave a”. |
| `Next(a)` | `X(a)` | `a` is true at the immediately following time point. | “Do a next”; “a must happen immediately”; “on the next step, a”. |
| `Absence(a)` | `!F(a)` | `a` is never true. Equivalent to `G(!a)`. | “Never do a”; “avoid a”; “a must not happen”. |
| `EventuallyAlways(a)` | `F(G(a))` | From some time point through the end, `a` remains true. | “Eventually keep a true”; “reach a and stay there”; “after some point, always a”. |
| `Precedence(a,b)` | project-defined | Both occur and `a` is preferred or required before `b`, according to priority. | “Do a before b”; “prefer a first”; “b only after a”. |

`!F(a)` is the canonical representation of absence; `G(!a)` is accepted as an
equivalent explanation, not as a second pattern. `F(G(a))` is not equivalent to
`F(a)`: the former requires `a` to remain true through the rest of the trace.

Only `Existence`, `ExistenceTwo`, and project-defined `Precedence` are currently
executable. `Always`, `Next`, `Absence`, and `EventuallyAlways` remain candidate
patterns from the teacher's table. They are not exposed as executable until their
online reward and failure behavior is implemented and reviewed.

## Natural-language interpretation contract

For each task, the model must:

1. Identify one or more atomic requirements expressed by the user.
2. Map every requirement to exactly one supported temporal pattern.
3. Ground every pattern argument to a declared proposition identifier.
4. Preserve explicit ordering and repetition; never weaken a requirement to a simpler
   pattern merely because it is supported.
5. Refuse when the language is ambiguous, requires an unsupported pattern, or refers
   to an unavailable environment fact.

Critic prompts receive the original task, each normalized clause, and its grounded
propositions, canonical LTLf, and reward/violation behavior. This makes interpretation
errors visible before formal compilation.

Examples:

| User task | Normalized interpretation |
|---|---|
| “Could you make sure passenger one gets there eventually?” | `Existence(passenger_1_delivered)` |
| “Pick up the parcel again later.” | `ExistenceTwo(parcel_picked_up)` |
| “Do not enter the restricted area.” | `Absence(in_restricted_area)` |
| “Once stable, remain stable until the run ends.” | `EventuallyAlways(stable)` |
| “I would rather collect the key before opening the door.” | `Precedence(key_collected, door_opened)` with soft priority |

## Tasks, clauses, and multiple Reward Machines

One submitted **task** produces one RM. A task may contain several clauses, and those
clauses belong in the same RM when they jointly describe one objective. For example,
“collect the key, open the door, then reach the goal” is one task with nested temporal
requirements, not three unrelated tasks.

Several independent submitted tasks produce several RMs. They must not be merged into
one product RM merely to enable transfer. Following ARM-FM, multi-task learning uses
one task-specific RM per task and trains a shared policy conditioned on the current
RM state's language description or embedding. Transfer comes from that shared policy
and shared subgoal representation, not from physically joining all task automata.

The current structured output for a composite task is a list of 1–10 normalized clauses
with conjunction semantics (“all clauses must hold”). Disjunction, optional branches,
and arbitrary Boolean nesting remain unsupported. Each clause is compiled separately,
then the reachable conjunction product is built. If the product has no reachable state
where every clause is accepting, the task is rejected as incompatible rather than
compiled into an RM that can never finish.

## Reward semantics required before extending execution

- `Existence`: reward once when its required occurrence is first completed.
- `ExistenceTwo`: reward once on the second distinct occurrence.
- `Next`: reward on the next step if satisfied; otherwise enter a rejecting state.
- `Absence` and `Always`: treat violations as immediate rejection. Successful
  completion can only be confirmed when the finite trace ends.
- `EventuallyAlways`: successful completion can only be confirmed at trace end;
  rewarding an apparent stabilization earlier would allow a later violation after the
  reward has already been collected.
- Composite tasks: unary and preferred-order clause completion pays `+0.10` once;
  soft reverse or simultaneous completion pays `0`; hard reverse or simultaneous
  completion enters an absorbing zero-reward rejecting sink. Completion of every clause
  adds `+1.00`. Rewards must not be repeatable through cycles.

These terminal-trace semantics require an explicit episode-end signal from the future
RL runtime. Until that interface exists, terminal-only patterns remain specification
candidates rather than executable patterns.

## Relationship to ARM-FM

ARM-FM generates one language-aligned RM for each task, including multiple RM states
for that task's subgoals. Its multi-task experiment associates tasks with separate
RMs and trains one policy using the language embedding of the active RM state. A novel
composite task receives its own RM and reuses familiar subgoal representations. The
recommended contract above preserves this separation while keeping the present
pipeline safer than ARM-FM: the model selects constrained semantics, bounded critics
accept or reject the result within three attempts, and deterministic formal tools own
the automaton. At least one critic must remain enabled, and a failed task prevents all
batch output writes.
