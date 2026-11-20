"""W5a at `max`: generator output tokens, wall time and speed, non-streamed in the loops and streamed in the replays.

Usage: python docs/paper/hidden-output-schema/check/w5a_speed.py     (from the repository root)
No model call. Non-streamed: every logged W5a generator call of loop 2 and of the shape-fix rounds
(`evidence/runs/*/A/W5a-r1.calls.jsonl`; a timed-out call logs no tokens). Streamed: the replay
summaries in `evidence/w5a-timeout/` (the same logged request resent with "stream": true; `pre` = the
loop-2 request, `post` = the shape-fix request; `ns` = the same request not streamed). The last line
sums every copied call log: the longest non-streamed reply and where the failed calls ended.
"""

import json
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent.parent / "evidence"


def speed(tokens: int, seconds: float) -> str:
    return f"{tokens / seconds:.0f}" if tokens and seconds else "-"


def main() -> None:
    print("| source | call | streamed | wall s | output tokens | tokens/s | result |")
    print("|---|---|---|---|---|---|---|")
    for log in sorted(EVIDENCE.glob("runs/*/A/W5a-r1.calls.jsonl")):
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        for i, call in enumerate(c for c in calls if c["stage"] == "declare_proposal"):
            usage = (call.get("provider") or {}).get("usage") or {}
            tokens = usage.get("completion_tokens") or 0
            result = call.get("error") or "reply"
            print(
                f"| {log.parent.parent.name} | {i + 1} | no | {call['wall_s']:.0f} | {tokens or '-'} "
                f"| {speed(tokens, call['wall_s'])} | {result[:60]} |"
            )
    for path in sorted((EVIDENCE / "w5a-timeout").glob("*.json")):
        replay = json.loads(path.read_text())
        usage = replay.get("usage") or {}
        tokens = usage.get("completion_tokens") or 0
        streamed = "no" if "-ns-" in replay["label"] else "yes"
        result = replay.get("error") or f"{replay['ended']}, {replay['n_clauses']} clauses"
        print(
            f"| replay | {replay['label']} | {streamed} | {replay['wall_s']:.0f} | {tokens or '-'} "
            f"| {speed(tokens, replay['wall_s'])} | {result[:60]} |"
        )
    calls = [
        json.loads(line)
        for log in EVIDENCE.glob("runs/*/A/*.calls.jsonl")
        for line in log.read_text().splitlines()
    ]
    replies = [c["wall_s"] for c in calls if not c.get("error")]
    errors = sorted({round(c["wall_s"]) for c in calls if c.get("error")})
    print(
        f"All {len(calls)} copied non-streamed calls: longest reply {max(replies):.1f} s, "
        f"replies between 300 and 600 s: {sum(300 <= w < 600 for w in replies)}, failed calls ended at {errors} s"
    )


if __name__ == "__main__":
    main()
