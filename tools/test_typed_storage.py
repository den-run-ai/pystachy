"""Typed native storage contracts and native/machine storage optimization interoperability."""
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
from src.pystachy_compiler.specs import FXBIT, RAWR, RAWW
from src.pystachy_compiler.syntax import Node


def memory_op(op, t="int", address="%x.1"):
    i = Ins(op, t if op == "mem.load" else "", "")
    i.a = [Val(address, "*" + t)]
    if op == "mem.store":
        i.a.append(Val("%a0", t))
    i.r = [1] if op == "mem.load" else []
    return i


def function_with(i):
    fn = IFn(FnInfo("storage", "@storage", Node("def", "storage", 1), ""))
    fn.n = 2
    fn.blocks[0].code = [i, Ins("ret.none", "", "")]
    return fn


class TypedStorageTests(unittest.TestCase):
    def assert_bad(self, i):
        errors = StringIO()
        with redirect_stderr(errors), self.assertRaises(SystemExit):
            Gen().verify(function_with(i), False)
        self.assertIn("bad IR", errors.getvalue())
        self.assertIn(i.op, errors.getvalue())

    def test_native_address_and_value_contracts(self):
        for t in ("int", "float", "bool", "None", "str", "bytes", "file", "env",
                  "list[int]", "dict[str,float]", "tuple[int,str]", "Box",
                  "opt[int]", "union[int,str]"):
            for op in ("mem.load", "mem.store"):
                with self.subTest(type=t, op=op):
                    i = memory_op(op, t)
                    g = Gen()
                    g.verify(function_with(i), False)
                    self.assertEqual(g.nums(i), 1 if op == "mem.load" else 0)

    def test_rejects_untyped_addresses_and_runtime_pseudo_types(self):
        for t in ("", "int", "*", "**int", "*%slot", "*%ptr", "*#", "*T", "*K", "*V", "*S"):
            for op in ("mem.load", "mem.store"):
                with self.subTest(type=t, op=op):
                    i = memory_op(op)
                    i.a[0].t = t
                    self.assert_bad(i)

    def test_rejects_mismatched_native_types(self):
        i = memory_op("mem.load")
        i.t = "float"
        self.assert_bad(i)
        i = memory_op("mem.store")
        i.a[1].t = "float"
        self.assert_bad(i)
        i = memory_op("mem.store")
        i.t = "int"
        self.assert_bad(i)

    def test_rejects_operand_result_and_metadata_mutations(self):
        for op in ("mem.load", "mem.store"):
            for operands in ([], [Val("%a0", "*int")] * 3):
                i = memory_op(op)
                i.a = operands
                self.assert_bad(i)
            for results in ([1, 2], [] if op == "mem.load" else [1]):
                i = memory_op(op)
                i.r = results
                self.assert_bad(i)
            for field, value in (("s", "load i64"), ("x", "int"), ("k", 1), ("b", ["entry"])):
                with self.subTest(op=op, field=field):
                    i = memory_op(op)
                    setattr(i, field, value)
                    self.assert_bad(i)

    def test_effects_distinguish_local_global_field_and_unknown_memory(self):
        for op, read, unknown in (("mem.load", "r", RAWR), ("mem.store", "w", RAWW)):
            for address, effect, fields in (("%x.1", 0, {}), ("@g.x", FXBIT[read + "G"], {}),
                                           ("%t2", FXBIT[read + "O"], {"%t2": True}),
                                           ("%t2", unknown, {}), ("%a0", unknown, {})):
                with self.subTest(op=op, address=address, fields=fields):
                    self.assertEqual(Gen().opfx(memory_op(op, address=address), fields), effect)

    def test_lowering_retains_native_layouts_and_numbers(self):
        for t, ll in (("int", "i64"), ("float", "double"), ("bool", "i1"),
                      ("None", "ptr"), ("Box", "ptr"), ("opt[int]", "ptr")):
            with self.subTest(type=t):
                g = Gen()
                g.lower_ins(function_with(memory_op("mem.load", t)), memory_op("mem.load", t))
                g.lower_ins(function_with(memory_op("mem.store", t)), memory_op("mem.store", t))
                self.assertEqual(g.out, [f"  %t1 = load {ll}, ptr %x.1",
                                         f"  store {ll} %a0, ptr %x.1"])

    def test_reaching_preserves_native_and_machine_load_store_combinations(self):
        for typed_store in (False, True):
            for typed_load in (False, True):
                for address in ("%x.1", "@g.x", "%a1"):
                    with self.subTest(store=typed_store, load=typed_load, address=address):
                        g = Gen()
                        a = Val(address, "*int")
                        if typed_store:
                            g.mem_store(a, Val("%a0", "int"))
                        else:
                            g.mstore("int", "%a0", address)
                        v = g.mem_load(a).v if typed_load else g.mload("int", address)
                        again = g.mem_load(a).v
                        g.fn.n = g.n
                        vs = Values(g.fn, {"entry": []})
                        self.assertEqual(g.canon(vs, v), "%a0")
                        self.assertEqual(g.canon(vs, again), "%a0")

    def test_heap_store_aliases_barrier_but_other_locals_and_globals_do_not(self):
        for typed in (False, True):
            for address, blocked in (("%a2", True), ("%other.2", False), ("@g.other", False)):
                with self.subTest(typed=typed, address=address):
                    g = Gen()
                    g.mem_store(Val("%a1", "*int"), Val("%a0", "int"))
                    if typed:
                        g.mem_store(Val(address, "*int"), Val("99", "int"))
                    else:
                        g.mstore("int", "99", address)
                    v = g.mem_load(Val("%a1", "*int"))
                    g.fn.n = g.n
                    vs = Values(g.fn, {"entry": []})
                    self.assertEqual(g.canon(vs, v.v), v.v if blocked else "%a0")

    def test_calls_invalidate_global_and_heap_reads_but_preserve_local_values(self):
        for address, blocked in (("%x.1", False), ("@g.x", True), ("%a1", True)):
            g = Gen()
            g.mem_store(Val(address, "*int"), Val("%a0", "int"))
            g.add(Ins("call", "None", "@unknown"))
            v = g.mem_load(Val(address, "*int"))
            g.fn.n = g.n
            self.assertEqual(g.canon(Values(g.fn, {"entry": []}), v.v), v.v if blocked else "%a0")

    def test_frontend_keeps_variable_and_parameter_storage_typed(self):
        source = """count = 0

def add(x: int) -> int:
    global count
    count += x
    y = x
    return y

print(add(2))
"""
        captured = []
        lower = Gen.lower

        def capture(g, fn):
            g.verify(fn, False)
            captured.extend(i for b in fn.blocks for i in b.code)
            lower(g, fn)

        with patch.object(Gen, "lower", capture):
            Gen().program(Loader([]).program("storage.py", source))
        self.assertTrue(any(i.op == "mem.load" and i.a[0].v.startswith("@g.") for i in captured))
        self.assertTrue(any(i.op == "mem.store" and i.a[1].v == "%a0" for i in captured))
        self.assertFalse(any(i.op == "raw" and (i.s.startswith("store ") or " = load " in i.s)
                             for i in captured))


if __name__ == "__main__":
    unittest.main()
