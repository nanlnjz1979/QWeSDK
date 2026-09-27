import importlib.util
from pathlib import Path


def _load_check():
    path = Path(__file__).resolve().parents[2] / "scripts" / "real_clickhouse_daily_check.py"
    spec = importlib.util.spec_from_file_location("real_clickhouse_daily_check", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_check_refuses_to_run_without_opt_in(monkeypatch):
    monkeypatch.delenv("QWESDK_REAL_CLICKHOUSE", raising=False)
    real_clickhouse_daily_check = _load_check()
    assert real_clickhouse_daily_check.main([]) == 2
