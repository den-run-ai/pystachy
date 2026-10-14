"""Native integration checks for regex results with runtime tuple lengths.

These checks compile the same source with the PYSTACHY_VARIADIC_TUPLES experiment
enabled and use CPython as the output oracle. REGEX_TUPLE_COMPILER='./pystachy'
selects a self-hosted compiler; otherwise the hosted compiler is used.
"""
import ast
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]

REGEX_GROUPS = """
import re

def show(pattern: str, text: str, default: str | None = None) -> None:
    match = re.fullmatch(pattern, text)
    assert match is not None
    values: tuple[str | None, ...] = match.groups(default)
    print("groups", pattern, default, len(values), values, repr(values))
    print("equal", values == match.groups(default=default), values != match.groups(default))
    print("changed-default", values == match.groups("different"), values != match.groups("different"))
    for value in values:
        print("member", repr(value))
    for index in range(-len(values), len(values)):
        print("index", index, repr(values[index]))
    indices: list[int] = [len(values), -len(values) - 1]
    for index in indices:
        try:
            print(values[index])
        except IndexError as error:
            print("bounds", index, str(error))

show("a", "a")
show("(a)", "a")
show("(a)(b)?", "a")
show("(a)(b)?(c)", "ac")
show("(a)(b)?(c)?(d)", "ad")
show("(a)(b)(c)(d)(e)(f)(g)(h)(i)(j)", "abcdefghij")
show("(a)(b)?", "a", "missing")
show("(a)(b)?(c)", "ac", "")
show("(?P<first>a)(?P<optional>b)?(?P<last>c)", "ac", "fallback")
"""

SNAPSHOT = """
def snapshot(values: list[int]) -> tuple[int, ...]:
    return tuple(values)

for count in [0, 1, 2, 3, 4, 10]:
    values: list[int] = [i for i in range(count)]
    alias = values
    result = snapshot(values)
    equal = tuple(values)
    changed = tuple([i + 1 for i in range(count)])
    result_alias = result
    if count > 0:
        alias[0] = 999
    alias.append(998)
    values[-1] = 997
    print("snapshot", count, result, result_alias, repr(result), len(result))
    print("attributes", hasattr(result, "__len__"), hasattr(result, "__getitem__"),
          hasattr(result, "__iter__"), hasattr(result, "__setitem__"), hasattr(result, "append"))
    print("equal", result == equal, result != equal, result == tuple(values))
    print("changed", result == changed, result != changed)
    for member in result:
        print("member", member)
    if count > 0:
        print("ends", result[0], result[-1])
    indices: list[int] = [len(result), -len(result) - 1]
    for index in indices:
        try:
            print(result[index])
        except IndexError as error:
            print("bounds", index, str(error))
"""

LIFETIME = """
def make_strings(count: int) -> tuple[str, ...]:
    items: list[str] = ["value-" + str(i) for i in range(count)]
    result = tuple(items)
    items.clear()
    return result

def make_optional() -> tuple[str | None, ...]:
    items: list[str | None] = ["first", None, "last"]
    result = tuple(items)
    alias = items
    alias[0] = None
    alias[1] = "changed"
    alias.clear()
    return result

strings = make_strings(10)
optional = make_optional()
numbers: list[float] = [0.5, -1.5, 2.5]
numeric: tuple[float, ...] = tuple(numbers)
numbers[0] = 99.5
flags: list[bool] = [True, False]
booleans: tuple[bool, ...] = tuple(flags)
flags[0] = False
for i in range(100):
    garbage = [str(i) * 32, "temporary" + str(i)]
    garbage.append("another" + str(i))
print("strings", strings, repr(strings), len(strings))
print("optional", optional, repr(optional), len(optional))
print("numeric", numeric, repr(numeric), numeric[0], numeric[-1])
print("booleans", booleans, repr(booleans), booleans[0], booleans[-1])
for item in optional:
    if item is None:
        print("none")
    else:
        print("text", item)
print("saved", strings[0], strings[-1], optional[0], optional[-1])
"""

