"""Optional environment integrations and deterministic task decoding."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.config import Configuration


class EnvironmentUnavailableError(RuntimeError):
    """A domain dependency is not installed; no fallback carrier is used."""


class UnsupportedTaskEncodingError(ValueError):
    """A benchmark task uses an encoding this reconstruction does not understand."""


CRAFTIUM_SOURCE_REVISION = "8eb8707cb756df47e76131a0058ab724d2383c76"
CRAFTIUM_NATIVE_PREREQUISITES = (
    "g++, make, libc6-dev, cmake, libpng-dev, libjpeg-dev, libgl1-mesa-dev, "
    "libsqlite3-dev, libogg-dev, libvorbis-dev, libopenal-dev, libcurl4-gnutls-dev, "
    "libfreetype6-dev, zlib1g-dev, libgmp-dev, libjsoncpp-dev, libzstd-dev, "
    "libluajit-5.1-dev, gettext, libsdl2-dev, libpython3-dev, and recursive submodules"
)
METAWORLD_TASK_IDS = {
    "assembly": "assembly-v3",
    "bin-picking": "bin-picking-v3",
    "pick-place": "pick-place-v3",
    "shelf-place": "shelf-place-v3",
    "stick-push": "stick-push-v3",
}
_MINIGRID_REGISTERED = False


@dataclass
class EnvironmentAdapter:
    """One lazy environment factory plus its documented proposition API."""

    environment_id: str
    factory: Any
    proposition_semantics: dict[str, str]
    task_decoder: Any | None = None

    def make(self, **kwargs: Any) -> Any:
        return self.factory(**kwargs)


def make_environment(environment_id: str, **kwargs: Any) -> Any:
    """Create a declared environment lazily, never silently substituting another domain."""
    normalized = environment_id.lower()
    try:
        if "xland" in normalized:
            return XLandEnvironmentAdapter(kwargs.pop("env_id", "XLand-MiniGrid-R4-13x13"), **kwargs)
        if "craftium" in normalized:
            import gymnasium as gym

            try:
                import craftium  # noqa: F401  # registration side effect
            except ImportError as error:
                raise EnvironmentUnavailableError(
                    "Craftium is a native dependency; build its recursive source tree before use"
                ) from error
            env_id = kwargs.pop("env_id", None) or (
                environment_id if "/" in environment_id else None
            )
            if not env_id:
                raise ValueError("Craftium requires the built task environment id")
            return gym.make(env_id, **kwargs)
        if "metaworld" in normalized or "meta-world" in normalized:
            import metaworld

            task_id = kwargs.pop("task_id", None)
            if task_id is None:
                task_id = next((value for key, value in METAWORLD_TASK_IDS.items() if key in normalized), None)
            if task_id is None:
                raise ValueError("Meta-World requires one of the five catalogued task ids")
            benchmark = metaworld.MT1(task_id, seed=kwargs.pop("seed", None))
            environment = benchmark.train_classes[task_id]()
            if benchmark.train_tasks:
                environment.set_task(benchmark.train_tasks[0])
            return environment
        import gymnasium as gym
        if "minigrid" in normalized or "babyai" in normalized:
            import minigrid
            global _MINIGRID_REGISTERED
            if not _MINIGRID_REGISTERED:
                minigrid.register_minigrid_envs()
                _MINIGRID_REGISTERED = True

        return gym.make(kwargs.pop("env_id", environment_id), **kwargs)
    except ImportError as error:
        raise EnvironmentUnavailableError(
            f"Environment dependency for {environment_id!r} is unavailable"
        ) from error


def minigrid_labeling_api() -> str:
    """Return the API contract used in generated MiniGrid predicates."""
    return (
        "env.grid.get(x, y), env.agent_pos, env.carrying, env.width, env.height; "
        "objects expose type, color, is_open, and is_locked"
    )


def labeling_api_for_domain(domain: str) -> str:
    """Return the documented, domain-specific snapshot surface for generators."""
    normalized = domain.lower()
    if "xland" in normalized:
        return "env.observation, env.state, env.params.ruleset, and the documented XLand snapshot proxy"
    if "craftium" in normalized:
        return "env.inventory, env.observation, env.world, and documented Craftium snapshot fields"
    if "meta" in normalized:
        return "env._last_obs, env._success, env.observation_space, and documented Meta-World fields"
    return minigrid_labeling_api()


def environment_adapter(domain: str) -> EnvironmentAdapter:
    """Return the documented adapter for a supported domain."""
    normalized = domain.lower()
    if "xland" in normalized:
        return EnvironmentAdapter(domain, lambda **kwargs: make_environment(domain, **kwargs), {
            "required_object_held": "The active ruleset's required object is held.",
            "required_object_reached": "The required tile has been reached.",
            "required_relation_satisfied": "The active relation is satisfied.",
            "intermediate_object_created": "A required transformation object exists.",
            "goal_satisfied": "The active ruleset goal is satisfied.",
        }, xland_benchmark_tasks)
    if "craftium" in normalized:
        return EnvironmentAdapter(domain, lambda **kwargs: make_environment(domain, **kwargs), {
            "wood_acquired": "Wood is acquired for this episode.",
            "stone_acquired": "Stone is acquired for this episode.",
            "iron_acquired": "Iron is acquired for this episode.",
            "diamond_acquired": "Diamond is acquired for this episode.",
        })
    if "meta" in normalized:
        return EnvironmentAdapter(domain, lambda **kwargs: make_environment(domain, **kwargs), {
            "near_object": "The gripper is near the object.",
            "object_grasped": "The object is grasped.",
            "object_near_goal": "The object is near but not at the goal.",
            "object_at_goal": "The object is at the goal.",
        })
    return EnvironmentAdapter(domain, lambda **kwargs: make_environment(domain, **kwargs), {
        "has_key": "The agent carries the key.",
        "door_open": "The relevant door is open.",
        "at_goal": "The agent is on the goal.",
        "key_lost": "The agent lost the key after acquiring it.",
    })


class XLandEnvironmentAdapter:
    """Gym-shaped adapter around XLand-MiniGrid's functional environment API."""

    def __init__(self, env_id: str, *, ruleset: object | None = None, seed: int = 0, **kwargs: Any) -> None:
        try:
            import gymnasium as gym
            import xminigrid
            import jax
        except ImportError as error:
            raise EnvironmentUnavailableError("XLand-MiniGrid and JAX are required") from error
        self._jax = jax
        self._env, self.params = xminigrid.make(env_id, **kwargs)
        if ruleset is not None:
            self.params = self.params.replace(ruleset=ruleset)
        self._seed = int(seed)
        self._timestep = None
        actions = self._env.num_actions(self.params) if callable(self._env.num_actions) else self._env.num_actions
        self.action_space = gym.spaces.Discrete(int(actions))
        self.observation = None
        self.state = None

    def reset(self, *, seed: int | None = None, **_kwargs: Any):
        if seed is not None:
            self._seed = int(seed)
        self._timestep = self._env.reset(self.params, self._jax.random.PRNGKey(self._seed))
        self.observation = _numpy(self._timestep.observation)
        self.state = self._timestep.state
        return self.observation, {"xland_state": self.state}

    def step(self, action: int):
        if self._timestep is None:
            raise RuntimeError("XLand environment must be reset before step")
        self._timestep = self._env.step(self.params, self._timestep, action)
        self.observation = _numpy(self._timestep.observation)
        self.state = self._timestep.state
        step_type = int(self._timestep.step_type)
        terminated = bool(step_type == 2 and float(self._timestep.discount) == 0.0)
        truncated = bool(step_type == 2 and not terminated)
        return (
            self.observation,
            float(self._timestep.reward),
            terminated,
            truncated,
            {"xland_state": self.state},
        )

    def render(self):
        if self._timestep is None:
            return None
        return _numpy(self._env.render(self.params, self._timestep))


