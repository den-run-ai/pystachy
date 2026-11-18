"""A bytearray's buffer is read only through lib/_pystachy_bytearray.py's primitives.

The compiler takes a bytes object's bytes never to change: it reuses reads of them (a runtime
call without memory effects, such as pys_bytes_get, is value-numbered by its operands). A
bytearray keeps its bytes in a buffer of that type and writes it in place, so no code may read a
buffer as a bytes object: analysis.buffer_escape finds such a read in the module, which the
compiler rejects. Other modules reach neither the buffer nor the length (Gen.field). A module that
names bytearray only in annotations bytes | bytearray that the compiler types at each call loads
no class (analysis.bytearray_values).
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pystachy_compiler.analysis import buffer_escape, bytearray_values  # noqa: E402
from src.pystachy_compiler.lexer import Lexer  # noqa: E402
from src.pystachy_compiler.parser import Parser  # noqa: E402


def module(src):
    return Parser(Lexer(src, 1).file()).module()


class BufferEscape(unittest.TestCase):
    def test_the_module_reads_its_buffers_through_its_primitives(self):
        self.assertIsNone(buffer_escape(module((ROOT / "lib" / "_pystachy_bytearray.py").read_text())))

    def test_reads_elsewhere_are_found(self):
        cases = {
            "def f(b):\n    buf = b._b\n    return 0\n": 2,  # (a local alias of the buffer)
            "def f(b):\n    return b._b[0]\n": 2,  # (an index of it as a bytes)
            "def f(b):\n    return len(b._b)\n": 2,
            "def f(b):\n    return b._b\n": 2,  # (the live buffer handed out)
            "def f(b):\n    g(b._b)\n": 2,
            "def f(b):\n    __pys_ba_put(g(b._b), 0, 1)\n": 2,  # (an argument's argument)
            "def f(b):\n    x = __pys_ba_new(3)\n    y = x\n    return y\n": 3,
            "def f(b):\n    x = __pys_ba_new(3)\n    __pys_ba_put(x, 0, 1)\n    return x[0]\n": 4,
            "def f(b):\n    x = __pys_ba_new(3)\n    x = b\n    return 0\n": 3,
            "class C:\n    def m(self):\n        return self._b.find(b'a')\n": 3,
        }
        for src, line in cases.items():
            with self.subTest(src=src):
                bad = buffer_escape(module(src))
                self.assertIsNotNone(bad)
                self.assertEqual(bad.line, line)

    def test_the_places_that_may_take_a_buffer(self):
        for src in ("def f(b):\n    __pys_ba_put(b._b, 0, 1)\n    return __pys_ba_get(b._b, 0)\n",
                    "def f(b, c):\n    b._b = c._b\n    c._b = b''\n",
                    "def f(b, n):\n    x = __pys_ba_new(n)\n    __pys_ba_copy(x, 0, b._b, 0, n)\n    b._b = x\n",
                    "def f(b, n):\n    r = __pys_ba_new(n)\n    __pys_ba_copy(r, 0, b._b, 0, n)\n    return r\n",
                    "def f(b):\n    return __pys_ba_cap(b._b) - b._n\n",
                    "class bytearray:\n    def m(self):\n        __pys_ba_put(self._b, 0, 1)\n"):  # (mangled)
            with self.subTest(src=src):
                self.assertIsNone(buffer_escape(module(src)))


class ClassImport(unittest.TestCase):
    def test_annotations_that_each_call_types_load_no_class(self):
        for src in ("def f(x: bytes | bytearray) -> int:\n    return len(x)\n",
                    "def f(x: bytearray | bytes) -> bytes | bytearray:\n    return x\n",
                    "class C:\n    def m(self, x: bytes | bytearray) -> int:\n        return 0\n",
                    "class C:\n    @staticmethod\n    def m(x: bytes | bytearray) -> int:\n        return 0\n"):
            with self.subTest(src=src):
                self.assertFalse(bytearray_values(module(src), False))

    def test_other_mentions_load_the_class(self):
        for src in ("x = bytearray(3)\n",
                    "def f(x: bytes) -> bytes | bytearray:\n    return x\n",  # (a return alone keeps its annotation)
                    "class C:\n    def __init__(self, x: bytes | bytearray) -> None:\n        self.n = 0\n",
                    "class C:\n    @property\n    def p(self, x: bytes | bytearray = b'') -> int:\n        return 0\n",
                    "class C:\n    def m(x: bytes | bytearray) -> int:\n        return 0\n",  # (a method's first)
                    "def f(*xs: bytes | bytearray) -> int:\n    return 0\n",
                    "def f() -> None:\n    x: bytes | bytearray = b''\n",
                    "def f(x: bytes) -> bool:\n    return isinstance(x, bytes | bytearray)\n",
                    "def f(x: list[bytes | bytearray]) -> int:\n    return 0\n"):
            with self.subTest(src=src):
                self.assertTrue(bytearray_values(module(src), False))


if __name__ == "__main__":
    unittest.main()
