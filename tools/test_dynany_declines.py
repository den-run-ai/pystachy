"""Comparison methods that do not compile for an Any operand are declined in one more pass (#801).

The CPython-hosted compiler compiles each program in this process: a program with any number of
such methods takes two passes, and each failed call leaves nothing of Gen's state that the rest of
its pass reads but what the next pass, a fresh Gen, never sees (gen_dyn_xcall). The compiler's
own source shows the state that code changes and changes back, which an error leaves changed:
Frame and Transient must hold all of it.
Run with python3 -m unittest discover -s tools -p test_dynany_declines.py.
"""
import ast
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "pystachy_compiler"
sys.path.insert(0, str(ROOT))

from src.pystachy_compiler import diagnostics, driver  # noqa: E402
from src.pystachy_compiler.gen import Gen  # noqa: E402
from src.pystachy_compiler.ir import ClassInfo, FnInfo  # noqa: E402

# Gen's tables that a failed call may add entries to, changing none it found: what the functions
# it compiled entered, which only its pass sees, the closures they define (by their def sites in
# those functions), and the methods that pass declines (newx)
GROWS = {"building", "called", "clokeys", "closures", "compiled", "dynfns", "dynkeys", "dynlines", "holes", "newx", "vnodes", "wide"}
# and a template's instances (FnInfo.insts), where the one the failed call made stays, half
# compiled: a later call with its types fails as the failed call did, in a pass that compiles it
INSTS = "insts"
# Gen's fields that code changes and changes back but that hold no state of what is being compiled:
# caches, which only ever learn something of the whole program
CACHES = {"cmexit": "whether a class of the program defines __exit__, found once (cm_exits)"}


def declining(k: int) -> str:
    # k classes whose __eq__ compares a typed list with an Any value's field, each boxed into Any
    out = ["# pystachy: dynamic-any", "from typing import Any", ""]
    for i in range(k):
        out += [f"class B{i}:", "    def __init__(self, n: int) -> None:", "        self.items = [n]", "",
                "    def __eq__(self, other):", "        return self.items == other.items", ""]
    out += ["xs: list[Any] = []"] + [f"xs.append(B{i}(1))" for i in range(k)]
    out.append("print(len(xs) == 0 or xs[0] == xs[0], len(xs))")
    return "\n".join(out) + "\n"


# methods whose calls fail in other statements and expressions: (the class, what its __init__ sets
# besides self.items, the method, its body); the class that comes last compiles its method for an
# Any operand
CASES = [
    # an if, an and after `is None`, an annotated assignment, a template function's body, a list
    # display's comprehension, a list typed by a later append, an ordering
    ("InIf", "self.n = n", "__eq__", "if self.n > 0:\n    return self.items == other.items\nreturn False"),
    ("NoneTest", "self.tag: str | None = None", "__eq__", "return self.tag is None and self.items == other.items"),
    ("Assign", "", "__eq__", "mine: list[int] = self.items\ntheirs = other.items\nreturn mine == theirs"),
    ("Generic", "", "__eq__", "return same(self.items, other)"),
    ("Comp", "", "__eq__", "return [i * 2 for i in self.items] == other.items"),
    ("Later", "", "__eq__", "xs = []\nxs.append(self.items)\nreturn xs[0] == other.items"),
    ("Order", "", "__lt__", "return self.items < other.items"),
    # a loop's body, nested loops, a for loop's else block, a generator expression's loop, a
    # template's loop, a loop in a try statement
    ("InFor", "", "__eq__", "for x in self.items:\n    return self.items == other.items\nreturn False"),
    ("InWhile", "", "__eq__", "while True:\n    return self.items == other.items"),
    ("InNested", "", "__eq__", "for x in self.items:\n    for y in self.items:\n        if x == y:\n            return self.items == other.items\nreturn False"),
    ("InForElse", "", "__eq__", "for x in self.items:\n    if x > 100:\n        break\nelse:\n    return self.items == other.items\nreturn False"),
    ("InGenexp", "", "__eq__", "return any(self.items == other.items for _ in range(1))"),
    ("InLoopy", "", "__eq__", "return loopy(self.items, other)"),
    ("InLoopInTry", "", "__eq__", "try:\n    for x in self.items:\n        return self.items == other.items\nexcept ValueError:\n    pass\nreturn False"),
    # a try statement's body, its handler and its finally block, a with block, a lambda, a def,
    # an assert, an f-string and an assignment expression
    ("InTry", "", "__eq__", "try:\n    return self.items == other.items\nexcept ValueError:\n    return False"),
    ("InExcept", "", "__eq__", "try:\n    raise ValueError('x')\nexcept ValueError:\n    return self.items == other.items"),
    ("InFinally", "", "__eq__", "r = False\ntry:\n    pass\nfinally:\n    r = self.items == other.items\nreturn r"),
    ("InWith", "", "__eq__", "with Ctx():\n    return self.items == other.items"),
    ("InLambda", "", "__eq__", "f = lambda: self.items == other.items\nreturn f()"),
    ("InDef", "", "__eq__", "def inner() -> bool:\n    return self.items == other.items\nreturn inner()"),
    ("InAssert", "", "__eq__", "assert self.items == other.items\nreturn True"),
    ("InFstring", "", "__eq__", "return f'{self.items == other.items}' == 'True'"),
    ("InWalrus", "", "__eq__", "if (r := self.items == other.items):\n    return r\nreturn False"),
    ("Fine", "self.v = n", "__eq__", "if isinstance(other, int):\n    return self.v == other\nreturn False"),
]


