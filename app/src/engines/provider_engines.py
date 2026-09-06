"""Provider-specific adapters for structured-output engines."""

import json
import os
from functools import partial
from pathlib import Path
import subprocess
from typing import Any

from openai import OpenAI

from src.models import EnvironmentDescription

from .errors import ImmediateEngineError, RetryableEngineError
from .generic_engine import GenericEngine
from .structured import completion_text, responses_text


ANTIGRAVITY_AGENT = "schema-rm-provider"
ANTIGRAVITY_TIMEOUT_SECONDS = 305
WORKSPACE_PATH = Path(__file__).resolve().parents[3]

# ======================================================================================
#                                  PROVIDER ADAPTERS
# ======================================================================================

class OpenAIEngine(GenericEngine):
    """IBM Engine-compatible backend using OpenAI Structured Outputs."""

    def __init__(
        self,
        environment: EnvironmentDescription,
        model: str | None,
    ) -> None:
        model = _required_model(model, "OpenAI")
        client = OpenAI(api_key=_required_env("OPENAI_API_KEY"), max_retries=0)
        super().__init__(
            environment,
            model,
            "OpenAI",
            partial(_request_responses, client),
        )


class OpenCodeEngine(GenericEngine):
    """IBM Engine-compatible backend using OpenCode's OpenAI-compatible API."""

    def __init__(
        self,
        environment: EnvironmentDescription,
        model: str | None,
    ) -> None:
        model = _required_model(model, "OpenCode")
        client = OpenAI(
            api_key=_required_env("OPENCODE_API_KEY"),
            base_url=os.environ.get("OPENCODE_BASE_URL") or "https://opencode.ai/zen/v1",
            max_retries=0,
        )
        super().__init__(
            environment,
            model,
            "OpenCode",
            partial(_request_chat_completions, client),
        )


class AntigravityEngine(GenericEngine):
    """IBM Engine-compatible backend using Antigravity's local CLI."""

    def __init__(
        self,
        environment: EnvironmentDescription,
        model: str | None,
    ) -> None:
        model = _required_model(model, "Antigravity")
        super().__init__(
            environment,
            model,
            "Antigravity",
            _request_antigravity,
        )


# ======================================================================================
#                                PROVIDER REQUEST HELPERS
# ======================================================================================

def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _required_model(model: str | None, provider_name: str) -> str:
    if not model:
        raise ValueError(f"A {provider_name} model is required")
    return model


def _request_responses(
    client: OpenAI,
    model: str,
    system: str,
    user: str,
    schema: dict,
    name: str,
) -> str:
    response = client.responses.create(
        model=model,
        input=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        text={"format": {"type": "json_schema", "name": name, "strict": True, "schema": schema}},
    )
    return responses_text(response)


def _request_chat_completions(
    client: OpenAI,
    model: str,
    system: str,
    user: str,
    schema: dict,
    name: str,
) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": name, "strict": True, "schema": schema},
        },
    )
    return completion_text(response)

