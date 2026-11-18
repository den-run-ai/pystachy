"""Fresh variable tuples keep evaluated elements until final allocation."""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import FnInfo, IFn, Ins, Val
from src.pystachy_compiler.loader import Loader
from src.pystachy_compiler.specs import FXBIT
from src.pystachy_compiler.syntax import Node


def compile_source(source):
    captured = {}
    lower = Gen.lower

    def capture(g, fn):
        g.verify(fn, False)
        captured[fn.f.name] = [i for b in fn.blocks for i in b.code]
        lower(g, fn)

    with patch.object(Gen, "lower", capture):
        ir = Gen().program(Loader([]).program("vtuple.py", source))
    return captured, ir


def make_tuple(t="vtuple[float]", values=None):
    i = Ins("vtuple.make", t, "")
    i.r = [1]
    i.a = [Val("%a0", "float"), Val("%a1", "float")] if values is None else values
    return i


def function_with(i):
    fn = IFn(FnInfo("tuples", "@tuples", Node("def", "tuples", 1), ""))
    fn.n = 3
    fn.blocks[0].code = [i, Ins("ret.none", "", "")]
    return fn


class VariableTupleMaterializationTests(unittest.TestCase):
    def assert_final_only(self, code):
        self.assertEqual(sum(i.op == "alloc.fixed" for i in code), 0)
        self.assertEqual(sum(i.op == "vtuple.make" for i in code), 1)
        self.assertFalse(any(i.op == "rt" and i.s == "vtuple.from" for i in code))
        return next(i for i in code if i.op == "vtuple.make")

    def test_contextual_display_allocates_only_final_tuple(self):
        captured, _ = compile_source("""
def pair(x: float) -> tuple[float, ...]:
    return (x, x + 1.0)
print(pair(2.0))
""")
        made = self.assert_final_only(captured["pair"])
        self.assertEqual(made.t, "vtuple[float]")
        self.assertEqual([a.t for a in made.a], ["float", "float"])

    def test_assignment_and_derivative_arguments_keep_only_final_representation(self):
        captured, _ = compile_source("""
class Derivatives:
    def __init__(self, values: tuple[float, ...]) -> None:
        self.values = values

def assigned(x: float):
    values: tuple[float, ...] = (x, -x)
    return values

def gradients(x: float, y: float) -> Derivatives:
    return Derivatives((y, x))

print(assigned(2.0), gradients(2.0, 3.0).values)
""")
        self.assert_final_only(captured["assigned"])
        code = captured["gradients"]
        self.assertEqual(sum(i.op == "alloc.fixed" and i.t.startswith("tuple[") for i in code), 0)
        self.assertEqual(sum(i.op == "vtuple.make" for i in code), 1)
        self.assertTrue(any(i.op == "alloc.fixed" and i.t == "Derivatives" for i in code))

    def test_existing_fixed_source_is_read_without_a_copy_container(self):
        captured, _ = compile_source("""
def copied(values: tuple[float, float]) -> tuple[float, ...]:
    return values
print(copied((2.0, 3.0)))
""")
        code = captured["copied"]
        self.assert_final_only(code)
        self.assertEqual(sum(i.op == "tuple.load" for i in code), 2)
        self.assertFalse(any(i.op == "tuple.store" for i in code))

    def test_literal_constant_displays_keep_the_existing_constant_path(self):
        captured, ir = compile_source("""
def constant():
    return (1.5, "same")
def converted() -> tuple[float, ...]:
    return (1.5, 2.5)
print(constant() is constant(), converted())
""")
        self.assertFalse(any(i.op in ("alloc.fixed", "vtuple.make") for i in captured["constant"]))
        self.assertTrue(any(i.op == "ret" and i.a[0].v.startswith("@") for i in captured["constant"]))
        self.assert_final_only(captured["converted"])
        self.assertIn("private constant", ir)

    def test_promoting_values_are_boxed_before_dynamic_tuple_construction(self):
        captured, _ = compile_source("""# pystachy: python-int
# pystachy: dynamic-any
from typing import Any

def huge(x: int) -> tuple[Any, ...]:
    return (x, x * x)
def copied(values: tuple[int, int]) -> tuple[Any, ...]:
    return values
print(huge(2 ** 80), copied((2 ** 80, 7)))
""")
        for name in ("huge", "copied"):
            with self.subTest(name=name):
                made = self.assert_final_only(captured[name])
                self.assertEqual(made.t, "vtuple[dyn]")
                self.assertEqual([a.t for a in made.a], ["dyn", "dyn"])
                self.assertFalse(any(i.op == "rt" and i.s == "big.narrow" for i in captured[name]))

    def test_all_items_run_before_checked_promoting_int_conversion(self):
        captured, _ = compile_source("""# pystachy: python-int
calls: list[str] = []
def mark(name: str, n: int) -> int:
    calls.append(name)
    return n
def pair(n: int) -> tuple[int, ...]:
    return (mark("first", n), mark("second", n))
print(pair(4))
""")
        code = captured["pair"]
        calls = [j for j, i in enumerate(code) if i.op == "call" and i.s == "@f.mark"]
        conversions = [j for j, i in enumerate(code) if i.op == "check" and i.s.startswith("OverflowError:")]
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(conversions), 2)
        self.assertLess(max(calls), min(conversions))
        self.assertLess(max(conversions), next(j for j, i in enumerate(code) if i.op == "vtuple.make"))

    def test_operand_hints_preserve_widening_and_comparison_types(self):
        captured, _ = compile_source("""# pystachy: dynamic-any
from typing import Any
class Leaf:
    def __eq__(self, other: Any) -> bool:
        return True

def concat(values: tuple[int, ...], item: int | None):
    return values + (item,)
def compare(values: tuple[str, ...]) -> bool:
    return values == (Leaf(), Leaf())
print(concat((1, 2), None), compare(("a", "b")))
""")
        made = [i for i in captured["concat"] if i.op == "vtuple.make"]
        self.assertEqual([i.t for i in made], ["vtuple[opt[int]]"])
        self.assertTrue(any(i.op == "alloc.fixed" and i.t == "tuple[Leaf,Leaf]"
                            for i in captured["compare"]))

    def test_numeric_companions_follow_scope_and_scalar_reads(self):
        source = """
def make(x: float) -> tuple[float, ...]:
    return (x, x + 1.0)
def scalar(values: tuple[float, ...]) -> float:
    return values[0] + values[1]
def expose(values: tuple[float, ...]) -> float:
    return values[0]
def iterate(values: tuple[float, ...]) -> float:
    total = 0.0
    for item in values:
        total += item
    return total
print(scalar(make(2.0)), expose(make(3.0)), iterate(make(4.0)))
"""
        plain, _ = compile_source(source)
        tracked, _ = compile_source("# pystachy: dynamic-any\n" + source)
        for code in plain.values():
            self.assertFalse(any(i.op == "rt" and i.s.endswith("_identity") for i in code))
        calls = [i.s for i in tracked["make"] if i.op == "rt"]
        self.assertEqual(calls.count("vtuple.set_identity"), 2)
        self.assertFalse(any(i.op == "rt" and i.s == "vtuple.get_identity" for i in tracked["scalar"]))
        self.assertTrue(any(i.op == "rt" and i.s == "vtuple.get_identity" for i in tracked["expose"]))
        # Bounds are already established by the immutable tuple iteration loop.
        # Ordinary typed iteration must stay an inline load, without a runtime
        # getter or an identity allocation; tracked items keep their boxes.
        self.assertFalse(any(i.op == "rt" and i.s.startswith("vtuple.get") for i in plain["iterate"]))
        self.assertTrue(any(i.op == "rt" and i.s == "vtuple.get_identity" for i in tracked["iterate"]))

    def test_reference_and_untracked_optional_iteration_keeps_inline_loads(self):
        for et, value in (("str", '("a", "b")'), ("bool", "(True, False)"),
                          ("float | None", "(1.5, None)"), ("str | None", '("a", None)')):
            for prefix in ("", "# pystachy: dynamic-any\n"):
                with self.subTest(element=et, tracked=bool(prefix)):
                    captured, _ = compile_source(prefix + f"""
def copied(values: tuple[{et}, ...]) -> list[{et}]:
    return [item for item in values]
print(copied({value}))
""")
                    tracks_optional = et == "float | None" and bool(prefix)
                    self.assertEqual(any(i.op == "rt" and i.s == "vtuple.get_identity" for i in captured["copied"]), tracks_optional)
                    if not tracks_optional:
                        self.assertFalse(any(i.op == "rt" and i.s.startswith("vtuple.get") for i in captured["copied"]))

    def test_native_operands_have_one_result_and_allocation_effect(self):
        g = Gen()
        g.runtime("pys_alloc")
        for t in ("int", "float", "bool", "str", "dyn", "opt[int]", "opt[float]", "opt[bool]", "opt[str]", "opt[dyn]"):
            with self.subTest(element=t):
                i = make_tuple(f"vtuple[{t}]", [Val("%a0", t)])
                g.verify(function_with(i), False)
                self.assertEqual(g.nums(i), 1)
                self.assertEqual(g.opfx(i, {}), FXBIT["A"])
        g.verify(function_with(make_tuple(values=[])), False)

    def assert_rejected(self, i, declared=True):
        g = Gen()
        if declared:
            g.runtime("pys_alloc")
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as raised:
            g.verify(function_with(i), False)
        self.assertEqual(raised.exception.code, 1)

    def test_verifier_rejects_erased_mismatched_and_non_slot_representations(self):
        for t in ("", "float", "tuple[float]", "opt[vtuple[float]]", "vtuple[]", "vtuple[float,float]",
                  "vtuple[float", "vtuple[float]]", "vtuple[float][str]", "vtuple[float]][[str]",
                  "vtuple[T]", "vtuple[%slot]", "vtuple[*float]", "vtuple[int+]", "vtuple[list[int]]"):
            with self.subTest(type=t):
                self.assert_rejected(make_tuple(t, []))
        self.assert_rejected(make_tuple(values=[Val("%a0", "int")]))
        self.assert_rejected(make_tuple(), declared=False)
        for field, value in (("s", "copy"), ("x", "float"), ("k", 1), ("b", ["entry"]), ("r", []), ("r", [1, 2])):
            with self.subTest(field=field):
                i = make_tuple()
                setattr(i, field, value)
                self.assert_rejected(i)

    def test_bool_and_address_scratch_values_belong_only_to_llvm_lowering(self):
        g = Gen()
        i = make_tuple("vtuple[bool]", [Val("%a0", "bool"), Val("%a1", "bool")])
        g.lower_ins(function_with(i), i)
        self.assertEqual(g.out, [
            "  %t1 = call ptr @pys_alloc(i64 32)",
            "  store i64 2, ptr %t1",
            "  %vt.1.0 = getelementptr i64, ptr %t1, i64 2",
            "  %vt.1.0.value = zext i1 %a0 to i64",
            "  store i64 %vt.1.0.value, ptr %vt.1.0",
            "  %vt.1.1 = getelementptr i64, ptr %t1, i64 3",
            "  %vt.1.1.value = zext i1 %a1 to i64",
            "  store i64 %vt.1.1.value, ptr %vt.1.1",
        ])
        self.assertEqual(i.r, [1])

    def test_reference_values_remain_native_and_live_across_scanned_allocation(self):
        g = Gen()
        i = make_tuple("vtuple[str]", [Val("%a0", "str"), Val("%a1", "str")])
        g.lower_ins(function_with(i), i)
        self.assertEqual(g.out[0], "  %t1 = call ptr @pys_alloc(i64 32)")
        self.assertIn("  store ptr %a0, ptr %vt.1.0", g.out)
        self.assertIn("  store ptr %a1, ptr %vt.1.1", g.out)
        self.assertEqual([a.t for a in i.a], ["str", "str"])

    def test_builder_retains_runtime_self_recursion_guard(self):
        g = Gen()
        g.rtmode = True
        g.curfn.ll = "@pys_alloc"
        error = StringIO()
        with redirect_stderr(error), self.assertRaises(SystemExit):
            g.vtuple_make([Val("0", "int")], "vtuple[int]")
        self.assertIn("pys_alloc() implements an operation that it uses", error.getvalue())
        self.assertEqual(g.fn.blocks[0].code, [])


if __name__ == "__main__":
    unittest.main()
