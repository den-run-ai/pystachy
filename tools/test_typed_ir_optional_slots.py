"""Private optional scalars keep presence and payload without allocating boxes."""
from copy import deepcopy
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import Val
from src.pystachy_compiler.loader import Loader


SOURCE = """
def minimum(xs: list[int]) -> int:
    best: int | None = None
    for x in xs:
        if best is None or x < best:
            best = x
    return 0 if best is None else best


def inferred_minimum(xs: list[int]) -> int:
    best = None
    for x in xs:
        if best is None or x < best:
            best = x
    return 0 if best is None else best


def rank_minimum(keys: list[int], ranks: dict[int, int]) -> int:
    best = None
    for key in keys:
        rank = ranks.get(key)
        if rank is not None and (best is None or rank < best):
            best = rank
    return -1 if best is None else best


def chosen(x: float, take: bool) -> float:
    value: float | None = x if take else None
    return 1.0 if value is None else value


def truth(x: bool, take: bool) -> bool:
    value: bool | None = None
    if take:
        value = x
    return value is not None and value


def escaped(x: int, take: bool) -> int | None:
    value: int | None = None
    if take:
        value = x
    return value


def argument(x: int | None) -> int:
    value: int | None = x
    return 0 if value is None else value


def looked_up(d: dict[str, int], key: str) -> int:
    value: int | None = d.get(key)
    return 0 if value is None else value


def produced(x: int, take: bool) -> int:
    value: int | None = escaped(x, take)
    return 0 if value is None else value


def string_value(x: str, take: bool) -> str:
    value = None
    if take:
        value = x
    return "empty" if value is None else value


def copied(x: int, take: bool) -> int:
    value: int | None = None
    if take:
        value = x
    other: int | None = value
    return 0 if other is None else other


print(inferred_minimum([5, 3, 1]), string_value("held", True))
print(minimum([5, 3, 1]), chosen(-0.0, True), truth(False, True))
print(escaped(1, True), argument(None), looked_up({"x": 2}, "y"))
print(produced(3, False), copied(4, True), rank_minimum([1, 2], {1: 3, 2: 0}))
"""


def compile_functions(source=SOURCE, options=""):
    functions = {}
    lower = Gen.lower

    def capture(gen, fn):
        gen.verify(fn, False)
        functions[fn.f.name] = deepcopy(fn)
        lower(gen, fn)

    with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "1", "PYSTACHY_OPT": options}), \
            patch.object(Gen, "lower", capture):
        Gen().program(Loader([]).program("optional_slots.py", source))
    return functions


def calls(fn, name):
    return [i for b in fn.blocks for i in b.code if i.op == "rt" and i.s == name]


def optional_slots(fn):
    return [s for s in fn.slots if s.t.startswith("opt[")]


class OptionalSlotsTests(unittest.TestCase):
    def test_local_minimum_phi_and_bool_remove_boxes(self):
        functions = compile_functions()
        for name in ("minimum", "inferred_minimum", "chosen", "truth"):
            with self.subTest(function=name):
                fn = functions[name]
                self.assertFalse(calls(fn, "box"))
                self.assertFalse(optional_slots(fn))
                self.assertTrue(any(s.s.endswith(".tag") for s in fn.slots))
                self.assertTrue(any(s.s.endswith(".pay") for s in fn.slots))

    def test_rank_minimum_keeps_one_lookup_without_optional_boxes(self):
        fn = compile_functions()["rank_minimum"]
        self.assertEqual(len(calls(fn, "dict.find")), 1)
        self.assertEqual(len(calls(fn, "dict.val_or_zero")), 1)
        self.assertFalse(calls(fn, "dict.getbox"))
        self.assertFalse(calls(fn, "box"))
        self.assertFalse(optional_slots(fn))
        before = compile_functions(options="-unionslots")["rank_minimum"]
        self.assertEqual(len(calls(before, "dict.getbox")), 1)

    def test_disabled_pass_retains_representation(self):
        functions = compile_functions(options="-unionslots")
        for name in ("minimum", "inferred_minimum", "chosen", "truth"):
            with self.subTest(function=name):
                self.assertTrue(calls(functions[name], "box"))
                self.assertTrue(optional_slots(functions[name]))

    def test_escape_unknown_producer_and_optional_copy_keep_boxes(self):
        functions = compile_functions()
        for name in ("escaped", "argument", "produced", "copied", "string_value"):
            with self.subTest(function=name):
                self.assertTrue(optional_slots(functions[name]))
        self.assertTrue(calls(functions["escaped"], "box"))
        self.assertTrue(calls(functions["copied"], "box"))

    def test_nonnull_pointer_comparison_keeps_box(self):
        split = Gen.unionslots

        def compare_value(gen, fn):
            if fn.f.name in ("chosen", "looked_up"):
                for block in fn.blocks:
                    for op in block.code:
                        if op.op == "ptr.cmp":
                            value = next(a for a in op.a if a.v != "null")
                            op.a = [Val(value.v, value.t), Val(value.v, value.t)]
            return split(gen, fn)

        with patch.object(Gen, "unionslots", compare_value):
            functions = compile_functions()
        self.assertTrue(optional_slots(functions["chosen"]))
        self.assertTrue(calls(functions["chosen"], "box"))
        self.assertTrue(optional_slots(functions["looked_up"]))
        self.assertTrue(calls(functions["looked_up"], "dict.getbox"))

    def test_generator_frame_stays_boxed(self):
        functions = compile_functions("""
def values(xs: list[int]):
    best: int | None = None
    for x in xs:
        if best is None or x < best:
            best = x
        yield 0 if best is None else best
print(list(values([3, 2, 1])))
""")
        fn = functions["values"]
        self.assertTrue(fn.coro)
        self.assertTrue(optional_slots(fn))
        self.assertTrue(calls(fn, "box"))

    def test_conditional_initialization_keeps_unbound_flag_and_guards(self):
        case = Path(__file__).resolve().parent.parent / "tests/programs/optional/optional_scalar_slots_unbound.py"
        source = case.read_text()
        functions = compile_functions(source)
        unchanged = compile_functions(source, options="-unionslots")
        for name in ("annotated", "inferred"):
            with self.subTest(function=name):
                fn = functions[name]
                before = unchanged[name]
                self.assertFalse(calls(fn, "box"))
                self.assertFalse(optional_slots(fn))
                flags = [(s.s, s.t, s.k) for s in fn.slots if s.k == 1]
                self.assertEqual(flags, [("value", "bool", 1)])
                self.assertEqual(flags, [(s.s, s.t, s.k) for s in before.slots if s.k == 1])
                checks = [i.s for b in fn.blocks for i in b.code
                          if i.op == "check" and i.s.startswith("UnboundLocalError:")]
                self.assertTrue(checks)
                self.assertEqual(checks, [i.s for b in before.blocks for i in b.code
                                         if i.op == "check" and i.s.startswith("UnboundLocalError:")])


if __name__ == "__main__":
    unittest.main()
