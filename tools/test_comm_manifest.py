"""Workload import identity controls for the compiler dogfood coordinator."""

from contextlib import chdir, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("comm_manifest_batch", ROOT / "examples" / "comm" / "compiler_batch.py")
assert SPEC is not None and SPEC.loader is not None
BATCH = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BATCH
SPEC.loader.exec_module(BATCH)


class CompilerManifestTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.root = Path(temporary.name)
        self.addCleanup(temporary.cleanup)
        environment = {name: value for name, value in os.environ.items()
                       if not name.startswith("PYSTACHY_") and name not in ("PYTHONPATH", "PYTHONHOME", "PYTHONSAFEPATH")}
        environment.update(PYSTACHY_HOME=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
        self.environment = patch.dict(os.environ, environment, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.command = [sys.executable, str(ROOT / "pystachy.py")]

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def manifest(self, source):
        return BATCH.input_manifest(self.command, None, [source])

    def test_sibling_import_and_same_size_transitive_change(self):
        source = self.write("entry/main.py", "from helper import value\nprint(value())\n")
        helper = self.write("entry/helper.py", "from dependency import value\n")
        dependency = self.write("entry/dependency.py", "def value() -> int:\n    return 111\n")
        before = self.manifest(source)
        self.assertIn(str(helper), before["files"])
        self.assertIn(str(dependency), before["files"])
        stat = dependency.stat()
        dependency.write_text("def value() -> int:\n    return 222\n")
        os.utime(dependency, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        after = self.manifest(source)
        self.assertNotEqual(before, after)
        self.assertNotEqual(before["files"][str(dependency)], after["files"][str(dependency)])

    def test_pystachy_path_package_relative_imports(self):
        source = self.write("entry/main.py", "from package import value\nprint(value())\n")
        package = self.write("imports/package/__init__.py", "from .helper import value\n")
        helper = self.write("imports/package/helper.py", "from .nested.dependency import value\n")
        self.write("imports/package/nested/__init__.py", "")
        dependency = self.write("imports/package/nested/dependency.py", "def value() -> int:\n    return 111\n")
        os.environ["PYSTACHY_PATH"] = str(self.root / "imports")
        before = self.manifest(source)
        for path in (package, helper, dependency):
            self.assertIn(str(path), before["files"])
        dependency.write_text("def value() -> int:\n    return 222\n")
        after = self.manifest(source)
        self.assertNotEqual(before["files"][str(dependency)], after["files"][str(dependency)])

    def test_namespace_imports_from_multiple_search_roots(self):
        source = self.write("entry/main.py", "from package.one import first\nfrom package.two import second\nprint(first, second)\n")
        first = self.write("first/package/one.py", "first = 1\n")
        second = self.write("second/package/two.py", "second = 2\n")
        os.environ["PYSTACHY_PATH"] = f"{self.root / 'first'}::{self.root / 'second'}:"
        manifest = self.manifest(source)
        self.assertIn(str(first), manifest["files"])
        self.assertIn(str(second), manifest["files"])

    def test_new_shadow_module_and_package_change_resolution(self):
        source = self.write("entry/main.py", "from dependency import value\nprint(value)\n")
        original = self.write("imports/dependency.py", "value = 1\n")
        os.environ["PYSTACHY_PATH"] = str(self.root / "imports")
        before = self.manifest(source)
        shadow = self.write("entry/dependency.py", "value = 1\n")
        shadowed = self.manifest(source)
        self.assertNotEqual(before, shadowed)
        self.assertIn(str(original), before["files"])
        self.assertNotIn(str(original), shadowed["files"])
        self.assertIn(str(shadow), shadowed["files"])
        package = self.write("entry/dependency/__init__.py", "value = 1\n")
        packaged = self.manifest(source)
        self.assertNotEqual(shadowed, packaged)
        self.assertNotIn(str(shadow), packaged["files"])
        self.assertIn(str(package), packaged["files"])

    def test_relative_search_paths_use_compiler_job_directory(self):
        source = self.write("entry/main.py", "from dependency import value\nprint(value)\n")
        dependency = self.write("imports/dependency.py", "value = 1\n")
        os.environ["PYSTACHY_PATH"] = os.path.relpath(dependency.parent, ROOT)
        with chdir(self.root):
            manifest = self.manifest(source)
        self.assertIn(str(dependency), manifest["files"])

    def test_search_path_order_and_environment_state_are_inputs(self):
        source = self.write("entry/main.py", "from dependency import value\nprint(value)\n")
        first = self.write("first/dependency.py", "value = 1\n")
        second = self.write("second/dependency.py", "value = 1\n")
        os.environ["PYSTACHY_PATH"] = f"{first.parent}:{second.parent}"
        before = self.manifest(source)
        os.environ["PYSTACHY_PATH"] = f"{second.parent}:{first.parent}"
        after = self.manifest(source)
        self.assertNotEqual(before, after)
        self.assertIn(str(first), before["files"])
        self.assertIn(str(second), after["files"])
        os.environ["PYSTACHY_OPT"] = "-listfast"
        self.assertNotEqual(after, self.manifest(source))

    @unittest.skipUnless(hasattr(os, "symlink"), "requires filesystem symlinks")
    def test_symlink_search_root_retarget_with_identical_content(self):
        source = self.write("entry/main.py", "from dependency import value\nprint(value)\n")
        first = self.write("first/dependency.py", "value = 1\n")
        second = self.write("second/dependency.py", "value = 1\n")
        alias = self.root / "alias"
        alias.symlink_to(first.parent, target_is_directory=True)
        os.environ["PYSTACHY_PATH"] = str(alias)
        before = self.manifest(source)
        alias.unlink()
        alias.symlink_to(second.parent, target_is_directory=True)
        after = self.manifest(source)
        self.assertEqual(before["files"], after["files"])
        self.assertNotEqual(before["workloads"], after["workloads"])

    def test_shadowed_builtin_ffi_and_fresh_process_per_workload(self):
        source = self.write("entry/main.py", "from ffi import value\nprint(value)\n")
        ffi = self.write("entry/ffi.py", "value = 1\n")
        before = self.manifest(source)
        self.assertIn(str(ffi), before["files"])
        self.assertEqual(before, self.manifest(source))
        other = self.write("other/main.py", "print(1)\n")
        mixed = BATCH.input_manifest(self.command, None, [source, other])
        self.assertIn(str(ffi), mixed["workloads"][str(source)]["files"])
        self.assertNotIn(str(ffi), mixed["workloads"][str(other)]["files"])

    def test_manifest_preflight_never_executes_workload(self):
        marker = self.root / "executed"
        source = self.write("entry/main.py", f"with open({str(marker)!r}, 'w') as stream:\n    stream.write('ran')\n")
        self.manifest(source)
        self.assertFalse(marker.exists())

    def test_unsupported_source_keeps_compiler_diagnostic(self):
        source = self.write("entry/main.py", "import unavailable_manifest_module\n")
        result = subprocess.run(self.command + ["ir", str(source)], cwd=ROOT,
                                capture_output=True, text=True, timeout=20)
        self.assertNotEqual(result.returncode, 0)
        with self.assertRaisesRegex(RuntimeError, "cannot resolve workload imports") as caught:
            self.manifest(source)
        self.assertIn(result.stderr.strip(), str(caught.exception))

    def test_optional_import_lookahead_and_new_missing_candidate(self):
        source = self.write("entry/main.py", "try:\n    from optional_dependency import value\nexcept ImportError:\n    value = 1\nprint(value)\n")
        before = self.manifest(source)
        dependency = self.write("entry/optional_dependency.py", "raise ImportError('unavailable')\nvalue = 1\n")
        present = self.manifest(source)
        self.assertNotEqual(before, present)
        self.assertIn(str(dependency), present["files"])
        dependency.write_text("raise ImportError('different')\nvalue = 1\n")
        self.assertNotEqual(present, self.manifest(source))

    def test_ignored_workload_import_is_captured(self):
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True)
        self.write(".gitignore", "entry/dependency.py\n")
        source = self.write("entry/main.py", "from dependency import value\nprint(value)\n")
        dependency = self.write("entry/dependency.py", "value = 1\n")
        subprocess.run(["git", "check-ignore", "--quiet", str(dependency)], cwd=self.root, check=True)
        self.assertIn(str(dependency), self.manifest(source)["files"])

    @unittest.skipUnless(hasattr(os, "symlink"), "requires filesystem symlinks")
    def test_entrypoint_symlink_uses_real_source_directory(self):
        source = self.write("entry/main.py", "from dependency import value\nprint(value)\n")
        dependency = self.write("entry/dependency.py", "value = 1\n")
        wrong = self.write("alias/dependency.py", "value = 2\n")
        link = self.root / "alias" / "main.py"
        link.symlink_to(source)
        files = self.manifest(link)["files"]
        self.assertIn(str(dependency), files)
        self.assertNotIn(str(wrong), files)

    def test_external_compiler_home_for_native_and_hosted_commands(self):
        source = self.write("entry/main.py", "from dependency import value\nprint(value)\n")
        self.write("external/runtime.c", "")
        dependency = self.write("external/lib/dependency.py", "value = 1\n")
        script = self.write("external/pystachy.py", "")
        native = self.write("external/bin/pystachy", "")
        os.environ.pop("PYSTACHY_HOME")
        for command in ([sys.executable, str(script)], [str(native)]):
            with self.subTest(command=command):
                manifest = BATCH.input_manifest(command, None, [source])
                self.assertIn(str(dependency), manifest["files"])
        self.assertEqual(BATCH.compiler_home([sys.executable, "-m", "pystachy"]), ROOT)
        for arguments in (["-c", "import runpy; runpy.run_module('pystachy', run_name='__main__')"],
                          ["-I", "-m", "pystachy"], ["-P", "-m", "pystachy"]):
            with self.subTest(arguments=arguments):
                with self.assertRaisesRegex(ValueError, "set PYSTACHY_HOME"):
                    BATCH.compiler_home([sys.executable] + arguments)
        os.environ["PYSTACHY_HOME"] = str(self.root / "external")
        manifest = BATCH.input_manifest([sys.executable, "-c", "import pystachy"], None, [source])
        self.assertIn(str(dependency), manifest["files"])

    @unittest.skipUnless(hasattr(os, "symlink"), "requires filesystem symlinks")
    def test_safe_module_invocation_requires_explicit_home(self):
        source = self.write("entry/main.py", "from textwrap import dedent\nprint(dedent('test'))\n")
        entrypoint = self.write("external/pystachy.py", (ROOT / "pystachy.py").read_text())
        self.write("external/runtime.c", "")
        dependency = self.write("external/lib/textwrap.py", "def dedent(s: str) -> str:\n    return '111'\n")
        (entrypoint.parent / "src").symlink_to(ROOT / "src", target_is_directory=True)
        os.environ.pop("PYSTACHY_HOME")
        os.environ["PYTHONPATH"] = str(entrypoint.parent)
        command = [sys.executable, "-m", "pystachy"]
        for value in ("1", "0"):
            # CPython treats every nonempty value, including "0", as enabled.
            with self.subTest(safe_path=value):
                os.environ["PYTHONSAFEPATH"] = value
                origin = subprocess.run([sys.executable, "-c", "import pystachy; print(pystachy.__file__)"],
                                        cwd=ROOT, capture_output=True, text=True, timeout=20, check=True)
                self.assertEqual(origin.stdout.strip(), str(entrypoint))
                self.assertEqual(origin.stderr, "")
                with self.assertRaisesRegex(ValueError, "set PYSTACHY_HOME.*PYTHONSAFEPATH"):
                    BATCH.input_manifest(command, None, [source])

        os.environ["PYSTACHY_HOME"] = str(entrypoint.parent)
        manifests = []
        outputs = []
        for value in ("111", "222"):
            dependency.write_text(f"def dedent(s: str) -> str:\n    return '{value}'\n")
            manifest = BATCH.input_manifest(command, None, [source])
            self.assertIn(str(dependency), manifest["files"])
            manifests.append(manifest)
            result = subprocess.run(command + ["ir", str(source)], cwd=ROOT,
                                    capture_output=True, timeout=20, check=True)
            self.assertEqual(result.stderr, b"")
            self.assertTrue(result.stdout)
            outputs.append(result.stdout)
        self.assertNotEqual(outputs[0], outputs[1])
        self.assertNotEqual(manifests[0], manifests[1])

    def test_python_safe_path_environment_is_an_input(self):
        source = self.write("entry/main.py", "print(1)\n")
        before = self.manifest(source)
        os.environ["PYTHONSAFEPATH"] = "1"
        after = self.manifest(source)
        self.assertTrue(before != after, "PYTHONSAFEPATH must change manifest identity")
        self.assertEqual(after["environment"]["PYTHONSAFEPATH"], "1")

    def test_after_measurement_check_rejects_import_mutation(self):
        source = self.write("entry/main.py", "from dependency import value\nprint(value)\n")
        dependency = self.write("entry/dependency.py", "value = 1\n")
        output = self.root / "report"

        def measured(jobs, **kwargs):
            dependency.write_text("value = 2\n")
            return {"seconds": 0.001, "completion_order": [job.job_id for job in jobs],
                    "records": [{"job": job.job_id, "status": 0, "diagnostics": 0, "sha256": "unchanged-ir"}
                                for job in jobs]}

        with patch.object(BATCH, "run_batch", side_effect=measured), redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "consumed inputs changed during measurement"):
                BATCH.main(["--compiler-command", json.dumps(self.command), "--directory", str(output),
                            "--sources", str(source), "--mode", "ir", "--samples", "1", "--warmups", "1"])
        report = json.loads((output / "report.json").read_text())
        self.assertEqual(report["result"], "fail")
        self.assertNotEqual(report["inputs"], report["inputs_after"])


if __name__ == "__main__":
    unittest.main()
