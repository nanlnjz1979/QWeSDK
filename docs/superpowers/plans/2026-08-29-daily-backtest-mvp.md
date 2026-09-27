# 日线回测 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect a unified backtest workspace to the real daily backtest execution chain and render persisted results in the browser.

**Architecture:** Add a SQLite-backed run registry to Gateway, expose same-origin browser APIs, and serve a static workspace page. Production submissions continue through Celery; local development can execute the existing worker task in a background thread, preserving sandbox and TraderV2 behavior.

**Tech Stack:** Python 3.11 standard-library HTTP server, SQLite, existing Celery/sandbox/TraderV2, vanilla HTML/CSS/JavaScript and SVG.

## Global Constraints

- Only daily data is supported in this MVP.
- Core metrics and chart data must come from the backend result; frontend must not contain fabricated result values.
- Strategy code must pass the existing entry-point and SHA-256 validation.
- Existing user changes in `docker/`, `gateway/`, `data/`, and untracked runtime files must be preserved.
- Every behavior change starts with a failing test.

---

### Task 1: Persist Backtest Runs

**Files:**
- Create: `gateway/backtest_store.py`
- Modify: `gateway/gateway_service.py`
- Test: `gateway/tests/test_backtest_store.py`

**Interfaces:**
- `BacktestStore.create_run(run_id, spec, status) -> None`
- `BacktestStore.record_event(run_id, event) -> None`
- `BacktestStore.save_result(run_id, result) -> None`
- `BacktestStore.get_status(run_id) -> dict | None`
- `BacktestStore.get_result(run_id) -> dict | None`

- [ ] Write failing tests for persistence, ordered events, and result reload.
- [ ] Run `pytest gateway/tests/test_backtest_store.py -q` and confirm the missing store API fails.
- [ ] Implement one SQLite store with JSON payloads, upserts, and per-operation connections.
- [ ] Add GatewayService helpers that write submission events and bridge results into the store.
- [ ] Run the focused store and existing gateway tests.

### Task 2: Add Browser Backtest API

**Files:**
- Modify: `gateway/app.py`
- Modify: `gateway/gateway_service.py`
- Test: `gateway/tests/test_app_api.py`

**Interfaces:**
- `POST /api/backtests` creates a complete run spec from form input.
- `GET /api/backtests/{run_id}` returns persisted status/events.
- `GET /api/backtests/{run_id}/result` returns the standard result.
- `GET /api/datasets` returns catalog metadata.

- [ ] Write failing handler tests for dataset listing, submission, status, and result responses.
- [ ] Run `pytest gateway/tests/test_app_api.py -q` and verify route failures.
- [ ] Implement request parsing, server-side hash/run ID generation, API responses, and local/queue dispatch.
- [ ] Add validation errors and cancellation response without exposing strategy source in logs.
- [ ] Run focused API and full Python tests.

### Task 3: Build the Workspace Page

**Files:**
- Create: `gateway/static/index.html`
- Create: `gateway/static/app.css`
- Create: `gateway/static/app.js`
- Modify: `gateway/app.py`
- Test: `gateway/tests/test_static_page.py`

**Interfaces:**
- Page loads datasets from `/api/datasets`.
- Form posts to `/api/backtests`.
- Polling reads `/api/backtests/{runId}` and `/result`.
- SVG renderers consume `series.equityCurve` and `series.drawdownCurve` only.

- [ ] Write failing static page tests for required controls and no embedded fake metrics.
- [ ] Run focused static tests and confirm missing page/routes fail.
- [ ] Implement responsive unified workspace styling, state transitions, accessible form controls, SVG charts, trade table, and event log.
- [ ] Serve static assets and SPA root from Gateway.
- [ ] Run static tests and browser smoke checks against a real local run.

### Task 4: End-to-End Real Run Verification

**Files:**
- Modify: `gateway/app.py` only if local runtime defaults need wiring.
- Test: `gateway/tests/test_end_to_end_backtest.py`

- [ ] Write a failing test that submits the fixture dataset and strategy through the API and waits for `succeeded`.
- [ ] Run it to verify the missing end-to-end path fails.
- [ ] Wire local execution to the existing `tasks.run_backtest` task and set repository-safe local data/source defaults.
- [ ] Assert persisted summary, curve, trades, and event progression.
- [ ] Run `pytest -q`, `python -m compileall -q m gateway docker/worker`, and browser screenshots at desktop/mobile sizes.
