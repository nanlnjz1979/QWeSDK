import json
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "docker" / "worker"))

import qwesdk_entrypoint
from m.worker.sandbox import SandboxLimits, run_sandboxed
from m.worker.protocol import EventStream, validate_run_spec


class WorkerSecurityTests(unittest.TestCase):
    def test_rejects_unknown_run_spec_version(self):
        with self.assertRaisesRegex(ValueError, "schemaVersion"):
            validate_run_spec({"schemaVersion": "9.0", "runId": "run-1", "code": "pass"})

    def test_rejects_path_traversal_run_id(self):
        with self.assertRaisesRegex(ValueError, "runId"):
            validate_run_spec({"schemaVersion": "1.0", "runId": "../escape", "code": "pass"})

    def test_runs_strategy_in_child_process_and_emits_ordered_events(self):
        events = EventStream("run-001")
        result = run_sandboxed(
            run_id="run-001",
            code="print('golden-ok')",
            work_root=Path("/tmp/qwesdk-test-worker"),
            limits=SandboxLimits(wall_seconds=5),
            emit=events.emit,
        )

        self.assertEqual(result.status, "succeeded")
        self.assertIn("golden-ok", result.stdout)
        self.assertEqual([event["sequence"] for event in events.events], [1, 2])
        self.assertEqual(events.events[0]["type"], "started")
        self.assertEqual(events.events[-1]["type"], "succeeded")

    def test_sandbox_delivers_stdout_lines_before_exit(self):
        lines = []
        result = run_sandboxed(
            run_id="run-lines",
            code="print('QWE_EVENT:one', flush=True)\nprint('QWE_EVENT:two', flush=True)\n",
            work_root=Path("/tmp/qwesdk-test-worker"),
            limits=SandboxLimits(wall_seconds=5),
            emit=lambda *_args, **_kwargs: {},
            on_stdout_line=lines.append,
        )

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(lines, ["QWE_EVENT:one", "QWE_EVENT:two"])
        self.assertIn("QWE_EVENT:one", result.stdout)
        self.assertIn("QWE_EVENT:two", result.stdout)

    def test_strategy_child_receives_task_local_home(self):
        events = EventStream("run-home")
        result = run_sandboxed(
            run_id="run-home",
            code="import os; print(os.environ['HOME'])",
            work_root=Path("/tmp/qwesdk-test-worker"),
            limits=SandboxLimits(wall_seconds=5),
            emit=events.emit,
        )
        self.assertEqual(result.status, "succeeded")
        self.assertIn("/tmp/qwesdk-test-worker/run-home-", result.stdout)

    def test_timeout_terminates_child_process(self):
        events = EventStream("run-timeout")
        result = run_sandboxed(
            run_id="run-timeout",
            code="import time; time.sleep(10)",
            work_root=Path("/tmp/qwesdk-test-worker"),
            limits=SandboxLimits(wall_seconds=0.1),
            emit=events.emit,
        )

        self.assertEqual(result.status, "timed_out")
        self.assertEqual(events.events[-1]["type"], "timed_out")

    def test_cancel_marker_terminates_child_process(self):
        events = EventStream("run-cancel")
        cancel_file = Path("/tmp/qwesdk-test-worker-cancel")
        cancel_file.unlink(missing_ok=True)
        cancel_file.write_text("cancel", encoding="utf-8")
        try:
            result = run_sandboxed(
                run_id="run-cancel",
                code="import time; time.sleep(10)",
                work_root=Path("/tmp/qwesdk-test-worker"),
                limits=SandboxLimits(wall_seconds=5),
                cancel_file=cancel_file,
                emit=events.emit,
            )
        finally:
            cancel_file.unlink(missing_ok=True)

        self.assertEqual(result.status, "cancelled")
        self.assertEqual(events.events[-1]["type"], "cancelled")

    def test_output_limit_fails_without_returning_unbounded_output(self):
        events = EventStream("run-output")
        result = run_sandboxed(
            run_id="run-output",
            code="print('x' * 10000)",
            work_root=Path("/tmp/qwesdk-test-worker"),
            limits=SandboxLimits(wall_seconds=5, max_output_bytes=1024),
            emit=events.emit,
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error_code, "OUTPUT_LIMIT_EXCEEDED")
        self.assertLessEqual(len(result.stdout) + len(result.stderr), 1024)
        self.assertEqual(events.events[-1]["type"], "failed")

    def test_installed_version_reads_the_mutable_sdk_target(self):
        with self.subTest("metadata target"):
            target = Path("/tmp/qwesdk-test-metadata")
            metadata = target / "qwesdk-9.8.7.dist-info"
            metadata.mkdir(parents=True, exist_ok=True)
            try:
                (metadata / "METADATA").write_text(
                    "Metadata-Version: 2.1\nName: qwesdk\nVersion: 9.8.7\n",
                    encoding="utf-8",
                )
                self.assertEqual(qwesdk_entrypoint.get_installed_version(target), "9.8.7")
            finally:
                import shutil

                shutil.rmtree(target, ignore_errors=True)

    def test_install_package_targets_the_mutable_sdk_directory(self):
        package = Path("/packages/qwesdk-9.8.7-py3-none-any.whl")
        target = Path("/tmp/qwesdk-test-install-target")
        target.mkdir(parents=True, exist_ok=True)
        try:
            completed = mock.Mock(returncode=0)
            with mock.patch.object(qwesdk_entrypoint.subprocess, "run", return_value=completed) as run:
                self.assertTrue(qwesdk_entrypoint.install_package(package, target))
            command = run.call_args.args[0]
            self.assertIn("--target", command)
            staged_target = Path(command[command.index("--target") + 1])
            self.assertEqual(staged_target.parent, target)
            self.assertTrue(staged_target.name.startswith(".qwesdk-install-"))
        finally:
            import shutil

            shutil.rmtree(target, ignore_errors=True)

    def test_install_package_replaces_existing_target_directories(self):
        package = Path("/packages/qwesdk-1.0.6-py3-none-any.whl")
        target = Path("/tmp/qwesdk-test-install-replace")
        import shutil

        shutil.rmtree(target, ignore_errors=True)
        (target / "bin").mkdir(parents=True)
        (target / "bin" / "old").write_text("old", encoding="utf-8")

        def stage_files(command, **kwargs):
            staging = Path(command[command.index("--target") + 1])
            (staging / "bin").mkdir()
            (staging / "bin" / "tool").write_text("new", encoding="utf-8")
            (staging / "m").mkdir()
            (staging / "m" / "trader_v2.py").write_text("range", encoding="utf-8")
            return mock.Mock(returncode=0)

        try:
            with mock.patch.object(qwesdk_entrypoint.subprocess, "run", side_effect=stage_files):
                self.assertTrue(qwesdk_entrypoint.install_package(package, target))
            self.assertEqual((target / "bin" / "tool").read_text(encoding="utf-8"), "new")
            self.assertFalse((target / "bin" / "bin").exists())
            self.assertFalse((target / "bin" / "old").exists())
            self.assertEqual((target / "m" / "trader_v2.py").read_text(encoding="utf-8"), "range")
        finally:
            shutil.rmtree(target, ignore_errors=True)

    def test_package_selection_prefers_wheel_for_same_version(self):
        package_dir = Path("/tmp/qwesdk-test-package-selection")
        package_dir.mkdir(parents=True, exist_ok=True)
        try:
            wheel = package_dir / "qwesdk-1.0.0-py3-none-any.whl"
            sdist = package_dir / "qwesdk-1.0.0.tar.gz"
            wheel.write_bytes(b"wheel")
            sdist.write_bytes(b"sdist")
            with mock.patch.object(
                qwesdk_entrypoint,
                "sdist_contains_package",
                return_value=True,
            ):
                candidates = qwesdk_entrypoint.find_candidates(package_dir)
            self.assertEqual(candidates[0][2], wheel)
        finally:
            import shutil

            shutil.rmtree(package_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
