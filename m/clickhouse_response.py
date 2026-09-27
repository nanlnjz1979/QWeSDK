"""Parse the JSON Lines format returned by ClickHouse queries.

All legacy QWeSDK HTTP data readers use ``FORMAT JSONEachRow``. Keeping the
parser in one small module prevents each reader from inventing a different
fallback for malformed or non-object responses.
"""

from __future__ import annotations

import json
from typing import Any


def parse_json_each_row(text: str) -> list[dict[str, Any]]:
    """Return ClickHouse JSONEachRow records, rejecting invalid rows."""
    if not isinstance(text, str):
        raise ValueError("ClickHouse response must be text")

    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"invalid ClickHouse JSONEachRow response at line {line_number}"
            ) from exc
        if not isinstance(value, dict):
            raise ValueError(
                f"ClickHouse JSONEachRow response line {line_number} is not an object"
            )
        rows.append(value)
    return rows
