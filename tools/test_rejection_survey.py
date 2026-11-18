"""Rejection survey controls: a scripted compiler and the checkout's hosted compiler; no native build."""
import ast
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import warnings

import rejection_survey as survey


ROOT = Path(__file__).resolve().parent.parent
# A compiler for the survey's own rules: it loads the entry and, first found first, the modules
# its files import from the entry's directory, PYSTACHY_PATH and FAKE_LIB (its lib/), and rejects
# the first line of them that holds "# REJECT message". Every file it loads must be valid Python,
# as a stubbed copy must be. FAKE_REJECT_STUBS makes it reject the survey's raising stub as well.
FAKE = r'''
import ast, os, sys, tokenize
entry = sys.argv[sys.argv.index("ir") + 1]
roots = [os.path.dirname(entry)] + [d for d in os.environ.get("PYSTACHY_PATH", "").split(":") if d] + [os.environ["FAKE_LIB"]]
loaded = []

def find(parts):
    for root in roots:
        for path in (os.path.join(root, *parts, "__init__.py"), os.path.join(root, *parts) + ".py"):
            if os.path.isfile(path):
                return path

def load(path):
    if path is None or path in loaded:
        return
    loaded.append(path)
    with tokenize.open(path) as source:  # (decoded as CPython decodes a module)
        tree = ast.parse(source.read())
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names = [node.module] + [node.module + "." + alias.name for alias in node.names]
        for name in names:
            parts = name.split(".")
            for n in range(1, len(parts) + 1):
                load(find(parts[:n]))

load(entry)
for path in loaded:
    with tokenize.open(path) as source:
        for number, line in enumerate(source, 1):
            if "# REJECT " in line or ("rejection survey stub" in line and os.environ.get("FAKE_REJECT_STUBS")):
                sys.exit(f"{path}:{number}: error: " + line.split("# REJECT ", 1)[-1].strip().replace("{file}", path))
'''


def digests(directory):
    return {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(Path(directory).rglob("*")) if path.is_file()}


class DiagnosticTests(unittest.TestCase):
    def test_message_notes_and_call_sites(self):
        found = survey.parse_diagnostic(
            "/t/a b/m.py:13: error: expected int (got 'str'); see f() (compiling m.g(Box) for the call at "
            "/t/a b/m.py:9, where x and y may be None: only a new object is known not to be None; "
            "specializing Box(int) for the call at lib/x.py:4; making a Callable of f(int) at /t/a b/main.py:35)")
        self.assertEqual((found["file"], found["line"]), ("/t/a b/m.py", 13))
        self.assertEqual(found["message"], "expected int (got 'str'); see f()")
        self.assertEqual([note.split(" ")[0] for note in found["context"]], ["making", "specializing", "compiling"])
        self.assertEqual(survey.call_sites(found["context"]),
                         [("/t/a b/main.py", 35), ("lib/x.py", 4), ("/t/a b/m.py", 9)])
        plain = survey.parse_diagnostic("m.py:2: error: unsupported call f(int) (see #12)")
        self.assertEqual((plain["message"], plain["context"]), ("unsupported call f(int) (see #12)", []))

    def test_other_output_is_no_diagnostic(self):
        for text in ("Traceback (most recent call last):", "m.py:2: warning: unused", "m.py: error: no line", ""):
            self.assertIsNone(survey.parse_diagnostic(text))


SCOPES = '''import functools

class Box:
    size: int = 0

    @functools.cache
    def area(self,
             scale: int = 1) -> int:
        def inner(k):
            return k

        return inner(scale)

def outer():
    class Local:
        def method(self):
            return 1
    return Local

value = [
    outer(),
]
'''


