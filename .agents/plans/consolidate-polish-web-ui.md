# Consolidate and Polish the Web UI

## Summary

Restructure the existing Dash layout without changing the generation workflow or backend. Merge generation/status controls, place Results and Graph beside each other, make instruction rows resilient to multiline text, fully theme dropdowns for Dash 4, standardize motion, and restore graph interaction.

## Implementation Changes

- In `app/src/web/components.py`, combine Generate and Run status into one desktop card containing filename, start button, status, log, and approval controls. Preserve all existing component IDs and callbacks.
- Make Results and State graph direct, equal-width children of the output row; stack them below the desktop breakpoint and preserve equal panel heights.
- Redesign each instruction as:
  - Header row: `Instruction N` on the left, compact non-searchable priority dropdown and square `×` remove action on the right.
  - Full-width, consistently sized textarea below.
  - Keep the first remove action visibly disabled and retain its accessible label.
- Reorder approval controls as Approve → feedback → Decline and use distributed spacing so the opposing actions cannot be clicked accidentally.
- Keep `dcc.Dropdown`, but disable search and theme the actual Dash 4 `.dash-dropdown-*` trigger, menu, option, placeholder, icon, focus, disabled, and scrollbar states in `app/assets/app.css`.
- Introduce one shared transition duration/easing for buttons, upload, text fields, dropdowns, and other interactive states. Animate only color, border, shadow, opacity, and transforms—not layout—and retain the reduced-motion override.
- Retain the existing Cola force layout, remove `autoungrabify=True`, and allow node dragging after the initial animated layout settles. Preserve canvas pan and zoom; do not run continuous physics.

## Interfaces

- No public Python, compiler, file-format, or callback contract changes.
- Existing Dash component IDs and run-state behavior remain authoritative.
- No new dependency, JavaScript asset, or UI abstraction.

## Test Plan

- Run the existing web-layout readiness check and verify every callback still registers against an existing component.
- At desktop width, confirm Environment, Instructions, and combined Generate/Status form the control row; Results and Graph form the next equal-width row.
- At tablet/mobile widths, confirm cards stack without overflow, instruction headers remain aligned, and approval actions retain clear separation.
- Open both priority and output selectors in enabled and disabled states; verify every popup surface, option, search-free trigger, focus state, and scrollbar uses the dark theme.
- Exercise Idle, Running, Awaiting approval, Completed, Failed, and Declined states; verify controls enable/disable exactly as before.
- Generate a graph, wait for Cola to settle, then drag individual nodes and test canvas pan/zoom.
- Verify interactive transitions share one timing and `prefers-reduced-motion` effectively removes them.

## Assumptions

- “Physics” means an animated force-directed initial layout followed by draggable nodes, not a permanently running simulation.
- Priority and output lists remain dropdowns because Dash 4.4.1 native `html.Select` exposes no callback-compatible `value` property.
- Existing user and untracked repository changes remain untouched outside the two UI files.
