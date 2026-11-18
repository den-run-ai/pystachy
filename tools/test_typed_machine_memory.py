"""Machine storage remains structured through closure/runtime header lowering."""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import ClassInfo, FnInfo, IFn, Ins, Val, Values
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
        # runtime.py's module names its own tags (!3, !4); a program's, the "@str" members under
        # fieldtbaa's root, numbered from TBAA_FIELDS (16 in a fresh Gen), and none without fieldtbaa.
        # A length load is bounded in each (!5)
        for op, t, metadata, runtime, program, plain in (
                ("mach.load", "int", "length.range", ", !tbaa !3, !range !5", ", !tbaa !16, !range !5", ", !range !5"),
                ("mach.load", "int", "length", ", !tbaa !3", ", !tbaa !16", ""),
                ("mach.store", "int", "length", ", !tbaa !3", ", !tbaa !16", ""),
                ("mach.load", "%byte", "bytes", ", !tbaa !4", ", !tbaa !16", ""),
                ("mach.store", "%byte", "bytes", ", !tbaa !4", ", !tbaa !16", "")):
            for mode, suffix in (("runtime", runtime), ("program", program), ("plain", plain)):
                with self.subTest(op=op, metadata=metadata, mode=mode):
                    i = memory(op, t, metadata)
                    g = Gen()
                    g.rtmode = mode == "runtime"
                    g.opts = {"fieldtbaa": True} if mode == "program" else {}
                    g.verify(function(i), False)
                    g.lower_ins(function(i), i)
                    self.assertTrue(g.out[0].endswith(suffix) and (suffix != "" or "!" not in g.out[0]), g.out)
                    self.assertEqual(g.tbaa, {} if mode != "program" else {"@str 0" if t == "int" else "@str 3": 16})
                    self.assertEqual(g.lenrange, metadata == "length.range")  # (a program's module defines !5)
        for op, t, metadata in (("mach.load", "int", "!tbaa !3"),
                                ("mach.store", "int", "length.range"),
                                ("mach.load", "float", "length"),
                                ("mach.store", "%ptr", "bytes")):
            self.assert_bad(memory(op, t, metadata))

    def test_reads_reach_across_writes_of_other_memory(self):
        # Gen.memclass: a program's field, a str's length and its bytes (a bytearray buffer's too)
        # are memories that a write of another never changes, as their TBAA says to LLVM; a write
        # of the same class, an untagged one and any in runtime.py's module stop the reuse
        def reaches(write, first_read, second_read, runtime=False):
            g = Gen()
            g.rtmode = runtime
            ci = ClassInfo("Box", Node("class", "Box", 1))
            ci.fields = ["x", "y"]
            ci.ftypes = {"x": "int", "y": "int"}
            g.classes["Box"] = ci
            first = first_read(g)
            write(g)
            second = second_read(g)
            g.fn.n = g.n
            vs = Values(g.fn, {"entry": []})
            return g.canon(vs, second) == g.canon(vs, first)

        def field(g):
            return g.mem_load(Val(g.fgep(Val("%a0", "Box"), 0), "*int")).v

        def length(g):
            return g.mload("int", "%a1", "length.range")

        def byte_at(index):
            return lambda g: g.mload("%byte", g.maddr("%byte", "%a1", index), "bytes")

        def store(kind, index="%a2"):
            return lambda g: g.mstore("%byte", "7", g.maddr("%byte", "%a1", index), kind)

        def field_store(g):
            g.mem_store(Val(g.fgep(Val("%a0", "Box"), 1), "*int"), Val("5", "int"))

        self.assertTrue(reaches(store("bytes"), field, field))  # (a buffer's byte: no field)
        self.assertTrue(reaches(store("bytes"), length, length))  # (nor a length)
        self.assertTrue(reaches(field_store, byte_at("%a3"), byte_at("%a3")))  # (a field: no byte)
        self.assertTrue(reaches(field_store, length, length))
        self.assertFalse(reaches(store("bytes"), byte_at("%a3"), byte_at("%a3")))  # (a byte may be any byte)
        self.assertFalse(reaches(store(""), field, field))  # (an untagged write may be any memory)
        self.assertFalse(reaches(store(""), length, length))
        self.assertFalse(reaches(store("bytes"), field, field, runtime=True))  # (runtime.py's: as before)
        self.assertFalse(reaches(store("bytes"), length, length, runtime=True))

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
                Gen().program(Loader([]).program(name, next(root.glob(f"programs/*/{name}"), root / name).read_text()))
        self.assertTrue({"mach.load", "mach.store", "mach.addr"}.issubset(captured))


if __name__ == "__main__":
    unittest.main()