def _numpy(value: object) -> Any:
    try:
        import numpy as np

        return np.asarray(value)
    except ImportError:
        return value


def xland_benchmark_tasks(benchmark: str = "medium-1m", *, limit: int = 1000) -> tuple[dict[str, Any], ...]:
    """Decode the first benchmark entries into stable JSON task records."""
    if limit < 1:
        raise ValueError("limit must be positive")
    try:
        import xminigrid
    except ImportError as error:
        raise EnvironmentUnavailableError("XLand-MiniGrid dependency is unavailable") from error
    try:
        source = xminigrid.load_benchmark(benchmark)
    except Exception as error:
        raise UnsupportedTaskEncodingError(f"Could not load XLand benchmark {benchmark!r}: {error}") from error
    records = []
    count = int(source.num_rulesets()) if hasattr(source, "num_rulesets") else len(source)
    for index in range(min(limit, count)):
        item = source.get_ruleset(index) if hasattr(source, "get_ruleset") else source[index]
        decoded = _decode_xland_ruleset(item)
        records.append({
            "index": index,
            "source": {"benchmark": benchmark, "index": index},
            "task": render_xland_task(decoded),
            "encoding": decoded,
        })
    if len(records) < limit:
        raise UnsupportedTaskEncodingError(
            f"Benchmark {benchmark!r} provided only {len(records)} task(s); expected {limit}"
        )
    return tuple(records)


