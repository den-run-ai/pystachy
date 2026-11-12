"""Negative controls for accepting match benchmark measurements."""
from contextlib import redirect_stderr
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("match_bench_controller", Path(__file__).with_name("bench.py"))
CONTROLLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROLLER)


class MeasurementControls(unittest.TestCase):
    def record(self, stdout="42\n10\n", stderr="kernel_wall_ns 100\n"):
        return {"stdout": stdout, "stderr": stderr, "wall_s": 0.25, "returncode": 0}

    def check(self, record):
        with patch.object(CONTROLLER, "execute", return_value=record):
            return CONTROLLER.checked(["program"], {}, 10, count=10, expected=42)

    def test_valid_measurement_keeps_kernel_and_command_times_separate(self):
        result = self.check(self.record())
        self.assertEqual(result["kernel_wall_ns"], 100)
        self.assertEqual(result["wall_s"], 0.25)

    def test_rejects_wrong_checksum_and_truncated_or_wrong_count(self):
        for stdout in ("41\n10\n", "42\n", "42\n9\n", "42\n10\nextra\n", "nan\n10\n"):
            with self.subTest(stdout=stdout), self.assertRaises(ValueError):
                self.check(self.record(stdout=stdout))

    def test_rejects_missing_invalid_duplicate_or_extra_stderr(self):
        for stderr in ("", "kernel_wall_ns 0\n", "kernel_wall_ns -2\n", "kernel_wall_ns nan\n",
                       "kernel_wall_ns 1.5\n", "kernel_wall_ns 10 extra\n", "wrong_timer 10\n",
                       "kernel_wall_ns 10\nkernel_wall_ns 12\n", "warning\nkernel_wall_ns 10\n",
                       "kernel_wall_ns 10\nerror\n", "kernel_wall_ns 10\n\n"):
            with self.subTest(stderr=stderr), self.assertRaises(ValueError):
                self.check(self.record(stderr=stderr))

    def test_failed_process_cannot_become_a_measurement(self):
        with patch.object(CONTROLLER, "execute", side_effect=RuntimeError("exit 7")):
            with self.assertRaisesRegex(RuntimeError, "exit 7"):
                CONTROLLER.checked(["program"], {}, 10, count=10, expected=42)

    def test_ratios_use_paired_samples_and_preserve_noise_span(self):
        pairs = [
            {"if": {"kernel_wall_ns": 20, "wall_s": 1.0}, "match": {"kernel_wall_ns": 10, "wall_s": 2.0}},
            {"if": {"kernel_wall_ns": 5, "wall_s": 6.0}, "match": {"kernel_wall_ns": 10, "wall_s": 2.0}},
        ]
        result = CONTROLLER.summaries(pairs)
        self.assertEqual(result["kernel_wall_ns"], {"median_if_over_match": 1.25,
                                                   "min_if_over_match": 0.5,
                                                   "max_if_over_match": 2.0, "samples": 2})
        self.assertEqual(result["wall_s"]["median_if_over_match"], 1.75)

    def test_duplicate_selections_fail_before_running_commands(self):
        for option, value in (("modes", "aot"), ("kinds", "literal"), ("shapes", "mixed")):
            with self.subTest(option=option), patch.object(CONTROLLER, "execute") as execute:
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                    CONTROLLER.main([f"--{option}", value, value])
                self.assertEqual(caught.exception.code, 2)
                execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
