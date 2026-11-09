"""Loader preprocessing and import resolution match their independent controls."""
from importlib.machinery import PathFinder
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler import analysis, loader
from src.pystachy_compiler.lexer import Lexer
from src.pystachy_compiler.module import Mod
from src.pystachy_compiler.parser import Parser
from src.pystachy_compiler.syntax import mk, names_in


def parsed(source):
    return Parser(Lexer(source, 1).file()).module()


class ImportFileKindTests(unittest.TestCase):
    @staticmethod
    def candidate(path, kind, target):
        path.parent.mkdir(parents=True, exist_ok=True)
        if kind == "directory":
            path.mkdir()
        elif kind == "fifo":
            os.mkfifo(path)
        else:
            path.symlink_to(target)

    def test_source_candidates_follow_cpython_regular_file_rule(self):
        kinds = ["directory", "symlink"] + (["fifo"] if hasattr(os, "mkfifo") else [])
        for suffix in ("chosen.py", "chosen/__init__.py"):
            for kind in kinds:
                with self.subTest(candidate=suffix, kind=kind), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    first, last = root / "first", root / "last"
                    first.mkdir()
                    last.mkdir()
                    target = root / "target.py"
                    target.write_text("VALUE = 31\n")
                    (last / "chosen.py").write_text("VALUE = 32\n")
                    self.candidate(first / suffix, kind, target)
                    directories = [str(first), str(last)]
                    expected = PathFinder.find_spec("chosen", directories)
                    self.assertIsNotNone(expected)
                    self.assertEqual(loader.Loader(directories).filepath("chosen"), expected.origin)

    def test_ffi_nonregular_candidates_do_not_hide_the_builtin(self):
        root = Path(__file__).resolve().parent.parent
        kinds = ["directory"] + (["fifo"] if hasattr(os, "mkfifo") else [])
        for suffix in ("ffi.py", "ffi/__init__.py"):
            for kind in kinds:
                with self.subTest(candidate=suffix, kind=kind), tempfile.TemporaryDirectory() as temporary:
                    work = Path(temporary)
                    source = work / "main.py"
                    source.write_text('import ffi\nprint("ok")\n')
                    self.candidate(work / suffix, kind, work / "unused.py")
                    environment = {key: value for key, value in os.environ.items()
                                   if not key.startswith("PYSTACHY_")}
                    environment["PYSTACHY_HOME"] = str(root)
                    result = subprocess.run([sys.executable, str(root / "pystachy.py"), "ir", str(source)],
                                            env=environment, capture_output=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr.decode())
                    self.assertIn(b"define i32 @main(", result.stdout)


