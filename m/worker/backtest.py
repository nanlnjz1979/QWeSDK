"""Run a validated QWeSDK callback strategy through TraderV2."""

from __future__ import annotations

import types
from datetime import date, datetime, timezone
from dataclasses import dataclass, field
from datetime import timedelta

from m.data_access.catalog import load_dataset
from m.data_access.catalog import create_data_loader, _read_manifest
from m.core.expression_analyzer import ExpressionAnalyzer
from m.core.ta_engine import TA
from m.trader.trader_v2 import TraderV2
from m.worker.stock_pool import StockPoolError, coerce_stock_codes, declared_stock_pool, defines_select_stocks


DEFAULT_EXTRACT_EXPRESSIONS = (
    "kdj(close,k,d,j)",
    "lag(k,1,k_lag1)",
    "lag(d,1,d_lag1)",
    "lag(j,1,j_lag1)",
)


def _date(value: str) -> date:
    return date.fromisoformat(value)


def load_script_module(code: str, entry_point: str = "qwesdk_callback_v1") -> types.ModuleType:
    module = types.ModuleType("helix_strategy")
    module.__file__ = "<helix-strategy>"
    exec(compile(code, module.__file__, "exec"), module.__dict__, module.__dict__)
    required = ("main",) if entry_point == "qwesdk_script_v1" else ("initialize", "handle_data")
    for name in required:
        if not callable(getattr(module, name, None)):
            signature = "main(runtime)" if name == "main" else f"{name}(context, data)"
            raise ValueError(f"strategy must define {signature}")
    return module


def _module_from_code(code: str, entry_point: str = "qwesdk_callback_v1") -> types.ModuleType:
    return load_script_module(code, entry_point)


@dataclass(frozen=True)
class BacktestRuntime:
    dataset: dict
    manifest: dict
    data_loader: object
    start_date: date
    end_date: date
    warmup_start_date: date
    before_start_days: int
    adjustment_mode: str
    symbols: tuple[str, ...] | None = None
    parameters: dict = field(default_factory=dict)

    def load_data(self, symbols, fields=None):
        """按冻结的回测区间加载数据，自动包含指标计算所需的预热区间。"""
        requested_symbols = list(symbols)
        if self.symbols is not None and any(symbol not in self.symbols for symbol in requested_symbols):
            raise ValueError("strategy requested a symbol outside the RunSpec scope")
        return self.data_loader.load_daily(
            requested_symbols, self.warmup_start_date, self.end_date, fields=fields,
            adjustment_mode=self.adjustment_mode,
        )

    def extract_data(self, symbols, expressions=None, fields=None):
        """使用受 Manifest 约束的 DataLoader 取数，再执行指标表达式。"""
        frames = self.load_data(symbols, fields=fields)
        analyzer = ExpressionAnalyzer()
        ta_engine = TA()
        expressions = list(expressions or DEFAULT_EXTRACT_EXPRESSIONS)
        if not all(isinstance(expression, str) for expression in expressions):
            raise ValueError("runtime extract expressions must be strings")
        return {
            symbol: _apply_expressions(frame, expressions, analyzer, ta_engine)
            for symbol, frame in frames.items()
        }


def build_script_runtime(
    dataset: dict,
    date_range: dict,
    *,
    manifest: dict,
    data_loader: object,
    before_start_days: int = 0,
    symbols: list[str] | None = None,
    parameters: dict | None = None,
) -> BacktestRuntime:
    start = _date(date_range["start"])
    end = _date(date_range["end"])
    if start > end:
        raise ValueError("runSpec.dateRange is invalid")
    days = int(before_start_days)
    if days < 0:
        raise ValueError("before_start_days must be non-negative")
    return BacktestRuntime(
        dataset=dataset,
        manifest=manifest,
        data_loader=data_loader,
        start_date=start,
        end_date=end,
        warmup_start_date=start - timedelta(days=days),
        before_start_days=days,
        adjustment_mode=dataset.get("adjustmentMode", "none"),
        symbols=tuple(symbols) if symbols is not None else None,
        parameters=dict(parameters or {}),
    )


def _noop(*_args, **_kwargs):
    return None


def _iso(value) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _trade_iso(value) -> str:
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc).isoformat()
    return _iso(value)


