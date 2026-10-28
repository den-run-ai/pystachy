"""The contracts group's steps run side by side in tests/verify.sh's lanes (deterministic doubles):
every step is reported once, in the plan's order, with its fields; the lanes of each phase really
overlap, and compile-limits runs beside the SIGINT lane only; the steps that take SIGINT run in the
shell's own lane, where SIGINT is not ignored; a failed step, or a lane that ends before its steps
report, fails the group instead of shortening its report."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
# in each phase, each lane's first step waits for the others' (a barrier): run one after another,
# they would time out
BARRIERS = [["compilelimits", "ffi"], ["re_probe", "unicode_audit", "rtcheck", "jitprobe"]]
# what may run while compile-limits does: the shell's lane beside it
BESIDE_LIMITS = {"compilelimits", "ffi", "selectprobe", "boxprobe"}
SUMMARY = {
    "check_ir": "the IR check and llvm-as accept the IR of 5 programs",
    "check_runtime": "12 RUNTIME entries, 3 exception classes: ok",
    "rtcheck": "100 cases, 0 failed",
    "re_fuzz": "2 upstream cases and 10 patterns (8 valid): 30 cases, 0 failed",
    "dynany_fuzz": "3 programs, 540 cases, 90 parity cases (JIT, AOT, JIT-GC, AOT-GC): 0 mismatches",
    "re_probe": "7 operations, 0 failed",
    "rtabi": "5 functions of runtime.py, 6 uses in runtime.c and 7 programs, 0 mismatches",
    "ffi": "3 passed, 0 failed",
}
TOOL = '''import os
from pathlib import Path
import signal
import sys
import time
name = Path(sys.argv[0] if sys.argv[0].endswith((".py", ".sh")) else sys.argv[0]).stem
mode = Path("mock-mode").read_text()
summary = json.loads(os.environ["MOCK_SUMMARY"]).get(name, "")
log = Path("mock-log")
with log.open("a") as f:
    f.write(f"{name} {'ignored' if signal.getsignal(signal.SIGINT) == signal.SIG_IGN else 'default'}\\n")
if name not in BESIDE_LIMITS and Path("started-compilelimits").exists() and not Path("ended-compilelimits").exists():
    with Path("beside-limits").open("a") as f:
        f.write(name + "\\n")
for barrier in BARRIERS:
    if name in barrier:
        Path(f"started-{name}").write_text("")
        deadline = time.monotonic() + 20
        while not all(Path(f"started-{n}").exists() for n in barrier):
            if time.monotonic() > deadline:
                print("the lanes did not overlap")
                sys.exit(1)
            time.sleep(0.02)
if name == "compilelimits":
    Path("ended-compilelimits").write_text("")
if mode == f"fail:{name}":
    print(summary.replace(", 0 failed", ", 1 failed"))
    sys.exit(1)
if mode == f"end-lane:{name}":
    os.kill(os.getppid(), signal.SIGKILL)
print(summary)
'''


class ContractLaneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("tests", "tests/programs", "tests/programs/x", "tests/errors", "tests/errors/x",
                     "tests/ffi", "tools", "src", "lib", "ryu", "mpz", "bin"):
            (self.root / name).mkdir()
        for name in ("tests/verify.sh", "tests/corpus.sh"):
            shutil.copy(ROOT / name, self.root / name)
        for name in ("pystachy.py", "runtime.py", "runtime.c", "tests/programs/x/example.py"):
            (self.root / name).write_text("# fixture\n")
        (self.root / "tests/errors/x/example.py").write_text("# error: mock rejection\n")
        header = f"import json\nBARRIERS = {BARRIERS!r}\nBESIDE_LIMITS = {BESIDE_LIMITS!r}\n"
        tool = header + TOOL
        compiler = self.root / "bin/compiler"
        compiler.write_text(f"#!{sys.executable}\n" + '''import os
from pathlib import Path
import shutil
import sys
args = sys.argv[1:]
if args in (["-"], ["--version"]):
    os.execv(sys.executable, [sys.executable] + args)
if args[0].startswith("tools/"):  # (a tool of a step: its double)
    sys.argv = args
    exec(compile(Path(os.environ["MOCK_TOOL"]).read_text(), "tool.py", "exec"), {"__name__": "__main__"})
    sys.exit(0)
if args[:2] == ["-m", "pystachy"]:
    args = args[2:]
if args[0] == "pystachy.py":
    args = args[1:]
if args[0] == "run":
    sys.exit(0)
output = Path(args[args.index("-o") + 1])
if args[0] == "build":
    shutil.copy(__file__, output)
    output.chmod(0o755)
else:
    output.write_text("fixed point\\n")
''')
        (self.root / "bin/tool.py").write_text(tool)
        for script, name in (("tools/check_ir.sh", "check_ir"), ("tests/ffi/run.sh", "ffi")):
            (self.root / script).write_text(f'#!/bin/sh\nexec "{sys.executable}" "$MOCK_TOOL_SH" {name}\n')
        (self.root / "bin/tool_sh.py").write_text(header + "import sys\nsys.argv[0] = sys.argv[1] + '.sh'\n" + TOOL)
        # a C probe's double: named by its executable, it prints dict-probes' summary
        (self.root / "bin/probe.py").write_text(
            header + "import os\nimport sys\nsys.argv[0] = os.path.basename(sys.argv[0]) + '.sh'\n" +
            TOOL.replace('summary = json.loads(os.environ["MOCK_SUMMARY"]).get(name, "")',
                         'summary = "worst average: 1.5 slots per lookup (limit 4.0)"'))
        for tool_name in ("clang", "llvm-link", "opt"):
            double = self.root / "bin" / tool_name
            # an executable output is a probe, whose double records how it takes SIGINT
            double.write_text(f"#!{sys.executable}\n" + '''from pathlib import Path
import os
import sys
args = sys.argv[1:]
if "-o" in args:
    out = Path(args[args.index("-o") + 1])
    if out.suffix:
        out.write_text("probe")
    else:
        out.write_text("#!" + sys.executable + "\\n" + Path(os.environ["MOCK_PROBE"]).read_text())
        out.chmod(0o755)
else:
    print("mock LLVM 18")
''')
            double.chmod(0o755)
        compiler.chmod(0o755)
        for script in ("tools/check_ir.sh", "tests/ffi/run.sh"):
            (self.root / script).chmod(0o755)
        self.env = {**os.environ, "PY": str(compiler), "LC_ALL": "C.UTF-8", "PYSTACHY_LLVM": str(self.root / "bin"),
                    "MOCK_TOOL": str(self.root / "bin/tool.py"), "MOCK_TOOL_SH": str(self.root / "bin/tool_sh.py"),
                    "MOCK_PROBE": str(self.root / "bin/probe.py"),
                    "MOCK_SUMMARY": json.dumps(SUMMARY), "PATH": str(self.root / "bin") + os.pathsep + os.environ["PATH"]}
        self.plan = subprocess.run(["sh", "tests/verify.sh", "--list"], cwd=self.root, env=self.env, text=True,
                                   capture_output=True, check=True, timeout=30).stdout
        self.steps = next(line.split()[1:] for line in self.plan.splitlines() if line.split()[0] == "contracts")

    def run_contracts(self, mode="pass"):
        (self.root / "mock-mode").write_text(mode)
        # (SIGINT as a terminal's shell leaves it, whatever runs this test)
        result = subprocess.run(["sh", "tests/verify.sh", "contracts"], cwd=self.root, env=self.env,
                                text=True, capture_output=True, timeout=120,
                                preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_DFL))
        report = json.loads((self.root / "build/verification.json").read_text())
        return result, report

    def disposition(self):
        out = {}
        for line in (self.root / "mock-log").read_text().splitlines():
            name, how = line.split()
            out.setdefault(name, set()).add(how)
        return out

    def test_every_step_once_in_plan_order_side_by_side(self):
        result, report = self.run_contracts()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(report["result"], "pass")
        self.assertEqual([step["name"] for step in report["steps"]], self.steps)
        self.assertEqual(report["summary"]["steps"], len(self.steps))
        steps = {step["name"]: step for step in report["steps"]}
        self.assertTrue(all(step["result"] == "pass" for step in report["steps"]))
        self.assertEqual(steps["check-ir"]["programs"], 5)
        self.assertEqual(steps["rt-abi"]["mismatches"], 0)
        self.assertEqual((steps["dynany-fuzz"]["cases"], steps["dynany-fuzz"]["parity_cases"]), (540, 90))
        self.assertEqual(steps["dict-probes"]["worst_average_slots"], 1.5)
        self.assertEqual(steps["ffi"]["passed"], 3)
        for name in sum(BARRIERS, []):  # (each met the others of its phase: the lanes overlapped)
            self.assertTrue((self.root / f"started-{name}").exists(), name)
        self.assertFalse((self.root / "beside-limits").exists())  # (only the shell's lane beside it)
        # the steps that take SIGINT run where it is not ignored
        how = self.disposition()
        for name in ("ffi", "selectprobe"):
            self.assertEqual(how[name], {"default"}, name)

    def test_a_failed_step_fails_the_group_and_the_others_still_report(self):
        for failing, step in (("rtcheck", "rtcheck"), ("re_probe", "re-probe"), ("ffi", "ffi"), ("check_ir", "check-ir"),
                              ("compilelimits", "compile-limits")):
            with self.subTest(step=step):
                for name in sum(BARRIERS, []):
                    (self.root / f"started-{name}").unlink(missing_ok=True)
                (self.root / "ended-compilelimits").unlink(missing_ok=True)
                result, report = self.run_contracts(f"fail:{failing}")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(report["result"], "fail")
                self.assertEqual([s["name"] for s in report["steps"]], self.steps)
                self.assertEqual([s["name"] for s in report["steps"] if s["result"] == "fail"], [step])

    def test_a_lane_that_ends_early_fails_its_unreported_steps(self):
        result, report = self.run_contracts("end-lane:rtcheck")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(report["result"], "fail")
        self.assertEqual([s["name"] for s in report["steps"]], self.steps)
        ended = [s["name"] for s in report["steps"] if s.get("lane_ended")]
        # (rtcheck's lane, contracts_c: every step of it)
        self.assertEqual(sorted(ended), sorted(["rtcheck", "dynany-fuzz", "streaming"]))
        self.assertTrue(all(s["result"] == "fail" for s in report["steps"] if s.get("lane_ended")))
        self.assertTrue(all(s["result"] == "pass" for s in report["steps"] if not s.get("lane_ended")))


if __name__ == "__main__":
    unittest.main()
