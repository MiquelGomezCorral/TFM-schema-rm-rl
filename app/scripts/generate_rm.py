"""Generate a Reward Machine from reviewed natural-language instructions."""

from pathlib import Path

from src.compiler import (
    CompilationResult,
    compile_approved_proposals,
    propose_instructions,
)
from src.config import Configuration
from src.engines import (
    OpenAIEngine,
    OpenCodeEngine,
    ProposalValidationError,
)
from src.models import EnvironmentDescription

from maikol_utils.print_utils import print_color, print_error, print_separator


def generate_rm(CONFIG: Configuration) -> int:
    """Propose, review, compile, and write one RM per instruction."""
    print_separator("START REWARD MACHINE GENERATION", sep_type="START")
    try:
        try:
            return _run_pipeline(CONFIG)
        except ProposalValidationError as error:
            print_error(f"Proposal generation failed: {error}")
            return 1
    finally:
        print_separator("END REWARD MACHINE GENERATION", sep_type="END")


def _run_pipeline(CONFIG: Configuration) -> int:
    """Run the generation phases inside the command separator boundary."""
    print_separator("OUTPUT SETUP", sep_type="LONG")
    if CONFIG.environment is None:
        raise ValueError("An environment file is required")
    if CONFIG.output is None:
        raise ValueError("An output file is required")
    if not CONFIG.instructions:
        raise ValueError("At least one instruction is required")
    output_paths = _derive_output_paths(CONFIG)
    print_color(
        f"Output setup complete for {len(CONFIG.instructions)} instruction(s).",
        color="green",
    )
    for output_path in output_paths:
        print_color(f" - Output path: {output_path}", color="green")

    print_separator("ENVIRONMENT AND ENGINE SETUP", sep_type="LONG")
    print(f" - Loading environment from {CONFIG.environment}...")
    environment = EnvironmentDescription.from_file(CONFIG.environment)
    print(f" - Using LLM engine for provider '{CONFIG.llm_provider}'...")
    engine = _get_engine(CONFIG, environment)
    print_color("Environment and engine setup complete.", color="green")

    print_separator("PROPOSAL GENERATION", sep_type="LONG")
    priority_overrides = tuple(CONFIG.priorities)
    if not priority_overrides:
        priority_overrides = ("infer",) * len(CONFIG.instructions)
    proposals = []
    for index, (instruction, priority_override) in enumerate(
        zip(CONFIG.instructions, priority_overrides, strict=True),
        start=1,
    ):
        print_separator(f"PROPOSAL {index}", sep_type="NORMAL")
        print(f"Instruction: {instruction}")
        proposal = propose_instructions(
            environment,
            (instruction,),
            engine,
            (priority_override,),
        )[0]
        proposals.append(proposal)
        print_color(f"Proposal {index} generated successfully.", color="green")
    proposals = tuple(proposals)
    print_color("Proposal generation complete.", color="green")

    print_separator("PROPOSAL REVIEW", sep_type="LONG")
    for index, proposal in enumerate(proposals, start=1):
        print_separator(f"REVIEW {index}", sep_type="NORMAL")
        print(f"Instruction: {proposal.instruction}")
        print(f" - Pattern: {proposal.pattern}")
        print(f" - Propositions: {', '.join(proposal.propositions)}")
        print(f" - Priority: {proposal.priority.value}")
        print(f" - LTLf: {proposal.ltlf_formula}")
        print(f" - Reward behavior: {proposal.reward_behavior}")
    print_color("Proposal review complete.", color="green")
    confirmation = input("\nApprove these proposals and compile the Reward Machines? [y/N] ")
    if confirmation.strip().lower() not in {"y", "yes"}:
        print("Compilation declined; no Reward Machine was written.")
        return 0

    print_separator("COMPILATION", sep_type="LONG")
    results = []
    for index, proposal in enumerate(proposals, start=1):
        print_separator(f"COMPILATION {index}", sep_type="NORMAL")
        compiled = compile_approved_proposals(
            environment,
            (proposal,),
            mona_executable=CONFIG.mona_executable or "mona",
        )
        results.extend(compiled)
        print_color(
            f"Compiled instruction {index}: {proposal.instruction}",
            color="green",
        )
    results = tuple(results)
    print_color("All approved proposals compiled successfully.", color="green")

    print_separator("WRITING OUTPUTS", sep_type="LONG")
    _save_results(results, output_paths, overwrite=CONFIG.overwrite)
    print_color("Writing outputs complete.", color="green")
    print_color("Reward Machine generation completed successfully.", color="green")

    return 0


def _derive_output_paths(CONFIG: Configuration) -> tuple[Path, ...]:
    if CONFIG.output is None:
        raise ValueError("An output file name is required")

    if len(CONFIG.instructions) == 1:
        output_names = (CONFIG.output,)
    else:
        output_names = tuple(
            CONFIG.output.with_name(
                f"{CONFIG.output.stem}-{index}{CONFIG.output.suffix}"
            )
            for index in range(1, len(CONFIG.instructions) + 1)
        )

    output_paths = tuple(CONFIG.OUTPUT_PATH / name for name in output_names)

    existing_paths = [path for path in output_paths if path.exists()]
    if existing_paths and not CONFIG.overwrite:
        raise ValueError(
            "Output file(s) already exist; pass --overwrite to replace them: "
            + ", ".join(str(path) for path in existing_paths)
        )
    
    return output_paths


def _get_engine(CONFIG: Configuration, environment: EnvironmentDescription) -> OpenAIEngine | OpenCodeEngine:
    if CONFIG.llm_provider == "opencode":
        engine = OpenCodeEngine(
            environment,
            model=CONFIG.model,
            api_key=CONFIG.api_key,
            base_url=CONFIG.base_url,
        )
    else:
        engine = OpenAIEngine(
            environment,
            model=CONFIG.model,
            api_key=CONFIG.api_key,
        )

    return engine

def _save_results(
    results: tuple[CompilationResult, ...],
    output_paths: tuple[Path, ...],
    overwrite: bool,
) -> None:
    mode = "w" if overwrite else "x"
    for output_path, result in zip(output_paths, results, strict=True):
        try:
            with output_path.open(mode, encoding="utf-8") as output_file:
                output_file.write(result.text)
        except FileExistsError as error:
            raise ValueError(
                f"Output file '{output_path}' already exists; pass --overwrite to replace it"
            ) from error
        except OSError as error:
            raise ValueError(f"Could not write output file '{output_path}': {error}") from error
        print_color(f" - Reward Machine written to {output_path}", color="green")
