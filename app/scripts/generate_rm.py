"""Generate one Reward Machine per critic-validated natural-language task."""

import json
from collections.abc import Sequence
from dataclasses import asdict, replace
from pathlib import Path

from src.compiler import (
    CompilationResult,
    Proposal,
    build_compilation_result,
    compile_dfas,
    materialize_proposal,
)
from src.config import Configuration
from src.engines import (
    GenericEngine,
    ImmediateEngineError,
    ProposalValidationError,
    RetryableEngineError,
    ProposalSelection
)
from src.models import EnvironmentDescription
from src.utils import (
    GenerationHooks,
    PipelineStep,
    Progress,
    StepState,
    record_attempt_failure,
    append_history,
    validate_configuration,
    proposal_json,
    structure_history_text,
    setup_environment_and_engines,
    derive_output_paths,
    save_results,
    attach_step_trace,
)

# One compiled candidate allows at most this many tagging requests; exhaustion stops the run.
TAGGING_ATTEMPTS = 3

# One accepted candidate allows at most this many labeling requests; exhaustion stops the run.
LABELING_ATTEMPTS = 3

# ============================================================================
#
#                                   PIPELINE
#
# ============================================================================

def generate_rm(
    CONFIG: Configuration,
    hooks: GenerationHooks | None = None,
    *,
    write_outputs: bool = True,
) -> int:
    """Propose, review, compile, and write one RM per task."""
    hooks = attach_step_trace(CONFIG, hooks or GenerationHooks())
    progress = Progress(hooks, CONFIG.LOGS_PATH)
    try:
        if progress.log_path is not None:
            hooks.notify_run_started(progress.log_path)
            progress(f"Run log: {progress.log_path}")

        return _run_pipeline(CONFIG, hooks, progress, write_outputs=write_outputs)

    except (ProposalValidationError, RetryableEngineError, ImmediateEngineError) as error:
        progress(f"Generation failed: {error}")
        hooks.notify_failure(str(error))
        return 1
    except Exception as error:
        progress(f"Generation failed unexpectedly: {error}")
        raise
    finally:
        progress.close()


