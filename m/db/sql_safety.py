"""Small, dependency-free helpers for building ClickHouse SQL fragments."""

import re


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def quote_identifier(value: str, allow_qualified: bool = False) -> str:
    """Validate and quote a ClickHouse identifier or qualified table name."""
    if not isinstance(value, str) or not value:
        raise ValueError("identifier must be a non-empty string")

    parts = value.split(".") if allow_qualified else [value]
    if len(parts) > 2 or any(not _IDENTIFIER.fullmatch(part) for part in parts):
        raise ValueError(f"invalid ClickHouse identifier: {value!r}")

    # Backticks keep an identifier separate from SQL keywords and operators.
    return ".".join(f"`{part}`" for part in parts)


def quote_string(value: str) -> str:
    """Return a ClickHouse single-quoted string literal."""
    if not isinstance(value, str):
        raise ValueError("SQL string values must be strings")

    # ClickHouse uses backslash escapes inside single-quoted literals.
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def quote_string_list(values) -> str:
    """Quote each string in an iterable for use in an ``IN`` expression."""
    if isinstance(values, (str, bytes)):
        raise ValueError("SQL string lists must be an iterable of strings")

    try:
        values = list(values)
    except TypeError as exc:
        raise ValueError("SQL string lists must be iterable") from exc

    return ", ".join(quote_string(value) for value in values)
