"""Typed IR prints as text and reads back unchanged; a pass runs on the text.

Run with python3 -m unittest discover -s tools -p test_typed_ir_text.py.
"""
from contextlib import redirect_stderr
from io import StringIO
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import typed_ir_text as text
from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.loader import Loader

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tools/fixtures/typed_ir"
EXAMPLE = ROOT / "tools/inspection_examples/score_samples.py"
WRITTEN = """function @written(left: int, names: dict[str,int]) -> None coroutine effects="R A" {
  %left.1 = slot left : int
  %left.def.1 = slot left k=1 : bool
  %stk.2 = slot k=2 : tuple[int,str]
entry:
  %t3 = rt dict.find x=!s (dict[str,int] %a1, str @s.4, int "ptrtoint (ptr @s.4 to i64)") : int
  %t4 = num.cmp < (int %t3, int -1) : bool
  check "KeyError: 'k'" x="Kind: text" (bool %t4) -> L5
L5: handler=L9
  ~%t6 %t7 = tuple.load int k=1 (tuple[int,str] %stk.2) : %slot
  call @f.other x=inline (%slot %t7, float "bitcast (i64 9218868437227405312 to double)") -> L8, L9 : None
L8:
  ret.none
L9:
  ~%t10 ~%t11 = landing(*exc %left.1) -> "" : exc
"":
  switch(int %t3, int 0, int 1) -> L8, L5, L8
cold "Kind: text" -> L8
loop kind=range mode="" head=L5 body=L8 step=L9 exit=L8 tests=[] indices=[%t3 "a b"] counter=%left.1 stop=(int 10) sequences=[] nonnegative=true
}
"""


def compiled(path, source=None):
    """Each function's record before the passes and as lowering takes it."""
    before, after = [], []
    optimize, lower = Gen.optimize, Gen.lower

    def passes(g, fn, on):
        before.append(text.from_ifn(fn))
        return optimize(g, fn, on)

    def lowering(g, fn):
        after.append(text.from_ifn(fn))
        lower(g, fn)

    with patch.object(Gen, "optimize", passes), patch.object(Gen, "lower", lowering):
        Gen().program(Loader([str(ROOT / "lib")]).program(str(path), path.read_text() if source is None else source))
    return before, after


class AtomTests(unittest.TestCase):
    def test_atoms_are_bare_where_the_parser_reads_them_back(self):
        for value in ("int", "dict[str,int]", "tuple[int,...]", "fn[c:3:outer.<locals>.f]", "%t10", "@s.1", "-0.5",
                      "*list[float]", "<", "list.get", "m$C", "opt[union[int,str]]"):
            with self.subTest(value=value):
                self.assertEqual(text.atom(value), value)
                self.assertEqual(text.read_atom(value + ", x", 0), (value, len(value)))
        for value in ("", "a b", 'q"uote', "ptrtoint (ptr @s.4 to i64)", "list[int", "a]", "a,b", "(", "tab\tbed", "new\nline"):
            with self.subTest(value=value):
                quoted = text.atom(value)
                self.assertEqual(json.loads(quoted), value)
                self.assertEqual(text.read_atom(quoted + ")", 0), (value, len(quoted)))

    def test_a_label_or_name_with_a_colon_is_quoted_before_a_colon(self):
        self.assertEqual(text.atom("a:b"), "a:b")
        self.assertEqual(text.atom("a:b", ":"), '"a:b"')
        self.assertEqual(text.read_atom('"a:b":', 0, ":"), ("a:b", 5))

    def test_an_ops_text_is_quoted_where_it_would_read_as_a_field_or_separator(self):
        for value in ("<", "==", "+", "dict.find", "@f.add", "OverflowError", "k", "-"):
            with self.subTest(value=value):
                self.assertEqual(text.text_atom(value), value)
        for value in ("->", ":", "k=1", "x=y", "a b", ""):
            with self.subTest(value=value):
                self.assertEqual(json.loads(text.text_atom(value)), value)
                self.assertNotEqual(text.text_atom(value), value)

    def test_needless_quotes_are_rejected(self):
        for line, stops in (('"int"', ""), ('"L5"', ":")):
            with self.subTest(line=line), self.assertRaisesRegex(text.TextError, "must be written bare"):
                text.read_atom(line, 0, stops)


