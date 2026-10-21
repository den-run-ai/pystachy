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
from src.pystachy_compiler.ir import ClassInfo, FnInfo  # noqa: E402

# Gen's tables that a failed call may add entries to, changing none it found: what the functions
# it compiled entered, which only its pass sees, and the methods that pass declines (newx)
GROWS = {"building", "called", "compiled", "dynfns", "dynkeys", "dynlines", "holes", "newx", "vnodes", "wide"}
# the nodes Gen keeps of the last method call, display and expression statement it compiled
MARKS = {"mcall", "soft", "stmtexpr"}
# and a template's instances (FnInfo.insts), where the one the failed call made stays, half
# compiled: a later call with its types fails as the failed call did, in a pass that compiles it
INSTS = "insts"


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


def sig(v) -> tuple:
    if v is None or isinstance(v, (bool, int, float, str)):
        return ("value", v)
    if isinstance(v, (list, dict)):
        return ("table", id(v), len(v))
    return ("object", id(v))


def entries(v) -> list:
    return list(v.items()) if isinstance(v, dict) else list(enumerate(v)) if isinstance(v, list) else []


def snapshot(g: Gen) -> tuple[dict, dict]:
    # Gen's attributes and their tables' entries, and the fields of every FnInfo and ClassInfo
    # that they hold (also through those objects' own fields and tables) and their tables'
    # entries: where -> what is there (a value, or a table's or object's identity, and a table's
    # size); and each object's name, for messages
    out: dict[tuple, tuple] = {}
    names: dict[int, str] = {}
    todo = []
    for k, v in vars(g).items():
        out[("gen", k)] = sig(v)
        todo.append(v)
        for kk, vv in entries(v):
            out[("gen", k, kk)] = sig(vv)
            todo.append(vv)
    while todo:
        o = todo.pop()
        if not isinstance(o, (FnInfo, ClassInfo)) or id(o) in names:
            continue
        names[id(o)] = f"{type(o).__name__} {getattr(o, 'll', '') or getattr(o, 'name', '')}"
        for k, v in vars(o).items():
            out[("obj", id(o), k)] = sig(v)
            todo.append(v)
            for kk, vv in entries(v):
                out[("obj", id(o), k, kk)] = sig(vv)
                todo.append(vv)
    return out, names


def changes(before: tuple[dict, dict], after: tuple[dict, dict]) -> list[str]:
    # what a failed call changed of Gen's state that it may not: anything but new entries of
    # GROWS's tables and of a template's instances, the objects it made, and MARKS
    (b0, names0), (a0, _) = before, after
    out = []
    for w in set(b0) | set(a0):
        b, a = b0.get(w), a0.get(w)
        if b == a:
            continue
        grown = b is not None and a is not None and b[0] == a[0] == "table" and b[1] == a[1] and a[2] >= b[2]
        if w[0] == "gen":
            if w[1] in MARKS or (w[1] in GROWS and (len(w) == 3 and b is None or len(w) == 2 and grown)):
                continue
            where = f"Gen.{w[1]}" + (f"[{w[2]!r}]" if len(w) == 3 else "")
        else:
            if w[1] not in names0 or (w[2] == INSTS and (len(w) == 4 and b is None or len(w) == 3 and grown)):
                continue  # (an object the failed call made, or a template's new instance)
            where = f"{names0[w[1]]}.{w[2]}" + (f"[{w[3]!r}]" if len(w) == 4 else "")
        out.append(f"{where}: {b} -> {a}")
    return sorted(out)


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
                left.extend(changes(before, snapshot(g)))
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
