"""Public ARM-FM reconstruction interfaces."""

from . import custom_envs
from .artifacts import (
    ArtifactBundle,
    BundleManifest,
    BundleValidationError,
    load_bundle,
    load_task_manifest,
)
from .dqn import train_dqn
from .environments import (
    make_environment,
    make_run_environment,
)
from .evaluation import (
    EMBEDDING_MODEL,
    EmbeddingCache,
    EmbeddingSettings,
    JudgeDecision,
    aggregate_judgments,
    embed_descriptions_over_http,
    embed_state_descriptions,
    frozen_evaluate,
    judge_bundle,
    load_qwen_embedding_model,
    resolve_embedding_settings,
)
from .generation import (
    adapt_compilation_result,
    generate_baseline_bundle,
    generate_compiler_bundle,
    record_bundle_embeddings,
    record_bundle_role_models,
)
from .paper_profile import (
    PAPER_REFERENCE_SHA,
    Engines,
    PaperPrompts,
    PaperRun,
    clone_head,
    generate_draw,
    infer_final_states,
    load_sources,
)
from .ppo import train_ppo
from .runtime import (
    RewardMachineEnvironment,
    RewardMachineRuntime,
    load_labeling_functions,
)
