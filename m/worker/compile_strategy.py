"""Check strategy source without executing it or opening ClickHouse."""

from __future__ import annotations

import ast
import hashlib
import json
import sys


MAX_CODE_BYTES = 2 * 1024 * 1024
ENTRY_POINTS = {
    "qwesdk_callback_v1": ("initialize", "handle_data"),
    "qwesdk_script_v1": ("main",),
}
MIN_ARGS = {
    "initialize": 1,
    "handle_data": 2,
    "main": 1,
}
FORBIDDEN_IMPORTS = {"os", "subprocess", "socket", "ctypes"}
FORBIDDEN_CALLS = {"exec", "eval", "open", "__import__", "compile"}


def compile_strategy(code: str, entry_point: str = "qwesdk_callback_v1") -> dict:
    source = code if isinstance(code, str) else ""
    entry = entry_point if isinstance(entry_point, str) and entry_point else "qwesdk_callback_v1"
    code_hash = "sha256:" + hashlib.sha256(source.encode("utf-8")).hexdigest()
    if entry not in ENTRY_POINTS:
        message = "不支持的入口类型"
        return _result("error", code_hash, entry, [], [_diagnostic("ENTRY_POINT_UNSUPPORTED", message, None)], message)
    if len(source.encode("utf-8")) > MAX_CODE_BYTES:
        message = "策略代码不能超过 2 MB"
        return _result("error", code_hash, entry, [], [_diagnostic("CODE_TOO_LARGE", message, None)], message)
    try:
        tree = ast.parse(source)
        compile(tree, "<strategy>", "exec")
    except SyntaxError as exc:
        message = f"语法错误: {exc.msg}"
        return _result("error", code_hash, entry, [], [_diagnostic("SYNTAX_ERROR", message, exc.lineno)], message)
    except ValueError as exc:
        message = f"语法错误: {exc}"
        return _result("error", code_hash, entry, [], [_diagnostic("SYNTAX_ERROR", message, None)], message)

    diagnostics = [*_import_diagnostics(tree), *_call_diagnostics(tree)]
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    async_names = {node.name: node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)}
    symbols: list[str] = []
    for name in ENTRY_POINTS[entry]:
        if name in async_names:
            diagnostics.append(_diagnostic("ENTRY_POINT_NOT_CALLABLE", f"{name} 必须是普通函数", async_names[name].lineno))
            continue
        function = functions.get(name)
        if function is None:
            diagnostics.append(_diagnostic("ENTRY_POINT_MISSING", f"策略源码必须提供 {name}", None))
            continue
        if not _accepts(function, MIN_ARGS[name]):
            diagnostics.append(_diagnostic("ENTRY_POINT_NOT_CALLABLE", f"{name} 参数个数不正确", function.lineno))
            continue
        symbols.append(name)
    if diagnostics:
        return _result("error", code_hash, entry, symbols, diagnostics, diagnostics[0]["message"])
    return _result("success", code_hash, entry, symbols, [], "编译成功")


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    code = payload.get("code")
    entry_point = payload.get("entryPoint")
    json.dump(
        compile_strategy("" if not isinstance(code, str) else code,
                         "qwesdk_callback_v1" if not isinstance(entry_point, str) else entry_point),
        sys.stdout,
        ensure_ascii=False,
    )
    sys.stdout.write("\n")
    return 0


def _import_diagnostics(tree: ast.AST) -> list[dict]:
    diagnostics = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in FORBIDDEN_IMPORTS:
                    diagnostics.append(_diagnostic("IMPORT_FORBIDDEN", f"禁止导入 {alias.name}", node.lineno))
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            if root in FORBIDDEN_IMPORTS:
                diagnostics.append(_diagnostic("IMPORT_FORBIDDEN", f"禁止导入 {node.module}", node.lineno))
    return diagnostics


def _call_diagnostics(tree: ast.AST) -> list[dict]:
    diagnostics = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if name in FORBIDDEN_CALLS:
            diagnostics.append(_diagnostic("CALL_FORBIDDEN", f"禁止调用 {name}", node.lineno))
    return diagnostics


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _accepts(function: ast.FunctionDef, count: int) -> bool:
    positional = len(function.args.posonlyargs) + len(function.args.args)
    defaults = len(function.args.defaults)
    required = positional - defaults
    if required > count:
        return False
    return bool(function.args.vararg) or positional >= count


def _diagnostic(code: str, message: str, line: int | None) -> dict:
    return {"code": code, "message": message, "line": line}


def _result(status: str, code_hash: str, entry_point: str, symbols: list[str], diagnostics: list[dict], message: str) -> dict:
    return {
        "status": status,
        "codeHash": code_hash,
        "entryPoint": entry_point,
        "symbols": symbols,
        "diagnostics": diagnostics,
        "message": message,
    }


if __name__ == "__main__":
    raise SystemExit(main())
