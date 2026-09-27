import hashlib
import json
from datetime import date

import pytest
import requests

from m.data_access.clickhouse import ClickHouseDatasetLoader, DatasetContractError, manifest_hash
from m.data_access import catalog as data_catalog


def clickhouse_manifest():
    return {
        "datasetId": "cn-stock-daily",
        "releaseVersion": "20260831",
        "sourceType": "clickhouse",
        "schemaVersion": "v1",
        "storageMode": "immutable_table",
        "components": {
            "daily": {
                "database": "default",
                "tables": {
                    "none": "release_20260831_stock_daily_none",
                    "qfq": "release_20260831_stock_daily_qfq",
                    "hfq": "release_20260831_stock_daily_hfq",
                },
            }
        },
        "coverage": {"start": "1990-12-19", "end": "2026-08-29"},
    }


class Response:
    status_code = 200
    text = '{"code":"000001.SZ","date":"2026-08-28 00:00:00","open":10,"high":11,"low":9,"close":10.5,"volume":1000}\n'

    def raise_for_status(self):
        return None

    def json(self):
        return [json.loads(self.text)]


class Session:
    def __init__(self, *, response=None, error=None):
        self.calls = []
        self.response = response or Response()
        self.error = error

    def post(self, url, *, data, params, auth, timeout):
        self.calls.append({"url": url, "data": data, "params": params, "auth": auth, "timeout": timeout})
        if self.error:
            raise self.error
        return self.response


def make_loader(session, timeout=30.0):
    return ClickHouseDatasetLoader(
        "http://fake-clickhouse:8123",
        "fake-user",
        "fake-password",
        session=session,
        timeout=timeout,
    )


def test_manifest_hash_is_sha256_of_canonical_json():
    manifest = {"b": 2, "a": 1}
    expected = "sha256:" + hashlib.sha256(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    assert manifest_hash(manifest) == expected


def test_loader_reads_allowlisted_daily_table_with_parameterized_filters():
    session = Session()
    loader = make_loader(session)
    manifest = clickhouse_manifest()

    result = loader.load_daily(
        manifest,
        symbols=["000001.SZ"],
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 29),
        adjustment_mode="hfq",
    )

    assert list(result) == ["000001.SZ"]
    assert result["000001.SZ"].iloc[0]["close"] == 10.5
    call = session.calls[0]
    assert "release_20260831_stock_daily_hfq" in call["data"]
    assert "000001.SZ" not in call["data"]
    assert call["params"]["database"] == "default"
    assert call["params"]["default_format"] == "JSONEachRow"
    assert call["params"]["param_codes"] == "['000001.SZ']"
    assert call["params"]["param_start_date"] == "2026-08-01 00:00:00"
    assert call["params"]["param_end_date"] == "2026-08-29 23:59:59"


def test_loader_uses_fixed_protocol_columns_when_manifest_omits_columns():
    session = Session()
    make_loader(session).load_daily(*(
        clickhouse_manifest(), ["user-symbol"], date(2026, 8, 1), date(2026, 8, 29), "none"
    ))

    query = session.calls[0]["data"]
    assert "SELECT `code`, `date`, `open`, `high`, `low`, `close`, `volume`" in query
    assert "user-symbol" not in query
    assert session.calls[0]["params"]["param_codes"] == "['user-symbol']"


def test_loader_rejects_unsafe_manifest_identifier_before_http_request():
    session = Session()
    manifest = clickhouse_manifest()
    manifest["components"]["daily"]["tables"]["none"] = "daily; DROP TABLE users"

    with pytest.raises(ValueError, match="invalid"):
        make_loader(session).load_daily(*(
            manifest, ["000001.SZ"], date(2026, 8, 1), date(2026, 8, 29), "none"
        ))
    assert session.calls == []


def test_loader_converts_timeout_to_controlled_value_error():
    session = Session(error=requests.Timeout("fake timeout"))

    with pytest.raises(ValueError):
        make_loader(session, timeout=0.25).load_daily(*(
            clickhouse_manifest(), ["000001.SZ"], date(2026, 8, 1), date(2026, 8, 29), "none"
        ))


