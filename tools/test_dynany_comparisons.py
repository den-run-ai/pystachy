"""Guard concrete comparison adapters and their whole-program restart budget."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pystachy_compiler import driver  # noqa: E402
from src.pystachy_compiler.dynamic import comparison_fields, comparison_reads  # noqa: E402
from src.pystachy_compiler.lexer import Lexer  # noqa: E402
from src.pystachy_compiler.parser import Parser  # noqa: E402
from src.pystachy_compiler.syntax import mk  # noqa: E402


class ConcreteComparisonTests(unittest.TestCase):
    def compile(self, count, body="return self.items == other.items", fields="self.items = [3]", extra=""):
        source = ("# pystachy: dynamic-any\nfrom typing import Any\n"
                  "class Strict:\n    def __init__(self):\n        self.items = [3]\n"
                  "    def __eq__(self, other):\n        " + body.replace("\n", "\n        ") + "\n"
                  "class Peer:\n    def __init__(self):\n        " + fields.replace("\n", "\n        ") + "\n"
                  "x: Any = Strict()\ny: Any = Peer()\nprint(x == y)\n" + extra)
        for index in range(count):
            source += f"class Irrelevant{index}:\n    pass\nz{index}: Any = Irrelevant{index}()\n"
        generators = []
        original = driver.Gen

        def generator():
            value = original()
            generators.append(value)
            return value

        with patch.object(driver, "Gen", generator):
            ir = driver.compile_program("concrete_comparison_probe.py", source, [str(ROOT / "lib")], "")
        return ir, len(generators), generators[-1]

    def test_irrelevant_classes_do_not_add_restarts(self):
        small = self.compile(0)
        large = self.compile(40)
        self.assertIn("@dyn.cmp.Strict.__eq__", large[0])
        self.assertEqual(small[1], large[1])
        self.assertLessEqual(large[1], 3)
        self.assertFalse(any(":concrete:" in key for key in large[2].xnot))

    def test_missing_and_incompatible_fields_do_not_add_failed_restarts(self):
        for fields in ["self.missing = [3]", "self.items = 'different type'"]:
            with self.subTest(fields=fields):
                result = self.compile(20, fields=fields)
                self.assertLessEqual(result[1], 3)
                self.assertFalse(any(":concrete:" in key for key in result[2].xnot))
                self.assertEqual(result[2].dyn_supports("Peer", "cmp.Strict.__eq__", "__eq__", 1), fields == "self.missing = [3]")

    def test_operand_escapes_and_nested_scopes_are_not_adapted(self):
        bodies = [
            "alias = other\nreturn self.items == alias.items",
            "other = self\nreturn self.items == other.items",
            "def nested():\n    return other.items\nreturn self.items == nested()",
        ]
        for body in bodies:
            with self.subTest(body=body):
                result = self.compile(0, body=body)
                self.assertNotIn("@dyn.cmp.Strict.__eq__", result[0])

    def test_property_is_not_treated_as_a_stored_field(self):
        extra = ("class PropertyPeer:\n"
                 "    @property\n    def items(self) -> list[int]:\n"
                 "        print('getter ran')\n        return [3]\n"
                 "property_peer: Any = PropertyPeer()\n")
        result = self.compile(0, extra=extra)
        self.assertIn("@dyn.cmp.Strict.__eq__", result[0])
        self.assertTrue(result[2].dyn_supports("Peer", "cmp.Strict.__eq__", "__eq__", 1))
        self.assertFalse(result[2].dyn_supports("PropertyPeer", "cmp.Strict.__eq__", "__eq__", 1))

    def test_hidden_binders_and_unknown_syntax_fail_closed(self):
        field = mk("attr", "items", 1, [mk("name", "other", 1, [])])
        for kind in ["walrus", "except", "import", "from", "genexpr", "future_syntax"]:
            with self.subTest(kind=kind):
                # These binders can carry the name in .s, not a name child.
                node = mk(kind, "other", 1, [field])
                self.assertFalse(comparison_fields(node, "other", []))


class ComparisonReadsTests(unittest.TestCase):
    def read_only_missing(self, source):
        body = Parser(Lexer(source + "\n", 1).file()).module()
        fields = []
        self.assertTrue(comparison_fields(body, "other", fields))
        return comparison_reads(body, "other", ["missing"])

    def test_reads_keep_evaluation_and_control_flow(self):
        for source in ("result = other.missing", "print(other.missing)",
                       "result = other.missing if flag else other.present",
                       "other.present = other.missing", "other.present[0] = other.missing"):
            with self.subTest(source=source):
                self.assertTrue(self.read_only_missing(source))

    def test_every_assignment_target_is_checked(self):
        for source in ("other.missing = [3]", "local = other.missing = [3]",
                       "other.missing = local = [3]", "other.present = other.missing = [3]",
                       "other.missing: list[int] = [3]", "other.missing += [3]",
                       "other.missing[0] = 3", "local, other.missing = ([3], [4])"):
            with self.subTest(source=source):
                self.assertFalse(self.read_only_missing(source))

    def test_existing_field_writes_remain_allowed(self):
        for source in ("other.present = [3]", "other.present += [3]",
                       "local = other.present = [3]", "other.present[0] = 3"):
            with self.subTest(source=source):
                self.assertTrue(self.read_only_missing(source))


if __name__ == "__main__":
    unittest.main()
