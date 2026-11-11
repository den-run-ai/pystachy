"""Exercise the Lint workflow's actual Lean selector on temporary Git histories."""

import os
import re
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]


class LeanBoundaryWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        workflow = yaml.load((ROOT / ".github/workflows/lint.yml").read_text(), Loader=yaml.BaseLoader)
        cls.selector = next(step["run"] for step in workflow["jobs"]["lint"]["steps"]
                            if step.get("id") == "lean-boundary")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.repo = self.directory / "repo"
        self.repo.mkdir()
        self.sequence = 0
        self.git("init", "--quiet", "--initial-branch=main")
        self.git("config", "user.name", "Workflow test")
        self.git("config", "user.email", "workflow@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.hooksPath", "/dev/null")
        self.commit_file("README.md")

    def git(self, *arguments):
        return subprocess.run(["git", *arguments], cwd=self.repo, check=True,
                              capture_output=True, text=True, timeout=10)

    def commit_file(self, name):
        self.sequence += 1
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture revision {self.sequence}\n")
        self.git("add", "--", name)
        self.git("commit", "--quiet", "-m", f"Change {name}")

    def merge_pr(self, *names):
        branch = f"pr-{self.sequence}"
        self.git("checkout", "--quiet", "-b", branch)
        for name in names:
            self.commit_file(name)
        self.git("checkout", "--quiet", "main")
        self.git("merge", "--quiet", "--no-ff", "--no-edit", branch)

    def selected(self, event="pull_request", repo=None):
        output = self.directory / "github-output"
        output.write_text("")
        env = dict(os.environ, GITHUB_EVENT_NAME=event, GITHUB_OUTPUT=str(output))
        completed = subprocess.run(
            ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", self.selector],
            cwd=repo or self.repo, env=env, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        result = output.read_text()
        self.assertIn(result, ("run=true\n", "run=false\n"))
        return result == "run=true\n"

    def test_documentation_only_pr_skips_lean(self):
        self.merge_pr("docs/typed-ir.md", "README.md")
        self.assertFalse(self.selected())

    def test_compiler_change_in_earlier_pr_commit_runs_lean(self):
        self.merge_pr("src/pystachy_compiler/dynamic.py", "docs/typed-ir.md")
        self.assertTrue(self.selected())

    def test_adapter_inspection_tests_and_pins_run_lean(self):
        for name in ("tools/check_lean_boundary.py", "tools/check_lean_access.py", "tools/test_lean_access.py",
                     "tools/inspect_compiler.py",
                     "tools/test_lean_boundary_workflow.py", "pystachy.py",
                     "tools/lean_boundary/PystachyBoundary.lean", "Makefile",
                     ".github/workflows/lint.yml", "tools/requirements-dev.txt", ".python-version"):
            with self.subTest(path=name):
                self.merge_pr(name)
                self.assertTrue(self.selected())

    def test_main_push_and_manual_run_check_after_documentation_commit(self):
        self.commit_file("src/pystachy_compiler/dynamic.py")
        self.commit_file("docs/typed-ir.md")
        for event in ("push", "workflow_dispatch"):
            with self.subTest(event=event):
                self.assertTrue(self.selected(event))

    def test_corpus_proof_runs_in_an_opt_in_group_of_every_profile_with_the_same_lean(self):
        def lean_step(steps, command):
            return next(step for step in steps if command in step.get("run", ""))
        lint = yaml.load((ROOT / ".github/workflows/lint.yml").read_text(), Loader=yaml.BaseLoader)
        ci = yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
        verification = ci["jobs"]["verification"]
        boundary = lean_step(lint["jobs"]["lint"]["steps"], "make check-lean-boundary")
        corpus = lean_step(verification["steps"], "make check-lean-corpus")
        # (the same pinned release archive, checked against the same digest, in both jobs)
        def pins(run):
            return (re.findall(r"https://github\.com/leanprover/lean4/releases/download/\S+?\.tar\.zst", run),
                    re.findall(r"\b[0-9a-f]{64}\b", run), "sha256sum --check -" in run)
        self.assertEqual(pins(corpus["run"]), pins(boundary["run"]))
        self.assertEqual([len(found) for found in pins(boundary["run"])[:2]], [1, 1])
        self.assertEqual(corpus["if"], "matrix.machine == 'x86_64' && "
                                       "(matrix.group == 'opt-in' || matrix.group == 'dynany-optin-0')")
        # (two workers, explicitly: the runner would otherwise start up to four)
        self.assertIn("LEAN_CORPUS_FLAGS='--jobs 2 ", corpus["run"])
        groups = verification["strategy"]["matrix"]["group"]
        self.assertIn('"opt-in"', groups.split("||")[0])
        self.assertIn('"dynany-optin-0"', groups.split("||")[1])
        self.assertIn("build/verify/lean-corpus.json", verification["steps"][-1]["with"]["path"])

    def test_missing_merge_parent_runs_lean(self):
        self.merge_pr("docs/typed-ir.md")
        shallow = self.directory / "shallow"
        self.git("clone", "--quiet", "--depth=1", self.repo.as_uri(), str(shallow))
        self.assertTrue(self.selected(repo=shallow))


if __name__ == "__main__":
    unittest.main()
