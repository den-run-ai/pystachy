"""Identity elision must stay inside its numeric function or scalar consumer proof."""
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

    def test_observable_or_open_bodies_keep_slots(self):
        bodies = [
            "observed: Any = n\nreturn m",
            "observed: Any = n\nreturn id(observed)",
            "return consume(n)",
            "items = [n]\nreturn items[0]",
            "print(n)\nreturn m",
            "annotated: int = n\nreturn annotated",
            "return GLOBAL + m",
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


if __name__ == "__main__":
    unittest.main()
