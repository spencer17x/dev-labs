import sys
import unittest
from unittest import mock

from run import _run_single, main


class RunLauncherTests(unittest.TestCase):
    def test_run_single_invokes_main_with_target_only(self):
        with mock.patch("run.subprocess.run") as run_mock:
            _run_single("bsc", dry_run=False)

        cmd = run_mock.call_args.args[0]
        self.assertEqual(cmd[:3], [sys.executable, "main.py", "bsc"])
        self.assertNotIn("--bot-config", cmd)
        self.assertNotIn("--common-config", cmd)

    def test_run_single_preserves_dry_run_flag(self):
        with mock.patch("run.subprocess.run") as run_mock:
            _run_single("sol", dry_run=True)

        self.assertEqual(run_mock.call_args.args[0][-1], "--dry-run")

    def test_start_dry_run_is_rejected_before_pm2_start(self):
        with (
            mock.patch.object(sys, "argv", ["run.py", "start", "bsc", "--dry-run"]),
            mock.patch("run._start_target") as start_mock,
        ):
            with self.assertRaisesRegex(RuntimeError, "--dry-run.*start"):
                main()

        start_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
