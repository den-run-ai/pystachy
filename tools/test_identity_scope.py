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

    def test_typed_json_container_delimiters_do_not_repeat_byte_reads(self):
        ir, _ = self.compile(
            'import json\nprint(json.dumps(json.loads(\'[1,2,{"a":3,"b":4}]\')))\n',
            helper=False,
        )
        bodies = functions(ir)
        # Initial close, loop delimiter, trailing close; an object additionally
        # reads the opening key quote and colon. Re-reading the loop delimiter
        # adds one bytes_get to each function and regresses the broad JSON probe.
        for method, limit in [("array", 3), ("object", 5)]:
            with self.subTest(method=method):
                body = bodies["@m.json$_Parser." + method]
                self.assertGreater(body.count("@pys_bytes_get("), 0)
                self.assertLessEqual(body.count("@pys_bytes_get("), limit)

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

    def test_typed_field_copies_do_not_start_lazy_identity_tracking(self):
        source = """import scopelib
class Cursor:
    def __init__(self) -> None:
        self.pos = 1000

    def step(self, text: str) -> int:
        i = self.pos
        i += len(text)
        self.pos = i
        return i

c = Cursor()
print(c.step('abc'), c.pos)
"""
        ir, generators = self.compile(source)
        final = generators[-1]
        self.assertEqual([g.idevent for g in generators], [""])
        self.assertIn("", final.idoff)
        for fn in final.fns:
            if final.fn_home(fn.f) == "":
                self.assertEqual(fn.lazyflag, {})
                self.assertEqual(fn.lazybit, {})
        for body in self.main_functions(final, ir).values():
            self.assertIsNone(BOXING.search(body))
            self.assertNotIn(".box.", body)
        # The same read/write-back shape still uses main's field-sharing optimization
        # in a module that tracks identity, rather than disabling that optimization.
        _, tracked = self.compile("# pystachy: dynamic-any\n" + source)
        self.assertTrue(any(fn.lazyflag for fn in tracked[-1].fns if fn.f.ll == "@m.Cursor.step"))

    def test_promoting_literals_and_chained_stores_follow_identity_scope(self):
        source = """# pystachy: python-int
import scopelib
literal = 3000
left = right = int('4000')
print(literal, left, right)
"""
        ir, generators = self.compile(source)
        final = generators[-1]
        self.assertEqual([g.idevent for g in generators], [""])
        self.assertIn("", final.idoff)
        self.assertNotIn("@dbi.$3000", ir)
        self.assertNotIn("@g.left.box", ir)
        self.assertNotIn("@g.right.box", ir)
        for body in self.main_functions(final, ir).values():
            self.assertIsNone(BOXING.search(body))
            self.assertNotIn(".box.", body)
        crossed = source + "scopelib.keep(left)\nscopelib.keep(right)\nscopelib.keep(literal)\n"
        ir, generators = self.compile(crossed)
        self.assertTrue(generators[-1].idfull)
        full, _ = self.compile(crossed, full=True)
        self.assertEqual(ir, full)
        self.assertIn("@dbi.$3000", ir)
        self.assertIn("@g.left.box", ir)
        self.assertIn("@g.right.box", ir)

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



INERTLIB = """# pystachy: identity-inert
type Value = None | bool | int | str | list[Value] | dict[str, Value]
LIMIT = 1000

class Cursor:
    def __init__(self, text: str) -> None:
        self.pos = len(text)

    def step(self, text: str) -> str:
        i = self.pos
        i += len(text)
        self.pos = i
        return str(i)

    def number(self) -> int:
        return self.pos

def make(text: str) -> Cursor:
    return Cursor(text)

def decode(text: str) -> Value:
    n = int(text)
    return {"value": n, "again": n}

def sequence(text: str) -> list[int]:
    n = int(text)
    return [n, n]

def numeric(text: str) -> int:
    return int(text)

def same(text: str) -> str:
    return text
"""


