"""Model-compare adapter: answer the app's model requests through a CLI and log every request.

Only the model call changes. ``install`` replaces the pipeline's engine factory so the models in
``CLAUDE_MODELS`` and ``CODEX_MODELS`` answer through one Claude Code or Codex one-shot per
request, and every engine, OpenCode included, appends each structured request and its raw reply
to one JSONL log. Prompts, schemas, parsing, retries, the critic loop and compilation stay the
app's own.
"""

import json
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.config import Configuration
from src.engines import GenericEngine, ImmediateEngineError, RetryableEngineError
from src.models import EnvironmentDescription
from src.utils import generation

CLAUDE_MODELS = frozenset({"claude-haiku-5-5"})
CODEX_MODELS = frozenset({"gpt-6-luna"})
CLI_TIMEOUT_S = 900
USAGE_STOP = 0.95  # a subscription window at 95 % or more ends the run (user rule)
CODEX_SESSIONS = Path.home() / ".codex" / "sessions"
JSON_ONLY = "Return only a JSON object matching this schema, with no markdown or commentary:"
LIMIT_WORDS = ("usage limit", "rate limit", "hit your limit", "limit reached", "quota")
# Linux caps one argv string at 128 KiB (MAX_ARG_STRLEN); the W4a critic prompt is already 98 K.
ARGV_PROMPT_LIMIT = 128 * 1024 - 1
# Codex context blocks and tools the app's prompt does not need, each checked on a probe call.
# Still sent with no flag to drop them: ~/.codex/AGENTS.md, the multi-agent role note and the
# exec, wait, request_user_input and collaboration tools.
CODEX_OFF_KEYS = (
    "include_permissions_instructions",
    "include_environment_context",
    "include_apps_instructions",
    "include_collaboration_mode_instructions",
    "skills.include_instructions",
)
CODEX_OFF_FEATURES = (
    "plugins",
    "apps",
    "hooks",
    "goals",
    "browser_use",
    "browser_use_external",
    "computer_use",
    "image_generation",
    "in_app_browser",
    "shell_tool",
    "code_mode_host",
    "view_image",
    "sleep_tool",
    "tool_suggest",
)


# ======================================================================================
#                                    ENGINE FACTORY
# ======================================================================================


def install(log_path: Path) -> None:
    """Route the CLI models through ``CliEngine`` and log every structured request to ``log_path``."""
    app_get_engine = generation.get_engine

    def get_engine(
        CONFIG: Configuration,
        environment: EnvironmentDescription,
        model: str | None,
        *,
        should_stop: Callable[[], bool] | None = None,
        warn: Callable[[str], None] | None = None,
    ) -> GenericEngine:
        if model in CLAUDE_MODELS | CODEX_MODELS:
            engine = CliEngine(environment, model)
            engine.should_stop, engine.warn = should_stop, warn
        else:
            engine = app_get_engine(CONFIG, environment, model, should_stop=should_stop, warn=warn)
            if hasattr(engine, "_create_completion"):
                _metered(engine)
        # The requester is the one seam every provider shares, so the log wraps it for all arms.
        engine._request = _logged(engine, log_path)
        return engine

    # setup_environment_and_engines looks the factory up in its module at call time.
    generation.get_engine = get_engine


def _logged(engine: GenericEngine, log_path: Path) -> Callable[..., str]:
    request = engine._request

    def send(model: str, system: str, user: str, schema: dict, name: str) -> str:
        started = time.time()
        record: dict[str, Any] = {"started": started, "model": model, "stage": name}
        record |= {"system": system, "user": user, "schema": schema}
        engine.provider_meta = None
        try:
            reply = request(model, system, user, schema, name)
            record["reply"] = reply
            return reply
        except Exception as error:
            record["error"] = f"{type(error).__name__}: {error}"
            raise
        finally:
            record["wall_s"] = round(time.time() - started, 1)
            record["model_reported"] = engine.reported_model
            record["cli"] = getattr(engine, "cli_meta", None)
            record["provider"] = engine.provider_meta
            with log_path.open("a") as handle:
                handle.write(json.dumps(record, default=str) + "\n")

    return send


