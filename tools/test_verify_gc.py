"""Exercise the real GC verification shell with deterministic compiler/test doubles: the bounded
self-compilation, the gc-ir halves (the compiler collecting every 1000 allocations against stage 2,
through the real tools/irsame.sh) and the program-stressed suites with their compiler-stressed samples."""
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
# the checks tests/run.sh makes of each case in one mode (tests/verify.sh's checks)
CHECKS = {"tests/programs/x/example.py": 1, "tests/programs/x/syntax_example.py": 2, "tests/deviations/example.py": 1,
          "tests/errors/x/example.py": 1, "tests/errors/x/syntax_example.py": 2}
GC_STEPS = ["gc-self", "gc-ir-0", "gc-ir-1", "gc-jit-0", "gc-jit-1", "gc-aot-0", "gc-aot-1"]
# group, mode, half, the shard of 32 its sample runs with the compiler stressed too (I for JIT, 2 + I for
# AOT, which lies in half I), and its steps after bootstrap
SUITES = [("gc-jit-0", "jit", 0, 0, ["gc-ir-0", "gc-jit-0"]), ("gc-jit-1", "jit", 1, 1, ["gc-ir-1", "gc-jit-1"]),
          ("gc-aot-0", "aot", 0, 2, ["gc-aot-0"]), ("gc-aot-1", "aot", 1, 3, ["gc-aot-1"])]


@unittest.skipUnless(TIMEOUT, "GNU timeout is required by verification")
class GCVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("tests", "tests/programs", "tests/programs/x", "tests/deviations", "tests/errors",
                     "tests/errors/x", "src", "lib", "ryu", "mpz", "bin", "tools"):
            (self.root / name).mkdir()
        for name in ("tests/verify.sh", "tests/corpus.sh", "tools/irsame.sh"):
            shutil.copy(ROOT / name, self.root / name)
        for name in ("pystachy.py", "runtime.py", "runtime.c", "tests/programs/x/example.py",
                     "tests/programs/x/syntax_example.py", "tests/deviations/example.py"):
            (self.root / name).write_text("# fixture\n")
        (self.root / "tests/errors/x/example.py").write_text("# error: mock rejection\n")
        (self.root / "tests/errors/x/syntax_example.py").write_text("# error: syntax_example.py: mock syntax\n")
        compiler = self.root / "bin/compiler"
        compiler.write_text(f"#!{sys.executable}\n" + '''import os
import signal
if os.environ.get("VERIFY_MOCK_MODE") == "timeout-kill" and os.environ.get("PYSTACHY_GC_STRESS") == "5000":
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
if not args:  # (tools/irsame.sh asks the usage whether rt exists)
    print("usage: pystachy run FILE.py\\n       pystachy rt runtime.py [-o OUT.ll]", file=sys.stderr)
    sys.exit(2)
mode = os.environ.get("VERIFY_MOCK_MODE", "")
stress = os.environ.get("PYSTACHY_GC_STRESS", "")
if args[0] in ("ir", "rt", "check") and (args[1].startswith("tests/") or (args[0] == "rt" and stress == "1000")):
    # a case of the corpus, or runtime.py, compiled by stage 2 or by it collecting every 1000 (gc-ir)
    assert stress in ("", "1000"), stress
    case = args[1]
    if args[0] != "check":
        assert os.environ.get("PYSTACHY_IRCHECK") == "1"
    with open("compiles.log", "a") as log:
        print(args[0], case, stress or "-", file=log)
    stressed = stress == "1000"
    target = {"gc-ir-differs": "tests/programs/x/example.py", "gc-msg-differs": "tests/errors/x/syntax_example.py",
              "gc-status-differs": "tests/deviations/example.py", "gc-check-differs": "tests/programs/x/syntax_example.py",
              "gc-rt-differs": "runtime.py"}.get(mode)
    differs = stressed and case == target and (args[0] == "check") == (mode == "gc-check-differs")
    if "/errors/" in case:
        print(f"{case}:1: error: mock {'stressed ' if differs else ''}rejection", file=sys.stderr)
        sys.exit(1)
    if args[0] == "check":
        print(" (stressed)" if differs else "", end="")
        sys.exit(0)
    output = Path(args[args.index("-o") + 1])
    if case == "runtime.py":
        output.write_text("wrong runtime IR\\n" if differs else "fixed point\\n")
        sys.exit(0)
    output.write_text(f"IR of {case}{' (stressed)' if differs and mode == 'gc-ir-differs' else ''}\\n")
    sys.exit(3 if differs and mode == "gc-status-differs" else 0)
if args[0] == "pystachy.py":
    args = args[1:]
output = Path(args[args.index("-o") + 1])
if args[0] == "build":
    shutil.copy(__file__, output)
    output.chmod(0o755)
else:
    text = "fixed point\\n"
    if stress:
        assert stress == "5000", stress
        assert os.environ["PYSTACHY_GC"] == "stats"
        Path("gc-child.pid").write_text(str(os.getpid()))
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
        # (a program-stressed run of a half, or its sample with the compiler stressed too; the group is
        # named by its mode and the half of its first case)
        suite.write_text('''#!/bin/sh
[ "$PYSTACHY_GC_STRESS_PROGRAM" = 1 ] || exit 9
case $PYSTACHY_CACHE in */build/verify/gc-cache) ;; *) exit 9 ;; esac
case ${PYSTACHY_GC_STRESS-unset} in 1000) kind=sample ;; unset) kind=suite ;; *) exit 9 ;; esac
mode=$2; shift 2
[ "$LC_ALL" = C.UTF-8 ] && [ $# -gt 0 ] || exit 9
case "$mode" in jit|aot) ;; *) echo "invalid mode: $mode"; exit 9 ;; esac
case "$1" in
  tests/programs/x/example.py|tests/deviations/example.py|tests/errors/x/syntax_example.py) group=$mode-0 ;;
  tests/programs/x/syntax_example.py|tests/errors/x/example.py) group=$mode-1 ;;
  *) exit 9 ;;
