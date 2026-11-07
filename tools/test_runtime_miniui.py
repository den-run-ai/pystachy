"""The optional backend smoke must exercise real AOT program collection."""
from contextlib import redirect_stdout
import importlib.util
from io import StringIO
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("miniui_backend_check", ROOT / "examples/miniui/check_backend.py")
BACKEND = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BACKEND)


class BackendStressTests(unittest.TestCase):
    def test_direct_aot_stresses_execution_without_stressing_the_build(self):
        calls = []

        def execute(command, **kwargs):
            env = kwargs["env"]
            calls.append((command, dict(env)))
            # Model the runtime's actual setting, independent of the driver-only alias.
            count = 9 if env.get("PYSTACHY_GC_STRESS") == "1" else 0
            stderr = f"gc: {count} collections, 0.1 ms\n" if env.get("PYSTACHY_GC") == "stats" else ""
            return subprocess.CompletedProcess(command, 0, "backend matched\n", stderr)

        with patch.object(sys, "argv", ["check_backend.py", "--compiler", str(ROOT / "pystachy")]), \
                patch.dict(os.environ, {"PYSTACHY_GC_STRESS": "999", "PYSTACHY_GC": "off"}), \
                patch.object(BACKEND.subprocess, "run", side_effect=execute), redirect_stdout(StringIO()):
            BACKEND.main()
        builds = [env for command, env in calls if "build" in command]
        self.assertEqual(len(builds), 2)
        self.assertTrue(all("PYSTACHY_GC_STRESS" not in env for env in builds))
        executions = [env for command, env in calls
                      if command[0].endswith("/run.sh")
                      and (len(command) == 1 or (len(command) == 2 and command[-1].endswith("/probe-stress")))]
        self.assertEqual([env.get("PYSTACHY_GC_STRESS") for env in executions], ["0", "1"])
        self.assertEqual(executions[1]["PYSTACHY_GC"], "stats")

    def test_a_stress_label_requires_an_observed_collection(self):
        for stderr in ("", "gc: 0 collections, 0.0 ms\n"):
            with self.subTest(stderr=stderr), patch.object(BACKEND.subprocess, "run",
                    return_value=subprocess.CompletedProcess(["program"], 0, "matched\n", stderr)):
                with self.assertRaisesRegex(AssertionError, "did not report collections"):
                    BACKEND.run(["program"], ROOT, {}, require_gc=True)


if __name__ == "__main__":
    unittest.main()