def _run_pipeline(
    CONFIG: Configuration,
    hooks: GenerationHooks,
    progress: Progress,
    *,
    write_outputs: bool = True,
) -> int:
    """Run every task through at most three proposal attempts."""
    output_paths = _prepare_outputs(CONFIG, progress)
    environment, generator_engine, critic_engine = setup_environment_and_engines(CONFIG, progress)
    labeling_api = _labeling_api(CONFIG) if CONFIG.labeling else ""
    accepted: list[CompilationResult] = []

    for task_index, task in enumerate(CONFIG.tasks):
        history: list[dict[str, object]] = []
        result: CompilationResult | None = None

        for attempt in range(1, 4):
            proposal_text: str | None = None
            compiled: CompilationResult | None = None
            try:
                # ====== pipeline =======

                selections, proposal_text = _step_generate_proposal(
                    task, generator_engine, history, progress, task_index, attempt
                )
                if not _step_task_critic(
                    CONFIG.task_critic, critic_engine, task, proposal_text, history,
                    progress, task_index, attempt,
                ):
                    continue

                proposal = _step_materialize_ltlf(
                    environment, task, selections, progress, task_index, attempt
                )
                dfas = _step_compile_dfa(
                    CONFIG, proposal, progress, task_index, attempt
                )
                compiled = _step_build_reward_machine(
                    environment, proposal, dfas, progress, task_index, attempt
                )
                compiled = _step_describe_states(
                    generator_engine, task, compiled, progress, task_index, attempt
                )
                if not _step_rm_critic(
                    CONFIG.rm_critic, critic_engine, task, proposal_text, compiled, history,
                    progress, task_index, attempt,
                ):
                    continue
                compiled = _step_generate_labeling(
                    CONFIG, generator_engine, critic_engine, task, compiled, labeling_api,
                    progress, task_index, attempt,
                )
                compiled = _step_embeddings(CONFIG, compiled, progress, task_index, attempt)

            # ====== Exception handling =======
            except (RetryableEngineError, ValueError) as error:
                record_attempt_failure(
                    progress, history, proposal_text, compiled, task_index, attempt,
                    error,
                    "retryable failure" if isinstance(error, RetryableEngineError)
                    else "rejected",
                )
                continue
            except ImmediateEngineError as error:
                progress.fail(task_index, attempt, str(error))
                raise
            except (FileNotFoundError, RuntimeError) as error:
                progress.fail(task_index, attempt, str(error))
                raise ImmediateEngineError(str(error)) from error

            # ====== Results handling =======

            result = compiled
            progress(f"Task {task_index + 1}: attempt {attempt}/3 accepted.")
            break

        if result is None:
            last_failure = history[-1]
            raise RetryableEngineError(
                f"Task {task_index + 1} was not accepted within 3 attempts. "
                f"Last {last_failure['source']} feedback: {last_failure['feedback']}"
            )
        accepted.append(result)

    # ====== Results handling =======

    progress("Writing Reward Machine outputs.")
    results = tuple(accepted)
    if write_outputs:
        if CONFIG.labeling:
            _preflight_labeling_bundles(CONFIG, output_paths)
        if CONFIG.embeddings:
            preflight_embedding_artifacts(
                [
                    embedding_artifact_path(CONFIG, output_path.stem)
                    for output_path in output_paths
                ],
                overwrite=CONFIG.overwrite,
            )
        save_results(results, output_paths, overwrite=CONFIG.overwrite)
        if CONFIG.labeling:
            bundle_paths = _write_labeling_bundles(
                results, output_paths, CONFIG, labeling_api, progress,
            )
            results = tuple(
                replace(result, bundle_path=path)
                for result, path in zip(results, bundle_paths, strict=True)
            )
        if CONFIG.embeddings:
            embedding_paths = _write_embedding_artifacts(
                results, output_paths, CONFIG, progress,
            )
            results = tuple(
                replace(result, embedding_path=path)
                for result, path in zip(results, embedding_paths, strict=True)
            )
        if CONFIG.svg:
            _write_svgs(results, output_paths, CONFIG, progress)

    progress("Writing outputs complete.")
    hooks.notify_completion(results, output_paths)

    progress("Generation completed successfully.")
    return 0

# ============================================================================
#
#                                  SVG OUTPUT
#
# ============================================================================

def _write_svgs(
    results: tuple[CompilationResult, ...],
    output_paths: tuple[Path, ...],
    CONFIG: Configuration,
    progress: Progress,
) -> None:
    """Write one SVG graph per accepted Reward Machine beside the requested outputs."""
    from .render_rm import render_structure_svg

    directory = CONFIG.svg_dir or CONFIG.OUTPUT_PATH / "svgs"
    directory.mkdir(parents=True, exist_ok=True)
    mode = "w" if CONFIG.overwrite else "x"
    for output_path, result in zip(output_paths, results, strict=True):
        svg_path = directory / f"{output_path.stem}.svg"
        try:
            with svg_path.open(mode, encoding="utf-8") as svg_file:
                svg_file.write(render_structure_svg(result.reward_machine))
        except FileExistsError as error:
            raise ValueError(
                f"SVG file '{svg_path}' already exists; pass --overwrite to replace it"
            ) from error
        except OSError as error:
            raise ValueError(f"Could not write SVG file '{svg_path}': {error}") from error
        progress(f"SVG graph: {svg_path}")


# ============================================================================
#
#                              LABELING BUNDLES
#
# ============================================================================

def _labeling_bundle_paths(
    CONFIG: Configuration,
    output_paths: tuple[Path, ...],
) -> tuple[Path, ...]:
    """Return one bundle directory per accepted task output, reusing its stem."""
    return tuple(CONFIG.OUTPUT_PATH / "bundles" / output_path.stem for output_path in output_paths)


def _preflight_labeling_bundles(CONFIG: Configuration, output_paths: tuple[Path, ...]) -> None:
    """Reject occupied bundle destinations before any final output is written."""
    occupied = [
        path for path in _labeling_bundle_paths(CONFIG, output_paths)
        if path.exists() and any(path.iterdir())
    ]
    if occupied and not CONFIG.overwrite:
        raise ValueError(
            "Labeling bundle(s) already exist; pass --overwrite to replace them: "
            + ", ".join(str(path) for path in occupied)
        )


