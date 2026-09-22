# Fix Python-skill and review findings

## Summary

Fix the reviewed issues except the optional separator cleanup and deletion of `test_env.py`. Preserve the decisions to execute labeling functions in-process and use `requirements.txt` with `RM_RL_env`.

## Implementation Changes

- Rename `_get_engine` to `get_engine`, expose it and `GenerationHooks` from `src.utils`, and replace every external `src.utils.<module>` import with `from src.utils import ...`. Use relative imports only inside `src.utils`.
- Audit the new ARM-FM code for the same package-boundary rule and expose cross-package symbols through their package `__init__.py` where needed.
- Rename `Configuration` instances and parameters to uppercase `CONFIG`; centralize duplicate workspace paths on `Configuration.WORKSPACE_PATH`.
- Make failure persistence respect `CONFIG.overwrite`. Existing bundles remain untouched unless overwrite was explicitly requested, and persistence conflicts must not hide the original generation failure.
- Keep labeling execution in-process, but strengthen AST validation against mutation, private/dunder access, reflection, and calls outside approved built-ins and documented environment methods.
- Load checkpoints with `weights_only=True` and keep the saved format limited to tensors and primitive containers.
- Lazy-import ARM-FM training commands so baseline commands and help do not import Tianshou.
- Synchronize install metadata with the new runtime dependencies while keeping `requirements.txt` authoritative.

## Tests

- Enforce that external code contains no `from src.utils.<module> import ...`.
- Verify failed generation preserves an existing bundle without `--overwrite` and replaces it only with explicit overwrite.
- Verify safe labeling predicates execute while mutation, private access, imports, and reflection are rejected.
- Round-trip a native checkpoint using safe loading.
- Confirm baseline CLI help works without importing Tianshou, then run ARM-FM tests inside `RM_RL_env`.

## Assumptions

- “Last two” means the optional separator/readability pass and deleting `test_env.py`; both remain untouched.
- No Docker or subprocess labeling sandbox is introduced.
- Decision records: no change; these edits enforce existing decisions.
