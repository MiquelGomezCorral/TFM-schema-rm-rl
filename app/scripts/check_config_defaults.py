"""Fail when a function parameter repeats the literal default of a CONFIG field.

Usage: python check_config_defaults.py CONFIG_PATH FILE...
"""

import ast
import sys
from pathlib import Path

NOT_LITERAL = object()  # sentinel: None is a valid literal default


def literal_value(node: ast.expr | None) -> object:
    if node is None:
        return NOT_LITERAL
    try:
        return ast.literal_eval(node)
    except ValueError:
        return NOT_LITERAL


def config_defaults(config_path: str) -> dict[str, object]:
    tree = ast.parse(Path(config_path).read_text(encoding="utf-8"))
    defaults: dict[str, object] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                value = literal_value(stmt.value)
                if value is not NOT_LITERAL:
                    defaults[stmt.target.id] = value
    return defaults


def check_file(path: str, defaults: dict[str, object]) -> int:
    hits = 0
    for node in ast.walk(ast.parse(Path(path).read_text(encoding="utf-8"))):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        args = node.args
        positional = reversed(args.posonlyargs + args.args)
        pairs = list(zip(positional, reversed(args.defaults), strict=False))
        pairs += zip(args.kwonlyargs, args.kw_defaults, strict=True)
        for arg, default in pairs:
            if arg.arg in defaults and literal_value(default) == defaults[arg.arg]:
                print(
                    f"{path}:{arg.lineno}: parameter '{arg.arg}' repeats the CONFIG default; "
                    "take it from CONFIG"
                )
                hits += 1
    return hits


def main(argv: list[str]) -> int:
    defaults = config_defaults(argv[1])
    hits = sum(check_file(path, defaults) for path in argv[2:])
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
