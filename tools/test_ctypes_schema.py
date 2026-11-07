"""The static ctypes subset accepts complete declarations and rejects unsafe guesses.

These tests run only the source loader; the c_ctypes_*.py programs exercise the
resulting ABI calls against real CPython ctypes in the JIT/AOT FFI suite.
"""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler import ctypes_schema, diagnostics, loader
from src.pystachy_compiler.lexer import Lexer
from src.pystachy_compiler.parser import Parser


ROOT = Path(__file__).resolve().parent.parent
IMPORT = "import ctypes as ct\n"
LIBRARY = IMPORT + "lib = ct.CDLL(None)\n"
DECLARED = LIBRARY + "lib.abs.argtypes = [ct.c_int]\nlib.abs.restype = ct.c_int\n"


def parsed(source):
    return Parser(Lexer(source, 1).file()).module()


def walk(node):
    yield node
    for child in node.kids:
        yield from walk(child)


def call_names(node):
    return [ctypes_schema.dotted(n.kids[0]) for n in walk(node) if n.kind == "call"]


def foreign_declarations(body):
    return [n for n in body.kids if n.kind == "def" and len(n.kids) == 4
            and n.kids[3].kids and n.kids[3].kids[0].kids[0].s == "extern"]


class CtypesSchemaTests(unittest.TestCase):
    def setUp(self):
        state = patch.multiple(diagnostics, SRC="schema.py", FILES=[], CAPTURE=False)
        state.start()
        self.addCleanup(state.stop)

    def lower(self, source):
        body = parsed(source)
        ctypes_schema.lower_ctypes(body)
        return body

    def assert_rejected(self, source, message="ctypes declarations:", line=None):
        with redirect_stderr(StringIO()) as output, self.assertRaises(SystemExit) as caught:
            self.lower(source)
        self.assertEqual(caught.exception.code, 1)
        self.assertIn(message, output.getvalue())
        if line is not None:
            self.assertIn(f"schema.py:{line}: error:", output.getvalue())
        return output.getvalue()

    def test_relative_ctypes_imports_are_not_lowered(self):
        for module in (".ctypes", "..ctypes", "...ctypes"):
            with self.subTest(module=module):
                source = (f"from {module} import api as ct\n"
                          "lib = ct.CDLL(None)\n"
                          "lib.abs.argtypes = [ct.c_int]\n"
                          "lib.abs.restype = ct.c_int\n"
                          "print(lib.abs(-7))\n")
                body = parsed(source)
                before = [(n.kind, n.s, n.line) for n in walk(body)]
                self.assertFalse(ctypes_schema.ctypes_import(body.kids[0]))
                ctypes_schema.lower_ctypes(body)
                self.assertEqual([(n.kind, n.s, n.line) for n in walk(body)], before)

    def test_relative_alias_stays_local_beside_an_absolute_ctypes_import(self):
        body = parsed("import ctypes as standard\n"
                      "from .ctypes import api as ct\n"
                      "lib = ct.CDLL(None)\n"
                      "lib.abs.argtypes = [ct.c_int]\n"
                      "lib.abs.restype = ct.c_int\n"
                      "print(lib.abs(-7))\n")
        before = [(n.kind, n.s, n.line) for n in walk(body)]
        ctypes_schema.lower_ctypes(body)
        self.assertEqual([(n.kind, n.s, n.line) for n in walk(body)], before)

    def test_aliases_tuple_signatures_and_restype_first(self):
        body = self.lower(
            "from ctypes import CDLL as Library, c_int32 as Int, c_void_p as Address, POINTER as Ptr\n"
            'lib = Library("libexample.so")\n'
            "lib.make.restype = Int\n"
            "lib.make.argtypes = (Int, Ptr(Address))\n"
            "result = lib.make(7, byref(cell))\n"
        )
        declarations = foreign_declarations(body)
        self.assertEqual(len(declarations), 1)
        decorator = declarations[0].kids[3].kids[0]
        self.assertEqual([n.s for n in decorator.kids[1:]], ["libexample.so", "make"])
        self.assertNotIn("lib.make", call_names(body))
        self.assertIn("byref", call_names(body))

    def test_library_and_symbol_binding_keep_original_execution_order(self):
        body = self.lower(
            IMPORT +
            "import before_open\n"
            'lib = ct.CDLL("libexample.so")\n'
            "import after_open\n"
            "lib.first.restype = ct.c_int\n"
            "pass\n"
            "lib.first.argtypes = []\n"
            "import between_symbols\n"
            "lib.second.argtypes = []\n"
            "lib.second.restype = None\n"
        )
        events = []
        for statement in body.kids:
            if statement.kind == "import":
                events.extend(a.s for a in statement.kids
                              if a.s in ("before_open", "after_open", "between_symbols"))
            elif statement.kind == "expr" and statement.kids[0].kind == "call":
                call = statement.kids[0]
                if call.kids[0].s == "load_library":
                    events.append("open")
                    self.assertEqual(statement.line, 3)
            elif statement in foreign_declarations(body):
                decorator = statement.kids[3].kids[0]
                events.append(decorator.kids[2].s)
                self.assertEqual(decorator.line, 5 if events[-1] == "first" else 9)
        self.assertEqual(events, ["before_open", "open", "after_open", "first", "between_symbols", "second"])

    def test_unused_library_still_loads(self):
        body = self.lower(IMPORT + 'unused = ct.CDLL("missing-library.so")\n')
        opens = [n for n in walk(body) if n.kind == "call" and n.kids[0].s == "load_library"]
        self.assertEqual(len(opens), 1)
        self.assertEqual(opens[0].kids[1].s, "missing-library.so")
        self.assertEqual(foreign_declarations(body), [])

    def test_library_text_is_data_not_generated_python(self):
        library = "quote'\\name\nnot_a_python_statement.so"
        body = self.lower(IMPORT + f"lib = ct.CDLL({library!r})\n"
                          + "lib.run.argtypes = []\nlib.run.restype = None\n")
        declaration = foreign_declarations(body)[0]
        self.assertEqual(declaration.kids[3].kids[0].kids[1].s, library)
        opens = [n for n in walk(body) if n.kind == "call" and n.kids[0].s == "load_library"]
        self.assertEqual(opens[0].kids[1].s, library)

    def test_argument_expressions_stay_at_call_site_in_original_order(self):
        body = parsed(LIBRARY + "lib.pair.argtypes = [ct.c_int, ct.c_int]\n"
                      + "lib.pair.restype = ct.c_int\nresult = lib.pair(first(), second())\n")
        call = body.kids[-1].kids[1]
        arguments = list(call.kids[1:])
        ctypes_schema.lower_ctypes(body)
        self.assertEqual(call.kids[1:], arguments)
        self.assertEqual([n.kids[0].s for n in call.kids[1:]], ["first", "second"])
        self.assertEqual(call.kids[0].kind, "name")
        self.assertEqual(sum(n is arguments[0] for n in walk(body)), 1)
        self.assertEqual(sum(n is arguments[1] for n in walk(body)), 1)

    def test_function_locals_hide_library_and_import_alias(self):
        body = self.lower(DECLARED
                          + "def local_library(lib):\n    return lib.abs(7)\n"
                          + "def local_import(ct):\n    return ct.c_int\n"
                          + "def global_library():\n    return lib.abs(-7)\n")
        functions = {n.s: n for n in body.kids if n.kind == "def"}
        self.assertEqual(call_names(functions["local_library"]), ["lib.abs"])
        attrs = [ctypes_schema.dotted(n) for n in walk(functions["local_import"]) if n.kind == "attr"]
        self.assertEqual(attrs, ["ct.c_int"])
        self.assertNotIn("lib.abs", call_names(functions["global_library"]))

    def test_function_defaults_use_the_enclosing_scope(self):
        body = self.lower(DECLARED + "def local(lib=lib.abs(-7)):\n    return lib\n")
        function = next(n for n in body.kids if n.kind == "def" and n.s == "local")
        self.assertNotIn("lib.abs", call_names(function))
        self.assertEqual(function.kids[2].kids[0].kids[0].s, "lib")

    def test_generated_names_do_not_replace_user_bindings(self):
        body = self.lower(DECLARED + "_pys_ctypes_fn0 = 99\nresult = lib.abs(-7)\n")
        names = [n.s for n in body.kids if n.kind == "def"]
        self.assertNotIn("_pys_ctypes_fn0", names)
        assignments = [n for n in body.kids if n.kind == "assign"]
        self.assertEqual(assignments[0].kids[0].s, "_pys_ctypes_fn0")
        self.assertEqual(assignments[0].kids[1].s, "99")

    def test_cells_and_copy_helpers_do_not_need_library_declarations(self):
        source = ("from ctypes import c_void_p, byref, string_at\n"
                  "cell = c_void_p()\nref = byref(cell)\nvalue = string_at(cell.value, 0)\n")
        body = self.lower(source)
        self.assertEqual(call_names(body), ["c_void_p", "byref", "string_at"])
        self.assertEqual([a.s for a in body.kids[0].kids], ["c_void_p", "byref", "string_at"])

    def test_missing_or_computed_signatures_are_rejected(self):
        declarations = (
            "lib.abs.argtypes = [ct.c_int]\n",
            "lib.abs.restype = ct.c_int\n",
            "lib.abs.argtypes = None\nlib.abs.restype = ct.c_int\n",
            "lib.abs.argtypes = types\nlib.abs.restype = ct.c_int\n",
            "lib.abs.argtypes = [ct.c_int]\nlib.abs.restype = choose_type()\n",
        )
        for source in declarations:
            with self.subTest(source=source):
                self.assert_rejected(LIBRARY + source)
        self.assert_rejected(LIBRARY + "print(lib.abs(-1))\n", "explicit argtypes and restype", 3)

    def test_unsupported_types_and_pointer_shapes_are_rejected(self):
        for ctype in ("ct.c_bool", "ct.c_ubyte", "ct.c_size_t", "ct.c_uint64", "ct.Structure",
                      "ct.POINTER(ct.c_int)", "ct.POINTER(ct.POINTER(ct.c_void_p))", "None"):
            with self.subTest(ctype=ctype):
                self.assert_rejected(LIBRARY + f"lib.f.argtypes = [{ctype}]\nlib.f.restype = None\n",
                                     "unsupported C type", 3)
        self.assert_rejected(LIBRARY + "lib.f.argtypes = []\nlib.f.restype = ct.POINTER(ct.c_void_p)\n",
                             "unsupported C type", 4)

    def test_loader_options_and_computed_library_names_are_rejected(self):
        for argument in ("path", '"one" + "two"', '"x", mode=1', '"x", use_errno=True',
                         'name="x"', 'b"x"', '"x\\0y"'):
            with self.subTest(argument=argument):
                self.assert_rejected(IMPORT + f"lib = ct.CDLL({argument})\n", line=2)

    def test_signature_mutation_and_late_declarations_are_rejected(self):
        for tail in ("lib.abs.argtypes = [ct.c_int]\n", "lib.abs.restype = None\n",
                     "print(1)\nlib.other.argtypes = []\nlib.other.restype = None\n",
                     "def f():\n    pass\nother = ct.CDLL(None)\n",
                     "def f():\n    local = ct.CDLL(None)\n"):
            with self.subTest(tail=tail):
                self.assert_rejected(DECLARED + tail)

    def test_signature_pair_cannot_span_other_execution_or_declarations(self):
        for middle in ("import unrelated\n", "other = ct.CDLL(None)\n",
                       "lib.other.argtypes = []\nlib.other.restype = None\n", "print(1)\n"):
            with self.subTest(middle=middle):
                self.assert_rejected(LIBRARY + "lib.abs.argtypes = [ct.c_int]\n" + middle
                                     + "lib.abs.restype = ct.c_int\n")

    def test_imports_must_precede_their_declarations(self):
        self.assert_rejected("lib = ct.CDLL(None)\n" + IMPORT, line=1)
        self.assert_rejected("from ctypes import CDLL\nlib = CDLL(None)\n"
                             "lib.abs.argtypes = [Int]\nlib.abs.restype = Int\n"
                             "from ctypes import c_int as Int\n", line=3)

    def test_library_function_objects_and_bindings_cannot_escape(self):
        for use in ("alias = lib\n", "alias = lib.abs\n", 'f = lib["abs"]\n', "lib = other\n",
                    "print(lib._handle)\n", 'getattr(lib, "abs")(-1)\n', "del lib\n"):
            with self.subTest(use=use):
                self.assert_rejected(DECLARED + use)
        self.assert_rejected(DECLARED + "ct = something_else\n", "single stable binding")

    def test_foreign_calls_require_exact_positional_arguments(self):
        for call in ("lib.abs()", "lib.abs(1, 2)", "lib.abs(n=-1)", "lib.abs(*values)",
                     "lib.abs(**values)", "lib.undeclared(-1)"):
            with self.subTest(call=call):
                self.assert_rejected(DECLARED + call + "\n", line=5)

    def test_cdll_python_attributes_are_not_foreign_symbols(self):
        for name in ("_handle", "_name", "_FuncPtr", "__class__", "__getitem__"):
            with self.subTest(name=name):
                self.assert_rejected(LIBRARY + f"lib.{name}.argtypes = []\nlib.{name}.restype = None\n",
                                     line=3)

    def test_unsupported_scopes_cannot_capture_library_names(self):
        for source in ("fn = lambda: lib.abs(-1)\n", "values = [lib.abs(x) for x in xs]\n",
                       "class Holder:\n    value = lib.abs(-1)\n"):
            with self.subTest(source=source):
                self.assert_rejected(DECLARED + source)


