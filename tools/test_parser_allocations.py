"""Parser fast paths preserve syntax and diagnostics without allocating unused lists."""
import ast
from contextlib import redirect_stderr
import dis
from io import StringIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler import diagnostics
from src.pystachy_compiler.lexer import Lexer, Tok
from src.pystachy_compiler.parser import Parser
from src.pystachy_compiler.syntax import mk


def parsed(expression):
    source = ("result = " + expression + "\n").encode("utf-8").decode("latin1")
    return Parser(Lexer(source, 1).file()).module().kids[0].kids[-1]


class ParserFastPathTests(unittest.TestCase):
    def setUp(self):
        state = patch.multiple(diagnostics, SRC="parser.py", FILES=[], CAPTURE=False)
        state.start()
        self.addCleanup(state.stop)

    def test_comparison_operators_and_operand_order_match_python(self):
        operators = {"==": ast.Eq, "!=": ast.NotEq, "<": ast.Lt, "<=": ast.LtE,
                     ">": ast.Gt, ">=": ast.GtE, "in": ast.In, "not in": ast.NotIn,
                     "is": ast.Is, "is not": ast.IsNot}

        def shape(node):
            if node.kind == "name":
                return ("name", node.s)
            if node.kind == "binop":
                return ("binary", node.s, *(shape(k) for k in node.kids))
            self.assertEqual(node.kind, "cmp")
            return ("compare", [operators[op].__name__ for op in node.s.split(",")],
                    [shape(k) for k in node.kids])

        def python_shape(node):
            if isinstance(node, ast.Name):
                return ("name", node.id)
            if isinstance(node, ast.BinOp):
                op = "+" if isinstance(node.op, ast.Add) else "*"
                return ("binary", op, python_shape(node.left), python_shape(node.right))
            self.assertIsInstance(node, ast.Compare)
            return ("compare", [type(op).__name__ for op in node.ops],
                    [python_shape(k) for k in [node.left, *node.comparators]])

        expressions = ["value", "left + right", *("left " + op + " right" for op in operators),
                       "a < b <= c is not d not in e", "a + b < c * d", "(a < b) == (c > d)"]
        for expression in expressions:
            with self.subTest(expression=expression):
                self.assertEqual(shape(parsed(expression)), python_shape(ast.parse(expression, mode="eval").body))

    def test_noncomparison_leaves_the_next_token_untouched(self):
        for tail in ("not other", "not", "island", "if condition else other", "and other", ", other"):
            with self.subTest(tail=tail):
                instance = Parser(Lexer("value " + tail + "\n", 1).file())
                expression = instance.comparison()
                self.assertEqual((expression.kind, expression.s, instance.p), ("name", "value", 1))

    def test_first_lookahead_keeps_tokenizer_and_parser_diagnostics(self):
        for kind, expected in (("error", "tokenizer failure"), ("stop", "tokenizer failure"),
                               ("?", "invalid syntax")):
            with self.subTest(kind=kind):
                instance = Parser([Tok(kind, "tokenizer failure", 7), Tok("eof", "", 7)])
                expression = mk("name", "value", 7, [])
                with patch.object(instance, "binary", return_value=expression), redirect_stderr(StringIO()) as output:
                    with self.assertRaises(SystemExit) as caught:
                        instance.comparison()
                self.assertEqual(caught.exception.code, 1)
                self.assertEqual(output.getvalue(), f"parser.py:7: error: {expected}\n")

    def test_incomplete_comparisons_keep_diagnostics(self):
        for expression in ("value <", "value is not", "value not other", "value not in", "value < < other"):
            with self.subTest(expression=expression), redirect_stderr(StringIO()) as output:
                with self.assertRaises(SystemExit) as caught:
                    parsed(expression)
                self.assertEqual(caught.exception.code, 1)
                self.assertEqual(output.getvalue(), "parser.py:1: error: invalid syntax\n")

    def test_noncomparison_executes_no_list_allocation(self):
        code = Parser.comparison.__code__
        instructions = {instruction.offset: instruction.opname for instruction in dis.get_instructions(code)}

        def allocations(expression):
            instance = Parser(Lexer(expression + "\n", 1).file())
            made = []

            def trace(frame, event, arg):
                if frame.f_code is not code:
                    return None
                frame.f_trace_opcodes = True
                if event == "opcode" and instructions.get(frame.f_lasti) == "BUILD_LIST":
                    made.append(frame.f_lasti)
                return trace

            previous = sys.gettrace()
            try:
                sys.settrace(trace)
                instance.comparison()
            finally:
                sys.settrace(previous)
            return len(made)

        self.assertEqual(allocations("ordinary"), 0)
        self.assertGreater(allocations("left < right"), 0)  # prove the allocation observer is active

    def test_literal_values_match_python_for_plain_raw_escaped_empty_and_unicode(self):
        literals = ['""', '"ordinary text"', '"café λ"', 'r"café\\n"', '"a\\nb\\tc"',
                    '"\\x41\\u03bb\\U0001f600"', '"line\\\ncontinued"', '"a" "b"',
                    'f"literal text"', 'f"café\\n"', 'b"ordinary bytes"', 'br"raw\\n"', 'b"\\x41"']
        for literal in literals:
            with self.subTest(literal=literal):
                # These expressions contain only literals; CPython independently decodes them.
                expected = eval(literal, {"__builtins__": {}}, {})
                node = parsed(literal)
                self.assertEqual(node.kind, "bytes" if isinstance(expected, bytes) else "str")
                encoded = expected if isinstance(expected, bytes) else expected.encode("utf-8")
                self.assertEqual(node.s.encode("latin1"), encoded)

    def test_plain_unescape_reuses_immutable_input_without_character_collection(self):
        class Unvisited(str):
            def __getitem__(self, index):
                raise AssertionError("plain literal should not be collected character by character")

        instance = Parser([Tok("eof", "", 1)])
        for text in ("", "ordinary text", "café λ", "line\nnext"):
            source = Unvisited(text)
            self.assertIs(instance.unescape(source, 1), source)

    def test_invalid_escape_keeps_position_after_plain_unicode(self):
        instance = Parser([Tok("eof", "", 1)])
        with redirect_stderr(StringIO()) as output, self.assertRaises(SystemExit) as caught:
            instance.unescape("é\\x1".encode("utf-8").decode("latin1"), 4)
        self.assertEqual(caught.exception.code, 1)
        self.assertEqual(output.getvalue(), "parser.py:4: error: (unicode error) 'unicodeescape' codec can't "
                         "decode bytes in position 10-12: truncated \\xXX escape\n")


if __name__ == "__main__":
    unittest.main()
