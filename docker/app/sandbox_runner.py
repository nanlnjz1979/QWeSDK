"""Run one strategy in a bounded child process.

The parent process never executes strategy source. Docker provides the outer
container boundary; this module adds a per-task process boundary and limits.
"""

from __future__ import annotations

import os
import selectors
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class SandboxLimits:
    wall_seconds: float = 300.0
    cpu_seconds: int = 300
    memory_bytes: int = 512 * 1024 * 1024
    max_output_bytes: int = 1024 * 1024
    max_processes: int = 32


@dataclass(frozen=True)
class SandboxResult:
    status: str
    stdout: str = ""
    stderr: str = ""
    error_code: str | None = None
    exit_code: int | None = None


def _preexec(limits: SandboxLimits) -> None:
    if os.name != "posix":
        return
    import resource

    os.setsid()
    limits_by_name = {
        "RLIMIT_CPU": (limits.cpu_seconds, limits.cpu_seconds),
        "RLIMIT_AS": (limits.memory_bytes, limits.memory_bytes),
        "RLIMIT_NPROC": (limits.max_processes, limits.max_processes),
        "RLIMIT_FSIZE": (limits.max_output_bytes, limits.max_output_bytes),
    }
    for name, value in limits_by_name.items():
        limit = getattr(resource, name, None)
        if limit is None:
            continue
        try:
            resource.setrlimit(limit, value)
        except (OSError, ValueError):
            # Some developer hosts reject individual rlimits; Docker enforces
            # the same limits in production at the container boundary.
            continue


def _terminate(process: subprocess.Popen) -> None:
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        pass


def _decode(buffer: bytearray) -> str:
    return bytes(buffer).decode("utf-8", errors="replace")


def run_sandboxed(
    run_id: str,
    code: str,
    work_root: Path,
    limits: SandboxLimits,
    emit: Callable[..., dict],
    cancel_file: Path | None = None,
) -> SandboxResult:
    work_root.mkdir(parents=True, exist_ok=True)
    task_dir = Path(tempfile.mkdtemp(prefix=f"{run_id}-", dir=work_root))
    code_path = task_dir / "strategy.py"
    code_path.write_text(code, encoding="utf-8")
    code_path.chmod(0o500)

    process = subprocess.Popen(
        [sys.executable, "-I", str(code_path)],
        cwd=str(task_dir),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        close_fds=True,
        env={
            "HOME": str(task_dir),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUNBUFFERED": "1",
        },
        preexec_fn=lambda: _preexec(limits) if os.name == "posix" else None,
    )
    emit("started", pid=process.pid)

    selector = selectors.DefaultSelector()
    assert process.stdout is not None and process.stderr is not None
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    stdout = bytearray()
    stderr = bytearray()
    started_at = time.monotonic()
    status = "succeeded"
    error_code = None

    try:
        while selector.get_map() or process.poll() is None:
            if cancel_file is not None and cancel_file.exists():
                status, error_code = "cancelled", "CANCEL_REQUESTED"
                _terminate(process)
            elif time.monotonic() - started_at > limits.wall_seconds:
                status, error_code = "timed_out", "WALL_TIME_LIMIT_EXCEEDED"
                _terminate(process)

            for key, _ in selector.select(timeout=0.05):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                remaining = limits.max_output_bytes - len(stdout) - len(stderr)
                if len(chunk) > remaining:
                    if remaining > 0:
                        target = stdout if key.data == "stdout" else stderr
                        target.extend(chunk[:remaining])
                    status, error_code = "failed", "OUTPUT_LIMIT_EXCEEDED"
                    _terminate(process)
                    continue
                target = stdout if key.data == "stdout" else stderr
                target.extend(chunk)

            if process.poll() is not None and not selector.get_map():
                break
        process.wait(timeout=2)
    finally:
        selector.close()
        if process.poll() is None:
            _terminate(process)
            process.wait(timeout=2)
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()

    if status == "succeeded" and process.returncode != 0:
        status, error_code = "failed", "CHILD_PROCESS_FAILED"
    emit(status, exitCode=process.returncode, errorCode=error_code)
    return SandboxResult(
        status=status,
        stdout=_decode(stdout),
        stderr=_decode(stderr),
        error_code=error_code,
        exit_code=process.returncode,
    )
