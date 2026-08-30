"""Application command-line entry point."""

import argparse
from pathlib import Path

import dotenv
from maikol_utils.other_utils import args_to_dataclass
from scripts import generate_rm
from src.config import Configuration
from src.models import PRIORITY_CHOICES



def cmd_generate_rm(args: argparse.Namespace) -> int:
    """Generate a Reward Machine from parsed CLI configuration."""
    config: Configuration = args_to_dataclass(args, Configuration)
    return generate_rm(config)


# ======================================================================================
#                                       ARGUMENTS
# ======================================================================================
if __name__ == "__main__":
    dotenv.load_dotenv()

    parser = argparse.ArgumentParser(
        prog="schema-rm-rl",
        description="Compile reviewed instructions into Reward Machines",
        epilog=f"generate-rm --priority options: {', '.join(PRIORITY_CHOICES)}",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")

    subparsers = parser.add_subparsers(dest="function", required=True)

    # ======================================================================================
    #                                       generate-rm
    # ======================================================================================
    generate_parser = subparsers.add_parser(
        "generate-rm",
        help="Generate Reward Machines",
    )
    generate_parser.add_argument("--environment", required=True, type=Path)
    generate_parser.add_argument(
        "--instruction",
        dest="instructions",
        action="append",
        required=True,
        help="Natural-language instruction; repeat for multiple instructions",
    )
    generate_parser.add_argument(
        "--model",
        help="LLM model (defaults to the selected provider's model variable)",
    )
    generate_parser.add_argument(
        "--priority",
        dest="priorities",
        action="append",
        choices=PRIORITY_CHOICES,
        help=(
            "Instruction priority; repeat once per instruction when used "
            "(default: infer each priority)"
        ),
    )
    generate_parser.add_argument("--output", required=True, type=Path)
    generate_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing an existing output file",
    )
    generate_parser.set_defaults(func=cmd_generate_rm)


    # ======================================================================================
    #                                       CALL
    # ======================================================================================
    args = parser.parse_args()
    raise SystemExit(args.func(args))
