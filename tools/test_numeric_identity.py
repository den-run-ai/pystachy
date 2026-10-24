"""Identity elision must stay inside its numeric function or scalar consumer proof."""
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pystachy_compiler import driver, functions  # noqa: E402
from src.pystachy_compiler.diagnostics import Rejoin  # noqa: E402
from src.pystachy_compiler.gen import Gen  # noqa: E402
from src.pystachy_compiler.syntax import mk  # noqa: E402
from src.pystachy_compiler.utils import folded_int  # noqa: E402


class NumericIdentityTests(unittest.TestCase):
    def decision(self, source):
        generators = []
        original = driver.Gen

        def make_generator():
            generator = original()
            generators.append(generator)
            return generator

        with patch.object(driver, "Gen", make_generator):
            driver.compile_program("numeric_identity_probe.py", "# pystachy: dynamic-any\n" + source,
                                   [str(ROOT / "lib")], "")
        # Use the final compilation: inference may restart with changed type hints.
        functions = [function for function in generators[-1].fns
                     if function.f.node.s == "target"]
        self.assertEqual(len(functions), 1)
        return functions[0].numeric_only

    def test_closed_numeric_functions(self):
        programs = [
            "def target(x: int) -> int:\n    n = x + 1000\n    m = n\n    return m + n\nprint(target(2))\n",
            "def target(x: int) -> int:\n    total = 0\n    for i in range(x):\n        n = (m := i + 1000)\n        total += n + m\n    return total\nprint(target(2))\n",
            "def target(x: float) -> float:\n    n = x\n    while n < 3.0:\n        n = n + 1.0\n    return n if x > 0.0 else -n\nprint(target(2.0))\n",
        ]
        for source in programs:
            with self.subTest(source=source):
                self.assertTrue(self.decision(source))

    def test_scalar_none_functions_and_builtin_print(self):
        bodies = [
            "for i in range(x):\n    print(n := i + 1000)\nreturn",
            "n = x + 1000\nm = x + 2000\nchosen = n if x else m\nprint('chosen', chosen)\nreturn None",
        ]
        for body in bodies:
            for header in ("def target(x: int) -> None:", "def target(x: int):", "def target(x):"):
                source = (header + "\n" +
                          "\n".join("    " + line for line in body.splitlines()) + "\ntarget(2)\n")
                with self.subTest(body=body, header=header):
                    self.assertTrue(self.decision(source))

    def test_inferred_numeric_return_does_not_use_none_proof(self):
        for header in ("def target(x):", "def target(x: int):"):
            source = header + "\n    n = x + 1000\n    print(n)\n    return n\nprint(target(2))\n"
            with self.subTest(header=header):
                self.assertFalse(self.decision(source))

    def test_print_proof_rejects_shadowing_keywords_and_objects(self):
        programs = [
            "from typing import Any\ndef print(x: Any) -> None:\n    pass\ndef target(x: int) -> None:\n    print(x)\ntarget(2)\n",
            "def target(x: int) -> None:\n    print(x, end='')\ntarget(2)\n",
            "def target(x: int) -> None:\n    print([x])\ntarget(2)\n",
            "def target(x: int) -> None:\n    print(*[x])\ntarget(2)\n",
        ]
        for source in programs:
            with self.subTest(source=source):
                self.assertFalse(self.decision(source))

    def test_observable_or_open_bodies_keep_slots(self):
        bodies = [
            "observed: Any = n\nreturn m",
            "observed: Any = n\nreturn id(observed)",
            "return consume(n)",
            "items = [n]\nreturn items[0]",
            "print(n)\nreturn m",
            "annotated: int = n\nreturn annotated",
            "global GLOBAL\nGLOBAL = n\nreturn m",
            "if x < 0:\n    raise ValueError('negative')\nreturn m",
            "try:\n    return m // x\nexcept ZeroDivisionError:\n    return n",
        ]
        prefix = "from typing import Any\nGLOBAL = 1\ndef consume(value: Any) -> int:\n    return 1\n"
        for body in bodies:
            source = (prefix + "def target(x: int) -> int:\n    n = x + 1000\n    m = n\n" +
                      "\n".join("    " + line for line in body.splitlines()) + "\nprint(target(2))\n")
            with self.subTest(body=body):
                self.assertFalse(self.decision(source))

    def test_numeric_global_reads_keep_scalar_argument_proof(self):
        for body in ["return GLOBAL + x", "return GLOBAL if x < GLOBAL else x + 1", "return GLOBAL"]:
            source = ("GLOBAL = 1000\ndef target(x: int) -> int:\n    " + body +
                      "\nprint(target(1))\n")
            with self.subTest(body=body):
                self.assertTrue(self.decision(source))

    def test_numeric_globals_do_not_admit_writes_or_callbacks(self):
        prefix = ("GLOBAL = 1000\ndef mutate() -> int:\n    global GLOBAL\n"
                  "    GLOBAL += 1\n    return 0\n")
        for body in ["global GLOBAL\nGLOBAL = x\nreturn GLOBAL", "return GLOBAL + mutate() + x"]:
            source = (prefix + "def target(x: int) -> int:\n" +
                      "\n".join("    " + line for line in body.splitlines()) + "\nprint(target(1))\n")
            with self.subTest(body=body):
                self.assertFalse(self.decision(source))

    def test_dynamic_and_inferred_signatures_keep_slots(self):
        headers = [
            ("def target(x: Any) -> int:", "target(2)"),
            ("def target(x: int) -> Any:", "target(2)"),
            ("def target(x: int) -> int | float:", "target(2)"),
            ("def target(x: int):", "target(2)"),
            ("def target(x) -> int:", "target(2)"),
            ("def target(x: int, *rest: int) -> int:", "target(2, 3)"),
            ("def target(x: int, **rest: int) -> int:", "target(2, extra=3)"),
        ]
        for header, call in headers:
            source = ("from typing import Any\n" + header +
                      "\n    n = 1000\n    m = n\n    return m\nprint(" + call + ")\n")
            with self.subTest(header=header):
                self.assertFalse(self.decision(source))

    def test_closures_generators_and_decorators_keep_slots(self):
        programs = [
            "def outer() -> int:\n    def target(x: int) -> int:\n        n = x + 1000\n        m = n\n        return m\n    return target(2)\nprint(outer())\n",
            "from typing import Iterator\ndef target(x: int) -> Iterator[int]:\n    n = x + 1000\n    m = n\n    yield m\nprint(list(target(2)))\n",
            "class Box:\n    @staticmethod\n    def target(x: int) -> int:\n        n = x + 1000\n        m = n\n        return m\nprint(Box.target(2))\n",
        ]
        for source in programs:
            with self.subTest(source=source):
                self.assertFalse(self.decision(source))

    def test_shadowed_builtin_calls_keep_slots(self):
        programs = [
            "from typing import Any\ndef float(value: Any) -> int:\n    return 7\ndef target(x: int) -> int:\n    n = x + 1000\n    m = n\n    return float(m)\nprint(target(2))\n",
            "from typing import Any\ndef bool(value: Any) -> int:\n    return 7\ndef target(x: int) -> int:\n    n = x + 1000\n    m = n\n    return bool(m)\nprint(target(2))\n",
            "from typing import Any\ndef int(value: Any) -> bool:\n    return True\ndef target(x: bool) -> bool:\n    n = 1000\n    m = n\n    return int(m)\nprint(target(True))\n",
            "def range(n: int) -> list[int]:\n    return [n]\ndef target(x: int) -> int:\n    total = 0\n    for n in range(x):\n        m = n\n        total += m\n    return total\nprint(target(2))\n",
        ]
        for source in programs:
            with self.subTest(source=source):
                self.assertFalse(self.decision(source))

    def test_accepting_unchecked_bodies_is_detected(self):
        # A proof that trusts every body must fail the real compiler boundary checks.
        with patch.object(functions, "numeric_statement", return_value=True):
            with self.assertRaises(AssertionError):
                NumericIdentityTests().test_observable_or_open_bodies_keep_slots()


