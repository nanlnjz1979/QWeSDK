import importlib


__all__ = ["ExpressionAnalyzer", "TradingCostManager", "TA", "ArrayManager"]
_MODULES = {
    "ExpressionAnalyzer": "expression_analyzer",
    "TradingCostManager": "trading_cost_manager",
    "TA": "ta_engine",
    "ArrayManager": "array_manager",
}


def __getattr__(name):
    """只在访问具体组件时加载其第三方依赖。"""
    module_name = _MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module 'm.core' has no attribute {name!r}")

    component = getattr(importlib.import_module(f"{__name__}.{module_name}"), name)
    globals()[name] = component
    return component
