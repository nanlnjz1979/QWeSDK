"""HTTP Gateway and browser-facing daily backtest workspace."""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

APP_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = Path(__file__).resolve().parent / "static"
sys.path.insert(0, str(APP_ROOT))

from gateway.backtest_api import BrowserBacktestService, list_datasets  # noqa: E402
from gateway.gateway_service import GatewayError, GatewayService  # noqa: E402
from m.worker.celery_app import app as celery_app  # noqa: E402


def _env_path(name: str, fallback: Path) -> str:
    return os.environ.get(name, str(fallback))


def create_services() -> tuple[GatewayService, BrowserBacktestService]:
    # Gateway 使用 SQLite 保存提交元数据和页面可见的回测状态。
    database = _env_path("HELIX_GATEWAY_DB", APP_ROOT / ".qwesdk-gateway.sqlite3")
    os.environ.setdefault("QWESDK_INSTALL_TARGET", str(APP_ROOT))
    gateway = GatewayService(
        os.environ.get("HELIX_GATEWAY_SECRET", "change-me-in-local-only-internal-secret"),
        database,
        celery_app,
        callback_base_url=os.environ.get("HELIX_GATEWAY_CALLBACK_BASE_URL"),
        callback_secret=os.environ.get("HELIX_GATEWAY_CALLBACK_SECRET") or os.environ.get("HELIX_GATEWAY_SECRET"),
        work_root=_env_path("QWESDK_WORK_ROOT", Path("/tmp/qwesdk-runs")),
    )
    default_local = "0" if os.environ.get("HELIX_GATEWAY_DB") else "1"
    local_execution = os.environ.get("QWESDK_LOCAL_EXECUTION", default_local).lower() in {"1", "true", "yes"}
    return gateway, BrowserBacktestService(gateway, local_execution=local_execution)


def make_handler(browser: BrowserBacktestService):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._write(200, {"status": "UP", "service": "execution-gateway"})
            elif parsed.path == "/internal/v1/ops/summary":
                try:
                    # Helix 服务端使用签名访问，浏览器不会直接调用这个接口。
                    self._write(200, browser.gateway.operational_summary(
                        dict(self.headers.items()), parsed.path
                    ))
                except GatewayError as error:
                    self._write(error.status, {"code": error.code, "message": str(error)})
                except Exception:
                    self._write(503, {"code": "GATEWAY_UNAVAILABLE"})
            elif parsed.path == "/api/datasets":
                self._write(200, list_datasets())
            elif parsed.path == "/":
                self._write_file(STATIC_ROOT / "index.html", "text/html; charset=utf-8")
            elif parsed.path in {"/app.css", "/app.js"}:
                suffix = parsed.path.lstrip("/")
                content_type = "text/css; charset=utf-8" if suffix.endswith(".css") else "text/javascript; charset=utf-8"
                self._write_file(STATIC_ROOT / suffix, content_type)
            elif parsed.path.startswith("/api/backtests/"):
                self._get_backtest(parsed.path)
            else:
                self._write(404, {"code": "NOT_FOUND"})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            try:
                body = self._read_json()
                if parsed.path == "/api/backtests":
                    # 浏览器便捷接口：在 Gateway 内部生成并签名 RunSpec。
                    self._write(202, browser.submit(body))
                elif parsed.path.startswith("/api/backtests/") and parsed.path.endswith("/cancel"):
                    run_id = parsed.path.split("/")[3]
                    self._write(202, browser.gateway.cancel(run_id))
                elif parsed.path.startswith("/v1/backtests/"):
                    # Helix 内部接口：请求必须通过 HMAC、摘要、时间戳、RunSpec 和幂等性校验，
                    # 校验通过后才能投递到 Celery。
                    parts = parsed.path.strip("/").split("/")
                    if len(parts) == 3:
                        run_id = parts[2]
                        raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                        result = browser.gateway.submit(run_id, raw, dict(self.headers.items()))
                        self._write(202, result.as_dict())
                    elif len(parts) == 4 and parts[3] == "cancel":
                        run_id = parts[2]
                        raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                        browser.gateway.authenticate_cancel(run_id, raw, dict(self.headers.items()))
                        self._write(202, browser.gateway.cancel(run_id))
                    else:
                        self._write(404, {"code": "NOT_FOUND"})
                else:
                    self._write(404, {"code": "NOT_FOUND"})
            except GatewayError as error:
                self._write(error.status, {"code": error.code, "message": str(error)})
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                self._write(400, {"code": "INVALID_REQUEST", "message": str(error)})
            except Exception:
                self._write(503, {"code": "GATEWAY_UNAVAILABLE"})

        def _get_backtest(self, path: str) -> None:
            parts = path.strip("/").split("/")
            if len(parts) not in {3, 4}:
                self._write(404, {"code": "NOT_FOUND"})
                return
            run_id = parts[2]
            if len(parts) == 4 and parts[3] == "result":
                result = browser.result(run_id)
                if result is None:
                    status = browser.status(run_id)
                    self._write(409 if status else 404, status or {"code": "TASK_NOT_FOUND"})
                else:
                    self._write(200, result)
                return
            status = browser.status(run_id)
            self._write(200 if status else 404, status or {"code": "TASK_NOT_FOUND"})

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 16 * 1024 * 1024:
                raise ValueError("request body is empty or too large")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("request body must be an object")
            return payload

        def _write_file(self, path: Path, content_type: str) -> None:
            try:
                data = path.read_bytes()
            except OSError:
                self._write(404, {"code": "NOT_FOUND"})
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)

        def _write(self, status: int, payload: object) -> None:
            data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_args) -> None:
            return

    return Handler


def main() -> None:
    _gateway, browser = create_services()
    host = os.environ.get("HELIX_GATEWAY_HOST", "127.0.0.1")
    port = int(os.environ.get("HELIX_GATEWAY_PORT", "8090"))
    # 同一个 HTTP 进程同时提供健康检查、本地页面和 Helix 内部接口。
    ThreadingHTTPServer((host, port), make_handler(browser)).serve_forever()


if __name__ == "__main__":
    main()
