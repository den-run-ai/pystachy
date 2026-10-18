"""Import-sweep provenance and argument checks; no native compiler is required."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest import mock

import import_sweep as sweep


class MetadataTests(unittest.TestCase):
    def test_counts_keep_exclusions_and_timeouts_separate_from_errors(self):
        result = {"a": "OK", "b": "OK (stubs: _thread)", "c": "error: unsupported",
                  "d": "timeout: no result after 120 s", "re": "left out: lib/ has re"}
        self.assertEqual(sweep.counts(result, ["re"]),
                         {"total": 5, "included": 4, "excluded": 1, "ok": 2,
                          "error": 1, "timeout": 1, "ok_without_stubs": 1})

    def test_source_git_is_observed_separately_and_unavailable_is_unknown(self):
        replies = [subprocess.CompletedProcess([], 0, stdout=value)
                   for value in ("/source\n", "abc123\n", " M source.py\n")]
        with mock.patch.object(sweep.subprocess, "run", side_effect=replies):
            self.assertEqual(sweep.source_git("/source"),
                             {"root": "/source", "revision": "abc123", "dirty": True})
        with mock.patch.object(sweep.subprocess, "run", side_effect=FileNotFoundError):
            self.assertEqual(sweep.source_git("/missing"),
                             {"root": "/missing", "revision": None, "dirty": None})

    def test_sha_is_the_compiler_file_contents(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "compiler"
            path.write_bytes(b"the actual compiler bytes")
            self.assertEqual(sweep.compiler_sha256(path), hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertIsNone(sweep.compiler_sha256(path.with_name("missing")))


class SweepTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.compiler = self.root / "compiler"
        self.compiler.write_text("#!/bin/sh\nexit 0\n")
        self.compiler.chmod(0o755)
        (self.root / "runtime.c").touch()
        self.stdlib = self.root / "stdlib"
        self.stdlib.mkdir()
        for name in ("good", "bad", "slow", "re"):
            (self.stdlib / f"{name}.py").touch()
        (self.stdlib / "test").mkdir()
        (self.stdlib / "test" / "ignored.py").touch()
        (self.root / "lib").mkdir()
        (self.root / "lib" / "re.py").touch()
        self.output = self.root / "out" / "results.json"
        self.metadata = self.root / "out" / "metadata.json"
        self.args = [str(self.compiler), str(self.stdlib), str(self.output)]
        patch = mock.patch.dict(os.environ)
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("PYSTACHY_HOME", None)

    @staticmethod
    def compile_one(cmd, env, directory, module, timeout, stubs):
        return {"good": "OK", "bad": "error: unsupported", "slow": "timeout: no result after 120 s"}[module], []

    def run_sweep(self, args):
        with contextlib.redirect_stdout(io.StringIO()), mock.patch.object(sweep, "compile_one", side_effect=self.compile_one):
            sweep.main(args)

    def test_metadata_preserves_result_mapping_and_records_overlay_scope(self):
        source = {"root": str(self.root), "revision": "unrelated-source-revision", "dirty": True}
        with mock.patch.object(sweep, "source_git", return_value=source):
            self.run_sweep(["-j", "2", "--metadata", str(self.metadata), *self.args])
        result = json.loads(self.output.read_text())
        self.assertEqual(result, {"good": "OK", "bad": "error: unsupported",
                                  "slow": "timeout: no result after 120 s", "re": "left out: lib/ has re"})
        metadata = json.loads(self.metadata.read_text())
        self.assertEqual(metadata["mode"], "import")
        self.assertEqual(metadata["python"]["version"], sweep.sys.version)
        self.assertEqual(metadata["stdlib"], str(self.stdlib))
        self.assertEqual(metadata["compiler"]["path"], str(self.compiler))
        self.assertEqual(metadata["compiler"]["sha256"], hashlib.sha256(self.compiler.read_bytes()).hexdigest())
        self.assertEqual(metadata["source_git"], source)
        self.assertIn("not proof", metadata["source_git_caveat"])
        self.assertEqual(metadata["overlay"]["ported_names"], ["re"])
        self.assertEqual(metadata["overlay"]["excluded_modules"], ["re"])
        self.assertIn("test", metadata["overlay"]["skipped_directories"])
        self.assertEqual(metadata["counts"], {"total": 4, "included": 3, "excluded": 1,
                                             "ok": 1, "error": 1, "timeout": 1, "ok_without_stubs": 1})
        self.assertGreaterEqual(metadata["duration_s"], 0)

    def test_metadata_is_optional_and_does_not_collect_provenance_by_default(self):
        with mock.patch.object(sweep, "source_git") as git, mock.patch.object(sweep, "compiler_sha256") as sha:
            self.run_sweep(self.args)
        self.assertTrue(self.output.is_file())
        self.assertFalse(self.metadata.exists())
        git.assert_not_called()
        sha.assert_not_called()

    def test_cli_writes_sidecar_through_real_subprocess_path(self):
        completed = subprocess.run([sweep.sys.executable, sweep.__file__, "-j", "1", "--metadata",
                                    str(self.metadata), *self.args], capture_output=True, text=True,
                                   check=True, timeout=30)
        self.assertIn("3 of 3 modules import", completed.stdout)
        self.assertEqual(json.loads(self.metadata.read_text())["counts"]["ok"], 3)
        self.assertEqual(json.loads(self.output.read_text())["re"], "left out: lib/ has re")

    def test_stubs_mode_records_hosted_entrypoint_and_used_stubs(self):
        (self.stdlib / "good.py").write_text("import _thread\n")
        package = types.ModuleType("src.pystachy_compiler")
        package.specs = types.SimpleNamespace(CBUILTIN={"_thread": 1}, STANDINS={})
        with mock.patch.dict(sweep.sys.modules, {"src.pystachy_compiler": package}), \
                mock.patch.object(sweep, "stub", return_value="pass\n"), \
                mock.patch.object(sweep, "compile_one", return_value=("OK", ["good"])), \
                contextlib.redirect_stdout(io.StringIO()):
            sweep.main(["--stubs", "--only", "_thread", "--metadata", str(self.metadata),
                        str(self.stdlib), str(self.output)])
        metadata = json.loads(self.metadata.read_text())
        self.assertEqual(metadata["mode"], "stubs")
        self.assertEqual(metadata["compiler"]["kind"], "hosted_entrypoint")
        self.assertEqual(metadata["compiler"]["path"], os.path.join(sweep.ROOT, "pystachy.py"))
        self.assertEqual(metadata["stubs"], ["_thread"])
        self.assertEqual(metadata["timeout_s"], sweep.STUB_TIMEOUT)
        self.assertEqual(metadata["counts"]["ok_without_stubs"], 0)
        self.assertIn("OK (stubs: _thread)", json.loads(self.output.read_text()).values())

    def test_legacy_overlay_argument_forms(self):
        for compiler in ([], [str(self.compiler)]):
            with self.subTest(compiler=compiler), mock.patch.object(sweep, "ported", return_value={"re"}):
                destination = self.root / "overlay"
                sweep.main(["--overlay", *compiler, str(self.stdlib), str(destination)])
                self.assertTrue((destination / "good.py").is_symlink())
                self.assertFalse((destination / "re.py").exists())

    def test_invalid_arguments_fail_before_compilation(self):
        bad_args = [["-j", "0", *self.args], ["-j", "-1", *self.args],
                    ["--only", "_thread", *self.args], [*self.args, "extra"],
                    ["--stubs", str(self.stdlib), str(self.output), "extra"],
                    ["--stubs", "--only", "_thread,"], ["--stubs", "--only", ""],
                    ["--metadata", str(self.output), *self.args],
                    ["--metadata", "", *self.args],
                    ["--metadata", str(self.compiler), *self.args],
                    ["--metadata", str(self.stdlib), *self.args],
                    [str(self.root / "missing"), str(self.stdlib), str(self.output)],
                    [str(self.compiler), str(self.root / "missing"), str(self.output)],
                    ["--overlay", str(self.stdlib)],
                    ["--overlay", str(self.stdlib), str(self.stdlib)]]
        for args in bad_args:
            with self.subTest(args=args), mock.patch.object(sweep, "compile_one") as compile_one:
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                    sweep.main(args)
                self.assertEqual(caught.exception.code, 2)
                compile_one.assert_not_called()

    def test_ineligible_stub_name_is_not_silently_ignored(self):
        with mock.patch.object(sweep, "compile_one") as compile_one:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                sweep.main(["--stubs", "--only", "not_a_real_builtin", str(self.stdlib), str(self.output)])
            self.assertEqual(caught.exception.code, 2)
            compile_one.assert_not_called()


if __name__ == "__main__":
    unittest.main()
