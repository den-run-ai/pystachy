"""Research harness checks using small fake executables, without native compilation."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("gc_application_build", HERE / "build.py")
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.home = self.work / "home"
        self.home.mkdir()
        (self.home / "runtime.c").write_text("/* fixture */\n")
        (self.home / "lib").mkdir()
        (self.home / "lib/value.py").write_text("value = 1\n")
        (self.home / "program.py").write_text(
            'from pathlib import Path\nimport sys\nPath(sys.argv[1]).write_bytes(b"payload")\nprint("ok")\n')
        self.compiler = self.work / "compiler.py"
        self.spec = {"source_root": "home", "oracle_python": sys.executable,
                     "run_env": {"APP_SETTING": "common"},
                     "cases": [{"name": "example", "source": "program.py", "args": ["{output}"],
                                "smoke_args": ["{output}"]}],
                     "variants": [{"name": "base", "compiler": "compiler.py", "home": "home",
                                   "run_env": {"PYSTACHY_GC_MIN": "32"}},
                                  {"name": "repeat", "build_from": "base",
                                   "run_env": {"PYSTACHY_GC_MIN": "32"}}]}
        self.make_compiler()

    def make_compiler(self, mutation="", changed_artifact=False):
        prefix = ('import os\nassert os.getenv("PYSTACHY_GC") == "stats"\n'
                  'assert os.getenv("PYSTACHY_GC_MIN") == "32"\n'
                  'assert os.getenv("APP_SETTING") == "common"\n'
                  'assert "GC_DONT_GC" not in os.environ\n')
        replace = '.replace(b"payload", b"changed")' if changed_artifact else ""
        self.compiler.write_text(f"#!{sys.executable}\nimport os,sys\nfrom pathlib import Path\n"
                                 + mutation + "\nsource = Path(sys.argv[2]).read_bytes()" + replace + "\n"
                                 + "target = Path(sys.argv[4])\n"
                                 + f"target.write_bytes({('#!' + sys.executable + chr(10) + prefix).encode()!r} + source)\n"
                                 + "target.chmod(0o755)\n")
        self.compiler.chmod(0o755)

    def invoke(self):
        spec = self.work / "spec.json"
        spec.write_text(json.dumps(self.spec))
        output = self.work / "output"
        result = subprocess.run([sys.executable, str(HERE / "build.py"), "--spec", str(spec), "--out", str(output)],
                                env=dict(os.environ, GC_DONT_GC="1"), capture_output=True, text=True)
        return result, output

    def test_build_environment_sanitization_and_explicit_override(self):
        with patch.dict(os.environ, {"GC_DONT_GC": "1", "PYSTACHY_GC": "off", "PATH": "/bin"}, clear=True):
            self.assertEqual(BUILD.clean_environment({"GC_INITIAL_HEAP_SIZE": "1048576"}),
                             {"PATH": "/bin", "GC_INITIAL_HEAP_SIZE": "1048576"})

    def test_fingerprint_follows_import_links_and_detects_changes(self):
        extra = self.work / "imports"
        extra.mkdir()
        (extra / "value.py").write_text("value = 1\n")
        (extra / "head.h").write_text("/* header */\n")
        (extra / "ignored.txt").write_text("ignored\n")
        (extra / "loop").symlink_to(extra, target_is_directory=True)
        link = self.work / "linked-imports"
        link.symlink_to(extra, target_is_directory=True)
        before = BUILD.fingerprint([link])
        self.assertEqual(set(before), {str(extra / "value.py"), str(extra / "head.h")})
        (extra / "value.py").write_text("value = 2\n")
        self.assertNotEqual(before, BUILD.fingerprint([link]))

    def test_exact_oracle_artifact_environment_and_same_binary_control(self):
        result, output = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((output / "builds.json").read_text())
        self.assertTrue(report["complete"])
        self.assertEqual(len(report["builds"]), 1)
        self.assertEqual(sum(k.startswith("home:") for k in report["source_manifests"]), 1)
        config = json.loads((output / "example.json").read_text())
        self.assertNotIn("PYSTACHY_GC_MIN", config["env"])
        a, b = config["variants"]
        self.assertEqual(a["argv"], b["argv"])
        self.assertEqual(a["env"], b["env"])
        self.assertEqual(a["validated_executable_sha256"], b["validated_executable_sha256"])
        self.assertEqual(report["cases"][0]["oracle_sha256"]["full"]["artifact"],
                         BUILD.digest(output / "base-example-full.artifact"))

    def test_invalid_reuse_is_rejected_before_output_creation(self):
        self.spec["variants"][1]["build_from"] = "missing"
        result, output = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())

    def test_changed_runtime_source_is_rejected(self):
        self.make_compiler('Path(os.environ["PYSTACHY_HOME"], "lib/value.py").write_text("value = 2\\n")')
        result, output = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("source or compiler changed", result.stderr)
        self.assertFalse(json.loads((output / "builds.json").read_text())["complete"])
        self.assertFalse((output / "example.json").exists())

    def test_changed_explicit_dependency_is_rejected(self):
        dependency = self.work / "liboptional.a"
        dependency.write_bytes(b"original library")
        self.spec["variants"][0]["build_inputs"] = ["liboptional.a"]
        self.make_compiler(f"Path({str(dependency)!r}).write_bytes(b'replaced library')")
        result, output = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("source or compiler changed", result.stderr)
        self.assertFalse(json.loads((output / "builds.json").read_text())["complete"])

    def test_changed_artifact_is_rejected_even_with_equal_stdout(self):
        self.make_compiler(changed_artifact=True)
        result, output = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("differs from CPython", result.stderr)
        self.assertFalse(json.loads((output / "builds.json").read_text())["complete"])


if __name__ == "__main__":
    unittest.main()
