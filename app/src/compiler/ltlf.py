"""Serialize the pylogics subset emitted by IBM DECLARE templates."""

from pylogics.syntax.base import And, Formula, Implies, Not, Or
from pylogics.syntax.ltl import Always, Atomic, Eventually, Next, Until


def to_flat_syntax(formula: Formula) -> str:
    """Serialize a supported pylogics LTLf AST with full parentheses."""
    if isinstance(formula, Atomic):
        return formula.name
    if isinstance(formula, Not):
        return f"(~{to_flat_syntax(formula.argument)})"
    if isinstance(formula, Next):
        return f"(X{to_flat_syntax(formula.argument)})"
    if isinstance(formula, Eventually):
        return f"(F{to_flat_syntax(formula.argument)})"
    if isinstance(formula, Always):
        return f"(G{to_flat_syntax(formula.argument)})"
    if isinstance(formula, Until):
        return _serialize_binary(formula, "U")
    if isinstance(formula, Implies):
        return _serialize_binary(formula, "->")
    if isinstance(formula, And):
        return _serialize_binary(formula, "&")
    if isinstance(formula, Or):
        return _serialize_binary(formula, "|")
    raise TypeError(f"Unsupported pylogics node: {type(formula).__name__}")


def _serialize_binary(formula: Formula, operator: str) -> str:
    operands = tuple(formula.operands)
    if len(operands) < 2:
        raise ValueError(f"{type(formula).__name__} requires at least two operands")
    serialized = to_flat_syntax(operands[-1])
    for operand in reversed(operands[:-1]):
        serialized = f"({to_flat_syntax(operand)}{operator}{serialized})"
    return serialized
