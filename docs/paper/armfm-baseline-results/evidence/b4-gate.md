# B4 gate: ARM-FM baseline machines (2026-11-23 00:13-00:48)

All 22 new bundles pass: 11 ARM-FM, 11 FARM, no failure, no side test, nothing held. Every runs file may be
released in full (counts below). No model call, no training, no runs file or machine edited.

## Verdicts

Every bundle: verdict **pass** (C8 `ok`, retire false). Records in `B/b4-gate/` (B =
`M/plans/farm-final-20261119/armfm-baseline-b`), C8 rows appended to `FP/gate/machine-review/results.jsonl`.

| Suite | Bundle | ARM-FM | FARM | Reason |
| --- | --- | --- | --- | --- |
| xland | xland-x1-197 | pass | pass (exact) | star made, then picked up into a blue pyramid, then pyramid on the right |
| xland | xland-x2-212 | pass | pass (exact) | white key, grey star, grey star on the right, in order |
| xland | xland-x3-260 | pass | pass (also_ok) | key pickup, orange star made, orange star held |
| xland | xland-x4-859 | pass | pass (exact) | brown pyramid, blue ball, goal; the one-step make-and-goal edge is right (no blue ball exists before) |
| xland | xland-x5-594 | pass | pass (exact) | pink ball made, then on the right |
| xland | xland-za | pass | pass (exact) | key pickup before the star; wrong-2 (ball put down first) goes to the well |
| xland | xland-zb | pass | pass (also_ok) | star pickup, then pyramid on the right |
| xland | xland-zc | pass | pass (also_ok) | key pickup, then pyramid on the right |
| armfm-paper | armfm-doorkey-5x5 | pass | pass (exact) | key, door, goal |
| armfm-paper | armfm-doorkey-16x16 | pass | pass (exact) | key, door, goal |
| armfm-paper | armfm-unlock-to-unlock | pass | pass (also_ok) | key, door, key, door, ball; labeling colour-free (doors read by wall column) |

Per arm:
- **ARM-FM (11):** C1 ok* (stamp `52e8b35`, clean, reasoning max, deepseek-v4.1-flash / glm-5.3-flash, level
  page and stages; the FARM-only pricing and compiler_text records do not apply). C2 `armfm_gate.py` passes 10;
  on UnlockToUnlock it passes facts and pay order, then crashes in its seeds 1-5 rollouts (see gate gap). C3
  trace-bank labeling ok on all 11. Too simple: none flagged. No start-final machine.
- **FARM (11):** C1 ok on all 11 (xland stamp `52e8b35`; the 3 armfm-paper bundles `1f90d85`, which changed only
  `experiments/benchmark/scripts/cluster/`; both after the freeze `809dfe3`, clean, not provisional). C2 `gate_all.py` passes all 8 xland and
  both DoorKeys; UnlockToUnlock crashes there the same way, so its checks ran separately (pay order 15 > 4 > 0 >
  -10 ok; scorer also_ok, the stored clauses equal also_ok 1; generation plan check on seed 1 passes). C3 ok on
  all 11. C4 scorer: 6 exact, 5 also_ok, no mismatch. Too simple: none flagged. Ready list 11/11.
- Autonomy: all 11 FARM bundles came from their own generate-suite run with no repair, retry by hand or edit.
  `xland-zb` waited about 18 minutes on one malformed critic reply; the request was retried inside the run
  (rm-facts: attempts 1, critic interventions 0, retries 0), so it counts as autonomous.

## Gate gap: UnlockToUnlock on seeds 1-5

