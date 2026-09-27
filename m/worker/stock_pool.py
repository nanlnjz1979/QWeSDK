"""Read the stock universe from strategy source before market data is loaded."""

from __future__ import annotations

import ast

from m.worker.protocol import normalize_symbols


class StockPoolError(ValueError):
    """A stock universe declared by the strategy could not be used."""


def declared_stock_pool(code: str) -> list[str] | None:
    """Return a module-level STOCK_POOL list, or None when the strategy does not assign one."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    for node in tree.body:
        value = _assigned_value(node, "STOCK_POOL")
        if value is None:
            continue
        return normalize_symbols(_literal_strings(value))
    return None


def defines_select_stocks(code: str) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    return any(isinstance(node, ast.FunctionDef) and node.name == "select_stocks" for node in tree.body)


def coerce_stock_codes(value: object) -> list[str]:
    if isinstance(value, str):
        raw = [value]
    elif isinstance(value, list):
        raw = []
        for item in value:
            if isinstance(item, str):
                raw.append(item)
            elif isinstance(item, dict) and isinstance(item.get("code"), str):
                raw.append(item["code"])
            else:
                raise ValueError("select_stocks 必须返回股票代码")
    else:
        raise ValueError("select_stocks 必须返回股票代码")
    return normalize_symbols(raw)


def _assigned_value(node: ast.AST, name: str) -> ast.AST | None:
    if isinstance(node, ast.Assign):
        if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return node.value
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
        return node.value
    return None


def _literal_strings(node: ast.AST) -> list[str]:
    if not isinstance(node, (ast.List, ast.Tuple)):
        raise ValueError("STOCK_POOL 必须是字符串列表")
    values: list[str] = []
    for element in node.elts:
        if not isinstance(element, ast.Constant) or not isinstance(element.value, str):
            raise ValueError("STOCK_POOL 必须是字符串列表")
        values.append(element.value)
    return values
