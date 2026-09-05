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
PYTHONPATH=app .venv/bin/python -m unittest discover -s tests -v
```

The suite checks bounded generator/critic orchestration, six-stage progress and persistent
diagnostics, prompt contracts, atomic output behavior, and web task navigation/critic
controls. It must not contact an LLM, invoke MONA, or start the web server.

Run the local web UI from the repository root with:

```bash
python app/app.py
```

## Live Validation

Live validation is pending explicit user approval. It requires `mona`, `OPENAI_API_KEY`,
and `OPENAI_MODEL` or `--model`. Use the MultiTaxi environment with three tasks, both
critics enabled, and a fresh output name. Verify that no approval prompt appears, the
Steps view accurately follows and browses sequential tasks, logs carry `[total … | step
…]` entries and readable stage artifacts, a local diagnostic file is retained, both
critics accept within three attempts, and three compatible Reward Machines are written.

## Commit And Publish

Do not commit or push unless explicitly requested. The public Flat adaptation was
published by explicit user authorization, but upstream still has no declared license;
the license request is tracked at `https://github.com/Jamidd/Flat/issues/1`.
