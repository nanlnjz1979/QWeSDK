import json
from datetime import datetime, timezone

from gateway.backtest_store import BacktestStore


def test_store_reloads_run_status_events_and_result(tmp_path):
    database = tmp_path / "runs.sqlite3"
    spec = {"runId": "bt-1", "schemaVersion": "1.0", "initialCapital": 100000}
    store = BacktestStore(database)

    store.create_run("bt-1", spec, status="queued")
    store.record_event("bt-1", {"sequence": 1, "type": "queued", "payload": {"progress": 0}})
    store.record_event("bt-1", {"sequence": 2, "type": "running", "payload": {"progress": 5}})
    result = {"status": "succeeded", "summary": {"totalReturn": 0.12}}
    store.save_result("bt-1", result)

    reloaded = BacktestStore(database)
    status = reloaded.get_status("bt-1")

    assert status["runId"] == "bt-1"
    assert status["status"] == "succeeded"
    assert [event["sequence"] for event in status["events"]] == [1, 2]
    assert reloaded.get_result("bt-1") == result


def test_store_ignores_duplicate_event_sequence(tmp_path):
    store = BacktestStore(tmp_path / "runs.sqlite3")
    store.create_run("bt-1", {"runId": "bt-1"}, status="queued")
    event = {"sequence": 1, "type": "queued", "payload": {}}

    store.record_event("bt-1", event)
    store.record_event("bt-1", dict(event, type="running"))

    assert store.get_status("bt-1")["events"] == [event]


def test_store_counts_gateway_operational_summary_by_status_and_failure_window(tmp_path):
    store = BacktestStore(tmp_path / "runs.sqlite3")
    for run_id in ("bt-queued-1", "bt-queued-2", "bt-running", "bt-failed-recent", "bt-failed-old"):
        store.create_run(run_id, {"runId": run_id}, status="queued")

    now = datetime(2026, 8, 30, 10, 0, tzinfo=timezone.utc)
    with store._connect() as connection:
        connection.execute("UPDATE backtest_runs SET status = 'running' WHERE run_id = ?", ("bt-running",))
        connection.execute(
            "UPDATE backtest_runs SET status = 'failed', updated_at = ? WHERE run_id = ?",
            ("2026-08-30T09:00:00Z", "bt-failed-recent"),
        )
        connection.execute(
            "UPDATE backtest_runs SET status = 'failed', updated_at = ? WHERE run_id = ?",
            ("2026-08-28T09:00:00Z", "bt-failed-old"),
        )

    assert store.get_operational_summary(now) == {
        "queuedTasks": 2,
        "runningTasks": 1,
        "failedTasksLast24h": 1,
    }
