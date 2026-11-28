# The web page

Back to the [main page](../README.md).

A local page that runs the same pipeline as `generate-rm`, with every step on screen.

## Open it

From the root of the repository, with the Conda environment active:

```bash
PYTHONPATH=app python app/app.py
```

Then open <http://127.0.0.1:8050>. To use another port, set `PORT` before the command, for
example `PORT=8060 PYTHONPATH=app python app/app.py`.

It uses the provider set in `.env` ([engines](../app/src/engines/README.md)) and needs MONA,
like the command line. The page never asks for or shows a key.

## Use it

1. **Give the environment description.** Upload the Markdown file or paste it.
2. **Write one or more tasks.**
3. **Give one output name.** With several tasks the files are numbered, as in the command line.
4. **Run.** The critic reviews each task on its own.

Each finished RM is shown with its file path, its text and its graph.

**Shortcut.** Uploading a tasks file such as
`experiments/dev/arm-fm/minigrid-doorkey/tasks.json` fills the description and all its tasks.

## Follow a run

- **Steps tab.** The current task, the attempt, each stage and how long it took. Blue is
  running, green done, grey waiting or skipped, red failed.
- **Log tab.** The full log of the run.
- **Stop generation.** Stops after the current request returns. The current task is dropped
  and no file is written.

## Limits

One run at a time, nothing is saved between runs, and there is no login. It is meant for one
person on their own machine.
