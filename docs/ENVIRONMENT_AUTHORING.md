# Writing an environment's files

Each environment has two files:

- **`environment.md`, the facts.** The clause generator and the critic read this file and nothing
  else. It holds the environment at the top level only: what each proposition means and when the
  environment emits it, what can and cannot happen, one real trace and example tasks, in plain
  words. No implementation: no `## Labeling API`, no source links, no gym ids or package
  versions, no code expressions, no file paths, no citations, no run counts, no build steps. An
  agent that only builds a Reward Machine never needs them, and they fill its context.
- **`environment-code.md`, the implementation.** It holds all of it: the `## Labeling API`, source
  and runtime, truth conditions in code, evidence (run counts, how traces were produced), links,
  build steps, and any reason that cites the labeling code or prompts. It adds to the facts file
  and never copies it: it refers to `environment.md` by section and proposition id. Steps that
  write code read both files as one text, the facts file first, a blank line, then the code file
  (`EnvironmentDescription.from_file(path, code=True)`): the ARM-FM baseline generator
  (`generate-larm`) and the labeling stage (`generate-rm --labeling`, also in ARM-FM compiler
  mode). The clause generator and the critic read the facts file alone.

The test for every line: would someone framing propositions and a Reward Machine need it? If it
only helps implement or verify, it goes to `environment-code.md`.

Whatever `environment.md` does not say, the generator and the critic guess. A guess becomes a
clause the environment already guarantees, and so a Reward Machine state it cannot reach
(KeyCorridor: 13 states, 6 encode orders the environment cannot produce). So the facts file
carries checked facts and says plainly what is not known. Never write a plausible guess.

## Rules

- Every fact in `environment.md` is checked against the environment's code or a real run. The
  check goes in `environment-code.md` as `[code: file:function]` or `[run: script]`.
- When the source does not say, `environment.md` says so in plain words ("It is not known
  whether the thermos can move without the stick"). Not known beats a guess.
- A constraint comes from the source code or from an observed run, never from intuition. A run
  only supports "no counterexample in N episodes"; prefer the code.
- When a proposition's description leaves a reading open, `environment.md` names the reading it
  uses and why, in plain words ("This file reads `key_lost` as the step the key is dropped").
- `environment.md` stays under 120 lines and `environment-code.md` under 120 lines. The facts
  file sits in every generator and critic prompt.
- Keep proposition ids, the `## Propositions` lines, and the `## Labeling API` text
  (in `environment-code.md`) unchanged. The compiler and the benchmark depend on them.
- Ids are unique, match `^[a-z_][a-z0-9_]*$`, and are never `true` or `false`
  (`.agents/conventions.md`).
- Every truth condition must be computable by the labeling code. It sees only the
  `## Labeling API` section of `environment-code.md` and
  `env.episode_memory["previous_valuation"]`, the complete
  valuation of the step before. Each predicate is one expression, with no loops, assignments
  or helper calls. So a condition can use the current state and the previous valuation, and
  nothing older. A latch is "true now, or true at the previous step". An event compares the
  previous step with the current one. Nothing else remembers. No field of view, no visibility
  mask and no "ever happened" beyond that self-reference exist. If a reading needs more,
  change the reading or say it is not known.

## `environment.md` sections, in this order

`# <Environment name>`, then exactly these eight sections:

1. `## Environment`: layout, objects, what changes between episodes, the actions the agent has.
2. `## Objective and episode boundary`: what ends the episode, when reward is given, the step
   limit.
3. `## Proposition semantics`: for each proposition, its kind and exact truth condition in plain
   words (table below), and the reading chosen where the description leaves one open.
4. `## Constraints`: physical facts the generator and the critic read.
5. `## What the agent can and cannot do`
6. `## Example trace`: one real successful episode.
7. `## Propositions`: exact syntax `` - `id`: description ``, one line each, ids matching
   `^[a-z_][a-z0-9_]*$`. The parser reads this section only and rejects any other line.
8. `## Example tasks`

The proposition lines stay one line, so kind and truth condition go in
`## Proposition semantics`, not in the description.

## Proposition semantics

One row per proposition:

    | id | kind | true when |
    | `has_key` | condition | the agent carries the yellow key |
    | `at_goal` | condition, last step only | the agent stands on the goal cell |

- **event**: true only on the step it happens, false on every other step. It compares the
  previous valuation with the current state, for example "`has_key` was true at the previous
  step, is false now, and the door is not open".
- **condition**: true while a state holds; it may turn false again.
- **latch**: once true, true until the episode ends. Written as "the condition holds now, or
  this proposition was true at the previous step".

Write what is true in the world, not how code reads it. The code expression for each row goes
in `environment-code.md`.

## Constraints

One constraint per bullet. The shape opens the bullet, the reason follows the colon. Its
source goes in `environment-code.md`, not here. The generator and the critic read this section as text; the critic rejects a
clause that restates one of these facts. The compiler never removes states because of it. Keep
to three shapes as a writing convention:

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
can turn false again", "an event can repeat"). Say plainly when a rule is not known.

## Example trace

A numbered list of one real successful episode. Per step: the action, then the propositions
that turn true or false at that step. Collapse runs of steps that change nothing ("4 turns and
moves"). Say in one line what the episode shows; the solver, search, script, seed and counts
go in `environment-code.md`.

## `environment-code.md` sections, in this order

The labeling steps parse the facts file and this file as one text, so this file never has its
own `## Propositions` heading (the parser rejects a second one).

1. `# <Environment name>: code notes`, then one line: "Addition to `environment.md`; read both.
   Facts live there; this file says where they come from and how code reads them."
2. `## Source and runtime`: official source, version or commit, gym id, the pinned package
   versions, how to build the environment, and what `[code]` and `[run]` point to.
3. `## Truth conditions in code`: per proposition id, the expression over the runtime state that
   the labeling code can compute (see the rules above), including how an event or a latch uses
   the previous valuation.
4. `## Evidence`: per fact of `environment.md`, named by its section and a few words or its
   proposition id, the `[code: file:function]` or `[run: script]` that supports it. Runs give
   script, seeds and counts: how many episodes reached the premise, not only how many ran.
5. `## Labeling API`: the exact attributes and calls the labeling code may read, with types and
   meaning, plus any hint on how to use them. The labeling generators receive this text as the
   only runtime surface; name nothing that does not exist on the real env. Required to generate
   labeling or train. Leave the section out when the environment has no labeling surface: any
   text under this heading counts as a declared API.

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