class NumericCallIdentityTests(unittest.TestCase):
    def compile(self, source):
        return driver.compile_program("numeric_call_identity.py", "# pystachy: dynamic-any\n" + source,
                                      [str(ROOT / "lib")], "")

    def function_ir(self, ir, name):
        return re.search(r"^define [^\n]*@" + re.escape(name) + r"\([^\n]*\n.*?^}", ir,
                         re.MULTILINE | re.DOTALL).group(0)

    def signature(self, body, annotation="int"):
        generators = []
        original = driver.Gen

        def make_generator():
            generator = original()
            generators.append(generator)
            return generator

        source = ("# pystachy: dynamic-any\ndef target(x: int) -> " + annotation + ":\n" +
                  "\n".join("    " + line for line in body.splitlines()) + "\nprint(target(1000))\n")
        with patch.object(driver, "Gen", make_generator):
            ir = driver.compile_program("numeric_call_identity.py", source, [str(ROOT / "lib")], "")
        fn = next(fn for fn in generators[-1].fns if fn.f.node.s == "target")
        return fn, ir

    def test_return_aliases_keep_their_parameter_provenance(self):
        for body, names in [
            ("return x", {"x"}),
            ("alias = x\nreturn alias", {"x", "alias"}),
            ("alias = x\nwhile alias < 1002:\n    alias += 1\nreturn alias", {"x", "alias"}),
            ("return int(x)", {"x"}),
        ]:
            with self.subTest(body=body):
                fn, _ = self.signature(body)
                self.assertTrue(fn.numeric_only)
                self.assertEqual(set(fn.f.idnames), names)

    def test_fresh_arithmetic_keeps_argument_boxing_elided(self):
        for body in ["return x + 1", "copy = x\nreturn copy + 1"]:
            fn, ir = self.signature(body)
            self.assertTrue(fn.f.scalar_args)
            self.assertFalse(fn.f.idnames)
            self.assertNotRegex(ir, r"(?:call|invoke) ptr @pys_dyn_(?:int|float)\(")

    def test_selected_numeric_returns_keep_boxes_lazy(self):
        for typ, value in [("int", "1000"), ("float", "1.5")]:
            for expression in ["x if x else -x", "x or -x", "x and -x"]:
                source = ("# pystachy: dynamic-any\ndef target(x: " + typ + ") -> " + typ + ":\n" +
                          "    selected = " + expression + "\n    copied = selected\n    return copied\n" +
                          "print(target(" + value + "))\n")
                with self.subTest(typ=typ, expression=expression):
                    ir = driver.compile_program("selected_identity.py", source, [str(ROOT / "lib")], "")
                    self.assertIn("ptr %aid0", ir)
                    self.assertNotRegex(ir, r"(?:call|invoke) ptr @pys_dyn_(?:int|float)\(")

    def test_numeric_annotation_argument_proof_is_separate(self):
        fn, ir = self.signature("value: int | float = 0\nfor i in range(x):\n    value += i\nreturn value", "int | float")
        self.assertFalse(fn.numeric_only)
        self.assertTrue(fn.f.scalar_args)
        self.assertNotIn("x", fn.f.idnames)
        self.assertNotRegex(ir, r"(?:call|invoke) ptr @pys_dyn_(?:int|float)\(")

    def test_foreign_code_has_no_companion_signature(self):
        source = "def target(x: int) -> int:\n    return x\nprint(target(1000))\n"
        ir = driver.compile_program("ordinary_numeric_call.py", source, [str(ROOT / "lib")], "")
        self.assertNotIn("%aid", ir)
        self.assertNotIn("%idret", ir)

    def test_exact_current_local_boxing_has_only_a_null_guard(self):
        for scalar, value in [("int", "1000"), ("float", "1.5")]:
            ir = self.compile("from typing import Any\ndef target(seed: str) -> Any:\n"
                              "    x = " + scalar + "(seed)\n    return x\nprint(target('" + value + "'))\n")
            body = self.function_ir(ir, "f.target")
            # The unchanged, exact local cannot contain another type or payload.
            # Keep allocation lazy without emitting the general stale-read CFG.
            self.assertEqual(body.count("br i1"), 1)
            self.assertNotIn("@pys_dyntype_" + scalar, body)
            self.assertEqual(body.count("call ptr @pys_dyn_" + scalar + "("), 1)

    def test_immutable_numeric_parameter_keeps_incoming_box_directly(self):
        for scalar, value in [("int", "1000"), ("float", "1.5")]:
            ir = self.compile("from typing import Any\ndef target(x: " + scalar +
                              ") -> Any:\n    return x\nprint(target(" + value + "))\n")
            body = self.function_ir(ir, "f.target")
            self.assertIn("ret ptr %aid0", body)
            self.assertNotIn("@pys_dyn_" + scalar, body)
            self.assertNotRegex(body, r"load [^\n]*%x\.box(?:gen)?\.")

    def test_rebound_numeric_parameter_keeps_slot_provenance(self):
        ir = self.compile("from typing import Any\ndef target(x: int) -> Any:\n"
                          "    x = x + 1\n    return x\nprint(target(1000))\n")
        body = self.function_ir(ir, "f.target")
        self.assertIn("@pys_dyn_int", body)
        self.assertRegex(body, r"load [^\n]*%x\.box\.")

    def test_scalar_local_operands_do_not_load_identity_slots(self):
        ir = self.compile("from typing import Any\ndef target(x: int) -> Any:\n"
                          "    return x + 1\nprint(target(1000))\n")
        body = self.function_ir(ir, "f.target")
        self.assertNotRegex(body, r"load [^\n]*%x\.box(?:gen)?\.")

    def test_narrowed_union_keeps_general_box_validation(self):
        ir = self.compile("from typing import Any\ndef target(x: int | float) -> Any:\n"
                          "    if isinstance(x, int):\n        return x\n"
                          "    return 0\nprint(target(1000))\n")
        self.assertIn("@pys_dyntype_int", self.function_ir(ir, "f.target"))

    def test_global_return_keeps_its_box_while_scalar_arguments_are_elided(self):
        ir = self.compile("GLOBAL = 1000\ndef target(x: int) -> int:\n"
                          "    return GLOBAL if x < GLOBAL else x + 1\nprint(target(1))\n")
        body = self.function_ir(ir, "f.target")
        self.assertIn("@g.GLOBAL.box", body)
        self.assertNotIn("@pys_dyn_int", self.function_ir(ir, "main.init"))

    def test_inferred_scalar_calls_elide_known_argument_boxes(self):
        source = ("def target(x, flag):\n    value = x if flag else x + 1\n    print(value)\n"
                  "target(0, True)\ntarget(flag=False, x=0.0)\n")
        ir = self.compile(source)
        self.assertNotRegex(ir, r"(?:call|invoke) ptr @pys_dyn_(?:int|float)\(")
        # The existing whole-fixture guard must retain its empty @main.init call list.
        source = (ROOT / "tests/ir/dynany_identity_scalar_expressions.py").read_text()
        ir = self.compile(source)
        self.assertNotIn("@pys_", self.function_ir(ir, "main.init"))

    def test_inferred_scalar_calls_accept_already_bound_numeric_names(self):
        ir = self.compile("def target(x, flag):\n    print(x if flag else x + 1)\n"
                          "def caller(value: int) -> None:\n    target(value, flag=True)\ncaller(0)\n")
        self.assertNotIn("@pys_dyn_int", self.function_ir(ir, "f.caller"))

    def test_unknown_arguments_keep_early_identity_snapshots(self):
        ir = self.compile("def callback() -> int:\n    return 1\n"
                          "def target(x, y):\n    print(x + y)\ntarget(0, callback())\n")
        main = self.function_ir(ir, "main.init")
        # Even a scalar callee must not speculate about an argument callback's type.
        self.assertIn("@pys_dyn_int(i64 0)", main)
        self.assertLess(main.index("@pys_dyn_int(i64 0)"), main.index("@f.callback("))

    def test_nonnumeric_arguments_block_early_specialization(self):
        ir = self.compile("def target(x, y):\n    print(x, y)\ntarget(0, 'text')\n")
        self.assertIn("@pys_dyn_int(i64 0)", self.function_ir(ir, "main.init"))

    def test_accepting_unchecked_argument_types_is_detected(self):
        original = Gen.scalar_call_types

        def unchecked(generator, function, args):
            return ["int", "int"] if function.node.s == "target" else original(generator, function, args)

        with patch.object(Gen, "scalar_call_types", unchecked):
            with self.assertRaises(AssertionError):
                NumericCallIdentityTests().test_unknown_arguments_keep_early_identity_snapshots()


