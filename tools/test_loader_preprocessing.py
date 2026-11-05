"""Loader preprocessing preserves scope while avoiding work on irrelevant trees."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler import loader
from src.pystachy_compiler.lexer import Lexer
from src.pystachy_compiler.parser import Parser
from src.pystachy_compiler.syntax import mk


def parsed(source):
    return Parser(Lexer(source, 1).file()).module()


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
