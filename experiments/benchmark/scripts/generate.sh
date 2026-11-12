#!/usr/bin/env bash
# Generate the benchmark bundles: the closed set first, then every suite for both arms (the
# pilot for FARM only), base wording and paraphrases in one call, then the ablation machines.
#
# usage: generate.sh [--dry-run] [--suite NAME]... [--max-calls N] [--deadline-min M] [--parallel N]
#   NAME is closed, smoke, base, templates, complex, pilot or ablation; without --suite all of
#   them run in that order. --dry-run prints the commands and runs nothing. The caps apply to
#   each generate-suite call, not to the whole script. The closed-set pass is its own
#   generate-suite call (per suite and arm) with its own cap; the cards it completes are
#   skipped by that suite's later call.
#
# Everything but smoke is refused while experiments/benchmark/prompt-budget.md is undecided
# (the prompt-budget gate): missing, a line starting "decision: pending", or no line starting
# "decision:". The full suites wait for the user's prompt-budget decision. A dry run still
# lists the refused commands, marked "# refused".
#
# Run it from anywhere with the RM_RL_env Python first on PATH (or set PYTHON), the provider
# variables in .env, and the embedding server up (see REPRODUCE.md).
set -euo pipefail

cd "$(dirname "$0")/../../.."
export PYTHONPATH=app
PYTHON=${PYTHON:-python}
BENCH=experiments/benchmark
BUDGET=$BENCH/prompt-budget.md
ARMS="farm arm-fm"
ABLATION_SWITCHES="progress well soft_break soft_pending end_judgment recurrent_soft_penalty"
ALL_PASSES="closed smoke base templates complex pilot ablation"

DRY_RUN=0
PASSES=""
MAX_CALLS=""
DEADLINE_MIN=""
PARALLEL=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --suite) PASSES="$PASSES $2"; shift ;;
    --max-calls) MAX_CALLS=$2; shift ;;
    --deadline-min) DEADLINE_MIN=$2; shift ;;
    --parallel) PARALLEL=$2; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done
PASSES=${PASSES:-$ALL_PASSES}

# pending: nothing is decided: the budget file is missing, has a line starting "decision: pending",
# or has no line starting "decision:" at all.
pending() {
  [ ! -f "$BUDGET" ] || grep -q '^decision: pending' "$BUDGET" || ! grep -q '^decision:' "$BUDGET"
}

# The spending caps of one generate-suite call; the smoke defaults are the smoke live test's.
caps() {
  if [ "$1" = smoke ]; then
    echo "--parallel ${PARALLEL:-3} --max-calls ${MAX_CALLS:-60} --deadline-min ${DEADLINE_MIN:-20}"
    return
  fi
  local flags=""
  [ -n "$PARALLEL" ] && flags="$flags --parallel $PARALLEL"
  [ -n "$MAX_CALLS" ] && flags="$flags --max-calls $MAX_CALLS"
  [ -n "$DEADLINE_MIN" ] && flags="$flags --deadline-min $DEADLINE_MIN"
  echo "$flags"
}

# run PASS COMMAND...: print the command (marked when the pass is refused), and run it unless
# this is a dry run. A real run never gets here for a refused pass.
run() {
  local pass=$1 prefix=""
  shift
  if [ "$pass" != smoke ] && pending; then
    prefix="# refused: "
  fi
  if [ "$DRY_RUN" = 1 ]; then
    printf '%s' "$prefix"
    printf '%q ' "$@"
    printf '\n'
  else
    "$@"
  fi
}

# card_ids FILE: the card ids of a card file, a list of ids, or {"ids": [...]} / {"cards": [...]}.
card_ids() {
  "$PYTHON" - "$1" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
items = data if isinstance(data, list) else data.get("ids") or data.get("cards") or []
for item in items:
    print(item if isinstance(item, str) else item["id"])
PY
}

# generate PASS SUITE ARM [ONLY]: one generate-suite call for one suite and arm. Outside smoke it
# adds --paraphrases, which also covers the base wordings, so the caps hold for the whole suite.
generate() {
  local pass=$1 suite=$2 arm=$3 only=${4:-} output
  output=$BENCH/$suite/bundles/$arm
  if [ "$suite" = smoke ]; then
    output=outputs/wave-tests/smoke/$arm
  fi
  local command=("$PYTHON" app/main.py generate-suite --tasks "$BENCH/$suite/tasks.json" --arm "$arm" --output "$output")
  if [ -n "$only" ]; then
    command+=(--only "$only")
  fi
  if [ "$suite" != smoke ]; then
    command+=(--paraphrases)
  fi
  # shellcheck disable=SC2046  # the caps are separate words by design
  run "$pass" "${command[@]}" $(caps "$suite")
}

# have FILE: true when the card file exists; a dry run notes the ones another slice adds.
have() {
  [ -f "$1" ] && return 0
  echo "# missing $1; skipped" >&2
  return 1
}

pass_closed() {
  have "$BENCH/closed-set.json" || return 0
  local suite ids closed suite_ids
  closed=$(card_ids "$BENCH/closed-set.json" | sort) || exit 1
  for suite in base templates complex; do
    have "$BENCH/$suite/tasks.json" || continue
    # The closed set's cards of this suite go into the suite's own folder, so the full pass skips them.
    suite_ids=$(card_ids "$BENCH/$suite/tasks.json" | sort) || exit 1
    ids=$(comm -12 <(echo "$closed") <(echo "$suite_ids") | paste -sd, -)
    [ -z "$ids" ] && continue
    for arm in $ARMS; do
      generate closed "$suite" "$arm" "$ids"
    done
  done
}

pass_suite() {
  local suite=$1 arm arms=$ARMS
  have "$BENCH/$suite/tasks.json" || return 0
  [ "$suite" = pilot ] && arms=farm
  for arm in $arms; do
    generate "$suite" "$suite" "$arm"
  done
}

pass_ablation() {
  have "$BENCH/complex/ablation.json" || return 0
  local card switch cards
  cards=$(card_ids "$BENCH/complex/ablation.json") || exit 1
  for card in $cards; do
    for switch in $ABLATION_SWITCHES; do
      run ablation "$PYTHON" app/main.py ablate-rm \
        --bundle "$BENCH/complex/bundles/farm/$card" --off "$switch" \
        --output "$BENCH/ablation/bundles/$card/off-$switch"
    done
  done
}

if [ "$DRY_RUN" = 0 ] && pending; then
  for pass in $PASSES; do
    if [ "$pass" != smoke ]; then
      echo "refused: $pass waits for the prompt-budget decision ($BUDGET has no decision yet)" >&2
      exit 1
    fi
  done
fi

for pass in $PASSES; do
  case "$pass" in
    closed) pass_closed ;;
    smoke | base | templates | complex | pilot) pass_suite "$pass" ;;
    ablation) pass_ablation ;;
    *) echo "unknown suite: $pass" >&2; exit 2 ;;
  esac
done
