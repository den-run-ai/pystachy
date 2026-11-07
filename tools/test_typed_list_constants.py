"""Large scalar literals use bounded executable IR and immutable typed data.

The differential corpus checks Python behavior; these guards detect a return to
one append/packing instruction per literal even when native outputs still match.
"""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from src.pystachy_compiler import diagnostics, driver
from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.loader import Loader


ROOT = Path(__file__).resolve().parents[1]


def compile_source(source):
    with patch.dict("os.environ", {"PYSTACHY_IRCHECK": "1"}):
        return driver.compile_program("scalar_literal_probe.py", source, [str(ROOT / "lib")], "")


def literal_source(items, item_type="int", prefix=""):
    return (prefix + "def literal() -> list[" + item_type + "]:\n    return [" +
            ", ".join(items) + "]\nprint(literal())\n")


def body(ir, name="literal"):
    match = re.search(r"^define [^\n]*@f\." + name + r"\([^\n]*\{\n(.*?)^}", ir, re.M | re.S)
    if not match:
        raise AssertionError(f"missing function {name}")
    return match[1]


class ScalarListConstantTests(unittest.TestCase):
    def test_initializer_instructions_stay_bounded_as_data_grows(self):
        for item_type in ("int", "float", "bool"):
            counts = []
            for n in (32, 256, 2048):
                items = [str(j - n // 2) if item_type == "int" else
                         repr((j - n // 2) * .125) if item_type == "float" else
                         "True" if j % 3 else "False" for j in range(n)]
                with self.subTest(item_type=item_type, n=n):
                    ir = compile_source(literal_source(items, item_type))
                    code = body(ir)
                    counts.append(sum(line.startswith("  ") for line in code.splitlines()))
                    self.assertEqual(code.count("@pys_list_from_const("), 1)
                    self.assertNotIn("@pys_list_append", code)
                    self.assertIn(f"private unnamed_addr constant [{n} x i64]", ir)
            self.assertEqual(counts, [counts[0]] * len(counts))
            self.assertLess(counts[0], 12)

    def test_small_literals_keep_the_existing_path(self):
        for n in (0, 1, 8, 31):
            with self.subTest(n=n):
                ir = compile_source(literal_source([str(j) for j in range(n)]))
                self.assertNotIn("@pys_list_from_const", ir)
                self.assertEqual(body(ir).count("@pys_list_append("), n)

    def test_scalar_data_keeps_types_and_exact_bits(self):
        source = (literal_source(["-0.0", "0.0", "1e309", "-1e309", "5e-324", "-5e-324"] * 6, "float") +
                  "ints = [-9223372036854775808, 9223372036854775807, 0, -1] * 2\n")
        g = Gen()
        ir = g.program(Loader([str(ROOT / "lib")]).program("scalar_bits.py", source))
        data = [d for d in g.consts if d.kind == "listdata"]
        self.assertEqual(len(data), 1)
        self.assertEqual([v.t for v in data[0].items], ["float"] * 36)
        self.assertEqual([int(v.v, 16) for v in data[0].items[:6]],
                         [0x8000000000000000, 0x0000000000000000, 0x7ff0000000000000,
                          0xfff0000000000000, 0x0000000000000001, 0x8000000000000001])
        self.assertIn("bitcast (double 0x8000000000000000 to i64)", ir)
        integers = compile_source(literal_source(["-9223372036854775808", "9223372036854775807"] * 16))
        self.assertIn("i64 -9223372036854775808, i64 9223372036854775807", integers)

    def test_shared_data_does_not_share_the_constructed_list(self):
        values = ", ".join(str(j) for j in range(32))
        source = (f"def first() -> list[int]:\n    return [{values}]\n"
                  f"def second() -> list[int]:\n    return [{values}]\n"
                  "print(first() is second(), first() is first())\n")
        ir = compile_source(source)
        self.assertEqual(len(re.findall(r"^@lc\.", ir, re.M)), 1)
        for name in ("first", "second"):
            self.assertEqual(body(ir, name).count("@pys_list_from_const("), 1)

    def test_pointer_tuple_dynamic_and_computed_items_stay_general(self):
        cases = [
            literal_source([repr("entry") for _ in range(32)], "str"),
            literal_source(["(1, 2)"] * 32, "tuple[int, int]"),
            literal_source(["None", "1"] * 16, "int | None"),
            literal_source(["float('nan')"] * 32, "float"),
            literal_source(["mark(" + str(j) + ")" for j in range(32)],
                           prefix="def mark(n: int) -> int:\n    print(n)\n    return n\n"),
            literal_source(["1"] * 32, prefix=diagnostics.DYNPRAGMA + "\n"),
            literal_source(["1"] * 32, prefix=diagnostics.INTPRAGMA + "\n"),
        ]
        for source in cases:
            with self.subTest(source=source[:90]):
                ir = compile_source(source)
                self.assertNotIn("@pys_list_from_const", ir)
                self.assertIn("@pys_list_append", ir)

    def test_fixed_width_rejection_is_not_bypassed(self):
        errors = StringIO()
        with redirect_stderr(errors), self.assertRaises(SystemExit):
            compile_source(literal_source(["1"] * 31 + ["9223372036854775808"]))
        self.assertIn("integer literal does not fit in 64 bits", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
