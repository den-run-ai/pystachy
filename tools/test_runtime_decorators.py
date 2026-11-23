"""Runtime mode's decorators reach the functions' LLVM definitions.

@_rt.noinline keeps a function a call of its own (the entry points that hash a key, which a
program's AOT build would otherwise copy into every use), @_rt.inline gives each caller a
copy, @_rt.cold is a slow path, and @_rt.unchecked changes the arithmetic, not the attributes.
"""
import os
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


def compile_runtime(source, tmp, opt=None):
    out = Path(tmp) / "module.ll"
    env = {k: v for k, v in os.environ.items() if k != "PYSTACHY_OPT"}
    if opt is not None:
        env["PYSTACHY_OPT"] = opt
    subprocess.run([sys.executable, str(ROOT / "pystachy.py"), "rt", str(source), "-o", str(out)], check=True, cwd=ROOT, env=env)
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

    def test_the_entry_points_that_hash_stay_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            ir = compile_runtime(ROOT / "runtime.py", tmp)
        for name in ("pys_set_add", "pys_set_has", "pys_set_discard", "pys_set_remove", "pys_set_big_add", "pys_set_big_has",
                     "pys_dict_has", "pys_dict_get", "pys_dict_getitem", "pys_dict_find", "pys_dict_set", "pys_dict_setdefault",
                     "pys_dict_entry", "pys_dict_big_find", "pys_dict_bkey_get"):
            with self.subTest(name):
                self.assertEqual(attributes(ir, name), ["noinline"])
        self.assertEqual(attributes(ir, "f.set_big_put"), ["cold", "noinline"])

    def test_a_result_of_two_words_is_returned_by_value(self):
        # RUNTIME's int+ results: the exported symbol returns {i64, ptr}, and its body, internal,
        # the tuple's two slots (tupleret); no tuple is allocated for it. The runtime's ABI, not an
        # optimization: so too where PYSTACHY_OPT turns tupleret off
        for opt in (None, "-tupleret"):
            with self.subTest(opt=opt):
                self.two_words(opt)

    def two_words(self, opt):
        with tempfile.TemporaryDirectory() as tmp:
            ir = compile_runtime(ROOT / "runtime.py", tmp, opt)
        for name in ("pys_set_big_pop", "pys_dict_big_pop", "pys_dict_big_setdefault", "pys_dict_bkey_big_pop", "pys_dict_bkey_big_setdefault"):
            with self.subTest(name):
                self.assertRegex(ir, r"(?m)^define \{i64, ptr\} @" + name + r"\(")
                self.assertRegex(ir, r"(?m)^define internal \{i64, i64\} @v\." + name + r"\(")
                body = ir[ir.index("@v." + name + "("):]
                body = body[: body.index("\n}\n")]
                self.assertNotIn("@pys_alloc(i64 16)", body)
        self.assertEqual(attributes(ir, "pys_dict_bkey_big_pop"), ["noinline"])
        self.assertEqual(attributes(ir, "v.pys_dict_bkey_big_pop"), [])

    def test_a_dict_lookup_has_its_hash_inline_and_its_probe_out_of_line(self):
        # runtime.c's shape: the hash and the choice of probe are a copy in each entry point, and
        # the probes of int and str keys are functions of their own
        with tempfile.TemporaryDirectory() as tmp:
            ir = compile_runtime(ROOT / "runtime.py", tmp)
        for name in ("f.dict_slot", "f.dict_put", "pys_rt_dhash", "pys_rt_dfind", "f.dict_entry", "pys_rt_dadd"):
            with self.subTest(name):
                self.assertEqual(attributes(ir, name), ["alwaysinline"])
        for name in ("f.dict_find_int", "f.dict_find_str"):
            with self.subTest(name):
                self.assertEqual(attributes(ir, name), ["noinline"])


if __name__ == "__main__":
    unittest.main()
