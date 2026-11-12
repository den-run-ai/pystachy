"""Exercise Lean workflow selection, corpus placement and dependency coverage."""

import ast
import os
import re
import shlex
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

from test_workflow_limits import matrix_rows


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

    def selects_matrix_row(self, condition, row):
        # Evaluate only the literal comparisons, startsWith and Boolean operators in these guards.
        condition = re.sub(r"startsWith\(matrix.group, '([^']*)'\)",
                           lambda match: str(row["group"].startswith(match[1])), condition)
        for key in ("group", "machine"):
            condition = condition.replace("matrix." + key, repr(row[key]))
        condition = condition.replace("&&", " and ").replace("||", " or ")
        expression = ast.parse(condition, mode="eval")
        allowed = (ast.Expression, ast.BoolOp, ast.Compare, ast.Constant, ast.And, ast.Or, ast.Eq)
        self.assertTrue(all(isinstance(node, allowed) for node in ast.walk(expression)), condition)
        return eval(compile(expression, "<Lean workflow condition>", "eval"), {"__builtins__": {}}, {})

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
                     "tools/check_lean_storage.py", "tools/check_lean_storage_corpus.py",
                     "tools/test_lean_storage.py", "tools/test_lean_storage_corpus.py",
                     "tools/test_lean_layout_metadata.py", "tools/check_lean_corpus.py",
                     "tools/lean_boundary/PystachyBoundary.lean", "tools/lean_boundary/PystachyInt.lean",
                     "tools/check_lean_int.py", "tools/test_lean_int.py", "Makefile",
                     "tools/check_lean_effects.py", "tools/check_lean_inline.py", "tools/test_lean_inline.py",
                     "tools/check_lean_guards.py", "tools/check_lean_guard_corpus.py",
                     "tools/test_lean_guards.py", "tools/test_lean_effects.py",
                     "tools/test_lean_range_bounds.py", "tools/test_lean_closure_cells.py",
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

    def test_corpus_proof_uses_pr_opt_in_and_full_gc_jit_with_the_same_lean(self):
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
                                       "(matrix.group == 'opt-in' || matrix.group == 'gc-jit-1' || matrix.group == 'scaling' || matrix.group == 'contracts')")
        for event in ("pull_request", "push", "workflow_dispatch"):
            with self.subTest(event=event):
                selected = [(row["machine"], row["group"]) for row in matrix_rows(verification, event)
                            if self.selects_matrix_row(corpus["if"], row)]
                group = "opt-in" if event == "pull_request" else "gc-jit-1"
                self.assertEqual(set(selected), {("x86_64", group), ("x86_64", "contracts")} if event == "pull_request" else {("x86_64", "gc-jit-1"), ("x86_64", "scaling"), ("x86_64", "contracts")})
        # (two workers, explicitly: the runner would otherwise start up to four)
        self.assertIn("LEAN_CORPUS_FLAGS='--jobs 2 ", corpus["run"])
        self.assertEqual(verification["timeout-minutes"], "15")
        self.assertNotIn("continue-on-error", corpus)
        self.assertNotIn("continue-on-error", verification)
        self.assertIn("build/verify/lean-corpus.json", verification["steps"][-1]["with"]["path"])
        self.assertIn("build/verify/lean-storage.json", verification["steps"][-1]["with"]["path"])

    def test_full_storage_proof_uses_the_short_scaling_group(self):
        ci = yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
        step = next(step for step in ci["jobs"]["verification"]["steps"]
                    if "make check-lean-storage" in step.get("run", ""))
        self.assertEqual(step["env"]["VERIFY_GROUP"], "${{ matrix.group }}")
        # Execute the real command selector with an inert make, without downloading Lean.
        selector = 'case "$VERIFY_GROUP" in' + step["run"].split('case "$VERIFY_GROUP" in', 1)[1]
        bin_dir = self.directory / "bin"
        bin_dir.mkdir()
        make = bin_dir / "make"
        make.write_text('#!/bin/sh\nprintf "%s\\n" "$1"\n'
                        'if [ "$1" = "check-lean-guards" ]; then printf "%s\\n" "$2"; fi\n')
        make.chmod(0o755)
        for group, expected in (("opt-in", ["check-lean-corpus", "check-lean-int", "check-lean-storage"]),
                                ("gc-jit-1", ["check-lean-corpus", "check-lean-int"]),
                                ("gc-jit-0", []), ("runtime-cache", []),
                                ("scaling", ["check-lean-storage"]), ("contracts", ["check-lean-guards"]), ("hosted", [])):
            with self.subTest(group=group):
                env = dict(os.environ, VERIFY_GROUP=group, lean_boundary_dir=str(self.directory),
                           PATH=str(bin_dir) + os.pathsep + os.environ["PATH"])
                completed = subprocess.run(["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", selector],
                                           env=env, capture_output=True, text=True, timeout=10)
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                lines = completed.stdout.splitlines()
                if group == "contracts":
                    flags = lines.pop()
                    self.assertTrue(flags.startswith("LEAN_GUARD_FLAGS="))
                    args = shlex.split(flags.removeprefix("LEAN_GUARD_FLAGS="))
                    self.assertEqual(args[:4], ["--jobs", "2", "--report", "build/verify/lean-guards.json"])
                    programs = args[4:]
                    self.assertGreaterEqual(len(programs), 2)
                    self.assertEqual(len(programs), len(set(programs)))
                    self.assertTrue(all((ROOT / path).is_file() for path in programs))
                self.assertEqual(lines, expected)

    def test_corpus_and_opt_in_dependencies_are_pinned_and_installed_before_checks(self):
        ci = yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
        verification = ci["jobs"]["verification"]
        steps = verification["steps"]
        dependencies = [step for step in steps if "/^typing_extensions==/p" in step.get("run", "")]
        self.assertEqual(len(dependencies), 1)
        dependency = dependencies[0]
        self.assertIn("tools/requirements-dev.txt", dependency["run"])
        self.assertNotIn("continue-on-error", dependency)
        for command in ("tests/verify.sh", "make check-lean-corpus"):
            probe = next(step for step in steps if command in step.get("run", ""))
            self.assertLess(steps.index(dependency), steps.index(probe))
        for event in ("pull_request", "push", "workflow_dispatch"):
            for row in matrix_rows(verification, event):
                with self.subTest(event=event, **row):
                    opted = row["group"] == "opt-in" or row["group"].startswith(
                        ("dynany-optin-", "python-int-optin-"))
                    lean_full = row["machine"] == "x86_64" and row["group"] == "gc-jit-1"
                    self.assertEqual(self.selects_matrix_row(dependency["if"], row), opted or lean_full)

    def test_missing_merge_parent_runs_lean(self):
        self.merge_pr("docs/typed-ir.md")
        shallow = self.directory / "shallow"
        self.git("clone", "--quiet", "--depth=1", self.repo.as_uri(), str(shallow))
        self.assertTrue(self.selected(repo=shallow))


if __name__ == "__main__":
    unittest.main()