def render_xland_task(task: object) -> str:
    """Render a decoded task deterministically, failing on unknown encodings."""
    value = _jsonable_task(task)
    return json.dumps(value, sort_keys=True, separators=(", ", ": "))


def _decode_xland_ruleset(ruleset: object) -> dict[str, Any]:
    """Decode XLand's stable goal/rule ids and tile pairs into text-ready records."""
    value = _jsonable_task(ruleset)
    if not isinstance(value, dict) or not {"goal", "rules", "init_tiles"} <= value.keys():
        raise UnsupportedTaskEncodingError("XLand ruleset must expose goal, rules, and init_tiles")
    goal = value["goal"]
    rules = value["rules"]
    if not isinstance(goal, list) or not goal or not isinstance(rules, list):
        raise UnsupportedTaskEncodingError("XLand ruleset has unsupported goal/rule arrays")
    goal_names = (
        "empty", "agent_holds", "agent_on_tile", "agent_near_tile", "tile_near_tile",
        "tile_on_position", "agent_on_position", "tile_near_up", "tile_near_right",
        "tile_near_down", "tile_near_left", "agent_near_up", "agent_near_right",
        "agent_near_down", "agent_near_left",
    )
    rule_names = (
        "empty", "agent_hold", "agent_near", "tile_near", "tile_near_up",
        "tile_near_right", "tile_near_down", "tile_near_left", "agent_near_up",
        "agent_near_right", "agent_near_down", "agent_near_left",
    )
    goal_id = int(goal[0])
    if not 0 <= goal_id < len(goal_names):
        raise UnsupportedTaskEncodingError(f"Unsupported XLand goal encoding id {goal_id}")
    decoded_rules = []
    for row in rules:
        if not isinstance(row, list) or not row:
            raise UnsupportedTaskEncodingError("Unsupported XLand rule row")
        rule_id = int(row[0])
        if not 0 <= rule_id < len(rule_names):
            raise UnsupportedTaskEncodingError(f"Unsupported XLand rule encoding id {rule_id}")
        decoded_rules.append({"kind": rule_names[rule_id], "encoding": row})
    return {
        "goal": {"kind": goal_names[goal_id], "encoding": goal},
        "rules": decoded_rules,
        "init_tiles": value["init_tiles"],
    }


def load_catalogue_tasks(root: str | Path) -> tuple[dict[str, Any], ...]:
    """Load catalogue companions and enforce their exact declared schema."""
    root = Path(root)
    records = []
    for path in sorted(root.glob("*/tasks.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if set(data) != {"env", "env_description", "tasks"}:
            raise ValueError(f"{path}: tasks.json must contain exactly env, env_description, tasks")
        environment_path = (Configuration.WORKSPACE_PATH / data["env_description"]).resolve()
        if not environment_path.exists() or environment_path != (path.parent / "environment.md").resolve():
            raise ValueError(f"{path}: env_description must resolve to environment.md")
        if not isinstance(data["tasks"], list) or not all(isinstance(task, str) and task.strip() for task in data["tasks"]):
            raise ValueError(f"{path}: tasks must be nonempty strings")
        records.append(data)
    return tuple(records)


def _jsonable_task(value: object) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _jsonable_task(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (tuple, list)):
        return [_jsonable_task(item) for item in value]
    if hasattr(value, "tolist"):
        return _jsonable_task(value.tolist())
    if hasattr(value, "__dict__"):
        data = {key: _jsonable_task(item) for key, item in vars(value).items() if not key.startswith("_")}
        if data:
            return data
    raise UnsupportedTaskEncodingError(f"Unsupported task encoding: {type(value).__name__}")