class CtypesLoaderResolutionTests(unittest.TestCase):
    def test_project_module_and_package_shadow_the_compatibility_module(self):
        for package in (False, True):
            with self.subTest(package=package), TemporaryDirectory() as directory:
                path = Path(directory) / ("ctypes/__init__.py" if package else "ctypes.py")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# This project owns ctypes.\n")
                instance = loader.Loader([directory, str(ROOT / "lib")])
                body = parsed(DECLARED + "print(lib.abs(-1))\n")
                with patch.object(loader, "lower_ctypes", side_effect=AssertionError("shadowed module")):
                    instance.ctypes(body)
                self.assertIn("lib.abs", call_names(body))

    def test_relative_ctypes_does_not_select_the_fallback_lowering(self):
        instance = loader.Loader([str(ROOT / "lib")])
        body = parsed("from .ctypes import api as ct\n"
                      "lib = ct.CDLL(None)\n"
                      "lib.abs.argtypes = [ct.c_int]\n"
                      "lib.abs.restype = ct.c_int\n")
        with patch.object(loader, "lower_ctypes", side_effect=AssertionError("relative import")):
            instance.ctypes(body)
        self.assertIn("ct.CDLL", call_names(body))

    def test_fallback_module_is_lowered(self):
        instance = loader.Loader([str(ROOT / "lib")])
        body = parsed(DECLARED + "print(lib.abs(-1))\n")
        instance.ctypes(body)
        self.assertEqual(len(foreign_declarations(body)), 1)
        self.assertNotIn("lib.abs", call_names(body))


if __name__ == "__main__":
    unittest.main()
