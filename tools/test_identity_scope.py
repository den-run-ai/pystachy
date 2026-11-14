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


# the shipped library's modules that model C extension modules (# pystachy: numeric-values)
VALUES = {"_pystachy_re_specialized": True, "datetime": True, "re": True, "re._sre": True}


class IdentityScopeTests(unittest.TestCase):
    def compile(self, source, helper=True, full=False, values=True, files=None):
        # the IR and every pass's Gen; helper: scopelib (above) on the module path; full: track
        # identity everywhere from the start, as the driver's fallback does; values: try
        # numeric-value modules (else they track identity as before them); files: more modules
        generators = []
        original = driver.Gen
        original_split = gen.dynamic_identity_modules

        def make_generator():
            generator = original()
            generators.append(generator)
            return generator

        def split(self, mods):
            if full:
                self.idfull = True
            if not values:
                self.idvals = False
            original_split(self, mods)

        with tempfile.TemporaryDirectory() as tmp:
            if helper:
                Path(tmp, "scopelib.py").write_text(SCOPELIB)
            for name, text in (files or {}).items():
                Path(tmp, name).write_text(text)
            with patch.object(driver, "Gen", make_generator), patch.object(gen, "dynamic_identity_modules", split):
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

    def test_tomllib_flags_keep_typed_private_storage(self):
        source = 'import tomllib\nprint(tomllib.loads("a.b = 1\\na.c = 2\\n[x]\\ny = 3"))\n'
        ir, generations = self.compile(source, helper=False)
        final = generations[-1]
        self.assertEqual([g.idevent for g in generations], [""])
        # The document remains dynamic; only the closed private flag tree is typed.
        # Its imported regex/date modules keep their numbers as values (numeric-values).
        for module in ["tomllib._parser", "tomllib._re"]:
            self.assertNotIn(module, final.idoff)
        for module in ["re", "datetime"]:
            self.assertIn(module, final.idval)
        flags = final.classes["tomllib$_parser$Flags"]
        tree = flags.ftypes["_flags"]
        self.assertRegex(tree, r"^dict\[str,[^\[\],]+\]$")
        entry_name = tree[len("dict[str,"):-1]
        entry = final.classes[entry_name]
        self.assertEqual(entry.ftypes["nested"], tree)
        self.assertEqual(entry.ftypes["flags"], "set[int]")
        self.assertEqual(entry.ftypes["recursive_flags"], "set[int]")
        bodies = functions(ir)
        private = {fn.f.ll: bodies[fn.f.ll] for fn in final.fns
                   if fn.f.cls in [flags.name, entry_name]}
        for method in ["set", "is_", "unset_all", "finalize_pending"]:
            self.assertIn("@m.tomllib$_parser$Flags." + method, private)
        calls = []
        for name, body in private.items():
            with self.subTest(function=name):
                dynamic = re.findall(r"\b(?:call|invoke) [^\n]*?@(pys_dyn_\w+|dyn\.[^(]+)\(", body)
                # No private container boxing, dynamic lookup or dispatch. A pending
                # tuple's int may still acquire one numeric companion when unpacked.
                self.assertLessEqual(set(dynamic), {"pys_dyn_int_box"})
                calls.extend(dynamic)
        self.assertLessEqual(len(calls), 1)

    def test_tomllib_numeric_callback_preserves_tracking_and_dynamic_result(self):
        source = '''import tomllib
number = float("123.5")
def reuse_float(text: str) -> float:
    return number
result = tomllib.loads("value = 123.5", parse_float=reuse_float)
print(result["value"] is number)
'''
        ir, generations = self.compile(source, helper=False)
        # Returning a caller-owned number through parse_float requires tracking in
        # that caller too. Generic specialization must not erase its original box.
        self.assertEqual(generations[0].idevent, "number as an Any value")
        self.assertTrue(generations[-1].idfull)
        # (every module but those that keep numbers as values)
        self.assertEqual(generations[-1].idoff, VALUES)
        self.assertEqual(generations[-1].idval, VALUES)
        number_functions = [fn.f for fn in generations[-1].fns
                            if fn.f.ll == "@f.tomllib$_re$match_to_number"]
        self.assertEqual(len(number_functions), 1)
        self.assertEqual(number_functions[0].ret, "dyn")
        full, _ = self.compile(source, helper=False, full=True)
        self.assertEqual(ir, full)

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
                symbol = "@m.json$_Parser." + method
                # (the parser's methods are closed recursion: each body is @r.<its symbol>, and
                # its symbol a wrapper that passes the depth along, docs/internals.md#native-recursion-depth)
                body = bodies.get("@r." + symbol[1:], bodies[symbol])
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

    def test_numeric_value_modules_keep_numbers_as_values(self):
        # re's engine and datetime model CPython's C modules (_sre, _datetime), which hold
        # positions, flags and fields as machine values: their code tracks no numeric identity,
        # even where tomllib's does, and their objects keep no companions, except exceptions and
        # named tuples, whose CPython counterparts hold objects
        source = 'import tomllib\nprint(tomllib.loads("when = 1979-05-27T07:32:00Z\\nn = 3"))\n'
        ir, generations = self.compile(source, helper=False)
        final = generations[-1]
        self.assertEqual([g.idevent for g in generations], [""])
        self.assertEqual(final.idval, VALUES)
        for module in VALUES:
            self.assertIn(module, final.idoff)
        for module in ["tomllib._parser", "tomllib._re", "re._constants"]:
            self.assertNotIn(module, final.idoff)
        bodies = functions(ir)
        # (their module code boxes the int literals their module variables hold, below)
        engine = {fn.f.ll: bodies[fn.f.ll] for fn in final.fns
                  if final.fn_home(fn.f) in VALUES and fn.f.ll in bodies and not fn.f.ll.startswith("@init.")}
        self.assertGreater(len(engine), 100)
        for name, body in engine.items():
            with self.subTest(function=name):
                self.assertIsNone(BOXING.search(body))
                self.assertNotIn(".box.", body)
        for name in ["re$Pattern", "re$Match", "re$_sre$State", "datetime$date", "datetime$datetime", "datetime$timezone"]:
            self.assertEqual(final.classes[name].fbox, {}, name)
        for name in ["re$error", "datetime$_IsoCalendarDate", "datetime$_struct_time"]:
            self.assertNotEqual(final.classes[name].fbox, {}, name)
        # Module variables keep their objects, as a CPython module's do.
        self.assertIn("@g.datetime$MAXYEAR.box", ir)
        tracked, _ = self.compile(source, helper=False, values=False)
        self.assertLess(len(ir.splitlines()), len(tracked.splitlines()))

    def test_crossings_that_are_not_values_restore_tracking(self):
        # Each compiles again with numeric-value modules tracking identity, as before them.
        programs = [
            # a tracking module's class extending one of theirs, whose layout differs
            ("class Zone(datetime.tzinfo):\n    def __init__(self) -> None:\n        self.n = 1000\nprint(Zone().n)\n",
             "inheritance of Zone"),
            # a numeric container, whose items keep companions in tracking code
            ("print(re.compile('(?P<a>x)').groupindex['a'])\n", "attribute of re$Pattern"),
            # a function, which may be tracking code (its call from re's code, or its passing)
            ("print(re.sub('a', lambda m: 'b', 'aaa'))\n", ("call of <lambda>()", "call of re$sub()")),
        ]
        for body, why in programs:
            source = "# pystachy: dynamic-any\nimport datetime\nimport re\n" + body
            with self.subTest(body=body):
                ir, generations = self.compile(source, helper=False)
                self.assertEqual(len(generations), 2)
                self.assertTrue(generations[0].idvalevent)
                self.assertTrue(generations[0].idevent.startswith(why), generations[0].idevent)
                self.assertFalse(generations[1].idvals)
                self.assertEqual(generations[1].idval, {})
                before, _ = self.compile(source, helper=False, values=False)
                self.assertEqual(ir, before)

    def test_dropping_the_value_checks_is_detected(self):
        # Without identity_value's check, a numeric container or a function would cross as a value.
        def all_values(self, t, seen):
            return True

        with patch.object(gen, "dynamic_identity_value", all_values):
            with self.assertRaises(AssertionError):
                IdentityScopeTests().test_crossings_that_are_not_values_restore_tracking()

    def test_programs_without_dynamic_any_are_unaffected(self):
        source = "import datetime\nimport re\nprint(re.match('a+', 'aaa').end(), datetime.date(2024, 5, 6).year)\n"
        ir, generations = self.compile(source, helper=False)
        self.assertEqual(generations[-1].idval, {})
        before, _ = self.compile(source, helper=False, values=False)
        self.assertEqual(ir, before)

    def test_numeric_values_need_a_module_without_other_opt_ins(self):
        valuelib = """# pystachy: numeric-values
class Cursor:
    def __init__(self, pos: int) -> None:
        self.pos = pos

    def end(self) -> int:
        return self.pos + 1


LIMIT = 5000
"""
        source = """# pystachy: dynamic-any
from typing import Any
import valuelib
c = valuelib.Cursor(1000)
a: Any = c.end()
b: Any = c.end()
x: Any = valuelib.LIMIT
y: Any = valuelib.LIMIT
print(a is b, x is y, a == b)
"""
        ir, generations = self.compile(source, helper=False, files={"valuelib.py": valuelib})
        final = generations[-1]
        self.assertEqual([g.idevent for g in generations], [""])
        self.assertEqual(final.idval, {"valuelib": True})
        self.assertEqual(final.classes["valuelib$Cursor"].fbox, {})
        self.assertIn("@g.valuelib$LIMIT.box", ir)
        # A module that also opts in to dynamic Any or promoting ints tracks identity as before.
        for pragma in ["# pystachy: dynamic-any\n", "# pystachy: python-int\n"]:
            with self.subTest(pragma=pragma):
                _, generations = self.compile(source, helper=False, files={"valuelib.py": pragma + valuelib})
                self.assertEqual(generations[-1].idval, {})



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
