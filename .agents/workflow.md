# Workflow

## Setup

Clone the repository with its pinned dependencies and use Python 3.13.

```bash
git clone --recurse-submodules https://github.com/MiquelGomezCorral/TFM-schema-rm-rl.git
cd TFM-schema-rm-rl
```

```bash
uv pip install -r requirements.txt
pip install -e .
```

Build and install MONA separately, then ensure `mona` is on `PATH`.

For dependency development, switch the detached submodule to the fork's default branch
(`main` for `nl2ltl` or `master` for Flat), synchronize the original project through
`upstream`, push to the fork `origin`, and then commit the updated gitlink here.

## Readiness

The minimum non-live readiness check is:

```bash
python app/main.py --help
```

It must display `generate-rm` without contacting OpenAI or invoking MONA.

## Live Validation

Live validation is pending explicit user approval. It requires `mona`, `OPENAI_API_KEY`, and `OPENAI_MODEL` or `--model`. Use the MultiTaxi example with two eventual-delivery instructions and one passenger-ordering instruction, inspect the proposal, and approve it before compilation.

## Commit And Publish

Do not commit or push unless explicitly requested. The public Flat adaptation was
published by explicit user authorization, but upstream still has no declared license;
the license request is tracked at `https://github.com/Jamidd/Flat/issues/1`.
