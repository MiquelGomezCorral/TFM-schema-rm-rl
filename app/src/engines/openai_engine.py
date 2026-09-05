"""Shared workflow and OpenAI-compatible engine adapters."""

import os
from collections.abc import Callable
from functools import partial

from nl2ltl.engines import Engine
from openai import OpenAI
from pylogics.syntax.base import Formula

from src.models import EnvironmentDescription
from src.prompts import read_prompt, read_user_prompt

from .errors import classify_provider_error
from .structured import (
    CriticResult,
    ProposalSelection,
    completion_text,
    critic_schema,
    parse_critic,
    parse_proposal,
    proposal_schema,
    responses_text,
)

# ======================================================================================
#                                    SHARED WORKFLOW
# ======================================================================================

StructuredRequester = Callable[[str, str, str, dict, str], str]


class GenericEngine(Engine):
    """Shared proposal and critic workflow for structured-output providers."""

    def __init__(
        self,
        environment: EnvironmentDescription,
        model: str,
        provider_name: str,
        requester: StructuredRequester,
    ) -> None:
        self.environment = environment
        self.model = model
        self.provider_name = provider_name
        self._request = requester

    def translate(self, utterance: str, filtering=None) -> dict[Formula, float]:
        """Return IBM's formula-to-score shape with neutral selection scores."""
        if filtering is not None:
            raise ValueError(f"{type(self).__name__} does not support nl2ltl filters")
        return {selection.template: 1.0 for selection in self.propose(utterance)}

    def propose_task(
        self,
        task: str,
        history: str = "",
    ) -> tuple[ProposalSelection, ...]:
        """Request and validate one constrained proposal per task clause."""
        schema = proposal_schema(task, self.environment)
        response_text = self._request_structured(
            read_prompt("creator"),
            read_user_prompt(
                "creator",
                environment_markdown=self.environment.markdown,
                task=task,
                history=history,
            ),
            schema,
            "declare_proposal",
        )
        return parse_proposal(response_text, self.environment, self.provider_name)

    def propose(self, task: str) -> tuple[ProposalSelection, ...]:
        """Return the constrained proposal for one task."""
        return self.propose_task(task)

    def review_task(self, task: str, candidate_proposal: str) -> CriticResult:
        """Review a task interpretation before compilation."""
        response = self._request_structured(
            read_prompt("ltlf_reviewer"),
            read_user_prompt(
                "ltlf_reviewer",
                environment_markdown=self.environment.markdown,
                task=task,
                candidate_proposal=candidate_proposal,
            ),
            critic_schema(),
            "task_critic",
        )
        return parse_critic(response)

    def review_reward_machine(self, task: str, candidate_rm: str) -> CriticResult:
        """Review a serialized Reward Machine."""
        response = self._request_structured(
            read_prompt("rm_reviewer"),
            read_user_prompt(
                "rm_reviewer",
                environment_markdown=self.environment.markdown,
                task=task,
                candidate_rm=candidate_rm,
            ),
            critic_schema(),
            "rm_critic",
        )
        return parse_critic(response)

    def _request_structured(
        self,
        system: str,
        user: str,
        schema: dict,
        name: str,
    ) -> str:
        try:
            return self._request(self.model, system, user, schema, name)
        except Exception as error:
            raise classify_provider_error(error) from error


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
