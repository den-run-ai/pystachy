"""A runtime call's types are an instance of its RUNTIME signature (docs/typed-ir.md#runtime-calls)."""
from contextlib import redirect_stderr
from copy import deepcopy
from io import StringIO
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import Val
from src.pystachy_compiler.loader import Loader
from src.pystachy_compiler.utils import RT_VARS, rt_generic, rt_instance_error, rtsig


SOURCE = """
class T:
    def __init__(self, n: int) -> None:
        self.n = n


def look(d: dict[str, int], k: str) -> int:
    return d[k]


def names() -> list[str]:
    xs = ["a", "b"]
    xs.append("c")
    return xs


def same(a: list[int], b: list[str]) -> bool:
    return a == b


def boxed(take: bool) -> int | str:
    value: int | str = 1 if take else "one"
    return value


def keyed(words: list[str]) -> list[str]:
    return sorted(words, key=len)


def objects() -> int:
    ts = [T(1)]
    return ts[0].n


print(look({"a": 1}, "a"), names(), same([1], ["1"]), boxed(True), keyed(["bb", "a"]), objects())
"""


def compile_functions(source=SOURCE):
    functions = {}
    lower = Gen.lower

    def capture(gen, fn):
        functions[fn.f.name] = (gen, deepcopy(fn))
        lower(gen, fn)

    with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "1"}), patch.object(Gen, "lower", capture):
        Gen().program(Loader([]).program("runtime_calls.py", source))
    return functions


def calls(fn, name):
    return [i for b in fn.blocks for i in b.code if i.op == "rt" and i.s == name]


class RuntimeCallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.functions = compile_functions()

    def fn(self, name):
        return self.functions[name][1]

    def test_operands_and_results_have_the_types_of_what_the_call_reads(self):
        [lookup] = calls(self.fn("look"), "dict.getitem")
        self.assertEqual([a.t for a in lookup.a], ["dict[str,int]", "*str"])
        self.assertEqual(lookup.t, "*int")
        [made] = calls(self.fn("names"), "list.new")
        self.assertEqual(made.t, "list[str]")

    def test_a_comparisons_operands_need_not_have_one_type(self):
        [eq] = calls(self.fn("same"), "eq.pair")
        self.assertEqual([a.t for a in eq.a[:2]], ["*list[int]", "*list[str]"])
        self.assertEqual(rtsig("eq")[1:3], ["*T", "*U"])

    def test_a_result_that_no_operand_types_takes_its_builders_type(self):
        [box] = calls(self.fn("boxed"), "ubox")[:1]
        self.assertEqual(box.t, "union[int,str]")
        [keys] = calls(self.fn("keyed"), "list.new")
        self.assertEqual(keys.t, "list[int]")

    def test_a_class_named_as_a_variable_is_a_class(self):
        # (list[T] of class T is no signature's list[T]: an instance keeps it)
        [append] = calls(self.fn("objects"), "list.append")
        self.assertEqual([a.t for a in append.a], ["list[T]", "*T"])
        [made] = calls(self.fn("objects"), "list.new")
        self.assertEqual(made.t, "list[T]")

    def test_no_variable_is_left_where_an_operand_binds_it(self):
        for name, (_, fn) in self.functions.items():
            for i in [i for b in fn.blocks for i in b.code if i.op == "rt" and i.s in ("dict.getitem", "list.append", "eq.pair")]:
                with self.subTest(function=name, op=i.s):
                    self.assertFalse(any(rt_generic(a.t) and a.t not in ("list[T]", "*T") for a in i.a), [a.t for a in i.a])
                    self.assertEqual(rt_instance_error(i, rtsig(i.s)), "")

    def test_the_verifier_rejects_a_second_type_for_a_variable(self):
        gen, fn = self.functions["look"]
        for change, message in (("result", "rt dict.getitem result needs *int, got *str"),
                                ("key", "rt operand 1 reads %t6 as *int, but it is *str")):
            with self.subTest(change=change):
                broken = deepcopy(fn)
                [lookup] = calls(broken, "dict.getitem")
                if change == "result":
                    lookup.t = "*str"  # (V is the dict's values)
                else:
                    lookup.a[1] = Val(lookup.a[1].v, "*int")  # (a key may have another type: its value's is *str)
                errors = StringIO()
                with redirect_stderr(errors), self.assertRaises(SystemExit):
                    gen.verify(broken, False)
                self.assertIn(message, errors.getvalue())

    def test_instances_are_checked_without_a_compiled_program(self):
        [lookup] = calls(self.fn("look"), "dict.getitem")
        wrong = deepcopy(lookup)
        wrong.t = "*str"
        self.assertEqual(rt_instance_error(wrong, rtsig("dict.getitem")), "rt dict.getitem result needs *int, got *str")
        self.assertIn("R", RT_VARS)


if __name__ == "__main__":
    unittest.main()
