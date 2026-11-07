"""Stage timing must leave compiler IR, retry decisions and diagnostics intact."""
import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from compiler_state_probe import ROOT
from src.pystachy_compiler import driver, utils


PREFIX = "pystachy-timing\t"
PHASES = ("prepare", "discover", "analysis", "optimize", "finalize", "lower")


class TimingHelpers(unittest.TestCase):
    def test_disabled_timing_never_reads_clock_or_prints(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(utils.time, "perf_counter") as clock:
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                utils.timing_end("probe", utils.timing_start())
        clock.assert_not_called()
        self.assertEqual(stderr.getvalue(), "")

    def test_zero_clock_start_is_reported(self):
        with patch.dict(os.environ, {"PYSTACHY_TIMING": "1"}, clear=True):
            with patch.object(utils.time, "perf_counter", side_effect=[0.0, 0.25]):
                with contextlib.redirect_stderr(io.StringIO()) as stderr:
                    utils.timing_end("probe", utils.timing_start())
        self.assertEqual(stderr.getvalue(), "pystachy-timing\tprobe\t0.250000000\n")

    def test_failed_command_preserves_status_and_reports(self):
        with patch.dict(os.environ, {"PYSTACHY_TIMING": "1"}, clear=True):
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(driver.timed_sh("probe", "exit 23"), 23)
        self.assertRegex(stderr.getvalue(), r"^pystachy-timing\tprobe\t[0-9]+\.[0-9]{9}\n$")


class BackendFailures(unittest.TestCase):
    def test_aot_stops_at_each_failed_stage_and_preserves_retained_ir(self):
        # Stub only native work; exercise the actual driver order, error handling
        # and retained-IR publication with both allocator and plain IR paths.
        script = """import sys
from src.pystachy_compiler import driver
failed = sys.argv.pop()
def command(name, text):
    print("stage " + name, file=sys.stderr)
    return 23 if name == failed else 0
driver.timed_sh = command
driver.runtime_ir = lambda *args: "; runtime\\n"
driver.main()
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "probe.py"
            output = root / "program"
            witness = root / "witness.ll"
            environment = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
            environment.update(PYSTACHY_HOME=str(ROOT), PYSTACHY_CACHE=str(root / "cache"),
                               PYSTACHY_LLVM=str(root / "missing-tools"))
            for program, middle in [("print(42)\n", ["program.optimize_codegen"]),
                                    ("class Cell:\n    def __init__(self, n: int):\n        self.n = n\nprint(Cell(42).n)\n",
                                     ["program.llvm_optimize", "program.late_inline", "program.codegen"])]:
                source.write_text(program)
                stages = ["program.llvm_link", *middle, "program.link"]
                for index, failed in enumerate(stages):
                    with self.subTest(program=program, stage=failed):
                        output.write_text("old executable")
                        witness.write_text("old IR")
                        result = subprocess.run([sys.executable, "-c", script, "build", str(source),
                                                 "-o", str(output), "--emit-ir", str(witness), failed],
                                                cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
                        self.assertEqual(result.returncode, 23, result.stderr)
                        observed = [line[6:] for line in result.stderr.splitlines() if line.startswith("stage program.")]
                        self.assertEqual(observed, stages[:index + 1])
                        self.assertEqual(output.read_text(), "old executable")
                        self.assertEqual(witness.read_text(), "old IR")


class TimingTests(unittest.TestCase):
    def compile_pair(self, source, runtime=False):
        expression = ('runtime_ir("timing-runtime.py", sys.stdin.read(), False)' if runtime else
                      'compile_program("timing-probe.py", sys.stdin.read(), [], "")')
        script = ("import sys\nfrom src.pystachy_compiler.driver import compile_program, runtime_ir\n"
                  f"print({expression}, end='')\n")
        env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
        env["PYSTACHY_IRCHECK"] = "1"
        # Separate processes give both runs the same initial semantic registries.
        off = subprocess.run([sys.executable, "-c", script], input=source, cwd=ROOT, env=env,
                             capture_output=True, text=True, timeout=45)
        on = subprocess.run([sys.executable, "-c", script], input=source, cwd=ROOT,
                            env=dict(env, PYSTACHY_TIMING="1"),
                            capture_output=True, text=True, timeout=45)
        self.assertEqual(on.returncode, off.returncode, on.stderr)
        self.assertEqual(on.stdout, off.stdout)
        diagnostics = "".join(line for line in on.stderr.splitlines(keepends=True)
                              if not line.startswith(PREFIX))
        self.assertEqual(diagnostics, off.stderr)
        self.assertNotIn(PREFIX, off.stderr)
        phases = []
        for line in on.stderr.splitlines():
            if line.startswith(PREFIX):
                _, name, elapsed = line.split("\t")
                self.assertRegex(elapsed, r"^\d+\.\d{9}$")
                self.assertGreaterEqual(float(elapsed), 0.0)
                phases.append(name)
        return on, phases

    def test_optimized_ir_is_unchanged(self):
        result, phases = self.compile_pair('''
def count(text: str, values: dict[str, int]) -> int:
    total = 0
    for ch in text:
        total += ord(ch)
    if "answer" in values:
        total += values["answer"]
    return total
print(count("abc", {"answer": 42}))
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = ["program." + phase for phase in PHASES]
        self.assertEqual([phase for phase in phases if phase in expected], expected)

    def test_global_join_keeps_retry_and_ir(self):
        result, phases = self.compile_pair('''
total = 0
def add(value: float) -> None:
    global total
    total += value
add(1.5)
print(total)
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(phases.count("program.prepare"), 2)
        self.assertEqual(phases.count("program.discover"), 2)
        self.assertEqual(phases.count("program.lower"), 1)

    def test_runtime_has_separate_scope(self):
        result, phases = self.compile_pair("def pys_probe(x: int) -> int:\n    return x + 1\n", runtime=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = ["runtime." + phase for phase in PHASES]
        self.assertEqual([phase for phase in phases if phase in expected], expected)

    def test_rejection_keeps_diagnostic_and_status(self):
        result, phases = self.compile_pair("print(unknown)\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("name 'unknown' is not defined", result.stderr)
        self.assertNotIn("program.lower", phases)


if __name__ == "__main__":
    unittest.main()
