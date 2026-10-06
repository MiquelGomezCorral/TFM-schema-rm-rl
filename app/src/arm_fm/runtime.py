"""String-state Reward Machine execution used by the ARM-FM reconstruction.

The numeric compiler has a deliberately different representation.  This module keeps
the paper's ordered, string-labelled transitions and does one transition selection for
each complete environment valuation.
"""

from __future__ import annotations

import ast
import builtins
import warnings
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from src.compiler.reward_machine import evaluate_boolean_guard, parse_boolean_guard
from src.compiler.rm_format import (
    PaperRewardMachine,
    RuntimeTransition,
    RuntimeValidationError,
)

_ALLOWED_LABELING_BUILTINS = {
    "abs",
    "all",
    "any",
    "bool",
    "dict",
    "float",
    "int",
    "len",
    "list",
    "max",
    "min",
    "range",
    "round",
    "sorted",
    "str",
    "sum",
    "tuple",
}
_MUTATING_ENV_METHODS = {
    "add",
    "append",
    "clear",
    "close",
    "discard",
    "extend",
    "insert",
    "pop",
    "remove",
    "reset",
    "reverse",
    "setdefault",
    "sort",
    "step",
    "update",
    "write",
}


@dataclass(frozen=True)
class RuntimeStep:
    """Result of exactly one RM update."""

    source: str
    destination: str
    reward: float
    transition: RuntimeTransition | None
    overlap: tuple[RuntimeTransition, ...] = ()


class RewardMachineRuntime:
    """Execute one ordered RM transition per environment step."""

    def __init__(
        self,
        machine: PaperRewardMachine,
        warning_handler: Callable[[str], None] | None = None,
    ) -> None:
        self.machine = machine
        self.warning_handler = warning_handler
        self.state = machine.initial_state
        self.episode_memory: dict[str, object] = {}

    def reset(self) -> str:
        """Reset RM state and episode-local labeling memory."""
        self.state = self.machine.initial_state
        self.episode_memory.clear()
        return self.state

    def step(self, valuation: Mapping[str, bool]) -> RuntimeStep:
        """Select and apply one transition from the old state."""
        values = _complete_valuation(valuation, self.machine.propositions)
        ordinary = [
            transition
            for transition in self.machine.transitions
            if transition.source == self.state
            and not transition.is_else
            and evaluate_boolean_guard(
                parse_boolean_guard(transition.condition, self.machine.propositions),
                values,
            )
        ]
        candidates = ordinary
        if not candidates:
            candidates = [
                transition
                for transition in self.machine.transitions
                if transition.source == self.state and transition.is_else
            ]
        overlap = tuple(ordinary[1:])
        selected = candidates[0] if candidates else None
        if len(ordinary) > 1:
            message = (
                f"Overlapping RM guards in state {self.state!r}; selecting stored transition "
                f"to {ordinary[0].destination!r}"
            )
            if self.warning_handler is not None:
                self.warning_handler(message)
            else:
                warnings.warn(message, RuntimeWarning, stacklevel=2)
        source = self.state
        if selected is None:
            destination, reward = source, 0.0
        else:
            destination, reward = selected.destination, float(selected.reward)
        self.state = destination
        return RuntimeStep(source, destination, reward, selected, overlap)

    def evaluate_labeling(
        self,
        env: object,
        labeling: Mapping[str, Callable[[object], bool]],
    ) -> dict[str, bool]:
        """Compute every proposition once from the live environment and remember the valuation."""
        previous = self.episode_memory.get("previous_valuation", {})
        snapshot = MappingProxyType(dict(previous) if isinstance(previous, Mapping) else {})
        context = _LabelingContext(
            env,
            MappingProxyType({**self.episode_memory, "previous_valuation": snapshot}),
        )
        values = {name: bool(labeling[name](context)) for name in self.machine.propositions}
        self.episode_memory["previous_valuation"] = dict(values)
        return values


