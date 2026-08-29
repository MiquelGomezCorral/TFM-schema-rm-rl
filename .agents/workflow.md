# Workflow

## Setup

Keep `nl2ltl`, `Flat`, and `schema-rm-rl` as sibling working copies. Use Python 3.13.

```bash
uv pip install -r requirements.txt
pip install -e .
```

Build and install MONA separately, then ensure `mona` is on `PATH`.

## Readiness

The minimum non-live readiness check is:

```bash
python app/main.py --help
```

It must display `generate-rm` without contacting OpenAI or invoking MONA.

## Live Validation

Live validation is pending explicit user approval. It requires `mona`, `OPENAI_API_KEY`, and `OPENAI_MODEL` or `--model`. Use the MultiTaxi example with two eventual-delivery instructions and one passenger-ordering instruction, inspect the proposal, and approve it before compilation.

## Commit And Publish

Do not commit, push, publish, or redistribute the modified sibling repositories unless explicitly requested. FL-AT has no declared upstream license.