class BindingTargetTests(unittest.TestCase):
    @staticmethod
    def reference(st, out, walrus):
        # The original list collector remains an independent oracle for dict insertion order.
        kind = st.kind
        if kind in ("assign", "annassign", "augassign", "for", "compfor", "with"):
            names = []
            if kind == "with":
                for item in st.kids[:-1]:
                    if len(item.kids) == 2:
                        names_in(item.kids[1], names)
            for i in range(len(st.kids) - 1 if kind == "assign" else 0 if kind == "with" else 1):
                names_in(st.kids[i], names)
            for name in names:
                out[name] = True
        if walrus:
            analysis.stmt_walrus(st, out)

    @staticmethod
    def statements():
        source = ('a = b = value\n'
                  'a: int\n'
                  'a += (update := 1)\n'
                  'a, (b, *rest), a = (rhs := value)\n'
                  'for a, b in (items := value):\n    hidden = 1\n'
                  'with first() as (a, b), (context := second()) as a:\n    hidden = 1\n'
                  'if (condition := True):\n    hidden = 1\n'
                  'fn = lambda arg=(default := 1): (inside := 2)\n')
        statements = parsed(source).kids
        statements.append(mk("compfor", "", 1,
                             [mk("tuple", "", 1, [mk("name", "a", 1, []), mk("name", "b", 1, [])]),
                              mk("walrus", "items", 1, [mk("name", "value", 1, [])])]))
        return statements

    def test_target_dict_matches_list_collector_and_keeps_duplicates_in_order(self):
        class Writes(dict):
            def __init__(self):
                super().__init__({"first": False, "a": False})
                self.writes = []

            def __setitem__(self, key, value):
                self.writes.append((key, value))
                super().__setitem__(key, value)

        name = mk("name", "a", 1, [mk("name", "ignored_child", 1, [])])
        nested = mk("tuple", "", 1, [name, mk("list", "", 1,
                    [mk("name", "b", 1, []), mk("starred", "", 1, [name])])])
        targets = [name, nested]
        targets.extend(mk(kind, "ignored", 1, [nested])
                       for kind in ("attr", "index", "call", "walrus", "block", "unknown"))
        for target in targets:
            with self.subTest(kind=target.kind):
                names = []
                names_in(target, names)
                expected = Writes()
                for item in names:
                    expected[item] = True
                actual = Writes()
                analysis.target_names(target, actual)
                self.assertEqual(list(actual.items()), list(expected.items()))
                self.assertEqual(actual.writes, expected.writes)

    def test_statement_targets_match_original_collector_with_and_without_walrus(self):
        for statement in self.statements():
            for walrus in (False, True):
                with self.subTest(kind=statement.kind, walrus=walrus):
                    expected = {"first": False, "a": False}
                    actual = dict(expected)
                    self.reference(statement, expected, walrus)
                    analysis.targets(statement, actual, walrus)
                    self.assertEqual(list(actual.items()), list(expected.items()))
                    self.assertNotIn("hidden", actual)
                    self.assertNotIn("inside", actual)

    def test_dict_collectors_do_not_use_the_temporary_names_list_helper(self):
        statements = self.statements()
        with patch.object(analysis, "names_in", side_effect=AssertionError("temporary names list")):
            for statement in statements:
                analysis.targets(statement, {})
            out = {}
            analysis.target_names(mk("tuple", "", 1, [mk("name", "bound", 1, [])]), out)
            self.assertEqual(out, {"bound": True})


class VersionExpressionTests(unittest.TestCase):
    def setUp(self):
        self.instance = loader.Loader([])
        self.module = Mod("", "version.py", "")
        self.module.spec = {"sys": "sys", "alias": "sys"}
        self.module.specat = {"sys": 0, "alias": 0}
        self.instance.pos = 1
        values = loader.VERSIONINFO
        self.version = ["(", values["sys.version_info.major"], values["sys.version_info.minor"],
                        values["sys.version_info.micro"], values["sys.version_info.releaselevel"][:-1],
                        values["sys.version_info.serial"]]

    def value(self, expression, own=False, scope=None):
        node = parsed("result = " + expression + "\n").kids[0].kids[-1]
        return self.instance.version(self.module, node, {} if scope is None else scope, own)

    def test_version_expressions_keep_fields_indices_slices_and_fresh_lists(self):
        cases = {
            "sys.version_info": self.version,
            "alias.version_info": self.version,
            "sys.version_info.major": [self.version[1]],
            "sys.version_info.releaselevel": [self.version[4]],
            "sys.version_info.unknown": [],
            "sys.version_info[0]": [self.version[1]],
            "sys.version_info[-1]": [self.version[5]],
            "sys.version_info[-5]": [self.version[1]],
            "sys.version_info[5]": [],
            "sys.version_info[:2]": self.version[:3],
            "sys.version_info[2:]": ["(", *self.version[3:]],
            "sys.version_info[1:4]": ["(", *self.version[2:5]],
            "sys.version_info[::2]": [],
            "sys.version_info[index]": [],
        }
        for expression, expected in cases.items():
            for own in (False, True):
                with self.subTest(expression=expression, own=own):
                    self.assertEqual(self.value(expression, own), expected)
        first = self.value("sys.version_info")
        first.append("changed")
        self.assertEqual(self.value("sys.version_info"), self.version)

    def test_non_version_expressions_do_not_materialize_version_values(self):
        class Unvisited(dict):
            def values(self):
                raise AssertionError("unrelated expression should not materialize VERSIONINFO")

        with patch.object(loader, "VERSIONINFO", Unvisited(loader.VERSIONINFO)):
            for expression, expected in (("ordinary", []), ("object.field", []), ("object[0]", []),
                                         ("1", ["1"]), ("-2", ["-2"]), ('"final"', ["'final"]),
                                         ('(3, "final")', ["(", "3", "'final"])):
                with self.subTest(expression=expression):
                    self.assertEqual(self.value(expression), expected)
                    self.assertEqual(self.value(expression, own=True), [])
            self.assertEqual(self.value("sys.version_info", scope={"sys": True}), [])
            self.module.rebound["sys"] = True
            self.assertEqual(self.value("sys.version_info.major"), [])

    def test_import_position_and_function_shadowing_still_control_version_recognition(self):
        self.instance.pos = 0
        self.assertEqual(self.value("sys.version_info"), [])
        self.instance.pos = -1
        self.assertEqual(self.value("sys.version_info"), self.version)
        self.instance.fs.spec["sys"] = "sys"
        self.assertEqual(self.value("sys.version_info"), [])
        self.instance.fsure["sys"] = True
        self.assertEqual(self.value("sys.version_info", scope={"sys": True}), self.version)
        self.instance.fs.rebound["sys"] = True
        self.assertEqual(self.value("sys.version_info", scope={"sys": True}), [])


