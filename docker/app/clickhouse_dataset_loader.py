"""通过受 Manifest 约束的窄接口读取 ClickHouse 数据集。"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date, datetime
from typing import Any

import pandas as pd
import requests


IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
REQUIRED_COLUMNS = ("code", "date", "open", "high", "low", "close", "volume")


class DatasetContractError(ValueError):
    """A safe, machine-readable dataset failure for the Worker boundary."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def manifest_hash(manifest: dict[str, Any]) -> str:
    """Hash canonical JSON so equivalent key ordering produces one identity."""
    payload = dict(manifest)
    # The digest is stored in the document for transport, but is excluded from
    # the input so the document does not hash itself recursively.
    payload.pop("manifestHash", None)
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER_RE.fullmatch(value):
        raise DatasetContractError("DATASET_TABLE_MAPPING_INVALID", f"dataset manifest {field} is invalid")
    return value


def _date(value: date | datetime | str, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise DatasetContractError("DATASET_MANIFEST_INVALID", f"dataset {field} is invalid") from exc


def _quoted_identifier(value: str) -> str:
    return "`" + value + "`"


class ClickHouseDatasetLoader:
    def __init__(self, url: str, user: str, password: str, *, session=None, timeout: float = 30.0):
        if not url:
            raise DatasetContractError("CLICKHOUSE_UNAVAILABLE", "ClickHouse connection is not configured")
        self.url = url.rstrip("/")
        self.auth = (user, password)
        self.session = session or requests.Session()
        self.timeout = timeout

    def load_daily(
        self,
        manifest: dict[str, Any],
        symbols: list[str],
        start_date: date | datetime | str,
        end_date: date | datetime | str,
        adjustment_mode: str,
        fields: list[str] | None = None,
    ) -> dict[str, pd.DataFrame]:
        if not isinstance(manifest, dict) or manifest.get("sourceType") != "clickhouse":
            raise DatasetContractError("DATASET_SOURCE_UNSUPPORTED", "dataset source is not clickhouse")
        storage_mode = manifest.get("storageMode")
        if storage_mode not in {"immutable_table", "current_view"}:
            raise DatasetContractError("DATASET_MANIFEST_INVALID", "ClickHouse dataset storageMode is invalid")
        if adjustment_mode not in {"none", "qfq", "hfq"}:
            raise DatasetContractError("DATASET_TABLE_MAPPING_INVALID", "dataset adjustment mode is unsupported")
        if not symbols or not all(isinstance(symbol, str) and symbol for symbol in symbols):
            raise DatasetContractError("DATASET_MANIFEST_INVALID", "dataset symbols are required")

        start = _date(start_date, "startDate")
        end = _date(end_date, "endDate")
        if start > end:
            raise DatasetContractError("DATASET_MANIFEST_INVALID", "dataset date range is invalid")
        coverage = manifest.get("coverage") or {}
        try:
            coverage_start = _date(coverage.get("start"), "coverage.start")
            coverage_end = _date(coverage.get("end"), "coverage.end")
        except DatasetContractError:
            raise DatasetContractError("DATASET_MANIFEST_INVALID", "dataset coverage is invalid") from None
        if start < coverage_start or end > coverage_end:
            raise DatasetContractError("DATASET_COVERAGE_EXCEEDED", "dataset date range is outside manifest coverage")

        components = manifest.get("components")
        daily = components.get("daily") if isinstance(components, dict) else None
        if not isinstance(daily, dict):
            raise DatasetContractError("DATASET_MANIFEST_INVALID", "dataset manifest daily component is missing")
        database = daily.get("database", "default")
        if database != "default":
            raise DatasetContractError("DATASET_TABLE_MAPPING_INVALID", "ClickHouse database must be default")
        database = _identifier(database, "components.daily.database")
        tables = daily.get("tables")
        if not isinstance(tables, dict):
            raise DatasetContractError("DATASET_TABLE_MAPPING_INVALID", "dataset manifest daily tables are missing")
        for adjustment in ("none", "qfq", "hfq"):
            if adjustment not in tables:
                raise DatasetContractError("DATASET_TABLE_MAPPING_INVALID", f"dataset manifest table {adjustment} is missing")
        table = _identifier(tables.get(adjustment_mode), f"components.daily.tables.{adjustment_mode}")
        if fields is not None:
            if not isinstance(fields, list) or not all(isinstance(field, str) for field in fields):
                raise DatasetContractError("DATASET_MANIFEST_INVALID", "dataset fields are invalid")
            if not set(fields).issubset(REQUIRED_COLUMNS):
                raise DatasetContractError("DATASET_MANIFEST_INVALID", "dataset fields are outside the daily protocol")
        # The protocol owns this projection. Manifest columns are deliberately ignored
        # so a user cannot make the Worker select an unapproved ClickHouse field.
        columns = list(REQUIRED_COLUMNS)

        select_columns = ", ".join(_quoted_identifier(column) for column in columns)
        query = (
            f"SELECT {select_columns} FROM {_quoted_identifier(database)}.{_quoted_identifier(table)} "
            "WHERE `code` IN {codes:Array(String)} "
            "AND `date` >= {start_date:DateTime} "
            "AND `date` <= {end_date:DateTime} "
            "ORDER BY `code`, `date`"
        )
        params = {
            "database": database,
            "default_format": "JSONEachRow",
            "param_codes": json.dumps(sorted(set(symbols)), ensure_ascii=False),
            "param_start_date": f"{start.isoformat()} 00:00:00",
            "param_end_date": f"{end.isoformat()} 23:59:59",
        }
        try:
            response = self.session.post(
                self.url,
                data=query,
                params=params,
                auth=self.auth,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise DatasetContractError("CLICKHOUSE_UNAVAILABLE", "ClickHouse is unavailable") from exc
        try:
            rows = [json.loads(line) for line in response.text.splitlines() if line.strip()]
        except (TypeError, json.JSONDecodeError) as exc:
            raise DatasetContractError("CLICKHOUSE_DATA_INVALID", "ClickHouse returned invalid data") from exc
        if any(not isinstance(row, dict) or not set(columns).issubset(row) for row in rows):
            raise DatasetContractError("CLICKHOUSE_DATA_INVALID", "ClickHouse data is missing protocol fields")
        frame = pd.DataFrame(rows, columns=columns)
        if frame.empty:
            return {}
        missing = set(REQUIRED_COLUMNS).difference(frame.columns)
        if missing:
            raise DatasetContractError("CLICKHOUSE_DATA_INVALID", "ClickHouse data is missing protocol fields")
        try:
            frame["date"] = pd.to_datetime(frame["date"], errors="raise")
        except (TypeError, ValueError) as exc:
            raise DatasetContractError("CLICKHOUSE_DATA_INVALID", "ClickHouse dates are invalid") from exc
        if frame.duplicated(subset=["code", "date"]).any():
            raise DatasetContractError("CLICKHOUSE_DATA_INVALID", "ClickHouse data contains duplicate rows")
        return {
            symbol: group.sort_values("date").reset_index(drop=True)
            for symbol, group in frame.groupby("code", sort=False)
        }


def configured_clickhouse_loader() -> ClickHouseDatasetLoader:
    return ClickHouseDatasetLoader(
        os.environ.get("QWESDK_CLICKHOUSE_URL", ""),
        os.environ.get("QWESDK_CLICKHOUSE_USER", "default"),
        os.environ.get("QWESDK_CLICKHOUSE_PASSWORD", ""),
    )
