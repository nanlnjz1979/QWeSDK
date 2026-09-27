"""Durable state for browser-visible backtest runs."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class BacktestStore:
    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS backtest_runs (
                    run_id TEXT PRIMARY KEY,
                    spec TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0,
                    stage TEXT NOT NULL DEFAULT 'queued',
                    error_code TEXT,
                    result TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS backtest_events (
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event TEXT NOT NULL,
                    PRIMARY KEY (run_id, sequence),
                    FOREIGN KEY (run_id) REFERENCES backtest_runs(run_id)
                )"""
            )

    def create_run(self, run_id: str, spec: dict[str, Any], status: str = "queued") -> None:
        timestamp = _now()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO backtest_runs
                (run_id, spec, status, progress, stage, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (run_id, json.dumps(spec, ensure_ascii=False, separators=(",", ":")), status,
                 0, status, timestamp, timestamp),
            )

    def record_event(self, run_id: str, event: dict[str, Any]) -> None:
        # 事件是状态流：每个事件都会持久化，同时推进返回给浏览器的
        # 状态和进度字段。
        payload = event.get("payload") or {}
        event_type = str(event.get("type") or "log")
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO backtest_events (run_id, sequence, event) VALUES (?, ?, ?)",
                (run_id, int(event.get("sequence", 0)), json.dumps(event, ensure_ascii=False, separators=(",", ":"))),
            )
            connection.execute(
                """UPDATE backtest_runs
                SET status = ?, progress = ?, stage = ?, error_code = ?, updated_at = ?
                WHERE run_id = ?""",
                ("succeeded" if event_type == "succeeded" else "failed" if event_type in {"failed", "timed_out", "cancelled"} else "running",
                 int(payload.get("progress", 0)), str(payload.get("stage") or event_type),
                 payload.get("errorCode"), _now(), run_id),
            )

    def save_result(self, run_id: str, result: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """UPDATE backtest_runs SET status = ?, progress = ?, stage = ?, error_code = ?, result = ?, updated_at = ?
                WHERE run_id = ?""",
                (result.get("status", "failed"), 100 if result.get("status") == "succeeded" else 0,
                 "completed" if result.get("status") == "succeeded" else "failed",
                 result.get("errorCode"), json.dumps(result, ensure_ascii=False, separators=(",", ":")), _now(), run_id),
            )

    def save_error(self, run_id: str, error_code: str, status: str = "failed") -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE backtest_runs SET status = ?, stage = ?, error_code = ?, updated_at = ? WHERE run_id = ?",
                (status, status, error_code, _now(), run_id),
            )

    def get_operational_summary(self, now: datetime) -> dict[str, int]:
        """统计 Gateway 已接收的回测任务，而不是 Redis 的物理队列深度。"""
        current = now.astimezone(timezone.utc)
        cutoff = (current - timedelta(hours=24)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        with self._connect() as connection:
            row = connection.execute(
                """SELECT
                    COALESCE(SUM(CASE WHEN status = 'queued' THEN 1 ELSE 0 END), 0) AS queued_tasks,
                    COALESCE(SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END), 0) AS running_tasks,
                    COALESCE(SUM(CASE WHEN status = 'failed' AND updated_at >= ? THEN 1 ELSE 0 END), 0) AS failed_tasks
                FROM backtest_runs""",
                (cutoff,),
            ).fetchone()
        return {
            "queuedTasks": int(row["queued_tasks"]),
            "runningTasks": int(row["running_tasks"]),
            "failedTasksLast24h": int(row["failed_tasks"]),
        }

    def get_status(self, run_id: str) -> dict[str, Any] | None:
        # 页面只轮询一个已知的 run ID；这里有意没有提供全局任务列表查询，
        # 因此这个存储层不是 Celery 监控看板。
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM backtest_runs WHERE run_id = ?", (run_id,)).fetchone()
            if row is None:
                return None
            events = connection.execute(
                "SELECT event FROM backtest_events WHERE run_id = ? ORDER BY sequence", (run_id,)
            ).fetchall()
        return {
            "runId": row["run_id"],
            "status": row["status"],
            "progress": row["progress"],
            "stage": row["stage"],
            "errorCode": row["error_code"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "events": [json.loads(item["event"]) for item in events],
        }

    def get_spec(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT spec FROM backtest_runs WHERE run_id = ?", (run_id,)).fetchone()
        return json.loads(row["spec"]) if row else None

    def get_result(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT result FROM backtest_runs WHERE run_id = ?", (run_id,)).fetchone()
        return json.loads(row["result"]) if row and row["result"] else None
