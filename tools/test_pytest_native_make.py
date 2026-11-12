"""Exercise the native pytest target's process bounds and failure propagation."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(shutil.which("make") and shutil.which("xargs"), "make and xargs required")
class NativeMakeTests(unittest.TestCase):
    def run_target(self, failure=""):
        with tempfile.TemporaryDirectory(prefix="pytest-native-make-") as temporary:
            directory = Path(temporary)
            state = directory / "state.json"
            state.write_text(json.dumps({"active": 0, "peak": 0, "events": []}))
            python = directory / "python"
            python.write_text(f"#!{sys.executable}\n" + textwrap.dedent('''\
                import fcntl, json, os, sys, time
                args = sys.argv[1:]
                module = args[-1] if args[:2] == ["-m", "unittest"] else ""
                name = module or args[0]
                def record(event):
                    with open(os.environ["MAKE_TEST_STATE"], "r+") as handle:
                        fcntl.flock(handle, fcntl.LOCK_EX)
                        state = json.load(handle)
                        state["active"] += 1 if event == "start" else -1
                        state["peak"] = max(state["peak"], state["active"])
                        state["events"].append({"event": event, "name": name,
                                                "module": module, "args": args,
                                                "compiler": os.environ.get("PYSTACHY_PYTEST_NATIVE_COMPILER")})
                        handle.seek(0)
                        json.dump(state, handle)
                        handle.truncate()
                record("start")
                time.sleep(0.04)
                record("end")
                sys.exit(1 if name == os.environ.get("MAKE_TEST_FAIL") else 0)
                '''))
            python.chmod(0o755)
            env = dict(os.environ, MAKE_TEST_STATE=str(state), MAKE_TEST_FAIL=failure)
            for key in ("MAKEFLAGS", "MFLAGS", "MAKELEVEL"):
                env.pop(key, None)
            result = subprocess.run(["make", "--no-print-directory", "test-pytest-native",
                                     f"PY={python}", "PYSTACHY_LLVM=/unused",
                                     "PYTEST_NATIVE_COMPILER=/verified/pystachy2", "PYTEST_NATIVE_TEST_JOBS=2"],
                                    cwd=ROOT, env=env, text=True, capture_output=True, timeout=30)
            return result, json.loads(state.read_text())

    def test_all_modules_and_parity_parts_with_two_processes(self):
        result, state = self.run_target()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(state["active"], 0)
        self.assertLessEqual(state["peak"], 2)
        starts = [event for event in state["events"] if event["event"] == "start"]
        modules = [event for event in starts if event["module"]]
        expected = sorted(path.name for path in (ROOT / "tools").glob("test_pytest_native*.py"))
        self.assertEqual(sorted(event["module"] for event in modules), expected)
        self.assertTrue(all(event["compiler"] == "/verified/pystachy2" for event in modules))
        parts = [event for event in starts if not event["module"]]
        self.assertEqual(len(parts), 4)
        self.assertEqual(sorted(event["name"] for event in parts),
                         ["tools/pytest_native.py", "tools/pytest_native.py",
                          "tools/pytest_native_controls.py", "tools/pytest_native_upstream.py"])
        last_module_end = max(i for i, event in enumerate(state["events"])
                              if event["module"] and event["event"] == "end")
        first_part = min(i for i, event in enumerate(state["events"]) if not event["module"])
        self.assertLess(last_module_end, first_part)
        for event in parts:
            args = event["args"]
            if "--mode" in args and args[args.index("--mode") + 1] == "jit":
                self.assertNotIn("--compiler", args)  # Preserve hosted compiler coverage.
            else:
                self.assertEqual(args[args.index("--compiler") + 1], "/verified/pystachy2")

    def test_module_failure_stops_before_parity_parts(self):
        result, state = self.run_target("test_pytest_native.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(state["active"], 0)
        self.assertTrue(all(event["module"] for event in state["events"]))

    def test_parity_failure_fails_make(self):
        result, state = self.run_target("tools/pytest_native_controls.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(state["active"], 0)
        self.assertLessEqual(state["peak"], 2)


if __name__ == "__main__":
    unittest.main()
