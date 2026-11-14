"""Check builtin arity and bounded dynamic call specialization."""
import sys
import tempfile
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


class TemplateMembershipTests(unittest.TestCase):
    def test_cross_module_exact_types_share_one_descriptor_dispatcher(self):
        helper = ""
        source = ("# pystachy: dynamic-any\nfrom typing import Any\nimport exacthelpers\n"
                  "class Box:\n    def __init__(self, value):\n        self.value = value\n"
                  "class Factory:\n    def make(self):\n        return Box(1.5)\n"
                  "a: Any = Box(1)\nb: Any = Box('text')\n")
        for index in range(32):
            helper += (f"def site{index}(left, right):\n"
                       "    return type(left) is type(right)\n")
            source += f"print(exacthelpers.site{index}(a, b))\n"
        source += "factory: Any = Factory()\nprint(exacthelpers.site0(a, factory.make()))\n"
        generators = []
        operations = {}
        original = driver.Gen
        lower = original.lower

        def generator():
            value = original()
            generators.append(value)
            return value

        def observed_lower(gen, fn):
            operations[fn.f.name] = [(ins.op, ins.s) for block in fn.blocks for ins in block.code]
            return lower(gen, fn)

        root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "exacthelpers.py").write_text(helper)
            with patch.object(driver, "Gen", generator), patch.object(original, "lower", observed_lower):
                driver.compile_program("template_type_probe.py", source,
                                       [directory, str(root / "lib")], "")
        gen = generators[-1]
        predicates = [fn for fn in gen.fns if fn.f.name == "dyn.sametype"]
        self.assertEqual(len(predicates), 1)
        code = operations[predicates[0].f.name]
        self.assertFalse(any(op in {"dyn.payload", "dyn.raw", "slot.unpack"} for op, _ in code))
        classes = [c for c in gen.dynclasses if gen.tmpl_of(c) == "Box"]
        self.assertEqual(len(classes), 3)

    def test_sites_share_origin_predicate_without_payload_narrowing(self):
        source = ("# pystachy: dynamic-any\nfrom typing import Any, Generic, TypeVar\n"
                  "T = TypeVar('T')\nclass Box(Generic[T]):\n"
                  "    def __init__(self, value: T) -> None:\n        self.value = value\n"
                  "class Unused(Generic[T]):\n"
                  "    def __init__(self, value: T) -> None:\n        self.value = value\n"
                  "    def unused(self):\n        return memoryview(self.value)\n"
                  "class Factory:\n    def make(self):\n        return Box(1.5)\n"
                  "def read(value: Any) -> Any:\n"
                  "    if isinstance(value, Box):\n        return value.value\n"
                  "    return None\n")
        for index in range(32):
            source += (f"def site{index}(value: Any) -> bool:\n"
                       "    return isinstance(value, Box)\n")
        source += ("print(site0(None), isinstance(None, Unused))\n"
                   "a: Any = Box(1)\nb: Any = Box('text')\n"
                   "print(read(a), read(b))\nfactory: Any = Factory()\n"
                   "print(read(factory.make()))\n")
        source += "\n".join(f"print(site{index}(a))" for index in range(32)) + "\n"
        generators = []
        operations = {}
        original = driver.Gen
        lower = original.lower

        def generator():
            value = original()
            generators.append(value)
            return value

        def observed_lower(gen, fn):
            operations[fn.f.name] = [(ins.op, ins.s) for block in fn.blocks for ins in block.code]
            return lower(gen, fn)

        root = Path(__file__).resolve().parent.parent
        with patch.object(driver, "Gen", generator), patch.object(original, "lower", observed_lower):
            driver.compile_program("template_membership_probe.py", source, [str(root / "lib")], "")
        gen = generators[-1]
        predicates = [fn for fn in gen.fns if fn.f.name == "dyn.isinstance.Box"]
        self.assertEqual(len(predicates), 1)
        code = operations[predicates[0].f.name]
        self.assertFalse(any(op in {"dyn.payload", "dyn.raw", "slot.unpack"} for op, _ in code))
        self.assertFalse(gen.dyn_unboxable("Box"))
        classes = [c for c in gen.dynclasses if gen.tmpl_of(c) == "Box"]
        self.assertEqual(len(classes), 3)  # int, str, and Factory.make's late float
        readers = [fn for fn in gen.fns if fn.f.name == "read"]
        self.assertEqual(len(readers), 1)
        reads = operations[readers[0].f.name]
        self.assertIn(("call", "@dyn.get.value"), reads)
        self.assertFalse(any(op == "dyn.payload" for op, _ in reads))
        self.assertFalse(any(gen.tmpl_of(c) == "Unused" for c in gen.dynclasses))


if __name__ == "__main__":
    unittest.main()