class ScalarGlobalIdentityTests(unittest.TestCase):
    def reads(self, body, extra="", signature=""):
        generators = []
        reads = {}
        original_read = Gen.dyn_id_read

        def make_generator():
            generator = Gen()
            generators.append(generator)
            reads[id(generator)] = []
            return generator

        def read(generator, value, slot):
            if generator.curfn.node.s == "target" and slot.startswith("@") and not generator.drying:
                reads[id(generator)].append(generator.fn.scalar_reads)
            return original_read(generator, value, slot)

        source = ("# pystachy: dynamic-any\nfrom typing import Any\nG = 1000\nF = 1.5\nH = 0\n" +
                  "def change() -> None:\n    global G\n    G = 1000\n" +
                  extra + "def target(" + signature + ") -> int:\n" +
                  "\n".join("    " + line for line in body.splitlines()) + "\n")
        with patch.object(driver, "Gen", make_generator), patch.object(Gen, "dyn_id_read", read):
            driver.compile_program("scalar_identity_probe.py", source, [str(ROOT / "lib")], "")
        self.assertTrue(all(not fn.scalar_reads for fn in generators[-1].fns))
        result = reads[id(generators[-1])]
        self.assertTrue(result, "the target must actually read a numeric global")
        return result

    def test_scalar_consumers_elide_global_snapshots(self):
        bodies = [
            "return G * 17 + 3",
            "global G\nG += 1\nreturn G + 1",
            "total = 0\ntotal += int(F)\nreturn total",
            "return int(-F) + bool(G)",
        ]
        for body in bodies:
            with self.subTest(body=body):
                self.assertTrue(all(self.reads(body)))

    def test_open_or_publishing_consumers_keep_snapshots(self):
        cases = [
            ("return G", "", ""),
            ("global H\nH = G\nreturn 0", "", ""),
            ("global H\nreturn (H := G) + 1", "", ""),
            ("return G + callback()", "def callback() -> int:\n    return 1\n", ""),
            ("result: Any = G + x\nreturn 1", "", "x: Any"),
            ("return float(G) + 1", "def float(x: Any) -> int:\n    return 1\n", ""),
            ("return G if True else H", "", ""),
            ("items = [G]\nreturn items[0]", "", ""),
        ]
        for body, extra, signature in cases:
            with self.subTest(body=body):
                self.assertFalse(any(self.reads(body, extra, signature)))

    def test_global_type_cannot_override_an_unbound_local(self):
        generator = Gen()
        generator.gtypes["G"] = "int"
        generator.assigned["G"] = True
        self.assertFalse(generator.scalar_read_value(mk("name", "G", 0, [])))

    def test_builtin_aliases_and_pending_globals_block_the_proof(self):
        node = mk("call", "", 0, [mk("name", "int", 0, []), mk("name", "G", 0, [])])
        for location in ("assigned", "aliases", "fglobals"):
            generator = Gen()
            generator.gtypes["G"] = "int"
            getattr(generator, location)["int"] = True if location == "assigned" else "other"
            with self.subTest(location=location):
                self.assertFalse(generator.scalar_read_value(node))
        generator = Gen()
        self.assertFalse(generator.scalar_read_value(mk("future_syntax", "", 0, [])))

    def test_restart_and_failure_restore_the_scoped_flag(self):
        original = Gen.arith
        for body in ("return G + 1", "global G\nG += 1\nreturn G"):
            for failure in (Rejoin, RuntimeError):
                held = []

                def fail_once(generator, *args, held=held, failure=failure, **kwargs):
                    if generator.curfn.node.s == "target" and generator.fn.scalar_reads and not held:
                        held.append(generator.fn)
                        raise failure()
                    return original(generator, *args, **kwargs)

                with self.subTest(body=body, failure=failure.__name__):
                    with patch.object(Gen, "arith", fail_once):
                        if failure is RuntimeError:
                            with self.assertRaises(RuntimeError):
                                self.reads(body)
                        else:
                            self.reads(body)
                    self.assertEqual(len(held), 1)
                    self.assertFalse(held[0].scalar_reads)
                    # A later hosted compilation still requires a bare global's snapshot.
                    self.assertEqual(self.reads("return G"), [False])

    def test_unchecked_scalar_proof_is_detected(self):
        with patch.object(Gen, "scalar_read_value", return_value=True):
            with self.assertRaises(AssertionError):
                ScalarGlobalIdentityTests().test_open_or_publishing_consumers_keep_snapshots()


