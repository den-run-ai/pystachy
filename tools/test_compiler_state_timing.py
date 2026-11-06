"""Stage timing must leave compiler IR, retry decisions and diagnostics intact."""
import os
import subprocess
import sys
import unittest

from compiler_state_probe import ROOT


PREFIX = "pystachy-timing\t"
PHASES = ("prepare", "discover", "analysis", "optimize", "finalize", "lower")


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
