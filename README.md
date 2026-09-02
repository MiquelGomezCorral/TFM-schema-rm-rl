# schema-rm-rl

`schema-rm-rl` converts environment Markdown and reviewed natural-language
instructions into formally compiled Reward Machines. For each instruction, the model
can select only `Existence`, `ExistenceTwo`, or `Precedence`, declared propositions,
and one of five priority levels. The compiler owns formulas, rewards, automata, and RM
topology; the model never invents numeric rewards, LTL, or transitions.

V1 ends after Reward Machine generation. It does not train or evaluate an RL agent.

## Quick start

Install Git and Conda, then clone the repository with its pinned dependencies:

```bash
git clone --recurse-submodules \
  https://github.com/MiquelGomezCorral/TFM-schema-rm-rl.git
cd TFM-schema-rm-rl

# For an existing clone:
git submodule update --init --recursive
```

The parent repository pins exact fork commits under `dependencies/nl2ltl` and
`dependencies/Flat`. Create the Python 3.13 environment and install the complete
project:

```bash
conda create --name TFM_2_env python=3.13 -y
conda activate TFM_2_env

python -m pip install uv
uv pip install -r requirements.txt
uv pip install -e .

cp example.env .env
```

Open `.env`, set `OPENCODE_API_KEY`, and keep or change the configured model. Install
MONA as described below, then verify the local installation without calling an LLM:

```bash
mona -v
python app/main.py --help
```

Jupyter support is optional:

```bash
uv pip install ipykernel
python -m ipykernel install --user --name=TFM_2_env --display-name "Python (TFM_2_env)"
```

The pinned `nl2ltl` fork removes its obsolete mandatory OpenAI pin while retaining
`pylogics`. The pinned FL-AT fork exposes the compiler API used here.

### Editing a dependency fork

Submodules are normally checked out at detached commits. Before editing one, switch to
the fork's default branch and add the original repository as `upstream`:

```bash
cd dependencies/nl2ltl
git switch main
git pull --ff-only origin main
git remote add upstream https://github.com/IBM/nl2ltl.git

cd ../Flat
git switch master
git pull --ff-only origin master
git remote add upstream https://github.com/Jamidd/Flat.git
```

In both submodules, `origin` is the maintained fork and `upstream` is the original
project. Commit and push dependency changes on `main` or `master`, then return to the
parent repository and commit the updated submodule gitlink.

## Install MONA from source

Download MONA from <https://www.brics.dk/mona/download.html>, unpack the source, and
follow its source build:

```bash
./configure --prefix="$HOME/.local"
make
make install
export PATH="$HOME/.local/bin:$PATH"
mona -v
```

The `mona` executable must be on `PATH`. Compilation fails with a clear error when it
is unavailable. System build tools and the dependencies listed by MONA may need to be
installed first.

## Environment Markdown

Normal Markdown prose is allowed, but exactly one strict proposition section is
required. Every nonblank line in it must use this shape:

```markdown
## Propositions
- `p1`: Passenger 1 entered the taxi.
- `d1`: Passenger 1 was delivered.
```

Identifiers must match `^[a-z_][a-z0-9_]*$`, be unique, and cannot be `true` or
`false`. Validation errors include the offending line. See
`examples/multitaxi/environment.md` for the transition-based MultiTaxi propositions.

## Generate a Reward Machine

Configure OpenCode in `.env`. The generated example already contains these values
except for the API key:

```bash
LLM_PROVIDER=opencode
OPENCODE_API_KEY="..."
OPENCODE_BASE_URL=https://opencode.ai/zen/v1
OPENCODE_MODEL=nemotron-3.5-lightning-free
```

Run the compiler from the repository root:

```bash
python app/main.py generate-rm \
  --environment examples/multitaxi/environment.md \
  --instruction "Eventually deliver passenger 1" \
  --instruction "Eventually deliver passenger 2" \
  --instruction "Deliver passenger 1 before passenger 2" \
  --priority none \
  --priority none \
  --priority hard \
  --output multitaxi.rm \
  --overwrite
```

