"""Evaluate the small expression language used by SQLQueryBuilder."""

import ast


_ALLOWED_NODES = {
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.keyword,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.BitAnd,
    ast.BitOr,
    ast.And,
    ast.Or,
    ast.UAdd,
    ast.USub,
    ast.Invert,
    ast.Not,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
}


def _validate_tree(tree, namespace):
    """Reject syntax outside the intentionally small expression language."""
    for node in ast.walk(tree):
        if type(node) not in _ALLOWED_NODES:
            if isinstance(node, ast.Attribute):
                raise ValueError("attribute access is not allowed")
            raise ValueError(
                f"unsupported expression node: {type(node).__name__}"
            )

        if isinstance(node, ast.Name) and node.id not in namespace:
            raise ValueError(f"name {node.id!r} is not allowed")

        if isinstance(node, ast.Constant) and not isinstance(
            node.value, (str, int, float, bool, type(None))
        ):
            raise ValueError("constant type is not allowed")

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("function calls must use whitelisted names")
            if node.func.id not in namespace:
                raise ValueError(f"name {node.func.id!r} is not allowed")
            function = namespace.get(node.func.id)
            if not callable(function):
                raise ValueError(f"function {node.func.id!r} is not allowed")
            if any(keyword.arg is None for keyword in node.keywords):
                raise ValueError("starred keyword arguments are not allowed")


def safe_eval(expression, namespace):
    """Evaluate an expression after validating its AST and names."""
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("expression must be a non-empty string")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"invalid expression: {exc.msg}") from exc

    _validate_tree(tree, namespace)
    return eval(compile(tree, "<qwesdk-expression>", "eval"), {"__builtins__": {}}, namespace)
