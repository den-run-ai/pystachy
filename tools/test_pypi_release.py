"""Reject unrelated sources, incomplete CI and unexpected upload artifacts."""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import pypi_release
from release_gate import REQUIRED_WORKFLOWS

COMMIT = "a" * 40
VERSION = "v0.2.0"
REPOSITORY = "den-run-ai/pystachy"


def run(name, identifier=1, **changes):
    result = {"id": identifier, "name": name, "head_sha": COMMIT, "head_branch": "main",
              "event": "push", "status": "completed", "conclusion": "success"}
    result.update(changes)
    return result


class PyPIReleaseTests(unittest.TestCase):
    def test_normalize_package_version(self):
        self.assertEqual(pypi_release.package_version(VERSION), "0.2.0")
        self.assertEqual(pypi_release.package_version("v0.2.0-alpha.1"), "0.2.0a1")
        for version in ("0.2.0", "v0.2", "v0.2.0\ncommit=other"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                pypi_release.package_version(version)

    def test_checkout_requires_tag_version_clean_tree_and_main_ancestry(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)

            def git(*args):
                return subprocess.check_output(["git", "-C", temporary, "-c", "user.name=Test",
                                                "-c", "user.email=test@example.invalid", *args],
                                               text=True, stderr=subprocess.DEVNULL).strip()

            git("init", "-q")
            (source / "VERSION").write_text(VERSION + "\n")
            git("add", "VERSION")
            git("commit", "-qm", "release")
            commit = git("rev-parse", "HEAD")
            git("tag", VERSION)
            git("update-ref", "refs/remotes/origin/main", commit)
            self.assertEqual(pypi_release.source_commit(source, VERSION), commit)
            with self.assertRaisesRegex(RuntimeError, "match source/VERSION"):
                pypi_release.source_commit(source, "v0.0.2")
            (source / "untracked.py").write_text("print('unexpected')\n")
            with self.assertRaisesRegex(RuntimeError, "clean"):
                pypi_release.source_commit(source, VERSION)
            (source / "untracked.py").unlink()
            git("commit", "--allow-empty", "-qm", "later")
            with self.assertRaisesRegex(RuntimeError, "HEAD does not match"):
                pypi_release.source_commit(source, VERSION)
            git("tag", "-f", VERSION)
            with self.assertRaises(RuntimeError):
                pypi_release.source_commit(source, VERSION)

    def test_release_must_be_published_and_target_exact_commit(self):
        valid = {"draft": False, "published_at": "2026-11-07T00:00:00Z",
                 "tag_name": VERSION, "target_commitish": COMMIT}
        ref = {"object": {"type": "commit", "sha": COMMIT}}
        with patch("pypi_release.get_json", side_effect=[valid, ref]):
            pypi_release.published_release(REPOSITORY, VERSION, COMMIT, "test")
        for release in (None, {**valid, "draft": True}, {**valid, "published_at": None},
                        {**valid, "tag_name": "v0.0.2"}, {**valid, "target_commitish": "main"},
                        {**valid, "target_commitish": "b" * 40}):
            with self.subTest(release=release), patch("pypi_release.get_json", return_value=release), \
                    self.assertRaises(RuntimeError):
                pypi_release.published_release(REPOSITORY, VERSION, COMMIT, "test")
        for remote in (None, {"object": {"type": "commit", "sha": "b" * 40}}):
            with self.subTest(remote=remote), \
                    patch("pypi_release.get_json", side_effect=[valid, remote]), \
                    self.assertRaisesRegex(RuntimeError, "tag does not resolve"):
                pypi_release.published_release(REPOSITORY, VERSION, COMMIT, "test")
        annotated = {"object": {"type": "tag", "sha": "c" * 40}}
        with patch("pypi_release.get_json", side_effect=[valid, annotated, ref]):
            pypi_release.published_release(REPOSITORY, VERSION, COMMIT, "test")

    def test_workflows_require_latest_success_on_exact_main_push(self):
        good = [run(name) for name in REQUIRED_WORKFLOWS]
        with patch("pypi_release.get_json", return_value={"workflow_runs": good}):
            pypi_release.verified_workflows(REPOSITORY, COMMIT, "test")
        for changes in ({"conclusion": "failure"}, {"conclusion": "cancelled"},
                        {"status": "in_progress"}, {"head_sha": "b" * 40},
                        {"head_branch": "other"}, {"event": "pull_request"}):
            runs = [run("CI", 2, **changes), *good[1:]]
            if "conclusion" in changes or "status" in changes:
                runs.append(good[0])
            with self.subTest(changes=changes), \
                    patch("pypi_release.get_json", return_value={"workflow_runs": runs}), \
                    self.assertRaisesRegex(RuntimeError, "CI:"):
                pypi_release.verified_workflows(REPOSITORY, COMMIT, "test")

    def test_workflows_read_every_page(self):
        first = [run("unrelated", n) for n in range(96)]
        first.extend(run(name) for name in REQUIRED_WORKFLOWS)
        pages = [{"workflow_runs": first, "total_count": 101},
                 {"workflow_runs": [run("CI", 200, conclusion="failure")], "total_count": 101}]
        with patch("pypi_release.get_json", side_effect=pages) as api, \
                self.assertRaisesRegex(RuntimeError, "CI: failure"):
            pypi_release.verified_workflows(REPOSITORY, COMMIT, "test")
        self.assertIn("page=2", api.call_args.args[0])

    def test_distribution_artifacts_and_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            stem = "pystachy-0.2.0"

            def artifacts(name="pystachy", version="0.2.0", bad_sdist=False):
                metadata = f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\n\n".encode()
                with zipfile.ZipFile(directory / (stem + "-py3-none-any.whl"), "w") as wheel:
                    wheel.writestr(stem + ".dist-info/METADATA", metadata if not bad_sdist else
                                   b"Metadata-Version: 2.4\nName: pystachy\nVersion: 0.2.0\n\n")
                with tarfile.open(directory / (stem + ".tar.gz"), "w:gz") as sdist:
                    member = tarfile.TarInfo(stem + "/PKG-INFO")
                    member.size = len(metadata)
                    sdist.addfile(member, io.BytesIO(metadata))

            artifacts()
            (directory / ".gitignore").write_text("*\n")
            pypi_release.audit_dist(directory, "0.2.0")
            for name, version in (("another-package", "0.2.0"), ("pystachy", "0.0.2")):
                for bad_sdist in (False, True):
                    artifacts(name, version, bad_sdist)
                    with self.subTest(name=name, version=version, bad_sdist=bad_sdist), \
                            self.assertRaisesRegex(RuntimeError, "metadata must identify"):
                        pypi_release.audit_dist(directory, "0.2.0")
            artifacts()
            with zipfile.ZipFile(directory / (stem + "-py3-none-any.whl"), "a") as wheel:
                wheel.writestr("../outside.py", b"unexpected")
            with self.assertRaisesRegex(RuntimeError, "unsafe"):
                pypi_release.audit_dist(directory, "0.2.0")
            artifacts()
            extra = directory / "pystachy-0.0.2.tar.gz"
            extra.write_bytes(b"unexpected")
            with self.assertRaisesRegex(RuntimeError, "exactly"):
                pypi_release.audit_dist(directory, "0.2.0")
            extra.unlink()
            (directory / (stem + ".tar.gz")).unlink()
            with self.assertRaisesRegex(RuntimeError, "exactly"):
                pypi_release.audit_dist(directory, "0.2.0")

    def test_cli_emits_normalized_version_and_source_sha(self):
        argv = ["pypi_release.py", "--repository", REPOSITORY, "--version", VERSION,
                "--source", "source", "--dist", "dist"]
        with patch("sys.argv", argv), patch.dict(os.environ, {"GH_TOKEN": "test", "GITHUB_OUTPUT": ""}), \
                patch("pypi_release.source_commit", return_value=COMMIT), \
                patch("pypi_release.published_release"), patch("pypi_release.verified_workflows"), \
                patch("pypi_release.audit_dist") as audit, redirect_stdout(io.StringIO()) as output:
            self.assertEqual(pypi_release.main(), 0)
        self.assertEqual(json.loads(output.getvalue()), {"package_version": "0.2.0", "commit": COMMIT})
        audit.assert_called_once_with(Path("dist"), "0.2.0")


if __name__ == "__main__":
    unittest.main()
