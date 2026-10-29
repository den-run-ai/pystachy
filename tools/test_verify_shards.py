"""Exercise the real verification shell's suite shards with deterministic compiler/test doubles:
CPython-hosted, native, opt-off, python-free and UBSan (the GC shards have tools/test_verify_gc.py)."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import merge_verification
from test_verify_case_weights import reference_shards

ROOT = Path(__file__).resolve().parent.parent
CASES = ["tests/programs/x/example.py", "tests/programs/x/syntax_example.py", "tests/deviations/example.py",
         "tests/errors/x/example.py", "tests/errors/x/syntax_example.py"]
# the fixture's tests/case_weights.txt (tests/errors/x/syntax_example.py takes the rejections' default),
# by which tests/corpus.sh's corpus_shard balances the shards
WEIGHTS = {"tests/programs/x/example.py": 5000, "tests/programs/x/syntax_example.py": 3000,
           "tests/deviations/example.py": 2000, "tests/errors/x/example.py": 10}
DEFAULTS = {"program": 1000, "rejection": 10}
# group, its suite step, the modes it reports, and the modes of each tests/run.sh run that makes its checks
SHARDS = [("native-0", "tests-native-0", ["jit", "aot"], ["jit aot"]),
          ("native-1", "tests-native-1", ["jit", "aot"], ["jit aot"]),
          ("native-2", "tests-native-2", ["jit", "aot"], ["jit aot"]),
          ("opt-off-0", "tests-opt-off-0", ["jit", "aot"], ["jit aot"]),
          ("opt-off-1", "tests-opt-off-1", ["jit", "aot"], ["jit aot"]),
          ("opt-off-2", "tests-opt-off-2", ["jit", "aot"], ["jit aot"]),
          ("python-free-0", "python-free-0", None, ["jit aot"]), ("python-free-1", "python-free-1", None, ["jit aot"]),
          ("python-free-2", "python-free-2", None, ["jit aot"]),
          ("ubsan-0", "ubsan-0", ["aot", "jit"], ["aot", "jit"]), ("ubsan-1", "ubsan-1", ["aot", "jit"], ["aot", "jit"]),
          ("ubsan-2", "ubsan-2", ["aot", "jit"], ["aot", "jit"]),
          ("ubsan-3", "ubsan-3", ["aot", "jit"], ["aot", "jit"])]
# how many shards each suite has: the group kind-I runs shard I
SHARD_COUNTS = {"native": 3, "opt-off": 3, "python-free": 3, "ubsan": 4}
# the kinds of program the hosted sample holds the first of (tests/verify.sh's hosted_strata): a source
# and the sidecar that make one
STRATA = [("ffi", "import ffi\n", None), ("full", "# fixture\n", ".full"), ("in", "# fixture\n", ".in"),
          ("path", "# fixture\n", ".path"), ("sigint", "import os\nos.system('kill -INT $PPID')\n", None)]


def checks(cases, modes):
    """tests/verify.sh's checks of these fixture cases in a tests/run.sh run of these modes."""
    total = 0
    for case in cases:
        total += 1 if "/errors/" in case else len(modes.split())
        total += case.endswith("syntax_example.py")   # (both syntax cases have a check of their own)
    return total


def shard(kind, index):
    """The fixture cases of shard INDEX of KIND's suite, heaviest first."""
    return reference_shards(CASES, WEIGHTS, DEFAULTS, SHARD_COUNTS[kind])[0][index]
# the LLVM tools python-free links into its PATH (doubles: only clang is called)
LLVM_TOOLS = ("clang", "opt", "lli", "llvm-link", "llvm-as")