def _metered(engine: GenericEngine) -> None:
    """Keep, per OpenCode reply, the reasoning level sent, refused sends, tokens and thinking size.

    The level is read after the reply because the engine switches ``none`` to ``low`` when a
    model refuses it. Thinking text arrives in a non-standard message field whose name varies
    by provider, so every string field with "reason" in its name is measured.
    """
    create = engine._create_completion

    def create_and_meter(**request: Any) -> Any:
        response = create(**request)
        message = response.choices[0].message if response.choices else None
        extra = (message.model_extra or {}) if message is not None else {}
        engine.provider_meta = {
            "reasoning_sent": engine.reasoning,
            "resends": engine.resends,
            "usage": response.usage.model_dump() if response.usage else None,
            "thinking_chars": {
                key: len(value)
                for key, value in extra.items()
                if "reason" in key and isinstance(value, str)
            },
        }
        return response

    engine._create_completion = create_and_meter


# ======================================================================================
#                                      CLI ENGINE
# ======================================================================================


class CliEngine(GenericEngine):
    """Answer each structured request with one Claude Code or Codex one-shot."""

    def __init__(self, environment: EnvironmentDescription, model: str) -> None:
        super().__init__(environment, model, f"CLI {model}", self._request_cli)
        self.cli_meta: dict[str, Any] | None = None

    def _request_cli(self, model: str, system: str, user: str, schema: dict, _name: str) -> str:
        """Send the app's system message as the system prompt and its user message plus schema.

        Returns the reply's JSON object. A reply without one goes back unchanged, so the app's
        parser rejects it as it would any provider's malformed reply.
        """
        schema_text = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
        prompt = f"{user}\n\n{JSON_ONLY}\n{schema_text}"
        run = _run_claude if model in CLAUDE_MODELS else _run_codex
        self.cli_meta = None
        # An empty folder outside the repository, so neither CLI finds project files.
        with tempfile.TemporaryDirectory(prefix="model-compare-") as folder:
            self.cli_meta = run(model, system, prompt, Path(folder))
        self.reported_model = self.cli_meta.get("model")
        _raise_on_failure(self.cli_meta)
        return _json_object(self.cli_meta["reply"])


