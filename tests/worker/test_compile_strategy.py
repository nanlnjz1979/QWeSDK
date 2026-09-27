import hashlib
import json
import subprocess
import sys

from m.worker.compile_strategy import MAX_CODE_BYTES, compile_strategy
from m.worker.protocol import MAX_CODE_BYTES as PROTOCOL_MAX_CODE_BYTES


CALLBACK = "qwesdk_callback_v1"
SCRIPT = "qwesdk_script_v1"


def test_code_limit_matches_worker_protocol():
    assert MAX_CODE_BYTES == PROTOCOL_MAX_CODE_BYTES


def test_success_hashes_source_and_does_not_execute_it():
    code = "raise RuntimeError('executed')\n\ndef initialize(context):\n    pass\n\ndef handle_data(context, data):\n    pass\n"
    result = compile_strategy(code, CALLBACK)

    assert result["status"] == "success"
    assert result["codeHash"] == "sha256:" + hashlib.sha256(code.encode()).hexdigest()
    assert result["entryPoint"] == CALLBACK
    assert result["symbols"] == ["initialize", "handle_data"]
    assert result["diagnostics"] == []


def test_script_entry_accepts_main():
    code = "def main(runtime):\n    return None\n"
    result = compile_strategy(code, SCRIPT)

    assert result["status"] == "success"
    assert result["symbols"] == ["main"]


def test_reports_syntax_error_with_line():
    result = compile_strategy("def initialize(:\n    pass\n", CALLBACK)

    assert result["status"] == "error"
    assert result["diagnostics"][0]["code"] == "SYNTAX_ERROR"
    assert result["diagnostics"][0]["line"] == 1


def test_missing_entry_point():
    result = compile_strategy("def initialize(context):\n    pass\n", CALLBACK)

    assert result["status"] == "error"
    assert result["diagnostics"][0]["code"] == "ENTRY_POINT_MISSING"


def test_rejects_non_callable_entry_point():
    code = "async def initialize(context):\n    pass\n\ndef handle_data(context, data):\n    pass\n"
    result = compile_strategy(code, CALLBACK)

    assert result["diagnostics"][0]["code"] == "ENTRY_POINT_NOT_CALLABLE"


def test_rejects_forbidden_import_and_call():
    code = (
        "import os\n"
        "def initialize(context):\n"
        "    eval('1')\n"
        "def handle_data(context, data):\n"
        "    pass\n"
    )
    result = compile_strategy(code, CALLBACK)
    codes = [item["code"] for item in result["diagnostics"]]

    assert result["status"] == "error"
    assert codes == ["IMPORT_FORBIDDEN", "CALL_FORBIDDEN"]
    assert result["diagnostics"][0]["line"] == 1
    assert result["diagnostics"][1]["line"] == 3


def test_rejects_oversized_source():
    result = compile_strategy("x" * (MAX_CODE_BYTES + 1), CALLBACK)

    assert result["diagnostics"][0]["code"] == "CODE_TOO_LARGE"


def test_cli_reads_stdin_and_does_not_execute():
    code = "raise RuntimeError('executed')\n\ndef initialize(context):\n    pass\n\ndef handle_data(context, data):\n    pass\n"
    completed = subprocess.run(
        [sys.executable, "-m", "m.worker.compile_strategy"],
        input=json.dumps({"code": code, "entryPoint": CALLBACK}),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "success"
    assert "executed" not in completed.stderr
