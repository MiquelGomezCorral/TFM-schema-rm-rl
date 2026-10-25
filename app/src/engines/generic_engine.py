"""Shared workflow for provider-backed structured-output engines."""

import json
from collections.abc import Callable, Sequence
from time import sleep

from openai import BadRequestError

from src.config import Configuration
from src.models import EnvironmentDescription
from src.prompts import read_prompt, render_prompt

from .errors import RetryableEngineError, RunCancelled, classify_provider_error
from .structured import (
    CriticResult,
    ProposalSelection,
    critic_schema,
    parse_critic,
    parse_proposal,
    parse_state_descriptions,
    proposal_schema,
)

# ======================================================================================
#                                    SHARED WORKFLOW
# ======================================================================================

StructuredRequester = Callable[[str, str, str, dict, str], str]
TextRequester = Callable[[str, str, str], str]


class GenericEngine:
    """Shared proposal and critic workflow for structured-output providers."""

    # Set by the pipeline so the provider retry loop stops when the client stops the run.
    should_stop: Callable[[], bool] | None = None
    # Set by the pipeline so an engine can report a run-wide change as a run warning.
    warn: Callable[[str], None] | None = None

    def __init__(
        self,
        environment: EnvironmentDescription,
        model: str,
        provider_name: str,
        requester: StructuredRequester,
        text_requester: TextRequester | None = None,
    ) -> None:
        self.environment = environment
        self.model = model
        self.provider_name = provider_name
        self._request = requester
        self._request_text = text_requester

    def request_text(self, system: str, user: str) -> str:
        """Request an unconstrained artifact while retaining provider error mapping."""
        if self._request_text is None:
            raise RuntimeError(f"{self.provider_name} does not provide text artifact requests")
        return self._call_provider(self._request_text, system, user)

    def propose_task(
        self,
        task: str,
        history: str = "",
    ) -> tuple[ProposalSelection, ...]:
        """Request and validate one constrained proposal per task clause."""
        schema = proposal_schema(task, self.environment)
        response_text = self._request_structured(
            read_prompt("compiler", "creator"),
            render_prompt(
                "compiler",
                "creator",
                environment_markdown=self.environment.markdown,
                task=task,
                history=history,
            ),
            schema,
            "declare_proposal",
        )
        return parse_proposal(response_text, self.environment, self.provider_name)

    def describe_states(
        self,
        task: str,
        clauses_json: str,
        candidate_rm: str,
        nodes: Sequence[str],
    ) -> tuple[str, ...]:
        """Request one validated description per ordered node identifier."""
        response_text = self.request_text(
            read_prompt("compiler", "rm_tagger"),
            render_prompt(
                "compiler",
                "rm_tagger",
                environment_markdown=self.environment.markdown,
                task=task,
                clauses_json=clauses_json,
                reward_machine=candidate_rm,
                nodes_json=json.dumps(list(nodes)),
            ),
        )
        return parse_state_descriptions(response_text, nodes)

    def review_candidate(
        self,
        task: str,
        clauses_json: str,
        candidate_rm: str,
        warnings: Sequence[str],
    ) -> CriticResult:
        """Review one compiled candidate: its clauses against the task, and the machine."""
        response = self._request_structured(
            read_prompt("compiler", "critic"),
            render_prompt(
                "compiler",
                "critic",
                environment_markdown=self.environment.markdown,
                task=task,
                clauses_json=clauses_json,
                reward_machine=candidate_rm,
                warnings="\n".join(f"- {warning}" for warning in warnings),
            ),
            critic_schema(),
            "critic",
        )
        return parse_critic(response)

    def review_labeling(
        self,
        task: str,
        candidate_rm: str,
        api: str,
        labeling: str,
        **context: str,
    ) -> CriticResult:
        """Review generated labeling predicates with the compiler's grounded context.

        ``context`` carries the prompt fields ``clauses_json``, ``state_descriptions_json``,
        ``nodes_json`` and ``propositions_json``; the prompt renderer rejects a missing one.
        """
        response = self._request_structured(
            read_prompt("compiler", "labeling_reviewer"),
            render_prompt(
                "compiler",
                "labeling_reviewer",
                environment_markdown=self.environment.markdown,
                task=task,
                reward_machine=candidate_rm,
                api=api,
                labeling=labeling,
                **context,
            ),
            critic_schema(),
            "labeling_critic",
        )
        return parse_critic(response)

    def _request_structured(
        self,
        system: str,
        user: str,
        schema: dict,
        name: str,
    ) -> str:
        return self._call_provider(self._request, system, user, schema, name)

    def _call_provider(self, request: Callable[..., str], *arguments: str | dict) -> str:
        """Call the provider and map its errors, repeating a transient HTTP 400 first.

        OpenCode answers some valid requests with a random HTTP 400 that sticks to the
        session: the same call succeeds on a new session. Each repeat starts a new session
        first. The repeats happen here, so they never use up a refinement attempt; a 400
        that survives every repeat is retryable like the other transient provider errors.
        """
        repeats = 0
        while True:
            try:
                return request(self.model, *arguments)
            except BadRequestError as error:
                repeats += 1
                if repeats > Configuration.PROVIDER_RETRIES:
                    raise RetryableEngineError(str(error)) from error
                self._check_stopped()
                self._renew_session()
                sleep(Configuration.PROVIDER_RETRY_WAIT_S)
            except Exception as error:
                raise classify_provider_error(error) from error

    def _check_stopped(self) -> None:
        """Abort the retry loop instead of retrying again once the run was stopped."""
        if self.should_stop is not None and self.should_stop():
            raise RunCancelled("Stopped by the user")

    def _renew_session(self) -> None:
        """Start a new provider session; a provider whose errors stick to one overrides this."""
