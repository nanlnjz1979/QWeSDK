import importlib


__all__ = ["DBMgr"]


def __getattr__(name):
    """按需加载 DuckDB 连接管理器，允许工具模块独立使用。"""
    if name != "DBMgr":
        raise AttributeError(f"module 'm.db' has no attribute {name!r}")

    manager = importlib.import_module(f"{__name__}.dbmgr").DBMgr
    globals()[name] = manager
    return manager
