"""Check builtin arity and bounded dynamic call specialization."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler import driver
from src.pystachy_compiler.dynamic import builtin_arity, builtin_limits
from src.pystachy_compiler.specs import METHODS


class BuiltinArityTests(unittest.TestCase):
    def test_invalid_positional_counts_match_cpython(self):
        # Use direct method calls: CPython words bool errors differently for bound method values.
        objects = {"str": "abc", "list": [1], "dict": {"x": 1}, "vtuple": (1,),
                   "int": 1, "bool": True, "float": 1.0}
        types = {"list": "list[dyn]", "dict": "dict[dyn,dyn]", "vtuple": "vtuple[dyn]"}
        names = list(METHODS) + ["list.sort", "dict.update", "bool.bit_count", "bool.bit_length"]
        cases = 0
        for key in names:
            base, method = key.split(".")
            if base not in objects:
                continue
            bt = types.get(base, base)
            lo, hi = builtin_limits(bt, method)
            # These two existing subset restrictions reject a shape CPython accepts.
            if key == "str.replace":
                hi = 3
            if key == "dict.setdefault":
                lo = 1
            for count in range(hi + 3):
                if lo <= count <= hi:
                    continue
                with self.subTest(method=key, count=count):
                    with self.assertRaises(TypeError) as error:
                        eval("obj." + method + "(" + ",".join(["None"] * count) + ")", {"obj": objects[base]})
                    self.assertEqual(builtin_arity(bt, method, count), str(error.exception))
                cases += 1
        self.assertGreater(cases, 150)

    def test_unsupported_shapes_are_explicit(self):
        self.assertEqual(builtin_arity("str", "replace", 3),
                         "str.replace() with 3 positional arguments is not supported")
        self.assertEqual(builtin_arity("dict[dyn,dyn]", "setdefault", 1),
                         "dict.setdefault() with 1 positional argument is not supported")


class GeneratorContextTests(unittest.TestCase):
    def compile(self, consumers, optional=False):
        source = ("# pystachy: dynamic-any\nfrom typing import Any, Iterator\n"
                  "def rows(value: int) -> Iterator[list[Any]]:\n    yield [value]\n"
                  "print(list(rows(0)))\n")
        for index in range(consumers):
            item = "int | None" if optional and index % 2 else "int"
            source += (f"def consumer{index}() -> Iterator[list[{item}]]:\n"
                       f"    yield from rows({index})\n"
                       f"print(list(consumer{index}()))\n")
        generators = []
        original = driver.Gen

        def generator():
            value = original()
            generators.append(value)
            return value

        root = Path(__file__).resolve().parent.parent
        with patch.object(driver, "Gen", generator):
            ir = driver.compile_program("generator_context_probe.py", source, [str(root / "lib")], "")
        rows = [fn.f for fn in generators[-1].fns if fn.f.name == "rows"]
        return ir, len(generators), rows

    def test_repeated_consumers_reuse_one_yield_specialization(self):
        sizes = []
        for consumers in [1, 16, 64]:
            ir, passes, rows = self.compile(consumers)
            self.assertEqual(passes, 1)
            self.assertCountEqual([f.ret for f in rows], ["gen[list[dyn]]", "gen[list[int]]"])
            sizes.append(len(ir))
        # More callers add their own bodies, not another generator body for each
        # caller or whole-program inference retry. This is a count/size bound,
        # deliberately independent of noisy wall-clock timings.
        self.assertLess(sizes[2], sizes[1] * 4)

    def test_distinct_layouts_do_not_share_a_yield_specialization(self):
        _, passes, rows = self.compile(12, optional=True)
        self.assertEqual(passes, 1)
        self.assertCountEqual([f.ret for f in rows],
                              ["gen[list[dyn]]", "gen[list[int]]", "gen[list[opt[int]]]"])
        self.assertTrue(all(f.gret == "None" and f.gsend == "None" for f in rows))


if __name__ == "__main__":
    unittest.main()
