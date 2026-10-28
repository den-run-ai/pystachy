"""Fail-closed contract tests for JSON-repair paired timing evidence."""
import copy
import os
from pathlib import Path
import sys
import unittest

from json_repair_bench import parse_output, run_process, validate_config


class JsonRepairBenchTests(unittest.TestCase):
    def test_all_measured_and_warmup_batches_are_retained(self):
        output = "witness escaped 5 27 13 0\nrounds 2\nwarmup_seconds 0.7\nseconds 0.2\nseconds 0.4\n"
        evidence = parse_output(output, 2, 1)
        self.assertEqual(evidence["seconds"], [0.2, 0.4])
        self.assertEqual(evidence["warmup_seconds"], [0.7])
        self.assertAlmostEqual(evidence["median_seconds"], 0.3)
        self.assertEqual(evidence["witness"], ["witness escaped 5 27 13 0", "rounds 2"])

    def test_missing_extra_and_invalid_timings_fail(self):
        witness = "witness escaped 5 27 13 0\n"
        for output in ("seconds 0.1\n", witness, witness + "seconds 0.1\nseconds 0.2\n",
                       witness + "seconds nan\n", witness + "seconds inf\n",
                       witness + "seconds -0.1\n", witness + "seconds bad\n"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                parse_output(output, 1, 0)
        with self.assertRaises(ValueError):
            parse_output(witness + "seconds 0.1\n", 1, 1)

    def test_full_mixed_witness_keeps_output_and_checksum(self):
        output = 'outputs [{"ok": true}]\nper_round 1\nrecords 10\nchecksum 10\nseconds 0.1\n'
        evidence = parse_output(output, 1, 0)
        self.assertEqual(evidence["witness"], output.splitlines()[:-1])

    def config(self):
        return {"variants": [
            {"name": name, "source": str(Path(__file__).resolve().parents[1]),
             "commands": {"scaling": [sys.executable, "probe.py"]}}
            for name in ("before", "after")
        ], "cases": [{"name": "escape", "probe": "scaling", "args": ["escaped", "32", "1"]}]}

    def test_shell_commands_and_duplicate_names_are_rejected(self):
        valid = self.config()
        validate_config(valid)
        bad = copy.deepcopy(valid)
        bad["variants"][0]["commands"]["scaling"] = "python probe.py"
        with self.assertRaises(ValueError):
            validate_config(bad)
        bad = copy.deepcopy(valid)
        bad["variants"][1]["name"] = "before"
        with self.assertRaises(ValueError):
            validate_config(bad)
        bad = copy.deepcopy(valid)
        bad["cases"][0]["args"] = ["escaped", 32, 1]
        with self.assertRaises(ValueError):
            validate_config(bad)

    @unittest.skipUnless(hasattr(os, "wait4"), "requires POSIX wait4")
    def test_child_exit_and_memory_are_recorded(self):
        result = run_process([sys.executable, "-c", "print('witness smoke'); print('seconds 0.1')"],
                             dict(os.environ), 5)
        self.assertGreater(result["whole_process_peak_rss_bytes"], 0)
        self.assertEqual(parse_output(result["stdout"], 1, 0)["seconds"], [0.1])
        with self.assertRaises(RuntimeError):
            run_process([sys.executable, "-c", "raise SystemExit(2)"], dict(os.environ), 5)


if __name__ == "__main__":
    unittest.main()
