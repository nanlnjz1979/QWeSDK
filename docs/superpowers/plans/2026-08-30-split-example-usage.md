# Split Example Usage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add separate, short-range V1 and V2 QWeSDK examples without changing the existing example file.

**Architecture:** Create two standalone scripts that each contain the small KDJ strategy, a three-stock input pool, a short daily data range, and the existing V1 data pipeline. The only execution difference is the final trader entry point: `m.trader.v1` versus `m.trader.v2`.

**Tech Stack:** Python, QWeSDK `m.selector`/`m.input`/`m.extract_data`, `m.trader.v1`, `m.trader.v2`, pytest.

## Global Constraints

- Do not modify `example_usage.py`.
- Do not add a shared common module.
- Do not add command-line arguments.
- Use a small explicit stock pool and a short default daily range.
- Keep the examples connected to real QWeSDK data access; do not add mock result values.

---

### Task 1: Add split-example regression checks

**Files:**
- Create: `tests/test_split_examples.py`

- [ ] Add checks that both scripts exist, contain the intended trader entry point, use the same short range and three-stock pool, and do not alter the original example.
- [ ] Run `PYTHONPATH=. .venv/bin/pytest -q tests/test_split_examples.py` and confirm it fails before the scripts exist.

### Task 2: Create standalone V1 and V2 examples

**Files:**
- Create: `example_usage_v1.py`
- Create: `example_usage_v2.py`

- [ ] Copy the strategy callbacks needed by the existing KDJ example into each file.
- [ ] Use `STOCK_POOL = ["000001.SZ", "600000.SH", "600519.SH"]`, `START_DATE = "2022-01-01"`, `END_DATE = "2022-03-31"`, and `BEFORE_START_DAYS = 30`.
- [ ] Build `m.input.v1` and `m.extract_data.v1` from the explicit pool with the existing daily table and KDJ/MACD/Lag expressions.
- [ ] Call `m.trader.v1` in the V1 script and `m.trader.v2` in the V2 script, with `plot_charts=False` and `debug=False` for shorter output.
- [ ] Run the focused regression test and compile both scripts.

### Task 3: Verify the examples and preserve the original

- [ ] Run the QWeSDK full test suite.
- [ ] Compare the original example checksum before and after the change.
- [ ] Run a real data-access smoke check when the local ClickHouse dataset is available; report an empty dataset separately from an execution error.
