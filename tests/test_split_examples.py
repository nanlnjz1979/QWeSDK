from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_split_examples_are_standalone_and_keep_short_defaults():
    v1 = (ROOT / "example_usage_v1.py").read_text(encoding="utf-8")
    v2 = (ROOT / "example_usage_v2.py").read_text(encoding="utf-8")

    assert 'END_DATE = "2022-03-31"' in v1
    assert "def main(runtime):" in v2

    for source in (v1, v2):
        if source is v1:
            assert 'START_DATE = "2022-01-01"' in source
            assert "BEFORE_START_DAYS = 30" in source
        assert "example_usage_common" not in source
        assert "argparse" not in source

    assert "m.trader.v1(" in v1
    assert "m.trader.v2(" in v2
    assert (ROOT / "example_usage.py").exists()


def test_v2_uses_runtime_data_loader_and_frozen_dates():
    source = (ROOT / "example_usage_v2.py").read_text(encoding="utf-8")

    assert "def main(runtime):" in source
    assert "runtime.extract_data(" in source
    assert "runtime.start_date" in source
    assert "runtime.end_date" in source
    assert "backtest_only=True" in source
