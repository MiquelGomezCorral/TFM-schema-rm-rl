"""Shared workflow for provider-backed structured-output engines."""

import json
from collections.abc import Callable, Sequence

from src.models import EnvironmentDescription
from src.prompts import read_prompt, render_prompt

from .errors import classify_provider_error
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
        try:
            return self._request_text(self.model, system, user)
        except Exception as error:
            raise classify_provider_error(error) from error

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

    def review_task(self, task: str, candidate_proposal: str) -> CriticResult:
        """Review a task interpretation before compilation."""
        response = self._request_structured(
            read_prompt("compiler", "ltlf_reviewer"),
            render_prompt(
                "compiler",
                "ltlf_reviewer",
                environment_markdown=self.environment.markdown,
                task=task,
                candidate_proposal=candidate_proposal,
            ),
            critic_schema(),
            "task_critic",
        )
        return parse_critic(response)

    def describe_states(
        self,
        task: str,
        clauses_json: str,
        candidate_rm: str,
        rejecting_states_json: str,
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
                rejecting_states_json=rejecting_states_json,
                nodes_json=json.dumps(list(nodes)),
            ),
        )
        return parse_state_descriptions(response_text, nodes)

    def review_reward_machine(
        self,
        task: str,
        candidate_rm: str,
        state_descriptions: str = "",
    ) -> CriticResult:
        """Review a serialized Reward Machine with its state descriptions as context."""
        response = self._request_structured(
            read_prompt("compiler", "rm_reviewer"),
            render_prompt(
                "compiler",
                "rm_reviewer",
                environment_markdown=self.environment.markdown,
                task=task,
                candidate_rm=candidate_rm,
                state_descriptions=state_descriptions,
            ),
            critic_schema(),
            "rm_critic",
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
        """Review generated MiniGrid predicates with the compiler's grounded context.

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
        try:
            return self._request(self.model, system, user, schema, name)
        except Exception as error:
            raise classify_provider_error(error) from error
