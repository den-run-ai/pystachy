"""runtime.c rounds floats without libm wherever the result is exact.

math.floor, math.ceil, math.trunc, round(), float.is_integer() and the % and // of whole floats
below 2**53 compute their results with conversions and int arithmetic: floor(), ceil(), trunc(),
nearbyint() and fmod() are libm calls on x86-64 before SSE4.1, and an inlined libm call that
LLVM takes for cheap may run ahead of the test that skips it. Each keeps the libm path out of line.
Set PYSTACHY_TEST_LLVM to a toolchain directory to compile runtime.c as the driver does and check
that none of these functions calls a libm rounding function itself.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LLVM = os.environ.get("PYSTACHY_TEST_LLVM", "")
LIBM = {"floor", "ceil", "trunc", "nearbyint", "rint", "round", "fmod",
        "llvm.floor.f64", "llvm.ceil.f64", "llvm.trunc.f64", "llvm.nearbyint.f64", "llvm.rint.f64", "llvm.round.f64"}
FUNCTIONS = ["pys_floor", "pys_ceil", "pys_m_trunc", "pys_round", "pys_float_is_integer", "pys_fmod", "pys_ffloordiv"]


def defined(text, name):
    """The definition of function name in LLVM IR text, or ""."""
    m = re.search(rf"^define [^\n]*@{re.escape(name)}\(.*?^}}$", text, re.M | re.S)
    return m.group(0) if m else ""


@unittest.skipUnless(LLVM, "set PYSTACHY_TEST_LLVM to compile runtime.c")
class Rounding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tools = LLVM.rstrip("/") + "/"
        with tempfile.TemporaryDirectory(prefix="pystachy-rounding-") as tmp:
            ll = Path(tmp) / "runtime.ll"
            subprocess.run([tools + "clang", "-O2", "-S", "-emit-llvm", "-x", "c", str(ROOT / "runtime.c"),
                            "-o", str(ll), "-fexceptions", "-Wno-unused-command-line-argument"], check=True)
            cls.text = ll.read_text(encoding="latin-1")

    def test_rounding_functions_call_no_libm_rounding_inline(self):
        for name in FUNCTIONS:
            with self.subTest(function=name):
                body = defined(self.text, name)
                self.assertNotEqual(body, "", f"runtime.c defines {name}")
                calls = set(re.findall(r"call [^@]*@([\w.$]+)\(", body))
                self.assertEqual(calls & LIBM, set(), f"{name} must leave its libm call out of line")


if __name__ == "__main__":
    unittest.main()
