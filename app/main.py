"""Application command-line entry point."""

import argparse
import sys
from pathlib import Path

import dotenv
from maikol_utils.other_utils import args_to_dataclass

from scripts import (
    OFF_CHOICES,
    SuiteOptions,
    ablate_rm,
    aggregate_suite,
    cross_critic,
    embed_larm,
    evaluate_larm,
    generate_larm,
    generate_rm,
    generate_suite,
    generation_table,
    import_paper_bundle,
    product_rm,
    regenerate_labeling,
    render_rm,
    repair_labeling,
    replay_traces,
    restore_farm,
    rm_facts,
    run_suite,
    state_check,
    test_rl,
    trace_bank,
    train_rl,
)
from src.config import REASONING_LEVELS, Configuration
from src.utils import GenerationHooks, print_warning


def cmd_generate_rm(args: argparse.Namespace) -> None:
    """Generate a Reward Machine from parsed CLI configuration."""
    CONFIG: Configuration = args_to_dataclass(args, Configuration)
    if not generate_rm(CONFIG, GenerationHooks(warning=print_warning)):
        sys.exit(1)


def cmd_render_rm(args: argparse.Namespace) -> None:
    """Render paper-format Reward Machines from a text file to SVG and optional HTML."""
    CONFIG: Configuration = args_to_dataclass(args, Configuration)
    render_rm(CONFIG)


def cmd_generate_larm(args: argparse.Namespace) -> None:
    """Generate one baseline or compiler-adapted ARM-FM bundle."""
    CONFIG: Configuration = args_to_dataclass(args, Configuration)
    generate_larm(CONFIG)


def cmd_generate_suite(args: argparse.Namespace) -> None:
    """Generate the bundles of one task card file for one arm."""
    only = tuple(item for item in (args.only or "").split(",") if item)
    generate_suite(
        SuiteOptions(
            tasks=args.tasks,
            arm=args.arm,
            output=args.output.resolve(),  # the child processes run in the repository root
            only=only,
            paraphrases=args.paraphrases,
            parallel=args.parallel,
            max_calls=args.max_calls,
            deadline_min=args.deadline_min,
            retry_failed=args.retry_failed,
        )
    )


def cmd_cross_critic(args: argparse.Namespace) -> None:
    """Judge generated machines with the other pipeline's critic."""
    CONFIG: Configuration = args_to_dataclass(args, Configuration)
    try:
        cross_critic(CONFIG, args.bundles, args.direction, args.max_calls, args.parallel)
    except ValueError as error:  # usage errors: no eligible bundle, no critic model
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)


def cmd_embed_larm(args: argparse.Namespace) -> None:
    """Embed validated ARM-FM state descriptions with the local server or the Qwen loader."""
    CONFIG: Configuration = args_to_dataclass(args, Configuration)
    embed_larm(CONFIG)


def cmd_ablate_rm(args: argparse.Namespace) -> None:
    """Rebuild a compiler bundle's Reward Machine with one reward part switched off."""
    CONFIG: Configuration = args_to_dataclass(args, Configuration)
    if not ablate_rm(CONFIG, args.off, args.destination):
        sys.exit(1)


def cmd_import_paper_bundle(args: argparse.Namespace) -> None:
    """Import the authors' released artifacts for one environment as a bundle."""
    CONFIG: Configuration = args_to_dataclass(args, Configuration)
    import_paper_bundle(CONFIG)


def cmd_evaluate_larm(args: argparse.Namespace) -> None:
    """Judge ARM-FM bundles with the configured provider."""
    CONFIG: Configuration = args_to_dataclass(args, Configuration)
    evaluate_larm(CONFIG)


def cmd_train_rl(args: argparse.Namespace) -> None:
    """Train one DQN run from a YAML run config."""
    CONFIG: Configuration = args_to_dataclass(args, Configuration)
    train_rl(CONFIG)


def cmd_test_rl(args: argparse.Namespace) -> None:
    """Test finished runs on unseen maps and render GIFs."""
    CONFIG: Configuration = args_to_dataclass(args, Configuration)
    test_rl(CONFIG, args.gifs, args.judge)