`armfm_gate.py`, `gate_all.py` and `sheet.py` play the card's plans on seeds 1-5, and the UnlockToUnlock plans
name seed 1's colours (README: they run on that seed only), so they stop with `PlanError: no reachable
key:yellow`. That is a tool limit, not a machine fault. Covered instead, for both arms, by
`armfm-paper/check/paper_cards_check.py` (plans on the card seed and on the 36 of 100 judge seeds where seed 1's
colours occur, solve final and wrong open; labels equal the reference over 103 traces, 100 of them random walks on
50 fresh layouts), the generation plan check on seed 1, `check-pay-order`, and the trace-bank labeling check. The
FARM UnlockToUnlock machine was read by hand from `reward_machine.txt` (no sheet).

## Runs to release

Dry runs from C (no lock, nothing written):

| Runs file | Runs it would start | Notes |
| --- | --- | --- |
| `xland/runs.yaml` | 45 of 45 | x1, zc, mix3, mix5, zab x 3 arms x 3 seeds, 5M |
| `xland/runs-mix5-noemb.yaml` | 3 of 3 | arm-fm only |
| `xland/runs-mix5-normreward.yaml` | 3 of 3 | arm-fm only |
| `armfm-paper/runs.yaml` | 12 of 27 | 5x5 and 5x5-fixed, arm-fm and farm; 15 skip as finished (8x8-fixed all 9, no-rm 5x5 and 5x5-fixed) |
| `armfm-paper/runs-5m.yaml` | 27 of 27 | 16x16, 16x16-fixed, UnlockToUnlock x 3 arms x 3 seeds |

No filtered copy was needed. Open for the user, not a gate failure: UnlockToUnlock trains on new maps, while the
released ARM-FM labeling suggests the paper used one map (README).

## Commands

All from C, with `env -i -C C HOME=/home/turbotowerlnx PATH=<RM_RL_env>/bin:/home/turbotowerlnx/.local/bin:/usr/bin:/bin
PYTHONPATH=app[:FP/tools] PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 PYTHON_DOTENV_DISABLED=1 <RM_RL_env python>`:

```
# C1
python -P FP/tools/precheck.py B/b4-gate/arm-fm 809dfe3 xland:experiments/benchmark/xland/bundles/arm-fm/<card> ... armfm-paper:experiments/benchmark/armfm-paper/bundles/arm-fm/<card> ...   (11 items)
python -P FP/tools/precheck.py B/b4-gate/farm 809dfe3 xland
python -P FP/tools/precheck.py B/b4-gate/farm-paper 809dfe3 armfm-paper
# C2
python -P FP/gate/arms-60/armfm_gate.py B/b4-gate/arm-fm <the same 11 items>
python -P FP/tools/gate_all.py B/b4-gate/farm xland
python -P FP/tools/gate_all.py B/b4-gate/farm-paper armfm-paper
python app/main.py check-pay-order experiments/benchmark/armfm-paper/bundles/farm/armfm-unlock-to-unlock --gym-id BabyAI-UnlockToUnlock-v0 --env-kwargs {}
python -P experiments/benchmark/armfm-paper/check/paper_cards_check.py      (output: B/b4-gate/arm-fm/paper_cards_check.txt, B/b4-gate/farm-paper/paper_cards_check.txt)
# C3 (writes <bundle>.labeling_check.json and bundles/labeling_check.json in these two suites only)
python app/main.py repair-labeling --traces experiments/benchmark/xland/traces --bundles experiments/benchmark/xland/bundles --check-only --parallel 10
python app/main.py repair-labeling --traces experiments/benchmark/armfm-paper/traces --bundles experiments/benchmark/armfm-paper/bundles --check-only --parallel 10
# C4
python app/main.py rm-facts --bundles experiments/benchmark/xland/bundles --tasks experiments/benchmark/xland/tasks.json --output B/b4-gate/farm/xland-rm-facts.json
python app/main.py rm-facts --bundles experiments/benchmark/armfm-paper/bundles --tasks experiments/benchmark/armfm-paper/tasks.json --output B/b4-gate/farm-paper/armfm-paper-rm-facts.json
# C5
python -P experiments/benchmark/scripts/check_too_simple.py --suite xland --start-labels --output B/b4-gate/farm/xland-too-simple.json
python -P experiments/benchmark/scripts/check_too_simple.py --suite armfm-paper --start-labels --output B/b4-gate/farm-paper/armfm-paper-too-simple.json
python -P experiments/benchmark/scripts/ready_list.py --suite xland --output B/b4-gate/farm
python -P experiments/benchmark/scripts/ready_list.py --suite armfm-paper --output B/b4-gate/farm-paper
# C7
python app/main.py run-suite --suite experiments/benchmark/<s>/<runs file> --dry-run      (all five runs files)
# C8 sheets and rows
python -P FP/tools/sheet.py B/b4-gate/farm xland
python -P FP/tools/sheet.py B/b4-gate/farm-paper armfm-paper      (DoorKeys only; stops on UnlockToUnlock)
python -P FP/soft-check/armfm_c8_view.py experiments/benchmark/<s>/bundles/<arm> experiments/benchmark/<s>/tasks.json <cards>
python -P FP/gate/arms-60/append_c8.py B/b4-gate/c8-rows-arm-fm.jsonl        (+11)
python -P FP/gate/arms-60/append_c8.py B/b4-gate/c8-rows-farm-xland.jsonl    (+8)
python -P FP/gate/arms-60/append_c8.py B/b4-gate/c8-rows-farm-paper.jsonl    (+3)
```

Earlier runs of some of these on the partial FARM set (before the embeddings landed) were overwritten by the reruns
above. One partial record stays: `B/b4-gate/arm-fm/too-simple.json` (both suites, 18 bundles before FARM finished);
the two per-suite too-simple files above supersede it. Files written in C: only `<bundle>.labeling_check.json` and
`bundles/labeling_check.json` in the xland and armfm-paper suites (both untracked bundle folders).