# ======================================================================================
#                                PROVIDER ANTIGRAVITY
# ======================================================================================
def _request_antigravity(
    model: str,
    system: str,
    user: str,
    schema: dict,
    name: str,
) -> str:
    """Run one schema-constrained Antigravity turn and return its JSON output."""
    request = json.dumps(
        {
            "application_instructions": system,
            "application_input": user,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    user_event = json.dumps(
        {
            "event": "user",
            "message": {"content": request},
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ) + "\n"
    command = [
        "agy",
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--json-schema",
        json.dumps(schema, separators=(",", ":")),
        "--model",
        model,
        "--agent",
        ANTIGRAVITY_AGENT,
        "--disable-slash-commands",
    ]

    try:
        # ponytail: one process per request keeps lifecycle simple; add a persistent
        # stream only if measured CLI startup latency becomes material.
        completed = subprocess.run(
            command,
            input=user_event,
            capture_output=True,
            text=True,
            shell=False,
            cwd=WORKSPACE_PATH,
            timeout=ANTIGRAVITY_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as error:
        raise ImmediateEngineError(
            "Antigravity CLI 'agy' is not installed or is not on PATH"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise RetryableEngineError("Antigravity request timed out") from error
    except OSError as error:
        raise ImmediateEngineError(f"Could not start Antigravity CLI: {error.strerror}") from error

    if completed.returncode:
        diagnostics = " ".join(
            value for value in (
                _antigravity_result_error(completed.stdout or ""),
                completed.stderr or "",
            ) if value
        )
        raise ImmediateEngineError(_antigravity_exit_message(diagnostics))
    return _parse_antigravity_output(completed.stdout)


def _antigravity_exit_message(stderr: str) -> str:
    """Turn private CLI diagnostics into concise actionable application errors."""
    diagnostic = stderr.lower()
    if any(marker in diagnostic for marker in ("login", "auth", "credential", "sign in")):
        hint = "Antigravity authentication failed; run 'agy' interactively once to sign in"
    elif "not found" in diagnostic and "model" in diagnostic:
        hint = "Antigravity model is unavailable; choose a slug from 'agy models'"
    else:
        hint = "Antigravity CLI exited with a nonzero status"
    # Always include the raw diagnostic so the real cause is visible.
    if stderr.strip():
        return f"{hint} — raw: {stderr.strip()}"
    return hint


def _antigravity_result_error(output: str) -> str:
    """Extract nested result error text without requiring a completed session."""
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("event") != "result":
            continue
        result = event.get("result")
        if not isinstance(result, dict) or not result.get("error"):
            continue
        error = result["error"]
        return error if isinstance(error, str) else json.dumps(error)
    return ""


def _parse_antigravity_output(output: str) -> str:
    """Validate the constrained session and extract the single terminal result."""
    saw_init = False
    result: dict[str, Any] | None = None
    for line in output.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise ImmediateEngineError(
                "Antigravity returned malformed stream-json output"
            ) from error
        if not isinstance(event, dict):
            raise ImmediateEngineError("Antigravity returned an invalid stream event")

        event_type = event.get("event")
        if event_type == "init":
            if saw_init:
                raise ImmediateEngineError("Antigravity returned duplicate init events")
            saw_init = True
            init = event.get("init")
            if not isinstance(init, dict):
                raise ImmediateEngineError("Antigravity returned an invalid init event")
            if (
                init.get("agent") != ANTIGRAVITY_AGENT
                or not isinstance(init.get("tools"), list)
            ):
                raise ImmediateEngineError("Antigravity returned an invalid init event")
        elif event_type == "step_update":
            step_update = event.get("step_update")
            if not isinstance(step_update, dict):
                raise ImmediateEngineError("Antigravity returned an invalid step update")
            if step_update.get("step_type") == "tool":
                raise ImmediateEngineError("Antigravity agent used a tool unexpectedly")
            if step_update.get("subagent_info"):
                raise ImmediateEngineError("Antigravity agent invoked a subagent unexpectedly")
        elif event_type == "result":
            if not saw_init:
                raise ImmediateEngineError("Antigravity returned a result before init")
            if result is not None:
                raise ImmediateEngineError("Antigravity returned duplicate result events")
            result = event.get("result")
            if not isinstance(result, dict):
                raise ImmediateEngineError("Antigravity returned an invalid result event")

    if not saw_init:
        raise ImmediateEngineError("Antigravity stream did not provide an init event")
    if result is None:
        raise ImmediateEngineError("Antigravity stream did not provide a result")
    status = result.get("status")
    if str(status).upper() != "SUCCESS":
        error = result.get("error")
        if error:
            error_text = error if isinstance(error, str) else json.dumps(error)
            raise ImmediateEngineError(_antigravity_exit_message(error_text))
        raise ImmediateEngineError("Antigravity returned an unsuccessful result")
    structured_output = result.get("structured_output")
    if not isinstance(structured_output, dict):
        raise ImmediateEngineError("Antigravity result has no structured output")
    return json.dumps(structured_output, ensure_ascii=False)