class BinaryOpenScopeTests(unittest.TestCase):
    def test_binding_and_value_uses_disable_builtin_rewriting(self):
        cases = (
            'open = other\n',
            'def open():\n    pass\n',
            'def f(open):\n    pass\n',
            'from somewhere import thing as open\n',
            'f = open\n',
            'open("x", mode=open)\n',
            'class C:\n    def open(self):\n        pass\n    x = open("x", "rb")\n',
            'class C:\n    def open(self):\n        pass\n    def f(self, open):\n        pass\n',
        )
        for source in cases:
            with self.subTest(source=source):
                self.assertTrue(loader.opens_bound(parsed(source)))

    def test_unshadowed_calls_literals_attributes_and_method_bodies(self):
        cases = (
            'open("x", "rb")\n',
            'def f():\n    return open("x", "rb")\n',
            'print("open", b"open", obj.open)\n',
            'def f():\n    return other(open="value")\n',
            'class C:\n    def open(self):\n        return open("x", "rb")\n',
            'class C:\n    def open(self):\n        pass\n    def f(self):\n        return open("x", "rb")\n',
        )
        for source in cases:
            with self.subTest(source=source):
                self.assertFalse(loader.opens_bound(parsed(source)))

    def test_binding_predicates_stop_at_the_first_match(self):
        # A large irrelevant sibling must not be visited after the answer is known.
        tail = mk("block", "", 1, [mk("name", "ordinary", 1, []) for _ in range(500)])
        tree = mk("block", "", 1, [mk("name", "open", 1, []), tail])
        for name in ("opens_bound", "names_open"):
            with self.subTest(predicate=name):
                original = getattr(loader, name)
                with patch.object(loader, name, wraps=original) as visit:
                    self.assertTrue(visit(tree))
                    self.assertLessEqual(visit.call_count, 2)

    def test_binary_calls_are_rewritten_only_when_builtin_is_unshadowed(self):
        for shadowed in (False, True):
            source = ('open = other\n' if shadowed else '') + 'f = open("x", "rb")\n'
            tree = parsed(source)
            loader.binary_opens(tree)
            call = tree.kids[-1].kids[1]
            self.assertEqual(call.kids[0].s, "open" if shadowed else "_pys_bfile_reader")
            self.assertEqual(tree.kids[0].kind, "assign" if shadowed else "import")


class ContextmanagerScopeTests(unittest.TestCase):
    def test_no_contextmanager_import_leaves_class_bodies_unvisited(self):
        tree = parsed('class Base:\n    pass\nclass Child(Base):\n    def f(self):\n        pass\n')
        names = loader.cm_names(tree)
        self.assertEqual(names, [])

        class Unvisited(list):
            def __iter__(self):
                raise AssertionError("unrelated class bodies should not be scanned")

        tree.kids = Unvisited(tree.kids)
        loader.cm_methods(tree, names)

    def test_imported_alias_still_rewrites_contextmanager_methods(self):
        tree = parsed('from contextlib import contextmanager as cm\n'
                      'class C:\n    @cm\n    def opened(self):\n        yield 1\n')
        loader.cm_methods(tree, loader.cm_names(tree))
        cls = next(n for n in tree.kids if n.kind == "class")
        self.assertEqual([n.s for n in cls.kids[0].kids], ["_pys_cm_opened", "opened"])


if __name__ == "__main__":
    unittest.main()
