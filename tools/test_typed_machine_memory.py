"""Machine storage remains structured through closure/runtime header lowering."""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import IFn, Ins, Val, Values
from src.pystachy_compiler.symbols import FnInfo
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

    def test_container_subclass_header_stores_have_no_class_field_tbaa(self):
        source = """class Rows(list[int]):
    def __init__(self):
        self.tag = 11

class Index(dict[str, int]):
    def __init__(self):
        self.tag = 22

print(Rows().tag + Index().tag)
"""
        ir = Gen().program(Loader([]).program("header.py", source))
        init = ir.split("define internal void @main.init() {", 1)[1].split("\n}", 1)[0]
        for cls, count in [("Rows", 4), ("Index", 12)]:
            fields = re.findall(rf"(%t\d+) = getelementptr %C\.{cls}, ptr %t\d+, i32 0, i32 (\d+)", init)
            header = {int(index): addr for addr, index in fields if int(index) < count}
            self.assertEqual(set(header), set(range(count)))
            for addr in header.values():
                self.assertRegex(init, rf"(?m)^  store (?:i64|ptr) %t\d+, ptr {addr}$")
        # Ordinary Python fields following either prefix still have their alias tags.
        for value in [11, 22]:
            self.assertRegex(ir, rf"store i64 {value}, ptr %t\d+, !tbaa !\d+")

    def test_storage_rejects_malformed_operands_types_results_and_metadata(self):
        for op in ("mach.load", "mach.store"):
            # (a word may hold a packed slot *T, and a store may write the opaque %slot)
            for t in ("", "None", "%raw", "*%slot", "*", "&int", "#", "T") + (("%slot",) if op == "mach.load" else ()):
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

    def test_runtime_records_address_fields_through_the_target_layout(self):
        # a field of one of runtime.c's records is a GEP through the record's LLVM type, so that
        # the target's layout places it; the index past the last field is the record's size
        for record, index, want in (("List", "0", "getelementptr inbounds {i64, i64, ptr, ptr}, ptr %a0, i32 0, i32 0"),
                                    ("List", "3", "getelementptr inbounds {i64, i64, ptr, ptr}, ptr %a0, i32 0, i32 3"),
                                    ("List", "4", "getelementptr inbounds {i64, i64, ptr, ptr}, ptr %a0, i64 1"),
                                    ("Str", "2", "getelementptr inbounds {i64, i64, i64}, ptr %a0, i32 0, i32 2"),
                                    ("Set", "7", "getelementptr inbounds {i64, i64, i64, i64, i64, ptr, ptr, ptr}, ptr %a0, i32 0, i32 7")):
            i = address("rec." + record, 1)
            i.a[1] = Val(index, "int")
            g = Gen()
            g.rtmode = True
            g.verify(function(i), False)
            self.assertEqual(g.opfx(i, {}), 0)
            g.lower_ins(function(i), i)
            self.assertEqual(g.out, ["  %t1 = " + want])
        for record, index, rtmode in (("List", "5", True), ("List", "%a1", True), ("List", "-1", True), ("Nothing", "0", True), ("List", "0", False)):
            i = address("rec." + record, 1)
            i.a[1] = Val(index, "int")
            errors = StringIO()
            g = Gen()
            g.rtmode = rtmode
            with redirect_stderr(errors), self.assertRaises(SystemExit):
                g.verify(function(i), False)
            self.assertIn("mach.addr", errors.getvalue())
        i = address("%i32")
        g = Gen()
        g.verify(function(i), False)
        g.lower_ins(function(i), i)
        self.assertEqual(g.out, ["  %t1 = getelementptr i32, ptr %a0, i64 2"])

    def test_runtime_memory_tags_tell_items_words_and_addresses_apart(self):
        for op, t, metadata, tag in (("mach.load", "int", "rt.word", 13), ("mach.store", "int", "rt.word", 13),
                                     ("mach.load", "int", "rt.int", 14), ("mach.store", "int", "rt.int", 14),
                                     ("mach.load", "%ptr", "rt.ptr", 15), ("mach.store", "%ptr", "rt.ptr", 15)):
            i = memory(op, t, metadata)
            g = Gen()
            g.rtmode = True
            g.verify(function(i), False)
            g.lower_ins(function(i), i)
            self.assertTrue(g.out[0].endswith(f", !tbaa !{tag}"), g.out)
            self.assert_bad(i)  # (a program's module has no such tags)
        for op, t, metadata in (("mach.load", "%ptr", "rt.word"), ("mach.store", "float", "rt.int"), ("mach.load", "int", "rt.ptr")):
            i = memory(op, t, metadata)
            errors = StringIO()
            g = Gen()
            g.rtmode = True
            with redirect_stderr(errors), self.assertRaises(SystemExit):
                g.verify(function(i), False)
            self.assertIn(op, errors.getvalue())

    def test_runtime_primitives_lower_to_unchecked_machine_memory(self):
        # runtime.py's _rt.word, _rt.get, ...: each lowers to the loads, stores and addresses it
        # names, with no check, and a cast (erased) types an address as an _rt.Ptr
        p, q, n = Val("%a0", "rtptr"), Val("%a1", "rtptr"), Val("%a2", "int")
        s = Val("%a0", "str")
        for name, vals, result, lines in (
                ("word", [p, n], "int", ["  %t1 = getelementptr i64, ptr %a0, i64 %a2", "  %t2 = load i64, ptr %t1, !tbaa !13"]),
                ("put", [p, n, n], "None", ["  %t1 = getelementptr i64, ptr %a0, i64 %a2", "  store i64 %a2, ptr %t1, !tbaa !13"]),
                ("byte_at", [s, n], "int", ["  %t1 = getelementptr i8, ptr %a0, i64 %a2", "  %t2 = load i8, ptr %t1", "  %t3 = zext i8 %t2 to i64"]),
                ("put_byte", [p, n, n], "None", ["  %t1 = trunc i64 %a2 to i8", "  %t2 = getelementptr i8, ptr %a0, i64 %a2", "  store i8 %t1, ptr %t2"]),
                ("i32_at", [p, n], "int", ["  %t1 = getelementptr i32, ptr %a0, i64 %a2", "  %t2 = load i32, ptr %t1", "  %t3 = sext i32 %t2 to i64"]),
                ("put_i32", [p, n, n], "None", ["  %t1 = trunc i64 %a2 to i32", "  %t2 = getelementptr i32, ptr %a0, i64 %a2", "  store i32 %t1, ptr %t2"]),
                ("at", [p, n], "rtptr", ["  %t1 = getelementptr i64, ptr %a0, i64 %a2"]),
                ("offset", [p, n], "rtptr", ["  %t1 = getelementptr i8, ptr %a0, i64 %a2"]),
                ("addr", [s], "int", ["  %t1 = ptrtoint ptr %a0 to i64"]),
                ("ptr", [Val("%a0", "int")], "rtptr", ["  %t1 = inttoptr i64 %a0 to ptr"]),
                ("get", [p, Val("@rec.List.cap", "str")], "int", ["  %t1 = getelementptr inbounds {i64, i64, ptr, ptr}, ptr %a0, i32 0, i32 1", "  %t2 = load i64, ptr %t1, !tbaa !14"]),
                ("set", [p, Val("@rec.Dict.cut", "str"), n], "None", ["  %t1 = getelementptr inbounds {i64, i64, i64, i64, ptr, ptr, ptr, ptr, i64, i64, ptr, ptr}, ptr %a0, i32 0, i32 8", "  store i64 %a2, ptr %t1, !tbaa !14"]),
                ("getp", [p, Val("@rec.List.a", "str")], "rtptr", ["  %t1 = getelementptr inbounds {i64, i64, ptr, ptr}, ptr %a0, i32 0, i32 2", "  %t2 = load ptr, ptr %t1, !tbaa !15"]),
                ("setp", [p, Val("@rec.List.ids", "str"), q], "None", ["  %t1 = getelementptr inbounds {i64, i64, ptr, ptr}, ptr %a0, i32 0, i32 3", "  store ptr %a1, ptr %t1, !tbaa !15"]),
                ("get", [s, Val("@rec.Str.len", "str")], "int", ["  %t1 = getelementptr inbounds {i64, i64, i64}, ptr %a0, i32 0, i32 0", "  %t2 = load i64, ptr %t1, !tbaa !3"]),
                ("field", [p, Val("@rec.VTuple.ids", "str")], "rtptr", ["  %t1 = getelementptr inbounds {i64, ptr}, ptr %a0, i32 0, i32 1"]),
                ("sizeof", [Val("@rec.List", "str")], "int", ["  %t1 = getelementptr {i64, i64, ptr, ptr}, ptr null, i64 1", "  %t2 = ptrtoint ptr %t1 to i64"]),
                ("move", [p, q, n], "None", ["  call void @llvm.memmove.p0.p0.i64(ptr %a0, ptr %a1, i64 %a2, i1 false)"]),
                ("cpy", [p, s, n], "None", ["  call void @llvm.memcpy.p0.p0.i64(ptr %a0, ptr %a0, i64 %a2, i1 false)"]),
                ("fill", [p, n, n], "None", ["  %t1 = trunc i64 %a2 to i8", "  call void @llvm.memset.p0.i64(ptr %a0, i8 %t1, i64 %a2, i1 false)"]),
                ("cmp", [p, q, n], "int", ["  %t1 = call i32 @memcmp(ptr %a0, ptr %a1, i64 %a2)", "  %t2 = sext i32 %t1 to i64"])):
            with self.subTest(primitive=name, operands=[v.v for v in vals]):
                g = Gen()
                g.rtmode = True
                value = g.primitive(name, vals)
                self.assertEqual(value.t, result)
                g.add(Ins("ret.none", "", ""))
                g.number_casts()
                g.fn.n = g.n
                g.verify(g.fn, False)
                g.erase_casts(g.fn)
                for i in g.fn.blocks[0].code[:-1]:
                    g.lower_ins(g.fn, i)
                self.assertEqual(g.out, lines)
        # a field is read as what it holds, and both a record and a field are literals of RTRECORDS
        for name, vals in (("get", [p, Val("@rec.List.a", "str")]), ("setp", [p, Val("@rec.List.len", "str"), q]),
                           ("get", [p, Val("@rec.List.size", "str")]), ("get", [p, Val("@rec.Tuple.len", "str")]),
                           ("get", [p, Val("@s.0", "str")]), ("sizeof", [Val("@rec.Lists", "str")]),
                           ("word", [n, n]), ("word", [p]), ("put", [p, n, p]), ("at", [Val("%a0", "%ptr"), n])):
            with self.subTest(primitive=name, operands=[v.v for v in vals]):
                g = Gen()
                g.rtmode = True
                errors = StringIO()
                with redirect_stderr(errors), self.assertRaises(SystemExit):
                    g.primitive(name, vals)
                self.assertIn("_rt." + name, errors.getvalue())

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
