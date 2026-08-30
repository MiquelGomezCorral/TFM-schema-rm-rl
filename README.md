# schema-rm-rl

`schema-rm-rl` converts environment Markdown and reviewed natural-language
instructions into formally compiled Reward Machines. For each instruction, the model
can select only `Existence`, `ExistenceTwo`, or `Precedence`, declared propositions,
and one of five priority levels. The compiler owns formulas, rewards, automata, and RM
topology; the model never invents numeric rewards, LTL, or transitions.

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

Copy `example.env` to `.env`, add the OpenCode key, and either keep its default model
or pass `--model`:

```bash
LLM_PROVIDER=opencode
OPENCODE_API_KEY="..."
OPENCODE_BASE_URL=https://opencode.ai/zen/v1
OPENCODE_MODEL=big-pickle
```
and launch
```bash

python app/main.py generate-rm \
  --environment examples/multitaxi/environment.md \
  --instruction "Eventually deliver passenger 1 and eventually deliver passenger 2" \
  --instruction "Deliver passenger 1 before passenger 2" \
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

After approval, every instruction is compiled independently through MONA. A single
instruction preserves the exact `--output` path. Multiple instructions number the
stem, so the example writes `multitaxi-1.rm`, `multitaxi-2.rm`, and
`multitaxi-3.rm`. All target paths are checked before compilation, and existing files
are rejected unless `--overwrite` is supplied.

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
- The upstream FL-AT checkout does not contain a license file. Keep the modified
  checkout local for research use; do not publish or redistribute it without explicit
  permission from its owner.
