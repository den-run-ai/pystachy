"""Runtime mode's decorators reach the functions' LLVM definitions.

@_rt.noinline keeps a function a call of its own (the entry points that hash a key, which a
program's AOT build would otherwise copy into every use), @_rt.inline gives each caller a
copy, @_rt.cold is a slow path, and @_rt.unchecked changes the arithmetic, not the attributes.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULE = '''import _rt


@_rt.inline
@_rt.unchecked
def step(i: int, k: int) -> int:
    return i * 5 + k


@_rt.noinline
def pys_probe(i: int) -> int:
    return step(i, 1)


@_rt.noinline
@_rt.unchecked
def pys_both(i: int) -> int:
    return step(i, 4) + 1


@_rt.cold
def pys_slow(i: int) -> int:
    return step(i, 2)


def pys_plain(i: int) -> int:
    return step(i, 3)
'''


def compile_runtime(source, tmp):
    out = Path(tmp) / "module.ll"
    subprocess.run([sys.executable, str(ROOT / "pystachy.py"), "rt", str(source), "-o", str(out)], check=True, cwd=ROOT)
    return out.read_text(encoding="latin-1")


def attributes(ir, name):
    m = re.search(r"^define [^@]*@" + re.escape(name) + r"\([^)]*\)([^{]*)\{$", ir, re.M)
    if m is None:
        raise AssertionError(f"no definition of {name}")
    return m.group(1).split()


class Decorators(unittest.TestCase):
    def test_each_decorator_marks_its_function(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "module.py"
            source.write_text(MODULE)
            ir = compile_runtime(source, tmp)
        self.assertEqual(attributes(ir, "f.step"), ["alwaysinline"])
        self.assertEqual(attributes(ir, "pys_probe"), ["noinline"])
        self.assertEqual(attributes(ir, "pys_both"), ["noinline"])
        self.assertEqual(attributes(ir, "pys_slow"), ["cold", "noinline"])
        self.assertEqual(attributes(ir, "pys_plain"), [])
        # (the unchecked function's arithmetic has no overflow check; the others' has)
        body = ir[ir.index("@pys_both(") : ir.index("@pys_slow(")]
        self.assertIn("add nsw", body)
        self.assertNotIn("with.overflow", body)

    def test_the_set_entry_points_that_hash_stay_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            ir = compile_runtime(ROOT / "runtime.py", tmp)
        for name in ("pys_set_add", "pys_set_has", "pys_set_discard", "pys_set_remove", "pys_set_big_add", "pys_set_big_has"):
            with self.subTest(name):
                self.assertEqual(attributes(ir, name), ["noinline"])
        self.assertEqual(attributes(ir, "f.set_big_put"), ["cold", "noinline"])


if __name__ == "__main__":
    unittest.main()
