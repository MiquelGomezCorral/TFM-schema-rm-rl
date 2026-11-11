"""Run ``app/main.py`` unchanged and log the shape of every OpenCode chat completion.

Run from the worktree root with ``PYTHONPATH=app``: ``capture_run.py <main.py arguments>``.
Appends one JSON line per completion to ``critic-calls.jsonl`` beside this file. It records
no headers, keys, client configuration or prompts, only the reply's shape and edges.
"""

import json
import runpy
import sys
import time
from pathlib import Path

from src.engines.provider_engines import OpenCodeEngine

LOG = Path(__file__).resolve().parent / "critic-calls.jsonl"
MAIN = Path("app/main.py")
_create_completion = OpenCodeEngine._create_completion


def _append(entry: dict) -> None:
    with LOG.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _recording_create_completion(self, **request):
    """Send the request as the engine does, then log the reply (or the error)."""
    entry = {
        # Structured requests carry their schema name ("labeling_critic", "critic", ...).
        "role": request.get("response_format", {}).get("json_schema", {}).get("name", "text"),
        "model": self.model,
        "reasoning_before": self.reasoning,
    }
    started = time.monotonic()
    try:
        response = _create_completion(self, **request)
    except Exception as error:
        _append({**entry, "error": type(error).__name__, "message": str(error)[:200]})
        raise

    choice = response.choices[0] if response.choices else None
    message = choice.message if choice else None
    content = (message.content if message else None) or ""
    extra = (message.model_extra if message else None) or {}
    reasoning = extra.get("reasoning_content") or extra.get("reasoning") or ""
    _append(
        {
            **entry,
            # After the call: "low" here means the engine switched from "none" for this reply.
            "reasoning_sent": self.reasoning,
            "seconds": round(time.monotonic() - started, 2),
            "finish_reason": choice.finish_reason if choice else None,
            "usage": response.usage.model_dump() if response.usage else None,
            "content_len": len(content),
            "content_head": content[:300],
            "content_tail": content[-100:],
            "reasoning_len": len(str(reasoning)),
            "message_extra_keys": sorted(extra),
            "refusal": bool(message and getattr(message, "refusal", None)),
        }
    )
    return response


OpenCodeEngine._create_completion = _recording_create_completion

if __name__ == "__main__":
    sys.argv = [str(MAIN), *sys.argv[1:]]
    runpy.run_path(str(MAIN), run_name="__main__")
