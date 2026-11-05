import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from ci_gate import require_jobs, verification_plan
from test_workflow_limits import workflows


class PlanTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        previous = Path.cwd()
        os.chdir(directory.name)
        self.addCleanup(os.chdir, previous)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "CI gate tests")
        self.git("config", "user.email", "ci@example.test")
        Path("old.py").write_text("pass\n")
        self.git("add", ".")
        self.git("commit", "-qm", "Base")
        self.base = self.git("rev-parse", "HEAD")
        self.git("switch", "-qc", "feature")

    def git(self, *args):
        return subprocess.check_output(["git", *args], text=True).strip()

    def merge(self):
        self.git("add", "-A")
        self.git("commit", "-qm", "Feature", "--allow-empty")
        self.git("switch", "-q", "main")
        self.git("merge", "-q", "--no-ff", "feature")

    def test_docs_paths_and_literal_newline(self):
        Path("README.md").write_text("Read me\n")
        Path("docs").mkdir()
        Path("docs/topic\nodd.txt").write_text("Docs\n")
        self.merge()
        self.assertEqual(verification_plan("pull_request", self.base), "docs")

    def test_mixed_changes(self):
        Path("README.md").write_text("Read me\n")
        Path("old.py").write_text("print(1)\n")
        self.merge()
        self.assertEqual(verification_plan("pull_request", self.base), "code")

    def test_moving_code_into_docs_counts_as_source_removal(self):
        Path("docs").mkdir()
        Path("old.py").rename("docs/old.py")
        self.merge()
        self.assertEqual(verification_plan("pull_request", self.base), "code")

    def test_empty_diff_keeps_code_plan(self):
        self.merge()
        self.assertEqual(verification_plan("pull_request", self.base), "code")

    def test_mismatched_base_fails_and_main_uses_code(self):
        self.merge()
        with self.assertRaisesRegex(ValueError, "expected PR base"):
            verification_plan("pull_request", self.git("rev-parse", "HEAD^2"))
        for event in ("push", "workflow_dispatch"):
            self.assertEqual(verification_plan(event, ""), "code")


class GateTests(unittest.TestCase):
    def test_expected_job_results(self):
        require_jobs("pull_request", "docs", "docs", ["success", "skipped", "skipped", "skipped"])
        require_jobs("pull_request", "code", "code", ["success"] * 4)
        require_jobs("push", "code", "code", ["success", "success", "skipped", "skipped"])

    def test_code_rejects_missing_skipped_failed_and_cancelled_jobs(self):
        for index in range(4):
            for result in ("", "skipped", "failure", "cancelled"):
                with self.subTest(index=index, result=result), self.assertRaises(ValueError):
                    results = ["success"] * 4
                    results[index] = result
                    require_jobs("pull_request", "code", "code", results)

    def test_docs_requires_successful_classification_and_explicit_skips(self):
        for event, plan, arm_plan, results in (
            ("push", "docs", "docs", ["success", "skipped", "skipped", "skipped"]),
            ("pull_request", "docs", "", ["success", "skipped", "skipped", "skipped"]),
            ("pull_request", "docs", "code", ["success", "skipped", "skipped", "skipped"]),
            ("pull_request", "docs", "docs", ["cancelled", "skipped", "skipped", "skipped"]),
            ("pull_request", "docs", "docs", ["success", "cancelled", "skipped", "skipped"]),
        ):
            with self.subTest(event=event, plan=plan, arm_plan=arm_plan, results=results):
                with self.assertRaises(ValueError):
                    require_jobs(event, plan, arm_plan, results)

    def test_workflow_reports_verification_and_keeps_cancellation(self):
        ci = workflows()["ci.yml"]
        self.assertFalse(ci["on"]["pull_request"])
        gate = ci["jobs"]["verify"]
        self.assertIn("'Verification'", gate["name"])
        self.assertEqual(gate["if"], "${{ !cancelled() }}")
        self.assertEqual(set(gate["needs"]), {"bootstrap", "verification", "pr-variants", "distribution"})


if __name__ == "__main__":
    unittest.main()