class TextTests(unittest.TestCase):
    def test_written_function_reads_and_prints_unchanged(self):
        record = text.parse_function(WRITTEN)
        self.assertEqual(text.format_function(record), WRITTEN)
        self.assertEqual(text.roundtrip_errors(record), [])
        self.assertEqual(record["symbol"], "@written")
        self.assertEqual(record["parameters"], [{"name": "left", "type": "int"}, {"name": "names", "type": "dict[str,int]"}])
        self.assertTrue(record["coroutine"])
        self.assertEqual(record["effects"], "R A")
        self.assertEqual([s["immediate"] for s in record["slots"]], [0, 1, 2])
        self.assertEqual([s["results"] for s in record["slots"]], [[1], [1], [2]])
        self.assertEqual(record["blocks"][1]["operations"][0]["results"], [6, 7])
        self.assertEqual([b["label"] for b in record["blocks"]], ["entry", "L5", "L8", "L9", ""])
        self.assertEqual(record["blocks"][1]["handler"], "L9")
        find = record["blocks"][0]["operations"][0]
        self.assertEqual(find, {
            "op": "rt", "type": "int", "text": "dict.find", "immediate": 0, "descriptor": "!s", "results": [3],
            "operands": [{"value": "%a1", "type": "dict[str,int]"}, {"value": "@s.4", "type": "str"},
                         {"value": "ptrtoint (ptr @s.4 to i64)", "type": "int"}], "targets": []})
        self.assertEqual(record["blocks"][1]["operations"][1]["targets"], ["L8", "L9"])
        self.assertEqual(record["blocks"][3]["operations"][0]["targets"], [""])
        self.assertEqual(record["check_targets"], {"Kind: text": "L8"})
        self.assertEqual(record["loops"][0]["indices"], ["%t3", "a b"])
        self.assertEqual(record["loops"][0]["stop"], {"value": "10", "type": "int"})

    def test_comments_and_blank_lines_are_skipped(self):
        record = text.parse_function("; a test\n\n" + WRITTEN.replace("entry:\n", "entry:\n  ; why\n"))
        self.assertEqual(text.format_function(record), WRITTEN)

    def test_several_functions(self):
        other = WRITTEN.replace("@written", "@other")
        records = text.parse_functions(WRITTEN + "\n" + other)
        self.assertEqual([r["symbol"] for r in records], ["@written", "@other"])
        with self.assertRaisesRegex(text.TextError, "expected one function, found 2"):
            text.parse_function(WRITTEN + other)

    def test_malformed_text_is_rejected_with_its_line(self):
        for old, new, expected in (
                ("  ret.none\n", "  ret.none \n", "line 13: trailing whitespace"),
                ("  ret.none\n", "  ret.none(int %t1) extra\n", "line 13: unexpected text"),
                ("  ret.none\n", "  Ret\n", "line 13: expected an operation name"),
                ("  ret.none\n", "  ret.none k=0\n", "line 13: k= needs a nonzero integer"),
                ("  ret.none\n", "  ret.none k=01\n", "line 13: k= needs a nonzero integer"),
                ("  ret.none\n", '  ret.none ""\n', "line 13: an empty text is omitted"),
                ("  ret.none\n", "  ret.none()\n", "line 13: expected an atom"),
                ("  ret.none\n", "  ret.none(int)\n", "line 13: expected ' '"),
                ("  ret.none\n", "  ret.none(int %t1,int %t2)\n", "line 13: expected ', '"),
                ("  ret.none\n", '  ret.none(int "unterminated)\n', "line 13: invalid quoted atom"),
                ("  ret.none\n", "  ret.none(list[int %t1)\n", "line 13: expected an atom"),
                ("  ret.none\n", "  ret.none <(int %t1)\n", "line 13: unexpected text"),
                ("  %left.1 = slot left : int\n", "  %t1 = br -> L5\n", "line 2: an instruction before the first block must be a slot"),
                ("  %left.1 = slot left", "  %x.1 = slot left", "line 2: results must be written %left.1"),
                ("  %stk.2 = slot k=2", "  %h.2 = slot k=2", "line 4: results must be written %stk.2"),
                ("  %t3 = rt dict.find", "  %3 = rt dict.find", "line 6: invalid result '%3'"),
                ("  %t3 = rt dict.find", '  %t3 = rt "dict.find"', "line 6: text 'dict.find' must be written dict.find"),
                ("  ~%t6 %t7 = tuple.load", "  %t6 %t7 = tuple.load", "line 10: results must be written ~%t6 %t7"),
                ("  ~%t6 %t7 = tuple.load", "  ~%t6 ~%t7 = tuple.load", "line 10: results must be written ~%t6 %t7"),
                ("L8:\n", "L8\n", "line 12: expected ':'"),
                ("L8:\n", "L8: handler=\n", "line 12: expected an atom"),
                ("L8:\n", "L8: handler=L9 x\n", "line 12: unexpected text after a block label"),
                ('cold "Kind: text" -> L8\n', 'cold "Kind: text" -> L8\n  ret.none\n', "line 19: an instruction after the check targets"),
                ('cold "Kind: text" -> L8\n', 'cold "Kind: text" -> L8\ncold "Kind: text" -> L5\n', "line 19: check target 'Kind: text' is repeated"),
                ("nonnegative=true", "nonnegative=yes", "line 19: nonnegative is true or false"),
                ("kind=range", "kind=range kind=seq", "line 19: loop field kind is repeated"),
                ("kind=range", "sort=range", "line 19: unknown loop field 'sort'"),
                ("}\n", "", "the last function has no closing brace"),
                ("-> None coroutine", "-> None coroutine extra", "line 1: expected ' {'"),
                ("(left: int,", "(left int,", "line 1: expected ': '")):
            with self.subTest(expected=expected):
                changed = WRITTEN.replace(old, new, 1)
                self.assertNotEqual(changed, WRITTEN)
                with self.assertRaises(text.TextError) as raised:
                    text.parse_functions(changed)
                self.assertIn(expected, str(raised.exception))

    def test_records_the_printer_cannot_write_are_rejected(self):
        record = text.parse_function(WRITTEN)
        for change, expected in ((lambda r: r["blocks"][2]["operations"][0].__setitem__("op", "Ret"), "invalid operation name"),
                                 (lambda r: r["blocks"][2]["operations"][0].__setitem__("immediate", True), "an immediate must be an integer"),
                                 (lambda r: r["blocks"][2]["operations"][0].__setitem__("results", ["1"]), "result numbers must be integers"),
                                 (lambda r: r["slots"][0].__setitem__("results", [1, 2]), "a slot has one number"),
                                 (lambda r: r["loops"][0].__setitem__("sort", "x"), "unknown loop field"),
                                 (lambda r: r.__setitem__("coroutine", 1), "coroutine must be a boolean")):
            with self.subTest(expected=expected):
                broken = json.loads(json.dumps(record))
                change(broken)
                self.assertTrue(any(expected in error for error in text.roundtrip_errors(broken)))


