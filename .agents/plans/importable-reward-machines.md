# Importable Reward Machines, Responsive Graph, and Reliable RM Critic

## Summary

Add one simple `.rm` import path to the Compiled Reward Machine panel, correct the graph canvas width while retaining gentle physics, and prevent the Antigravity RM critic from attempting tools by giving it complete closed-world instructions.

## Implementation Changes

- Add `parse_reward_machine(text)` beside the existing serializer in `app/src/compiler/reward_machine.py`.
  - Accept only the repository’s existing `s:`, `i:`, `f:`, `r:` and semicolon-separated transition format.
  - Validate UTF-8 content, headers, state references, guards, finite rewards, and malformed or duplicate entries.
  - Return the existing `RewardMachineStructure`; raise a concise `ValueError` for invalid files.
  - Derive rejecting states from states that cannot reach a final state.

- Extend the Compiled Reward Machine panel in `app/src/web/components.py` and its callbacks in `app/src/web/application.py`.
  - Add an Environment-style single-file upload accepting `.rm`.
  - Store one validated import in an in-memory `dcc.Store`; a later valid upload replaces it.
  - Add `Imported: <filename>` to the existing output selector and select it immediately.
  - Preserve generated task entries and the imported entry during polling and generation.
  - Render imported text and graph through the same result components as generated machines.
  - On corrupt, unsupported, or malformed input, show a red error and preserve the current selection and graph.

- Set the Cytoscape component’s explicit inline size to `width: 100%` and `height: 100%`, overriding its 600px defaults. Keep the current low-intensity continuous Cola physics, dragging, panning, and zooming.

- Expand `app/src/prompts/reward-machine-reviewer.system.md` with the exact serialized RM semantics and an explicit closed-world instruction: review only the supplied environment, task, and candidate; never inspect files, invoke tools, or delegate. Insufficient or malformed input must produce structured rejection feedback.
  - Keep the provider’s strict rejection of actual tool or subagent execution.
  - Do not add a fallback model or silently bypass the critic.

## Validation

- Do not add or modify files under `tests/`.
- Run a temporary, non-persisted parser check covering one valid RM and representative malformed inputs.
- Instantiate the Dash application and verify the new upload/store/callback wiring and full-size Cytoscape style.
- Run the existing test suite unchanged and run `git diff --check`.
- Browser acceptance:
  - A valid `.rm` appears in the selector and renders its source and complete graph.
  - A bad file displays an error without replacing the current result.
  - Generated and imported selector entries coexist.
  - The graph uses the entire panel and gently readjusts after dragging.
- With separate approval because it consumes provider quota, run one Antigravity generation with both critics enabled and confirm the RM critic returns structured feedback without invoking a tool.

## Assumptions and Boundaries

- Support only the project’s current serialized `.rm` format and one imported slot; no history, persistence, conversion, download, or critique of uploaded machines.
- No dependencies, migrations, decision-record changes, or agent-memory changes are needed.
- Preserve unrelated worktree edits and deleted output files.
- Decision records: no change—the implementation follows the existing RM format ownership and strict no-tool provider boundary.

Plan ready for a separate `$review-plan`; a subsequent `$code` can implement the approved version.
