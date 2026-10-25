"""Guards for the experimental integer frontend and its default-mode boundary."""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.pystachy_compiler.driver import compile_program  # noqa: E402
from src.pystachy_compiler.integer_mode import integer_parse, integer_pragma  # noqa: E402
from src.pystachy_compiler.lexer import Lexer  # noqa: E402
from src.pystachy_compiler.parser import Parser  # noqa: E402


PRAGMA = '# pystachy: python-int\n'


def tree(node):
    return node.kind, node.s, node.line, [tree(child) for child in node.kids]


class IntegerModeTests(unittest.TestCase):
    def reject(self, source, message):
        err = StringIO()
        with redirect_stderr(err), self.assertRaises(SystemExit):
            integer_parse(PRAGMA + source, 1)
        self.assertIn(message, err.getvalue())

    def test_leading_comment_only(self):
        self.assertTrue(integer_pragma('#!/usr/bin/python3\n\n' + PRAGMA))
        self.assertFalse(integer_pragma('x = 1\n' + PRAGMA))
        self.assertFalse(integer_pragma('"' + PRAGMA.strip() + '"\n'))
        self.assertFalse(integer_pragma('# pystachy: python-integer\n'))

    def test_default_ast_unchanged(self):
        source = '"doc"\nx: int = 123\ndef f(a: int) -> int:\n    return a + 1\n'
        self.assertEqual(tree(integer_parse(source, 1)), tree(Parser(Lexer(source, 1).file()).module()))

    def test_preserves_large_radix_literal(self):
        node = integer_parse(PRAGMA + 'x = 0x10000000000000000\n', 1)
        call = node.kids[-1].kids[-1]
        self.assertEqual(call.kind, 'call')
        self.assertEqual(call.kids[1].s, '0x10000000000000000')
        self.assertEqual(call.kids[1].kind, 'str')
        self.assertEqual(call.kids[2].s, '0')

    def test_oversized_decimal_literal_parses_with_base_zero(self):
        node = integer_parse(PRAGMA + 'x = 18446744073709551616\n', 1)
        call = node.kids[-1].kids[-1]
        self.assertEqual(call.kids[0].s, '_pys_promoting_convert_base')
        self.assertEqual((call.kids[1].kind, call.kids[1].s), ('str', '18446744073709551616'))
        self.assertEqual((call.kids[2].kind, call.kids[2].s), ('int', '0'))

    def test_quoted_annotations_remain_forward_references(self):
        node = integer_parse(PRAGMA + 'def f(a: "Node | int") -> "list[\'int\']":\n    return [a]\n', 1)
        fn = node.kids[-1]
        self.assertEqual((fn.kids[0].kids[0].kids[0].kind, fn.kids[0].kids[0].kids[0].s), ('str', 'Node | _pys_promoting_int'))
        self.assertEqual((fn.kids[1].kind, fn.kids[1].s), ('str', "list['_pys_promoting_int']"))
        node = integer_parse(PRAGMA + 'x: "typing.int | intx | int_" = 1\n', 1)
        self.assertEqual(node.kids[-1].kids[1].s, 'typing.int | intx | int_')

    def test_literal_values_and_annotated_metadata_are_not_types(self):
        node = integer_parse(PRAGMA + 'x: Literal["int", 1] = "int"\ny: Annotated[int, "int doc", 2] = 3\n', 1)
        literal = node.kids[-2].kids[1].kids[1].kids
        self.assertEqual([(k.kind, k.s) for k in literal], [('str', 'int'), ('int', '1')])
        annotated = node.kids[-1].kids[1].kids[1].kids
        self.assertEqual([(k.kind, k.s) for k in annotated], [('name', '_pys_promoting_int'), ('str', 'int doc'), ('int', '2')])

    def test_preserves_docstring(self):
        node = integer_parse(PRAGMA + '"doc"\nx = 1\n', 1)
        self.assertEqual(node.kids[0].kids[0].s, 'doc')
        self.assertEqual(node.kids[1].kind, 'import')

    def test_binding_guards(self):
        for source in ['int = 1\n', 'x = int = 1\n', 'def f(int):\n    pass\n',
                       'for int in [1]:\n    pass\n', '[int for int in [1]]\n',
                       'with thing as int:\n    pass\n', '(int := 1)\n',
                       'try:\n    pass\nexcept Exception as int:\n    pass\n',
                       'def isinstance(a, b):\n    return False\n']:
            with self.subTest(source=source):
                self.reject(source, 'does not support rebinding')

    def test_unreviewed_combinations_rejected(self):
        self.reject('# pystachy: dynamic-any\nx = 1\n', 'cannot yet be combined')
        self.reject('from builtins import int as native\n', 'builtin import aliases')
        self.reject('from things import *\n', 'builtin import aliases')
        self.reject('alias = int\n', 'only in annotations')
        self.reject('isinstance(True, (int, str))\n', 'only in annotations')
        self.reject('_pys_promoting_int = 1\n', 'does not support rebinding')

    def test_imported_module_contract_and_no_state_leak(self):
        # Successive hosted compilations do not carry a global pragma state.
        dirs = [str(ROOT / 'lib')]
        promoted = compile_program('probe.py', PRAGMA + 'print(2 ** 100)\n', dirs, '')
        ordinary = compile_program('probe.py', 'print(2 + 3)\n', dirs, '')
        self.assertIn('pys_mpz_', promoted)
        self.assertNotIn('_pystachy_int', ordinary)

    def test_shadowed_runtime_helper_rejected_only_with_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ['_pystachy_int', 'mpz']:
                with self.subTest(name=name):
                    path = Path(tmp) / (name + '.py')
                    path.write_text('value = 19\n')
                    dirs = [tmp, str(ROOT / 'lib')]
                    err = StringIO()
                    with redirect_stderr(err), self.assertRaises(SystemExit):
                        compile_program('probe.py', PRAGMA + 'print(1)\n', dirs, '')
                    self.assertIn('requires the unshadowed shipped', err.getvalue())
                    ordinary = compile_program('probe.py', 'from ' + name + ' import value\nprint(value)\n', dirs, '')
                    self.assertNotIn('pys_mpz_binop', ordinary)
                    path.unlink()

    def test_private_integer_fields_rejected(self):
        err = StringIO()
        with redirect_stderr(err), self.assertRaises(SystemExit):
            compile_program('probe.py', PRAGMA + 'x = 1\nx._small = 2\n', [str(ROOT / 'lib')], '')
        self.assertIn("has no attribute '_small'", err.getvalue())


if __name__ == '__main__':
    unittest.main()
