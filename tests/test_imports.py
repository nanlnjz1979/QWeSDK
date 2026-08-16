import subprocess
import sys
import unittest


class ImportBoundaryTests(unittest.TestCase):
    def test_import_m_does_not_require_legacy_vnpy_dependencies(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import m; import m.core; print('import-ok')",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("import-ok", result.stdout)

    def test_import_trader_v2_does_not_load_legacy_v1_backend(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from m.trader.trader_v2 import TraderV2; print(TraderV2.__name__)",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("TraderV2", result.stdout)


if __name__ == "__main__":
    unittest.main()