class CompilerTests(unittest.TestCase):
    def test_compiled_functions_round_trip_before_the_passes_and_at_lowering(self):
        count = 0
        ops = set()
        for case in ("typed_ir_slots.py", "typed_ir_numeric.py", "closures_more.py", "tuple_runtime_operations.py",
                     "tuples_and_classes.py", "gen_basic.py", "gen_close.py", "exc_as_rebind.py"):
            before, after = compiled(next((ROOT / "tests").glob(f"programs/*/{case}")))
            for record in before + after:
                with self.subTest(case=case, symbol=record["symbol"]):
                    self.assertEqual(text.roundtrip_errors(record), [])
                    self.assertEqual(text.from_ifn(text.to_ifn(record)), record)
                count += 1
                ops.update(i["op"] for b in record["blocks"] for i in b["operations"])
        self.assertGreater(count, 100)
        # (exception edges, generators and loops are among what was printed and read back)
        self.assertLessEqual({"landing", "throw", "gen.start", "gen.yield", "gen.resume", "phi", "check"}, ops)

    def test_snapshot_functions_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "inspect"
            subprocess.run([sys.executable, str(ROOT / "tools/inspect_compiler.py"), str(EXAMPLE), "--output", str(output)],
                           check=True, capture_output=True, timeout=120)
            for name in ("typed-before.json", "typed-after.json"):
                snapshot = json.loads((output / name).read_text())
                self.assertGreater(len(snapshot["functions"]), 0)
                for function in snapshot["functions"]:
                    record = text.from_snapshot(function)
                    self.assertEqual(text.roundtrip_errors(record), [])
                    self.assertEqual(text.parse_function(text.format_function(record))["symbol"], function["symbol"])
            printed = subprocess.run([sys.executable, str(ROOT / "tools/typed_ir_text.py"), "print", str(output / "typed-after.json"),
                                      "--function", "score_samples"], check=True, capture_output=True, text=True, timeout=60).stdout
            self.assertEqual(text.parse_function(printed)["symbol"], "@f.score_samples")
            listing = Path(directory) / "score.tir"
            listing.write_text(printed)
            checked = subprocess.run([sys.executable, str(ROOT / "tools/typed_ir_text.py"), "check", str(listing)],
                                     capture_output=True, text=True, timeout=60)
            self.assertEqual((checked.returncode, checked.stdout), (0, "typed_ir_text: 1 functions parse and print unchanged\n"))
            listing.write_text(printed.replace("  br -> ", "  br  -> ", 1))
            checked = subprocess.run([sys.executable, str(ROOT / "tools/typed_ir_text.py"), "check", str(listing)],
                                     capture_output=True, text=True, timeout=60)
            self.assertEqual(checked.returncode, 1)


