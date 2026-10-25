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
than exact wording. The model reads the same catalogue, with cue words and worked
examples, from one prompt file that both the creator and the critic load:
`app/src/prompts/compiler-rm/declare-templates.md`. Extend it there; a new template also
needs an entry in `SUPPORTED_TEMPLATES` (`app/src/engines/structured.py`).

| Template | IBM LTLf (`to_ltlf()`) | Meaning on a finite trace | Example ordinary language |
|---|---|---|---|
| `Existence(a)` | `F(a)` | `a` is true at least once. | "Make sure a happens"; "eventually reach a". |
| `ExistenceTwo(a)` | `F(a & X(F(a)))` | `a` is true at two distinct time points. | "Do a twice"; "after doing a, do it again". |
| `Absence(a)` | `!F(a)` | `a` is never true. | "Never do a"; "avoid a". |
| `RespondedExistence(a,b)` | `F(a) -> F(b)` | If `a` happens, `b` happens too, in any order. | "If you open the door, also hold the key at some point". |
| `Response(a,b)` | `G(a -> F(b))` | Every `a` is followed later by `b`. | "Every time you pick up a, place it somewhere afterwards". |
| `Precedence(a,b)` | `(!b U a) \| G(!b)` | No `b` before `a`; also true when neither happens. A required `b` needs `Existence(b)` too. | "Open the door only after taking the key". |
| `ChainResponse(a,b)` | `G(a -> X(b))` | Every `a` is followed by `b` on the very next step. | "Right after a, do b". |
| `NotCoExistence(a,b)` | `F(a) -> !F(b)` | `a` and `b` never both happen. | "Never do both a and b". |

All 8 are executable, each with a `hard` or `soft` priority. The formula is always IBM's; the
priority only changes how the reward layer treats the clause (see
`docs/COMPILER_REWARD_DESIGN.md`). Patterns outside IBM's set (`Always`, `Next`,
`EventuallyAlways`) are not exposed.

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

The structured output for a composite task is a list of 1–25 normalized clauses with
conjunction semantics ("all hard clauses must hold"). Disjunction and arbitrary Boolean
nesting remain unsupported; preferences are soft clauses. Each clause is compiled to its own
DFA, then FL-AT builds the reachable product. If the task has a hard goal clause but no
reachable final state, it is rejected as having conflicting clauses rather than compiled
into an RM that can never finish; a task with no hard goal clause compiles as rule-only.

## Reward semantics

The reward layer computes every reward from the clause DFAs; the full rules and their sources are
in `docs/COMPILER_REWARD_DESIGN.md`. In short: progress shaping pays `0.1` per step closer to the
goal (longest remaining path, idle steps pay 0, cycles sum to 0), finishing pays `+1`, a hard
violation enters one rejecting well (`-1`, episode ends), a pending hard obligation blocks
finishing, and each soft clause pays `-0.5` when it breaks and `-0.5` if still pending at the
finish; keeping a soft clause earns nothing. LTLf cannot say "broken again", so by default
(recurrent soft rules on, switched off with `--no-recurrent-soft-penalty`) a soft `Absence`,
`Precedence`, `ChainResponse` or `NotCoExistence` is re-armed after a break and pays `-0.5` at every
new break; with the switch off it pays once. A task with no hard goal clause has no final state.

## Relationship to ARM-FM

ARM-FM generates one language-aligned RM for each task, including multiple RM states
for that task's subgoals. Its multi-task experiment associates tasks with separate
RMs and trains one policy using the language embedding of the active RM state. A novel
composite task receives its own RM and reuses familiar subgoal representations. The
recommended contract above preserves this separation while keeping the present
pipeline safer than ARM-FM: the model selects constrained semantics, one bounded critic
accepts or rejects the result within three attempts, and deterministic formal tools own
the automaton. The critic may be disabled, which warns and accepts every compiler
result without review, and a failed task prevents all batch output writes.
