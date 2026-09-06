# Readable, stable Reward Machine graph

## Goal

Make reward-machine graphs readable and stable without changing RM semantics or serialized output.

## Context

The supplied diamond RM is correct. Its graph is unreadable because each explicit valuation becomes a separate parallel Cytoscape edge. Existing graph code is in `app/src/web/visualization.py`, layout/UI in `app/src/web/components.py`, and callbacks in `app/src/web/application.py`.

## Files touched

- `app/src/web/visualization.py`
- `app/src/web/components.py`
- `app/src/web/application.py`
- `app/assets/00-tailwind.css`

## Requirements

1. Group visual transitions by `(source, destination)` while retaining every original guard/reward pair in edge `cases` data.
2. Display each grouped edge as `N case(s) · r=<value>`; use `mixed r` only if cases have differing rewards.
3. Add edge classes for positive, zero, negative, and rejecting transitions. Positive is green, zero muted white, negative/rejecting soft rose.
4. Add a floating graph overlay that:
   - previews on edge hover;
   - pins on edge click;
   - unpins on node click or its close button;
   - lists every formal case immediately, with off-white positive literals, pale-rose negated literals, and reward color by sign.
5. Make the legend an absolute overlay within the graph panel so it never changes graph canvas size.
6. Add a focus toggle:
   - normal layout remains unchanged;
   - focused layout hides Environment, Tasks, and Run status;
   - keeps the existing Compiled Reward Machine panel, selector/import controls, and raw RM in a narrow left column;
   - gives the graph all remaining width;
   - does not change graph elements, layout settings, pan, zoom, or node positions.
7. Keep Cola continuous physics, but remove the many parallel force pulls via grouping. Set `wheelSensitivity=0.15`.
8. Apply one-line ellipsis truncation to long Run status task titles; include the full title as the native `title` tooltip.
9. Do not add tests under `./tests`.

## Steps

1. In `reward_machine_to_elements`, collect transitions by source/destination and emit one Cytoscape edge per group. Store `cases`, `case_count`, formatted display label, and style class; keep node data unchanged.
2. Extend `CYTOSCAPE_STYLESHEET` with the grouped edge color classes.
3. In `graph_panel`, add:
   - focus button;
   - absolute-positioned legend;
   - hidden transition-inspector overlay with close button;
   - `wheelSensitivity=0.15`;
   - Cytoscape hover/click support with `clearOnUnhover=True`.
4. Add stable IDs to the workspace, input region, Run status sidebar, and output region. Add a `dcc.Store` for pinned graph-edge data and focus state.
5. In `application.py`, add one callback for hover/pin/unpin that renders formal case chips, and one callback that toggles focus CSS classes without replacing the graph component.
6. Add truncation classes and native title tooltip in `render_steps`.
7. Run `npm run build:css` to include the new static Tailwind utility classes in the served stylesheet.
8. Inspect the final diff and run the smallest readiness check: `python -m compileall -q app/src`.

## Applicable instructions

- `AGENTS.md`: preserve unrelated dirty worktree changes and use focused edits.
- `AGENTS.md`: do not add tests merely for coverage; user explicitly excludes `./tests`.
- `AGENTS.md`: no decision-record update is needed because compiler semantics and output format remain unchanged.
- `ponytail`: reuse Dash/Cytoscape and Tailwind; add no dependency or custom JavaScript.
- `review-plan`: live validation remains user-approved.

## Live validation

Flow: Load the supplied diamond RM, hover and pin the grouped rejecting edge, toggle focus mode, drag a node, and zoom.

Expected: One grouped visual edge per state pair; readable formal cases in the overlay; legend does not resize the canvas; focus preserves viewport; movement is gentle; zoom increments are smaller.

Can run: User-only, pending approval, in the running Dash application.

## Main-agent memory updates

None needed.

## Out of scope

- Reward-machine compiler/parser semantics.
- Per-task persistence while other tasks run; that conflicts with the current atomic-output decision until explicitly revised.
- Changes outside the four listed files.

Decision records: no change — presentation-only graph changes; compiler semantics and persisted RM format remain unchanged.
Record changes: none
Enforcement: existing compiler/parser and web presentation code
