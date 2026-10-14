# Writing an environment file

The generator and the critic read only this file. Whatever it does not say, they guess. A
guess becomes a Reward Machine state the environment cannot reach (KeyCorridor: 13 states,
6 encode orders the environment cannot produce). So the file carries facts, real examples,
and an honest `unknown` where the source is silent. Never write a plausible guess.

## Rules

- Every fact carries a source: `[code: file:function]`, `[run: script]`, or the word `unknown`.
- Write `unknown` when the source does not say. `unknown` beats a guess.
- A constraint comes from the source code or from an observed run, never from intuition.
  Say which. A run only supports "no counterexample in N episodes"; prefer the code.
- Target under 150 lines. The file sits in a prompt.
- Keep proposition ids, the `## Propositions` lines, and the `## Labeling API` text
  unchanged. The compiler and the benchmark depend on them.
- Ids are unique, match `^[a-z_][a-z0-9_]*$`, and are never `true` or `false`
  (`.agents/conventions.md`).
- Every truth condition must be computable by the labeling code. It sees only the
  `## Labeling API` section and `env.episode_memory["previous_valuation"]`, the complete
  valuation of the step before. Each predicate is one expression, with no loops, assignments
  or helper calls. So a condition can use the current state and the previous valuation, and
  nothing older. A latch is "true now, or true at the previous step". An event compares the
  previous step with the current one. Nothing else remembers. No field of view, no visibility
  mask and no "ever happened" beyond that self-reference exist. If a reading needs more,
  change the reading or write `unknown`.

## Sections, in this order

1. `# <Environment name>`
2. `## Source and runtime`: official source, version or commit, gym id, the pinned package
   versions, and what `[code]` and `[run]` point to.
3. `## Environment`: layout, objects, what is random per reset, the actions the agent has.
4. `## Objective and episode boundary`: what ends the episode, reward, step limit.
5. `## Proposition semantics`: for each proposition, its kind and exact truth condition
   (table below). If the description leaves a reading open, say which reading the table
   uses and mark it `reading`.
6. `## Constraints`: physical facts the compiler and the critic may rely on.
7. `## What the agent can and cannot do`
8. `## Example trace`: one real successful episode.
9. `## Labeling API`: only where labeling or training applies. Rules unchanged
   (`EnvironmentDescription.require_labeling_api`).
10. `## Propositions`: exact syntax `` - `id`: description ``, one line each, ids matching
    `^[a-z_][a-z0-9_]*$`. The parser reads this section only and rejects any other line.
11. `## Example tasks`

The proposition lines stay one line, so kind and truth condition go in
`## Proposition semantics`, not in the description.

## Proposition semantics

One row per proposition:

    | id | kind | true when |
    | `has_key` | condition | `env.carrying` is a yellow key |
    | `at_goal` | condition, last step only | the agent's cell holds the goal |

- **event**: true only on the step it happens, false on every other step. It compares the
  previous valuation with the current state, for example "`has_key` was true at the previous
  step, is false now, and the door is not open".
- **condition**: true while a state holds; it may turn false again.
- **latch**: once true, true until the episode ends. Written as "the condition holds now, or
  this proposition was true at the previous step".

A truth condition names what the labeling code can read (see the rule above).

## Constraints

One constraint per bullet. The shape opens the bullet, the reason follows the colon, the
source comes last. The compiler parses this section (`EnvironmentDescription.constraints`) and
uses it to drop the states and transitions the environment cannot reach; it is strict: every
bullet must be one of the three shapes with declared proposition ids, and anything else is
rejected with its line number. Three shapes exist:

- `` `b` cannot become true before `a` ``: only a toggle with the key unlocks the door.
- `` `a` and `b` never hold together ``: the agent carries one object.
- `` `a` cannot become false once true ``: no code path undoes it.

Three names that exclude each other are three pairs, three bullets. Two orders are two bullets.
"All latches stay true" is one bullet per latch. Facts that fit no shape ("an event is the last
step", "`door_open` can turn false again") go under `## What the agent can and cannot do`.
A constraint that holds only in one mission or configuration says so. Do not list an order
that only held in your runs because the explorer was biased. Check it against the code.

## What the agent can and cannot do

Actions with their exact conditions (what `pickup`, `drop`, `toggle` need), what is
blocked, what is irreversible, and what can happen that a reader might doubt ("`door_open`
can turn false again", "an event can repeat"). Mark unverified rules `unknown`.

## Example trace

A numbered list of one real successful episode. Per step: the action, then the propositions
that turn true or false at that step. Collapse runs of steps that change nothing ("4 turns and
moves"). Name where it comes from: the script and seed of a run, or the code
(`file:function`) when no run was possible. A trace made by a debug path says so. A layout
count or a run count says how many episodes reached the premise, not only how many were run.

## How to collect evidence

1. Read the environment's own code for layout, rules and termination.
2. Write a scripted solver for the task. Log every proposition's truth value after each
   step. Keep the raw log next to the script.
3. Run many seeds of a random macro policy and count: orders (`b` true while `a` never was),
   joint truth, true-then-false. Zero counterexamples support a constraint. Confirm it in the
   code. A random policy that always opens the door proves nothing about the door.
4. Check layout claims over many seeds (counts, reachability, colors).
5. Test each rule you write down in a minimal scenario (`toggle` without a key, `pickup` with
   full hands, `drop` on an occupied cell).

## Future ablation (not run)

Remove sections one at a time and measure clause accuracy and critic rejections:
- full file against file without `## Example trace`;
- full file against file without `## Constraints`;
- full file against file without `## What the agent can and cannot do`;
- each removal on the benchmark tasks, 3 runs each, same model and level;
- compare unreachable states per Reward Machine and critic rejection counts;
- keep a section only if its removal costs accuracy or adds rejections.
