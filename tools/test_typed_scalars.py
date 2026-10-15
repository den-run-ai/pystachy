"""Machine scalar IR keeps arithmetic, casts, flags and predicates structured."""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import ast
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import Ins, Val, Values
from src.pystachy_compiler.scalar_ir import SCALAR_CASTS, SCALAR_FCMP, SCALAR_ICMP


class TypedScalarTests(unittest.TestCase):
    def finish(self, g):
        g.add(Ins("ret.none", "", ""))
        g.fn.n = g.n
        g.verify(g.fn, False)
        for i in g.fn.blocks[0].code[:-1]:
            self.assertEqual(g.opfx(i, {}), 0)
            self.assertEqual(g.nums(i), 1)
            g.lower_ins(g.fn, i)
        return g.out

    def bad(self, build, field, value):
        g = Gen()
        build(g)
        setattr(g.fn.blocks[0].code[-1], field, value)
        g.add(Ins("ret.none", "", ""))
        g.fn.n = g.n
        error = StringIO()
        with redirect_stderr(error), self.assertRaises(SystemExit):
            g.verify(g.fn, False)
        self.assertIn("bad IR", error.getvalue())

    def test_arithmetic_bitwise_and_overflow_flags_lower_exactly(self):
        for op in ("add", "sub", "mul", "udiv", "urem", "shl", "lshr", "ashr", "and", "or", "xor"):
            for t, llvm in (("int", "i64"), ("bool", "i1"), ("%byte", "i8"), ("%i32", "i32")):
                g = Gen()
                g.scalar(op, [Val("%a0", t), Val("1", t)])
                self.assertEqual(self.finish(g), [f"  %t1 = {op} {llvm} %a0, 1"])
        for flags in ("nsw", "nuw", "nuw nsw"):
            g = Gen()
            g.scalar("add", [Val("%a0", "int"), Val("1", "int")], flags)
            self.assertEqual(self.finish(g), [f"  %t1 = add {flags} i64 %a0, 1"])
        for op in ("fadd", "fsub", "fmul", "fdiv", "fneg"):
            g = Gen()
            g.scalar(op, [Val("%a0", "float")] + ([] if op == "fneg" else [Val("0.0", "float")]))
            self.assertEqual(self.finish(g), [f"  %t1 = {op} double %a0" + ("" if op == "fneg" else ", 0.0")])

    def test_cast_and_comparison_lowering_is_finite_and_typed(self):
        ll = {"int": "i64", "bool": "i1", "%byte": "i8", "%i32": "i32", "float": "double", "%ptr": "ptr"}
        for signature in SCALAR_CASTS:
            op, source, target = signature.split(":")
            g = Gen()
            g.scalar_cast(op, Val("%a0", source), target)
            self.assertEqual(self.finish(g), [f"  %t1 = {op} {ll[source]} %a0 to {ll[target]}"])
        for t, preds in (("int", SCALAR_ICMP), ("%i32", SCALAR_ICMP), ("bool", SCALAR_ICMP), ("float", SCALAR_FCMP), ("%ptr", ["eq", "ne"])):
            for pred in preds:
                g = Gen()
                g.scalar_cmp(pred, Val("%a0", t), Val("%a1", t))
                self.assertEqual(self.finish(g), [f"  %t1 = {'fcmp' if t == 'float' else 'icmp'} {pred} {ll[t]} %a0, %a1"])

    def test_verifier_rejects_mismatches_unknown_operators_and_extra_metadata(self):
        def binary(g):
            return g.scalar("add", [Val("%a0", "int"), Val("1", "int")])
        def cast(g):
            return g.scalar_cast("trunc", Val("%a0", "int"), "%byte")
        def cmp(g):
            return g.scalar_cmp("eq", Val("%a0", "%ptr"), Val("null", "%ptr"))
        for build in (binary, cast, cmp):
            for field, value in (("a", []), ("r", []), ("r", [1, 2]), ("k", 1), ("b", ["entry"]), ("s", "bogus"), ("x", "arbitrary LLVM")):
                with self.subTest(build=build, field=field):
                    self.bad(build, field, value)
        for field, value in (("a", [Val("0", "float"), Val("1", "float")]), ("a", [Val("0", "int"), Val("1", "bool")]), ("x", "fast"), ("t", "float")):
            self.bad(binary, field, value)
        self.bad(cast, "t", "float")
        self.bad(cmp, "s", "slt")

    def test_canonical_values_keep_types_flags_predicates_and_operand_order(self):
        g = Gen()
        a, b = Val("%a0", "int"), Val("%a1", "int")
        first = g.scalar("add", [a, b])
        same = g.scalar("add", [a, b])
        others = [g.scalar("add", [b, a]), g.scalar("add", [a, b], "nsw"), g.scalar("sub", [a, b])]
        g.fn.n = g.n
        vs = Values(g.fn, {"entry": []})
        self.assertEqual(g.canon(vs, first), g.canon(vs, same))
        for value in others:
            self.assertNotEqual(g.canon(vs, first), g.canon(vs, value))

    def test_select_verifier_checks_condition_values_and_metadata(self):
        def build(g):
            return g.select("%c", Val("%a0", "int"), Val("%a1", "int"))
        for field, value in (("a", []), ("a", [Val("0", "int"), Val("0", "int"), Val("1", "int")]), ("a", [Val("true", "bool"), Val("0", "int"), Val("1", "bool")]), ("t", "float"), ("s", "text"), ("x", "fast")):
            self.bad(build, field, value)

    def test_producers_do_not_encode_scalar_llvm_in_raw_instructions(self):
        for path in (Path(__file__).resolve().parent.parent / "src" / "pystachy_compiler").glob("*.py"):
            tree = ast.parse(path.read_text())
            for n in ast.walk(tree):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "ins" and n.args and isinstance(n.args[0], ast.JoinedStr):
                    text = "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in n.args[0].values)
                    self.assertTrue(text.startswith(("load ", "getelementptr ")), f"{path}:{n.lineno}: {text}")


if __name__ == "__main__":
    unittest.main()
