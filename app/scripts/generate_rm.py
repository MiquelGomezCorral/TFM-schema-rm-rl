"""Generate a Reward Machine from reviewed natural-language instructions."""

from pathlib import Path

from src.compiler import compile_approved_proposals, propose_instructions
from src.config import Configuration
from src.engines import OpenAIEngine, OpenCodeEngine
from src.models import EnvironmentDescription

from maikol_utils.print_utils import print_separator, print_color


def generate_rm(CONFIG: Configuration) -> int:
    """Propose, review, compile, and write one RM per instruction."""
    if CONFIG.environment is None:
        raise ValueError("An environment file is required")
    if CONFIG.output is None:
        raise ValueError("An output file is required")
    if not CONFIG.instructions:
        raise ValueError("At least one instruction is required")


    # =====================================================================================
    #                                       OUTPUT FILES
    # =====================================================================================
    print(f" - Generating Reward Machines for {len(CONFIG.instructions)} instruction(s)...")
    
    output_paths = _derive_output_paths(CONFIG)

    # =====================================================================================
    #                                        ENV & ENGINE
    # =====================================================================================
    print(f" - Loading environment from {CONFIG.environment}...")
    environment = EnvironmentDescription.from_file(CONFIG.environment)

    print(f" - Using LLM engine for provider '{CONFIG.llm_provider}'...")
    engine = _get_engine(CONFIG, environment)

    proposals = propose_instructions(
        environment,
        CONFIG.instructions,
        engine,
        CONFIG.priorities,
    )

    # =====================================================================================
    #                                       REVIEW
    # =====================================================================================
    print_separator("Review proposed Reward Machine constraints:")
    for index, proposal in enumerate(proposals, start=1):
        print(f"\n[{index}] Instruction: {proposal.instruction}")
        print(f" - Pattern: {proposal.pattern}")
        print(f" - Propositions: {', '.join(proposal.propositions)}")
        print(f" - Priority: {proposal.priority.value}")
        print(f" - LTLf: {proposal.ltlf_formula}")
        print(f" - Reward behavior: {proposal.reward_behavior}")

    print_color("\nReview complete. If you approve, the Reward Machines will be compiled and written to the output file(s).", color="cyan")
    confirmation = input("\nApprove these proposals and compile the Reward Machines? [y/N] ")
    if confirmation.strip().lower() not in {"y", "yes"}:
        print("Compilation declined; no Reward Machine was written.")
        return 0

    # =====================================================================================
    #                                       COMPILE & WRITE
    # =====================================================================================
    results = compile_approved_proposals(
        environment,
        proposals,
        mona_executable=CONFIG.mona_executable or "mona",
    )
    _save_results(results, output_paths, overwrite=CONFIG.overwrite)

    return 0


# =====================================================================================
#                                     HELPERS
# =====================================================================================

def _derive_output_paths(CONFIG: Configuration) -> tuple[Path, ...]:
    if len(CONFIG.instructions) == 1:
        return (CONFIG.output,)
    
    output_paths = tuple(
        CONFIG.output.with_name(f"{CONFIG.output.stem}-{index}{CONFIG.output.suffix}")
        for index in range(1, len(CONFIG.instructions) + 1)
    )

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

def _save_results(results: list[tuple[str, str]], output_paths: tuple[Path, ...], overwrite: bool) -> None:
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