class RewardMachineEnvironment:
    """Small Gym-compatible adapter that combines environment and RM rewards."""

    def __init__(
        self,
        environment: object,
        runtime: RewardMachineRuntime,
        labeling: Mapping[str, Callable[[object], bool]] | str,
        propositions: Sequence[str] | None = None,
    ) -> None:
        self.environment = environment
        self.runtime = runtime
        self.propositions = tuple(propositions or runtime.machine.propositions)
        self.labeling = (
            load_labeling_functions(labeling, self.propositions)
            if isinstance(labeling, str)
            else dict(labeling)
        )
        if set(self.labeling) != set(self.propositions):
            raise RuntimeValidationError(
                "Labeling functions must cover the declared proposition vocabulary"
            )
        self.episode_memory = runtime.episode_memory
        self.execution_evidence: list[dict[str, object]] = []

    def __getattr__(self, name: str):
        return getattr(self.environment, name)

    @property
    def unwrapped(self):
        return getattr(self.environment, "unwrapped", self.environment)

    def reset(self, **kwargs):
        self.runtime.reset()
        self.episode_memory = self.runtime.episode_memory
        self.execution_evidence.clear()
        return self.environment.reset(**kwargs)

    def step(self, action):
        result = self.environment.step(action)
        if len(result) == 5:
            observation, reward, terminated, truncated, info = result
        else:
            observation, reward, terminated, info = result
            truncated = False
        valuation = self.runtime.evaluate_labeling(self.environment, self.labeling)
        rm_step = self.runtime.step(valuation)
        self.execution_evidence.append(
            {
                "valuation": dict(valuation),
                "source": rm_step.source,
                "destination": rm_step.destination,
                "reward": rm_step.reward,
            }
        )
        info = dict(info or {})
        info.update(
            {
                "valuation": valuation,
                "rm_state": rm_step.destination,
                "rm_reward": rm_step.reward,
            }
        )
        return observation, float(reward) + rm_step.reward, terminated, truncated, info


class _LabelingContext:
    """Forward a live environment while exposing resettable episode memory."""

    def __init__(self, environment: object, episode_memory: Mapping[str, object]) -> None:
        self._environment = environment
        self.episode_memory = episode_memory

    def __getattr__(self, name: str):
        try:
            return getattr(self._environment, name)
        except AttributeError:
            unwrapped = getattr(self._environment, "unwrapped", self._environment)
            return getattr(unwrapped, name)

    def __getitem__(self, key):
        return self._environment[key]  # type: ignore[index]


def load_labeling_functions(
    source: str,
    expected_propositions: Sequence[str],
) -> dict[str, Callable[[object], bool]]:
    """Compile generated predicates once in an isolated, documented namespace."""
    if not isinstance(source, str) or not source.strip():
        raise RuntimeValidationError("Labeling source must be nonempty")
    expected = tuple(str(name) for name in expected_propositions)
    if len(set(expected)) != len(expected):
        raise RuntimeValidationError("Labeling proposition vocabulary must be unique")
    try:
        tree = ast.parse(source, filename="labeling.py")
    except SyntaxError as error:
        raise RuntimeValidationError(f"Generated labeling code is invalid: {error}") from error

    functions = _predicate_definitions(tree)
    _check_vocabulary(functions, expected)
    for name, node in functions.items():
        _check_signature(name, node)
        _validate_labeling_ast(node)

    namespace: dict[str, object] = {
        "__builtins__": {name: getattr(builtins, name) for name in _ALLOWED_LABELING_BUILTINS},
    }
    exec(compile(tree, "labeling.py", "exec"), namespace, namespace)  # noqa: S102  approved: AST allow-listed labeling code
    return {name: namespace[name] for name in expected if callable(namespace.get(name))}  # type: ignore[return-value]


