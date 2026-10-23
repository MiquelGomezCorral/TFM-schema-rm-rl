# Environment files: facts and implementation

Appendix note on how each environment is described. Every environment has two Markdown files
(`docs/ENVIRONMENT_AUTHORING.md`, `docs/decisions/arm-fm/catalogue-and-evidence.md`).

**The rule.** `environment.md` describes the environment at the top level only: what each
proposition means and when the environment emits it. `environment-code.md` holds all
implementation and adds to the facts file without copying it.

**The per-line test.** For every line: would someone framing propositions and a reward machine need
it? If the line only helps implement or verify, it belongs in `environment-code.md`.

## The environment file (`environment.md`)

**Who reads it.** The clause generator and the critic of the compiler read this file and nothing
else. The steps that write code read it together with the code file (see below).

**Why it stays top level.** A component that only chooses propositions and builds a reward machine
needs the meaning of each proposition and the moment the environment emits it. Source links, gym
ids, package versions, code expressions, file paths, citations, run counts and build steps add
context it cannot use. What the file leaves out, the generator and the critic have to guess, and a
guess can become a clause the environment already guarantees, which yields a reward-machine state
the environment cannot reach. The file therefore carries checked facts and says plainly what is
not known. It stays under 120 lines because it is part of every generator and critic prompt.

The file has a title and exactly eight sections, in this order.

| Section | Purpose |
| --- | --- |
| Environment | Layout, objects, what changes between episodes, the actions the agent has. |
| Objective and episode boundary | What ends an episode, when reward is given, the step limit. |
| Proposition semantics | For each proposition, its kind (event, condition or latch) and its truth condition in plain words, and the reading chosen where the description leaves one open. |
| Constraints | Physical facts the generator and the critic read, written as orders, exclusions and one-way changes. |
| What the agent can and cannot do | Actions with their exact conditions, what is blocked or irreversible, what a reader might doubt, and what is not known. |
| Example trace | One real successful episode: per step, the action and the propositions that change. |
| Propositions | One line per proposition, `` - `id`: description ``. This is the only section the parser reads for the vocabulary. |
| Example tasks | Sample task wordings. |

## What the code file adds (`environment-code.md`)

**Who reads it.** The steps that write code: the ARM-FM baseline generator (which writes the
Reward Machine and the labeling code) and every labeling generator, including compiler-mode
labeling. They read both files as one text: the facts file, a blank line, then the code file,
parsed as one document. The parser therefore finds one propositions section (in the facts file)
and at most one labeling API section (in the code file). The clause generator and the critic of the
compiler do not read the code file, so none of its text reaches their prompts.

**What it holds.** All implementation, and a reference back to the facts file by section and
proposition id instead of a copy of any fact. Evidence uses two tags: `[code: file:function]` for
the environment's source and `[run: script]` for a scripted run or check on the real environment.

| Section | Purpose |
| --- | --- |
| Title and one line | Names the file as an addition to `environment.md` and says to read both. |
| Source and runtime | Official source, version or commit, gym id, pinned package versions, how to build the environment, and what the evidence tags point to. |
| Truth conditions in code | Per proposition id, the expression over the runtime state that the labeling code computes, including how an event or a latch uses the previous valuation. |
| Evidence | Per fact of the facts file, the `[code]` or `[run]` entry that supports it. Runs give the script, the seeds and the counts, including how many episodes reached the premise. |
| Labeling API | The attributes and calls the labeling code may read, with types and meaning. It is the only runtime surface the labeling generators receive. Absent when the environment has no labeling surface. |

## Worked example: MiniGrid DoorKey

The folder holds the two final files of one environment.

- `minigrid-doorkey.environment.md`: the facts file.
- `minigrid-doorkey.environment-code.md`: the code file.

DoorKey has four propositions: `has_key`, `door_open`, `at_goal` and `key_lost`. For each, the facts
file states in words when it is true, and the code file gives the expression the labeling code
evaluates and the evidence for the claim.

## Rerun

After the two DoorKey files are in this folder, from the repository root inside `RM_RL_env`:

```bash
PYTHONPATH=app python - <<'PY'
from pathlib import Path
from src.models import EnvironmentDescription

folder = Path("docs/paper/environment-files")
facts = (folder / "minigrid-doorkey.environment.md").read_text(encoding="utf-8")
code = (folder / "minigrid-doorkey.environment-code.md").read_text(encoding="utf-8")
environment = EnvironmentDescription.from_markdown(f"{facts}\n\n{code}", source="environment.md")
print(environment.proposition_ids)
print(environment.require_labeling_api())
PY
```

It prints the four proposition ids and the labeling API text, taken from the joined text. In the
repository the same join is `EnvironmentDescription.from_file(path, code=True)`, which appends the
sibling `environment-code.md` of `path`; the script joins the two renamed copies by hand because
the folder cannot hold two files with those names.

## Code

`EnvironmentDescription.from_file(path, code=True)` in `app/src/models/environment.py` joins and
parses the two files. Its callers are `generate_larm` in `app/scripts/generate_larm.py` (the
baseline generator) and the labeling stage of `_Pipeline` in `app/scripts/generate_rm.py`;
`setup_environment_and_engines` in `app/src/utils/generation.py` loads the facts file alone for the
clause generator and the critic. Every ARM-FM bundle manifest stores the joined text, because the
judge reviews generated code. The web app takes the code file as a second input
(`app/src/web/runner.py`). Not committed when this note was written.
