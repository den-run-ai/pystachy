"""Guard concrete comparison adapters and their whole-program restart budget."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pystachy_compiler import driver  # noqa: E402
from src.pystachy_compiler.dynamic import comparison_equalities, comparison_fields, comparison_reads  # noqa: E402
from src.pystachy_compiler.lexer import Lexer  # noqa: E402
from src.pystachy_compiler.parser import Parser  # noqa: E402
from src.pystachy_compiler.syntax import mk  # noqa: E402
from src.pystachy_compiler.utils import disjoint_keys  # noqa: E402


class ConcreteComparisonTests(unittest.TestCase):
    def compile(self, count, body="return self.items == other.items", fields="self.items = [3]", extra="", own_fields="self.items = [3]"):
        source = ("# pystachy: dynamic-any\nfrom typing import Any\n"
                  "class Strict:\n    def __init__(self):\n        " + own_fields.replace("\n", "\n        ") + "\n"
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

    def test_missing_and_builtin_equality_fields_do_not_add_failed_restarts(self):
        for fields in ["self.missing = [3]", "self.items = 'different type'", "self.items = ['x']",
                       "self.items = {1: 'x'}", "self.items = (1, 'x')"]:
            with self.subTest(fields=fields):
                result = self.compile(20, fields=fields)
                self.assertLessEqual(result[1], 3)
                self.assertFalse(any(":concrete:" in key for key in result[2].xnot))
                self.assertTrue(result[2].dyn_supports("Peer", "cmp.Strict.__eq__", "__eq__", 1))

    def test_unsupported_field_types_do_not_add_failed_restarts(self):
        for fields in ["self.items = b'x'", "self.items: set[int] = {3}", "self.items = object()"]:
            with self.subTest(fields=fields):
                result = self.compile(20, fields=fields)
                self.assertLessEqual(result[1], 3)
                self.assertFalse(any(":concrete:" in key for key in result[2].xnot))
                self.assertFalse(result[2].dyn_supports("Peer", "cmp.Strict.__eq__", "__eq__", 1))

    def test_scalar_set_fields_do_not_add_failed_restarts(self):
        own = "self.items: set[int] = {0}"
        peer = "self.items: set[str] = {''}"
        results = []
        for count in [1, 20]:
            extra = ""
            for index in range(count):
                extra += (f"class Compatible{index}:\n    def __init__(self):\n        {peer}\n"
                          f"compatible{index}: Any = Compatible{index}()\n")
            result = self.compile(0, fields=peer, own_fields=own, extra=extra)
            results.append(result[1])
            self.assertFalse(any(":concrete:" in key for key in result[2].xnot))
            self.assertTrue(result[2].dyn_supports("Peer", "cmp.Strict.__eq__", "__eq__", 1))
            for index in range(count):
                self.assertTrue(result[2].dyn_supports(f"Compatible{index}", "cmp.Strict.__eq__", "__eq__", 1))
        self.assertEqual(results[0], results[1])
        self.assertLessEqual(results[1], 3)

    def test_scalar_set_adapters_check_actual_operand_pairs(self):
        own = "self.items: set[int] = {0}\nself.other: set[str] = {''}"
        peer = "self.items: set[str] = {''}\nself.other: list[int] = [0]"
        for body in ["return self.items == other.items == other.other",
                     "return self.items == other.items and other.items != other.other", "return self.items < other.items",
                     "return self.items | other.items == self.items"]:
            with self.subTest(body=body):
                results = []
                for count in [1, 20]:
                    extra = ""
                    for index in range(count):
                        extra += (f"class Incompatible{index}:\n    def __init__(self):\n        " +
                                  peer.replace("\n", "\n        ") + "\n" +
                                  f"incompatible{index}: Any = Incompatible{index}()\n")
                    result = self.compile(0, fields=own, own_fields=own, extra=extra, body=body)
                    results.append(result[1])
                    self.assertFalse(any(":concrete:" in key for key in result[2].xnot))
                    for index in range(count):
                        self.assertFalse(result[2].dyn_supports(f"Incompatible{index}", "cmp.Strict.__eq__", "__eq__", 1))
                self.assertEqual(results[0], results[1])
                self.assertLessEqual(results[1], 3)

    def test_differing_field_operations_do_not_add_restarts_per_class(self):
        results = []
        for count in [1, 20]:
            extra = ""
            for index in range(count):
                extra += (f"class Incompatible{index}:\n    def __init__(self):\n"
                          "        self.items = ['x']\n"
                          f"incompatible{index}: Any = Incompatible{index}()\n")
            result = self.compile(0, body="return self.items + other.items == self.items", extra=extra)
            results.append(result[1])
            self.assertFalse(any(":concrete:" in key for key in result[2].xnot))
            # The preexisting adapter still accepts the matching list[int].
            self.assertTrue(result[2].dyn_supports("Peer", "cmp.Strict.__eq__", "__eq__", 1))
            for index in range(count):
                self.assertFalse(result[2].dyn_supports(f"Incompatible{index}", "cmp.Strict.__eq__", "__eq__", 1))
        self.assertEqual(results[0], results[1])
        self.assertLessEqual(results[1], 3)

    def test_tuple_and_union_adapters_do_not_add_failed_restarts(self):
        pairs = [
            ("self.items: tuple[int, ...] = (1, 2)", "self.items = ('1', '2')"),
            ("self.items = (1, 2)", "self.items: tuple[str, ...] = ('1', '2')"),
            ("self.items: int | list[int] = [1]", "self.items = ('1', '2')"),
            ("self.items = (1, 2)", "self.items: str | list[str] = ['x']"),
        ]
        for own, peer in pairs:
            with self.subTest(own=own, peer=peer):
                results = []
                for count in [1, 20]:
                    extra = ""
                    for index in range(count):
                        extra += (f"class Incompatible{index}:\n    def __init__(self):\n"
                                  f"        self.force = [1]\n        {peer}\n"
                                  f"incompatible{index}: Any = Incompatible{index}()\n")
                    fields = "self.force = [1]\n" + own
                    result = self.compile(0, body="return self.force == other.force and self.items == other.items",
                                          fields=fields, extra=extra, own_fields=fields)
                    results.append(result[1])
                    self.assertFalse(any(":concrete:" in key for key in result[2].xnot))
                    self.assertTrue(result[2].dyn_supports("Peer", "cmp.Strict.__eq__", "__eq__", 1))
                    for index in range(count):
                        self.assertTrue(result[2].dyn_supports(f"Incompatible{index}", "cmp.Strict.__eq__", "__eq__", 1))
                self.assertEqual(results[0], results[1])
                self.assertLessEqual(results[1], 3)

    def test_operand_aliases_and_captured_fields_are_adapted(self):
        bodies = [
            "alias = other\nreturn self.items == alias.items",
            "def nested():\n    return other.items\nreturn self.items == nested()",
            "alias = other\ndef nested():\n    return self.items == alias.items\nreturn nested()",
        ]
        for body in bodies:
            with self.subTest(body=body):
                result = self.compile(0, body=body)
                self.assertTrue("@dyn.cmp.Strict.__eq__" in result[0])
                self.assertFalse(any(":concrete:" in key for key in result[2].xnot))

    def test_rebinding_and_operand_escapes_are_not_adapted(self):
        bodies = ["other = self\nreturn self.items == other.items",
                  "alias = other\nalias = self\nreturn self.items == alias.items",
                  "alias = other\nprint(alias)\nreturn self.items == alias.items",
                  "def nested(other):\n    return other.items\nreturn self.items == nested(other)"]
        for body in bodies:
            with self.subTest(body=body):
                result = self.compile(0, body=body)
                self.assertFalse("@dyn.cmp.Strict.__eq__" in result[0])

    def test_property_uses_its_accessor(self):
        extra = ("class PropertyPeer:\n"
                 "    @property\n    def items(self) -> list[int]:\n"
                 "        print('getter ran')\n        return [3]\n"
                 "property_peer: Any = PropertyPeer()\n")
        result = self.compile(0, extra=extra)
        self.assertIn("@dyn.cmp.Strict.__eq__", result[0])
        self.assertTrue(result[2].dyn_supports("Peer", "cmp.Strict.__eq__", "__eq__", 1))
        self.assertTrue(result[2].dyn_supports("PropertyPeer", "cmp.Strict.__eq__", "__eq__", 1))
        self.assertTrue("call ptr @m.PropertyPeer.items(" in result[0])
        self.assertFalse(any(":concrete:" in key for key in result[2].xnot))

    def test_extended_shapes_keep_restart_counts_bounded(self):
        cases = [
            ("self.items = [3]", "self.items = [3.0]", "return self.items[0] + other.items[0] >= 6"),
            ("self.items = {1: 3}", "self.items = {1: 3.0}", "return self.items[1] == other.items[1]"),
            ("self.items = [3]", "self.items = ['x']", "alias = other\nreturn self.items == alias.items"),
            ("self.items = [3]", "self.items = ['x']", "def nested():\n    return self.items == other.items\nreturn nested()"),
            ("self.items = [3]", "self.items = ['x']", "try:\n    return self.items == other.items\nfinally:\n    print('cleanup')"),
            ("self.items: set[tuple[int, str]] = {(0, '')}", "self.items: set[tuple[str, str]] = {('', '')}", "return self.items == other.items"),
            ("self.items: set[int] = {1}", "self.items: frozenset[int] = frozenset({1})", "return self.items == other.items"),
        ]
        for own, peer, body in cases:
            with self.subTest(own=own, peer=peer, body=body):
                results = []
                for count in [1, 20]:
                    extra = ""
                    for index in range(count):
                        extra += (f"class Compatible{index}:\n    def __init__(self):\n        {peer}\n"
                                  f"compatible{index}: Any = Compatible{index}()\n")
                    result = self.compile(0, fields=peer, own_fields=own, body=body, extra=extra)
                    results.append(result[1])
                    self.assertFalse(any(":concrete:" in key for key in result[2].xnot))
                    for index in range(count):
                        self.assertTrue(result[2].dyn_supports(f"Compatible{index}", "cmp.Strict.__eq__", "__eq__", 1))
                self.assertEqual(results[0], results[1])
                self.assertLessEqual(results[1], 3)

    def test_missing_reads_do_not_leak_into_aliases_or_closures(self):
        bodies = ["alias = other\nreturn self.items == alias.items",
                  "def nested():\n    return self.items == other.items\nreturn nested()"]
        for body in bodies:
            with self.subTest(body=body):
                result = self.compile(20, body=body, fields="self.missing = [3]")
                self.assertFalse(result[2].dyn_supports("Peer", "cmp.Strict.__eq__", "__eq__", 1))
                self.assertFalse(any(":concrete:" in key for key in result[2].xnot))

    def test_nested_receiver_shadow_does_not_add_restarts_per_class(self):
        results = []
        for count in [1, 20]:
            extra = ("class Leaf:\n    def __eq__(self, values: list[int]) -> bool:\n"
                     "        return len(values) == 1\nclass Holder:\n    def __init__(self):\n"
                     "        self.items = Leaf()\nholder = Holder()\n")
            for index in range(count):
                extra += (f"class Incompatible{index}:\n    def __init__(self):\n        self.items = ['x']\n"
                          f"incompatible{index}: Any = Incompatible{index}()\n")
            result = self.compile(0, body="def nested(self):\n    return self.items == other.items\nreturn nested(holder)", extra=extra)
            results.append(result[1])
            self.assertFalse(any(":concrete:" in key for key in result[2].xnot))
            self.assertTrue(result[2].dyn_supports("Peer", "cmp.Strict.__eq__", "__eq__", 1))
            for index in range(count):
                self.assertFalse(result[2].dyn_supports(f"Incompatible{index}", "cmp.Strict.__eq__", "__eq__", 1))
        self.assertEqual(results[0], results[1])
        self.assertLessEqual(results[1], 3)

    def test_shadowed_capture_and_unknown_nodes_fail_closed(self):
        for source in ["def nested(other):\n    return other.items",
                       "alias = other\ndef nested(alias):\n    return alias.items",
                       "alias = other\ntry:\n    pass\nexcept Exception as alias:\n    print(alias.items)",
                       "for other in values:\n    print(other.items)",
                       "with context() as other:\n    print(other.items)"]:
            with self.subTest(source=source):
                body = Parser(Lexer(source + "\n", 1).file()).module()
                self.assertFalse(comparison_fields(body, "other", []))

    def test_hidden_binders_and_unknown_syntax_fail_closed(self):
        field = mk("attr", "items", 1, [mk("name", "other", 1, [])])
        for kind in ["walrus", "except", "import", "from", "genexpr", "def", "param", "starparam", "dstarparam", "future_syntax"]:
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
                       "other.missing[0] = 3", "local, other.missing = ([3], [4])",
                       "for other.missing in values:\n    pass", "with context() as other.missing:\n    pass"):
            with self.subTest(source=source):
                self.assertFalse(self.read_only_missing(source))

    def test_existing_field_writes_remain_allowed(self):
        for source in ("other.present = [3]", "other.present += [3]",
                       "local = other.present = [3]", "other.present[0] = 3"):
            with self.subTest(source=source):
                self.assertTrue(self.read_only_missing(source))


class ComparisonEqualitiesTests(unittest.TestCase):
    def supported(self, source):
        module = Parser(Lexer("def compare(self, other):\n    " + source + "\n", 1).file()).module()
        body = module.kids[0].kids[2]
        return comparison_equalities(body, "self", "other", ["items"], {"items": "list[int]"}, {"items": "list[str]"})

    def test_direct_builtin_field_equality(self):
        for source in ("return self.items == other.items", "return other.items != self.items",
                       "return self.items == other.items != self.items", "print('effect'); return self.items == other.items",
                       "return self.items == other.items and self.marker == other.marker",
                       "return self.items == other.items[0]", "return self.items[0] != other.items[0]"):
            with self.subTest(source=source):
                self.assertTrue(self.supported(source))

    def test_other_uses_of_differing_field_are_rejected(self):
        for source in ("return self.items + other.items == self.items", "return self.items[0] + other.items[0] > 0",
                       "return self.items < other.items", "return self.callback == other.items",
                       "return callback() == other.items",
                       "other.items = self.items", "return other.items", "print(other.items)"):
            with self.subTest(source=source):
                self.assertFalse(self.supported(source))


class DisjointKeyTests(unittest.TestCase):
    def test_numeric_and_callback_domains_are_not_disjoint(self):
        for a, b in [("int", "float"), ("bool", "int"), ("tuple[int]", "tuple[float]"),
                     ("tuple[User,int]", "tuple[User,str]"), ("tuple[User]", "tuple[int,int]"),
                     ("opt[int]", "str")]:
            with self.subTest(a=a, b=b):
                self.assertFalse(disjoint_keys(a, b))
                self.assertFalse(disjoint_keys(b, a))

    def test_tuple_lengths_and_builtin_components_prove_disjointness(self):
        for a, b in [("int", "str"), ("tuple[int,str]", "tuple[str,str]"),
                     ("tuple[tuple[int,int],bytes]", "tuple[tuple[int,str],bytes]"),
                     ("tuple[int]", "tuple[int,int]"), ("int", "tuple[int]")]:
            with self.subTest(a=a, b=b):
                self.assertTrue(disjoint_keys(a, b))
                self.assertTrue(disjoint_keys(b, a))


if __name__ == "__main__":
    unittest.main()
