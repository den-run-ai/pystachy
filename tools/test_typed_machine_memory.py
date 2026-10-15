"""Machine storage remains structured through closure/runtime header lowering."""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import FnInfo, IFn, Ins, Val, Values
from src.pystachy_compiler.loader import Loader
from src.pystachy_compiler.specs import RAWR, RAWW
from src.pystachy_compiler.syntax import Node


def memory(op="mach.load", t="int", metadata="", pointer="%a0"):
    i = Ins(op, t if op == "mach.load" else "", metadata)
    i.a = [Val(pointer, "%ptr")]
    if op == "mach.store":
        i.a.append(Val("%a1", t))
    i.r = [1] if op == "mach.load" else []
    return i


def address(t="int", inbounds=0):
    i = Ins("mach.addr", "%ptr", t)
    i.a = [Val("%a0", "%ptr"), Val("2", "int")]
    i.k = inbounds
    i.r = [1]
    return i


def function(i):
    fn = IFn(FnInfo("machine", "@machine", Node("def", "machine", 1), ""))
    fn.n = 2
    fn.blocks[0].code = [i, Ins("ret.none", "", "")]
    return fn


class TypedMachineMemoryTests(unittest.TestCase):
    def assert_bad(self, i):
        errors = StringIO()
        with redirect_stderr(errors), self.assertRaises(SystemExit):
            Gen().verify(function(i), False)
        self.assertIn(i.op, errors.getvalue())

    def test_storage_types_numbers_effects_and_exact_lowering(self):
        for t, ll in (("int", "i64"), ("bool", "i1"), ("float", "double"),
                      ("%ptr", "ptr"), ("%byte", "i8"), ("%i32", "i32"),
                      ("Box", "ptr"), ("opt[int]", "ptr")):
            for op in ("mach.load", "mach.store"):
                with self.subTest(type=t, op=op):
                    i = memory(op, t)
                    g = Gen()
                    g.verify(function(i), False)
                    self.assertEqual(g.nums(i), 1 if op == "mach.load" else 0)
                    self.assertEqual(g.opfx(i, {}), RAWR if op == "mach.load" else RAWW)
                    g.lower_ins(function(i), i)
                    self.assertEqual(g.out, [f"  %t1 = load {ll}, ptr %a0" if op == "mach.load"
                                             else f"  store {ll} %a1, ptr %a0"])

    def test_finite_metadata_preserves_tbaa_and_range(self):
        for op, t, metadata, suffix in (("mach.load", "int", "length.range", ", !tbaa !3, !range !5"),
                                        ("mach.load", "int", "length", ", !tbaa !3"),
                                        ("mach.store", "int", "length", ", !tbaa !3"),
                                        ("mach.load", "%byte", "bytes", ", !tbaa !4"),
                                        ("mach.store", "%byte", "bytes", ", !tbaa !4")):
            i = memory(op, t, metadata)
            g = Gen()
            g.verify(function(i), False)
            g.lower_ins(function(i), i)
            self.assertTrue(g.out[0].endswith(suffix), g.out)
        for op, t, metadata in (("mach.load", "int", "!tbaa !3"),
                                ("mach.store", "int", "length.range"),
                                ("mach.load", "float", "length"),
                                ("mach.store", "%ptr", "bytes")):
            self.assert_bad(memory(op, t, metadata))

    def test_storage_rejects_malformed_operands_types_results_and_metadata(self):
        for op in ("mach.load", "mach.store"):
            for t in ("", "None", "%slot", "%raw", "*int", "#", "T"):
                self.assert_bad(memory(op, t))
            for field, value in (("a", []), ("a", [Val("%a0", "int")]),
                                 ("x", "LLVM"), ("k", 1), ("b", ["entry"]),
                                 ("r", [1, 2])):
                i = memory(op)
                setattr(i, field, value)
                self.assert_bad(i)
        i = memory("mach.store")
        i.t = "int"
        self.assert_bad(i)

    def test_indexed_address_has_explicit_element_index_and_inbounds(self):
        for t, ll in (("int", "i64"), ("%ptr", "ptr"), ("%byte", "i8")):
            for inbounds in (0, 1):
                i = address(t, inbounds)
                g = Gen()
                g.verify(function(i), False)
                self.assertEqual(g.opfx(i, {}), 0)
                g.lower_ins(function(i), i)
                self.assertEqual(g.out, [f"  %t1 = getelementptr{' inbounds' if inbounds else ''} {ll}, ptr %a0, i64 2"])
        for field, value in (("t", "int"), ("s", "i64"), ("s", "%raw"),
                             ("k", -1), ("k", 2), ("x", "inbounds"),
                             ("a", [Val("%a0", "%ptr"), Val("2", "%i32")]),
                             ("b", ["entry"]), ("r", [])):
            i = address()
            setattr(i, field, value)
            self.assert_bad(i)

    def test_indexed_addresses_interoperate_with_tuple_slots(self):
        g = Gen()
        i = Ins("tuple.store", "", "int")
        i.a = [Val("%a0", "tuple[int,int,int]"), Val("99", "%slot")]
        i.k = 2
        g.put(i, 1)
        p = g.maddr("int", "%a0", "2")
        v = g.mload("int", p)
        g.fn.n = g.n
        vs = Values(g.fn, {"entry": []})
        self.assertEqual(g.canon(vs, f"%t{i.r[0]}"), g.canon(vs, p))
        self.assertEqual(g.canon(vs, v), "99")

    def test_source_memory_producers_are_structured(self):
        root = Path(__file__).resolve().parent.parent / "tests"
        captured = []
        lower = Gen.lower

        def capture(g, fn):
            g.verify(fn, False)
            for b in fn.blocks:
                for i in b.code:
                    if i.op == "raw":
                        self.assertFalse(i.s.startswith("store ") or " = load " in i.s
                                         or " = getelementptr " in i.s, i.s)
                    if i.op.startswith("mach."):
                        captured.append(i.op)
            lower(g, fn)

        with patch.object(Gen, "lower", capture):
            for name in ("closures.py", "generator_consumers.py", "typed_ir_slots.py", "ir/passes_exc.py"):
                Gen().program(Loader([]).program(name, (root / name).read_text()))
        self.assertTrue({"mach.load", "mach.store", "mach.addr"}.issubset(captured))


if __name__ == "__main__":
    unittest.main()