class CellIdentityAllocationTests(unittest.TestCase):
    def test_cells_keep_the_existing_allocation_class(self):
        path = ROOT / "tests/ir/dynany_identity_cells.py"
        ir = driver.compile_program(str(path), path.read_text(), [str(ROOT / "lib")], "")
        for name in ("integer", "floating", "observed"):
            body = re.search(r"define[^\n]*@f\." + name + r"\([^\n]*\n(.*?)\n}", ir, re.S)
            self.assertIsNotNone(body)
            # One shared cell and one one-capture environment. Like gc_box, the
            # cell requests 15 bytes to use the allocator's 16-byte scanned slot;
            # requesting 16 would silently grow it into the 24-byte class.
            self.assertEqual(re.findall(r"@pys_alloc\(i64 (\d+)\)", body[1]), ["15", "8"])


class JoinedIdentityCostTests(unittest.TestCase):
    def test_union_arithmetic_stays_raw_and_dynamic_typed_stars_keep_objects(self):
        source = '''# pystachy: dynamic-any
def arithmetic(n: int) -> int | float:
    value: int | float = 0
    for i in range(n):
        value = value + i
    return value

def typed_star() -> list[int]:
    value = int("1000")
    return [value, *[2], value]

print(arithmetic(2), typed_star())
'''
        ir = driver.compile_program("joined_identity_cost.py", source, [str(ROOT / "lib")], "")
        arithmetic = re.search(r"define[^\n]*@f\.arithmetic\([^\n]*\n(.*?)\n}", ir, re.S)
        starred = re.search(r"define[^\n]*@f\.typed_star\([^\n]*\n(.*?)\n}", ir, re.S)
        self.assertIsNotNone(arithmetic)
        self.assertIsNotNone(starred)
        self.assertNotRegex(arithmetic[1], r"(?:call|invoke) ptr @pys_dyn_(?:int|float)\(")
        self.assertEqual(starred[1].count("@pys_list_append_identity("), 3)
        self.assertNotIn("@pys_list_append(", starred[1])
        # Numeric list identity is opt-in at graph level; ordinary typed stars still box nothing.
        ordinary = driver.compile_program("ordinary_joined_cost.py", source.replace("# pystachy: dynamic-any\n", ""), [str(ROOT / "lib")], "")
        self.assertNotRegex(ordinary, r"(?:call|invoke) ptr @pys_dyn_(?:int|float)\(")
        self.assertNotIn("@pys_list_append_identity", ordinary)

    def test_non_boxable_union_cells_remain_accepted(self):
        # Reading a numeric member must not box a different, typed-container member
        # merely because the same cell can hold either representation.
        source = '''# pystachy: dynamic-any
def outer() -> int:
    value: int | list[int] = [7]
    def read() -> int:
        if isinstance(value, int):
            return value
        return value[0]
    return read()
print(outer())
'''
        ir = driver.compile_program("joined_identity_boundary.py", source, [str(ROOT / "lib")], "")
        read = re.search(r"define[^\n]*@c\.0\.1\([^\n]*\n(.*?)\n}", ir, re.S)
        self.assertIsNotNone(read)
        self.assertNotRegex(read[1], r"(?:call|invoke) ptr @pys_dyn_(?:int|float)\(")
        # The list member's items have boxes from construction; reading one returns that object.
        self.assertIn("@pys_list_get_identity", read[1])


