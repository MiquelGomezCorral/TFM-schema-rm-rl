"""Application command-line entry point."""

import argparse
from pathlib import Path

import dotenv
from maikol_utils.other_utils import args_to_dataclass

from scripts import (
    embed_larm,
    evaluate_larm,
    generate_larm,
    generate_rm,
    render_rm,
    train_rl,
)
from src.config import Configuration


def cmd_generate_rm(args: argparse.Namespace) -> None:
    """Generate a Reward Machine from parsed CLI configuration."""
    CONFIG: Configuration = args_to_dataclass(args, Configuration)
    generate_rm(CONFIG)


def cmd_render_rm(args: argparse.Namespace) -> None:
    """Render paper-format Reward Machines from a text file to SVG."""
    CONFIG: Configuration = args_to_dataclass(args, Configuration)
    render_rm(CONFIG)


def cmd_generate_larm(args: argparse.Namespace) -> None:
    """Generate one baseline or compiler-adapted ARM-FM bundle."""
    CONFIG: Configuration = args_to_dataclass(args, Configuration)
    generate_larm(CONFIG)


def cmd_embed_larm(args: argparse.Namespace) -> None:
    """Embed validated ARM-FM state descriptions with the local server or the Qwen loader."""
    CONFIG: Configuration = args_to_dataclass(args, Configuration)
    embed_larm(CONFIG)


def cmd_evaluate_larm(args: argparse.Namespace) -> None:
    """Judge ARM-FM bundles with the configured provider."""
    CONFIG: Configuration = args_to_dataclass(args, Configuration)
    evaluate_larm(CONFIG)


def cmd_train_rl(args: argparse.Namespace) -> None:
    """Train one DQN run from a YAML run config."""
    CONFIG: Configuration = args_to_dataclass(args, Configuration)
    train_rl(CONFIG)


