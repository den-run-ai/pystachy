"""A chain of constructor calls through __class__ compiles each receiver once."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pystachy_compiler import driver
from src.pystachy_compiler.gen import Gen


class ClassValueChainTests(unittest.TestCase):
    def test_linear_receiver_visits(self):
        original = Gen.call
        for pragma in ("", "# pystachy: dynamic-any\n"):
            for depth in (2, 4, 6):
                with self.subTest(pragma=pragma, depth=depth):
                    visits = 0

                    def observe(compiler, node, *args, **kwargs):
                        nonlocal visits
                        callee = node.kids[0]
                        if callee.kind == "attr" and callee.s == "__class__":
                            visits += 1
                        return original(compiler, node, *args, **kwargs)

                    code = pragma + "class C:\n    def __init__(self) -> None:\n        self.v = 1\n"
                    code += "c = C()\nx = c" + ".__class__()" * depth + "\nprint(x.v)\n"
                    with patch.object(Gen, "call", observe):
                        driver.compile_program("chain.py", code, [], "")
                    self.assertEqual(visits, depth)
