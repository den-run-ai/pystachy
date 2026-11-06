"""Proven scalar tags select atomic boxes only at the LLVM lowering boundary."""
import os
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import FnInfo, IFn, Ins, Val
from src.pystachy_compiler.loader import Loader
from src.pystachy_compiler.specs import BIG, OPTS
from src.pystachy_compiler.syntax import Node
from src.pystachy_compiler.utils import optimizations

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "tests/programs/inference/union_gc_boxes.py").read_text()


def compile_source(setting, source=SOURCE):
    with patch.dict(os.environ, {"PYSTACHY_OPT": setting, "PYSTACHY_IRCHECK": "1"}):
        g = Gen()
        llvm = g.program(Loader([]).program("union_gc_boxes.py", source))
    bodies = dict(re.findall(r"^define [^@]*@([^ (]+)\([^\n]*\n(.*?)^\}", llvm, re.M | re.S))
    return g, llvm, bodies


class AtomicUnionTests(unittest.TestCase):
    def test_experiment_is_explicit_and_tokens_apply_in_order(self):
        for setting, expected in [
            ("", set(OPTS)),
            ("-atomicunion", set(OPTS)),
            ("+atomicunion", set(OPTS) | {"atomicunion"}),
            ("+atomicunion,-atomicunion", set(OPTS)),
            ("+atomicunion,-all", set()),
            ("-all,+atomicunion", {"atomicunion"}),
        ]:
            with self.subTest(setting=setting), patch.dict(os.environ, {"PYSTACHY_OPT": setting}):
                self.assertEqual(set(optimizations()), expected)

    def test_source_proof_keeps_reference_optional_and_runtime_tags_scanned(self):
        off, llvm_off, before = compile_source("")
        on, llvm_on, after = compile_source("+atomicunion")
        self.assertNotIn("@pys_ubox_atomic(", llvm_off)
        self.assertIn("declare ptr @pys_ubox_atomic(i64, i64)", llvm_on)
        for name in ("int_member", "float_member", "bool_member"):
            with self.subTest(function=name):
                self.assertIn("@pys_ubox(", before["f." + name])
                self.assertIn("@pys_ubox_atomic(", after["f." + name])
                self.assertNotIn("@pys_ubox(", after["f." + name])
        for name in ("str_member", "list_member", "dict_member", "reference_member"):
            with self.subTest(function=name):
                self.assertIn("@pys_ubox(", after["f." + name])
                self.assertNotIn("@pys_ubox_atomic(", after["f." + name])
        self.assertIn("@pys_ubox_opt(", after["f.optional_member"])
        self.assertNotIn("@pys_ubox_atomic(", after["f.optional_member"])
        # unionslots removes the loop's allocations, then reboxes a runtime tag.
        self.assertRegex(after["f.runtime_member"], r"@pys_ubox\(i64 %")
        self.assertNotIn("@pys_ubox_atomic(", after["f.runtime_member"])
        # The experiment must not introduce a new typed-IR operation or bypass
        # the existing union proofs / the transformations they protect.
        def boxes(g):
            return [(fn.f.ll, i.s, [(a.v, a.t) for a in i.a])
                    for fn in g.fns for b in fn.blocks for i in b.code
                    if i.op == "rt" and i.s.startswith("ubox")]
        self.assertEqual(boxes(off), boxes(on))
        self.assertNotIn("allockind", after["f.int_member"])

    def test_tag_number_is_not_assumed_and_non_scalar_representations_stay_scanned(self):
        # Allocate tags in an unfamiliar order, including a promoting int whose
        # representation owns an Mpz. This directly exercises the lowerer's
        # boundary; the source language currently narrows ints in closed unions.
        g = Gen()
        g.opts = {"atomicunion": True}
        tags = {m: g.utag(m) for m in ("str", BIG, "list[int]", "float", "bool", "int")}
        key = g.runtime("pys_ubox")
        fn = IFn(FnInfo("probe", "@probe", Node("def", "probe", 1), ""))
        for member, tag in list(tags.items()) + [("runtime", "%tag"), ("unknown", "99999")]:
            with self.subTest(member=member):
                g.out = []
                i = Ins("rt", "%ptr", key)
                i.r = [1]
                i.a = [Val(str(tag), "int"), Val("%payload", "*T")]
                g.lower_ins(fn, i)
                symbol = "pys_ubox_atomic" if member in {"int", "float", "bool"} else "pys_ubox"
                self.assertIn("@" + symbol + "(", "\n".join(g.out))

    def test_promoting_optional_boxes_keep_the_wide_payload(self):
        source = '''# pystachy: python-int
def optional_big(n: int) -> int | None:
    return n

def native_union(n: int) -> int | str:
    return n

print(optional_big(2**80), native_union(17))
'''
        _, _, before = compile_source("", source)
        _, _, bodies = compile_source("+atomicunion", source)
        self.assertIn("@pys_big_box(", bodies["f.optional_big"])
        self.assertNotIn("@pys_ubox_atomic(", bodies["f.optional_big"])
        # A promoting input can enter a native-int union only after the existing
        # checked conversion establishes that it fits. A wide input still raises.
        native = bodies["f.native_union"]
        self.assertRegex(native, r"extractvalue \{i64, ptr\} %t[0-9]+, 1")
        self.assertIn("br i1", native)
        self.assertIn("@pys_raise(", native)
        self.assertIn("@pys_ubox_atomic(", native)
        self.assertEqual(native, before["f.native_union"].replace("@pys_ubox(", "@pys_ubox_atomic("))


if __name__ == "__main__":
    unittest.main()