def _write_labeling_bundles(
    results: tuple[CompilationResult, ...],
    output_paths: tuple[Path, ...],
    CONFIG: Configuration,
    api_description: str,
    progress: Progress,
) -> tuple[Path, ...]:
    """Persist one reuse bundle per accepted task and return their directories."""
    from src.arm_fm.generation import (
        StageAttempt,
        build_compiler_bundle,
        pair_state_descriptions,
        record_bundle_embeddings,
        record_bundle_role_models,
    )

    written = []
    bundle_paths = _labeling_bundle_paths(CONFIG, output_paths)
    for result, bundle_path, output_path in zip(results, bundle_paths, output_paths, strict=True):
        bundle = build_compiler_bundle(
            result,
            api_description=api_description,
            labeling_source=result.labeling_source,
            state_descriptions=pair_state_descriptions(result, result.state_descriptions),
            attempts=[StageAttempt(**item) for item in result.labeling_attempts],
        )
        record_bundle_role_models(bundle, CONFIG)
        if CONFIG.embeddings:
            record_bundle_embeddings(
                bundle, result, embedding_artifact_path(CONFIG, output_path.stem)
            )
        try:
            bundle.save(bundle_path, overwrite=CONFIG.overwrite)
        except OSError as error:
            raise ValueError(f"Could not write labeling bundle '{bundle_path}': {error}") from error
        progress(f"Labeling bundle: {bundle_path}")
        written.append(bundle_path)
    return tuple(written)


# ============================================================================
#
#                               EMBEDDING ARTIFACTS
#
# ============================================================================

def embedding_artifact_path(CONFIG: Configuration, stem: str) -> Path:
    """Return the persisted node-embedding artifact path for one task stem."""
    return Path(CONFIG.EMBEDDINGS_PATH) / stem / "embeddings.json"


def preflight_embedding_artifacts(
    destinations: Sequence[Path],
    *,
    overwrite: bool,
) -> None:
    """Reject occupied embedding destinations before any final output is written."""
    occupied = [path for path in destinations if path.exists()]
    if occupied and not overwrite:
        raise ValueError(
            "Embedding artifact(s) already exist; pass --overwrite to replace them: "
            + ", ".join(str(path) for path in occupied)
        )


def write_embedding_artifact(
    result: CompilationResult,
    destination: Path,
    *,
    context: str,
) -> None:
    """Write one accepted task's node vectors, effective texts, and settings as JSON."""
    from src.arm_fm.generation import pair_state_descriptions

    payload = {
        "task": result.proposal.task,
        "environment": str(result.environment.source),
        "reward_machine": result.text,
        "proposition_semantics": {
            item.identifier: item.description for item in result.environment.propositions
        },
        "nodes": list(result.embeddings),
        "embeddings": result.embeddings,
        "descriptions": pair_state_descriptions(result, result.state_descriptions),
        "effective_texts": result.embedding_texts,
        "context": context,
        "settings": dict(result.embedding_settings),
    }
    serialized = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(serialized, encoding="utf-8")
    except OSError as error:
        raise ValueError(f"Could not write embedding artifact '{destination}': {error}") from error


def _write_embedding_artifacts(
    results: tuple[CompilationResult, ...],
    output_paths: tuple[Path, ...],
    CONFIG: Configuration,
    progress: Progress,
) -> tuple[Path, ...]:
    """Persist one embedding artifact per accepted task and return their paths."""
    written = []
    for result, output_path in zip(results, output_paths, strict=True):
        destination = embedding_artifact_path(CONFIG, output_path.stem)
        write_embedding_artifact(result, destination, context=CONFIG.embedding_context)
        progress(f"State embeddings: {destination}")
        written.append(destination)
    return tuple(written)


# ============================================================================
#
#                                   STEPS
#
# ============================================================================
def _prepare_outputs(CONFIG: Configuration, progress: Progress) -> tuple[Path, ...]:
    progress("Validating output configuration.")

    validate_configuration(CONFIG)
    output_paths = derive_output_paths(CONFIG)

    for output_path in output_paths:
        progress(f"Output path: {output_path}")
    progress(f"Output setup complete for {len(CONFIG.tasks)} task(s).")

    return output_paths