esac
echo "suite: $mode $kind"
echo "$mode $kind $*" >> runs.log
checks=0
for file; do
  echo "selected: $file"
  case "$file" in
    tests/programs/x/example.py|tests/deviations/example.py|tests/errors/x/example.py) checks=$((checks + 1)) ;;
    tests/programs/x/syntax_example.py|tests/errors/x/syntax_example.py) checks=$((checks + 2)) ;;
    *) exit 9 ;;
  esac
done
if [ "$VERIFY_MOCK_MODE" = "$kind-$group-failure" ]; then
  echo "$((checks - 1)) passed, 1 failed"
  exit 1
fi
if [ "$VERIFY_MOCK_MODE" = "short-$kind" ]; then
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
        for name in ("PYSTACHY_GC_STRESS", "PYSTACHY_GC_STRESS_PROGRAM", "PYSTACHY_CACHE", "PYSTACHY_JOBS"):
            self.env.pop(name, None)

    def run_group(self, group, mode="pass"):
        for name in ("compiles.log", "runs.log"):
            (self.root / name).unlink(missing_ok=True)
        result = subprocess.run(["sh", "tests/verify.sh", group], cwd=self.root,
                                env={**self.env, "VERIFY_MOCK_MODE": mode},
                                text=True, capture_output=True, timeout=30)
        report = json.loads((self.root / "build/verification.json").read_text())
        logs = {step["name"]: (self.root / step["log"]).read_text() for step in report["steps"]}
        return result, report, logs

    def runs(self):
        """The suite runs, in order: (mode, sample or suite, cases)."""
        path = self.root / "runs.log"
        return [(line.split()[0], line.split()[1], line.split()[2:])
                for line in (path.read_text().splitlines() if path.exists() else [])]

    def compiles(self):
        """The corpus compilations of gc-ir: (command, file, stress)."""
        path = self.root / "compiles.log"
        return [tuple(line.split()) for line in (path.read_text().splitlines() if path.exists() else [])]

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

    def test_each_suite_runs_its_half_once_with_program_stress_and_its_sample_compiler_stressed_first(self):
        observed = {"jit": [], "aot": []}
        for group, mode, half, sample, steps in SUITES:
            with self.subTest(group=group):
                result, report, logs = self.run_group(group)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(report["result"], "pass")
                self.assertEqual([step["name"] for step in report["steps"]], ["bootstrap", *steps])
                step = report["steps"][-1]
                self.assertEqual(step["modes"], [mode])
                self.assertEqual((step["tests_compiler_interval"], step["tests_interval"]), (0, 1))
                self.assertEqual((step["shard_index"], step["shard_count"]), (half, 2))
                self.assertEqual(report["sources"]["mode_checks"], 7)  # (CASES's checks in one mode)
                # the sample first, with the compiler stressed too, then the half's other cases
                self.assertEqual([(m, kind) for m, kind, _ in self.runs()], [(mode, "sample"), (mode, "suite")])
                stressed, rest = self.runs()[0][2], self.runs()[1][2]
                self.assertEqual(stressed, CASES[sample::32])
                self.assertEqual(sorted(stressed + rest), sorted(CASES[half::2]))
                self.assertEqual(rest, [case for case in CASES[half::2] if case not in stressed])
                sample_step = step["stressed_sample"]
                self.assertEqual((sample_step["index"], sample_step["count"]), (sample, 32))
                self.assertEqual((sample_step["tests_compiler_interval"], sample_step["tests_interval"]), (1000, 1))
                self.assertEqual((sample_step["passed"], sample_step["failed"], sample_step["expected"]),
                                 (sum(CHECKS[c] for c in stressed), 0, sum(CHECKS[c] for c in stressed)))
                self.assertEqual((step["passed"], step["failed"], step["expected"]),
                                 (sum(CHECKS[c] for c in rest), 0, sum(CHECKS[c] for c in rest)))
                self.assertLess(logs[group].index(f"suite: {mode} sample"), logs[group].index(f"suite: {mode} suite"))
                self.assertFalse((self.root / "gc-child.pid").exists())
                observed[mode] += stressed + rest
        for mode, cases in observed.items():  # each case once in each mode
            self.assertEqual(sorted(cases), sorted(CASES), mode)

    def test_gc_ir_halves_compile_every_case_once_stressed_as_stage2_does(self):
        compiled = []
        for group, half, cases, checks in (("gc-jit-0", 0, 3, 1), ("gc-jit-1", 1, 2, 1)):
            with self.subTest(group=group):
                result, report, logs = self.run_group(group)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                step = report["steps"][1]
                self.assertEqual(step["name"], f"gc-ir-{half}")
                self.assertEqual((step["ir_cases"], step["ir_identical"], step["runtime_identical"]), (cases, True, True))
                self.assertEqual((step["check_cases"], step["check_differences"]), (checks, 0))
                self.assertEqual((step["compiler_interval"], step["reference"]), (1000, "stage2"))
                self.assertEqual((step["shard_index"], step["shard_count"]), (half, 2))
                self.assertEqual((report["sources"]["corpus_cases"], report["sources"]["syntax_cases"]), (5, 2))
                self.assertIn(f"{cases} programs identical", logs[f"gc-ir-{half}"])
                self.assertIn("1 programs identical", logs[f"gc-ir-{half}"])   # (runtime.py)
                self.assertIn(f"{checks} checks compared, 0 differ", logs[f"gc-ir-{half}"])
                # each case of the half by both compilers (rt for runtime.py), syntax cases checked by both
                calls = self.compiles()
                for case in CASES[half::2]:
                    for stress in ("-", "1000"):
                        self.assertEqual(calls.count(("ir", case, stress)), 1, (case, stress))
                        if "syntax_" in case:
                            self.assertEqual(calls.count(("check", case, stress)), 1, (case, stress))
                self.assertEqual(calls.count(("rt", "runtime.py", "1000")), 1)
                compiled += [case for command, case, stress in calls if command == "ir" and stress == "1000"]
        self.assertEqual(sorted(compiled), sorted(CASES))   # the halves: every case once, stressed

    def test_gc_ir_differences_and_missing_cases_cannot_pass(self):
        # (gc-jit-0's half holds tests/programs/x/example.py, the deviation and the syntax rejection;
        # gc-jit-1's the syntax program and the other rejection)
        for mode, group, field, text in (("gc-ir-differs", "gc-jit-0", "ir_identical", "DIFF tests/programs/x/example.py"),
                                         ("gc-msg-differs", "gc-jit-0", "ir_identical", "DIFF tests/errors/x/syntax_example.py"),
                                         ("gc-status-differs", "gc-jit-0", "ir_identical", "exit status 0 -> 3"),
                                         ("gc-check-differs", "gc-jit-1", "check_differences",
                                          "CHECK DIFF tests/programs/x/syntax_example.py"),
                                         ("gc-rt-differs", "gc-jit-0", "runtime_identical", "DIFF runtime.py"),
                                         ("gc-ir-missing", "gc-jit-1", "ir_identical", "1 programs identical")):
            with self.subTest(mode=mode):
                irsame = self.root / "tools/irsame.sh"
                if mode == "gc-ir-missing":   # irsame drops the half's last case and finds the others identical
                    irsame.rename(self.root / "tools/irsame-real.sh")
                    irsame.write_text('#!/bin/sh\n[ $# -le 3 ] || { n=$#; i=0; for a; do i=$((i + 1)); '
                                      '[ $i = 1 ] && set --; [ $i = $n ] || set -- "$@" "$a"; done; }\n'
                                      'exec sh "$(dirname "$0")/irsame-real.sh" "$@"\n')
                    irsame.chmod(0o755)
                result, report, logs = self.run_group(group, mode)
                if mode == "gc-ir-missing":
                    (self.root / "tools/irsame-real.sh").replace(irsame)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(report["result"], "fail")
                step = report["steps"][1]
                self.assertEqual((step["name"], step["result"]), (f"gc-ir-{group[-1]}", "fail"))
                self.assertEqual(step[field], 1 if field == "check_differences" else False)
                self.assertIn(text, logs[step["name"]])
                if mode == "gc-ir-missing":   # (one of the half's two cases compared, and runtime.py)
                    self.assertEqual((step["ir_cases"], step["runtime_identical"]), (1, True))
                    self.assertEqual(sum(1 for command, _, stress in self.compiles() if command == "ir" and stress == "1000"), 1)
                self.assertEqual(report["steps"][-1]["result"], "pass")   # (the suite still runs)

    def test_local_aliases_run_all_selected_gc_checks(self):
        for group, expected in (("gc-stress", GC_STEPS), ("gc-ir", GC_STEPS[1:3]), ("gc-jit", GC_STEPS[1:5]),
                                ("gc-aot", GC_STEPS[5:])):
            with self.subTest(group=group):
                result, report, logs = self.run_group(group)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(report["result"], "pass")
                self.assertEqual([step["name"] for step in report["steps"]], ["bootstrap", *expected])
                if group == "gc-stress":
                    self.assertIn("gc statistics", logs["gc-self"])
                for suite, mode, _, _, _ in SUITES:
                    if suite not in expected:
                        continue
                    self.assertIn(f"suite: {mode} sample", logs[suite])
                    self.assertIn(f"suite: {mode} suite", logs[suite])
                if "gc-ir-0" in expected:
                    self.assertEqual(sorted(case for command, case, stress in self.compiles()
                                            if command == "ir" and stress == "1000"), sorted(CASES))

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

    def test_failed_and_incomplete_suites_and_samples_cannot_pass(self):
        for group, _, _, _, _ in SUITES:
            name = group.removeprefix("gc-")
            for failure in (f"suite-{name}-failure", f"sample-{name}-failure", "short-suite", "short-sample"):
                with self.subTest(group=group, failure=failure):
                    result, report, _ = self.run_group(group, failure)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(report["result"], "fail")
                    self.assertEqual(report["steps"][-1]["result"], "fail")

    def test_local_alias_reports_failure_and_still_runs_remaining_modes(self):
        for failure in ("failure", "gc-ir-differs", "suite-jit-0-failure", "sample-jit-1-failure",
                        "suite-aot-0-failure", "sample-aot-1-failure"):
            with self.subTest(failure=failure):
                result, report, logs = self.run_group("gc-stress", failure)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(report["result"], "fail")
                self.assertEqual([step["name"] for step in report["steps"]], ["bootstrap", *GC_STEPS])
                for group, mode, _, _, _ in SUITES:
                    self.assertIn(f"suite: {mode} suite", logs[group])

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
