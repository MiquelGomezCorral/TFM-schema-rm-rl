# schema-rm-rl

`schema-rm-rl` converts environment Markdown and reviewed natural-language
instructions into a formally compiled Reward Machine. The model can select only one
of IBM `nl2ltl`'s eight DECLARE templates, declared propositions, and one numeric
reward per instruction. IBM constructs the LTLf AST; FL-AT and MONA construct and
compose the automata. The model never writes LTL or Reward Machine topology.

V1 ends after Reward Machine generation. It does not train or evaluate an RL agent.

## Local setup

Use Python 3.13 and keep the three working copies as siblings:

```text
nl2ltl/
Flat/
schema-rm-rl/
```

Install the sibling projects editably, then this package:

```bash
conda create --name TFM_2_env python=3.13 -y
conda activate TFM_2_env

# pip install uv
uv pip install -r requirements.txt
pip install -e .

uv pip install ipykernel
python -m ipykernel install --user --name=TFM_2_env --display-name "Python (TFM_2_env)"
```

The local `nl2ltl` checkout removes its obsolete mandatory OpenAI pin while retaining
`pylogics`. The local FL-AT checkout is packaged only to expose the compiler API used
here.

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

Set the API key and either set a default model or pass `--model`:

```bash
export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-4o-2024-08-06"

python app/main.py generate-rm \
  --environment examples/multitaxi/environment.md \
  --instruction "Eventually deliver passenger 1" \
  --instruction "Eventually deliver passenger 2" \
  --output multitaxi.rm
```

The command displays every instruction, selected DECLARE pattern, grounded
propositions, generated LTLf formula, and proposed reward. It then asks once for
explicit approval. Declining does not call FL-AT and writes nothing. Existing output
files are rejected unless `--overwrite` is supplied.

After approval, MONA compiles each formula and FL-AT composes the DFAs. States are
renamed in breadth-first order from `u0`. Boolean guards are expanded into disjoint
conjunctions such as `d1&!d2`. The output uses only these sections:

```text
REWARD_MACHINE:
STATES: ...
INITIAL_STATE: ...
TRANSITION_FUNCTION:
...
REWARD_FUNCTION:
...
```

Only nonzero rewards are written; omitted rewards mean zero.

## Limitations and licensing

- The generated reference-format labels may be Boolean conjunction guards. The
  reference runtime does not evaluate those guards without an integration change;
  extending that runtime is outside V1.
- Structured Outputs requires a compatible OpenAI model. An unsupported model is an
  API error and is not silently retried or downgraded.
- The upstream FL-AT checkout does not contain a license file. Keep the modified
  checkout local for research use; do not publish or redistribute it without explicit
  permission from its owner.
