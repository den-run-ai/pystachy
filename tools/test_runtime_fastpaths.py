"""runtime.c's inline fast paths keep their libm calls out of line.

AOT inlines runtime.c into compiled code, and LLVM takes trunc() for cheap and safe to compute
ahead of a branch, though on x86-64 before SSE4.1 it is a libm call: where pys_cmp_if's whole-part
comparison was inline, LLVM computed its trunc() ahead of the test that skips it for ints within
2**53 (pyperformance's chaos made 12,995 such calls). Set PYSTACHY_TEST_LLVM to a toolchain
directory to compile runtime.c as the driver does and check that pys_cmp_if rounds nothing itself.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LLVM = os.environ.get("PYSTACHY_TEST_LLVM", "")
ROUNDING = {"trunc", "floor", "ceil", "llvm.trunc.f64", "llvm.floor.f64", "llvm.ceil.f64"}


def defined(text, name):
    """The definition of function name in LLVM IR text, or ""."""
    m = re.search(rf"^define [^\n]*@{re.escape(name)}\(.*?^}}$", text, re.M | re.S)
    return m.group(0) if m else ""


def callees(body):
    return set(re.findall(r"call [^@]*@([\w.$]+)\(", body))


@unittest.skipUnless(LLVM, "set PYSTACHY_TEST_LLVM to compile runtime.c")
class FastPaths(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tools = LLVM.rstrip("/") + "/"
        with tempfile.TemporaryDirectory(prefix="pystachy-fastpaths-") as tmp:
            ll = Path(tmp) / "runtime.ll"
            subprocess.run([tools + "clang", "-O2", "-S", "-emit-llvm", "-x", "c", str(ROOT / "runtime.c"),
                            "-o", str(ll), "-fexceptions", "-Wno-unused-command-line-argument"], check=True)
            cls.text = ll.read_text(encoding="latin-1")

    def test_cmp_if_rounds_out_of_line(self):
        body = defined(self.text, "pys_cmp_if")
        self.assertNotEqual(body, "", "runtime.c defines pys_cmp_if")
        self.assertEqual(callees(body) & ROUNDING, set(), "pys_cmp_if's whole-part comparison must stay out of line")


if __name__ == "__main__":
    unittest.main()
