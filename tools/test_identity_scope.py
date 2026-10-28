"""Numeric identity tracking stays inside the modules that can observe it (#969).

A program that does not opt in to dynamic Any but imports a module that does (tomllib) keeps
its own classes' layouts and its functions' code: no companion boxes, box slots or boxing calls.
A value that crosses into tracking code and could carry a number's identity makes the compiler
start again with every module tracking it, which must give the same IR as tracking from the start
(docs/dynamic-any.md#identity-scope).
"""
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pystachy_compiler import driver, gen  # noqa: E402

# a number's box made, or a list item's companion read or written
BOXING = re.compile(r"@pys_dyn_(int|float)(_box)?\(|@pys_list_\w*identity\(")

COUNTER = """
class Counter:
    def __init__(self) -> None:
        self.pos = 0
        self.n = 0

    def step(self, k: int) -> None:
        for i in range(k):
            self.pos = self.pos + i
            self.n += 1


def total(xs: list[int]) -> int:
    t = 0
    for x in xs:
        y = x
        t += y
    return t


c = Counter()
c.step(1000)
print(c.pos, c.n, total([1000, 2000]))
"""

SCOPELIB = """# pystachy: dynamic-any
from typing import Any, Callable

kept: list[Any] = []
LIMIT = 1000


class Pair:
    def __init__(self, a: int) -> None:
        self.a = a


def keep(x: Any) -> None:
    kept.append(x)


def half(n: int) -> int:
    return n // 2


def table(text: str) -> dict[str, Any]:
    n = int(text)
    return {"a": n, "b": n, "s": text}


def same(a: Any, b: Any) -> bool:
    return a is b


def call(f: Callable[[str], Any], text: str) -> Any:
    return f(text)


def make() -> Pair:
    return Pair(LIMIT)
"""


def functions(ir):
    # each function the IR defines, by its symbol, with its body's text
    found = {}
    name = ""
    body = []
    for line in ir.splitlines():
        if line.startswith("define "):
            name = re.sub(r"\(.*", "", line).split(" ")[-1]
            body = []
        elif line == "}" and name != "":
            found[name] = "\n".join(body)
            name = ""
        elif name != "":
            body.append(line)
    return found


