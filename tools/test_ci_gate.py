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

    def plan(self, base=None, commit=None, head=None):
        return verification_plan("pull_request", self.base if base is None else base,
                                 self.git("rev-parse", "HEAD") if commit is None else commit,
                                 self.git("rev-parse", "feature") if head is None else head)

    def test_docs_paths_and_literal_newline(self):
        Path("README.md").write_text("Read me\n")
        Path("docs").mkdir()
        Path("docs/topic\nodd.txt").write_text("Docs\n")
        self.merge()
        self.assertEqual(self.plan(), "docs")

    def test_mixed_changes(self):
        Path("README.md").write_text("Read me\n")
        Path("old.py").write_text("print(1)\n")
        self.merge()
        self.assertEqual(self.plan(), "code")

    def test_moving_code_into_docs_counts_as_source_removal(self):
        Path("docs").mkdir()
        Path("old.py").rename("docs/old.py")
        self.merge()
        self.assertEqual(self.plan(), "code")

    def test_empty_diff_keeps_code_plan(self):
        self.merge()
        self.assertEqual(self.plan(), "code")

    def test_newer_merge_base_requires_code_instead_of_failing(self):
        Path("README.md").write_text("Read me\n")
        self.git("add", "README.md")
        self.git("commit", "-qm", "Docs")
        self.git("switch", "-q", "main")
        Path("old.py").write_text("print(1)\n")
        self.git("commit", "-qam", "New base")
        actual_base = self.git("rev-parse", "HEAD")
        self.git("merge", "-q", "--no-ff", "feature")
        # The same docs merge permits skipping only with its exact event base.
        self.assertEqual(self.plan(base=actual_base), "docs")
        self.assertEqual(self.plan(), "code")
        # Reproduce checkout's depth two: the stale event base can be unavailable,
        # while the validated actual base remains usable for changed-case checks.
        merge = self.git("rev-parse", "HEAD")
        head = self.git("rev-parse", "feature")
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as shallow:
            self.git("clone", "-q", "--depth=2", previous.as_uri(), shallow)
            os.chdir(shallow)
            try:
                self.assertEqual(self.plan(commit=merge, head=head), "code")
                self.assertEqual(self.git("rev-parse", "HEAD^1"), actual_base)
                self.assertEqual(self.git("diff", "--name-only", actual_base, "HEAD"), "README.md")
                missing = subprocess.run(["git", "cat-file", "-e", self.base], capture_output=True)
                self.assertNotEqual(missing.returncode, 0)
            finally:
                os.chdir(previous)

    def test_wrong_checkout_or_pr_head_fails_even_with_stale_base(self):
        self.merge()
        for base in (self.base, "1" * 40):
            with self.subTest(base=base):
                with self.assertRaisesRegex(ValueError, "event merge commit"):
                    self.plan(base=base, commit=self.base)
                with self.assertRaisesRegex(ValueError, "expected PR head"):
                    self.plan(base=base, head=self.base)

    def test_nonmerge_and_missing_event_identities_fail(self):
        with self.assertRaisesRegex(ValueError, "exactly two parents"):
            self.plan()
        self.merge()
        for name in ("base", "commit", "head"):
            for value in ("", "HEAD", "1" * 39):
                with self.subTest(name=name, value=value), self.assertRaisesRegex(ValueError, "invalid event"):
                    self.plan(**{name: value})

    def test_main_and_manual_runs_use_code(self):
        for event in ("push", "workflow_dispatch"):
            self.assertEqual(verification_plan(event, "", "", ""), "code")


class GateTests(unittest.TestCase):
    def test_expected_job_results(self):
        require_jobs("pull_request", "docs", "", ["success", "skipped", "skipped", "skipped"])
        require_jobs("pull_request", "code", "", ["success", "success", "success", "skipped"])
        require_jobs("push", "code", "code", ["success", "success", "skipped", "success"])

    def test_code_rejects_any_unexpected_job_result(self):
        for event, arm, expected in (
            ("pull_request", "", ["success", "success", "success", "skipped"]),
            ("push", "code", ["success", "success", "skipped", "success"]),
            ("workflow_dispatch", "code", ["success", "success", "skipped", "success"]),
        ):
            for index in range(4):
                for result in ("", "skipped", "success", "failure", "cancelled"):
                    if result == expected[index]:
                        continue
                    with self.subTest(event=event, index=index, result=result), self.assertRaises(ValueError):
                        results = expected.copy()
                        results[index] = result
                        require_jobs(event, "code", arm, results)

    def test_docs_requires_successful_classification_and_explicit_skips(self):
        for event, plan, arm_plan, results in (
            ("push", "docs", "docs", ["success", "skipped", "skipped", "skipped"]),
            ("pull_request", "docs", "docs", ["success", "skipped", "skipped", "skipped"]),
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
        self.assertEqual(set(gate["needs"]), {"bootstrap", "verification", "pr-variants", "qualification"})

    def test_workflow_checks_event_identity_and_shares_the_validated_base(self):
        ci = workflows()["ci.yml"]
        self.assertEqual(ci["env"]["CI_EVENT_BASE_SHA"], "${{ github.event.pull_request.base.sha || '' }}")
        self.assertEqual(ci["env"]["CI_HEAD_SHA"], "${{ github.event.pull_request.head.sha || '' }}")
        self.assertNotIn("CI_BASE_SHA", ci["env"])
        bootstrap = ci["jobs"]["bootstrap"]
        plan = next(step for step in bootstrap["steps"] if step.get("id") == "plan")["run"]
        self.assertIn('"$CI_EVENT_BASE_SHA" "$GITHUB_SHA" "$CI_HEAD_SHA"', plan)
        self.assertIn('base=$(git rev-parse HEAD^1)', plan)
        self.assertEqual(bootstrap["outputs"]["base"], "${{ steps.plan.outputs.base }}")
        for name in ("verification", "pr-variants", "verify"):
            with self.subTest(job=name):
                self.assertEqual(ci["jobs"][name]["env"]["CI_BASE_SHA"], "${{ needs.bootstrap.outputs.base }}")


if __name__ == "__main__":
    unittest.main()
