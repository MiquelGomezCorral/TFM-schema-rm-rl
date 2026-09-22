# Compare the ARM-FM baseline against the compiler on MiniGrid DoorKey

## Goal

Generate the four `examples/arm-fm/minigrid-doorkey/tasks.json` tasks with both RM generators,
twice each and independently, render every Reward Machine to SVG, and report what each pipeline
produces versus the other.

## Context

- **Baseline (ARM-FM):** direct paper-format RM generation (`rm_generator`), refined by the packaged
  ARM-FM `rm_critic` for at most three attempts. No clause restrictions.
- **Compiler:** proposal -> task critic -> DECLARE/LTLf -> FL-AT/MONA DFA -> RM -> RM critic, bounded
  to `Existence`, `ExistenceTwo`, and `Precedence`.
- **Provider/model:** `.env` as-is (`opencode`); no provider or model override.
- **Comparison is semantic.** The baseline serializes `u0...un` paper RMs; the compiler serializes the
  numeric `s/i/f/r` format. Text is never compared byte-for-byte
  (`docs/decisions/arm-fm/reproduction-boundary.md`).

## Requirements

- 4 tasks x 2 runs x 2 pipelines = 16 Reward Machines, each with an SVG.
- **Compiler:** first try both critics. If one task exhausts its three attempts, re-run **that task
  only** with `task_critic=False, rm_critic=False` and tag it `critics: off (fallback)`.
- **ARM-FM:** use its own `rm_critic` loop. If it never accepts, keep the last parseable candidate and
  tag it `rm_critic: rejected (fallback)`.
- A deterministic refusal (unsupported template / undeclared proposition) is reported as `refused`
  and is **not** retried with critics off, because critics are not the cause.
- Never overwrite a previous run's artifacts. No credentials in logs or artifacts.
- Runs are independent: no shared history between run 1 and run 2.

## User decisions (2026-09-22)

- Running with **no** critic is now a supported option. `Configuration` prints a warning instead of
  raising. This supersedes the previous "at least one critic remains enabled" invariant.
- `--svg` on the RM generation CLI writes one SVG per accepted RM under `outputs/svgs/` by default.
- All generated experiment artifacts are kept under `docs/artifacts/`.

## Files touched

- `app/src/config/config.py` — warn instead of raise when both critics are off; add `svg` / `svg_dir`.
- `app/src/arm_fm/generation.py` — extract the RM-only critic loop into a public function.
- `app/scripts/render_rm.py` — expose the structure and SVG renderers.
- `app/scripts/generate_rm.py` — write SVGs after a successful run when requested.
- `app/main.py` — add `--svg` and `--svg-dir` to `generate-rm`.
- `outputs/svgs/.gitkeep` — keep the default SVG directory in git.
- `notebooks/compare_pipelines.ipynb` — the experiment driver.
- `README.md`, `.agents/architecture.md`, `docs/decisions/arm-fm/task-and-rm-identity.md`,
  `docs/decisions/arm-fm/reproduction-boundary.md` — record the no-critic decision.

## Steps

### 1. Allow a run with no critic