def _labeling_api(CONFIG: Configuration) -> str:
    """Resolve the MiniGrid labeling API, rejecting unrecognized explicit domains."""
    from src.arm_fm.environments import labeling_api_for_domain

    domain = (CONFIG.domain or "minigrid").strip().lower()
    families = ("minigrid", "babyai")
    recognized = any(
        domain == family
        or domain.startswith(f"{family}-")
        or domain.startswith(f"{family}_")
        for family in families
    )
    if not recognized:
        raise ValueError(
            "Compiler labeling supports the MiniGrid and BabyAI domain families only, "
            f"got {CONFIG.domain!r}"
        )
    return labeling_api_for_domain(domain)


def _step_generate_proposal(
    task: str,
    engine: GenericEngine,
    history: list[dict[str, object]],
    progress: Progress,
    task_index: int,
    attempt: int,
) -> tuple[tuple[ProposalSelection, ...], str]:
    """Generate and log validated proposal selections."""
    progress.start(task_index, attempt, PipelineStep.GENERATE)

    history_text = structure_history_text(history)
    selections = engine.propose_task(task, history=history_text)
    proposal_text = proposal_json(selections, task)

    progress.artifact("Validated proposal", proposal_text)
    progress.complete(task_index, attempt)

    return selections, proposal_text


def _step_task_critic(
    enabled: bool,
    engine: GenericEngine | None,
    task: str,
    proposal_text: str,
    history: list[dict[str, object]],
    progress: Progress,
    task_index: int,
    attempt: int,
) -> bool:
    if not enabled:
        progress.stage_skip(task_index, attempt, PipelineStep.TASK_CRITIC)
        return True
    progress.start(task_index, attempt, PipelineStep.TASK_CRITIC)


    critic = engine.review_task(task, proposal_text)


    progress.artifact(
        "Task critic verdict",
        {"accepted": critic.accepted, "feedback": critic.feedback},
    )
    if critic.accepted:
        progress.complete(task_index, attempt, StepState.COMPLETED)
    else:
        progress.complete(task_index, attempt, StepState.FAILED, critic.feedback)
        append_history(history, proposal_text, None, PipelineStep.TASK_CRITIC, critic.feedback)
        
    return critic.accepted
    

def _step_materialize_ltlf(
    environment: EnvironmentDescription,
    task: str,
    selections: Sequence[ProposalSelection],
    progress: Progress,
    task_index: int,
    attempt: int,
) -> Proposal:
    progress.start(task_index, attempt, PipelineStep.LTLF)

    proposal = materialize_proposal(environment, task, selections)

    progress.artifact(
        "LTLf clauses",
        [
            {
                "normalized_clause": clause.normalized_clause,
                "formula": clause.ltlf_formula,
            }
            for clause in proposal.clauses
        ],
    )
    progress.complete(task_index, attempt)
    return proposal


def _step_compile_dfa(
    CONFIG: Configuration,
    proposal: Proposal,
    progress: Progress,
    task_index: int,
    attempt: int,
) -> tuple[dict, ...]:
    progress.start(task_index, attempt, PipelineStep.DFA)

    dfas = compile_dfas(
        proposal, mona_executable=CONFIG.mona_executable or "mona"
    )

    progress.artifact("DFA data", dfas)
    progress.complete(task_index, attempt)
    return dfas


def _step_build_reward_machine(
    environment: EnvironmentDescription,
    proposal: Proposal,
    dfas: Sequence[dict],
    progress: Progress,
    task_index: int,
    attempt: int,
) -> CompilationResult:
    progress.start(task_index, attempt, PipelineStep.REWARD_MACHINE)
    
    compiled = build_compilation_result(environment, proposal, dfas)

    progress.artifact("Serialized Reward Machine", compiled.text)
    progress.complete(task_index, attempt)
    return compiled


