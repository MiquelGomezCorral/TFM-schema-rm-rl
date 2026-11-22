#!/bin/bash
# Runbook step 8: the 46-case benchmark, 3 runs per thinking level, levels in order, PARALLEL runs at once.
# Usage: level-bench.sh PARALLEL [LEVEL...]. Log: freeze-prep/run-logs/level-bench.log.
# Each level waits for 10 GB free RAM, runs under budget_guard (runs so far + 140, calls so far + 450), and the
# driver writes until-fix/runs/STOP at the first quota or region error. A STOP file ends the driver.
set -u
P=/home/turbotowerlnx/Documents/Master/TFM/TFM-schema-rm-rl/.git/agent-memory/plans/farm-final-20261119
U=$P/until-fix
LOG=$P/freeze-prep/run-logs/level-bench.log
PY=/home/turbotowerlnx/miniconda3/envs/RM_RL_env/bin/python
CASES=W5a,G12,O2,O3,W1a,W1b,W2a,W2b,W3a,W3b,W4a,W4b,W5b,W6,CX,C1,C2,C3,U1,U2,U3,U4,U5,U6,U7,O1,O4,O5,O6,O7,O8,G1,G2,G3,G4,G5,G6,G7,G8,G9,G10,G11,S1,S2,S3,S4
par=$1
shift
levels=${*:-none low medium high max}
say() { echo "$(TZ=Europe/Madrid date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }
for L in $levels; do
  [ -e "$U/runs/STOP" ] && { say "STOP file present, not starting $L: $(cat "$U/runs/STOP")"; exit 1; }
  while [ "$(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo)" -lt 10 ]; do sleep 60; done
  total=$($PY "$U/tools/budget.py" | grep '^TOTAL')
  runs=$(echo "$total" | sed -n 's/^TOTAL: runs \([0-9]*\), calls.*/\1/p')
  calls=$(echo "$total" | sed -n 's/^TOTAL: runs [0-9]*, calls \([0-9]*\).*/\1/p')
  say "start freeze-$L p$par ($total)"
  bash "$U/tools/run_arms.sh" "freeze-$L" "$CASES" A 3 "$par" "$L" &
  arms=$!
  sleep 30
  bash "$U/tools/budget_guard.sh" $((runs + 140)) $((calls + 450)) &
  guard=$!  # stopped when the level ends: it keeps watching while any round runs, so it would stop the next level
  while kill -0 "$arms" 2>/dev/null; do
    if grep -l -s -E "GoUsageLimitError|invalid_request_error" "$U/runs/freeze-$L"/A/*.log "$U/runs/freeze-$L"/A/*.calls.jsonl > /dev/null; then
      [ -e "$U/runs/STOP" ] || { echo "quota/region error in freeze-$L" > "$U/runs/STOP"; say "quota/region error in freeze-$L: STOP written"; }
    fi
    sleep 60
  done
  kill "$guard" 2>/dev/null
  wait "$guard" 2>/dev/null
  say "end freeze-$L: $(tail -n 1 "$U/runs/freeze-$L/round.log")"
done
say "all levels done"
