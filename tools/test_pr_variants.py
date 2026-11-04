"""Packed PR variants use the validated compiler and reject false-green evidence."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import ci_sample
import pr_variants


class PRVariantTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.write("tests/corpus.sh", (ci_sample.ROOT / "tests/corpus.sh").read_text())
        self.write("tests/programs/basic/a.py", "print(1)\n")
        self.write("tests/programs/basic/b.py", "print(2)\n")
        self.write("tests/errors/basic/error.py", "# error: error.py:1: unsupported\n")
        self.environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                            "VERIFY_BOOTSTRAP_DIR": "build/ci-bootstrap", "PYSTACHY_JOBS": "99",
                            "VARIANTS": "wrong", "VARIANTS_SHARD": "3/9", "MODES": "wrong",
                            "COMPILER": "wrong"}
        self.restore = patch.object(pr_variants, "restore_bundle", return_value={
            "bootstrap_reused": True, "bootstrap_bundle_id": "verified"}).start()
        self.addCleanup(patch.stopall)
        self.runner()

    def write(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data)

    def runner(self, log="5 passed, 0 failed", exit_code=0, body=None):
        self.write("tools/variants.sh", '''#!/bin/sh
printf '%s\\n' "$COMPILER" "$MODES" "$VARIANTS" "${VARIANTS_SHARD-unset}" "$PYSTACHY_JOBS" "$@" > build/call
mkdir -p build/variants
''' + (body if body is not None else '''for variant in $VARIANTS; do
  printf '%s\\n' ''' + "'" + log + "'" + ''' > "build/variants/$variant.log"
done
''') + f"exit {exit_code}\n")

    def run_worker(self, worker=0):
        with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
            code = pr_variants.run_worker(worker, self.root, self.environment)
        return code, json.loads((self.root / "build/variants/report.json").read_text())

    def test_two_workers_cover_each_configuration_once_and_use_native_bootstrap(self):
        seen = []
        for worker in (0, 1):
            code, report = self.run_worker(worker)
            self.assertEqual(code, 0, report)
            self.assertEqual(report["profile"], "pr")
            self.assertEqual(report["coverage"], "representative")
            self.assertEqual(report["result"], "pass")
            self.assertEqual(report["bootstrap"]["bootstrap_bundle_id"], "verified")
            self.assertEqual(report["expected_checks_per_variant"], 5)
            self.assertEqual(len(report["steps"]), len(pr_variants.VARIANT_GROUPS[worker]))
            self.assertTrue(all(step["result"] == "pass" for step in report["steps"]))
            call = (self.root / "build/call").read_text().splitlines()
            self.assertEqual(call[:5], [str(self.root / "build/verify/pystachy2"), "jit aot",
                                       " ".join(pr_variants.VARIANT_GROUPS[worker]), "unset", "4"])
            self.assertEqual(call[5:], report["sample"]["cases"])
            seen.extend(report["variants"])
        self.assertEqual(seen, ["opt-1", "opt-2", "opt-3", "opt-4", "opt-5", "opt-6", "cflags-O0"])
        self.assertEqual(self.restore.call_count, 2)
        self.restore.assert_called_with(self.root / "build/ci-bootstrap", self.root)

    def test_missing_incorrect_duplicate_and_nonterminal_summaries_fail(self):
        for log in ("", "4 passed, 0 failed", "4 passed, 1 failed", "5 passed, 0 failed\n5 passed, 0 failed",
                    "5 passed, 0 failed\nunfinished output", "garbled output"):
            with self.subTest(log=log):
                self.runner(log)
                code, report = self.run_worker()
                self.assertEqual(code, 1)
                self.assertEqual(report["result"], "fail")
                self.assertTrue(all(step["result"] == "fail" for step in report["steps"]))

    def test_successful_summary_cannot_hide_nonzero_process_exit(self):
        self.runner(exit_code=7)
        code, report = self.run_worker()
        self.assertEqual(code, 1)
        self.assertEqual(report["exit_code"], 7)
        self.assertIn("status 7", report["error"])

    def test_old_logs_are_removed_and_partial_worker_cannot_pass(self):
        for variant in pr_variants.VARIANT_GROUPS[0]:
            self.write(f"build/variants/{variant}.log", "5 passed, 0 failed\n")
        self.runner(body="printf '%s\\n' '5 passed, 0 failed' > build/variants/opt-1.log\n")
        code, report = self.run_worker()
        self.assertEqual(code, 1)
        self.assertEqual([step["result"] for step in report["steps"]], ["pass", "fail", "fail", "fail"])

    def test_bad_bootstrap_is_not_rebuilt_or_ignored_and_emits_failed_report(self):
        self.restore.side_effect = ValueError("bootstrap checkout identity differs")
        code, report = self.run_worker()
        self.assertEqual(code, 1)
        self.assertIn("identity differs", report["error"])
        self.assertFalse((self.root / "build/call").exists())
        self.assertEqual(report["steps"], [])

    def test_bundle_is_required_and_bad_base_is_not_silently_ignored(self):
        del self.environment["VERIFY_BOOTSTRAP_DIR"]
        code, report = self.run_worker()
        self.assertEqual(code, 1)
        self.assertIn("VERIFY_BOOTSTRAP_DIR", report["error"])
        self.restore.assert_not_called()
        self.environment["CI_BASE_SHA"] = "invalid-base"
        code, report = self.run_worker()
        self.assertEqual(code, 1)
        self.assertIn("base commit", report["error"])
        self.restore.assert_not_called()

    def test_worker_counts_are_bounded_and_invalid_values_fail(self):
        self.assertEqual(pr_variants.case_workers("100"), 4)
        self.assertEqual(pr_variants.case_workers("1"), 1)
        for value in ("0", "-1", "all", "", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                pr_variants.case_workers(value)
        for worker in (-1, 2, "0", True):
            with self.subTest(worker=worker), self.assertRaises(ValueError):
                pr_variants.run_worker(worker, self.root, self.environment)


if __name__ == "__main__":
    unittest.main()