class PassTests(unittest.TestCase):
    """Text in, a pass, text out: the fixtures are the compiler's own IR around listget."""

    def fixture(self, name):
        return (FIXTURES / f"score_samples.listget.{name}.tir").read_text()

    def test_listget_rewrites_the_parsed_function_as_the_compiler_does(self):
        fn = text.to_ifn(text.parse_function(self.fixture("before")))
        g = text.gen_for(fn)
        g.verify(fn, False)
        self.assertEqual(g.listget(fn), 1)
        g.verify(fn, False)
        self.assertEqual(text.format_function(text.from_ifn(fn)), self.fixture("after"))

    def test_without_its_loop_record_the_read_stays_checked(self):
        before = "".join(line for line in self.fixture("before").splitlines(True) if not line.startswith("loop "))
        self.assertNotEqual(before, self.fixture("before"))
        fn = text.to_ifn(text.parse_function(before))
        g = text.gen_for(fn)
        self.assertEqual(g.listget(fn), 0)
        self.assertEqual(text.format_function(text.from_ifn(fn)), before)

    def test_fixtures_are_what_the_compiler_emits(self):
        captured = {}
        listget = Gen.listget

        def observe(g, fn):
            before = text.from_ifn(fn)
            changed = listget(g, fn)
            if fn.f.ll == "@f.score_samples":
                captured["before"], captured["after"] = before, text.from_ifn(fn)
            return changed

        with patch.object(Gen, "listget", observe):
            Gen().program(Loader([]).program(str(EXAMPLE), EXAMPLE.read_text()))
        for name in ("before", "after"):
            self.assertEqual(text.format_function(captured[name]), self.fixture(name))

    def test_verifier_reads_parsed_text(self):
        broken = self.fixture("before").replace("  br -> L7\n", "  br\n", 1)
        fn = text.to_ifn(text.parse_function(broken))
        errors = StringIO()
        with redirect_stderr(errors), self.assertRaises(SystemExit):
            text.gen_for(fn).verify(fn, False)
        self.assertIn("bad IR in @f.score_samples, block entry", errors.getvalue())