def _trade(record: dict) -> dict:
    side = record.get("direction")
    quantity = record.get("volume") or 0
    price = record.get("price") or 0
    gross_amount = float(price) * int(quantity)
    commission = float(record.get("commission", 0) or 0)
    tax = float(record.get("stamp_duty", 0) or 0)
    transfer_fee = float(record.get("transfer_fee", 0) or 0)
    total = record.get("total_cost") if side == "buy" else record.get("total_revenue")
    return {
        "tradeId": str(record.get("trade_id") or record.get("order_id") or record.get("timestamp")),
        "executedAt": _trade_iso(record.get("timestamp")),
        "symbol": record.get("stock_code"),
        "side": record.get("direction"),
        "positionEffect": "open" if side == "buy" else "close" if side == "sell" else "unknown",
        "quantity": quantity,
        "price": price,
        "grossAmount": gross_amount,
        "commission": commission,
        "tax": tax,
        "transferFee": transfer_fee,
        "netCashFlow": -float(total or 0) if side == "buy" else float(total or 0),
    }


def _extract_expressions(run_spec: dict) -> list[str]:
    extraction = run_spec.get("dataExtraction") or {}
    expressions = extraction.get("exprMutates")
    if expressions is None:
        expressions = (run_spec.get("parameters") or {}).get("exprMutates")
    if expressions is None:
        expressions = list(DEFAULT_EXTRACT_EXPRESSIONS)
    if not isinstance(expressions, list) or not all(isinstance(item, str) for item in expressions):
        raise ValueError("dataExtraction.exprMutates must be a list of expressions")
    return expressions


def _prepare_dataset(dataset: dict, run_spec: dict) -> dict:
    """Apply the local equivalent of m.extract_data.v1 to the immutable dataset."""
    analyzer = ExpressionAnalyzer()
    ta_engine = TA()
    prepared = {}
    for symbol, frame in dataset.items():
        prepared[symbol] = _apply_expressions(
            frame, _extract_expressions(run_spec), analyzer, ta_engine
        )
    return prepared


def _apply_expressions(frame, expressions, analyzer, ta_engine):
    current = frame.copy().sort_values("date").reset_index(drop=True)
    for expression in expressions:
        current = analyzer.parse_and_execute(expression, current, ta_engine)
    return current


def _return_candle(snapshot: dict) -> dict:
    close_return = float(snapshot.get("close_return", float(snapshot.get("cumulative_return", 0)) / 100))
    open_return = snapshot.get("open_return")
    open_return = close_return if open_return is None else float(open_return)
    high_return = snapshot.get("high_return")
    low_return = snapshot.get("low_return")
    high_return = max(open_return, close_return) if high_return is None else float(high_return)
    low_return = min(open_return, close_return) if low_return is None else float(low_return)
    return {
        "date": _iso(snapshot.get("date")),
        "open": open_return,
        "high": max(high_return, open_return, close_return),
        "low": min(low_return, open_return, close_return),
        "close": close_return,
    }


def _equity(snapshot: dict) -> dict:
    return {
        "date": _iso(snapshot.get("date")),
        "normalizedValue": snapshot.get("total_value", 0) / snapshot.get("initial_capital", 1),
        "marketValue": snapshot.get("total_value"),
        "dailyReturn": snapshot.get("daily_return", 0) / 100,
        "cash": snapshot.get("cash"),
        "positionValue": snapshot.get("positions_value", snapshot.get("position_value")),
    }


def resolve_run_symbols(run_spec: dict) -> list[str]:
    """Prefer the strategy universe over codes supplied with the backtest request."""
    code = run_spec.get("strategyCode") or ""
    entry_point = run_spec.get("strategyEntryPoint", "qwesdk_callback_v1")
    if defines_select_stocks(code):
        module = _module_from_code(code, entry_point)
        selected = coerce_stock_codes(module.select_stocks())
        if not selected:
            raise StockPoolError("select_stocks 没有返回股票代码")
        return selected
    declared = declared_stock_pool(code)
    if declared is not None:
        if not declared:
            raise StockPoolError("STOCK_POOL 不能为空")
        return declared
    requested = list(run_spec.get("symbols") or [])
    if not requested:
        raise StockPoolError("策略未声明股票池")
    return requested