COERCIONS = """
string_values: tuple[str | None, ...] = tuple("abc")
integers: list[int] = [1, 2, 3]
integer_values: tuple[int | None, ...] = tuple(integers)
integers[0] = 99
floats: list[float] = [0.5, -1.5]
float_values: tuple[float | None, ...] = tuple(floats)
floats[0] = 99.5
booleans: list[bool] = [True, False]
boolean_values: tuple[bool | None, ...] = tuple(booleans)
booleans[0] = False

def choose(present: bool) -> tuple[str, ...] | None:
    return ("a", "b") if present else None

for i in range(100):
    garbage = [str(i) * 32, "temporary" + str(i)]
print("strings", string_values, repr(string_values), len(string_values), string_values[0])
print("integers", integer_values, repr(integer_values), len(integer_values), integer_values[0])
print("floats", float_values, repr(float_values), len(float_values), float_values[0])
print("booleans", boolean_values, repr(boolean_values), len(boolean_values), boolean_values[0])
for present in [False, True]:
    result = choose(present)
    if result is None:
        print("absent")
    else:
        print("present", result, repr(result), len(result), result[0], result[-1])
"""


class RegexTupleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pystachy-regex-tuple-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        command = os.environ.get("REGEX_TUPLE_COMPILER", "")
        self.compiler = shlex.split(command) if command else [sys.executable, str(ROOT / "pystachy.py")]
        self.env = dict(os.environ, PYSTACHY_HOME=str(ROOT), PYSTACHY_VARIADIC_TUPLES="1")
        for key in ["PYSTACHY_SKEW_PROFILE", "PYSTACHY_IRFX", "PYSTACHY_GC_STRESS"]:
            self.env.pop(key, None)

    def process(self, command, *, env=None, successful=True, timeout=180):
        result = subprocess.run([str(item) for item in command], cwd=ROOT,
                                env=self.env if env is None else env, capture_output=True,
                                text=True, timeout=timeout)
        if successful:
            self.assertEqual(result.returncode, 0,
                             f"{command!r}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        return result

    def source(self, name, text):
        path = self.directory / (name + ".py")
        path.write_text(textwrap.dedent(text), encoding="utf-8")
        return path

    def compile(self, mode, source, *arguments, successful=True, **overrides):
        return self.process([*self.compiler, mode, source, *arguments],
                            env=dict(self.env, **overrides), successful=successful)

    def check_modes(self, source):
        original = source.read_bytes()
        expected = self.process([sys.executable, source]).stdout
        self.assertEqual(self.compile("run", source).stdout, expected)
        binary = self.directory / source.stem
        self.compile("build", source, "-o", binary)
        for stress in ["", "1"]:
            with self.subTest(source=source.name, gc_stress=stress):
                result = self.process([binary], env=dict(self.env, PYSTACHY_GC_STRESS=stress))
                self.assertEqual(result.stdout, expected)
        self.assertEqual(source.read_bytes(), original)
        return expected

    def test_original_re_match_groups_ast_compiles_for_runtime_capture_counts(self):
        # Preserve the existing library implementation: no replacement matcher,
        # fixed capture helper or hand-written unrolled group reader is involved.
        library = ROOT / "lib/re/__init__.py"
        original = library.read_bytes()
        module = ast.parse(original)
        match = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "Match")
        groups = next(node for node in match.body if isinstance(node, ast.FunctionDef) and node.name == "groups")
        returned = next(node.value for node in groups.body if isinstance(node, ast.Return))
        expected_expression = ast.parse(
            "tuple([self._get(i, default) for i in range(1, self.re.groups + 1)])", mode="eval").body
        self.assertEqual(ast.dump(returned), ast.dump(expected_expression))
        source = self.source("regex_groups", REGEX_GROUPS)
        expected = self.check_modes(source)
        self.assertIn("groups a None 0 () ()\n", expected)
        self.assertIn("('a',) ('a',)", expected)
        self.assertIn("('a', None, 'c')", expected)
        self.assertIn("('a', 'missing')", expected)
        self.assertIn("('a', '', 'c')", expected)
        self.assertIn("('a', 'fallback', 'c')", expected)
        self.assertIn("changed-default False True\n", expected)
        self.assertEqual(library.read_bytes(), original)

    def test_tuple_list_snapshot_survives_alias_mutation_and_variable_lengths(self):
        source = self.source("snapshots", SNAPSHOT)
        expected = self.check_modes(source)
        self.assertIn("snapshot 0 () () () 0\n", expected)
        self.assertIn("snapshot 1 (0,) (0,) (0,) 1\n", expected)
        self.assertIn("snapshot 3 (0, 1, 2) (0, 1, 2) (0, 1, 2) 3\n", expected)
        self.assertEqual(expected.count("equal True False False\n"), 6)
        self.assertEqual(expected.count("changed False True\n"), 5)
        self.assertEqual(expected.count("changed True False\n"), 1)
        self.assertEqual(expected.count("attributes True True True False False\n"), 6)
        self.assertIn("bounds -1 tuple index out of range\n", expected)
        self.assertIn("bounds 10 tuple index out of range\n", expected)

    def test_heap_members_and_optional_none_remain_rooted_after_source_list_dies(self):
        source = self.source("lifetime", LIFETIME)
        expected = self.check_modes(source)
        self.assertIn("optional ('first', None, 'last') ('first', None, 'last') 3\n", expected)
        self.assertIn("numeric (0.5, -1.5, 2.5) (0.5, -1.5, 2.5) 0.5 2.5\n", expected)
        self.assertIn("booleans (True, False) (True, False) True False\n", expected)
        self.assertIn("saved value-0 value-9 first last\n", expected)

    def test_optional_member_widening_and_optional_fixed_tuple_results_preserve_values(self):
        source = self.source("coercions", COERCIONS)
        expected = self.check_modes(source)
        self.assertIn("strings ('a', 'b', 'c') ('a', 'b', 'c') 3 a\n", expected)
        self.assertIn("integers (1, 2, 3) (1, 2, 3) 3 1\n", expected)
        self.assertIn("floats (0.5, -1.5) (0.5, -1.5) 2 0.5\n", expected)
        self.assertIn("booleans (True, False) (True, False) 2 True\n", expected)
        self.assertIn("absent\npresent ('a', 'b') ('a', 'b') 2 a b\n", expected)

    def test_flag_off_preserves_rejection_of_runtime_tuple_annotations_and_groups(self):
        sources = [self.source("disabled_tuple", """
            def snapshot(values: list[int]) -> tuple[int, ...]:
                return tuple(values)
            print(snapshot([1, 2, 3]))
            """), self.source("disabled_regex", """
            import re
            match = re.fullmatch("(a)(b)?", "a")
            assert match is not None
            print(match.groups())
            """)]
        for source in sources:
            with self.subTest(source=source.name):
                rejected = self.compile("ir", source, successful=False, PYSTACHY_VARIADIC_TUPLES="0")
                self.assertNotEqual(rejected.returncode, 0, rejected.stdout)
                self.assertIn("tuple", rejected.stderr.lower())
                self.compile("ir", source)

    def test_counted_tuples_cannot_be_mutated_through_item_assignment(self):
        source = self.source("immutable", """
            items: list[int] = [1, 2, 3]
            result: tuple[int, ...] = tuple(items)
            result[0] = 99
            print(result)
            """)
        rejected = self.compile("ir", source, successful=False)
        self.assertNotEqual(rejected.returncode, 0, rejected.stdout)
        self.assertIn("tuple", rejected.stderr.lower())


if __name__ == "__main__":
    unittest.main()
