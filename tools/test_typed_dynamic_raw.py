"""Opaque dynamic identity bits cannot masquerade as typed payload reads.

Malformed IR is only verified, never lowered or executed.
"""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import Val, Values
from src.pystachy_compiler.loader import Loader
from src.pystachy_compiler.machine_ir import machine_ops
from tools.test_typed_union_proofs import Case


def raw_case():
    c = Case("raw_identity", ["dyn", "%ptr"])
    bits = c.op("dyn.raw", "%slot", a=[("%a0", "dyn")])
    return c, bits


class DynamicRawTests(unittest.TestCase):
    def assert_bad(self, case, message="dyn.raw"):
        errors = StringIO()
        with redirect_stderr(errors), self.assertRaises(SystemExit):
            case.g.verify(case.fn, False)
        self.assertIn(message, errors.getvalue())

    def test_builder_has_no_member_claim_or_effects(self):
        g = Gen()
        value = g.dyn_raw(Val("%a0", "dyn"))
        ins, = g.fn.blocks[0].code
        self.assertEqual((ins.op, ins.t, ins.s, ins.x, ins.k, ins.b),
                         ("dyn.raw", "%slot", "", "", 0, []))
        self.assertEqual((value.v, value.t), ("%t" + str(ins.r[1]), "int"))
        self.assertEqual(g.nums(ins), 2)
        self.assertEqual(g.opfx(ins, {}), 0)

    def test_lowering_preserves_the_existing_two_load_instructions(self):
        c, _ = raw_case()
        ins = c.b.code[0]
        for machine in machine_ops(ins):
            c.g.lower_ins(c.fn, machine)
        raw = c.g.out[:]
        c.g.out = []
        ins.op, ins.s = "dyn.payload", "int"
        for machine in machine_ops(ins):
            c.g.lower_ins(c.fn, machine)
        self.assertEqual(raw, c.g.out)
        self.assertEqual(raw, ["  %t1 = getelementptr i64, ptr %a0, i64 1",
                               "  %t2 = load i64, ptr %t1"])

    def test_repeated_reads_keep_the_same_opaque_value(self):
        g = Gen()
        first = g.dyn_raw(Val("%a0", "dyn"))
        second = g.dyn_raw(Val("%a0", "dyn"))
        g.fn.n = g.n
        values = Values(g.fn, {"entry": []})
        self.assertEqual(g.canon(values, first.v), g.canon(values, second.v))

    def test_direct_integer_equalities_are_allowed_in_both_orders(self):
        for pred in ("==", "!="):
            for swap in (False, True):
                with self.subTest(predicate=pred, swap=swap):
                    c, bits = raw_case()
                    args = [(bits, "int"), ("0", "int")]
                    c.op("num.cmp", "bool", pred, a=args[::-1] if swap else args)
                    c.ret()
                    c.g.verify(c.fn, False)

    def test_shape_and_metadata_are_rejected(self):
        changes = [("t", "int"), ("s", "float"), ("x", "int"), ("k", 1),
                   ("b", ["entry"]), ("a", []), ("a", [Val("%a0", "int")]),
                   ("a", [Val("%a0", "dyn"), Val("%a0", "dyn")]),
                   ("r", []), ("r", [1]), ("r", [-1, 2]), ("r", [1, 1])]
        for field, value in changes:
            with self.subTest(field=field, value=value):
                c, _ = raw_case()
                setattr(c.b.code[0], field, value)
                c.ret()
                self.assert_bad(c)

    def test_bits_cannot_be_reinterpreted_stored_called_or_computed(self):
        for operation in ("unpack", "cast", "promote", "arithmetic", "store", "call", "select", "phi", "ordering", "float"):
            with self.subTest(operation=operation):
                c, bits = raw_case()
                if operation == "unpack":
                    c.op("slot.unpack", "str", a=[(bits, "%slot")])
                elif operation == "cast":
                    c.op("scalar.cast", "%ptr", "inttoptr", a=[(bits, "int")])
                elif operation == "promote":
                    c.op("num.cast", "float", a=[(bits, "int")])
                elif operation == "arithmetic":
                    c.op("scalar.bin", "int", "add", a=[(bits, "int"), ("1", "int")])
                elif operation == "store":
                    c.op("mem.store", a=[("@output", "*int"), (bits, "int")])
                elif operation == "call":
                    c.op("icall", "None", a=[("%a1", "%ptr"), (bits, "int")])
                elif operation == "select":
                    c.op("select", "int", a=[("true", "bool"), (bits, "int"), ("0", "int")])
                elif operation == "phi":
                    c.op("br", b=["join"])
                    c.block("join")
                    c.op("phi", "int", a=[(bits, "int")], b=["entry"])
                elif operation == "ordering":
                    c.op("num.cmp", "bool", "<", a=[(bits, "int"), ("0", "int")])
                else:
                    c.op("num.cmp", "bool", "==", a=[(bits, "float"), ("0.0", "float")])
                c.ret()
                self.assert_bad(c, "dyn.raw bits require")

    def test_internal_address_cannot_escape_even_before_its_producer(self):
        for forward in (False, True):
            with self.subTest(forward_reference=forward):
                c, _ = raw_case()
                address = "%t" + str(c.b.code[0].r[0])
                c.op("mem.load", "int", a=[(address, "*int")])
                if forward:
                    c.b.code[0], c.b.code[1] = c.b.code[1], c.b.code[0]
                c.ret()
                self.assert_bad(c, "dyn.raw internal address")

    def test_frontend_identity_uses_raw_reads(self):
        source = """# pystachy: dynamic-any
from typing import Any

def same(a: Any, b: Any) -> bool:
    return a is b

print(same(1.5, 1.5), same("x", "x"))
"""
        captured = []
        lower = Gen.lower

        def capture(g, fn):
            g.verify(fn, False)
            captured.extend(i for b in fn.blocks for i in b.code if i.op == "dyn.raw")
            lower(g, fn)

        root = Path(__file__).resolve().parent.parent
        with patch.object(Gen, "lower", capture):
            Gen().program(Loader([str(root / "lib")]).program("raw_identity.py", source))
        self.assertGreaterEqual(len(captured), 2)
        self.assertTrue(all(i.s == "" for i in captured))


if __name__ == "__main__":
    unittest.main()
