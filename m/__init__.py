import importlib


__all__ = ["trader", "input", "extract_data", "selector", "config"]


def __getattr__(name):
    """按需加载功能模块，避免可选的 V1 依赖阻塞基础模块导入。"""
    if name not in __all__:
        raise AttributeError(f"module 'm' has no attribute {name!r}")

    # V1 的 vn.py 依赖只在访问 m.trader 时加载，core 用户无需安装它。
    module = importlib.import_module(f"{__name__}.{name}")
    globals()[name] = module
    return module