def cmd_product_rm(args: argparse.Namespace) -> None:
    """Build the product of two bundles' machines, for evaluation only."""
    CONFIG: Configuration = args_to_dataclass(args, Configuration)
    product_rm(CONFIG, args.first, args.second, args.folder, (args.first_card, args.second_card))


def cmd_state_check(args: argparse.Namespace) -> None:
    """Compare a test machine's states with the training machines' states."""
    state_check(args.train, args.test, args.product, args.output)


def cmd_trace_bank(args: argparse.Namespace) -> None:
    """Run every card plan in the real env and check the judge's verdicts."""
    trace_bank(args.tasks, args.output, args.only, args.seed)


def cmd_replay_traces(args: argparse.Namespace) -> None:
    """Replay a trace bank through generated bundles and check each machine."""
    replay_traces(args.traces, args.bundles, args.output)


def cmd_rm_facts(args: argparse.Namespace) -> None:
    """Write the machine, clause and generation facts of generated bundles."""
    rm_facts(args.bundles, args.tasks, args.replay, args.output)


def cmd_generation_table(args: argparse.Namespace) -> None:
    """Print how often each generation step was accepted, per arm and suite."""
    generation_table(args.root, args.output)


def cmd_regenerate_labeling(args: argparse.Namespace) -> None:
    """Run the generation labeling loop again on bundles that have an accepted machine."""
    CONFIG: Configuration = args_to_dataclass(args, Configuration)
    regenerate_labeling(CONFIG, args.bundles, tuple(args.only or ()))


def cmd_repair_labeling(args: argparse.Namespace) -> None:
    """Check bundles' labeling against a trace bank and repair the failed ones."""
    CONFIG: Configuration = args_to_dataclass(args, Configuration)
    repair_labeling(CONFIG, args.traces, args.bundles, tuple(args.only or ()), args.check_only)


def cmd_restore_farm(args: argparse.Namespace) -> None:
    """Rebuild FARM failure bundles from their generation logs."""
    if not restore_farm(args.bundles, tuple(args.only or ())):
        sys.exit(1)


def cmd_run_suite(args: argparse.Namespace) -> None:
    """Train every run of a benchmark suite, skipping finished ones."""
    CONFIG: Configuration = args_to_dataclass(args, Configuration)
    if not run_suite(CONFIG):
        sys.exit(1)


