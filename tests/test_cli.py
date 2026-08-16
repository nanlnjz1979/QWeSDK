import io
import unittest
from contextlib import redirect_stdout

from m.cli import main


class CliTests(unittest.TestCase):
    def test_smoke_command_reports_success(self):
        output = io.StringIO()

        with redirect_stdout(output):
            result = main([])

        self.assertEqual(result, 0)
        self.assertIn("QWeSDK import check passed", output.getvalue())


if __name__ == "__main__":
    unittest.main()
