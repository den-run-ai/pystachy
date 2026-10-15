"""Control, tag and bounds comparisons keep signedness in typed IR."""
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
from src.pystachy_compiler.syntax import Node


def function_with(i):
    fn = IFn(FnInfo("compare", "@compare", Node("def", "compare", 1), ""))
    fn.n = 2
    fn.blocks[0].code = [i, Ins("ret.none", "", "")]
    return fn


def unsigned(predicate="<"):
    i = Ins("int.ucmp", "bool", predicate)
    i.a = [Val("%a0", "int"), Val("%a1", "int")]
    i.r = [1]
    return i

def reference(predicate="==", left="opt[str]", right="None"):
    i = Ins("ptr.cmp", "bool", predicate)
    i.a = [Val("%a0", left), Val("null" if right == "None" else "%a1", right)]
    i.r = [1]
    return i


class TypedComparisonTests(unittest.TestCase):
    def assert_bad(self, i):
        error = StringIO()
        with redirect_stderr(error), self.assertRaises(SystemExit):
            Gen().verify(function_with(i), False)
        self.assertIn("bad IR", error.getvalue())
        self.assertIn(i.op, error.getvalue())

    def test_reference_identity_and_null_comparisons_are_typed_and_pure(self):
        for t in ("str", "bytes", "file", "exc", "list[int]", "dict[str,float]",
                  "tuple[int,str]", "union[int,str]", "opt[int]", "opt[float]",
                  "opt[bool]", "opt[union[int,str]]", "fn[c:0:f]", "Box", "None"):
            for predicate in ("==", "!="):
                with self.subTest(type=t, predicate=predicate):
                    g = Gen()
                    g.classes["Box"] = ClassInfo("Box", Node("class", "Box", 1))
                    i = reference(predicate, t)
                    g.verify(function_with(i), False)
                    self.assertEqual(g.nums(i), 1)
                    self.assertEqual(g.opfx(i, {}), 0)
                    g.lower_ins(function_with(i), i)
                    llvm = "eq" if predicate == "==" else "ne"
                    self.assertEqual(g.out, [f"  %t1 = icmp {llvm} ptr %a0, null"])

    def test_reference_comparisons_reject_nonreferences_ordering_and_metadata(self):
        for t in ("", "int", "float", "bool", "%slot", "%ptr", "*str", "#", "T", "K", "V", "S"):
            for index in (0, 1):
                with self.subTest(type=t, index=index):
                    i = reference()
                    i.a[index].t = t
                    self.assert_bad(i)
        for predicate in ("", "<", "<=", ">", ">=", "is", "eq"):
            self.assert_bad(reference(predicate))
        for field, value in (("a", []), ("a", [Val("null", "None")]),
                             ("a", [Val("null", "None")] * 3), ("t", "int"),
                             ("r", []), ("r", [1, 2]), ("x", "ptr"),
                             ("k", 1), ("b", ["entry"])):
            with self.subTest(field=field, value=value):
                i = reference()
                setattr(i, field, value)
                self.assert_bad(i)

    def test_repeated_reference_comparisons_keep_operand_and_predicate_identity(self):
        g = Gen()
        a, b = Val("%a0", "list[int]"), Val("%a1", "list[int]")
        first = g.ptr_cmp("==", a, b)
        same = g.ptr_cmp("==", a, b)
        other = g.ptr_cmp("!=", a, b)
        null = g.ptr_cmp("==", a, Val("null", "None"))
        g.fn.n = g.n
        vs = Values(g.fn, {"entry": []})
        self.assertEqual(g.canon(vs, same.v), g.canon(vs, first.v))
        for value in (other, null):
            self.assertNotEqual(g.canon(vs, value.v), g.canon(vs, first.v))

    def test_unsigned_predicates_are_pure_and_lower_without_changing_bits(self):
        for predicate, llvm in (("<", "ult"), ("<=", "ule"), (">", "ugt"), (">=", "uge")):
            with self.subTest(predicate=predicate):
                i = unsigned(predicate)
                i.a = [Val("-1", "int"), Val("9223372036854775807", "int")]
                g = Gen()
                g.verify(function_with(i), False)
                self.assertEqual(g.nums(i), 1)
                self.assertEqual(g.opfx(i, {}), 0)
                g.lower_ins(function_with(i), i)
                self.assertEqual(g.out, [f"  %t1 = icmp {llvm} i64 -1, 9223372036854775807"])

    def test_unsigned_verifier_rejects_other_types_shapes_and_predicates(self):
        for predicate in ("", "==", "!=", "ult", "is", "<= "):
            with self.subTest(predicate=predicate):
                self.assert_bad(unsigned(predicate))
        for index in (0, 1):
            for t in ("", "bool", "float", "str", "opt[int]", "%slot", "union[int,float]"):
                with self.subTest(index=index, type=t):
                    i = unsigned()
                    i.a[index].t = t
                    self.assert_bad(i)
        for field, value in (("a", []), ("a", [Val("0", "int")]),
                             ("a", [Val("0", "int")] * 3), ("t", "int"),
                             ("r", []), ("r", [1, 2]), ("x", "int"),
                             ("k", 1), ("b", ["entry"])):
            with self.subTest(field=field, value=value):
                i = unsigned()
                setattr(i, field, value)
                self.assert_bad(i)

    def test_canonical_comparisons_retain_signedness_and_predicate(self):
        g = Gen()
        a, b = Val("%a0", "int"), Val("%a1", "int")
        first = g.int_ucmp("<", a, b)
        same = g.int_ucmp("<", a, b)
        signed = g.num_cmp("<", a, b)
        other = g.int_ucmp("<=", a, b)
        swapped = g.int_ucmp("<", b, a)
        g.fn.n = g.n
        vs = Values(g.fn, {"entry": []})
        self.assertEqual(g.canon(vs, same.v), g.canon(vs, first.v))
        for value in (signed, other, swapped):
            self.assertNotEqual(g.canon(vs, value.v), g.canon(vs, first.v))

    def test_typed_membership_conditions_preserve_dictfuse_and_mutation_barriers(self):
        source = '''
def positive(d: dict[str, int], k: str) -> int:
    if k in d:
        return d[k]
    return -1

def negative(d: dict[str, int], k: str) -> int:
    if k not in d:
        return -1
    return d[k]

def negated(d: dict[str, int], k: str) -> int:
    if not k in d:
        return -1
    return d[k]

def changed(d: dict[str, int], k: str) -> int:
    if k in d:
        d.clear()
        return d[k]
    return -1
'''
        captured = {}
        lower = Gen.lower

        def capture(g, fn):
            g.verify(fn, False)
            captured[fn.f.name] = [i for b in fn.blocks for i in b.code]
            lower(g, fn)

        with patch.object(Gen, "lower", capture):
            Gen().program(Loader([]).program("typed_compare.py", source))
        for name in ("positive", "negative", "negated"):
            with self.subTest(name=name):
                ops = captured[name]
                calls = [i.s for i in ops if i.op == "rt"]
                self.assertIn("dict.find", calls)
                self.assertIn("dict.val", calls)
                self.assertNotIn("dict.has", calls)
                self.assertTrue(any(i.op == "num.cmp" and i.a[1].v == "0" for i in ops))
        calls = [i.s for i in captured["changed"] if i.op == "rt"]
        self.assertIn("dict.has", calls)
        self.assertIn("dict.getitem", calls)
        self.assertNotIn("dict.find", calls)

    def test_source_loops_tag_checks_and_mixed_nan_comparisons_are_typed(self):
        root = Path(__file__).resolve().parent.parent
        lower = Gen.lower
        captured = []

        def capture(g, fn):
            g.verify(fn, False)
            captured.extend(i for b in fn.blocks for i in b.code)
            lower(g, fn)

        with patch.object(Gen, "lower", capture):
            for name in ("typed_ir_numeric.py", "scalar_union_optional_narrowing.py", "opt_dictfuse.py"):
                Gen().program(Loader([str(root / "lib")]).program(name, (root / "tests" / name).read_text()))
        self.assertTrue(any(i.op == "int.ucmp" for i in captured))
        self.assertTrue(any(i.op == "num.cmp" for i in captured))
        self.assertFalse(any(i.op == "raw" and "icmp " in i.s and " i64 " in i.s for i in captured))


if __name__ == "__main__":
    unittest.main()