class ScopeTests(unittest.TestCase):
    def place(self, line):
        chain = survey.scope_chain(ast.parse(SCOPES), line)
        return survey.qualified(chain), [type(node).__name__ for node in chain]

    def test_a_line_belongs_to_the_definitions_from_their_def_line(self):
        self.assertEqual(self.place(1), ("", []))
        self.assertEqual(self.place(4), ("Box", ["ClassDef"]))
        # A decorator runs in the scope around its definition; the signature is the function's.
        self.assertEqual(self.place(6), ("Box", ["ClassDef"]))
        self.assertEqual(self.place(8)[0], "Box.area")
        self.assertEqual(self.place(10)[0], "Box.area.<locals>.inner")
        self.assertEqual(self.place(12)[0], "Box.area")
        self.assertEqual(self.place(17), ("outer.<locals>.Local.method", ["FunctionDef", "ClassDef", "FunctionDef"]))
        self.assertEqual(self.place(15)[1], ["FunctionDef", "ClassDef"])
        self.assertEqual(self.place(21), ("", []))

    def test_statement_and_its_own_names(self):
        tree = ast.parse(SCOPES)
        self.assertEqual(survey.own_names(survey.statement_at(tree, 21)), {"value", "outer"})
        # A decorator's line is its definition's, whose own names are its header's.
        self.assertEqual(survey.own_names(survey.statement_at(tree, 6)), {"functools", "cache", "int"})
        self.assertEqual(survey.own_names(survey.statement_at(tree, 15)), set())
        self.assertIsNone(survey.statement_at(tree, 2))
        loop = ast.parse("for a in f(b):\n    c = d\nelse:\n    e = g\n").body[0]
        self.assertEqual((survey.own_names(loop), survey.names_used(loop, True)), ({"a", "f", "b"}, {"a", "c", "e"}))

    def test_names_reach_through_assignments(self):
        scope = ast.parse("a = stub()\nb, c.d = a, 1\nfor e in b:\n    f = other\nwith d as g, f as h:\n    i += g\n"
                          "j: int = [k for k in i]\nif (m := j):\n    stub = unrelated\n")
        self.assertEqual(survey.reaching(scope, {"stub"}), {"stub", "a", "b", "d", "e", "g", "i", "k", "j", "m"})
        self.assertEqual(survey.reaching(scope, {"other"}), {"other", "f", "h"})


class StubTests(unittest.TestCase):
    def stub(self, text, name):
        """Stub the function NAME of TEXT and check everything that a stub must keep."""
        tree = ast.parse(text)
        function = next(node for node in ast.walk(tree) if isinstance(node, survey.FUNCTIONS) and node.name == name)
        chain = survey.scope_chain(tree, function.lineno)
        self.assertIs(chain[-1], function)
        result = survey.stubbed(text, function, survey.stub_statement(chain))
        before, after = (io.StringIO(source, newline="").readlines() for source in (text, result))
        self.assertEqual(len(after), len(before))
        start = survey.first_line(function.body[0])
        for number, (old, new) in enumerate(zip(before, after), 1):
            if number < start or number > function.end_lineno:
                self.assertEqual(new, old, number)
            elif number > start:
                self.assertEqual(new, old[len(old.rstrip("\r\n")):], number)
        stubbed = next(node for node in ast.walk(ast.parse(result))
                       if isinstance(node, survey.FUNCTIONS) and node.lineno == function.lineno)

        def header(node):
            return (type(node).__name__, node.name, ast.dump(node.args), [ast.dump(d) for d in node.decorator_list],
                    node.returns and ast.dump(node.returns))

        self.assertEqual(header(stubbed), header(function))
        return stubbed, after[start - 1]

    def test_body_becomes_one_raising_line(self):
        text = ('import os\n\n@staticmethod\ndef f(a: int,\n      b: int = 2) -> int:\n    """Doc\n    string."""\n'
                '    # comment\n    @os.cache\n    def g():\n        return a\n\n    return (a +\n            b)\n\n# after\nx = 1')
        stubbed, line = self.stub(text, "f")
        self.assertEqual(line, "    " + survey.STUB + "\n")
        self.assertEqual([type(node).__name__ for node in stubbed.body], ["Raise"])

    def test_body_on_a_line_of_the_header(self):
        stubbed, line = self.stub("class C:\n\tdef f(self, é='ü'): return (self.x +\n\t\t1)\n\tdef g(self): pass\n", "f")
        self.assertEqual(line, "\tdef f(self, é='ü'): " + survey.STUB + "\n")
        _, line = self.stub("def f(a,\n      b): return a\n", "f")
        self.assertEqual(line, "      b): " + survey.STUB + "\n")
        _, line = self.stub("def f(): x = 1; return x", "f")
        self.assertEqual(line, "def f(): " + survey.STUB)

    def test_line_ends_and_form_feeds_are_kept(self):
        _, line = self.stub("def f():\r\n    x = 1\x0c\r\n    return x\r\n\r\ndef g():\r\n    return 2\r\n", "f")
        self.assertEqual(line, "    " + survey.STUB + "\r\n")

    def test_a_decorated_definition_first_in_the_body(self):
        stubbed, line = self.stub("def f():\n\n    @staticmethod\n    def g(): pass\n    return g\n", "f")
        self.assertEqual((line, len(stubbed.body)), ("    " + survey.STUB + "\n", 1))

    def test_generators_and_typed_special_methods_keep_their_kind(self):
        text = ("class C:\n    def __len__(self):\n        return 1\n    def __str__(self) -> str:\n        return ''\n"
                "    def __iter__(self):\n        def helper():\n            yield 0\n        yield from helper()\n"
                "    async def feed(self):\n        yield 1\n    def plain(self):\n        return (lambda: (yield))\n"
                "def __len__(x):\n    return 1\n")
        for name, cls, body in (("__iter__", "C", ["Raise", "Expr"]), ("feed", "C", ["Raise", "Expr"]),
                                ("plain", "C", ["Raise"]), ("helper", "C", ["Raise", "Expr"]),
                                ("__str__", "C", ["Raise"])):
            with self.subTest(name=name):
                self.assertEqual([type(node).__name__ for node in self.stub(text, name)[0].body], body)
        tree = ast.parse(text)
        function, method = (node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "__len__")
        self.assertEqual(survey.stub_statement([tree.body[0], method]), "return 0")
        self.assertEqual(survey.stub_statement([function]), survey.STUB)

    def test_typed_special_methods_are_the_compilers(self):
        sys.path.insert(0, str(ROOT))
        self.addCleanup(sys.path.remove, str(ROOT))
        from src.pystachy_compiler import specs
        literal = {"str": '""', "int": "0", "bool": "False"}
        wanted = {name: literal[value.partition(":")[2]] for name, value in specs.SPECIAL.items() if value.partition(":")[2]}
        self.assertEqual(survey.RESULTS, wanted)

    def test_names_that_a_stub_takes_away(self):
        tree = ast.parse("class C:\n    def __init__(me, v):\n        me.v, me.w.x = v, 1\n        other.y = me.z\n"
                         "def f(a):\n    a.b = 1\n")
        self.assertEqual(survey.stub_names([tree.body[0], tree.body[0].body[0]]), {"__init__", "v"})
        self.assertEqual(survey.stub_names([tree.body[1]]), {"f"})


