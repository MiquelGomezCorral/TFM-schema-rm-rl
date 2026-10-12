"""Import the authors' released ARM-FM artifacts for one environment as a trainable bundle.

``--reference`` is a local clone of github.com/roger-creus/llms-rm-rl. Its files are read at
run time and written only into the output bundle, so none of its text enters this repository.

Usage:
    python app/main.py import-paper-bundle --reference ~/src/llms-rm-rl --env DoorKey \
        --output outputs/bundles/paper-authors-DoorKey
"""

import json
import re
from pathlib import Path

import numpy as np

from src.arm_fm import ArtifactBundle, BundleManifest, clone_head, infer_final_states
from src.compiler import parse_paper_reward_machine
from src.config import Configuration

PAPER_ENVIRONMENTS = ("DoorKey", "UnlockToUnlock", "BlockedUnlockPickup", "KeyCorridorS6R3")
_STAGES = ("reward_machine", "labeling", "descriptions", "embeddings")
_MISSION = re.compile(r'\*\*Mission:\*\*\s*"(.+?)"', re.DOTALL)
_EVENT_NOTE = "Released labeling function of the authors; no description was published."


def import_paper_bundle(CONFIG: Configuration) -> None:
    """Write the released RM, labeling, state descriptions and embeddings as one bundle.

    The RM events are the guard names of ``RM-vFINAL.txt``; ``FNS-vFINAL.py`` is copied as is
    and may define more functions than the RM uses. The task text is the mission quoted in the
    authors' generation trace, which for KeyCorridorS6R3 is the DoorKey mission. The released
    RM names no final state and the bundle keeps it that way, so only the environment ends an
    episode; the states that cannot be left are our inference, recorded in the manifest only.

    Raises:
        ValueError: If an option is missing, the environment is unknown, or the clone lacks a file.
        BundleValidationError: If the imported files do not form a complete bundle.
    """
    if CONFIG.reference is None or CONFIG.paper_env is None or CONFIG.bundle is None:
        raise ValueError("import-paper-bundle requires --reference, --env and --output")
    if CONFIG.paper_env not in PAPER_ENVIRONMENTS:
        raise ValueError(f"--env must be one of {', '.join(PAPER_ENVIRONMENTS)}")

    machine_dir = CONFIG.reference / "reward_machines" / CONFIG.paper_env
    embedding_dir = CONFIG.reference / "state_embeddings" / CONFIG.paper_env
    machine = parse_paper_reward_machine((machine_dir / "RM-vFINAL.txt").read_text("utf-8"))
    generator = f"authors-released @ {clone_head(CONFIG.reference)}"
    task, trace = _mission(machine_dir)

    # allow_pickle stays off: the clone is untrusted input.
    embeddings = {
        state: np.load(embedding_dir / f"{state}.npy").tolist() for state in machine.states
    }
    descriptions = json.loads((embedding_dir / "state_descriptions.json").read_text("utf-8"))
    manifest = BundleManifest(
        task=task,
        environment=CONFIG.paper_env,
        proposition_semantics=dict.fromkeys(machine.propositions, _EVENT_NOTE),
        provenance={"generator": generator, "status": "imported", "mission_source": trace},
        generation={
            "generator": generator,
            "final_states_inferred": list(infer_final_states(machine)),
        },
        validation={"structural": True},
        stage_status=dict.fromkeys(_STAGES, "complete"),
        inputs={"task": task},
        effective_settings={
            "embedding": {"source": "authors u*.npy", "dimension": len(embeddings["u0"])},
            "mode": "arm-fm",
        },
    )
    bundle = ArtifactBundle(
        manifest,
        machine,
        (machine_dir / "FNS-vFINAL.py").read_text("utf-8"),
        descriptions,
        embeddings,
    )

    bundle.validate(require_complete=True)
    print(bundle.save(CONFIG.bundle, overwrite=CONFIG.overwrite))


def _mission(machine_dir: Path) -> tuple[str, str]:
    """Return the quoted mission and the trace file name it was read from."""
    for trace in sorted(machine_dir.glob("GENCRIT-TRACE*.txt")):
        match = _MISSION.search(trace.read_text("utf-8"))
        if match:
            return " ".join(match.group(1).split()), trace.name
    raise ValueError(f"No quoted mission found in the generation traces of {machine_dir}")