def _step_describe_states(
    engine: GenericEngine,
    task: str,
    compiled: CompilationResult,
    progress: Progress,
    task_index: int,
    attempt: int,
) -> CompilationResult:
    """Tag every machine state, retrying malformed or transient responses locally."""
    progress.start(task_index, attempt, PipelineStep.STATE_DESCRIPTIONS)

    identifiers = _state_identifiers(compiled)
    nodes = tuple(identifiers.values())
    clauses_json = _clauses_json(compiled)
    rejecting_states_json = json.dumps(
        [identifiers[state] for state in compiled.reward_machine.rejecting_states]
    )

    last_error: Exception | None = None
    for tagging_attempt in range(1, TAGGING_ATTEMPTS + 1):
        try:
            descriptions = engine.describe_states(
                task, clauses_json, compiled.text, rejecting_states_json, nodes
            )
        except RetryableEngineError as error:
            last_error = error
            progress(
                f"Task {task_index + 1}: state tagging attempt "
                f"{tagging_attempt}/{TAGGING_ATTEMPTS} failed — {error}"
            )
            continue

        progress.artifact(
            "State descriptions",
            dict(zip(nodes, descriptions, strict=True)),
        )
        progress.complete(task_index, attempt)
        return replace(compiled, state_descriptions=descriptions)

    raise ImmediateEngineError(
        f"State-description tagging failed after {TAGGING_ATTEMPTS} requests: {last_error}"
    )


def _step_generate_labeling(
    CONFIG: Configuration,
    generator_engine: GenericEngine,
    critic_engine: GenericEngine | None,
    task: str,
    compiled: CompilationResult,
    api_description: str,
    progress: Progress,
    task_index: int,
    attempt: int,
) -> CompilationResult:
    """Generate MiniGrid predicates for one accepted RM, retrying locally."""
    if not CONFIG.labeling:
        progress.stage_skip(task_index, attempt, PipelineStep.LABELING)
        return compiled
    progress.start(task_index, attempt, PipelineStep.LABELING)

    from src.arm_fm.generation import StageAttempt, generate_labeling

    identifiers = _state_identifiers(compiled)
    context = {
        "clauses_json": _clauses_json(compiled),
        "state_descriptions_json": _descriptions_json(compiled),
        "nodes_json": json.dumps(list(identifiers.values())),
        "propositions_json": json.dumps(
            {item.identifier: item.description for item in compiled.environment.propositions},
            indent=2,
            sort_keys=True,
        ),
    }
    attempts: list[StageAttempt] = []
    try:
        source = generate_labeling(
            task,
            compiled.environment,
            compiled.text,
            generator_engine,
            api_description,
            LABELING_ATTEMPTS,
            attempts,
            critic_engine=critic_engine,
            critic_enabled=CONFIG.rm_critic,
            compiler_context=context,
        )
    except RuntimeError as error:
        last = attempts[-1] if attempts else None
        detail = (last.feedback or last.error) if last is not None else str(error)
        raise ImmediateEngineError(
            f"Labeling generation failed after {LABELING_ATTEMPTS} requests: {detail or error}"
        ) from error

    progress.artifact("Labeling source", source)
    progress.complete(task_index, attempt)
    return replace(
        compiled,
        labeling_source=source,
        labeling_attempts=tuple(item.__dict__ for item in attempts),
    )