class CopyTests(unittest.TestCase):
    def test_files_are_those_the_loader_would_find_for_the_imports(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {
                "app/main.py": "import helper, os\nimport pkg.sub as s\nfrom ns import part\n"
                               "def f():\n    try:\n        from late import thing\n    except ImportError:\n        import missing\n",
                "app/helper.py": "import extra\n",
                "app/unused.py": "import never\n",
                "app/never.py": "",
                "app/pkg/__init__.py": "from . import sibling\nfrom .deep import leaf\n",
                "app/pkg/sub.py": "from .. import helper\nfrom .deep.leaf import g\n",
                "app/pkg/sibling.py": "",
                "app/pkg/other.py": "",
                "app/pkg/deep/__init__.py": "",
                "app/pkg/deep/leaf.py": "from ..sibling import *\nimport pkg.deep.more\n",
                "app/pkg/deep/more.py": "def broken(:\n    import never\n",
                "app/ns/part.py": "from ns import far\n",
                "one/helper.py": "",
                "one/extra.py": "",
                "one/late/__init__.py": "",
                "one/ns/unimported.py": "",
                "two/ns/far.py": "",
                "two/late.py": "",
            }
            for name, text in files.items():
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_text(text)
            roots = [str(root / "app"), str(root / "one"), str(root / "two")]
            found = survey.program_files(str(root / "app/main.py"), roots)
            self.assertEqual(found[0], (0, "main.py"))
            self.assertEqual(len(found), len(set(found)))
            self.assertEqual(sorted(found), sorted([
                (0, "main.py"), (0, "helper.py"), (0, "pkg/__init__.py"), (0, "pkg/sub.py"), (0, "pkg/sibling.py"),
                (0, "pkg/deep/__init__.py"), (0, "pkg/deep/leaf.py"), (0, "pkg/deep/more.py"), (0, "ns/part.py"),
                (1, "extra.py"), (1, "late/__init__.py"), (2, "ns/far.py")]))

    def test_source_nested_too_deeply_for_cpythons_parser_is_unparsable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app").mkdir()
            (root / "app/main.py").write_text("import helper\nx = " + "-" * 20000 + "1\n")
            (root / "app/helper.py").write_text("")
            self.assertEqual(survey.program_files(str(root / "app/main.py"), [str(root / "app")]), [(0, "main.py")])
            copied = survey.Survey(str(root / "scratch"), str(root / "app/main.py"), [])
            with self.assertRaisesRegex(survey.Unparsable, "MemoryError|RecursionError"):
                copied.source(copied.entry)

    def test_only_files_inside_the_copies_are_owned(self):
        # (a diagnostic's path is resolved before the survey writes a stub to it)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app").mkdir()
            (root / "app/main.py").write_text("x = 1\n")
            (root / "app/other.py").write_text("y = 2\n")
            copied = survey.Survey(str(root / "scratch"), str(root / "app/main.py"), [])
            copy = copied.copies[0]
            self.assertTrue(copied.owned(copied.entry))
            self.assertFalse(copied.owned(str(root / "app/main.py")))
            self.assertFalse(copied.owned(os.path.join(copy, "..", "..", "app", "other.py")))
            os.symlink(root / "app", os.path.join(copy, "linked"))
            self.assertFalse(copied.owned(os.path.join(copy, "linked", "other.py")))

    def test_cpythons_warnings_about_a_source_are_not_printed(self):
        # (an invalid escape: a SyntaxWarning, before Python 3.12 a DeprecationWarning)
        with tempfile.TemporaryDirectory() as temporary, warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            program = Path(temporary, "main.py")
            program.write_text("import re\nimport helper\npattern = re.compile('\\d+')\n")
            Path(temporary, "helper.py").write_text("digits = '\\d'\n")
            copied = survey.Survey(str(Path(temporary, "scratch")), str(program), [])
            self.assertTrue(os.path.isfile(Path(temporary, "scratch/program/helper.py")))
            self.assertIn("pattern", survey.names_used(copied.source(copied.entry)[2]))
        self.assertEqual([str(warning.message) for warning in caught], [])


class SurveyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()
        (self.directory / "lib").mkdir()
        fake = self.directory / "fake_compiler.py"
        fake.write_text(FAKE)
        self.compiler = shlex.join([sys.executable, "-I", str(fake)])
        environment = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
        patch = mock.patch.dict(os.environ, environment | {"FAKE_LIB": str(self.directory / "lib")}, clear=True)
        patch.start()
        self.addCleanup(patch.stop)

    def write(self, name, text):
        path = self.directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return str(path)

    def survey(self, program, *arguments, compiler=None, text=False):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = survey.main(["--compiler", compiler or self.compiler, *arguments, *([] if text else ["--json"]), program])
        return status, output.getvalue() if text else json.loads(output.getvalue())

    def test_several_rejections_in_one_file(self):
        program = self.write("app/main.py", (
            "def first(x):\n    y = x\n    return y  # REJECT first reason\n\n"
            "def fine(x):\n    return x\n\n"
            "class Box:\n    def method(self):\n        return 1  # REJECT second reason\n\n"
            "def third(x): return x  # REJECT third reason\n\n"
            "print(first(1), fine(2), Box().method(), third(3))\n"))
        before = digests(self.directory / "app")
        status, report = self.survey(program)
        self.assertEqual(status, 1)
        self.assertEqual(report["status"], "rejected")
        self.assertEqual([(r["index"], r["file"], r["line"], r["definition"], r["message"], r["stubbed"]) for r in report["rejections"]],
                         [(1, program, 3, "first", "first reason", True), (2, program, 10, "Box.method", "second reason", True),
                          (3, program, 12, "third", "third reason", True)])
        self.assertEqual((report["compilations"], report["ended"]["reason"]), (4, "compiled"))
        self.assertEqual(report["limits"], survey.LIMITS)
        self.assertEqual(digests(self.directory / "app"), before)

    def test_no_rejection(self):
        status, report = self.survey(self.write("main.py", "print(1)\n"))
        self.assertEqual((status, report["status"], report["rejections"], report["compilations"]), (0, "ok", [], 1))
        self.assertEqual(report["ended"], {"reason": "compiled", "detail": "The program compiles."})

    def test_rejections_in_imported_modules_and_on_the_module_path(self):
        program = self.write("app/main.py", "import helper\nfrom pkg import sub\nimport shared\n")
        self.write("app/helper.py", "def broken():\n    return 1  # REJECT in helper\n")
        self.write("app/pkg/__init__.py", "")
        self.write("app/pkg/sub.py", "class C:\n    def f(self):\n        return 1  # REJECT in package\n")
        self.write("app/unused.py", "def unreached():\n    return 1  # REJECT never loaded\n")
        self.write("one/shared.py", "def g():\n    return 1  # REJECT on the path\n")
        self.write("two/shared.py", "def shadowed():\n    return 1  # REJECT never loaded\n")
        before = digests(self.directory)
        path = f"{self.directory / 'one'}:{self.directory / 'two'}"
        wanted = [(str(self.directory / "app/helper.py"), 2, "broken"), (str(self.directory / "app/pkg/sub.py"), 3, "C.f"),
                  (str(self.directory / "one/shared.py"), 2, "g")]
        for arguments, environment in ((["--path", path], {"PYSTACHY_PATH": "/nowhere"}), ([], {"PYSTACHY_PATH": path})):
            with self.subTest(arguments=arguments), mock.patch.dict(os.environ, environment):
                status, report = self.survey(program, *arguments)
                self.assertEqual((status, report["ended"]["reason"]), (1, "compiled"))
                self.assertEqual([(r["file"], r["line"], r["definition"]) for r in report["rejections"]], wanted)
                self.assertEqual(report["path"], path.split(":"))
        self.assertEqual(digests(self.directory), before)

    def test_relative_names_are_reported_as_given(self):
        self.write("app/main.py", "import helper\n")
        self.write("app/helper.py", "def broken():\n    return 1  # REJECT relative (compiling helper.broken() for the call at {file}:9)\n")
        previous = os.getcwd()
        self.addCleanup(os.chdir, previous)
        os.chdir(self.directory)
        _, report = self.survey("app/main.py")
        self.assertEqual((report["rejections"][0]["file"], report["rejections"][0]["call_sites"]),
                         ("app/helper.py", [{"file": "app/helper.py", "line": 9}]))
        os.chdir(self.directory / "app")
        _, report = self.survey("main.py")
        self.assertEqual(report["rejections"][0]["file"], "helper.py")
        self.assertEqual(report["rejections"][0]["context"], ["compiling helper.broken() for the call at helper.py:9"])

    def test_bound(self):
        program = self.write("main.py", "".join(f"def f{k}():\n    return 1  # REJECT number {k}\n" for k in range(3)))
        status, report = self.survey(program, "--max", "2")
        self.assertEqual((status, report["status"], report["compilations"], report["ended"]["reason"]), (1, "rejected", 2, "bound"))
        self.assertEqual([(r["definition"], r["stubbed"]) for r in report["rejections"]], [("f0", True), ("f1", False)])

    def test_a_statement_outside_any_function_ends_the_survey(self):
        function = "def f():\n    return 1  # REJECT in a function\n"
        later = "def later():\n    return 1  # REJECT not reached\n"
        for statement, scope, definition in (("x = 1  # REJECT at module level\n", "module", None),
                                             ("class Box:\n    size = 1  # REJECT in a class\n", "class Box", None),
                                             ("@decorate  # REJECT a decorator\ndef g(): pass\n", "module", None)):
            with self.subTest(scope=scope):
                status, report = self.survey(self.write("main.py", function + statement + later))
                self.assertEqual((status, report["status"], report["compilations"], report["ended"]["reason"]),
                                 (1, "rejected", 2, "no-function"))
                self.assertEqual([(r["definition"], r["scope"], r["stubbed"]) for r in report["rejections"]],
                                 [("f", "function", True), (definition, scope, False)])

    def test_a_signature_that_is_still_rejected_ends_the_survey(self):
        program = self.write("main.py", "def f(x=1):  # REJECT the default\n    return x\n\ndef g():\n    return 1  # REJECT not reached\n")
        status, report = self.survey(program)
        self.assertEqual((status, report["compilations"], report["ended"]["reason"]), (1, 2, "repeated"))
        self.assertEqual([(r["definition"], r["line"], r["stubbed"]) for r in report["rejections"]], [("f", 1, True)])
        self.assertIn(f"{program}:1", report["ended"]["detail"])
        self.assertIn("the default", report["ended"]["detail"])

    def test_a_rejected_stub_ends_the_survey(self):
        program = self.write("main.py", "def f(x):\n    y = x\n    return y  # REJECT the body\n")
        with mock.patch.dict(os.environ, {"FAKE_REJECT_STUBS": "1"}):
            status, report = self.survey(program)
        self.assertEqual((status, report["compilations"], report["ended"]["reason"]), (1, 2, "repeated"))
        self.assertEqual([(r["line"], r["stubbed"]) for r in report["rejections"]], [(3, True)])
        self.assertIn(f"{program}:2", report["ended"]["detail"])

    def test_a_file_outside_the_copy_ends_the_survey(self):
        program = self.write("app/main.py", "import helper, libmod\n")
        self.write("app/helper.py", "def f():\n    return 1  # REJECT in the program\n")
        library = self.write("lib/libmod.py", "class Wrapper:\n    def wrap(self):\n        return 1  # REJECT in lib\n")
        self.write("lib/helper.py", "def f():\n    return 1  # REJECT shadowed by the program's\n")
        before = digests(self.directory)
        status, report = self.survey(program)
        self.assertEqual((status, report["status"], report["compilations"], report["ended"]["reason"]), (1, "rejected", 2, "outside"))
        self.assertEqual([(r["file"], r["line"], r["definition"], r["stubbed"]) for r in report["rejections"]],
                         [(str(self.directory / "app/helper.py"), 2, "f", True), (library, 3, "Wrapper.wrap", False)])
        self.assertEqual(digests(self.directory), before)

    def test_a_module_that_the_scan_misses_is_still_the_programs(self):
        # (as a module of the program's directory that only the compiler's lib/ imports)
        program = self.write("app/main.py", "import libmod\n")
        self.write("lib/libmod.py", "import plugin\n")
        plugin = self.write("app/plugin.py", "def f():\n    return 1  # REJECT in the program's module\n")
        self.write("lib/plugin.py", "")
        status, report = self.survey(program)
        self.assertEqual((status, report["ended"]["reason"]), (1, "outside"))
        self.assertEqual([(r["file"], r["definition"]) for r in report["rejections"]], [(plugin, "f")])

    def test_rejections_that_may_follow_from_a_stub_are_marked(self):
        program = self.write("main.py", (
            "def first(x):\n    return x  # REJECT one\n\n"                                    # 1
            "def caller():\n    v = first(1)\n    return v  # REJECT two\n\n"                  # 2: uses first
            "def independent():\n    return 0  # REJECT three\n\n"                             # 3
            "class Box:\n"
            "    def __init__(self): self.size = 1  # REJECT four\n"                           # 4
            "    def area(self):\n        return self.size  # REJECT five\n"                   # 5: reads the field
            "    def name(self):\n        return 'box'  # REJECT six\n\n"                      # 6
            "def template(v):\n    return v  # REJECT seven (compiling template(int) for the call at {file}:23)\n\n"  # 7
            "def passes():\n    w = independent()\n    return template(w)\n\n"                 # line 23: w is its result
            "def other(v):\n    return v  # REJECT eight (compiling other(int) for the call at {file}:30)\n\n"  # 8
            "def hub():\n    first(1)\n    return other(2)\n\n"                                # line 30: no use of first
            "t = Box().area  # REJECT nine\n"                                                  # 9: the statement's names
            "u = hub()  # REJECT not reached\n"))
        status, report = self.survey(program)
        self.assertEqual((status, report["ended"]["reason"]), (1, "no-function"))
        self.assertEqual([(r["message"], r["may_follow_from"]) for r in report["rejections"]],
                         [("one", []), ("two", [1]), ("three", []), ("four", []), ("five", [4]), ("six", []),
                          ("seven", [3]), ("eight", []), ("nine", [5])])
        self.assertEqual(report["rejections"][6]["call_sites"], [{"file": program, "line": 23}])

    def test_a_compiler_failure_is_an_error_not_a_rejection(self):
        program = self.write("main.py", "def f():\n    return 1  # REJECT first\n")
        # (run as SCRIPT CODE ir ENTRY -o FILE: one rejection, then two lines and exit status CODE)
        script = self.write("fail.py", (
            "import sys\nentry = sys.argv[3]\n"
            "if 'REJECT' in open(entry).read():\n    sys.exit(entry + ':2: error: first')\n"
            "print('Traceback (most recent call last):\\n' + entry + ':3: error: not a lone line', file=sys.stderr)\n"
            "sys.exit(int(sys.argv[1]))\n"))
        for code in (1, 2, 139):
            with self.subTest(code=code):
                status, report = self.survey(program, compiler=shlex.join([sys.executable, "-I", script, str(code)]))
                self.assertEqual((status, report["status"], report["ended"]["reason"]), (2, "error", "failed"))
                self.assertEqual([(r["definition"], r["stubbed"]) for r in report["rejections"]], [("f", True)])
                self.assertIn(f"exit {code}", report["ended"]["detail"])
                self.assertIn("not a lone line", report["ended"]["detail"])
        status, report = self.survey(program, compiler=str(self.directory / "no-such-compiler"))
        self.assertEqual((status, report["status"], report["compilations"]), (2, "error", 1))

    def test_timeout(self):
        program = self.write("main.py", "print(1)\n")
        status, report = self.survey(program, "--timeout", "0.3",
                                     compiler=shlex.join([sys.executable, "-c", "import time; time.sleep(30)"]))
        self.assertEqual((status, report["status"], report["ended"]["reason"], report["rejections"]), (124, "timeout", "timeout", []))

    def test_text_report(self):
        program = self.write("main.py", (
            "def first(x):\n    return x  # REJECT one (compiling first(int) for the call at {file}:5)\n\n"
            "def caller():\n    return first(1)  # REJECT two\n\nclass Box:\n    size = 1  # REJECT three\n"))
        status, text = self.survey(program, text=True)
        self.assertEqual(status, 1)
        self.assertEqual(text.splitlines(), [
            f"1. {program}:2: error: one (compiling first(int) for the call at {program}:5)",
            "   in first",
            f"2. {program}:5: error: two",
            "   in caller; may follow from the stub of first (rejection 1)",
            f"3. {program}:8: error: three",
            "   in class Box, outside any function",
            f"3 rejections in 3 compilations of {program}. The survey ended at {program}:8: a statement in class Box, "
            "outside any function, cannot be stubbed.",
            survey.LIMITS])
        self.assertIn("unless its parameters and result are all annotated", survey.LIMITS)

    def test_keep_and_a_symbolic_link(self):
        real = self.write("app/main.py", "import helper\n\ndef f():\n    x = 1\n    return x  # REJECT kept\n")
        self.write("app/helper.py", "def g():\n    return 1  # REJECT beside the real file\n")
        (self.directory / "links").mkdir()
        os.symlink(real, self.directory / "links/program.py")
        kept = self.directory / "kept"
        status, report = self.survey(str(self.directory / "links/program.py"), "--keep", str(kept))
        self.assertEqual([(r["file"], r["definition"]) for r in report["rejections"]],
                         [(real, "f"), (str(self.directory / "app/helper.py"), "g")])
        self.assertEqual((kept / "program/main.py").read_text(), f"import helper\n\ndef f():\n    {survey.STUB}\n\n")
        self.assertFalse((kept / "program/main.py").is_symlink())
        self.assertEqual(Path(real).read_text().count("REJECT"), 1)

    def test_a_stubbed_files_encoding_and_line_ends_are_kept(self):
        latin = "# -*- coding: latin-1 -*-\nimport helper\nNAME = 'café'\n\ndef f():\n    return NAME  # REJECT latin-1\n"
        marked = "\ufeff# ü\r\ndef g():\r\n    return 1  # REJECT with a byte order mark\r\n"
        program = self.directory / "app/main.py"
        program.parent.mkdir()
        program.write_bytes(latin.encode("latin-1"))
        (self.directory / "app/helper.py").write_bytes(marked.encode("utf-8"))
        status, report = self.survey(str(program), "--keep", str(self.directory / "kept"))
        self.assertEqual((status, report["ended"]["reason"]), (1, "compiled"))
        self.assertEqual([r["definition"] for r in report["rejections"]], ["f", "g"])
        kept = self.directory / "kept/program"
        self.assertEqual((kept / "main.py").read_bytes(), latin.replace("return NAME  # REJECT latin-1", survey.STUB).encode("latin-1"))
        self.assertEqual((kept / "helper.py").read_bytes(),
                         marked.replace("return 1  # REJECT with a byte order mark", survey.STUB).encode("utf-8"))

    def test_usage_errors(self):
        program = self.write("main.py", "print(1)\n")
        for arguments in (["--max", "0", program], ["--timeout", "0", program], ["--timeout", "inf", program],
                          ["--compiler", "", program], ["--compiler", "'", program], [str(self.directory / "missing.py")],
                          [str(self.directory)], ["--keep", str(self.directory), program], []):
            with self.subTest(arguments=arguments), contextlib.redirect_stderr(io.StringIO()), \
                    mock.patch.object(survey, "compile_once") as compile_once:
                with self.assertRaises(SystemExit) as caught:
                    survey.main(arguments)
                self.assertEqual(caught.exception.code, 2)
                compile_once.assert_not_called()


HOSTED = '''from typing import Iterator
import helper
from pkg import sub


def template(items):
    return items + 1


def numbers(n: int) -> Iterator[int]:
    for i in range(n):
        yield i + "g"


class Box:
    def __init__(self, v: int) -> None:
        self.v = v + "i"

    def __len__(self):
        return 1 + "l"

    def get(self) -> int:
        return self.v


def one(x: int) -> int: return x + "a"


def main() -> None:
    b = Box(1)
    print(len(b))
    print(b.get())
    print(one(1))
    print(template([1]))
    print(helper.broken(1), sub.f(1))
    for i in numbers(2):
        print(i)


main()
'''


class HostedCompilerTests(unittest.TestCase):
    """The diagnostics and the stubs against the checkout's compiler, run by CPython. Only where
    a rejection is and what it stops are compared, never a message's text."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}

    def write(self, name, text):
        path = self.directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def survey(self, *arguments):
        run = subprocess.run([sys.executable, str(ROOT / "tools/rejection_survey.py"), "--json", *arguments],
                             cwd=self.directory, env=self.env, capture_output=True, text=True, timeout=120)
        self.assertEqual(run.stderr, "")
        return run.returncode, json.loads(run.stdout)

    def test_every_stubbed_function_compiles_and_other_lines_keep_their_numbers(self):
        self.write("main.py", HOSTED)
        self.write("helper.py", "def broken(x: int) -> str:\n    return x + 'z'\n")
        self.write("pkg/__init__.py", "")
        self.write("pkg/sub.py", "from .deep import leaf\n\n\ndef f(x: int) -> int:\n    return leaf.g(x)\n")
        self.write("pkg/deep/__init__.py", "")
        self.write("pkg/deep/leaf.py", "def g(x: int) -> int:\n    return x + 'leaf'\n")
        before = digests(self.directory)
        status, report = self.survey("main.py")
        self.assertEqual((status, report["status"], report["ended"]["reason"]), (1, "rejected", "compiled"))
        self.assertEqual(report["compiler"], [sys.executable, str(ROOT / "pystachy.py")])
        found = {(r["file"], r["line"], r["definition"]): r for r in report["rejections"]}
        self.assertEqual(sorted(found), [
            ("helper.py", 2, "broken"), ("main.py", 7, "template"), ("main.py", 12, "numbers"),
            ("main.py", 17, "Box.__init__"), ("main.py", 20, "Box.__len__"), ("main.py", 23, "Box.get"),
            ("main.py", 26, "one"), ("pkg/deep/leaf.py", 2, "g")])
        self.assertTrue(all(r["stubbed"] for r in report["rejections"]))
        self.assertEqual(report["compilations"], len(found) + 1)
        # The compiler names the call that made it compile a function without annotations.
        self.assertEqual(found["main.py", 7, "template"]["call_sites"], [{"file": "main.py", "line": 34}])
        # Box.get() reads the field that only the stubbed __init__ assigned; main(), which holds
        # the call sites, uses every stubbed function, but none of those statements does.
        get = found.pop(("main.py", 23, "Box.get"))
        self.assertEqual(get["may_follow_from"], [found["main.py", 17, "Box.__init__"]["index"]])
        self.assertEqual([r["may_follow_from"] for r in found.values()], [[]] * 7)
        self.assertEqual(digests(self.directory), before)

    def test_a_file_cpython_cannot_parse_ends_the_survey(self):
        self.write("main.py", "import helper\n\n\ndef f(x: int) -> int:\n    return x + 'a'\n\n\nprint(f(1))\n")
        self.write("helper.py", "def g(:\n    pass\n")
        status, report = self.survey("main.py")
        self.assertEqual((status, report["status"], report["ended"]["reason"]), (1, "rejected", "unparsable"))
        last = report["rejections"][-1]
        self.assertEqual((last["file"], last["line"], last["definition"], last["scope"], last["stubbed"]),
                         ("helper.py", 1, None, "unknown", False))


if __name__ == "__main__":
    unittest.main()
