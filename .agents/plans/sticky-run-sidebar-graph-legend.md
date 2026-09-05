# Sticky Run Sidebar and Graph Legend

## Goal

Reorganize the existing Dash UI around a sticky run-control sidebar, make instruction controls safer and more consistent, and add a compact graph legend without changing callbacks, generation behavior, or graph interaction.

## Files touched

- `app/src/web/components.py`
- `app/assets/app.css`

## Requirements

- Preserve every existing component ID, callback property/state, graph interaction setting, and run-state transition.
- Keep the full-width application header above the workspace.
- Keep logical DOM order as inputs, run controls, then outputs.
- Above 1200px, use a `19rem` sticky left sidebar spanning the input and output rows. Place Environment and Instructions side by side in the main area, then place Compiled Reward Machine and State graph side by side at equal width.
- From 901px through 1200px, retain the sticky sidebar while stacking both main-area pairs.
- At 900px and below, remove sticky positioning and stack inputs, run controls, and outputs in logical DOM order.
- Keep the graph legend collapsed initially.
- Add no dependency, callback, client-side state, or shared Python/CSS color abstraction.

## Implementation

1. Change `output_controls()` to return an `html.Aside` with the `run-sidebar` class while retaining its current children and existing styling classes.
2. In `create_layout()`, add a `workspace` wrapper containing, in order, the input region, sidebar, and output region. Use CSS grid areas to display the sidebar at left across both desktop rows without changing logical DOM order.
3. Replace the instruction header grid with a non-wrapping flex row. Give `Instruction N` a dedicated `instruction-title` class, slightly larger normal foreground text, and stronger weight. Keep the Priority label screen-reader-only, place its dropdown immediately after the title, and push the remove action to the far right.
4. Keep the remove action as an accessible `×`. Make it a `2.75rem` square, and make the priority dropdown and trigger `2.75rem` high. Use an `8rem` dropdown width normally and `7rem` below 560px.
5. In `graph_panel()`, replace the standalone explanation with a native collapsed `html.Details` legend in the graph toolbar. Include semantic rows for default, initial, accepting, and rejecting states plus a transition. Mark decorative swatches `aria-hidden` and use the existing Cytoscape colors. Include the existing explanation that only explicit transitions are shown and omitted transitions are zero-reward self-loops.
6. Style the disclosure for the dark theme with visible hover and focus states using the existing motion and focus conventions. Let expanded legend content increase toolbar height rather than overlay the graph.
7. Change approval controls to a two-column grid in the narrow sidebar: Approve on the left, Decline on the right, and feedback on its own full-width row.
8. Replace the obsolete three-column input/generate responsive rules with workspace breakpoints. Preserve the existing mobile header behavior, graph sizing, dark dropdown styling, reduced-motion handling, and graph canvas behavior.

## Interfaces

- No public Python, compiler, output-format, or callback contract changes.
- No changes to `application.py`, `visualization.py`, compiler code, or generation orchestration.

## Readiness check

```bash
PYTHONPATH=app .venv/bin/python -c "from src.web import create_app; app = create_app(); assert app.layout is not None; assert len(app.callback_map) == 6"
```

Inspect the final diff and run `git diff --check`. Do not run the live generation flow without approval.

## Live validation

- **Flow:** Start the Dash UI, resize it across the three breakpoints, add and remove multiline instructions, open both dropdowns, expand the graph legend, run a generation, approve or decline the batch, and drag graph nodes while testing pan and zoom.
- **Expected:** The sidebar and paired content follow the specified responsive layout; instruction controls stay aligned and safely separated; selectors retain the dark theme; approval actions are separated; the legend accurately explains graph encoding; all run states and graph interactions behave as before.
- **Can run:** Codex can start the server, but the complete flow requires browser interaction and configured LLM/MONA execution, so it needs explicit user approval.

## Main-agent memory updates

None. This is a presentation-only change that preserves documented architecture and behavior.

## Out of scope

- Backend or pipeline refactoring.
- New automated tests, dependencies, JavaScript assets, persistence, callbacks, or graph semantics.
- Continuous physics after the existing Cola layout settles.