class IdentityScopeTests(unittest.TestCase):
    def compile(self, source, helper=True, full=False):
        # the IR and every pass's Gen; helper: scopelib (above) on the module path; full: track
        # identity everywhere from the start
        generators = []
        original = driver.Gen

        def make_generator():
            generator = original()
            generators.append(generator)
            return generator

        def no_split(self, mods):
            self.idoff = {}

        with tempfile.TemporaryDirectory() as tmp:
            if helper:
                Path(tmp, "scopelib.py").write_text(SCOPELIB)
            with patch.object(driver, "Gen", make_generator):
                if full:
                    with patch.object(gen, "dynamic_identity_modules", no_split):
                        ir = driver.compile_program("identity_scope_probe.py", source, [tmp, str(ROOT / "lib")], "")
                else:
                    ir = driver.compile_program("identity_scope_probe.py", source, [tmp, str(ROOT / "lib")], "")
        return ir, generators

    def main_functions(self, generator, ir):
        # the IR of the functions of the main program's own code
        mine = {f.f.ll for f in generator.fns if generator.fn_home(f.f) == ""}
        return {k: v for k, v in functions(ir).items() if k in mine}

    def test_importing_tomllib_keeps_typed_layout_and_code(self):
        plain, _ = self.compile(COUNTER, helper=False)
        ir, generators = self.compile("import tomllib\n" + COUNTER + "print(len(tomllib.loads('a = 1')))\n", helper=False)
        final = generators[-1]
        self.assertEqual(final.idevent, "")
        self.assertIn("", final.idoff)
        self.assertNotIn("tomllib._parser", final.idoff)
        self.assertIn("%C.Counter = type {i64, i64}", plain)
        self.assertIn("%C.Counter = type {i64, i64}", ir)
        mine = self.main_functions(final, ir)
        self.assertIn("@m.Counter.step", mine)
        for name, body in mine.items():
            with self.subTest(function=name):
                self.assertIsNone(BOXING.search(body))
                self.assertNotIn(".box.", body)
                self.assertNotIn(".boxgen.", body)
        # (tomllib's own code still tracks identity)
        self.assertIn("call ptr @pys_dyn_int_box", ir)

    def test_identity_free_exchanges_keep_the_split(self):
        programs = [
            "import scopelib\nt = scopelib.table('5000')\nprint(scopelib.same(t['a'], t['b']))\n",
            "import scopelib\nt = scopelib.table('5000')\na = t['a']\nprint(scopelib.same(a, t['b']))\n",
            "import scopelib\nprint(scopelib.call(lambda s: s + '!', 'x'))\n",
            "import scopelib\nn = scopelib.LIMIT + 1\nprint(n, scopelib.table('7')['a'])\n",
            "import scopelib\nscopelib.keep('text')\nscopelib.keep(1000)\nprint(len(scopelib.kept))\n",
        ]
        for source in programs:
            with self.subTest(source=source):
                _, generators = self.compile(source)
                self.assertEqual([g.idevent for g in generators], [""])
                self.assertIn("", generators[0].idoff)

    def test_crossings_track_identity_everywhere(self):
        # Each crossing alone: a number, an object, a function or a field of the code that does
        # not track identity reaching code that does, or the reverse
        programs = [
            ("n = int('1000')\nscopelib.keep(n)\n", "number as an Any value"),
            ("def f(x: int) -> None:\n    scopelib.keep(x)\nf(1000)\n", "number as an Any value"),
            ("n = int('7')\nprint(scopelib.half(n))\n", "call of scopelib$half()"),
            ("class B:\n    def __init__(self) -> None:\n        self.n = 1\nscopelib.keep(B())\n", "B object as an Any value"),
            ("p = scopelib.Pair(5)\nprint(p.a)\n", "attribute of scopelib$Pair"),
            ("p = scopelib.make()\nprint(p.a)\n", "call of scopelib$make()"),
            ("t = scopelib.table('5')\nn: int = t['a']\nscopelib.keep(n)\n", "number as an Any value"),
            ("scopelib.LIMIT = int('5')\n", "module variable scopelib$LIMIT"),
            ("print(scopelib.call(lambda s: len(s), 'x'))\n", "number as an Any value"),
        ]
        for body, why in programs:
            with self.subTest(body=body):
                _, generators = self.compile("import scopelib\n" + body)
                self.assertEqual(len(generators), 2)
                self.assertTrue(generators[0].idevent.startswith(why), generators[0].idevent)
                self.assertTrue(generators[1].idfull)
                self.assertEqual(generators[1].idoff, {})

    def test_fallback_compiles_as_full_tracking_does(self):
        source = ("import scopelib\n" + COUNTER +
                  "n = int('1000')\nscopelib.keep(n)\nscopelib.keep(c.pos)\nprint(scopelib.same(scopelib.kept[0], scopelib.kept[1]))\n")
        ir, generators = self.compile(source)
        self.assertTrue(generators[-1].idfull)
        full, _ = self.compile(source, full=True)
        self.assertEqual(ir, full)
        self.assertIn("%C.Counter = type {i64, i64, ptr, ptr}", ir)

    def test_programs_that_opt_in_track_identity_everywhere(self):
        ir, generators = self.compile("# pystachy: dynamic-any\n" + COUNTER)
        self.assertEqual([g.idoff for g in generators], [{}])
        self.assertIn("%C.Counter = type {i64, i64, ptr, ptr}", ir)

    def test_dropping_the_crossing_checks_is_detected(self):
        # Without identity_call's check, a number passed to tracking code would lose its object.
        def no_check(self, f):
            return None

        with patch.object(gen, "dynamic_identity_call", no_check):
            with self.assertRaises(AssertionError):
                IdentityScopeTests().test_crossings_track_identity_everywhere()


if __name__ == "__main__":
    unittest.main()
