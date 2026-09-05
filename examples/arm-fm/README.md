# ARM-FM Environment Catalogue

These examples describe the environments reported in `docs/ARM-FM/ARM-FM.md` for
the current natural-language-to-LTLf Reward Machine generator. They define RM
propositions only. Labeling-function generation and RL integration are intentionally
out of scope.

## Sources

- ARM-FM code: <https://github.com/roger-creus/llms-rm-rl> (inspected at commit
  `9a38c4a0f4e82c02052218193f033b2575bd3396`).
- MiniGrid/BabyAI: <https://github.com/Farama-Foundation/Minigrid>.
- Craftium: <https://github.com/mikelma/craftium>.
- Meta-World: <https://github.com/Farama-Foundation/Metaworld>.
- XLand-MiniGrid: <https://github.com/corl-team/xland-minigrid>.

## Installation entry points

- MiniGrid/BabyAI: `pip install minigrid`, then `gymnasium.make(<environment-id>)`.
- Meta-World: `pip install metaworld`, then use the MT1 constructions listed below.
- XLand-MiniGrid: `pip install xminigrid`; it uses `xminigrid.make` and
  `xminigrid.load_benchmark`, not Gymnasium registration.
- Craftium: use a prebuilt release or clone with
  `git clone --recurse-submodules https://github.com/mikelma/craftium.git`; its native
  build has system dependencies, so it is not added to this project's requirements.

## Reported environments

| Paper task | Runnable source | Example |
|---|---|---|
| DoorKey, all sizes | `MiniGrid-DoorKey-{5x5,6x6,8x8,16x16}-v0` | `minigrid-doorkey/environment.md` |
| UnlockPickup | `MiniGrid-UnlockPickup-v0` | `minigrid-unlock-pickup/environment.md` |
| BlockedUnlockPickup | `MiniGrid-BlockedUnlockPickup-v0` | `minigrid-blocked-unlock-pickup/environment.md` |
| UnlockToUnlock | `BabyAI-UnlockToUnlock-v0` | `babyai-unlock-to-unlock/environment.md` |
| KeyCorridor | `MiniGrid-KeyCorridorS6R3-v0` | `minigrid-key-corridor/environment.md` |
| Craftium diamond gathering | Closest stock carrier: `Craftium/OpenWorld-v0` | `craftium-diamond/environment.md` |
| Meta-World Assembly | `gym.make("Meta-World/MT1", env_name="assembly-v3")` | `metaworld-assembly/environment.md` |
| Meta-World Bin-Picking | `gym.make("Meta-World/MT1", env_name="bin-picking-v3")` | `metaworld-bin-picking/environment.md` |
| Meta-World Pick-Place | `gym.make("Meta-World/MT1", env_name="pick-place-v3")` | `metaworld-pick-place/environment.md` |
| Meta-World Shelf-Place | `gym.make("Meta-World/MT1", env_name="shelf-place-v3")` | `metaworld-shelf-place/environment.md` |
| Meta-World Stick-Push | `gym.make("Meta-World/MT1", env_name="stick-push-v3")` | `metaworld-stick-push/environment.md` |
| XLand-MiniGrid `medium-1m` | `xminigrid.load_benchmark("medium-1m")` | `xland-minigrid/environment.md` |

## Reproducibility notes

- The ARM-FM repository publishes runnable code and finalized artifacts only for
  DoorKey, BlockedUnlockPickup, UnlockToUnlock, and KeyCorridor. It lists S6R3 for
  KeyCorridor, while the paper's human-intervention table says S3R3; this catalogue
  follows the released code (`MiniGrid-KeyCorridorS6R3-v0`).
- UnlockPickup appears in the paper's human-intervention table but has no released RM
  artifact in the ARM-FM repository. Its official MiniGrid environment is still
  runnable.
- The paper's Craftium diamond task is a custom sparse-reward experiment. The stock
  `Craftium/OpenWorld-v0` environment is the closest public carrier, not an exact
  reproduction of the unpublished configuration.
- The paper adapts Meta-World to sparse rewards. The official MT1 tasks are runnable,
  but reproducing the reported experiment requires the paper's unpublished sparse
  reward wrapper and training configuration.
- The paper identifies the first 1,000 rulesets from `medium-1m`, but does not identify
  the XLand grid carrier. The example uses the official benchmark API and records
  `XLand-MiniGrid-R4-13x13` only as a practical default, not as a paper-reported fact.

## Prompt layout

The reusable creator and reviewer prompts now live in `app/src/prompts`. Their public
Python functions render the user templates and append use-case information only under
`Case-specific context`. They are not yet wired into the runtime engines.

## Reconstruction artefacts

Each environment directory contains only the evidence categories that apply:

- `tasks.md` lists paper-reported or source-recoverable tasks plus small probes for
  the current pipeline.
- `reward-machines.md` preserves RMs actually printed in the paper or released in its
  repository. It does not silently repair malformed published machines.
- `task-rm-pairs.md` links the two and labels the pair as exact, inferred, or merely
  associated by the paper.

All environments have a task catalogue. UnlockPickup and XLand-MiniGrid have no
`reward-machines.md` or `task-rm-pairs.md` because their complete RMs are not
published. Source-associated generator input–output pairs are recoverable only for
DoorKey, BlockedUnlockPickup, and UnlockToUnlock. KeyCorridor is an inferred pair
because its released trace contains the wrong mission. Craftium and Meta-World pairs
are supported by the paper but lack the original generator prompts.

The reconstruction targets are multi-stage tasks. Submit each reconstruction target as
one task so its clauses are composed into one task-specific RM; use the atomic probes
only to isolate individual stages. The current compiler can compose the clauses, but
its limited DECLARE templates and deterministic reward policy do not guarantee a
byte-identical copy of a paper RM.