class ShardVerificationTests(unittest.TestCase):
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
        (self.root / "tests/case_weights.txt").write_text(
            "".join(f"{weight} {case}\n" for case, weight in WEIGHTS.items()) + "default rejection 10\n")
        (self.root / "tests/errors/x/syntax_example.py").write_text("# error: syntax_example.py: mock syntax\n")
        compiler = self.root / "bin/compiler"
        compiler.write_text(f"#!{sys.executable}\n" + '''import os
from pathlib import Path
import shutil
import sys
args = sys.argv[1:]
if args == ["-"]:
    os.execv(sys.executable, [sys.executable, "-"])
if args == ["--version"]:
    print("mock compiler")
    sys.exit(0)
if args and args[0] == "-c":  # (the hosted step's py_compile of the compiler's modules)
    sys.exit(0)
hosted = args[:2] == ["-m", "pystachy"]  # (tests-cpython's: $PY -m pystachy)
if hosted:
    args = args[2:]
if not args:  # (tools/irsame.sh asks the usage whether rt exists)
    print("usage: pystachy run FILE.py\\n       pystachy rt runtime.py [-o OUT.ll]", file=sys.stderr)
    sys.exit(2)
if args[0] in ("ir", "rt", "check") and args[1].startswith("tests/"):  # (a case of the corpus)
    case = args[1]
    mode = Path("mock-mode").read_text() if Path("mock-mode").exists() else ""
    target = {"ir": "tests/programs/x/example.py", "check": "tests/programs/x/syntax_example.py"}.get(args[0])
    differs = " (hosted)" if hosted and case == target and mode == f"hosted-{args[0]}-differs" else ""
    if "/errors/" in case:
        print(f"{case}:1: error: mock rejection", file=sys.stderr)
        sys.exit(1)
    if args[0] == "check":
        print(differs, end="")
    else:
        Path(args[args.index("-o") + 1]).write_text(f"IR of {case}{differs}\\n")
    sys.exit(0)
if args[0] == "pystachy.py":
    args = args[1:]
output = Path(args[args.index("-o") + 1])
if args[0] == "build":
    shutil.copy(__file__, output)
    output.chmod(0o755)
    if os.environ.get("PYSTACHY_HOME"):  # (a rebuild writes the runtime to its home's cache)
        cache = Path(os.environ["PYSTACHY_HOME"]) / "build"
        cache.mkdir(exist_ok=True)
        sanitized = "-fsanitize=undefined" in os.environ.get("PYSTACHY_CFLAGS", "")
        mark = "__ubsan_handle" if sanitized and os.environ.get("VERIFY_MOCK_MODE") != "plain-runtime" else ""
        (cache / "runtime-mock.bc").write_text(f"bitcode {mark}\\n")
else:
    output.write_text("fixed point\\n")
''')
        compiler.chmod(0o755)
        for tool in LLVM_TOOLS:
            double = self.root / "bin" / tool
            double.write_text(f"#!{sys.executable}\n" + '''from pathlib import Path
import sys
args = sys.argv[1:]
if args and args[0].startswith("-print-file-name="):
    print()  # (no UBSan runtime to preload in the doubles)
elif "-o" in args:
    sys.stdin.read()
    Path(args[args.index("-o") + 1]).write_text("probe")
else:
    print("mock LLVM 18")
''')
            double.chmod(0o755)
        suite = self.root / "tests/run.sh"
        suite.write_text('''#!/bin/sh
compiler=$1; mode=$2; shift 2
echo "suite: $compiler $mode${PYSTACHY_OPT:+ PYSTACHY_OPT=$PYSTACHY_OPT}"
case "$compiler $mode" in
  *" -m pystachy jit aot") m=2 ;;
  */pystachy2" jit aot") [ -z "$PYSTACHY_CFLAGS" ] || exit 9; m=2 ;;
  */pystachy-nopy" jit aot") [ -z "$PYSTACHY_CFLAGS" ] && [ -z "$PY" ] || exit 9; m=2 ;;
  */pystachy-ubsan" aot") case $PYSTACHY_CFLAGS in *-fsanitize=undefined*) ;; *) exit 9 ;; esac; m=1 ;;
  */pystachy2" jit") case $UBSAN_OPTIONS in *handle_segv=0*) ;; *) exit 9 ;; esac; m=1 ;;
  *) echo "unexpected suite: $compiler $mode"; exit 9 ;;
esac
[ $# -gt 0 ] || exit 9
checks=0
for file; do
  echo "selected: $file"
  case "$file" in
    tests/programs/x/example.py|tests/deviations/example.py|tests/programs/[as]/*.py) checks=$((checks + m)) ;;
    tests/programs/x/syntax_example.py) checks=$((checks + m + 1)) ;;
    tests/errors/x/example.py) checks=$((checks + 1)) ;;
    tests/errors/x/syntax_example.py) checks=$((checks + 2)) ;;
    *) exit 9 ;;
  esac
done
# (from a file: python-free runs the suite in an empty environment)
case $(cat mock-mode) in
  suite-failure) echo "$((checks - 1)) passed, 1 failed"; exit 1 ;;
  short-suite) echo "$((checks - 1)) passed, 0 failed" ;;
  *) echo "$checks passed, 0 failed" ;;
esac
''')
        suite.chmod(0o755)
        self.env = {**os.environ, "PY": str(compiler), "LC_ALL": "C.UTF-8", "PYSTACHY_LLVM": str(self.root / "bin"),
                    "PATH": str(self.root / "bin") + os.pathsep + os.environ["PATH"]}

    def run_group(self, group, mode="pass"):
        (self.root / "mock-mode").write_text(mode)
        result = subprocess.run(["sh", "tests/verify.sh", group], cwd=self.root,
                                env={**self.env, "VERIFY_MOCK_MODE": mode},
                                text=True, capture_output=True, timeout=60)
        report = json.loads((self.root / "build/verification.json").read_text())
        logs = {step["name"]: (self.root / step["log"]).read_text() for step in report["steps"]}
        return result, report, logs

    def selected(self, log):
        return [line.removeprefix("selected: ") for line in log.splitlines() if line.startswith("selected: ")]

    def test_each_shard_runs_its_share_of_the_corpus(self):
        observed = {}
        for group, name, modes, runs in SHARDS:
            with self.subTest(group=group):
                result, report, logs = self.run_group(group)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(report["result"], "pass")
                self.assertEqual([step["name"] for step in report["steps"]], ["bootstrap", name])
                step = report["steps"][-1]
                kind, index = group.rsplit("-", 1)[0], int(group[-1])
                cases = shard(kind, index)
                count = sum(checks(cases, run) for run in runs)
                self.assertEqual((step["passed"], step["failed"], step["expected"]), (count, 0, count))
                if modes:
                    self.assertEqual(step["modes"], modes)
                shards = SHARD_COUNTS[kind]
                self.assertEqual((step["shard_index"], step["shard_count"]), (index, shards))
                # (heaviest first: the order tests/run.sh's workers take them in)
                self.assertEqual(self.selected(logs[name]), cases * len(runs))
                if group.startswith(("ubsan", "python-free")):
                    self.assertTrue(step["ir_identical"])
                if group.startswith("python-free"):
                    self.assertFalse(step["python_on_path"])
                # (opt-off alone runs with the IR passes off)
                self.assertEqual("PYSTACHY_OPT=-all" in logs[name], group.startswith("opt-off"))
                if group.startswith("opt-off"):
                    self.assertEqual(step["PYSTACHY_OPT"], ["-all"])
                self.assertEqual(report["sources"]["suite_checks"], 10)  # (CASES's checks in JIT and AOT)
                observed[group] = cases
        for kind, shards in SHARD_COUNTS.items():
            parts = [observed[f"{kind}-{index}"] for index in range(shards)]
            self.assertEqual(sum(map(len, parts)), len(set().union(*parts)))  # disjoint
            self.assertCountEqual([case for part in parts for case in part], CASES)

    def test_local_aliases_run_all_their_shards(self):
        for group, prefix, total in (("native", "tests-native", 10),
                                     ("opt-off", "tests-opt-off", 10), ("python-free", "python-free", 10),
                                     ("ubsan", "ubsan", 14)):
            steps = [f"{prefix}-{index}" for index in range(SHARD_COUNTS[group])]
            with self.subTest(group=group):
                result, report, _ = self.run_group(group)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual([step["name"] for step in report["steps"]], ["bootstrap", *steps])
                self.assertEqual(sum(step["expected"] for step in report["steps"][1:]), total)

    def test_failed_and_incomplete_shards_cannot_pass(self):
        for group, _, _, _ in SHARDS:
            for failure in ("suite-failure", "short-suite"):
                with self.subTest(group=group, failure=failure):
                    result, report, _ = self.run_group(group, failure)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(report["result"], "fail")
                    self.assertEqual(report["steps"][-1]["result"], "fail")

    def add_strata(self, *omit):
        """Programs of each kind the hosted sample holds one of (tests/verify.sh's hosted_strata), but
        those of the kinds OMIT, and one more of each, later in C order; a plain program first."""
        shutil.copy(ROOT / "tests/prepare_path.sh", self.root / "tests/prepare_path.sh")
        (self.root / "tests/programs/a").mkdir(exist_ok=True)
        (self.root / "tests/programs/s").mkdir(exist_ok=True)
        (self.root / "tests/programs/a/plain.py").write_text("# fixture\n")
        for prefix in ("", "z"):
            for kind, source, sidecar in STRATA:
                if kind not in omit:
                    case = self.root / "tests/programs/s" / f"{prefix}{kind}.py"
                    case.write_text(source)
                    if sidecar:
                        case.with_suffix(sidecar).write_text("tests\n")
        # (a rejection of every kind is none's program: it never runs)
        decoy = self.root / "tests/errors/x/decoy.py"
        decoy.write_text("# error: mock rejection\nimport ffi  # kill -INT\n")
        for sidecar in (".full", ".in", ".path"):
            decoy.with_suffix(sidecar).write_text("tests\n")

    def test_hosted_compares_every_case_with_stage2_and_runs_its_sample(self):
        self.add_strata()
        result, report, logs = self.run_group("hosted")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual([step["name"] for step in report["steps"]], ["bootstrap", "tests-cpython"])
        step = report["steps"][-1]
        # every case's IR, messages and status (tools/irsame.sh), both syntax cases' check (tools/irsame.sh
        # --check), and end to end, JIT and AOT, shard 0 of 64 (the plain program alone here) and the
        # first program of each kind
        cases = 5 + 1 + 2 * len(STRATA) + 1
        self.assertEqual((step["ir_cases"], step["ir_identical"], step["check_cases"], step["check_identical"]),
                         (cases, True, 2, True))
        self.assertEqual((report["sources"]["corpus_cases"], report["sources"]["syntax_cases"]), (cases, 2))
        self.assertEqual((report["sources"]["test_programs"], report["sources"]["rejection_tests"]), (cases - 4, 3))
        self.assertEqual((step["reference"], step["modes"], step["sample_index"], step["sample_count"]),
                         ("stage2", ["jit", "aot"], 0, 64))
        strata = {kind: f"tests/programs/s/{kind}.py" for kind, _, _ in STRATA}
        sample = ["tests/programs/a/plain.py", *sorted(strata.values())]
        self.assertEqual(step["sample_strata"], strata)
        self.assertEqual((step["sample"], step["sample_cases"]), (sample, len(sample)))
        # (the final gate draws the same sample from the checkout)
        self.assertEqual(merge_verification.hosted_sample(step["sample_strata"], self.root), sample)
        self.assertEqual((step["passed"], step["failed"], step["expected"]), (2 * len(sample), 0, 2 * len(sample)))
        self.assertIn(f"{cases} programs identical", logs["tests-cpython"])
        self.assertIn("== check of the 2 syntax_*.py cases: stage 2, then CPython-hosted (tools/irsame.sh --check)\n"
                      "2 programs identical", logs["tests-cpython"])
        for kind, case in strata.items():
            self.assertIn(f"  {kind} {case}\n", logs["tests-cpython"])
        self.assertEqual(self.selected(logs["tests-cpython"]), sample)
        for failure in ("hosted-ir-differs", "hosted-check-differs", "suite-failure", "short-suite"):
            with self.subTest(failure=failure):
                result, report, logs = self.run_group("hosted", failure)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(report["steps"][-1]["result"], "fail")
                if failure == "hosted-ir-differs":
                    self.assertFalse(report["steps"][-1]["ir_identical"])
                    self.assertIn("DIFF tests/programs/x/example.py", logs["tests-cpython"])
                if failure == "hosted-check-differs":
                    self.assertFalse(report["steps"][-1]["check_identical"])
                    check = logs["tests-cpython"].split("(tools/irsame.sh --check)\n", 1)[1]
                    self.assertTrue(check.startswith("DIFF tests/programs/x/syntax_example.py\n"), check)

    def test_hosted_fails_without_a_program_of_each_kind(self):
        for kind, _, _ in STRATA:
            with self.subTest(kind=kind):
                shutil.rmtree(self.root / "tests/programs/s", ignore_errors=True)
                self.add_strata(kind)
                result, report, logs = self.run_group("hosted")
                self.assertNotEqual(result.returncode, 0)
                step = report["steps"][-1]
                self.assertEqual(step["result"], "fail")
                self.assertIsNone(step["sample_strata"][kind])
                self.assertIn(f"  {kind} none\n", logs["tests-cpython"])
                # (the other kinds still run, and pass: only the missing kind fails the step)
                self.assertEqual((step["passed"], step["failed"]), (step["expected"], 0))

    def test_ubsan_shards_need_an_instrumented_runtime(self):
        for group in ("ubsan-0", "ubsan-1", "ubsan-2", "ubsan-3"):
            with self.subTest(group=group):
                result, report, logs = self.run_group(group, "plain-runtime")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(report["steps"][-1]["result"], "fail")
                self.assertNotIn("selected: ", logs[group])  # (no suite runs on an uninstrumented runtime)


if __name__ == "__main__":
    unittest.main()
