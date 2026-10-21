"""Comparison methods that do not compile for an Any operand are declined in one more pass (#801).

The CPython-hosted compiler compiles each program in this process: a program with any number of
such methods takes two passes, and each failed call leaves nothing of Gen's state that the rest of
its pass reads but what the next pass, a fresh Gen, never sees (gen_dyn_xcall).
Run with python3 -m unittest discover -s tools -p test_dynany_declines.py.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pystachy_compiler import diagnostics, driver  # noqa: E402
from src.pystachy_compiler.gen import Gen  # noqa: E402

# Gen's tables that a failed call may add to: what the functions it compiled entered, which only
# its pass sees, and the methods that pass declines (newx)
GROWS = {"building", "called", "compiled", "dynfns", "dynkeys", "dynlines", "holes", "newx", "vnodes", "wide"}
# and the nodes Gen keeps of the last method call, display and expression statement it compiled
MARKS = {"mcall", "soft", "stmtexpr"}


def declining(k: int) -> str:
    # k classes whose __eq__ compares a typed list with an Any value's field, each boxed into Any
    out = ["# pystachy: dynamic-any", "from typing import Any", ""]
    for i in range(k):
        out += [f"class B{i}:", "    def __init__(self, n: int) -> None:", "        self.items = [n]", "",
                "    def __eq__(self, other):", "        return self.items == other.items", ""]
    out += ["xs: list[Any] = []"] + [f"xs.append(B{i}(1))" for i in range(k)]
    out.append("print(len(xs) == 0 or xs[0] == xs[0], len(xs))")
    return "\n".join(out) + "\n"


# methods whose calls fail in other statements and expressions: an if, an and after `is None`, an
# assignment, a template function's body, a list display's comprehension, a list typed by a later
# append, an ordering; the class that comes last compiles its method for an Any operand
CONTEXTS = '''# pystachy: dynamic-any
from typing import Any


def same(a, b):
    return a == b.items


class InIf:
    def __init__(self, n: int) -> None:
        self.n = n
        self.items = [n]

    def __eq__(self, other):
        if self.n > 0:
            return self.items == other.items
        return False


class NoneTest:
    def __init__(self, n: int) -> None:
        self.items = [n]
        self.tag: str | None = None

    def __eq__(self, other):
        return self.tag is None and self.items == other.items


class Assign:
    def __init__(self, n: int) -> None:
        self.items = [n]

    def __eq__(self, other):
        mine: list[int] = self.items
        theirs = other.items
        return mine == theirs


class Generic:
    def __init__(self, n: int) -> None:
        self.items = [n]

    def __eq__(self, other):
        return same(self.items, other)


class Comp:
    def __init__(self, n: int) -> None:
        self.items = [n]

    def __eq__(self, other):
        return [i * 2 for i in self.items] == other.items


class Later:
    def __init__(self, n: int) -> None:
        self.items = [n]

    def __eq__(self, other):
        xs = []
        xs.append(self.items)
        return xs[0] == other.items


class Order:
    def __init__(self, n: int) -> None:
        self.items = [n]

    def __lt__(self, other):
        return self.items < other.items


class Fine:
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, other):
        if isinstance(other, int):
            return self.v == other
        return False


vals: list[Any] = [InIf(1), NoneTest(1), Assign(1), Generic(1), Comp(1), Later(1), Order(1), Fine(5)]
five: Any = 5
print([v == v for v in vals], vals[7] == five, vals[6] < vals[6])
'''


def snapshot(g: Gen) -> dict:
    out = {}
    for k, v in vars(g).items():
        if v is None or isinstance(v, (bool, int, float, str)):
            out[k] = ("value", v)
        elif isinstance(v, (list, dict)):
            out[k] = ("table", id(v), len(v))
        else:
            out[k] = ("object", id(v))
    return out


class DeclineTests(unittest.TestCase):
    def compile(self, src: str) -> tuple[int, list[str], int]:
        # (the passes, what failed calls left of Gen's state that they should not have, and how
        # many calls failed)
        made: list[int] = []
        left: list[str] = []
        failed: list[int] = []

        class Counting(Gen):
            def __init__(self) -> None:
                made.append(1)
                super().__init__()

        xcall = Gen.dyn_xcall

        def checked(g: Gen, *args):
            before = snapshot(g)
            r = xcall(g, *args)
            if r == "":
                failed.append(1)
                after = snapshot(g)
                for k in sorted(set(before) | set(after)):
                    b, a = before.get(k), after.get(k)
                    if b == a or k in MARKS:
                        continue
                    if k in GROWS and b is not None and a is not None and b[:2] == a[:2]:
                        continue
                    left.append(f"{k}: {b} -> {a}")
            return r

        made_gen, saved = driver.Gen, diagnostics.SRC
        driver.Gen = Counting
        Gen.dyn_xcall = checked
        try:
            with tempfile.TemporaryDirectory() as d:
                path = os.path.join(d, "prog.py")
                with open(path, "w") as f:
                    f.write(src)
                diagnostics.SRC = path
                driver.compile_program(path, src, [d, str(ROOT / "lib")], "")
        finally:
            driver.Gen = made_gen
            Gen.dyn_xcall = xcall
            diagnostics.SRC = saved
        return len(made), left, len(failed)

    def test_two_passes(self):
        # (main took k + 1: a pass for each declined method, and the last)
        for k, passes in ((0, 1), (1, 2), (4, 2), (16, 2)):
            with self.subTest(k=k):
                got, left, failed = self.compile(declining(k))
                self.assertEqual((got, failed), (passes, k))
                self.assertEqual(left, [])

    def test_state_after_failed_calls(self):
        # (seven calls fail, each in another kind of statement or expression; Fine's compiles)
        got, left, failed = self.compile(CONTEXTS)
        self.assertEqual((got, failed), (2, 7))
        self.assertEqual(left, [])

    def test_recorded_programs(self):
        for name, failed in (("dynany_eq_declines.py", 6), ("dynany_eq_template.py", 3)):
            with self.subTest(name=name):
                src = (ROOT / "tests" / "programs" / "inference" / name).read_text()
                self.assertEqual(self.compile(src), (2, [], failed))


if __name__ == "__main__":
    unittest.main()
