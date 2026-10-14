# Template tasks

A held-out set for checking which clauses the compiler's LLM picks for a task: the
template, its propositions, and `hard` or `soft`. It has 37 tasks over 8 environments,
and every IBM template appears both hard and soft. `tasks.json` holds the tasks and the
clauses each one should produce.

## Rules for this set

- **The wording stays apart from the prompt guide.** No task uses a phrase from the
  wording table, the worked examples, or the soft-cue list in
  `app/src/prompts/compiler-rm/declare-templates.md` ("after", "never", "at some point",
  "preferably", and so on). So the set tests whether the guide's rules carry over to new
  wording, not whether the model spots the guide's own phrases. Don't copy these
  sentences into a prompt, and when the guide gains a phrase, reword any task that uses it.
- **Expected clauses follow the guide's rules.** A required event ordered by "until" or
  "before" gets `Existence` plus `Precedence`; an order rule on an event the task doesn't
  require gets `Precedence` alone. A `Response` consequent gets no `Existence` of its own.
  A task with no hard goal is rule-only: the compiler warns that its RM has no final state.

## Fields

- `environment`: the environment Markdown, relative to the repository root.
- `case`: what the task tests.
- `task`: the sentence given to `generate-rm`.
- `expect`: the clauses, each `[template, [propositions], priority]`, in any order.
- `also_ok`: other clause sets that also count as a match. They either mean the same thing
  (an extra `Existence(a)` next to `Existence(b)` and `Precedence(a, b)`, or
  `NotCoExistence` with its arguments swapped), or the environment requires the extra
  clause anyway (the door has to open before the object behind it can be picked up).

## Running it

From the repository root, inside `RM_RL_env`, one task at a time:

```bash
python app/main.py generate-rm \
  --environment examples/arm-fm/minigrid-doorkey/environment.md \
  --task "Get hold of the yellow key." \
  --steps-report steps.md
```

The steps report lists the clauses the run accepted. Run each task 3 times: it passes
when all 3 runs match `expect` or an `also_ok` set, it is unclear when only some do, and
it fails when none do.
