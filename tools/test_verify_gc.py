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
CASES = ["tests/programs/x/example.py", "tests/programs/x/syntax_example.py", "tests/deviations/example.py",
         "tests/errors/x/example.py", "tests/errors/x/syntax_example.py"]
GC_STEPS = ["gc-self", "gc-jit-0", "gc-jit-1", "gc-aot-0", "gc-aot-1", "gc-aot-2"]
SUITES = [("gc-jit-0", "jit", 4), ("gc-jit-1", "jit", 3), ("gc-aot-0", "aot", 2), ("gc-aot-1", "aot", 4),
          ("gc-aot-2", "aot", 1)]


@unittest.skipUnless(TIMEOUT, "GNU timeout is required by verification")
class GCVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("tests", "tests/programs", "tests/programs/x", "tests/deviations", "tests/errors",
                     "tests/errors/x", "src", "lib", "ryu", "mpz", "bin"):
            (self.root / name).mkdir()
        for name in ("tests/verify.sh", "tests/corpus.sh"):
            shutil.copy(ROOT / name, self.root / name)
        for name in ("pystachy.py", "runtime.py", "runtime.c", "tests/programs/x/example.py",
                     "tests/programs/x/syntax_example.py", "tests/deviations/example.py"):
            (self.root / name).write_text("# fixture\n")
        (self.root / "tests/errors/x/example.py").write_text("# error: mock rejection\n")
        (self.root / "tests/errors/x/syntax_example.py").write_text("# error: syntax_example.py: mock syntax\n")
        compiler = self.root / "bin/compiler"
        compiler.write_text(f"#!{sys.executable}\n" + '''import os
import signal
if os.environ.get("VERIFY_MOCK_MODE") == "timeout-kill" and os.environ.get("PYSTACHY_GC_STRESS"):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)   # before the other imports: TERM must find it ignored
from pathlib import Path
import shutil
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
        assert os.environ["PYSTACHY_GC_STRESS"] == "5000"
        assert os.environ["PYSTACHY_GC"] == "stats"
        Path("gc-child.pid").write_text(str(os.getpid()))
        mode = os.environ["VERIFY_MOCK_MODE"]
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
[ "$PYSTACHY_GC_STRESS" = 1000 ] || exit 9
[ "$PYSTACHY_GC_STRESS_PROGRAM" = 1 ] || exit 9
mode=$2; shift 2
echo "suite mode: $mode"
case "$mode" in
  jit)
    [ "$LC_ALL" = C.UTF-8 ] && [ $# -gt 0 ] || exit 9
    case "$1" in tests/programs/x/example.py) group=jit-0 ;; tests/programs/x/syntax_example.py) group=jit-1 ;; *) exit 9 ;; esac ;;
  aot)
    [ "$LC_ALL" = C.UTF-8 ] && [ $# -gt 0 ] || exit 9
    case "$1" in tests/programs/x/example.py) group=aot-0 ;; tests/programs/x/syntax_example.py) group=aot-1 ;; tests/deviations/example.py) group=aot-2 ;; *) exit 9 ;; esac ;;
  *) echo "invalid mode: $mode"; exit 9 ;;
esac
checks=0
for file; do
  echo "selected: $file"
  case "$file" in
    tests/programs/x/example.py|tests/deviations/example.py|tests/errors/x/example.py) checks=$((checks + 1)) ;;
    tests/programs/x/syntax_example.py|tests/errors/x/syntax_example.py) checks=$((checks + 2)) ;;
    *) exit 9 ;;
  esac
done
if [ "$VERIFY_MOCK_MODE" = "suite-$group-failure" ]; then
  echo "$((checks - 1)) passed, 1 failed"
  exit 1
fi
if [ "$VERIFY_MOCK_MODE" = short-suite ]; then
  echo "$((checks - 1)) passed, 0 failed"
  exit 0
fi
echo "$checks passed, 0 failed"
''')
        suite.chmod(0o755)
        timeout = self.root / "bin/timeout"
        timeout.write_text(f"#!{sys.executable}\n" + f'''import os
import sys
assert sys.argv[1:4] == ["--verbose", "--kill-after=10s", "10m"]
mode = os.environ["VERIFY_MOCK_MODE"]
# timeout-kill's mock must ignore TERM before it comes: 0.2s is less than a cold Python's start
limit = "3s" if mode == "timeout-kill" else "0.2s" if mode.startswith("timeout") else "10s"
os.execv({TIMEOUT!r}, [{TIMEOUT!r}, "--verbose", "--kill-after=0.2s", limit, *sys.argv[4:]])
''')
        timeout.chmod(0o755)
        self.env = {**os.environ, "PY": str(compiler), "LC_ALL": "C.UTF-8",
                    "PATH": str(self.root / "bin") + os.pathsep + os.environ["PATH"]}

    def run_group(self, group, mode="pass"):
        result = subprocess.run(["sh", "tests/verify.sh", group], cwd=self.root,
                                env={**self.env, "VERIFY_MOCK_MODE": mode},
                                text=True, capture_output=True, timeout=15)
        report = json.loads((self.root / "build/verification.json").read_text())
        logs = {step["name"]: (self.root / step["log"]).read_text() for step in report["steps"]}
        return result, report, logs

    def test_self_compile_preserves_ir_stress_and_gc_diagnostics(self):
        result, report, logs = self.run_group("gc-self")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(report["result"], "pass")
        self.assertEqual([step["name"] for step in report["steps"]], ["bootstrap", "gc-self"])
        step = report["steps"][-1]
        self.assertTrue(step["ir_identical"])
        self.assertEqual(step["compiler_interval"], 5000)
        self.assertNotIn("expected", step)
        for text in ("gc-self: started", "limit 10m", "gc-self: finished after", "gc statistics"):
            self.assertIn(text, logs["gc-self"])

    def test_each_suite_runs_its_complete_selection_at_original_stress(self):
        observed = {}
        for group, mode, count in SUITES:
            with self.subTest(group=group):
                result, report, logs = self.run_group(group)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(report["result"], "pass")
                self.assertEqual([step["name"] for step in report["steps"]], ["bootstrap", group])
                step = report["steps"][-1]
                self.assertEqual((step["passed"], step["failed"], step["expected"]), (count, 0, count))
                self.assertEqual(step["modes"], [mode])
                self.assertEqual((step["tests_compiler_interval"], step["tests_interval"]), (1000, 1))
                self.assertEqual(report["sources"]["mode_checks"], 7)  # (CASES's checks in one mode)
                self.assertIn(f"suite mode: {mode}", logs[group])
                self.assertFalse((self.root / "gc-child.pid").exists())
                observed[group] = [line.removeprefix("selected: ") for line in logs[group].splitlines()
                                   if line.startswith("selected: ")]
                index, shard_count = int(group[-1]), (3 if mode == "aot" else 2)
                self.assertEqual((step["shard_index"], step["shard_count"]), (index, shard_count))
                self.assertEqual(observed[group], CASES[index::shard_count])
        for kind, shard_count in (("gc-jit", 2), ("gc-aot", 3)):
            shards = [observed[f"{kind}-{index}"] for index in range(shard_count)]
            self.assertEqual(sum(map(len, shards)), len(set().union(*shards)))  # disjoint
            self.assertCountEqual([case for shard in shards for case in shard], CASES)

    def test_local_aliases_run_all_selected_gc_checks(self):
        for group, expected in (("gc-stress", GC_STEPS), ("gc-jit", GC_STEPS[1:3]), ("gc-aot", GC_STEPS[3:])):
            with self.subTest(group=group):
                result, report, logs = self.run_group(group)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(report["result"], "pass")
                self.assertEqual([step["name"] for step in report["steps"]], ["bootstrap", *expected])
                if group == "gc-stress":
                    self.assertIn("gc statistics", logs["gc-self"])
                for suite, mode, count in SUITES:
                    if suite not in expected:
                        continue
                    step = next(step for step in report["steps"] if step["name"] == suite)
                    self.assertEqual((step["passed"], step["expected"]), (count, count))
                    self.assertEqual(step["modes"], [mode])
                    self.assertIn(f"suite mode: {mode}", logs[suite])

    def test_failure_timeout_and_mismatched_ir_cannot_pass(self):
        for mode, text in (("failure", "mock compiler failed"),
                           ("timeout", "sending signal TERM"),
                           ("timeout-kill", "sending signal KILL"),
                           ("mismatch", "differ")):
            with self.subTest(mode=mode):
                result, report, logs = self.run_group("gc-self", mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(report["result"], "fail")
                self.assertEqual(report["steps"][-1]["result"], "fail")
                self.assertIn(text, logs["gc-self"])

    def test_failed_and_incomplete_suites_cannot_pass(self):
        for group, _, _ in SUITES:
            for failure in (f"suite-{group.removeprefix('gc-')}-failure", "short-suite"):
                with self.subTest(group=group, failure=failure):
                    result, report, _ = self.run_group(group, failure)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(report["result"], "fail")
                    self.assertEqual(report["steps"][-1]["result"], "fail")

    def test_local_alias_reports_failure_and_still_runs_remaining_modes(self):
        for failure in ("failure", "suite-jit-0-failure", "suite-jit-1-failure", "suite-aot-0-failure",
                        "suite-aot-1-failure", "suite-aot-2-failure"):
            with self.subTest(failure=failure):
                result, report, logs = self.run_group("gc-stress", failure)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(report["result"], "fail")
                self.assertEqual([step["name"] for step in report["steps"]], ["bootstrap", *GC_STEPS])
                for group, mode, _ in SUITES:
                    self.assertIn(f"suite mode: {mode}", logs[group])

    def test_cancellation_terminates_the_background_compiler(self):
        process = subprocess.Popen(["sh", "tests/verify.sh", "gc-self"], cwd=self.root,
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
