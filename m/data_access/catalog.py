"""Load only immutable, versioned datasets configured for the Worker."""

from __future__ import annotations

import os
import re
from datetime import date

from .clickhouse import ClickHouseDatasetLoader, DatasetContractError, validate_manifest


SAFE_COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _safe_component(value: object, field: str) -> str:
    if not isinstance(value, str) or not SAFE_COMPONENT_RE.fullmatch(value):
        raise ValueError(f"dataset.{field} is invalid")
    return value


def _read_manifest(dataset_spec: dict) -> dict:
    if not isinstance(dataset_spec, dict):
        raise DatasetContractError("DATASET_MANIFEST_INVALID", "dataset specification is invalid")
    if dataset_spec.get("sourceType") != "clickhouse":
        raise DatasetContractError("DATASET_SOURCE_UNSUPPORTED", "dataset source is not clickhouse")
    dataset_id = _safe_component(dataset_spec.get("id"), "id")
    version = _safe_component(dataset_spec.get("version"), "version")
    inline_manifest = dataset_spec.get("manifest")
    if inline_manifest is None:
        raise DatasetContractError("DATASET_MANIFEST_MISSING", "dataset Manifest is required in RunSpec")
    if not isinstance(inline_manifest, dict):
        raise DatasetContractError("DATASET_MANIFEST_INVALID", "dataset manifest is invalid")
    manifest = dict(inline_manifest)
    expected_hash = dataset_spec.get("manifestHash")
    if not isinstance(expected_hash, str) or not expected_hash:
        raise DatasetContractError("DATASET_MANIFEST_INVALID", "dataset manifestHash is required")
    return validate_manifest(manifest, dataset_id=dataset_id, version=version, expected_hash=expected_hash)


def load_dataset(
    dataset_spec: dict,
    *,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    symbols: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    manifest = _read_manifest(dataset_spec)
    if start_date is None or end_date is None:
        date_range = dataset_spec.get("dateRange") or {}
        start_date, end_date = date_range.get("start"), date_range.get("end")
    if start_date is None or end_date is None:
        raise DatasetContractError("DATASET_MANIFEST_INVALID", "ClickHouse dataset date range is required")
    requested_symbols = symbols or dataset_spec.get("symbols")
    loader = ClickHouseDatasetLoader(
        os.environ.get("QWESDK_CLICKHOUSE_URL", ""),
        os.environ.get("QWESDK_CLICKHOUSE_USER", "default"),
        os.environ.get("QWESDK_CLICKHOUSE_PASSWORD", ""),
    )
    return loader.load_daily(
        manifest,
        requested_symbols,
        start_date,
        end_date,
        dataset_spec.get("adjustmentMode", "none"),
    )


class DatasetDataLoader:
    """Expose ClickHouse dataset reads without exposing backing table details."""

    def __init__(self, dataset_spec: dict):
        self.dataset_spec = dict(dataset_spec)
        self.manifest = _read_manifest(self.dataset_spec)
        self._clickhouse = ClickHouseDatasetLoader(
            os.environ.get("QWESDK_CLICKHOUSE_URL", ""),
            os.environ.get("QWESDK_CLICKHOUSE_USER", "default"),
            os.environ.get("QWESDK_CLICKHOUSE_PASSWORD", ""),
        )

    def load_daily(self, symbols, start_date, end_date, fields=None, adjustment_mode=None):
        mode = adjustment_mode or self.dataset_spec.get("adjustmentMode", "none")
        if self._clickhouse is not None:
            arguments = (self.manifest, list(symbols), start_date, end_date, mode)
            if fields:
                return self._clickhouse.load_daily(*arguments, fields=fields)
            return self._clickhouse.load_daily(*arguments)


def create_data_loader(dataset_spec: dict) -> DatasetDataLoader:
    return DatasetDataLoader(dataset_spec)