def run_backtest_spec(run_spec: dict, event_stream) -> dict:
    def _log(stage: str, message: str, level: str = "info") -> None:
        event_stream.emit("log", level=level, stage=stage, message=message)

    event_stream.emit("queued", progress=0, stage="queued")
    _log("queued", "任务已提交，等待执行")
    event_stream.emit("running", progress=5, stage="loading_data")
    _log("loading_data", "正在读取数据")

    run_spec = dict(run_spec)
    run_spec["symbols"] = resolve_run_symbols(run_spec)
    date_range = run_spec["dateRange"]
    entry_point = run_spec.get("strategyEntryPoint", "qwesdk_callback_v1")
    manifest = _read_manifest(run_spec["dataset"])
    module = _module_from_code(run_spec["strategyCode"], entry_point)
    dataset_read_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if entry_point == "qwesdk_script_v1":
        runtime = build_script_runtime(
            run_spec["dataset"],
            date_range,
            manifest=manifest,
            data_loader=create_data_loader(run_spec["dataset"]),
            before_start_days=int((run_spec.get("parameters") or {}).get("beforeStartDays", 0)),
            symbols=run_spec["symbols"],
            parameters=run_spec.get("parameters") or {},
        )
        engine = module.main(runtime)
        if not hasattr(engine, "run") or not hasattr(engine, "get_results"):
            raise ValueError("strategy main(runtime) must return a TraderV2 engine")
        dataset = None
    else:
        dataset = _prepare_dataset(
            load_dataset(
                run_spec["dataset"],
                start_date=date_range["start"],
                end_date=date_range["end"],
                symbols=run_spec["symbols"],
            ),
            run_spec,
        )
        engine = None
    initial_capital = float(run_spec["initialCapital"])
    if engine is None:
        engine = TraderV2(
            data=dataset,
            start_date=_date(date_range["start"]),
            end_date=_date(date_range["end"]),
            initialize=module.initialize,
            before_trading_start=getattr(module, "before_trading_start", _noop),
            handle_data=module.handle_data,
            handle_tick=_noop,
            handle_trade=getattr(module, "handle_trade", _noop),
            handle_order=getattr(module, "handle_order", _noop),
            after_trading=getattr(module, "after_trading", _noop),
            after_backtest=getattr(module, "after_backtest", None),
            capital_base=initial_capital,
            frequency="daily",
            benchmark=run_spec.get("benchmark"),
            plot_charts=False,
            debug=False,
        )
    engine.context["parameters"] = dict(run_spec.get("parameters") or {})
    event_stream.emit("progress", progress=10, stage="running")
    _log("running", "开始回测")

    def _report_dates(completed: int, total: int) -> None:
        if total <= 0:
            return
        event_stream.emit(
            "progress",
            progress=min(90, 10 + int(80 * completed / total)),
            stage="running",
            completedDates=completed,
            totalDates=total,
        )
        _log("running", f"正在回测 {completed}/{total}")

    engine.progress_callback = _report_dates
    engine.run()
    raw = engine.get_results()
    curve = list(raw.get("equity_curve") or [])
    for snapshot in curve:
        snapshot.setdefault("initial_capital", initial_capital)
    total_return = float(raw.get("total_return", 0)) / 100
    summary = {
        "startValue": initial_capital,
        "endValue": raw.get("final_value"),
        "totalPnl": raw.get("final_value", initial_capital) - initial_capital,
        "totalReturn": total_return,
        "maxDrawdown": float(raw.get("max_drawdown", 0)) / 100,
        "sharpeRatio": raw.get("sharpe_ratio"),
        "tradeCount": int(raw.get("trade_count", 0)),
    }
    series = {
        "equityCurve": [_equity(snapshot) for snapshot in curve],
        "benchmarkCurve": [],
        "drawdownCurve": [
            {"date": _iso(snapshot.get("date")), "drawdown": float(snapshot.get("drawdown", 0)) / 100}
            for snapshot in curve
        ],
        "trades": [_trade(record) for record in (raw.get("trades") or [])],
        "positions": [],
        "returnCandles": [_return_candle(snapshot) for snapshot in curve],
    }
    event_stream.emit("progress", progress=90, stage="persisting")
    event_stream.emit("persisting", progress=95, stage="persisting")
    _log("persisting", "正在保存回测结果")
    result = {
        "schemaVersion": "1.0",
        "status": "succeeded",
        "summary": summary,
        "series": series,
        "warnings": [],
        "artifacts": [],
        "runtime": {
            "qwesdkVersion": run_spec.get("runtime", {}).get("qwesdkVersion"),
            "workerImageDigest": run_spec.get("runtime", {}).get("workerImageDigest"),
            "datasetManifestHash": run_spec["dataset"]["manifestHash"],
            "datasetStorageMode": manifest.get("storageMode", "immutable_table"),
            "datasetReadAt": dataset_read_at,
        },
    }
    _log("completed", "回测完成")
    event_stream.emit("succeeded", progress=100, stage="completed")
    return result