def test_loader_collapses_identical_replacing_rows():
    row = '{"code":"000001","date":"2025-09-25 00:00:00","open":11.43,"high":11.5,"low":11.2,"close":11.4,"volume":100}\n'
    session = Session(response=Response())
    session.response.text = row + row

    result = make_loader(session).load_daily(*(
        clickhouse_manifest(), ["000001"], date(2025, 9, 25), date(2025, 9, 25), "none"
    ))

    assert len(result["000001"]) == 1
    assert result["000001"].iloc[0]["close"] == 11.4


def test_loader_rejects_conflicting_duplicate_rows():
    session = Session(response=Response())
    session.response.text = (
        '{"code":"000001","date":"2025-09-25 00:00:00","open":11.43,"high":11.5,"low":11.2,"close":11.4,"volume":100}\n'
        '{"code":"000001","date":"2025-09-25 00:00:00","open":11.43,"high":11.5,"low":11.2,"close":12.0,"volume":100}\n'
    )

    with pytest.raises(DatasetContractError, match="duplicate rows"):
        make_loader(session).load_daily(*(
            clickhouse_manifest(), ["000001"], date(2025, 9, 25), date(2025, 9, 25), "none"
        ))


def test_loader_rejects_malformed_clickhouse_response():
    session = Session(response=Response())
    session.response.text = "not-json\n"

    with pytest.raises(ValueError):
        make_loader(session).load_daily(*(
            clickhouse_manifest(), ["000001.SZ"], date(2026, 8, 1), date(2026, 8, 29), "none"
        ))


def test_loader_rejects_non_immutable_manifest_and_unknown_adjustment_table():
    loader = make_loader(Session())
    manifest = clickhouse_manifest()
    manifest["storageMode"] = "mutable_table"

    with pytest.raises(ValueError, match="immutable|storageMode"):
        loader.load_daily(manifest, ["000001.SZ"], date(2026, 8, 1), date(2026, 8, 29), "none")

    manifest = clickhouse_manifest()
    manifest["components"]["daily"]["tables"].pop("qfq")
    with pytest.raises(ValueError, match="qfq"):
        loader.load_daily(manifest, ["000001.SZ"], date(2026, 8, 1), date(2026, 8, 29), "qfq")


def test_loader_accepts_explicit_current_view_manifest_for_rolling_data():
    session = Session()
    loader = ClickHouseDatasetLoader("http://fake-clickhouse:8123", "fake-user", "fake-password", session=session)
    manifest = clickhouse_manifest()
    manifest["storageMode"] = "current_view"
    manifest["components"]["daily"]["tables"] = {
        "none": "stock_daily",
        "qfq": "stock_daily_qfq_v",
        "hfq": "stock_daily_hfq_v",
    }

    result = loader.load_daily(
        manifest, ["000001.SZ"], date(2026, 8, 1), date(2026, 8, 29), "qfq"
    )

    assert list(result) == ["000001.SZ"]
    assert "stock_daily_qfq_v" in session.calls[0]["data"]


def test_data_catalog_dispatches_clickhouse_manifest(monkeypatch):
    manifest = clickhouse_manifest()
    manifest["manifestHash"] = manifest_hash(manifest)

    class FakeLoader:
        def __init__(self, *args, **kwargs):
            pass

        def load_daily(self, loaded_manifest, symbols, start_date, end_date, adjustment_mode):
            assert loaded_manifest == manifest
            assert symbols == ["000001.SZ"]
            return {"000001.SZ": "loaded"}

    monkeypatch.setattr(data_catalog, "ClickHouseDatasetLoader", FakeLoader)
    result = data_catalog.load_dataset(
        {
            "id": "cn-stock-daily",
            "version": "20260831",
            "manifestHash": manifest["manifestHash"],
            "sourceType": "clickhouse",
            "symbols": ["000001.SZ"],
            "adjustmentMode": "none",
            "dateRange": {"start": "2026-08-01", "end": "2026-08-29"},
            "manifest": manifest,
        },
    )

    assert result == {"000001.SZ": "loaded"}