# ======================================================================================
#                                       ARGUMENTS
# ======================================================================================
if __name__ == "__main__":
    dotenv.load_dotenv()

    parser = argparse.ArgumentParser(
        prog="schema-rm-rl",
        description="Compile critic-validated tasks into Reward Machines",
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
        "--task",
        dest="tasks",
        action="append",
        required=True,
        help="Natural-language task; repeat for multiple tasks",
    )
    generate_parser.add_argument(
        "--model",
        help="Compiler generator model (defaults to the selected provider's generator model variable)",
    )
    generate_parser.add_argument(
        "--output",
        required=True,
        type=Path,
        metavar="NAME",
        help="Output file name under Configuration.OUTPUT_PATH",
    )
    generate_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing an existing output file",
    )
    generate_parser.add_argument(
        "--task-critic",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable the task critic (default: enabled)",
    )
    generate_parser.add_argument(
        "--rm-critic",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable the Reward Machine critic (default: enabled)",
    )
    generate_parser.add_argument(
        "--labeling",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Generate MiniGrid labeling functions after RM acceptance (default: disabled)",
    )
    generate_parser.add_argument(
        "--domain",
        help="Labeling domain used by --labeling (default: minigrid; only MiniGrid/BabyAI supported)",
    )
    generate_parser.add_argument(
        "--embeddings",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Embed accepted state descriptions through the configured local server (default: disabled)",
    )
    generate_parser.add_argument(
        "--embedding-context",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Prefix each description with its task context before embedding (default: disabled)",
    )
    generate_parser.add_argument(
        "--svg",
        action="store_true",
        help="Write one SVG graph per accepted Reward Machine",
    )
    generate_parser.add_argument(
        "--svg-dir",
        type=Path,
        default=None,
        help="SVG directory (default: outputs/svgs)",
    )
    generate_parser.add_argument(
        "--trace-dir",
        type=Path,
        default=Configuration.TRACE_PATH,
        help="Folder for the step trace of every run (default: outputs/traces)",
    )
    generate_parser.add_argument(
        "--steps-report",
        type=Path,
        default=None,
        help="Also write the readable step report to this Markdown file",
    )
    generate_parser.set_defaults(func=cmd_generate_rm)

    # ======================================================================================
    #                                       render-rm
    # ======================================================================================
    render_parser = subparsers.add_parser(
        "render-rm", help="Render paper-format Reward Machines to SVG"
    )
    render_parser.add_argument(
        "--rm-file",
        required=True,
        type=Path,
        help="Text or Markdown file with REWARD_MACHINE blocks",
    )
    render_parser.add_argument(
        "--svg-dir",
        type=Path,
        default=None,
        help="Output .svg file, or a directory for several machines (default: outputs/svgs)",
    )
    render_parser.set_defaults(func=cmd_render_rm)

    # ======================================================================================
    #                                       generate-larm
    # ======================================================================================
    larm_parser = subparsers.add_parser(
        "generate-larm", help="Generate one inspectable ARM-FM task bundle"
    )
    larm_parser.add_argument("--mode", choices=("arm-fm", "compiler"), default="arm-fm")
    larm_parser.add_argument("--environment", type=Path)
    larm_parser.add_argument("--task", dest="tasks", action="append", default=[])
    larm_parser.add_argument("--bundle", type=Path)
    larm_parser.add_argument("--task-manifest", type=Path)
    larm_parser.add_argument("--output", type=Path, default=Path("arm-fm.rm"))
    larm_parser.add_argument("--model")
    larm_parser.add_argument("--judge-model", default="Qwen3-30B-A3B-Instruct-2507")
    larm_parser.add_argument("--overwrite", action="store_true")
    larm_parser.add_argument("--task-critic", action=argparse.BooleanOptionalAction, default=True)
    larm_parser.add_argument("--rm-critic", action=argparse.BooleanOptionalAction, default=True)
    larm_parser.add_argument(
        "--embeddings",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Embed accepted compiler descriptions through the configured local server (default: disabled)",
    )
    larm_parser.add_argument(
        "--embedding-context",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Prefix each description with its task context before embedding (default: disabled)",
    )
    larm_parser.set_defaults(func=cmd_generate_larm)

    # ======================================================================================
    #                                       embed-larm
    # ======================================================================================
    embed_parser = subparsers.add_parser(
        "embed-larm", help="Embed validated ARM-FM state descriptions"
    )
    embed_parser.add_argument("--bundle", required=True, type=Path)
    embed_backend = embed_parser.add_mutually_exclusive_group()
    embed_backend.add_argument("--model")
    embed_backend.add_argument(
        "--embedding-server",
        dest="embeddings",
        action="store_true",
        help="Embed through the configured local server with the compiler's settings "
        "(default: built-in Qwen loader)",
    )
    embed_parser.set_defaults(func=cmd_embed_larm)

    # ======================================================================================
    #                                       evaluate-larm
    # ======================================================================================
    evaluate_parser = subparsers.add_parser("evaluate-larm", help="Judge ARM-FM artifacts")
    evaluate_parser.add_argument("--bundle", type=Path)
    evaluate_parser.add_argument(
        "--manifest", dest="manifests", action="append", type=Path, default=[]
    )
    evaluate_parser.add_argument("--model")
    evaluate_parser.add_argument("--judge-model", default="Qwen3-30B-A3B-Instruct-2507")
    evaluate_parser.add_argument("--output", type=Path)
    evaluate_parser.set_defaults(func=cmd_evaluate_larm)

    # ======================================================================================
    #                                       train-rl
    # ======================================================================================
    train_parser = subparsers.add_parser(
        "train-rl", help="Train one DQN run, with or without a Reward Machine"
    )
    train_parser.add_argument(
        "--config",
        dest="yaml_config_name",
        required=True,
        help="Run config under configs/, e.g. minigrid-unlock-pickup/smoke-rm-symbolic.yaml",
    )
    # SUPPRESS keeps the global --seed when this one is absent, so both positions work.
    train_parser.add_argument("--seed", type=int, default=argparse.SUPPRESS)
    train_parser.set_defaults(func=cmd_train_rl)

    # ======================================================================================
    #                                       CALL
    # ======================================================================================
    args = parser.parse_args()
    args.func(args)
