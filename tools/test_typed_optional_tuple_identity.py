"""Dynamic tuple destinations retain native operand identity until boxing."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.loader import Loader
from src.pystachy_compiler.utils import targs


def compile_functions(source):
    captured = {}
    lower = Gen.lower

    def capture(gen, fn):
        gen.verify(fn, False)
        captured[fn.f.name] = [item for block in fn.blocks for item in block.code]
        lower(gen, fn)

    with patch.object(Gen, "lower", capture):
        Gen().program(Loader([]).program("optional_tuple.py", source))
    return captured


class OptionalTupleIdentityTests(unittest.TestCase):
    def test_fresh_dynamic_destinations_box_before_tuple_storage(self):
        code = compile_functions('''# pystachy: dynamic-any
from typing import Any

def fresh(value: float | None) -> Any:
    return (value, None)
def fixed(value: float | None) -> tuple[Any, Any]:
    return (value, value)
def runtime(value: float | None) -> tuple[Any, ...]:
    return (value, value)
def nested(value: float | None) -> Any:
    return ((value, None), value)

x = float("1.25")
print(fresh(x)[0] is x, fixed(x)[0] is x, runtime(x)[0] is x,
      nested(x)[0][0] is x)
''')
        for name in ("fresh", "fixed", "runtime", "nested"):
            with self.subTest(function=name):
                tuples = [item for item in code[name] if item.op == "vtuple.make"
                          or (item.op == "alloc.fixed" and item.t.startswith("tuple["))]
                self.assertTrue(tuples)
                for item in tuples:
                    self.assertTrue(all(t == "dyn" for t in targs(item.t)), item.t)
                    if item.op == "vtuple.make":
                        self.assertEqual(item.t, "vtuple[dyn]")
                        self.assertTrue(all(value.t == "dyn" for value in item.a))
                self.assertFalse(any(item.op == "tuple.load" and item.s == "opt[float]"
                                     for item in code[name]))

    def test_concrete_tuple_storage_keeps_its_existing_contract(self):
        code = compile_functions('''# pystachy: dynamic-any
from typing import Any

def typed(value: float | None) -> tuple[float | None, None]:
    return (value, None)
def existing(values: tuple[float | None, None]) -> Any:
    return values

print(existing(typed(1.25)))
''')
        self.assertTrue(any(item.op == "alloc.fixed" and item.t == "tuple[opt[float],None]"
                            for item in code["typed"]))
        self.assertTrue(any(item.op == "tuple.load" and item.s == "opt[float]"
                            for item in code["existing"]))


if __name__ == "__main__":
    unittest.main()