def _run_cli(command: list[str], cwd: Path, stdin_marker: str | None) -> dict[str, Any]:
    """Run one CLI call; the record keeps its raw output, or why it gave none.

    ``command`` ends with the prompt. A prompt over the argv limit goes on stdin instead, with
    ``stdin_marker`` (when the CLI needs one) in its place; the record says which way it went.
    """
    prompt = command[-1]
    via_stdin = len(prompt.encode()) > ARGV_PROMPT_LIMIT
    if via_stdin:
        command = command[:-1] + ([stdin_marker] if stdin_marker else [])
    feed = {"input": prompt} if via_stdin else {"stdin": subprocess.DEVNULL}
    meta: dict[str, Any] = {"argv": command if via_stdin else command[:-1]}
    meta |= {"prompt_chars": len(prompt), "prompt_via": "stdin" if via_stdin else "argv"}
    try:
        completed = subprocess.run(  # noqa: S603  approved: fixed provider CLI argv, no shell
            command,
            cwd=cwd,
            **feed,
            capture_output=True,
            text=True,
            timeout=CLI_TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired:
        meta["error"] = f"timeout after {CLI_TIMEOUT_S} s"
        meta["retryable"] = True
        return meta
    except OSError as error:
        meta["error"] = f"could not start {command[0]}: {error}"
        return meta
    meta |= {"returncode": completed.returncode, "stdout": completed.stdout}
    meta["stderr"] = completed.stderr
    return meta


def _events(stdout: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in stdout.splitlines() if line.startswith("{")]


# ======================================================================================
#                                    CLAUDE AND CODEX
# ======================================================================================


def _run_claude(model: str, system: str, prompt: str, cwd: Path) -> dict[str, Any]:
    # The given one-shot argv; then the flags that leave only the app's prompt (safe mode drops
    # CLAUDE.md, skills, plugin hooks and MCP; no tools; the app's system prompt replaces Claude
    # Code's); then stream-json, whose events carry the model, tool use, cost and usage snapshot.
    command = ["claude", "--model", model, "--effort", "max", "--print"]
    command += ["--dangerously-skip-permissions", "--no-session-persistence"]
    command += ["--safe-mode", "--strict-mcp-config", "--disable-slash-commands", "--tools", ""]
    command += ["--system-prompt", system]
    command += ["--output-format", "stream-json", "--verbose", prompt]
    meta = _run_cli(command, cwd, stdin_marker=None)
    # The record already keeps the system prompt once.
    meta["argv"] = [part if part != system else "<app system prompt>" for part in meta["argv"]]
    if "stdout" not in meta:
        return meta

    events = _events(meta["stdout"])
    result = next((e for e in reversed(events) if e.get("type") == "result"), {})
    init = next((e for e in events if e.get("subtype") == "init"), {})
    messages = [e.get("message") or {} for e in events if e.get("type") == "assistant"]
    contents = [c for m in messages for c in m.get("content") or [] if isinstance(c, dict)]
    meta["model"] = init.get("model")
    meta["loaded"] = {
        "tools": init.get("tools"),
        "mcp_servers": init.get("mcp_servers"),
        "skills": len(init.get("skills") or []),
        "hook_events": sum(1 for e in events if str(e.get("subtype")).startswith("hook_")),
    }
    meta["tool_uses"] = [c.get("name") for c in contents if c.get("type") == "tool_use"]
    meta["rate_limits"] = [
        e["rate_limit_info"] for e in events if e.get("type") == "rate_limit_event"
    ]
    meta |= {
        key: result.get(key) for key in ("duration_ms", "num_turns", "total_cost_usd", "usage")
    }
    if meta["returncode"] or result.get("is_error") or not isinstance(result.get("result"), str):
        meta["error"] = str(result.get("result") or meta["stderr"] or "no result event")[:2000]
    else:
        meta["reply"] = result["result"]
    return meta


def _run_codex(model: str, system: str, prompt: str, cwd: Path) -> dict[str, Any]:
    # The given one-shot argv, with approval_policy as a -c setting (`codex exec` has no
    # --ask-for-approval flag); then the flags that leave only the app's prompt where Codex has
    # one (no user config, skills, plugins, hooks or extra instruction blocks; the app's system
    # prompt replaces Codex's); --strict-config fails on a mistyped key instead of ignoring it.
    reply_path, system_path = cwd / "reply.txt", cwd / "system.txt"
    system_path.write_text(system)
    command = ["codex", "exec", "--sandbox", "danger-full-access", "-c", "approval_policy=never"]
    command += ["-c", "model_reasoning_effort=xhigh", "--model", model, "--skip-git-repo-check"]
    command += [
        "--ignore-user-config",
        "--strict-config",
        "-c",
        f"model_instructions_file={system_path}",
    ]
    for key in CODEX_OFF_KEYS:
        command += ["-c", f"{key}=false"]
    command += ["-c", "web_search=disabled", "--enable", "skip_host_skill_discovery"]
    for feature in CODEX_OFF_FEATURES:
        command += ["--disable", feature]
    command += ["--json", "--output-last-message", str(reply_path), prompt]
    meta = _run_cli(command, cwd, stdin_marker="-")
    if "stdout" not in meta:
        return meta

    events = _events(meta["stdout"])
    thread = next((e.get("thread_id") for e in events if e.get("type") == "thread.started"), None)
    meta["usage"] = next(
        (e.get("usage") for e in events if e.get("type") == "turn.completed"), None
    )
    meta["tool_uses"] = [
        e["item"].get("type")
        for e in events
        if e.get("type") == "item.completed" and e["item"].get("type") != "agent_message"
    ]
    meta |= _codex_session(thread)
    failures = [e for e in events if e.get("type") in ("error", "turn.failed")]
    if meta["returncode"] or failures or not reply_path.exists():
        meta["error"] = (json.dumps(failures) if failures else meta["stderr"][-2000:]) or "no reply"
    else:
        meta["reply"] = reply_path.read_text()
    return meta


def _codex_session(thread: str | None) -> dict[str, Any]:
    """From the thread's session file: the model, the last rate-limit snapshot, and what was sent.

    ``loaded`` lists every input message (role, size, first words) and the tool names, so the
    log shows which context reached the model besides the app's prompt.
    """
    paths = sorted(CODEX_SESSIONS.glob(f"*/*/*/rollout-*-{thread}.jsonl")) if thread else []
    found: dict[str, Any] = {"thread": thread, "model": None, "rate_limits": None}
    loaded: dict[str, list] = {"messages": [], "tools": []}
    for line in paths[0].read_text().splitlines() if paths else []:
        payload = json.loads(line).get("payload") or {}
        if not isinstance(payload, dict):
            continue
        if payload.get("model"):
            found["model"] = payload["model"]
        if payload.get("rate_limits"):
            found["rate_limits"] = payload["rate_limits"]
        if payload.get("type") == "message" and payload.get("role") != "assistant":
            texts = [c.get("text") or "" for c in payload.get("content") or []]
            loaded["messages"] += [[payload["role"], len(t), t[:60]] for t in texts]
        if payload.get("type") == "additional_tools":
            loaded["tools"] += _tool_names(payload.get("tools") or [])
    found["loaded"] = loaded
    return found


def _tool_names(tools: list[dict[str, Any]]) -> list[str]:
    names = []
    for tool in tools:
        names += _tool_names(tool["tools"]) if tool.get("tools") else [str(tool.get("name"))]
    return names


# ======================================================================================
#                                   FAILURES AND USAGE
# ======================================================================================


def usage_peak(meta: dict[str, Any]) -> float:
    """The highest used share (0 to 1) of any subscription window a CLI call reported."""
    limits = meta.get("rate_limits")
    if isinstance(limits, list):  # Claude: one rate_limit_info per event
        windows = [w for info in limits for w in (info.get("unifiedWindows") or {}).values()]
        return max((w.get("utilization") or 0 for w in windows), default=0.0)
    if isinstance(limits, dict):  # Codex: primary and secondary windows in percent
        windows = [limits.get("primary") or {}, limits.get("secondary") or {}]
        return max((w.get("used_percent") or 0) / 100 for w in windows)
    return 0.0


def _raise_on_failure(meta: dict[str, Any]) -> None:
    error = meta.get("error")
    peak = usage_peak(meta)
    if error and any(word in error.lower() for word in LIMIT_WORDS):
        raise ImmediateEngineError(f"usage limit: {error[:300]}")
    if peak >= USAGE_STOP:
        raise ImmediateEngineError(f"usage guard: a subscription window is at {peak:.0%}")
    if error and meta.get("retryable"):
        raise RetryableEngineError(f"CLI {error}")
    if error:
        raise ImmediateEngineError(f"CLI failed: {error[:600]}")


def _json_object(reply: str) -> str:
    """The first JSON object in the reply, compact; the reply unchanged when it holds none."""
    start = reply.find("{")
    while start != -1:
        try:
            value, _end = json.JSONDecoder().raw_decode(reply, start)
        except json.JSONDecodeError:
            start = reply.find("{", start + 1)
            continue
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False)
        start = reply.find("{", start + 1)
    return reply