class FoldedIntegerIdentityTests(unittest.TestCase):
    def test_literal_operations_match_cpython_with_int64_boundaries(self):
        values = [-2**63, -2**63 + 1, -1000, -1, 0, 1, 3, 1000, 2**63 - 1]
        for op in ["+", "-", "*", "//", "%", "**", "<<", ">>", "&", "|", "^"]:
            for a in values:
                for b in values if op not in ["**", "<<", ">>"] else [-1, 0, 1, 3, 62, 63, 64]:
                    with self.subTest(op=op, a=a, b=b):
                        got = folded_int(op, str(a), str(b))
                        if op in ["**", "<<", ">>"] and not 0 <= b <= 63:
                            self.assertEqual(got, "")
                            continue
                        try:
                            expected = eval(f"({a}) {op} ({b})")
                        except (ValueError, ZeroDivisionError):
                            self.assertEqual(got, "")
                            continue
                        self.assertEqual(got, str(expected) if -2**63 <= expected < 2**63 else "")

    def test_large_exponents_and_counts_are_not_evaluated(self):
        for op in ["**", "<<", ">>"]:
            self.assertEqual(folded_int(op, "2", str(2**63 - 1)), "")
        self.assertEqual(folded_int("/", "1000", "2"), "")

    def test_non_boxable_global_unions_remain_accepted(self):
        source = '''# pystachy: dynamic-any
value: int | list[int] = [7]
def read() -> int:
    local = value
    if isinstance(local, int):
        return local
    return local[0]
print(read())
'''
        driver.compile_program("global_identity_boundary.py", source, [str(ROOT / "lib")], "")


if __name__ == "__main__":
    unittest.main()
