"""Generate a Reward Machine from reviewed natural-language instructions."""

from src.compiler import compile_approved_proposals, propose_instructions
from src.config import Configuration
from src.engines import OpenAIEngine
from src.models import EnvironmentDescription


def generate_rm(CONFIG: Configuration) -> int:
    """Propose, review, confirm, compile, and write one Reward Machine."""
    if CONFIG.environment is None:
        raise ValueError("An environment file is required")
    if CONFIG.output is None:
        raise ValueError("An output file is required")
    if CONFIG.output.exists() and not CONFIG.overwrite:
        raise ValueError(
            f"Output file '{CONFIG.output}' already exists; pass --overwrite to replace it"
        )
    if not CONFIG.model:
        raise ValueError("An OpenAI model is required through --model or OPENAI_MODEL")
    if not CONFIG.api_key:
        raise ValueError("OPENAI_API_KEY is required")

    environment = EnvironmentDescription.from_file(CONFIG.environment)
    engine = OpenAIEngine(
        environment,
        model=CONFIG.model,
        api_key=CONFIG.api_key,
    )
    proposals = propose_instructions(environment, CONFIG.instructions, engine)

    print("Review proposed Reward Machine constraints:")
    for index, proposal in enumerate(proposals, start=1):
        print(f"\n[{index}] Instruction: {proposal.instruction}")
        print(f"    Pattern: {proposal.pattern}")
        print(f"    Propositions: {', '.join(proposal.propositions)}")
        print(f"    LTLf: {proposal.ltlf_formula}")
        print(f"    Reward: {proposal.reward}")

    confirmation = input("\nApprove these proposals and compile the Reward Machine? [y/N] ")
    if confirmation.strip().lower() not in {"y", "yes"}:
        print("Compilation declined; no Reward Machine was written.")
        return 0

    result = compile_approved_proposals(
        environment,
        proposals,
        mona_executable=CONFIG.mona_executable or "mona",
    )
    try:
        mode = "w" if CONFIG.overwrite else "x"
        with CONFIG.output.open(mode, encoding="utf-8") as output_file:
            output_file.write(result.text)
    except FileExistsError as error:
        raise ValueError(
            f"Output file '{CONFIG.output}' already exists; pass --overwrite to replace it"
        ) from error
    except OSError as error:
        raise ValueError(f"Could not write output file '{CONFIG.output}': {error}") from error
    print(f"Reward Machine written to {CONFIG.output}")
    return 0