class IdentityInertTests(unittest.TestCase):
    def compile(self, source, helper=INERTLIB, hints=True):
        generators = []
        original = driver.Gen
        original_scope = gen.dynamic_identity_modules

        def make_generator():
            generator = original()
            generators.append(generator)
            return generator

        def scope(generator, mods):
            if not hints:
                generator.idtry = False
            original_scope(generator, mods)

        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "inertlib.py").write_text(helper)
            with patch.object(driver, "Gen", make_generator), patch.object(gen, "dynamic_identity_modules", scope):
                ir = driver.compile_program("identity_inert_probe.py", source, [tmp, str(ROOT / "lib")], "")
        return ir, generators

    def test_recursive_values_and_typed_handles_keep_the_hint(self):
        source = """# pystachy: dynamic-any
import inertlib
p = inertlib.make('abc')
print(p.step('def'), inertlib.decode('1000'))
"""
        ir, generations = self.compile(source)
        self.assertEqual([g.idevent for g in generations], [""])
        self.assertEqual(generations[-1].idhint, {"inertlib": True})
        self.assertIn("%C.inertlib$Cursor = type {i64}", ir)
        for fn in generations[-1].fns:
            if generations[-1].fn_home(fn.f) == "inertlib":
                self.assertIsNone(BOXING.search(functions(ir)[fn.f.ll]))
        baseline, _ = self.compile(source, hints=False)
        self.assertIn("%C.inertlib$Cursor = type {i64, ptr}", baseline)

    def test_json_keeps_typed_parser_without_numeric_companions(self):
        source = (ROOT / "bench/pyperformance/json_loads.py").read_text()
        ir, generations = self.compile(source)
        self.assertEqual([g.idevent for g in generations], [""])
        self.assertIn("json", generations[-1].idhint)
        self.assertIn("%C.json$_Parser = type {ptr, i1, ptr, i1, i1, i64, i64, i64, i64, ptr, ptr}", ir)
        for fn in generations[-1].fns:
            if generations[-1].fn_home(fn.f) == "json":
                self.assertIsNone(BOXING.search(functions(ir)[fn.f.ll]), fn.f.ll)
        # Scanner categories must not add generic string equality or bytes indexing
        # to each decoded value: both erased identity savings in an Any consumer.
        for name, body in functions(ir).items():
            if name.startswith("@f._pystachy_json_any$_value"):
                self.assertNotIn("@pys_eq(", body)
                self.assertNotIn("@pys_bytes_get(", body)
        baseline, _ = self.compile(source, hints=False)
        self.assertIn("%C.json$_Parser = type {ptr, i1, ptr, i1, i1, i64, i64, i64, i64, ptr, ptr, ptr, ptr, ptr, ptr}", baseline)

    def test_observed_any_json_does_not_reenter_typed_container_decoder(self):
        source = (ROOT / "bench/smoke/json_decode_any.py").read_text()
        ir, generations = self.compile(source)
        self.assertEqual([g.idevent for g in generations], [""])
        self.assertIn("json", generations[-1].idhint)
        names = functions(ir)
        self.assertIn("@m.json$_Parser.scalar_value", names)
        # Falling back through value() reaches typed recursive array/object code,
        # preventing inlining even though this consumer needs Any containers only.
        for method in ["value", "array", "object"]:
            self.assertNotIn("@m.json$_Parser." + method, names)

    def test_unsafe_boundaries_restore_the_unhinted_ir(self):
        programs = [
            "print(inertlib.numeric('1000'))\n",
            "print(inertlib.sequence('1000'))\n",
            "print(inertlib.LIMIT)\n",
            "inertlib.LIMIT = int('2000')\nprint(inertlib.LIMIT)\n",
            "p = inertlib.make('abc')\nprint(p.pos)\n",
            "p = inertlib.make('abc')\np.pos = int('2000')\nprint(p.step('x'))\n",
            "p = inertlib.make('abc')\nprint(getattr(p, 'pos'))\n",
            "p = inertlib.make('abc')\nprint(dict(vars(p)))\n",
            "p: Any = inertlib.make('abc')\nprint(p.pos)\n",
            "f: Any = inertlib.same\nprint(f('x'))\n",
            "class Child(inertlib.Cursor):\n    pass\np = Child('abc')\nprint(p.step('d'))\n",
        ]
        for body in programs:
            source = "# pystachy: dynamic-any\nfrom typing import Any\nimport inertlib\n" + body
            with self.subTest(body=body):
                ir, generations = self.compile(source)
                self.assertTrue(generations[0].idevent)
                self.assertFalse(generations[-1].idtry)
                self.assertFalse(generations[-1].idfull)
                self.assertEqual(generations[-1].idhint, {})
                baseline, _ = self.compile(source, hints=False)
                self.assertEqual(ir, baseline)

    def test_scalar_unions_are_not_identity_inert(self):
        helper = INERTLIB + "\ndef scalar(text: str) -> int | str:\n    return int(text)\n"
        source = "# pystachy: dynamic-any\nimport inertlib\nprint(inertlib.scalar('1000'))\n"
        ir, generations = self.compile(source, helper=helper)
        self.assertTrue(generations[0].idevent)
        baseline, _ = self.compile(source, helper=helper, hints=False)
        self.assertEqual(ir, baseline)

    def test_internal_numeric_lists_restore_identity_tracking(self):
        helper = INERTLIB + "\ndef observes() -> bool:\n    x = float('nan')\n    xs = [x]\n    return x in xs\n"
        source = "# pystachy: dynamic-any\nimport inertlib\nprint(inertlib.observes())\n"
        ir, generations = self.compile(source, helper=helper)
        self.assertEqual(generations[0].idevent, "numeric list in an identity-inert module")
        baseline, _ = self.compile(source, helper=helper, hints=False)
        self.assertEqual(ir, baseline)

    def test_feature_opt_ins_override_the_hint(self):
        source = "# pystachy: dynamic-any\nimport inertlib\nprint(inertlib.numeric('1000'))\n"
        for pragma in ["dynamic-any", "python-int"]:
            with self.subTest(pragma=pragma):
                _, generations = self.compile(source, helper="# pystachy: " + pragma + "\n" + INERTLIB)
                self.assertEqual([g.idevent for g in generations], [""])
                self.assertEqual(generations[-1].idhint, {})

    def test_crossing_guard_negative_control(self):
        with patch.object(gen, "dynamic_identity_call", lambda self, f: None):
            with self.assertRaises(AssertionError):
                IdentityInertTests().test_scalar_unions_are_not_identity_inert()

if __name__ == "__main__":
    unittest.main()