def _predicate_definitions(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    """Return the module's predicate definitions; only docstrings may sit beside them."""
    function_nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    duplicate_names = {
        node.name
        for node in function_nodes
        if [item.name for item in function_nodes].count(node.name) > 1
    }
    if duplicate_names:
        raise RuntimeValidationError(
            "Duplicate labeling function(s): " + ", ".join(sorted(duplicate_names))
        )
    if any(
        not isinstance(node, ast.FunctionDef)
        and not (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
        for node in tree.body
    ):
        raise RuntimeValidationError("Labeling code may only contain predicate definitions")
    return {node.name: node for node in function_nodes}


def _check_vocabulary(functions: Mapping[str, ast.FunctionDef], expected: tuple[str, ...]) -> None:
    missing = set(expected) - set(functions)
    extra = set(functions) - set(expected)
    if missing or extra:
        details = []
        if missing:
            details.append("missing " + ", ".join(sorted(missing)))
        if extra:
            details.append("extra " + ", ".join(sorted(extra)))
        raise RuntimeValidationError(
            "Labeling functions do not match proposition vocabulary: " + "; ".join(details)
        )


def _check_signature(name: str, node: ast.FunctionDef) -> None:
    if (
        len(node.args.posonlyargs) != 0
        or len(node.args.args) != 1
        or node.args.args[0].arg != "env"
        or node.args.vararg
        or node.args.kwarg
        or node.args.kwonlyargs
        or node.args.defaults
        or node.args.kw_defaults
        or node.args.args[0].annotation
        or node.returns
        or node.decorator_list
    ):
        raise RuntimeValidationError(f"Labeling function {name!r} must accept exactly env")


class _LabelingSafetyVisitor(ast.NodeVisitor):
    """Reject generated predicate syntax outside the read-only labeling contract."""

    def __init__(self) -> None:
        self._locals: dict[str, bool] = {}

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load) and node.id not in {
            "env",
            *_ALLOWED_LABELING_BUILTINS,
            *self._locals,
        }:
            raise RuntimeValidationError(f"Labeling code references unknown name {node.id!r}")

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("_") or not self._is_env_derived(node.value):
            raise RuntimeValidationError(
                "Labeling code may only access public environment attributes"
            )
        self.visit(node.value)

    def _is_env_derived(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Name):
            return node.id == "env" or self._locals.get(node.id, False)
        if isinstance(node, ast.Attribute):
            return self._is_env_derived(node.value)
        if isinstance(node, ast.Call):
            return (
                isinstance(node.func, ast.Attribute)
                and not node.func.attr.startswith("_")
                and node.func.attr not in _MUTATING_ENV_METHODS
                and self._is_env_derived(node.func.value)
            )
        if isinstance(node, ast.Subscript):
            return self._is_env_derived(node.value)
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return any(self._is_env_derived(item) for item in node.elts)
        if isinstance(node, ast.Dict):
            return any(
                self._is_env_derived(item)
                for item in (*node.keys, *node.values)
                if item is not None
            )
        return False

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            if node.func.id not in _ALLOWED_LABELING_BUILTINS:
                raise RuntimeValidationError(f"Labeling code may not call {node.func.id!r}")
        elif isinstance(node.func, ast.Attribute):
            if _attribute_root(node.func) != "env" or node.func.attr.startswith("_"):
                raise RuntimeValidationError(
                    "Labeling code may only call documented environment methods"
                )
            if node.func.attr in _MUTATING_ENV_METHODS:
                raise RuntimeValidationError(
                    f"Labeling code may not call mutating method {node.func.attr!r}"
                )
        else:
            raise RuntimeValidationError(
                "Labeling code may only call approved built-ins or environment methods"
            )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        if len(node.targets) != 1:
            raise RuntimeValidationError("Labeling predicates may only assign fresh local names")
        target = node.targets[0]
        names = self._assignment_names(target)
        if any(
            name in {"env", "previous_valuation", *_ALLOWED_LABELING_BUILTINS} for name in names
        ):
            raise RuntimeValidationError("Labeling predicates may not rebind environment state")
        if any(name in self._locals for name in names):
            raise RuntimeValidationError("Labeling predicates may only assign fresh local names")
        self.visit(node.value)
        self._collect_target_names(target, self._is_env_derived(node.value))

    def _assignment_names(self, node: ast.AST) -> tuple[str, ...]:
        if isinstance(node, ast.Name):
            return (node.id,)
        if isinstance(node, (ast.List, ast.Tuple)):
            names = tuple(name for item in node.elts for name in self._assignment_names(item))
            if len(set(names)) != len(names):
                raise RuntimeValidationError(
                    "Labeling predicates may only assign fresh local names"
                )
            return names
        raise RuntimeValidationError("Labeling predicates may only assign fresh local names")

    visit_AnnAssign = visit_Assign
    visit_AugAssign = visit_Assign
    visit_Delete = visit_Assign
    visit_NamedExpr = visit_Assign

    def _reject_control_flow(self, _node: ast.AST) -> None:
        raise RuntimeValidationError("Labeling predicates may only read environment state")

    visit_ClassDef = _reject_control_flow
    visit_For = _reject_control_flow
    visit_While = _reject_control_flow
    visit_With = _reject_control_flow
    visit_AsyncWith = _reject_control_flow
    visit_Try = _reject_control_flow
    visit_Raise = _reject_control_flow
    visit_Yield = _reject_control_flow
    visit_YieldFrom = _reject_control_flow
    visit_Await = _reject_control_flow
    visit_Match = _reject_control_flow
    visit_Global = _reject_control_flow
    visit_Nonlocal = _reject_control_flow

    def visit_FunctionDef(self, _node: ast.FunctionDef) -> None:
        raise RuntimeValidationError("Labeling predicates may not define nested functions")

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, _node: ast.Lambda) -> None:
        raise RuntimeValidationError("Labeling predicates may not define lambdas")

    def visit_Import(self, _node: ast.Import) -> None:
        raise RuntimeValidationError("Labeling code may not import modules")

    visit_ImportFrom = visit_Import

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.visit(node.iter)
        derived = self._is_env_derived(node.iter)
        self._collect_target_names(node.target, derived)
        self.visit(node.target)
        for condition in node.ifs:
            self.visit(condition)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension_expression(node, node.elt)

    visit_SetComp = visit_ListComp
    visit_GeneratorExp = visit_ListComp

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension_expression(node, node.key, node.value)

    def _visit_comprehension_expression(self, node: ast.AST, *expressions: ast.AST) -> None:
        generators = node.generators
        for generator in generators:
            self.visit(generator.iter)
            self._collect_target_names(generator.target, self._is_env_derived(generator.iter))
            self.visit(generator.target)
            for condition in generator.ifs:
                self.visit(condition)
        for expression in expressions:
            self.visit(expression)

    def _collect_target_names(self, node: ast.AST, derived: bool) -> None:
        for item in ast.walk(node):
            if isinstance(item, ast.Name):
                self._locals[item.id] = derived


def _attribute_root(node: ast.Attribute) -> str | None:
    value: ast.AST = node
    while isinstance(value, ast.Attribute):
        value = value.value
    return value.id if isinstance(value, ast.Name) else None


def _validate_labeling_ast(function: ast.FunctionDef) -> None:
    visitor = _LabelingSafetyVisitor()
    for statement in function.body:
        if (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        ):
            continue
        visitor.visit(statement)


def _complete_valuation(
    valuation: Mapping[str, bool], propositions: Sequence[str]
) -> dict[str, bool]:
    values = {str(name).lower(): bool(value) for name, value in valuation.items()}
    missing = [name for name in propositions if name.lower() not in values]
    if missing:
        raise RuntimeValidationError(
            "Complete valuation is missing proposition(s): " + ", ".join(missing)
        )
    return {name.lower(): values[name.lower()] for name in propositions}