def contexts() -> str:
    out = ["# pystachy: dynamic-any", "from typing import Any", "", "",
           "def same(a, b):", "    return a == b.items", "", "",
           "def loopy(a, b):", "    for x in a:", "        return a == b.items", "    return False", "", "",
           "class Ctx:", '    def __enter__(self) -> "Ctx":', "        return self", "",
           "    def __exit__(self, a, b, c) -> None:", "        pass", "", ""]
    for name, init, m, body in CASES:
        out += [f"class {name}:", "    def __init__(self, n: int) -> None:", "        self.items = [n]"]
        out += ["        " + init] if init != "" else []
        out += ["", f"    def {m}(self, other):"] + ["        " + x for x in body.split("\n")] + ["", ""]
    names = [c[0] for c in CASES]
    fine, order = names.index("Fine"), names.index("Order")
    out += ["vals: list[Any] = [" + ", ".join(f"{n}(1)" for n in names) + "]", "five: Any = 5",
            f"print([v == v for v in vals], vals[{fine}] == five, vals[{order}] < vals[{order}])"]
    return "\n".join(out) + "\n"


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
    # GROWS's tables and of a template's instances, and the objects it made
    (b0, names0), (a0, _) = before, after
    out = []
    for w in set(b0) | set(a0):
        b, a = b0.get(w), a0.get(w)
        if b == a:
            continue
        grown = b is not None and a is not None and b[0] == a[0] == "table" and b[1] == a[1] and a[2] >= b[2]
        if w[0] == "gen":
            if w[1] in GROWS and (len(w) == 3 and b is None or len(w) == 2 and grown):
                continue
            where = f"Gen.{w[1]}" + (f"[{w[2]!r}]" if len(w) == 3 else "")
        else:
            if w[1] not in names0 or (w[2] == INSTS and (len(w) == 4 and b is None or len(w) == 3 and grown)):
                continue  # (an object the failed call made, or a template's new instance)
            where = f"{names0[w[1]]}.{w[2]}" + (f"[{w[3]!r}]" if len(w) == 4 else "")
        out.append(f"{where}: {b} -> {a}")
    return sorted(out)


def self_field(n: ast.AST) -> str:
    # x, of self.x; else ""
    return n.attr if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "self" else ""


def init_fields(path: Path, cls: str) -> set[str]:
    # the fields that cls's __init__ in path gives a value
    for c in ast.parse(path.read_text()).body:
        if isinstance(c, ast.ClassDef) and c.name == cls:
            for fn in c.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == "__init__":
                    targets = [t for n in ast.walk(fn) if isinstance(n, ast.Assign) for t in n.targets]
                    targets += [n.target for n in ast.walk(fn) if isinstance(n, ast.AnnAssign)]
                    return {self_field(t) for t in targets} - {""}
    raise AssertionError(f"{path.name} defines no {cls}.__init__")


def changed_back() -> dict[str, str]:
    # the fields that a function of the compiler changes and changes back: a value it saves in a
    # local and puts back, a stack it pushes and pops, a count it raises and lowers, a field it
    # gives two constants (a flag it sets and resets); field -> such a function, for messages
    out: dict[str, str] = {}
    for path in sorted(SRC.glob("*.py")):
        for fn in ast.walk(ast.parse(path.read_text())):
            if not isinstance(fn, ast.FunctionDef):
                continue
            nodes = list(ast.walk(fn))
            assigns = [n for n in nodes if isinstance(n, ast.Assign) and len(n.targets) == 1]
            saved = {n.targets[0].id: self_field(n.value) for n in assigns if isinstance(n.targets[0], ast.Name) and self_field(n.value) != ""}
            found = {self_field(n.targets[0]) for n in assigns if isinstance(n.value, ast.Name) and saved.get(n.value.id, "") == self_field(n.targets[0]) != ""}
            calls = [(self_field(n.func.value), n.func.attr, len(n.args)) for n in nodes if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
            found |= {f for f, m, _ in calls if f != "" and m == "append"} & {f for f, m, k in calls if f != "" and m == "pop" and k == 0}
            augs = [(self_field(n.target), type(n.op)) for n in nodes if isinstance(n, ast.AugAssign)]
            found |= {f for f, op in augs if f != "" and op is ast.Add} & {f for f, op in augs if op is ast.Sub}
            consts: dict[str, set] = {}
            for n in assigns:
                if self_field(n.targets[0]) != "" and isinstance(n.value, ast.Constant):
                    consts.setdefault(self_field(n.targets[0]), set()).add(repr(n.value.value))
            found |= {f for f, vs in consts.items() if len(vs) > 1}
            for f in found:
                out.setdefault(f, f"{path.name}:{fn.name}")
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
        # (each case's call fails but Fine's, which compiles)
        got, left, failed = self.compile(contexts())
        self.assertEqual((got, failed), (2, len(CASES) - 1))
        self.assertEqual(left, [])

    def test_recorded_programs(self):
        for name, failed in (("dynany_eq_declines.py", 6), ("dynany_eq_template.py", 3)):
            with self.subTest(name=name):
                src = (ROOT / "tests" / "programs" / "inference" / name).read_text()
                self.assertEqual(self.compile(src), (2, [], failed))

    def test_transient_fields(self):
        # every field of Gen's that a function changes and changes back is a function's (Frame:
        # restore() puts it back, and each function compiles with its own tables), or Transient's,
        # which dyn_xcall puts back after an error, or a cache
        gen = init_fields(SRC / "gen.py", "Gen")
        held = init_fields(SRC / "ir.py", "Frame") | init_fields(SRC / "ir.py", "Transient") | set(CACHES)
        missing = {f: w for f, w in changed_back().items() if f in gen and f not in held}
        self.assertEqual(missing, {}, "add these to Transient (ir.py, and emission.py's gen_save_transient and gen_restore_transient)")
        self.assertEqual(init_fields(SRC / "ir.py", "Transient") - gen, set())


if __name__ == "__main__":
    unittest.main()