`--priority` accepts `infer`, `none`, `soft`, `medium`, `strong`, or `hard`. If any
priority overrides are supplied, there must be exactly one per instruction; `infer`
delegates only that position to the model. Unary templates always use `none`.
Unsoftened categorical "A before B" instructions infer `hard`.

The command displays every instruction, selected pattern, grounded propositions,
priority, generated LTLf formula, and effective reward behavior. It asks once for
approval of all proposals. Declining does not call MONA and writes nothing.

After approval, every instruction is compiled independently through MONA. `--output`
is a file name, not a path; files are always written under `Configuration.OUTPUT_PATH`.
Multiple instructions number the stem, so the example writes `multitaxi-1.rm`,
`multitaxi-2.rm`, and `multitaxi-3.rm` under that directory. All target paths are
checked before compilation, and existing files are rejected unless `--overwrite` is
supplied.

The output uses the current TFM runtime's numeric semicolon format. For example, a
hard `d1`-before-`d2` machine has one success final state and a declared rejecting
sink:

```text
s: 0, 1, 2
i: 0
f: 3
r: 0
0; 1; !d1,d2; 0
0; 2; d1,!d2; 0
0; 1; d1,d2; 0
2; 3; !d1,d2; 1.00
2; 3; d1,d2; 1.00
```

Missing transitions are zero-reward self-loops. Only state-changing transitions and
necessary nonzero-reward transitions are emitted, using propositions from that
instruction only. The rejecting sink has no explicit outgoing rows, so it remains
there through the same implicit self-loop rule.

Rewards occur once, only when completion enters the final state. `Existence` rewards
the first occurrence and `ExistenceTwo` the second. Non-hard precedence requires both
events but allows either order; preferred/reverse completion rewards are `1.00/1.00`,
`1.25/0.75`, `1.50/0.50`, and `1.75/0.25` for `none`, `soft`, `medium`, and `strong`.
Simultaneous completion receives `1.00`. Hard precedence gives `1.00` only to the
strict preferred order; reverse and simultaneous order enter the rejecting sink.

## Limitations and licensing

- `Absence`, `RespondedExistence`, `Response`, `ChainResponse`, and
  `NotCoExistence` do not have executable V1 reward semantics and are rejected rather
  than assigned ambiguous rewards.
- Structured output requires a compatible provider model. An unsupported model is an
  API error and is not silently retried or downgraded.
