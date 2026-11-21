"""An operand's value is one of a closed set of spellings.

Run with python3 -m unittest discover -s tools -p test_typed_operands.py.
"""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler import ir
from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import IFn, Ins, Val, operand_kind, slot_register, tmpname
from src.pystachy_compiler.loader import Loader
from src.pystachy_compiler.symbols import FnInfo
from src.pystachy_compiler.syntax import Node
from src.pystachy_compiler.utils import fbits, fconst

ROOT = Path(__file__).resolve().parent.parent
KINDS = {
    "value": ["%t0", "%t7", "%t123456"],
    "param": ["%a0", "%a12", "%aid3", "%idret"],
    "slot": ["%samples.2", "%x.def.9", "%stk.4", "%h.5", "%t5.12", "%a.7", "%aid.3", "%name.with.dots.1"],
    "global": ["@s.1", "@f.main", "@tc.0", "@dt.collections$Counter-1", "@g.mods$sentinels$MISSING-0.def", "@pys_dyn_none_box"],
    "const": ["0", "7", "-1", "-9223372036854775808", "0.0", "0.5", "-1.5e+20", "1.0e-05", "5.0e22", "true", "false", "null", "undef"],
    "expr": ["bitcast (i64 9218868437227405312 to double)", "bitcast (i64 -4503599627370496 to double)",
             "ptrtoint (ptr @s.5 to i64)", "ptrtoint (ptr getelementptr (i8, ptr @s.5, i64 2) to i64)"],
}
INFINITY = """def above(x: float) -> bool:
    return x < 1e999


print(above(2.0))
"""
REJECTED = [
    "", "%", "%t", "%t1x", "%a", "%aid", "%x", "%x.", "%.5", "%rd", "%coro.promise", "@", "@a b", '@"quoted"', "@s.1, i64 2",
    "1.", ".5", "1.5e", "1.5e+", "1e5", "-", "--1", "+1", "0x10", "inf", "nan", "zeroinitializer", "poison", "none", "True",
    "bitcast (i64 1 to float)", "bitcast (i64 x to double)", "bitcast (i64 1 to double) ", "ptrtoint (ptr %t1 to i64)",
    "ptrtoint (ptr @s.5 to i32)", "ptrtoint (ptr getelementptr (i8, ptr @s.5, i64 2) to i64",
    "ptrtoint (ptr getelementptr (i64, ptr @s.5, i64 2) to i64)", "inttoptr (i64 5 to ptr)", "add (i64 1, i64 2)",
    "%t1 = add i64 1, 2", "1, i64 2", "%t1, %t2", "%t1 ", " %t1", "%t1\n",
]


class OperandKindTests(unittest.TestCase):
    def test_block_labels_share_common_spellings_and_bound_retention(self):
        for number in (1, 63, 2047):
            self.assertEqual(ir.block_label(number), f"L{number}")
            self.assertIs(ir.block_label(number), ir.block_label(number))
        for number in (-1, 2048, 10**9):
            self.assertEqual(ir.block_label(number), f"L{number}")
            self.assertNotIn(number, ir.BLOCK_LABELS)

    def test_each_kind_has_its_spellings_and_no_other(self):
        self.assertEqual(ir.OPERAND_KINDS, list(KINDS))
        for kind, spellings in KINDS.items():
            for v in spellings:
                with self.subTest(value=v):
                    self.assertEqual(ir.OPERAND_KINDS[operand_kind(v)], kind)
        for v in REJECTED:
            with self.subTest(value=v):
                self.assertEqual(operand_kind(v), -1)

    def test_compiler_names_are_of_their_kinds(self):
        for n in (0, 1, 99):
            self.assertEqual(operand_kind(tmpname(n)), ir.OPERAND_VALUE)
        for name, k in (("x", 0), ("x", 1), ("", 0), ("t5", 0), ("stack", 2)):
            slot = Ins("slot", "int", name)
            slot.k = k
            slot.r = [7]
            self.assertEqual(operand_kind(slot_register(slot)), ir.OPERAND_SLOT, slot_register(slot))
        for text in ("0.0", "1.5", "1e300", "inf", "-inf", "nan", "5e-324", "-0.0", "1e22", "123456789012345680000.0"):
            spelling = fbits(text)
            self.assertTrue(fconst(spelling))
            self.assertEqual(operand_kind(spelling), ir.OPERAND_CONST if float(text) - float(text) == 0.0 else ir.OPERAND_EXPR,
                             (text, spelling))

    def test_verifier_rejects_instruction_text_in_an_operand(self):
        for value in ("%t1 = add i64 1, 2", "add (i64 1, i64 2)", "%rd", "zeroinitializer", ""):
            with self.subTest(value=value):
                fn = IFn(FnInfo("operand", "@operand", Node("def", "operand", 1), ""))
                fn.n = 2
                i = Ins("num.cmp", "bool", "==")
                i.a = [Val("%a0", "int"), Val(value, "int")]
                i.r = [1]
                fn.blocks[0].code = [i, Ins("ret.none", "", "")]
                errors = StringIO()
                with redirect_stderr(errors), self.assertRaises(SystemExit):
                    Gen().verify(fn, False)
                self.assertIn(f"num.cmp operand {value} is no value, parameter, slot, symbol or constant", errors.getvalue())
                i.a[1] = Val("7", "int")
                Gen().verify(fn, False)

    def test_compiled_programs_use_every_kind(self):
        seen = set()
        verify = Gen.verify

        def capture(g, fn, eh):
            for block in fn.blocks:
                for i in block.code:
                    for a in i.a:
                        kind = operand_kind(a.v)
                        self.assertGreaterEqual(kind, 0, (fn.f.ll, i.op, a.v))
                        seen.add(ir.OPERAND_KINDS[kind])
            verify(g, fn, eh)

        with patch.object(Gen, "verify", capture), patch.dict("os.environ", {"PYSTACHY_IRCHECK": "1"}):
            for case in ("typed_ir_slots.py", "typed_ir_numeric.py", "tuples_and_classes.py"):
                path = next((ROOT / "tests").glob(f"programs/*/{case}"))
                Gen().program(Loader([]).program(str(path), path.read_text()))
            # (an infinity has no decimal spelling: its operand is a constant expression of its bits)
            Gen().program(Loader([]).program("infinity.py", INFINITY))
        self.assertEqual(seen, set(KINDS))


if __name__ == "__main__":
    unittest.main()
