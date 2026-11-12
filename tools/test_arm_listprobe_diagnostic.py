"""Fail-closed controls for the temporary, branch-only diagnostic harness."""

from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import arm_listprobe_diagnostic as diagnostic


ROOT = Path(__file__).resolve().parent.parent


class DiagnosticTests(unittest.TestCase):
    def test_original_inputs_unchanged_and_assertion_retained(self):
        runtime = (ROOT / "runtime.c").read_text()
        probe = (ROOT / "tools/listprobe.c").read_text()
        traced_runtime, traced_probe = diagnostic.instrument(runtime, probe)
        self.assertEqual(runtime, (ROOT / "runtime.c").read_text())
        self.assertEqual(probe, (ROOT / "tools/listprobe.c").read_text())
        self.assertIn(diagnostic.FIRST_MARK, traced_runtime)
        self.assertIn(diagnostic.MARK_ROOTS, traced_runtime)
        self.assertIn(diagnostic.ROOT_SCAN, traced_runtime)
        self.assertEqual(probe.count("bad("), traced_probe.count("bad("))
        self.assertIn('if (gc_live >= 1048576) { arm_diag_dump(buffers); bad("cleared list storage survives collection"); }', traced_probe)

    def test_missing_or_duplicate_anchor_fails_closed(self):
        with self.assertRaises(ValueError):
            diagnostic.replace_once("absent", "anchor", "change")
        with self.assertRaises(ValueError):
            diagnostic.replace_once("anchor anchor", "anchor", "change")

    def test_trace_records_without_logging_or_allocating_during_mark(self):
        header = (ROOT / "tools/arm_listprobe_trace.h").read_text()
        capture = header.split("static void arm_diag_record", 1)[1].split("static void arm_diag_dump", 1)[0]
        self.assertNotIn("fprintf", capture)
        self.assertNotIn("malloc", capture)
        self.assertIn("GC_NO_ROOT(arm_diag_marks)", header)
        self.assertIn("source_slot", capture)
        self.assertIn("arm_diag_in_roots", capture)

    def test_probe_environment_drops_inherited_gc_and_preserves_two_workers(self):
        with patch.dict("os.environ", {"PYSTACHY_GC": "off", "PYSTACHY_GC_STRESS": "100",
                                       "PYSTACHY_JOBS": "99", "PYSTACHY_HOME": "/wrong"}):
            environment = diagnostic.clean_environment()
        self.assertEqual(environment["PYSTACHY_JOBS"], "2")
        self.assertNotIn("PYSTACHY_GC", environment)
        self.assertNotIn("PYSTACHY_GC_STRESS", environment)
        self.assertNotIn("PYSTACHY_HOME", environment)

    def test_child_failure_is_retained_and_budget_exhaustion_fails(self):
        with tempfile.TemporaryDirectory() as name:
            log = Path(name) / "failed.log"
            result = diagnostic.run(
                [sys.executable, "-c", "print('assertion failed'); raise SystemExit(23)"],
                log, diagnostic.clean_environment(), time.monotonic() + 10, 2)
            self.assertEqual(result["returncode"], 23)
            self.assertFalse(result["timed_out"])
            self.assertEqual(log.read_text(), "assertion failed\n")
            with self.assertRaises(TimeoutError):
                diagnostic.run(["must-not-run"], log, {}, time.monotonic() - 1, 2)


if __name__ == "__main__":
    unittest.main()
