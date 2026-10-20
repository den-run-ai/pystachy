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

ROOT = Path(__file__).resolve().parent.parent
CASES = ["tests/programs/x/example.py", "tests/programs/x/syntax_example.py", "tests/deviations/example.py",
         "tests/errors/x/example.py", "tests/errors/x/syntax_example.py"]
# group, its suite step, the modes it reports, the checks of its shard (tests/verify.sh's checks), and
# how many tests/run.sh runs make them
SHARDS = [("hosted-0", "tests-cpython-0", ["jit", "aot"], 3, 1), ("hosted-1", "tests-cpython-1", ["jit", "aot"], 5, 1),
          ("hosted-2", "tests-cpython-2", ["jit", "aot"], 2, 1),
          ("native-0", "tests-native-0", ["jit", "aot"], 6, 1), ("native-1", "tests-native-1", ["jit", "aot"], 4, 1),
          ("opt-off-0", "tests-opt-off-0", ["jit", "aot"], 6, 1), ("opt-off-1", "tests-opt-off-1", ["jit", "aot"], 4, 1),
          ("python-free-0", "python-free-0", None, 3, 1), ("python-free-1", "python-free-1", None, 5, 1),
          ("python-free-2", "python-free-2", None, 2, 1),
          ("ubsan-0", "ubsan-0", ["aot", "jit"], 4, 2), ("ubsan-1", "ubsan-1", ["aot", "jit"], 8, 2),
          ("ubsan-2", "ubsan-2", ["aot", "jit"], 2, 2)]
# how many shards each suite has: the group kind-I runs shard I
SHARD_COUNTS = {"hosted": 3, "native": 2, "opt-off": 2, "python-free": 3, "ubsan": 3}
# the LLVM tools python-free links into its PATH (doubles: only clang is called)
LLVM_TOOLS = ("clang", "opt", "lli", "llvm-link", "llvm-as")


class ShardVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("tests", "tests/programs", "tests/programs/x", "tests/deviations", "tests/errors",
                     "tests/errors/x", "src", "lib", "ryu", "bin"):
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
from pathlib import Path
import shutil
import sys
args = sys.argv[1:]
if args == ["-"]:
    os.execv(sys.executable, [sys.executable, "-"])
if args == ["--version"]:
    print("mock compiler")
    sys.exit(0)
if args[0] == "-c":  # (the hosted step's py_compile of the compiler's modules)
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
    tests/programs/x/example.py|tests/deviations/example.py) checks=$((checks + m)) ;;
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
        for group, name, modes, count, runs in SHARDS:
            with self.subTest(group=group):
                result, report, logs = self.run_group(group)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(report["result"], "pass")
                self.assertEqual([step["name"] for step in report["steps"]], ["bootstrap", name])
                step = report["steps"][-1]
                self.assertEqual((step["passed"], step["failed"], step["expected"]), (count, 0, count))
                if modes:
                    self.assertEqual(step["modes"], modes)
                index, shards = int(group[-1]), SHARD_COUNTS[group.rsplit("-", 1)[0]]
                self.assertEqual((step["shard_index"], step["shard_count"]), (index, shards))
                self.assertEqual(self.selected(logs[name]), CASES[index::shards] * runs)
                if group.startswith(("ubsan", "python-free")):
                    self.assertTrue(step["ir_identical"])
                if group.startswith("python-free"):
                    self.assertFalse(step["python_on_path"])
                # (opt-off alone runs with the IR passes off)
                self.assertEqual("PYSTACHY_OPT=-all" in logs[name], group.startswith("opt-off"))
                if group.startswith("opt-off"):
                    self.assertEqual(step["PYSTACHY_OPT"], ["-all"])
                self.assertEqual(report["sources"]["suite_checks"], 10)  # (CASES's checks in JIT and AOT)
                observed[group] = CASES[index::shards]
        for kind, shards in SHARD_COUNTS.items():
            parts = [observed[f"{kind}-{index}"] for index in range(shards)]
            self.assertEqual(sum(map(len, parts)), len(set().union(*parts)))  # disjoint
            self.assertCountEqual([case for part in parts for case in part], CASES)

    def test_local_aliases_run_all_their_shards(self):
        for group, prefix, total in (("hosted", "tests-cpython", 10), ("native", "tests-native", 10),
                                     ("opt-off", "tests-opt-off", 10), ("python-free", "python-free", 10),
                                     ("ubsan", "ubsan", 14)):
            steps = [f"{prefix}-{index}" for index in range(SHARD_COUNTS[group])]
            with self.subTest(group=group):
                result, report, _ = self.run_group(group)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual([step["name"] for step in report["steps"]], ["bootstrap", *steps])
                self.assertEqual(sum(step["expected"] for step in report["steps"][1:]), total)

    def test_failed_and_incomplete_shards_cannot_pass(self):
        for group, _, _, _, _ in SHARDS:
            for failure in ("suite-failure", "short-suite"):
                with self.subTest(group=group, failure=failure):
                    result, report, _ = self.run_group(group, failure)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(report["result"], "fail")
                    self.assertEqual(report["steps"][-1]["result"], "fail")

    def test_ubsan_shards_need_an_instrumented_runtime(self):
        for group in ("ubsan-0", "ubsan-1", "ubsan-2"):
            with self.subTest(group=group):
                result, report, logs = self.run_group(group, "plain-runtime")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(report["steps"][-1]["result"], "fail")
                self.assertNotIn("selected: ", logs[group])  # (no suite runs on an uninstrumented runtime)


if __name__ == "__main__":
    unittest.main()