def cmd_aggregate_suite(args: argparse.Namespace) -> None:
    """Collect a benchmark suite's runs into results tables."""
    CONFIG: Configuration = args_to_dataclass(args, Configuration)
    aggregate_suite(CONFIG)


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
        "--critic",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable the critic that reviews each compiled candidate (default: enabled)",
    )
    generate_parser.add_argument(
        "--recurrent-soft-penalty",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Charge a soft rule's -0.5 at every new break (default: enabled)",
    )
    generate_parser.add_argument(
        "--reasoning",
        choices=REASONING_LEVELS,
        default=Configuration.reasoning,
        help="Reasoning level of the generator and the critic (default: %(default)s)",
    )
    generate_parser.add_argument(
        "--attempts",
        type=int,
        choices=Configuration.ATTEMPT_LIMITS,
        default=Configuration.attempts,
        metavar="N",
        help="Reward Machine attempts per task, 1 to 10 (every new candidate counts: accepted, "
        "rejected by the critic or invalid; a provider outage or a failed critic request is "
        "repeated without counting) (default: %(default)s)",
    )
    generate_parser.add_argument(
        "--labeling",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Generate MiniGrid labeling functions after RM acceptance (default: disabled)",
    )
    generate_parser.add_argument(
        "--state-descriptions",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Describe each Reward Machine state after acceptance; labeling and embeddings "
        "need it (default: enabled)",
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
        "render-rm", help="Render paper-format Reward Machines to SVG and optional HTML"
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
    render_parser.add_argument(
        "--html",
        action="store_true",
        help="Also write an interactive <same stem>.html beside each SVG",
    )
    render_parser.set_defaults(func=cmd_render_rm)

    # ======================================================================================
    #                                       generate-larm
    # ======================================================================================
    larm_parser = subparsers.add_parser(
        "generate-larm", help="Generate one inspectable ARM-FM task bundle"
    )
    larm_parser.add_argument("--mode", choices=("arm-fm", "compiler", "paper"), default="arm-fm")
    larm_parser.add_argument(
        "--reference", type=Path, help="paper mode: clone of roger-creus/llms-rm-rl"
    )
    larm_parser.add_argument(
        "--paper-sources", dest="paper_sources", type=Path, help="paper mode: paper-sources.json"
    )
    larm_parser.add_argument(
        "--draws", type=int, default=3, help="paper mode: independent generations (default: 3)"
    )
    larm_parser.add_argument("--environment", type=Path)
    larm_parser.add_argument("--task", dest="tasks", action="append", default=[])
    larm_parser.add_argument("--bundle", type=Path)
    larm_parser.add_argument("--task-manifest", type=Path)
    larm_parser.add_argument("--output", type=Path, default=Path("arm-fm.rm"))
    larm_parser.add_argument("--model")
    larm_parser.add_argument("--judge-model", default="Qwen3-30B-A3B-Instruct-2507")
    larm_parser.add_argument("--overwrite", action="store_true")
    larm_parser.add_argument(
        "--critic",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="compiler mode only: review each compiled candidate with the critic "
        "(arm-fm and paper modes always run their own critic; default: enabled)",
    )
    larm_parser.add_argument(
        "--recurrent-soft-penalty",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="compiler mode only: charge a soft rule's -0.5 at every new break (default: enabled)",
    )
    larm_parser.add_argument(
        "--reasoning",
        choices=REASONING_LEVELS,
        default=Configuration.reasoning,
        help="Reasoning level of every model call (default: %(default)s)",
    )
    larm_parser.add_argument(
        "--attempts",
        type=int,
        choices=Configuration.ATTEMPT_LIMITS,
        default=Configuration.attempts,
        metavar="N",
        help="Reward Machine attempts per task in both arms (every new candidate counts: "
        "accepted, rejected by the critic or invalid; a provider outage reruns without counting), "
        "1 to 10; --mode paper ignores it and runs its own three rounds (default: %(default)s)",
    )
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
    larm_parser.add_argument(
        "--arm-fm-critic",
        action="store_true",
        help="arm-fm mode only: the critic calls use the critic model and the generator calls the "
        "generator model (default: one model for every role)",
    )
    larm_parser.set_defaults(func=cmd_generate_larm)

    # ======================================================================================
    #                                       generate-suite
    # ======================================================================================
    suite_parser = subparsers.add_parser(
        "generate-suite",
        help="Generate one bundle per task card for one arm, with a status file per card",
    )
    suite_parser.add_argument("--tasks", required=True, type=Path, help="Task card file")
    suite_parser.add_argument("--arm", required=True, choices=("farm", "arm-fm"))
    suite_parser.add_argument(
        "--output", required=True, type=Path, help="Folder that receives <card-id>/ bundles"
    )
    suite_parser.add_argument("--only", help="Comma-separated card ids to run (default: all)")
    suite_parser.add_argument(
        "--paraphrases",
        action="store_true",
        help="Also generate each card's paraphrases as <card-id>~p<k>",
    )
    suite_parser.add_argument(
        "--parallel", type=int, default=10, help="Bundles generated at once (default: %(default)s)"
    )
    suite_parser.add_argument(
        "--max-calls",
        type=int,
        help="Stop launching bundles once finished bundles used this many model calls",
    )
    suite_parser.add_argument(
        "--deadline-min", type=float, help="Stop launching bundles after this many minutes"
    )
    suite_parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Run bundles whose status is pipeline-failed again (default: they stay skipped)",
    )
    suite_parser.set_defaults(func=cmd_generate_suite)

    # ======================================================================================
    #                                       cross-critic
    # ======================================================================================
    cross_parser = subparsers.add_parser(
        "cross-critic", help="Judge generated machines with the other pipeline's critic"
    )
    cross_parser.add_argument(
        "--bundles", required=True, type=Path, help="Folder of <card-id>/ bundles of one arm"
    )
    cross_parser.add_argument(
        "--critic",
        dest="direction",
        required=True,
        choices=("farm", "arm-fm"),
        help="farm judges ARM-FM bundles; arm-fm judges FARM bundles",
    )
    cross_parser.add_argument(
        "--max-calls", type=int, help="Stop launching judgments after this many model calls"
    )
    cross_parser.add_argument(
        "--parallel", type=int, default=10, help="Bundles judged at once (default: %(default)s)"
    )
    cross_parser.set_defaults(func=cmd_cross_critic)

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
    #                                       ablate-rm
    # ======================================================================================
    ablate_parser = subparsers.add_parser(
        "ablate-rm",
        help="Rebuild a compiler bundle's Reward Machine with one reward part switched off",
    )
    ablate_parser.add_argument(
        "--bundle",
        required=True,
        type=Path,
        help="Source bundle made by generate-larm --mode compiler; it must store its clauses",
    )
    ablate_parser.add_argument(
        "--off",
        required=True,
        choices=OFF_CHOICES,
        help="Reward part that pays 0 in the copy; none rebuilds the source unchanged",
    )
    ablate_parser.add_argument(
        "--output",
        dest="destination",
        required=True,
        type=Path,
        metavar="DIR",
        help="Bundle folder to write",
    )
    ablate_parser.add_argument("--overwrite", action="store_true")
    ablate_parser.set_defaults(func=cmd_ablate_rm)

    # ======================================================================================
    #                                   import-paper-bundle
    # ======================================================================================
    import_parser = subparsers.add_parser(
        "import-paper-bundle",
        help="Import the authors' released RM, labeling and embeddings as a bundle",
    )
    import_parser.add_argument(
        "--reference", required=True, type=Path, help="Local clone of roger-creus/llms-rm-rl"
    )
    import_parser.add_argument(
        "--env",
        dest="paper_env",
        required=True,
        help="Released environment: DoorKey, UnlockToUnlock, BlockedUnlockPickup or KeyCorridorS6R3",
    )
    import_parser.add_argument(
        "--output", dest="bundle", required=True, type=Path, help="Bundle folder to write"
    )
    import_parser.add_argument("--overwrite", action="store_true")
    import_parser.set_defaults(func=cmd_import_paper_bundle)

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
    #                                       test-rl
    # ======================================================================================
    test_parser = subparsers.add_parser(
        "test-rl", help="Test finished train-rl runs on unseen maps and render GIFs"
    )
    test_parser.add_argument(
        "--run",
        dest="exp_name",
        required=True,
        metavar="RUN",
        help="A run folder, or an exp_name to test every finished run under outputs/runs/<exp_name>/",
    )
    test_parser.add_argument(
        "--episodes",
        dest="final_eval_episodes",
        type=int,
        default=100,
        metavar="N",
        help="Test episodes",
    )
    test_parser.add_argument(
        "--seed-base",
        dest="eval_seed_base",
        type=int,
        default=2_000_000,
        metavar="SEED",
        help="Episode i resets with this seed + i (training uses the run seed, validation 1000000)",
    )
    test_parser.add_argument(
        "--gifs", type=int, default=0, metavar="N", help="Test episodes to render as GIFs"
    )
    test_parser.add_argument(
        "--judge",
        type=Path,
        default=None,
        metavar="CARD",
        help="Task card (card.json) to judge the test episodes with: writes agent-traces/ep<k>.json "
        "and judge.json in each run folder",
    )
    test_parser.add_argument(
        "--bundle",
        type=Path,
        default=None,
        metavar="DIR",
        help="Play this bundle's machine, labeling and state embeddings instead of the run's own "
        "(needs --judge; the policy is not retrained). Writes <run>/transfer/<name>/",
    )
    test_parser.add_argument(
        "--shuffle-embeddings",
        dest="shuffle_embeddings_seed",
        type=int,
        default=None,
        metavar="SEED",
        help="Control: permute the state embeddings among the machine's states with this seed",
    )
    test_parser.set_defaults(func=cmd_test_rl)

    # ======================================================================================
    #                                       product-rm
    # ======================================================================================
    product_parser = subparsers.add_parser(
        "product-rm", help="Build the product of two bundles' machines to test a policy on"
    )
    product_parser.add_argument("--first", required=True, type=Path, help="First bundle")
    product_parser.add_argument("--second", required=True, type=Path, help="Second bundle")
    product_parser.add_argument(
        "--output", dest="folder", required=True, type=Path, help="Product bundle folder to write"
    )
    product_parser.add_argument("--first-card", type=Path, help="Card of the first bundle")
    product_parser.add_argument(
        "--second-card",
        type=Path,
        help="Card of the second bundle; with --first-card, writes <output>/card.json",
    )
    product_parser.add_argument("--overwrite", action="store_true")
    product_parser.set_defaults(func=cmd_product_rm)

    # ======================================================================================
    #                                      state-check
    # ======================================================================================
    check_parser = subparsers.add_parser(
        "state-check", help="Compare test machines' states with the training machines' states"
    )
    check_parser.add_argument(
        "--train", action="append", required=True, type=Path, help="Training bundle (repeatable)"
    )
    check_parser.add_argument(
        "--test", action="append", default=[], type=Path, help="Test bundle (repeatable)"
    )
    check_parser.add_argument(
        "--product", action="append", default=[], type=Path, help="Product bundle (repeatable)"
    )
    check_parser.add_argument(
        "--output", required=True, type=Path, help="Folder for state-check.json, .md and .html"
    )
    check_parser.set_defaults(func=cmd_state_check)

    # ======================================================================================
    #                                       trace-bank
    # ======================================================================================
    bank_parser = subparsers.add_parser(
        "trace-bank", help="Run every card plan in the real env, write traces, check the judge"
    )
    bank_parser.add_argument("--tasks", required=True, type=Path, help="Card file (tasks.json)")
    bank_parser.add_argument("--output", required=True, type=Path, help="Folder for the traces")
    bank_parser.add_argument("--only", nargs="+", metavar="ID", help="Run only these card ids")
    bank_parser.set_defaults(func=cmd_trace_bank)

    # ======================================================================================
    #                                      replay-traces
    # ======================================================================================
    replay_parser = subparsers.add_parser(
        "replay-traces", help="Replay a trace bank through generated bundles and check each machine"
    )
    replay_parser.add_argument("--traces", required=True, type=Path, help="trace-bank output")
    replay_parser.add_argument(
        "--bundles", required=True, type=Path, help="Folder <arm>/<card-id>[~p<k>]/ of bundles"
    )
    replay_parser.add_argument("--output", required=True, type=Path, help="Folder for the replay")
    replay_parser.set_defaults(func=cmd_replay_traces)

    # ======================================================================================
    #                                        rm-facts
    # ======================================================================================
    facts_parser = subparsers.add_parser(
        "rm-facts", help="Write the machine, clause and generation facts of bundles"
    )
    facts_parser.add_argument(
        "--bundles", required=True, type=Path, help="Folder <arm>/<card-id>[~p<k>]/ of bundles"
    )
    facts_parser.add_argument("--tasks", type=Path, default=None, help="Card file (clause check)")
    facts_parser.add_argument(
        "--replay", type=Path, default=None, help="replay-summary.json (paraphrase agreement)"
    )
    facts_parser.add_argument("--output", required=True, type=Path, help="JSON file to write")
    facts_parser.set_defaults(func=cmd_rm_facts)

    # ======================================================================================
    #                                   generation-table
    # ======================================================================================
    table_parser = subparsers.add_parser(
        "generation-table",
        help="Print the generation acceptance table of a benchmark folder, per arm and suite",
    )
    table_parser.add_argument(
        "--root", required=True, type=Path, help="Folder <suite>/bundles/<arm>/<name>/ of suites"
    )
    table_parser.add_argument("--output", type=Path, default=None, help="JSON file to write")
    table_parser.set_defaults(func=cmd_generation_table)

    # ======================================================================================
    #                                  regenerate-labeling
    # ======================================================================================
    regenerate_parser = subparsers.add_parser(
        "regenerate-labeling",
        help="Run the generation labeling loop again on bundles with an accepted machine",
    )
    regenerate_parser.add_argument(
        "--bundles", required=True, type=Path, help="Folder <arm>/<card-id>[~p<k>]/ of bundles"
    )
    regenerate_parser.add_argument(
        "--only", nargs="+", metavar="ID", help="Only these card ids or bundle names"
    )
    regenerate_parser.add_argument(
        "--parallel",
        dest="repair_parallel",
        type=int,
        default=Configuration.repair_parallel,
        metavar="N",
        help="Most bundles at once (default: %(default)s)",
    )
    regenerate_parser.set_defaults(func=cmd_regenerate_labeling)

    # ======================================================================================
    #                                    repair-labeling
    # ======================================================================================
    repair_parser = subparsers.add_parser(
        "repair-labeling",
        help="Class every bundle's labeling failures against a trace bank, repair them, finish repaired bundles",
    )
    repair_parser.add_argument("--traces", required=True, type=Path, help="trace-bank output")
    repair_parser.add_argument(
        "--bundles", required=True, type=Path, help="Folder <arm>/<card-id>[~p<k>]/ of bundles"
    )
    repair_parser.add_argument(
        "--only", nargs="+", metavar="ID", help="Only these card ids or bundle names"
    )
    repair_parser.add_argument(
        "--check-only",
        action="store_true",
        help="Class the failures and write the records; ask no model",
    )
    repair_parser.add_argument(
        "--max-iterations",
        dest="repair_iterations",
        type=int,
        default=Configuration.repair_iterations,
        metavar="N",
        help="Repair rounds per bundle (default: %(default)s)",
    )
    repair_parser.add_argument(
        "--parallel",
        dest="repair_parallel",
        type=int,
        default=Configuration.repair_parallel,
        metavar="N",
        help="Most bundles repaired at once (default: %(default)s)",
    )
    repair_parser.set_defaults(func=cmd_repair_labeling)

    # ======================================================================================
    #                                      restore-farm
    # ======================================================================================
    restore_parser = subparsers.add_parser(
        "restore-farm",
        help="Rebuild FARM failure bundles that hold no machine from their generation logs",
    )
    restore_parser.add_argument(
        "--bundles", required=True, type=Path, help="Folder of FARM bundles (<name>/, <name>.log)"
    )
    restore_parser.add_argument(
        "--only",
        nargs="+",
        metavar="NAME",
        help="Only these bundle names; one that cannot be restored is an error",
    )
    restore_parser.set_defaults(func=cmd_restore_farm)

    # ======================================================================================
    #                                       run-suite
    # ======================================================================================
    run_suite_parser = subparsers.add_parser(
        "run-suite", help="Train every run of a benchmark runs.yaml, skipping finished runs"
    )
    run_suite_parser.add_argument("--suite", required=True, type=Path, help="A runs.yaml")
    run_suite_parser.add_argument(
        "--parallel",
        dest="suite_parallel",
        type=int,
        default=Configuration.suite_parallel,
        metavar="N",
        help="Most runs at once (default: %(default)s)",
    )
    run_suite_parser.add_argument(
        "--max-ram-gb",
        dest="suite_max_ram_gb",
        type=float,
        default=Configuration.suite_max_ram_gb,
        metavar="GB",
        help="Budget for the running runs' RAM estimates; a run waits when it would not fit "
        "(default: only the free RAM limits)",
    )
    run_suite_parser.add_argument(
        "--time-box-min",
        dest="suite_time_box_min",
        type=float,
        default=Configuration.suite_time_box_min,
        metavar="M",
        help="Stop a run after this many minutes and mark it timed-out "
        "(default: the runs.yaml value, else none)",
    )
    run_suite_parser.add_argument(
        "--retry-timed-out",
        dest="suite_retry_timed_out",
        action="store_true",
        help="Restart timed-out runs from zero (default: they are skipped)",
    )
    run_suite_parser.add_argument(
        "--dry-run",
        dest="suite_dry_run",
        action="store_true",
        help="List the runs and what would happen to each; start and write nothing",
    )
    run_suite_parser.set_defaults(func=cmd_run_suite)

    # ======================================================================================
    #                                    aggregate-suite
    # ======================================================================================
    aggregate_parser = subparsers.add_parser(
        "aggregate-suite", help="Collect a benchmark suite's runs into results.csv, .json and .md"
    )
    aggregate_parser.add_argument("--suite", required=True, type=Path, help="A runs.yaml")
    aggregate_parser.add_argument(
        "--output",
        dest="suite_output",
        required=True,
        type=Path,
        metavar="DIR",
        help="Folder for results.csv, results.json and results.md",
    )
    aggregate_parser.set_defaults(func=cmd_aggregate_suite)

    # ======================================================================================
    #                                       CALL
    # ======================================================================================
    args = parser.parse_args()
    args.func(args)
