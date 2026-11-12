# Generation cost per bundle, FARM and ARM-FM

Date: 2026-11-12, from the S6 live smoke (L6.1) on three cards, with the 3-attempt limit that was the
default then. Six bundles, one model pair (generator `deepseek-v4.1-flash`, critic `glm-5.3-flash`),
reasoning `none`: a smoke measurement, not a benchmark of the two methods.

## What it shows

Each bundle is a Reward Machine plus its labeling functions and state descriptions. On the same three
cards, with the same models:

| Arm | Model calls per bundle | Wall time per bundle | Attempts (critic interventions) |
| --- | --- | --- | --- |
| FARM | 5 to 7 (mean 5.7) | 21 to 31 s (mean 24.3 s) | 2, 1, 1 (1, 0, 0) |
| ARM-FM | 7 to 9 (mean 7.7) | 36 to 46 s (mean 39.7 s) | 3, 2, 2 (2, 1, 1) |

ARM-FM, which writes the whole machine in one go, needed more attempts and about 1.6 times the wall
time of FARM, which asks for clauses and compiles the machine. All six bundles ended `complete`. With
three cards, the ranges are the honest summary; the ratio is a rough one.

## Per card

| Card | Natural-language task | LTL (what FARM compiled) | Arm | Calls | Time | Graph | RM text |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `smoke-doorkey-base` | Use the key to open the door, then reach the goal. | has_key happens at some point; door_open happens at some point; door_open does not happen before has_key; at_goal happens at some point; at_goal does not happen before door_open | FARM | 7 | 30.5 s | [graph](graphs/farm-doorkey-base.html) | [text](graphs/farm-doorkey-base.rm.txt) |
| | | none (ARM-FM writes the machine directly) | ARM-FM | 9 | 46.1 s | [graph](graphs/arm-fm-doorkey-base.html) | [text](graphs/arm-fm-doorkey-base.rm.txt) |
| `smoke-doorkey-response` | Whenever you hold the key, open the door afterwards, and reach the goal. | Whenever the agent holds the key, open the door afterwards; Reach the goal | FARM | 5 | 21.3 s | [graph](graphs/farm-doorkey-response.html) | [text](graphs/farm-doorkey-response.rm.txt) |
| | | none | ARM-FM | 7 | 37.1 s | [graph](graphs/arm-fm-doorkey-response.html) | [text](graphs/arm-fm-doorkey-response.rm.txt) |
| `smoke-unlock-pickup-base` | Acquire the matching key, unlock the door, and pick up the designated box in the other room. | has_door_key; door_open; target_picked_up; has_door_key before door_open; door_open before target_picked_up | FARM | 5 | 21.0 s | [graph](graphs/farm-unlock-pickup-base.html) | [text](graphs/farm-unlock-pickup-base.rm.txt) |
| | | none | ARM-FM | 7 | 35.8 s | [graph](graphs/arm-fm-unlock-pickup-base.html) | [text](graphs/arm-fm-unlock-pickup-base.rm.txt) |

The LTL column is the clause list FARM's compiler wrote for the card, in the words the run recorded
(`ltl_clauses`); the formulas of the same wording are on the base cards in the card-set entry.

## Where the numbers come from

- Calls and times are the lines `generate-suite` printed (`evidence/l61-farm.out`,
  `evidence/l61-arm-fm.out`). The stamp inside each bundle records a shorter generation time (FARM
  24.3, 15.3 and 15.0 s; ARM-FM 40.2, 31.0 and 29.8 s), taken over the generation itself; the status
  files give 2.8 and 2.7 s for the first bundle of each arm, which is inconsistent with their own
  stamps. This entry uses the printed lines for both arms, so the arms are compared like for like.
- Attempts and critic interventions are the stamp's fields (`evidence/l6-smoke-evidence.json`).

## What this does not show

- Cost of the whole benchmark: the full suites use up to 10 attempts (decision of 2026-11-12), so the
  per-bundle cost will rise, and more for the arm that needs more attempts.
- Quality: a cheaper bundle is not a better one. ARM-FM's machines are cross-judged in the
  [cross-critic caution](../s6-cross-critic-caution/README.md), where the FARM critic's verdicts are
  not evidence of quality.
- Three cards and one model pair; the times depend on the provider's load that morning.

## Files

- `evidence/`: the smoke evidence JSON (task, clauses, RM text, stamps and cross-critic verdicts of the
  six bundles) and the command outputs.
- `graphs/`: the six machines as live HTML, SVG and RM text.

## Rerun

The smoke needs the provider, so it is not rerun from this folder. The commands, from the repository
root, were the `smoke` suite of `experiments/benchmark/REPRODUCE.md` (3 cards x 2 arms, capped):

```bash
bash experiments/benchmark/scripts/generate.sh --suite smoke --dry-run   # lists the commands
```

The counts above can be listed from the evidence file:

```bash
python -c "import json; [print(e['arm'], e['card'], e['status']['calls'], e['stamp']['attempts'], e['stamp']['critic_interventions']) for e in json.load(open('docs/paper/s6-generation-cost/evidence/l6-smoke-evidence.json'))]"
```

## Code

`generate-suite` and its provenance stamps (`app/scripts/`), merged into the wave as `merge:
tp-s6-generation` (commit `ab1ecbc`).
