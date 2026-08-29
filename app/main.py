"""Application command-line entry point."""

import argparse
from pathlib import Path

import dotenv
from maikol_utils.other_utils import args_to_dataclass
from scripts import generate_rm
from src.config import Configuration


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
        description="Compile reviewed instructions into a Reward Machine",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")

    subparsers = parser.add_subparsers(dest="function", required=True)

    # ======================================================================================
    #                                       generate-rm
    # ======================================================================================
    generate_parser = subparsers.add_parser(
        "generate-rm",
        help="Generate a Reward Machine",
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
        help="OpenAI model (defaults to OPENAI_MODEL)",
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
