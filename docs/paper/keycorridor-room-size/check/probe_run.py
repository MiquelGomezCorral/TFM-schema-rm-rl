"""Probe supervisor: train every run of one queue file (caps below), then judge them (probe_judge.py).

Adapted from tp-chain-progress/outputs/chain-reg/chain_run.py; it does not rebuild the machines (run make_probes.py
and read gate/summary.txt first). Launch detached from the worktree root (a user scope survives the shell):
    systemd-run --user --scope --unit=tp-probes-<round> -- env PYTHONPATH=app PROBE_MAX_OURS=18 \
        <python> outputs/probes/probe_run.py queue-<round>.json
Stop it and every training it started: systemctl --user stop tp-probes-<round>.scope

A run starts only while fewer than PROBE_MAX_OURS of this queue train, fewer than PROBE_MAX_TOTAL (18) trainings run
on the machine, MemAvailable is at least PROBE_MIN_AVAIL_GB (8) and the GPU has PROBE_MIN_GPU_FREE_MB (1500) free.
Starts are 20 s apart. A run that died of an out-of-memory error is started once more. Finished runs (a
summary.json) are never retrained, so a restart resumes the queue.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from probe_judge import judge_all

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[1]
MAX_OURS = int(os.environ.get("PROBE_MAX_OURS", 18))
MAX_TOTAL = int(os.environ.get("PROBE_MAX_TOTAL", 18))
MIN_AVAIL_GB = float(os.environ.get("PROBE_MIN_AVAIL_GB", 8))
MIN_GPU_FREE_MB = int(os.environ.get("PROBE_MIN_GPU_FREE_MB", 1500))
STAGGER = 20.0
POLL = 30
OOM_MARKS = (b"OUT_OF_MEMORY", b"ALLOC_FAILED", b"out of memory", b"OutOfMemory")


class Queue:
    def __init__(self, path: Path, say) -> None:
        self.runs = json.loads(path.read_text(encoding="utf-8"))
        self.say = say
        self.logs = HERE / "logs" / path.stem
        self.pids = HERE / "pids" / path.stem
        self.logs.mkdir(parents=True, exist_ok=True)
        self.pids.mkdir(parents=True, exist_ok=True)
        self.starts: dict[str, int] = {}

    def alive(self, run: dict) -> bool:
        pid_file = self.pids / f"{run['name']}.pid"
        if not pid_file.is_file():
            return False
        try:
            cmdline = Path(f"/proc/{pid_file.read_text().strip()}/cmdline").read_bytes()
        except OSError:
            return False
        return b"train-rl" in cmdline and f"{run['name']}.yaml".encode() in cmdline

    def oom_crash(self, run: dict) -> bool:
        log = self.logs / f"{run['name']}.log"
        return log.is_file() and any(mark in log.read_bytes() for mark in OOM_MARKS)

    def start(self, run: dict) -> None:
        command = [
            sys.executable,
            "app/main.py",
            "train-rl",
            "--config",
            run["config"],
            "--seed",
            str(run["seed"]),
        ]
        env = {**os.environ, "OMP_NUM_THREADS": "2", "PYTHONPATH": "app", "PYTHONUNBUFFERED": "1"}
        with (self.logs / f"{run['name']}.log").open("ab") as log:
            process = subprocess.Popen(  # noqa: S603  fixed argv, no shell
                command,
                cwd=WORKTREE,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        (self.pids / f"{run['name']}.pid").write_text(str(process.pid), encoding="utf-8")
        self.starts[run["name"]] = self.starts.get(run["name"], 0) + 1
        self.say(f"started {run['name']} (pid {process.pid}, start {self.starts[run['name']]})")


def finished(run: dict) -> bool:
    return any((WORKTREE / "outputs/runs" / run["name"]).glob("seed*-*/summary.json"))


def machine_trainings() -> int:
    count = 0
    for cmdline in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            text = cmdline.read_bytes()
        except OSError:
            continue
        count += b"main.py" in text and b"train-rl" in text
    return count


def available_gb() -> float:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 1024**2
    return 0.0


def gpu_free_mb() -> int:
    query = ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"]
    out = subprocess.run(query, capture_output=True, text=True, check=False)  # noqa: S603
    return int(out.stdout.split()[0]) if out.returncode == 0 and out.stdout.strip() else 0


def main() -> None:
    queue_path = HERE / sys.argv[1]
    out = HERE / f"judge-{queue_path.stem.removeprefix('queue-')}.out"
    log = HERE / "logs" / queue_path.stem / "supervisor.log"
    log.parent.mkdir(parents=True, exist_ok=True)

    def say(text: str) -> None:
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}"
        print(line, flush=True)
        with log.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    queue = Queue(queue_path, say)
    say(
        f"queue {queue_path.name}: {len(queue.runs)} runs, at most {MAX_OURS} of ours, {MAX_TOTAL} on the machine"
    )
    while True:
        ours = [run for run in queue.runs if queue.alive(run)]
        gone = [
            r for r in queue.runs if r["name"] in queue.starts and not finished(r) and r not in ours
        ]
        retry = [r for r in gone if queue.starts[r["name"]] == 1 and queue.oom_crash(r)]
        pending = [
            r
            for r in queue.runs
            if not finished(r) and r not in ours and (r not in gone or r in retry)
        ]
        if not ours and not pending:
            break
        room = len(ours) < MAX_OURS and machine_trainings() < MAX_TOTAL
        if pending and room and available_gb() >= MIN_AVAIL_GB and gpu_free_mb() >= MIN_GPU_FREE_MB:
            queue.start(pending[0])
            time.sleep(STAGGER)
            continue
        time.sleep(POLL)

    failed = [run["name"] for run in queue.runs if not finished(run)]
    say(f"training done; {len(failed)} runs did not finish: {failed}")
    judge_all(queue_path, 100, out)
    say(f"judged into {out}")


if __name__ == "__main__":
    main()