- The upstream FL-AT repository does not declare a license. Its public adaptation fork
  is maintained at the project owner's accepted publication risk while the
  [license request](https://github.com/Jamidd/Flat/issues/1) remains unresolved.

## How the pipeline uses the formal tools

```mermaid
flowchart TD
    A["Input<br/>environment.md + instruction"]
    B["Validate input<br/>fix the allowed proposition vocabulary"]
    C["LLM<br/>only natural-language interpretation step"]
    D{"Human approval"}
    X["Stop<br/>write nothing"]
    E["IBM nl2ltl templates + our priority rules<br/>build the formal formula"]
    F["FL-AT + MONA<br/>compile the formula into an automaton"]
    G["Our RM compiler<br/>minimize + assign one-time rewards"]
    H["One executable .rm file"]

    A -->|"description + proposition declarations + instruction"| B
    B -->|"validated description + fixed proposition IDs"| C
    C -->|"pattern + proposition IDs + priority"| D
    D -- Reject --> X
    D -->|"Approved interpretation"| E
    E -->|"LTLf formula"| F
    F -->|"DFA"| G
    G -->|"compact Reward Machine"| H
```

Input validation is not another interpretation step. It only checks that the Markdown
contains one valid proposition section, that proposition IDs are unique and safe for
the formal tools, and that later stages can use only that fixed vocabulary. This stops
the LLM from inventing events that the environment cannot emit.

There is only one NLP step in the current pipeline. The OpenCode or OpenAI model reads
the instruction and chooses a constrained pattern, proposition IDs, and priority. IBM
`nl2ltl` is not running a second language model here: we use its deterministic DECLARE
template classes to turn the approved choice into a `pylogics` LTLf formula. The LLM
does not generate LTLf, automaton states, transitions, numeric rewards, or output files.
Everything after approval is deterministic code and formal compilation.

The main ownership boundary is: **FL-AT and MONA compile the approved LTLf formula
into the formal DFA; `schema-rm-rl` converts that DFA into the executable Reward
Machine.** The current pipeline calls FL-AT's `compile_dfa()` entry point, not its
original `compile_reward_machine()` path.

| Tool | What this project uses | What this project does not use, and why |
|---|---|---|
| IBM `nl2ltl` | The `Existence`, `ExistenceTwo`, and `Precedence` DECLARE templates, their argument checks, and `pylogics` formula objects. `Existence` and `ExistenceTwo` use the template's `to_ltlf()` method. | Its GPT and Rasa engines, grounding, filters, confidence ranking, and generic `translate()` wrapper are unnecessary because this project has a schema-constrained provider engine and a human review step. PPLTL is unused because FL-AT receives LTLf. Other DECLARE templates are rejected until their executable reward and violation semantics are defined. |
| FL-AT | The LTLf lexer, parser, translation to MONA logic, MONA process invocation, and DFA output parser exposed through `flat_tool.compile_dfa()`. | PDDL3, PLTL, and regular-expression inputs are outside the current LTLf pipeline. FL-AT's old CLI, automata composition, reward assignment, and RM serializer are unused because this project creates one RM per instruction and owns its one-time reward and compact runtime semantics. |
| `schema-rm-rl` | Environment parsing, LLM request validation, priority semantics, human approval, LTLf serialization, DFA normalization and minimization, reward assignment, and RM serialization. | It does not invent formal automaton topology; MONA remains responsible for compiling the approved formula. |

For precedence, the IBM template supplies the constrained pattern and argument order,
but this project builds the final formula itself. Non-hard priorities require both
events while allowing either order. Hard priority requires strict preferred ordering
and rejects reverse or simultaneous completion.

## MONA's role

MONA is a formal logic compiler and decision procedure, not an AI model. FL-AT
translates an approved LTLf formula into MONA's logic, and MONA constructs the
deterministic finite automaton that recognizes traces satisfying that formula.

```mermaid
flowchart LR
    A["LTLf formula"]
    B["FL-AT<br/>translate for MONA"]
    C["MONA<br/>construct the DFA"]
    D["Our compiler<br/>construct the RM"]
    E["Executable .rm file"]

    A -->|"LTLf text"| B
    B -->|"MONA logic"| C
    C -->|"DFA"| D
    D -->|"states + sparse transitions + rewards"| E
```

After MONA runs, the modified FL-AT adapter parses its DFA text and removes a proven
event-ignoring preamble when present. It then passes the parsed DFA to our RM compiler.

The local MONA source contains several subsystems:

| MONA component | Purpose in MONA | Use in this project |
|---|---|---|
| `Front/` | Parses and processes logical formulas. | Used indirectly through the `mona` executable. |
| `BDD/` | Represents Boolean conditions efficiently. | Used internally by MONA. |
| `DFA/` | Builds and manipulates automata over finite strings. | This is the automaton output the pipeline needs. |
| `GTA/` | Builds tree automata. | Not used because the pipeline handles finite event traces, not trees. |
| `Lib/` | Provides supporting automata operations and output utilities. | Used only as internal support for the executable. |

MONA does not read natural language, call an LLM, select propositions, assign rewards,
write the final RM format, or train an RL agent. Its responsibility is narrower: given
the formal meaning of an approved instruction, produce the corresponding deterministic
automaton. FL-AT invokes it in `dependencies/Flat/LTLf/Translator.py`, and this project
then converts the returned DFA into the compact Reward Machine consumed by the TFM
runtime.
