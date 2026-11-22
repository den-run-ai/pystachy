"""The runtime's inline fast paths keep their libm calls out of line.

AOT inlines the runtime into compiled code, and LLVM takes trunc() for cheap and safe to compute
ahead of a branch, though on x86-64 before SSE4.1 it is a libm call: where pys_cmp_if's whole-part
comparison was inline, LLVM computed its trunc() ahead of the test that skips it for ints within
2**53 (pyperformance's chaos made 12,995 such calls). Set PYSTACHY_TEST_LLVM to a toolchain
directory to build the runtime as the driver does (runtime.c and runtime.py, linked and optimized)
and check that pys_cmp_if, which runtime.py defines, rounds nothing itself.
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LLVM = os.environ.get("PYSTACHY_TEST_LLVM", "")
ROUNDING = {"trunc", "floor", "ceil", "llvm.trunc.f64", "llvm.floor.f64", "llvm.ceil.f64"}


def linked_runtime(llvm):
    """The LLVM IR of the runtime as the driver builds it: runtime.c's and runtime.py's, linked, at -O2."""
    tools = llvm.rstrip("/") + "/"
    with tempfile.TemporaryDirectory(prefix="pystachy-runtime-ir-") as tmp:
        c, py, both, out = (Path(tmp) / n for n in ("runtime-c.ll", "runtime-py.ll", "linked.bc", "runtime.ll"))
        subprocess.run([tools + "clang", "-O2", "-S", "-emit-llvm", "-x", "c", str(ROOT / "runtime.c"),
                        "-o", str(c), "-fexceptions", "-Wno-unused-command-line-argument"], check=True)
        subprocess.run([sys.executable, str(ROOT / "pystachy.py"), "rt", str(ROOT / "runtime.py"), "-o", str(py)], check=True, cwd=ROOT)
        subprocess.run([tools + "llvm-link", str(py), str(c), "-o", str(both)], check=True)
        subprocess.run([tools + "opt", "-O2", "-S", str(both), "-o", str(out)], check=True)
        return out.read_text(encoding="latin-1")


def defined(text, name):
    """The definition of function name in LLVM IR text, or ""."""
    m = re.search(rf"^define [^\n]*@{re.escape(name)}\(.*?^}}$", text, re.M | re.S)
    return m.group(0) if m else ""


def callees(body):
    return set(re.findall(r"call [^@]*@([\w.$]+)\(", body))


@unittest.skipUnless(LLVM, "set PYSTACHY_TEST_LLVM to build the runtime")
class FastPaths(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = linked_runtime(LLVM)

    def test_cmp_if_rounds_out_of_line(self):
        body = defined(self.text, "pys_cmp_if")
        self.assertNotEqual(body, "", "the runtime defines pys_cmp_if")
        self.assertEqual(callees(body) & ROUNDING, set(), "pys_cmp_if's whole-part comparison must stay out of line")


if __name__ == "__main__":
    unittest.main()
