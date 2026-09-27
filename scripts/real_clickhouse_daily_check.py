"""Read one real ClickHouse daily table when explicitly enabled."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from m.data_access.clickhouse import REQUIRED_COLUMNS, ClickHouseDatasetLoader  # noqa: E402


def main(argv=None) -> int:
    del argv
    if os.environ.get("QWESDK_REAL_CLICKHOUSE") != "1":
        print("real ClickHouse check disabled")
        return 2

    required = (
        "QWESDK_CLICKHOUSE_URL",
        "QWESDK_CLICKHOUSE_USER",
        "QWESDK_CLICKHOUSE_PASSWORD",
        "QWESDK_CLICKHOUSE_TABLE_NONE",
        "QWESDK_CLICKHOUSE_SYMBOLS",
        "QWESDK_CLICKHOUSE_START",
        "QWESDK_CLICKHOUSE_END",
    )
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        print("missing " + ", ".join(missing))
        return 1

    table = os.environ["QWESDK_CLICKHOUSE_TABLE_NONE"]
    symbols = [item.strip() for item in os.environ["QWESDK_CLICKHOUSE_SYMBOLS"].split(",") if item.strip()]
    if not symbols:
        print("QWESDK_CLICKHOUSE_SYMBOLS is empty")
        return 1

    manifest = {
        "datasetId": "real-clickhouse-check",
        "releaseVersion": "manual",
        "sourceType": "clickhouse",
        "schemaVersion": "v1",
        "storageMode": "immutable_table",
        "coverage": {
            "start": os.environ["QWESDK_CLICKHOUSE_START"],
            "end": os.environ["QWESDK_CLICKHOUSE_END"],
        },
        "components": {
            "daily": {
                "database": "default",
                "tables": {"none": table, "qfq": table, "hfq": table},
            }
        },
    }
    loader = ClickHouseDatasetLoader(
        os.environ["QWESDK_CLICKHOUSE_URL"],
        os.environ["QWESDK_CLICKHOUSE_USER"],
        os.environ["QWESDK_CLICKHOUSE_PASSWORD"],
    )
    frames = loader.load_daily(
        manifest,
        symbols,
        os.environ["QWESDK_CLICKHOUSE_START"],
        os.environ["QWESDK_CLICKHOUSE_END"],
        "none",
    )
    for symbol in symbols:
        frame = frames.get(symbol)
        if frame is None or frame.empty or not set(REQUIRED_COLUMNS).issubset(frame.columns):
            print(f"{symbol} has no complete daily rows")
            return 1
        print(f"{symbol} {len(frame)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
