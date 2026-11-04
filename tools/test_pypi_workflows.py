"""The manual PyPI probe must not count stale outputs or unsuccessful oracles."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pypi_workflows as probe


class ProbeTests(unittest.TestCase):
    def test_hash_mismatch_stops_before_install_or_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "sample.whl"
            artifact.write_bytes(b"substituted")
            with self.assertRaisesRegex(ValueError, "unexpected SHA-256"):
                probe.checked_file(artifact, "0" * 64)

    def test_missing_output_and_changed_streams_are_not_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work / "output.txt").write_bytes(b"old result")
            got = probe.execute([sys.executable, "-c", "print('ok')"], {}, work, 10, True)
            self.assertIsNone(got["output_file_hex"])
            for changed in ({"output_file_hex": "6162"}, {"stdout": "other"}, {"stderr": "warning"}):
                self.assertEqual(probe.stage(got, got | changed), {"mismatch": got})
            self.assertEqual(probe.stage(got, got), "pass")

    def test_failed_reference_is_ineligible_even_if_native_would_match(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(probe, "command") as run:
            work = Path(directory)
            run.return_value = {"timeout": 2}
            with self.assertRaisesRegex(RuntimeError, "CPython oracle failed"):
                probe.probe("api", "pass", [], work, work, work / "compiler", {}, 2)
            self.assertEqual(run.call_count, 1)

    def test_ir_rejection_blocks_execution_but_retains_qualified_oracle(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(probe, "command") as run:
            work = Path(directory)
            run.side_effect = [{"exit": 0, "stdout": "qualified", "stderr": ""},
                               {"exit": 1, "stdout": "", "stderr": f"{work}/pkg.py: rejected"}]
            row = probe.probe("api", "pass", [], work, work, work / "compiler", {}, 2)
            self.assertEqual(row["cpython"]["stdout"], "qualified")
            self.assertEqual(row["ir"], {"exit": 1, "diagnostic": "SITE/pkg.py: rejected"})
            self.assertEqual([row[k] for k in ("jit", "build", "aot")], ["not run"] * 3)
            self.assertEqual(run.call_count, 2)
