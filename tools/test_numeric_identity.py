"""Identity-slot elision must stay inside its closed numeric function boundary."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pystachy_compiler import driver, functions  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
