# Recurrent soft rules: which rules charge again, and why

A design note. It says which soft rules charge −0.5 again at every new break, why only those,
and what the other rules do instead. The user and the supervisor decided it on 2026-10-23; it
was merged into main on 2026-10-25.

## The problem

LTLf can only say that a rule was broken somewhere in the trace. So a soft rule charged −0.5
once per episode: an agent that broke a preference 15 times got the same reward as one that
broke it once.

## Which rules re-arm

The test is not a hand-picked list. A soft rule re-arms only if its automaton (MONA's DFA) has
a "broken for good" state: once that state is reached, no later step can fix the rule. Of the
eight templates, only Absence, Precedence, ChainResponse and NotCoExistence have one.

Re-arming rewrites a copy of that DFA before the product into the Reward Machine: the broken
state takes the start state's edges, so the rule watches again from the next step. A step
that breaks the rule again while it is still broken is free.

## Rules that break mid-episode: the goal is recovery

These four are prohibitions. The agent breaks one at a given moment (the door opens, `y`
happens before `x`), and it can break it again later. What we want is the agent to recover
and obey the rule again.

- **Otherwise the agent makes one mistake, then repeats it with no consequence.** With one
  charge per episode, the first break costs the whole penalty and the rule stays broken for
  good. Every later break is free, so the agent has no reason to go back to obeying it.
  Charging each new break gives it that reason.
- **Penalties are not farmed.** Breaking a rule again only lowers the return, so a charge that
  repeats never pays the agent for doing something over and over.

The supervisor's examples (`x` and `y` are the template's `a` and `b`, `-` is a step with
neither), with recurrent soft rules on:

| Template | Steps | Charges |
|---|---|---|
| `Absence(x)` | `x x` | 1 |
| `Absence(x)` | `x !x x` | 2 |
| `Precedence(x, y)` | `x y y` | 0 |
| `Precedence(x, y)` | `y - y x` | 2 |
| `ChainResponse(x, y)` | `x y` | 0 |
| `ChainResponse(x, y)` | `x - x -` | 2 |
| `NotCoExistence(x, y)` | `x y` | 1 |
| `NotCoExistence(x, y)` | `x y x` | 1 |
| `NotCoExistence(x, y)` | `x y x y` | 2 |

With the switch off, every row charges at most 1.

## Rules that only say "eventually": no repeat

Existence, ExistenceTwo and RespondedExistence say that something happens at some point. None
of them can break mid-episode: each is "not yet" until it happens, then "done" for good. The
only failure is that it never happened by the end of the episode. That is one fact at the end,
so there is no break to charge again.

- **Existence and ExistenceTwo are goals.** A recurring version would pay `x` again after a
  reset. The agent would learn to do `x`, undo it and do it again instead of finishing:
  reward farming. From a goal we want the agent to reach it, not to repeat it.
- **RespondedExistence has no exact recurring version.** It means "if `x`, then `y` at some
  point, in any order". It splits into two rules, and each depends on order:
  - `y` before `x` is Precedence(`y`, `x`). It can break mid-episode, so with recurrent soft
    rules on it charges every `x` that comes before the first `y`. This is the closest to a
    recurring RespondedExistence.
  - `y` after `x` is Response(`x`, `y`). Each new `x` opens a new obligation, but the rule
    never breaks mid-episode, so nothing is charged until the end.

  Keeping "any order" with its own `y` for each `x` needs counting; see the limitation below.
- **Response already re-arms.** Its DFA has no broken-for-good state.

## Limitation: the setup cannot count

Each rule is written in LTLf, MONA turns it into a DFA, and the Reward Machine is the product
of those DFAs. Each machine has a fixed, finite number of states, so it can tell apart only a
fixed number of counts. ExistenceTwo ("`x` at least twice") works because it only needs to
tell 0, 1, and 2 or more apart. None of them can compare two counts that grow without a bound,
such as "at least as many `y` as `x`".

That is why RespondedExistence cannot be made recurring for real. Giving each `x` its own
`y`, in any order, means keeping at least as many `y` as `x`, and no finite automaton keeps
that count. Any task that needs "as many `x` as `y`" hits the same limit.

## Not tried: reset the Reward Machine, keep the environment

In this project the episode ends when the Reward Machine reaches a final or rejecting state,
and the next episode starts the machine fresh. Doing the task again is a new episode.

A different framework could keep the environment running and send the machine back to its
start each time it finishes, so the agent collects the goal reward again in the same episode.
That is valid, and it has been done:

- **Reward Machines.** In the cookie domain of Toro Icarte et al. (2019), the agent gets +1
  for eating a cookie and may then press a button for a new one. The +1 edge goes back to the
  machine's initial state, and an episode lasts 5,000 steps, so the agent eats as many
  cookies as it can.
- **Infinite traces.** In temporal logic this is "always eventually `x`" (`GF x`), a
  recurrence property. It needs infinite traces: in LTLf, `GF x` only says that `x` holds at
  the last step. Model-free RL can learn such objectives through Büchi automata, whose
  acceptance asks for an accepting transition infinitely often (Hahn et al., 2019).

Two conditions make it sound:

- **The environment must take the goal back.** The cookie is gone once eaten, and a new one
  needs the button. If `x` stays true, for example the agent stays on the goal tile, a machine
  sent back to its start would pay again on the next step for doing nothing. The goal has to
  become false (`!x`) before it can count again (`x`).
- **Repeating must be the task.** There, collecting the goal again is what the task asks for,
  so it is not farming. Farming is the same behaviour when the task meant "do it once".

We have not tried or tested this. It stays a theory note.

## Code and docs

- `_rearm_violated` in `app/src/compiler/reward_layer.py` rewrites the DFA. The switch is
  `--recurrent-soft-penalty` (the default) or `--no-recurrent-soft-penalty`, and the web
  checkbox "Recurrent soft rules"; every run records it.
- The episode end and the machine reset: `app/src/arm_fm/environments.py` (the Reward Machine
  wrapper's docstring and `reset`).
- Design: the "Recurrent soft rules" section of `docs/COMPILER_REWARD_DESIGN.md`. Decision
  records: `docs/decisions/arm-fm/task-and-rm-identity.md` and
  `docs/decisions/arm-fm/rm-execution.md`.
- Commits: `ddb0c82` (`merge: recurrent soft penalty and the reasoning none fallback`) and
  `0effa25` (`merge: recurrent soft rules wording`).
- Check: `test_a_soft_rule_pays_every_new_break_with_the_recurrent_penalty_and_once_without`
  in `tests/test_reward_layer.py`. Breaking a rule, keeping it, then breaking it again pays
  −0.5, 0, −0.5 with the switch on and −0.5, 0, 0 with it off.

## Sources

- Rodrigo Toro Icarte, Ethan Waldie, Toryn Q. Klassen, Richard Valenzano, Margarita P. Castro,
  Sheila A. McIlraith. "Learning Reward Machines for Partially Observable Reinforcement
  Learning." NeurIPS 2019. Example 3.1 and Figure 2 (cookie domain); the experiments section
  gives the 5,000-step episode.
  <https://proceedings.neurips.cc/paper/2019/hash/532435c44bec236b471a47a88d63513d-Abstract.html>
- Ernst Moritz Hahn, Mateo Perez, Sven Schewe, Fabio Somenzi, Ashutosh Trivedi, Dominik
  Wojtczak. "Omega-Regular Objectives in Model-Free Reinforcement Learning." TACAS 2019.
  <https://arxiv.org/abs/1810.00950>
