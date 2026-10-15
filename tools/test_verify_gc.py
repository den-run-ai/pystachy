"""Exercise the real GC verification shell with deterministic compiler/test doubles."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parent.parent
TIMEOUT = shutil.which("timeout")


@unittest.skipUnless(TIMEOUT, "GNU timeout is required by verification")
class GCVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("tests", "src", "lib", "ryu", "bin"):
            (self.root / name).mkdir()
        shutil.copy(ROOT / "tests/verify.sh", self.root / "tests/verify.sh")
        for name in ("pystachy.py", "runtime.py", "runtime.c", "tests/example.py"):
            (self.root / name).write_text("# fixture\n")
        compiler = self.root / "bin/compiler"
        compiler.write_text(f"#!{sys.executable}\n" + '''import os
from pathlib import Path
import shutil
import signal
import sys
import time
args = sys.argv[1:]
if args == ["-"]:
    os.execv(sys.executable, [sys.executable, "-"])
if args == ["--version"]:
    print("mock compiler")
    sys.exit(0)
if args[0] == "pystachy.py":
    args = args[1:]
output = Path(args[args.index("-o") + 1])
if args[0] == "build":
    shutil.copy(__file__, output)
    output.chmod(0o755)
else:
    text = "fixed point\\n"
    if os.environ.get("PYSTACHY_GC_STRESS"):
        assert os.environ["PYSTACHY_GC_STRESS"] == "1000"
        assert os.environ["PYSTACHY_GC"] == "stats"
        Path("gc-child.pid").write_text(str(os.getpid()))
        mode = os.environ["VERIFY_MOCK_MODE"]
        if mode == "timeout-kill":
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
        if mode in ("timeout", "timeout-kill", "signal"):
            time.sleep(30)
        if mode == "failure":
            print("mock compiler failed", file=sys.stderr)
            sys.exit(7)
        if mode == "mismatch":
            text = "wrong IR\\n"
        print("gc statistics", file=sys.stderr)
    output.write_text(text)
''')
        compiler.chmod(0o755)
        suite = self.root / "tests/run.sh"
        suite.write_text('''#!/bin/sh
if [ "$VERIFY_MOCK_MODE" = suite-failure ]; then
  echo '0 passed, 2 failed'
  exit 1
fi
echo '2 passed, 0 failed'
''')
        suite.chmod(0o755)
        timeout = self.root / "bin/timeout"
        timeout.write_text(f"#!{sys.executable}\n" + f'''import os
import sys
assert sys.argv[1:4] == ["--verbose", "--kill-after=10s", "30m"]
limit = "0.2s" if os.environ["VERIFY_MOCK_MODE"].startswith("timeout") else "10s"
os.execv({TIMEOUT!r}, [{TIMEOUT!r}, "--verbose", "--kill-after=0.2s", limit, *sys.argv[4:]])
''')
        timeout.chmod(0o755)
        self.env = {**os.environ, "PY": str(compiler),
                    "PATH": str(self.root / "bin") + os.pathsep + os.environ["PATH"]}

    def run_group(self, mode):
        result = subprocess.run(["sh", "tests/verify.sh", "gc-stress"], cwd=self.root,
                                env={**self.env, "VERIFY_MOCK_MODE": mode},
                                text=True, capture_output=True, timeout=15)
        report = json.loads((self.root / "build/verification.json").read_text())
        log = (self.root / "build/verify/gc-stress.log").read_text()
        return result, report, log

    def test_success_preserves_counts_ir_and_gc_diagnostics(self):
        result, report, log = self.run_group("pass")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(report["result"], "pass")
        step = report["steps"][-1]
        self.assertEqual((step["passed"], step["failed"], step["expected"]), (2, 0, 2))
        self.assertTrue(step["ir_identical"])
        for text in ("gc-self: started", "gc-self: finished after", "gc statistics", "gc-self: exit 0"):
            self.assertIn(text, log)

    def test_failure_timeout_mismatch_and_failed_suite_cannot_pass(self):
        for mode, text in (("failure", "gc-self: exit 7"), ("timeout", "gc-self: exit 124"),
                           ("timeout-kill", "gc-self: exit 137"),
                           ("mismatch", "differ"), ("suite-failure", "0 passed, 2 failed")):
            with self.subTest(mode=mode):
                result, report, log = self.run_group(mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(report["result"], "fail")
                self.assertEqual(report["steps"][-1]["result"], "fail")
                self.assertIn(text, log)
                if mode.startswith("timeout"):
                    self.assertIn("sending signal TERM", log)

    def test_cancellation_terminates_the_background_compiler(self):
        process = subprocess.Popen(["sh", "tests/verify.sh", "gc-stress"], cwd=self.root,
                                   env={**self.env, "VERIFY_MOCK_MODE": "signal"},
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                   start_new_session=True)
        try:
            deadline = time.monotonic() + 5
            pidfile = self.root / "gc-child.pid"
            while not pidfile.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(pidfile.exists())
            child = int(pidfile.read_text())
            process.terminate()
            process.communicate(timeout=5)
            self.assertEqual(process.returncode, 130)
            with self.assertRaises(ProcessLookupError):
                os.kill(child, 0)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()


if __name__ == "__main__":
    unittest.main()
