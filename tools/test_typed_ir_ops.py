"""The operation table is the one definition of an instruction's shape.

Run with python3 -m unittest discover -s tools -p test_typed_ir_ops.py.
"""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import typed_ir_ops
from src.pystachy_compiler import specs
from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import Blk, IFn, Ins, Val
from src.pystachy_compiler.ircheck import op_shape_error
from src.pystachy_compiler.symbols import FnInfo
from src.pystachy_compiler.syntax import Node


def ins(op, t="", s="", operands=0, labels=0, k=0, x=""):
    i = Ins(op, t, s)
    i.a = [Val("%a0", "int") for _ in range(operands)]
    i.b = ["next" for _ in range(labels)]
    i.k = k
    i.x = x
    return i


def function(code):
    fn = IFn(FnInfo("shape", "@shape", Node("def", "shape", 1), ""))
    fn.n = 8
    fn.blocks[0].code = code
    fn.blocks.append(Blk("next"))
    fn.blocks[1].code = [Ins("ret.none", "", "")]
    return fn


class OperationTableTests(unittest.TestCase):
    def test_rows_are_well_formed_and_cover_the_registry(self):
        rows = typed_ir_ops.rows()
        self.assertEqual([row["name"] for row in rows], list(specs.IROPS))
        self.assertEqual(len({row["name"] for row in rows}), len(rows))
        self.assertEqual([row["name"] for row in rows if row["entry"]], ["slot"])

    def test_derived_views_agree_with_the_rows(self):
        for row in typed_ir_ops.rows():
            op = row["name"]
            with self.subTest(op=op):
                effects = specs.IROPS[op].split()
                self.assertEqual("T" in effects, row["terminator"])
                self.assertEqual("*" in effects, row["varies"])
                self.assertEqual([e for e in effects if e not in ("T", "*")], row["effects"])
                self.assertEqual(specs.RESULT_NUMBERS.get(op, 0), row["results"] or 0)
                self.assertEqual(specs.VALUE_AT.get(op, 0), row["value"])
                self.assertEqual(specs.OP_ENTRY[op], row["entry"])
                self.assertEqual(specs.OP_MIN[op], row["min"])
                self.assertEqual(specs.OP_MAX[op], -1 if row["max"] is None else row["max"])
                self.assertEqual(specs.OP_LABELS[op], {"a": specs.OP_PER_OPERAND, "i": specs.OP_INVOKE}.get(row["labels"]) or int(row["labels"]))
                self.assertEqual(specs.OP_FIELDS[op], sum(typed_ir_ops.FIELD_BITS[f] for f in row["fields"]))

    def test_malformed_rows_are_rejected(self):
        for text in ("T|0|0|1|", "Q|0|0|0||0", "T T|0|0|0||0", "|1-0|0|0||0", "|01|0|0||0", "|0|-1|0||0",
                     "|0|0|b||0", "|0|0|0|s t|0", "|0|0|0|t t|0", "|0|1|0||2", "|0|0|0||4", "E T|0|1|0||0",
                     "E|0|1|1||0"):
            with self.subTest(text=text), patch.dict(typed_ir_ops.OPS, {"probe": text}, clear=True):
                with self.assertRaises(ValueError):
                    typed_ir_ops.rows()

    def test_documentation_reference_is_current(self):
        text = typed_ir_ops.DOC.read_text(encoding="utf-8")
        self.assertEqual(typed_ir_ops.current(text), typed_ir_ops.reference())
        self.assertEqual(text.count(typed_ir_ops.BEGIN), 1)
        self.assertIsNone(typed_ir_ops.current(text.replace(typed_ir_ops.END, "")))

    def test_schema_matches_the_lean_checker_fields(self):
        for row, spec in zip(typed_ir_ops.rows(), typed_ir_ops.schema(), strict=True):
            self.assertEqual(set(spec), {"terminator", "entry", "min", "max", "results", "labels", "fields"})
            self.assertEqual(spec["labels"][0], {"a": 2, "i": 1}.get(row["labels"], 0))


class ShapeCheckTests(unittest.TestCase):
    def test_each_count_and_field_of_a_row_is_enforced(self):
        self.assertEqual(op_shape_error(ins("br", labels=1), False), "")
        self.assertEqual(op_shape_error(ins("slot", "int", "x", k=1), True), "")
        for i, entry, expected in (
                (ins("br"), False, "br with 0 labels, where the operation table has 1"),
                (ins("br", labels=2), False, "br with 2 labels, where the operation table has 1"),
                (ins("br", operands=1, labels=1), False, "br with 1 operands, where the operation table has 0"),
                (ins("cbr", operands=1, labels=1), False, "cbr with 1 labels, where the operation table has 2"),
                (ins("phi", "int", operands=2, labels=1), False, "phi with 1 labels, where the operation table has a"),
                (ins("switch", operands=1, labels=1), False, "switch with 1 operands, where the operation table has 2+"),
                (ins("rt", "int", "list.len", operands=1, labels=1), False, "rt with 1 labels, where the operation table has i"),
                (ins("ret", operands=2), False, "ret with 2 operands, where the operation table has 0-1"),
                (ins("br", s="text", labels=1), False, "br sets a field outside the operation table's none"),
                (ins("br", "int", labels=1), False, "br sets a field outside the operation table's none"),
                (ins("throw", operands=1, k=1), False, "throw sets a field outside the operation table's none"),
                (ins("icall", "int", operands=1, x="inline"), False, "icall sets a field outside the operation table's t"),
                (ins("slot", "int", "x"), False, "slot in a block, where entry storage belongs among the slots"),
                (ins("br", labels=1), True, "br among the slots")):
            with self.subTest(op=i.op, expected=expected):
                self.assertEqual(op_shape_error(i, entry), expected)

    def test_an_invoke_keeps_its_two_labels(self):
        for op in ("rt", "call", "icall", "init", "gen.resume"):
            with self.subTest(op=op):
                self.assertEqual(specs.OP_LABELS[op], specs.OP_INVOKE)
                operands = max(specs.OP_MIN[op], 1 if op != "init" else 0)
                self.assertEqual(op_shape_error(ins(op, operands=operands, labels=2), False), "")
                self.assertEqual(op_shape_error(ins(op, operands=operands), False), "")

    def test_verifier_reports_a_shape_no_specific_check_names(self):
        for code, expected in (([ins("cbr", operands=1, labels=1)], "cbr with 1 labels"),
                               ([ins("slot", "int", "x"), ins("br", labels=1)], "slot in a block"),
                               ([ins("throw", operands=2)], "throw with 2 operands")):
            with self.subTest(expected=expected):
                for i in code:
                    for a in i.a:
                        a.t = "bool"
                errors = StringIO()
                with redirect_stderr(errors), self.assertRaises(SystemExit):
                    Gen().verify(function(code), False)
                self.assertIn(expected, errors.getvalue())

    def test_verifier_holds_slots_to_the_table(self):
        fn = function([ins("br", labels=1)])
        slot = ins("slot", "int", "x", x="descriptor")
        slot.r = [1]
        fn.slots = [slot]
        errors = StringIO()
        with redirect_stderr(errors), self.assertRaises(SystemExit):
            Gen().verify(fn, False)
        self.assertIn("slot sets a field outside the operation table's t s k", errors.getvalue())
        slot.x = ""
        Gen().verify(fn, False)


if __name__ == "__main__":
    unittest.main()
