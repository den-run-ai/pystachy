"""Repository hygiene checks the index, not ignore rules or working-tree presence."""

from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from check_repository_hygiene import check


class RepositoryHygieneTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.git("init", "--quiet", "--template=")

    def git(self, *args):
        return subprocess.run(
            ["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
             "-c", "user.name=Hygiene Test", "-c", "user.email=hygiene@example.invalid", *args],
            cwd=self.root, capture_output=True, check=True,
        )

    def write(self, path, content="fixture\n"):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def run_check(self, root=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = check(self.root if root is None else root)
        return status, stdout.getvalue(), stderr.getvalue()

    def test_staged_research_fails_until_removal_is_staged(self):
        path = "research/compiler-state/results.json"
        self.write(path)
        self.git("add", path)
        status, _, errors = self.run_check()
        self.assertEqual(status, 1)
        self.assertIn(path, errors)
        (self.root / path).unlink()
        self.assertEqual(self.run_check()[0], 1)
        self.git("add", "-u")
        self.assertEqual(self.run_check()[0], 0)

    def test_committed_research_fails_despite_gitignore(self):
        self.write("research/results.json")
        self.git("add", "research/results.json")
        self.git("commit", "--quiet", "-m", "Fixture")
        self.write(".gitignore", "/research/\n")
        self.git("add", ".gitignore")
        self.assertEqual(self.run_check()[0], 1)

    def test_untracked_and_ignored_research_are_not_proposed_changes(self):
        self.write("research/local.json")
        self.assertEqual(self.run_check()[0], 0)
        self.write(".gitignore", "/research/\n")
        self.git("add", ".gitignore")
        self.assertEqual(self.run_check()[0], 0)
        self.git("add", "-f", "research/local.json")
        self.assertEqual(self.run_check()[0], 1)

    def test_maintained_reports_benchmarks_and_tests_pass(self):
        for path in ("docs/reports/compatibility.md", "bench/router/results/data.json",
                     "tests/programs/inference/research_case.py", "tools/research_check.py",
                     ".github/workflows/unit-tests.yml", "docs/version-1.2.md"):
            self.write(path)
            self.git("add", path)
        self.assertEqual(self.run_check()[0], 0)

    def test_special_characters_in_tracked_paths_fail(self):
        for path in ("tests/paths]/fixture.py", "tests/fixtures/[case].py",
                     "tests/with space/fixture.py", "tests/fixtures/line\nbreak.py",
                     "tests/tab\tpath/fixture.py", "tests/\u00e9/fixture.py",
                     "tests/fixtures/case?.py", "tests/pipe|path/fixture.py",
                     "tests/fixtures/quote\".py", "tests/percent%path/fixture.py",
                     "tests/fixtures/comma,.py", "tests/back\\slash/fixture.py"):
            with self.subTest(path=path):
                self.write(path)
                self.git("add", "--", path)
                status, _, errors = self.run_check()
                self.assertEqual(status, 1)
                self.assertIn(repr(path), errors)
                self.assertIn("ASCII letters, digits, '.', '_' and '-'", errors)
                self.git("rm", "--cached", "--", path)
                self.assertEqual(self.run_check()[0], 0)

    def test_generated_special_character_paths_are_allowed_until_staged(self):
        path = "tests/generated/paths]/fixture.py"
        self.write(path)
        self.assertEqual(self.run_check()[0], 0)
        self.write(".gitignore", "/tests/generated/\n")
        self.git("add", ".gitignore")
        self.assertEqual(self.run_check()[0], 0)
        self.git("add", "-f", "--", path)
        status, _, errors = self.run_check()
        self.assertEqual(status, 1)
        self.assertIn(repr(path), errors)

    def test_top_level_research_file_fails(self):
        self.write("research")
        self.git("add", "research")
        self.assertEqual(self.run_check()[0], 1)

    def test_top_level_research_symlink_fails(self):
        (self.root / "research").symlink_to("elsewhere")
        self.git("add", "research")
        self.assertEqual(self.run_check()[0], 1)

    def test_newline_in_filename_does_not_hide_research(self):
        self.write("research/line\nbreak.json")
        self.git("add", "research")
        status, _, errors = self.run_check()
        self.assertEqual(status, 1)
        self.assertIn(repr("research/line\nbreak.json"), errors)

    def test_non_repository_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            status, _, errors = self.run_check(Path(temporary))
        self.assertEqual(status, 2)
        self.assertIn("cannot read Git index", errors)

    def test_missing_git_fails_closed(self):
        with patch("check_repository_hygiene.subprocess.run", side_effect=FileNotFoundError):
            status, _, errors = self.run_check()
        self.assertEqual(status, 2)
        self.assertIn("cannot read Git index", errors)


if __name__ == "__main__":
    unittest.main()
