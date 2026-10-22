"""Check builtin positional errors against the pinned CPython oracle."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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


if __name__ == "__main__":
    unittest.main()
