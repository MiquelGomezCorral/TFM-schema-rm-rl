"""Describe the states of stored FARM bundles again with the worktree's state tagger.

The real tagging path (``tag_states``, the deepseek-v4.1-flash generator over OpenCode) runs on
each bundle's stored machine text, clauses and environment page, as the original run showed
them. No MONA, no bundle is written: one JSON per bundle goes to OUT_DIR
with every state's role, its entry guards, the new text and the stored one.

Usage (from the worktree, PYTHONPATH=<worktree>/app, under the dotenv wrapper):
    python retag.py OUT_DIR BUNDLE_DIR...
"""

import json
import os
import sys
from pathlib import Path

from scripts.ablate_rm import _stored_task
from scripts.generate_rm import _state_roles, tag_states
from src.arm_fm import load_bundle
from src.compiler import CompilationResult, compiler_machine_to_paper
from src.compiler.rm_format import paper_to_structure
from src.config import Configuration
from src.utils import get_engine

MODEL = "deepseek-v4.1-flash"


def retag(folder: Path) -> dict:
    CONFIG = Configuration(llm_provider="opencode", generator_model=MODEL, bundle=folder)
    bundle = load_bundle(folder)
    environment, proposal = _stored_task(CONFIG, bundle)
    text = (folder / "reward_machine.txt").read_text(encoding="utf-8")
    structure = paper_to_structure(bundle.reward_machine)
    # The tagger names states as the compiler does; they must be the stored names.
    renamed = compiler_machine_to_paper(structure, environment.proposition_ids)
    assert renamed.states == bundle.reward_machine.states, (renamed.states, folder)
    compiled = CompilationResult(environment, proposal, structure, text)

    engine = get_engine(CONFIG, environment, MODEL, warn=print)
    warnings: list[str] = []
    descriptions = tag_states(engine, bundle.manifest.task, compiled, warnings.append)

    roles = _state_roles(compiled)
    entries = {state: [] for state in roles}
    for item in bundle.reward_machine.transitions:
        if item.source != item.destination:
            entries[item.destination].append(f"{item.source}: {item.condition}")
    states = [
        {
            "state": state,
            "role": role,
            "entered_on": entries[state],
            "new": new,
            "old": bundle.state_descriptions.get(state),
        }
        for (state, role), new in zip(roles.items(), descriptions, strict=True)
    ]
    return {
        "bundle": str(folder),
        "task": bundle.manifest.task,
        "model": MODEL,
        "model_calls": len(engine.calls),
        "calls": engine.calls,
        "warnings": warnings,
        "last_reply": engine.last_reply,
        "states": states,
    }


def main(out_dir: Path, folders: list[Path]) -> None:
    # A repeat round sets RETAG_ATTEMPTS=1 so its model calls stay within the run's call budget.
    if attempts := os.environ.get("RETAG_ATTEMPTS"):
        Configuration.TAGGING_ATTEMPTS = int(attempts)
    out_dir.mkdir(exist_ok=True)
    for folder in folders:
        record = retag(folder)
        path = out_dir / f"{folder.parent.parent.name}-{folder.name}.json"
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", "utf-8")
        print(
            f"{folder.name}: {record['model_calls']} call(s), {len(record['warnings'])} warning(s) -> {path}"
        )


if __name__ == "__main__":
    main(Path(sys.argv[1]), [Path(argument) for argument in sys.argv[2:]])