`Configuration.__post_init__` currently raises
`ValueError("At least one critic must be enabled")` when both critics are disabled. Replace it with
`print_warn(...)` (from `maikol_utils.print_utils`) and no other behavior change. Update the two
decision records, `.agents/architecture.md` ("Either critic may be disabled, but at least one remains
enabled"), and the README sentence about the critics. `docs/decisions/index.md` needs no new link.

### 2. Add `--svg` to the RM generation CLI

- `Configuration` gains `svg: bool = False` and `svg_dir: Path | None = None`; `__post_init__`
  resolves `svg_dir` to `OUTPUT_PATH / "svgs"` when it is `None`.
- `app/scripts/generate_rm.py` writes `<output stem>.svg` into `CONFIG.svg_dir` for every accepted
  result, but only when `write_outputs` and `CONFIG.svg` are set. Import the renderer **inside** the
  writer function so the ordinary CLI path does not pull the Dash stack through `src.web`.
- `app/main.py` adds `--svg` (store_true) and `--svg-dir` (Path, default `None`) to `generate-rm`.
- Create `outputs/svgs/.gitkeep`.

### 3. Expose the renderers from `render_rm.py`

- Rename `_paper_to_structure` to a public `paper_to_structure(machine) -> RewardMachineStructure`.
- Add `render_structure_svg(structure) -> str`; make `render_reward_machine(text)` call it.

### 4. Extract the ARM-FM RM-only critic loop

Add `generate_reward_machine(task, environment, engine, *, api_description=..., human_feedback=None,
max_attempts=MAX_ATTEMPTS) -> tuple[PaperRewardMachine | None, str, list[StageAttempt]]` to
`app/src/arm_fm/generation.py`, holding the existing `rm_generator` + `rm_critic` loop. It returns the
last parseable machine and its text even when the critic never accepted, so a caller can fall back.
`generate_baseline_bundle` calls it and keeps its current acceptance check, failure persistence, and
labeling/description stages. No behavior change for existing callers.

### 5. Build the experiment notebook

`notebooks/compare_pipelines.ipynb`, executed from the repository root:

1. Imports: `dotenv`, `Configuration`, `get_engine`, `EnvironmentDescription`,
   `generate_rm` / `GenerationHooks` / `ProgressEvent`, `generate_reward_machine`,
   `serialize_paper_reward_machine`, `paper_to_structure`, `render_structure_svg`.
2. One `CONFIG = Configuration()` plus an `EXPERIMENT` settings block: tasks file, environment file,
   runs, pipelines, artifact directory, critics on/off, `max_attempts`.
3. A small loop over `run in (1, 2)`, `pipeline in ("arm-fm", "compiler")`, `task in tasks`:
   - generate the RM,
   - write `<task>.rm` and `<task>.svg` under `docs/artifacts/arm-fm-vs-compiler/run-N/<pipeline>/`,
   - record status, attempts, per-attempt stage events, fallback usage, and reason.
4. Write `run-log.json` beside the artifacts.

Collect critic verdicts and failure reasons from `GenerationHooks.event` (`ProgressEvent.detail`);
do not scrape console text.

### 6. Artifact layout

```text
docs/artifacts/arm-fm-vs-compiler/
  run-1/
    arm-fm/   task-1.rm task-1.svg ... task-4.rm task-4.svg
    compiler/ task-1.rm task-1.svg ... task-4.rm task-4.svg
    run-log.json
  run-2/  (same shape)
```

### 7. Reports (hand-written, not scripted)

- `ARM-FM-vs-COMPILER-graphs.md` — SVG tables, rows = run 1 / run 2, columns = ARM-FM / compiler,
  one section per task, mirroring `AFTER-vs-ONLY-AFTER-graphs.md`.
- `ARM-FM-vs-COMPILER.md` — the text tables and analysis, mirroring `AFTER-vs-ONLY-AFTER.md`,
  including per-run status, fallback flags, refusals, and a signal-frequency tabulation.

## Verification

- `python -m unittest tests.test_prompts tests.test_arm_fm tests.test_generation
  tests.test_pipeline_orchestration` passes.
- `python app/main.py generate-rm --help` shows `--svg` and `--svg-dir`.
- A small validation run (`--svg`, one task, `--overwrite`) writes both `outputs/<stem>.rm` and
  `outputs/svgs/<stem>.svg`; the SVG parses as XML and contains arrow markers.
- `Configuration(task_critic=False, rm_critic=False)` warns and does not raise.
- `generate_baseline_bundle` still passes its existing tests after the loop extraction.
- The notebook completes two runs and leaves 16 `.rm` files, 16 `.svg` files, and two `run-log.json`
  files under `docs/artifacts/arm-fm-vs-compiler/`.
- Both report files resolve every referenced SVG path.

## Out of scope

- Moving `svg.py` out of `src.web` so the CLI does not import Dash. Handled here with a lazy import.
- Labeling functions, descriptions, embeddings, training, and evaluation.
- Any change to the published DoorKey evidence under `examples/arm-fm/minigrid-doorkey/`.