def test_data_catalog_loads_inline_clickhouse_manifest_without_local_data_root(monkeypatch):
    manifest = clickhouse_manifest()
    manifest["manifestHash"] = manifest_hash(manifest)
    session = Session()
    monkeypatch.setenv("QWESDK_CLICKHOUSE_URL", "http://fake-clickhouse:8123")

    class FakeConfiguredLoader:
        def __init__(self, url, user, password):
            self.loader = ClickHouseDatasetLoader(url, user, password, session=session)

        def load_daily(self, *args, **kwargs):
            return self.loader.load_daily(*args, **kwargs)

    monkeypatch.setattr(data_catalog, "ClickHouseDatasetLoader", FakeConfiguredLoader)
    result = data_catalog.load_dataset(
        {
            "id": "cn-stock-daily", "version": "20260831",
            "manifestHash": manifest["manifestHash"], "sourceType": "clickhouse",
            "symbols": ["000001.SZ"], "adjustmentMode": "none", "manifest": manifest,
        }, start_date="2026-08-01", end_date="2026-08-29",
    )

    assert list(result) == ["000001.SZ"]
    assert len(session.calls) == 1


@pytest.mark.parametrize(
    ("source_type", "manifest_hash_value", "message", "code"),
    [
        ("csv", "sha256:fixture", "source is not clickhouse", "DATASET_SOURCE_UNSUPPORTED"),
        ("clickhouse", "sha256:wrong", "content hash does not match", "DATASET_MANIFEST_INVALID"),
    ],
)
def test_data_catalog_rejects_non_clickhouse_missing_or_wrong_manifest(
    source_type, manifest_hash_value, message, code
):
    manifest = clickhouse_manifest()
    manifest["sourceType"] = source_type
    manifest["manifestHash"] = globals()["manifest_hash"](manifest)
    expected_spec_hash = manifest["manifestHash"] if source_type == "csv" else manifest_hash_value
    spec = {
        "id": "cn-stock-daily", "version": "20260831",
        "manifestHash": expected_spec_hash, "sourceType": source_type,
        "manifest": manifest,
    }

    with pytest.raises(DatasetContractError, match=message) as exc_info:
        data_catalog.load_dataset(spec, start_date="2026-08-01", end_date="2026-08-29")
    assert exc_info.value.code == code


def test_data_catalog_rejects_missing_inline_manifest():
    with pytest.raises(DatasetContractError, match="Manifest is required") as exc_info:
        data_catalog.load_dataset(
            {
                "id": "cn-stock-daily", "version": "20260831",
                "manifestHash": "sha256:x", "sourceType": "clickhouse",
            },
        )
    assert exc_info.value.code == "DATASET_MANIFEST_MISSING"


def test_data_catalog_accepts_manifest_frozen_inside_runspec(monkeypatch):
    manifest = clickhouse_manifest()
    manifest["manifestHash"] = manifest_hash(manifest)

    class FakeLoader:
        def __init__(self, *args, **kwargs):
            pass

        def load_daily(self, loaded_manifest, symbols, start_date, end_date, adjustment_mode):
            assert loaded_manifest == manifest
            return {"000001.SZ": "loaded"}

    monkeypatch.setattr(data_catalog, "ClickHouseDatasetLoader", FakeLoader)
    result = data_catalog.load_dataset(
        {
            "id": "cn-stock-daily",
            "version": "20260831",
            "manifestHash": manifest["manifestHash"],
            "sourceType": "clickhouse",
            "symbols": ["000001.SZ"],
            "adjustmentMode": "none",
            "manifest": manifest,
        },
        start_date="2026-08-01",
        end_date="2026-08-29",
    )

    assert result == {"000001.SZ": "loaded"}


def test_load_daily_posts_parameterized_protocol_query():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import parse_qs, urlparse

    captured = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            captured["query"] = parse_qs(urlparse(self.path).query)
            captured["body"] = self.rfile.read(length).decode("utf-8")
            body = (
                '{"code":"000001.SZ","date":"2024-01-02 00:00:00","open":1,"high":2,"low":1,"close":2,"volume":10}\n'
                '{"code":"600000.SH","date":"2024-01-03 00:00:00","open":3,"high":4,"low":3,"close":4,"volume":20}\n'
            )
            payload = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = __import__("threading").Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        loader = ClickHouseDatasetLoader(f"http://127.0.0.1:{port}", "user", "secret")
        frames = loader.load_daily(
            clickhouse_manifest(),
            ["600000.SH", "000001.SZ"],
            "2024-01-02",
            "2024-01-05",
            "qfq",
        )
    finally:
        server.shutdown()
        server.server_close()

    assert captured["query"]["param_codes"] == ["['000001.SZ','600000.SH']"]
    assert "release_20260831_stock_daily_qfq" in captured["body"]
    assert "release_20260831_stock_daily_none" not in captured["body"]
    assert set(frames) == {"000001.SZ", "600000.SH"}