class VerifyModeTests(unittest.TestCase):
    INVALID = FIXTURES / "invalid.tir"
    CASE = """function @f(n: int) -> None {
entry:
  ; expected-error {{cbr operand 0 needs bool, got int}}
  cbr(int %a0) -> L1, L1
L1:
  ret.none
}
"""

    def test_each_fixture_function_reports_the_error_it_expects(self):
        source = self.INVALID.read_text()
        self.assertEqual(text.verify_errors(source), [])
        expected = [e["message"] for found in text.expectations(source) for e in found]
        # (each kind of rule of an op's row, and of its types, has a case; MLIR's testing guide
        # asks a diagnostic test of every error a user can see)
        for pattern in (r"with \d+ operands, where", r"with \d+ labels, where", r"sets a field outside",
                        r"in a block, where entry storage", r"operand \d+ needs [a-z%]+, got",
                        r"operand \d+ needs a ", r"operand \d+ needs .* \(\$\w+ is ", r"needs &\$T, \$T ",
                        r"result needs ", r"the function's return type", r"reads %\S+ as \S+, but it is ",
                        r"reads the address %\S+ as a packed slot", r"a packed slot, as an address",
                        r"reads %\S+ as \S+, where .* reads it as "):
            with self.subTest(pattern=pattern):
                self.assertTrue(any(re.search(pattern, m) for m in expected), pattern)
        self.assertEqual(len(text.parse_functions(source)), len(text.expectations(source)))

    def test_an_expected_error_must_be_reported_in_its_block(self):
        self.assertEqual(text.verify_errors(self.CASE), [])
        moved = self.CASE.replace("  ; expected-error {{cbr operand 0 needs bool, got int}}\n", "").replace(
            "L1:\n", "L1:\n  ; expected-error {{cbr operand 0 needs bool, got int}}\n")
        self.assertEqual(text.verify_errors(moved), ["@f: line 5: expected error {{cbr operand 0 needs bool, got int}} "
                                                     "in block L1, got in block entry: cbr operand 0 needs bool, got int"])
        other = self.CASE.replace("needs bool, got int}}", "needs int}}")
        self.assertIn("expected error {{cbr operand 0 needs int}} in block entry, got in block entry", text.verify_errors(other)[0])

    def test_an_error_nothing_expects_and_an_expected_error_not_reported_fail(self):
        unexpected = self.CASE.replace("  ; expected-error {{cbr operand 0 needs bool, got int}}\n", "")
        self.assertEqual(text.verify_errors(unexpected), ["@f: unexpected error in block entry: cbr operand 0 needs bool, got int"])
        missing = self.CASE.replace("cbr(int %a0)", "cbr(bool true)")
        self.assertEqual(text.verify_errors(missing), ["@f: line 3: expected error {{cbr operand 0 needs bool, got int}} was not reported"])
        twice = self.CASE.replace("entry:\n", "entry:\n  ; expected-error {{cbr}}\n")
        self.assertEqual(text.verify_errors(twice), ["@f: expects 2 errors, where the verifier reports its first alone"])
        with self.assertRaisesRegex(text.TextError, "line 1: an expected error outside a function"):
            text.verify_errors("; expected-error {{x}}\n" + self.CASE)

    def test_verify_mode_reports_and_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "case.tir"
            path.write_text(self.CASE.replace("  ; expected-error {{cbr operand 0 needs bool, got int}}\n", ""))
            result = subprocess.run([sys.executable, str(ROOT / "tools/typed_ir_text.py"), "verify", str(path)],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertIn("@f: unexpected error in block entry", result.stderr)
            result = subprocess.run([sys.executable, str(ROOT / "tools/typed_ir_text.py"), "verify", str(self.INVALID)],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("functions verify as expected", result.stdout)


if __name__ == "__main__":
    unittest.main()