def _step_embeddings(
    CONFIG: Configuration,
    compiled: CompilationResult,
    progress: Progress,
    task_index: int,
    attempt: int,
) -> CompilationResult:
    """Embed the accepted state descriptions through the configured local server."""
    if not CONFIG.embeddings:
        progress.stage_skip(task_index, attempt, PipelineStep.EMBEDDINGS)
        return compiled
    progress.start(task_index, attempt, PipelineStep.EMBEDDINGS)

    from src.arm_fm.evaluation import (
        SERVER_EMBEDDING_EXTRACTION,
        EmbeddingCache,
        EmbeddingSettings,
        effective_embedding_text,
        embed_descriptions_over_http,
    )
    from src.arm_fm.generation import pair_state_descriptions

    descriptions = pair_state_descriptions(compiled, compiled.state_descriptions)
    if not descriptions:
        raise ImmediateEngineError("Embedding stage requires accepted state descriptions")
    settings = EmbeddingSettings(
        model=CONFIG.embedding_model,
        model_revision=CONFIG.embedding_revision,
        tokenizer_revision=CONFIG.embedding_revision,
        extraction=SERVER_EMBEDDING_EXTRACTION,
        normalize=True,
        device="remote",
    )
    cache = EmbeddingCache(Path(CONFIG.EMBEDDINGS_PATH) / "cache.json")
    try:
        vectors = embed_descriptions_over_http(
            descriptions,
            endpoint=CONFIG.embedding_endpoint,
            settings=settings,
            cache=cache,
            context=CONFIG.embedding_context,
            timeout=CONFIG.embedding_timeout,
        )
    except (RuntimeError, ValueError, OSError) as error:
        raise ImmediateEngineError(f"Embedding stage failed: {error}") from error

    dimension = len(next(iter(vectors.values())))
    progress.artifact(
        "State embeddings",
        {
            "model": settings.model,
            "revision": settings.model_revision,
            "extraction": settings.extraction,
            "dimension": dimension,
            "context": CONFIG.embedding_context,
            "nodes": list(vectors),
        },
    )
    progress.complete(task_index, attempt)
    return replace(
        compiled,
        embeddings=vectors,
        embedding_settings={
            **asdict(settings),
            "dimension": dimension,
            "context": CONFIG.embedding_context,
            "endpoint": CONFIG.embedding_endpoint,
        },
        embedding_texts={
            node: effective_embedding_text(CONFIG.embedding_context, text)
            for node, text in descriptions.items()
        },
    )


def _state_identifiers(compiled: CompilationResult) -> dict[int, str]:
    """Map each numeric compiler state to its shared ARM-FM identity."""
    # Deferred: keeps this module's import free of the ARM-FM package, mirroring
    # serialize_reward_machine, which loads the adapter through the same deferred import.
    from src.arm_fm.runtime import compiler_machine_to_paper

    machine = compiler_machine_to_paper(
        compiled.reward_machine, compiled.environment.proposition_ids
    )
    return dict(zip(compiled.reward_machine.states, machine.states, strict=True))


def _clauses_json(compiled: CompilationResult) -> str:
    """Serialize validated clauses for the tagging and labeling prompts."""
    return json.dumps(
        [
            {
                "normalized_clause": clause.normalized_clause,
                "pattern": clause.pattern,
                "propositions": list(clause.propositions),
                "priority": clause.priority.value,
            }
            for clause in compiled.proposal.clauses
        ],
        indent=2,
        sort_keys=True,
    )


def _descriptions_json(compiled: CompilationResult) -> str:
    """Pair one candidate's descriptions with the shared node identities."""
    # Deferred: keeps this module's import free of the ARM-FM package, mirroring
    # serialize_reward_machine, which loads the adapter through the same deferred import.
    from src.arm_fm.generation import pair_state_descriptions

    # Keep the adapter's node order (u0, u1, ... u10), which the reviewer prompt
    # promises as a node-ordered mapping; sorting keys would put u10 before u2.
    return json.dumps(
        pair_state_descriptions(compiled, compiled.state_descriptions),
        indent=2,
    )


def _step_rm_critic(
    enabled: bool,
    engine: GenericEngine | None,
    task: str,
    proposal_text: str,
    compiled: CompilationResult,
    history: list[dict[str, object]],
    progress: Progress,
    task_index: int,
    attempt: int,
) -> bool:
    if not enabled:
        progress.stage_skip(task_index, attempt, PipelineStep.RM_CRITIC)
        return True
    progress.start(task_index, attempt, PipelineStep.RM_CRITIC)


    critic = engine.review_reward_machine(
        task, compiled.text, _descriptions_json(compiled)
    )

    
    progress.artifact(
        "Reward Machine critic verdict",
        {"accepted": critic.accepted, "feedback": critic.feedback},
    )
    if critic.accepted:
        progress.complete(task_index, attempt, StepState.COMPLETED)
    else:
        progress.complete(task_index, attempt, StepState.FAILED, critic.feedback)
        append_history(history, proposal_text, compiled, PipelineStep.RM_CRITIC, critic.feedback)
        
    return critic.accepted
