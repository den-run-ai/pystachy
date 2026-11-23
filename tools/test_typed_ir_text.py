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
  %left.1 = slot name=left : int
  %left.def.1 = slot name=left kind=1 : bool
  %stk.2 = slot kind=2 : tuple[int,str]
entry:
  %t3 = rt entry=dict.find descriptor=!s (dict[str,int] %a1, str @s.4, int "ptrtoint (ptr @s.4 to i64)") : int
  %t4 = num.cmp < (int %t3, int -1) : bool
  check message="KeyError: 'k'" key="Kind: text" (bool %t4) -> L5
L5: handler=L9
  ~%t6 %t7 = tuple.load item=int index=1 (tuple[int,str] %stk.2) : %slot
  call callee=@f.other hint=inline (%slot %t7, float "bitcast (i64 9218868437227405312 to double)") -> L8, L9 : None
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
# WRITTEN with locations on an instruction that ends in each part a line may end in: a type, a
# label, an operand list, a field and the operation's name; the slot's line is in file 2
LOCATED = (WRITTEN.replace("  %left.1 = slot name=left : int\n", "  %left.1 = slot name=left : int loc(2:1)\n")
           .replace(' -> L5\nL5: handler=L9\n', ' -> L5 loc(7)\nL5: handler=L9\n')
           .replace("(tuple[int,str] %stk.2) : %slot\n", "(tuple[int,str] %stk.2) : %slot loc(8)\n")
           .replace("  ret.none\n", "  ret.none loc(12)\n")
           .replace("-> L8, L5, L8\n", "-> L8, L5, L8 loc(9999999)\n"))
MODULE = """module version=1 {
  class Base tag=1
  class Error base=Exception fields=[" cls":str " str":str " args":str]
  class Node base=Base roles=[Reader] tag=2 fields=[" class":int value:int "a:b":"odd type" next:opt[Node]] flags=[value:4 "a:b":5] boxes=[value:6]
  class Reader overlaps=[Base "odd name"] tag=3
  class "odd name"
  dyntype @dt.Node kind=obj cls=1 flags=[role] base=@dt.Base role=@dt.Reader payload=Node
  dyntype @dtf.0 kind=func cls=-1 flags=[boxid] payload=fn[m:Node.f]
  dyntype @dt.Base kind=obj cls=0
  layout Node descriptor=@dt.Node base=@dt.Base role=@dt.Reader number=1 members=[int int+ dyn]
  layout Base descriptor=@dt.Base number=0
}

""" + WRITTEN


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
        for value in ("->", ":", "k=1", "x=y", "index=3", "entry=a b", "a b", ""):
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
                         {"value": "ptrtoint (ptr @s.4 to i64)", "type": "int"}], "targets": [], "line": 0})
        self.assertEqual(record["blocks"][1]["operations"][1]["targets"], ["L8", "L9"])
        self.assertEqual(record["blocks"][3]["operations"][0]["targets"], [""])
        self.assertEqual(record["check_targets"], {"Kind: text": "L8"})
        self.assertEqual(record["loops"][0]["indices"], ["%t3", "a b"])
        self.assertEqual(record["loops"][0]["stop"], {"value": "10", "type": "int"})

    def test_locations_print_on_request_and_read_back(self):
        self.assertEqual(LOCATED.count(" loc("), 5)
        record = text.parse_function(LOCATED)
        self.assertEqual(record["slots"][0]["line"], 20000001)
        self.assertEqual([i["line"] for b in record["blocks"] for i in b["operations"]], [0, 0, 7, 8, 0, 12, 0, 9999999])
        self.assertEqual(text.format_function(record, True), LOCATED)
        self.assertEqual(text.format_function(record), WRITTEN)
        self.assertEqual(text.roundtrip_errors(record), [])
        unlocated = text.parse_function(WRITTEN)
        self.assertEqual({i["line"] for i in unlocated["slots"] + [i for b in unlocated["blocks"] for i in b["operations"]]}, {0})
        self.assertEqual(text.format_function(unlocated, True), WRITTEN)
        self.assertEqual(text.location_text(1), "loc(1)")
        self.assertEqual(text.location_text(10000000), "loc(1:0)")

    def test_malformed_locations_are_rejected_with_their_line(self):
        for written, expected in (("loc(0)", "an unknown location is omitted"), ("loc(0:0)", "an unknown location is omitted"),
                                  ("loc(012)", "a location must be written loc(12)"),
                                  ("loc(0:12)", "a location must be written loc(12)"),
                                  ("loc(30000012)", "a location must be written loc(3:12)"),
                                  ("loc(3:012)", "a location must be written loc(3:12)"),
                                  ("loc(3:10000000)", "a location's line must be below 10000000"),
                                  ("loc(-1)", "ret.none has no operator to write bare"), ("loc()", "ret.none has no operator to write bare"),
                                  ("loc(1:)", "ret.none has no operator to write bare")):
            with self.subTest(written=written), self.assertRaises(text.TextError) as raised:
                text.parse_functions(WRITTEN.replace("  ret.none\n", f"  ret.none {written}\n"))
            self.assertIn(f"line 13: {expected}", str(raised.exception))
        for line in ("  ret.none  loc(1)", "  ret.noneloc(1)", "  ret.none loc(1) "):
            with self.subTest(line=line), self.assertRaises(text.TextError):
                text.parse_functions(WRITTEN.replace("  ret.none\n", line + "\n"))

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
                ("  %t4 = num.cmp <", '  %t4 = num.cmp ""', "line 7: an empty operator is omitted"),
                ("  ret.none\n", "  ret.none()\n", "line 13: expected an atom"),
                ("  ret.none\n", "  ret.none(int)\n", "line 13: expected ' '"),
                ("  ret.none\n", "  ret.none(int %t1,int %t2)\n", "line 13: expected ', '"),
                ("  ret.none\n", '  ret.none(int "unterminated)\n', "line 13: invalid quoted atom"),
                ("  ret.none\n", "  ret.none(list[int %t1)\n", "line 13: expected an atom"),
                ("  ret.none\n", "  ret.none <(int %t1)\n", "line 13: ret.none has no operator to write bare: its row names none"),
                ("  %left.1 = slot name=left : int\n", "  %t1 = br -> L5\n", "line 2: an instruction before the first block must be a slot"),
                ("  %left.1 = slot name=left", "  %x.1 = slot name=left", "line 2: results must be written %left.1"),
                ("  %stk.2 = slot kind=2", "  %h.2 = slot kind=2", "line 4: results must be written %stk.2"),
                ("  %t3 = rt entry=dict.find", "  %3 = rt entry=dict.find", "line 6: invalid result '%3'"),
                # (fields by the names the operation table gives them: an operator bare, first; a
                # field the op's row names by that name and no other; any other field by its letter)
                ("rt entry=dict.find", 'rt entry="dict.find"', "line 6: atom 'dict.find' must be written bare"),
                ("rt entry=dict.find", "rt dict.find", "line 6: rt has no operator to write bare: its row names entry (s), hole (k), descriptor (x)"),
                ("rt entry=dict.find", "rt s=dict.find", "line 6: rt names its s entry: write entry="),
                ("rt entry=dict.find", "rt entry=dict.find index=2", "line 6: rt has no field index: its row names entry (s), hole (k), descriptor (x)"),
                ("rt entry=dict.find descriptor=!s", "rt descriptor=!s entry=dict.find", "line 6: rt field entry must come before descriptor"),
                ("rt entry=dict.find", "rt entry=dict.find entry=x", "line 6: rt field entry is repeated"),
                ("rt entry=dict.find", "rt entry=dict.find hole=0", "line 6: hole= needs a nonzero integer"),
                ("rt entry=dict.find", 'rt entry=""', "line 6: an empty entry is omitted"),
                ("num.cmp <", "num.cmp operator=<", "line 7: num.cmp writes its operator bare, before its other fields"),
                ("num.cmp <", "num.cmp s=<", "line 7: num.cmp names its s operator: write it bare"),
                ("num.cmp <", 'num.cmp "<"', "line 7: operator '<' must be written <"),
                ("num.cmp <", "num.cmp k=1 <", "line 7: unexpected text"),
                ("tuple.load item=int index=1", "tuple.load item=int k=1", "line 10: tuple.load names its k index: write index="),
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
                ("-> None coroutine", "-> None coroutine extra", "line 1: unknown function field 'extra'"),
                ('effects="R A" {', 'effects="R A"', "line 1: expected ' {'"),
                # (a function's attributes, written as a declaration's fields)
                ('effects="R A" {', 'effects="R A" name=a name=b {', "line 1: function field name is repeated"),
                ('effects="R A" {', 'effects="R A" tupleret=2 name=a {', "line 1: function field name must come before tupleret"),
                ('effects="R A" {', 'effects="R A" closed=1 {', "line 1: function field closed is a flag, written bare"),
                ('effects="R A" {', 'effects="R A" home=- {', "line 1: function field home is omitted where it holds its default"),
                ('effects="R A" {', 'effects="R A" casts=[3 x] {', "line 1: casts=[ needs integers"),
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
                                 (lambda r: r["slots"][1].__setitem__("line", -1), "a line must be a nonnegative integer"),
                                 (lambda r: r["slots"][1].__setitem__("line", "3"), "a line must be a nonnegative integer"),
                                 (lambda r: r["slots"][1].pop("line"), "a line must be a nonnegative integer"),
                                 (lambda r: r.__setitem__("coroutine", 1), "coroutine must be a boolean")):
            with self.subTest(expected=expected):
                broken = json.loads(json.dumps(record))
                change(broken)
                self.assertTrue(any(expected in error for error in text.roundtrip_errors(broken)))

    def test_each_ops_fields_print_by_the_names_its_row_gives_them(self):
        specs = text.compiler()[1]
        for op in specs.OPS:
            names = text.named_fields(op)
            ins = {"op": op, "type": "", "text": "", "immediate": 0, "descriptor": "", "results": [],
                   "operands": [{"value": "%a0", "type": "int"}], "targets": [], "line": 0}
            for field, key in text.FIELD_KEYS:
                ins[key] = (3 if field == "k" else "v." + field) if field in names else ins[key]
            with self.subTest(op=op):
                line = text.instruction_text(ins)
                self.assertEqual(text.read_instruction(line), ins)
                words = [w.split("=")[0] for w in line[: line.index("(")].split()[1:]]
                self.assertEqual(words, [n if n != text.OPERATOR else "v.s" for f, n in names.items()])
        # (a field outside its op's row, which the verifier rejects, by its letter, and an op the
        # table lacks: such records still print)
        for line in ("%t1 = num.cmp < k=1 x=y (int %a0, int 1) : bool", "ret.none s=text k=-2", "nop s=a k=1 x=b"):
            with self.subTest(line=line):
                self.assertEqual(text.instruction_text(text.read_instruction(line)), line)


class ModuleTests(unittest.TestCase):
    def test_dyntype_kinds_and_flags_are_named_as_runtime_c_names_them(self):
        source = (ROOT / "runtime.c").read_text(encoding="utf-8")
        kinds = re.search(r"enum \{ (DK_NONE[^}]*) \};", source).group(1).split(",")
        self.assertEqual([k.strip().removeprefix("DK_").lower() for k in kinds], list(text.DYN_KINDS))
        flags = re.search(r"enum \{ (DF_EQ[^}]*) \};", source).group(1).split(",")
        self.assertEqual([(f.split("=")[0].strip().removeprefix("DF_").lower(), int(f.split("=")[1])) for f in flags],
                         list(text.DYN_FLAGS))

    def test_written_module_reads_and_prints_unchanged(self):
        module = text.parse_module(MODULE)
        self.assertEqual(text.format_module(module), MODULE)
        self.assertEqual(text.module_roundtrip_errors(module), [])
        self.assertEqual(list(module), text.MODULE_KEYS)
        self.assertEqual(module["attributes"], dict({key: default for key, _, default in text.MODULE_ATTRIBUTES}, version=1))
        self.assertEqual(module["dynamic_types"][0], {"symbol": "@dt.Node", "kind": 8, "cls": 1, "flags": 256, "base": "@dt.Base",
                                                      "role": "@dt.Reader", "payload": "Node"})
        self.assertEqual(module["dynamic_layouts"][0]["llvm"], ["i64", "{i64, ptr}", "ptr"])
        self.assertEqual(list(module["classes"]), ["Base", "Error", "Node", "Reader", "odd name"])
        self.assertEqual(module["classes"]["Node"], {
            "base": "Base", "roles": ["Reader"], "overlaps": [], "tag": 2,
            "fields": [{"name": " class", "type": "int"}, {"name": "value", "type": "int"}, {"name": "a:b", "type": "odd type"},
                       {"name": "next", "type": "opt[Node]"}],
            "flags": {"value": 4, "a:b": 5}, "boxes": {"value": 6}, "template": False, "exception": "", "module": ""})
        self.assertEqual(module["classes"]["Reader"]["overlaps"], ["Base", "odd name"])
        self.assertEqual(module["classes"]["odd name"], {"base": "", "roles": [], "overlaps": [], "tag": 0,
                                                         "fields": [], "flags": {}, "boxes": {}, "template": False,
                                                         "exception": "", "module": ""})
        self.assertEqual(module["dynamic_types"][1], {"symbol": "@dtf.0", "kind": 9, "cls": -1, "flags": 8, "base": "",
                                                      "role": "", "payload": "fn[m:Node.f]"})
        self.assertEqual(module["dynamic_types"][2], {"symbol": "@dt.Base", "kind": 8, "cls": 0, "flags": 0, "base": "",
                                                      "role": "", "payload": ""})
        self.assertEqual(module["dynamic_layouts"][0], {"name": "Node", "descriptor": "@dt.Node", "base": "@dt.Base",
                                                        "role": "@dt.Reader", "number": 1, "members": ["int", "int+", "dyn"],
                                                        "llvm": ["i64", "{i64, ptr}", "ptr"]})
        self.assertEqual(module["dynamic_layouts"][1]["members"], [])
        self.assertEqual(module["functions"], [text.parse_function(WRITTEN)])
        self.assertEqual(json.loads(json.dumps(module)), module)

    def test_a_text_is_a_module_or_functions_alone(self):
        self.assertIsInstance(text.parse(WRITTEN), list)
        self.assertEqual(text.parse_functions(MODULE), text.parse_functions(WRITTEN))
        self.assertEqual(text.parse_function(MODULE)["symbol"], "@written")
        self.assertEqual(text.format_text(text.parse(WRITTEN)), WRITTEN)
        self.assertEqual(text.format_text(text.parse(MODULE)), MODULE)
        with self.assertRaisesRegex(text.TextError, "expected a module, found functions alone"):
            text.parse_module(WRITTEN)
        # (a module without declarations or functions)
        self.assertEqual(text.format_module(text.parse_module("; empty\nmodule version=1 {\n}\n")), "module version=1 {\n}\n")

    def test_malformed_module_is_rejected_with_its_line(self):
        for old, new, expected in (
                ("  class Base tag=1\n", "  klass Base tag=1\n", "line 2: expected a declaration: class, dyntype, layout, hole"),
                ("  class Base tag=1\n", "class Base tag=1\n", "line 2: expected a declaration, indented by two spaces"),
                ("  class Base tag=1\n", "  class Base tag\n", "line 2: tag= needs an integer"),
                ("  class Base tag=1\n", "  class Base tag=0\n", "line 2: class field tag is omitted where it holds its default"),
                ("  class Base tag=1\n", "  class Base tag=1 base=X\n", "line 2: class field base must come before tag"),
                ("  class Base tag=1\n", "  class Base tag=1 tag=1\n", "line 2: class field tag is repeated"),
                ("  class Base tag=1\n", "  class Base sort=X\n", "line 2: unknown class field 'sort'"),
                ("  class Base tag=1\n", '  class Base base="" tag=1\n', "line 2: class field base is omitted where it holds its default"),
                ("  class Base tag=1\n", "  class Base roles=[] tag=1\n", "line 2: class field roles is omitted where it holds its default"),
                ("  class Base tag=1\n", "  class Base roles=Reader\n", "line 2: expected '=['"),
                ("  class Base tag=1\n", '  class "Base" tag=1\n', "line 2: atom 'Base' must be written bare"),
                # (a struct: NAME:TYPE fields, NAME:INT flags and boxes, a name quoted where it has
                # a space or a colon)
                ('fields=[" cls":str " str":str " args":str]', "fields=[]", "line 3: class field fields is omitted where it holds its default"),
                ("boxes=[value:6]", "boxes=[]", "line 4: class field boxes is omitted where it holds its default"),
                ('" args":str]\n', '" args":str\n', "line 3: fields=[ has no closing ']'"),
                ('fields=[" cls":str', 'fields=[" cls" :str', "line 3: expected ':' at column 42"),
                ('fields=[" cls":str', 'fields=[" cls": str', "line 3: expected an atom at column 43"),
                ('fields=[" cls":str', 'fields=[ cls:str', "line 3: expected an atom at column 36"),
                ('fields=[" cls":str', 'fields=["cls":str', "line 3: atom 'cls' must be written bare"),
                ('"a:b":"odd type"', 'a:b:"odd type"', "line 4: expected ' ' at column 78"),
                ("flags=[value:4", "flags=[value:04", "line 4: flags=[ needs an integer after value:"),
                ("flags=[value:4", "flags=[value:x", "line 4: flags=[ needs an integer after value:"),
                ('flags=[value:4 "a:b":5]', "flags=[value:4 value:5]", "line 4: class field flags names 'value' twice"),
                (' flags=[value:4 "a:b":5] boxes=[value:6]', ' boxes=[value:6] flags=[value:4 "a:b":5]',
                 "line 4: class field flags must come before boxes"),
                ('" args":str]\n', '" args":str] tag=4\n', "line 3: class field tag must come before fields"),
                ("kind=obj cls=0\n", "kind=obj cls=0 flags=[]\n", "line 9: dyntype field flags is omitted where it holds its default"),
                ("kind=obj cls=0\n", "kind=obj\n", "line 9: dyntype @dt.Base needs cls="),
                ("kind=func", "kind=function", "line 8: kind= needs a DynType kind: none, bool, int"),
                ("kind=func", "kind=9", "line 8: kind= needs a DynType kind"),
                ("flags=[role]", "flags=[256]", "line 7: flags=[ needs DynType flags: eq, cmp, hash"),
                ("flags=[boxid]", "flags=[boxid eq]", "line 8: flags=[ names each flag once, in the order eq cmp hash"),
                ("flags=[boxid]", "flags=[boxid boxid]", "line 8: flags=[ names each flag once"),
                ("dyn]\n", "dyn] llvm=[i64 \"{i64, ptr}\" ptr]\n", "line 10: layout field llvm is derived from the others, not written"),
                ("module version=1 {", "module {", "line 1: module needs version="),
                ("module version=1 {", "module version=2 {", "line 1: a module text of version 2, where this one reads version 1"),
                ("module version=1 {", "module complete version=1 {", "line 1: module field version must come before complete"),
                ("cls=-1", "cls=-01", "line 8: cls= needs an integer"),
                ("number=0\n", "number=x\n", "line 11: number= needs an integer"),
                ("dyn]\n", "dyn\n", "line 10: members=[ has no closing ']'"),
                ("  layout Base", "  class Late\n  layout Base", "line 11: a class after the layouts"),
                ("  layout Base", "  dyntype @dt.Late kind=obj cls=2\n  layout Base", "line 11: a dyntype after the layouts"),
                ("  class Error base=Exception", "  class Error\n  class Error base=Exception", "line 4: class Error is declared twice"),
                ("  dyntype @dt.Base kind=obj cls=0\n", "  dyntype @dt.Base kind=obj cls=0\n  dyntype @dt.Node kind=obj cls=1\n",
                 "line 10: dyntype @dt.Node is declared twice"),
                ("}\n\nfunction", "\nfunction", "line 13: expected a declaration, indented by two spaces"),
                ("function @written", "module version=1 {\n}\nfunction @written", "line 14: a module's declarations come once, before its functions")):
            with self.subTest(expected=expected):
                changed = MODULE.replace(old, new, 1)
                self.assertNotEqual(changed, MODULE)
                with self.assertRaises(text.TextError) as raised:
                    text.parse(changed)
                self.assertIn(expected, str(raised.exception))
        for source, expected in (("module version=1 {\n  class A\n", "the module's declarations have no closing brace"),
                                 (WRITTEN + "module version=1 {\n}\n", "line 21: a module's declarations come once, before its functions")):
            with self.subTest(expected=expected), self.assertRaisesRegex(text.TextError, expected):
                text.parse(source)

    def test_records_the_printer_cannot_write_are_rejected(self):
        module = text.parse_module(MODULE)
        for change, expected in ((lambda m: m.pop("dynamic_layouts"), "a module record holds attributes, classes, dynamic_types, dynamic_layouts, holes"),
                                 (lambda m: m.__setitem__("dynamic_types", {}), "a module's dynamic_types must be a list"),
                                 (lambda m: m["classes"]["Base"].pop("tag"),
                                  "class Base: the record must hold base, roles, overlaps, tag, fields, flags, boxes, template, exception, module"),
                                 (lambda m: m["classes"]["Base"].__setitem__("tag", True), "class Base: tag must be an int"),
                                 (lambda m: m["classes"]["Base"].__setitem__("fields", {}), "class Base: fields must be a list of names with types"),
                                 (lambda m: m["classes"]["Node"]["fields"].append({"name": "x"}),
                                  "class Node: each of its fields must hold a name and a type"),
                                 (lambda m: m["classes"]["Node"]["fields"][1].__setitem__("type", 1), "an atom must be a string, not 1"),
                                 (lambda m: m["classes"]["Node"].__setitem__("flags", []), "class Node: flags must be a dict of names to ints"),
                                 (lambda m: m["classes"]["Node"]["boxes"].__setitem__("value", True), "class Node: boxes must map names to ints"),
                                 (lambda m: m["dynamic_types"][0].__setitem__("kind", "8"), "dyntype @dt.Node: kind must be an int"),
                                 (lambda m: m["dynamic_types"][0].__setitem__("flags", True), "dyntype @dt.Node: flags must be an int"),
                                 (lambda m: m["dynamic_layouts"][0].__setitem__("members", "int"), "layout Node: members must be a list"),
                                 (lambda m: m["dynamic_types"][0].__setitem__("kind", 13), "dyntype @dt.Node: kind 13 is no DynType kind"),
                                 (lambda m: m["dynamic_types"][0].__setitem__("flags", 512), "dyntype @dt.Node: flags 512 holds no DynType flag"),
                                 (lambda m: m["dynamic_layouts"][0]["llvm"].append("i64"), "layout Node: llvm must hold its members' LLVM types"),
                                 (lambda m: m["attributes"].__setitem__("version", None), "module: version must be an int"),
                                 (lambda m: m["functions"][0].__setitem__("coroutine", 1), "@written: coroutine must be a boolean")):
            with self.subTest(expected=expected):
                broken = json.loads(json.dumps(module))
                change(broken)
                self.assertTrue(any(expected in error for error in text.module_roundtrip_errors(broken)),
                                text.module_roundtrip_errors(broken))


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
                    # (each op the compiler built has its source line, which the round trips keep)
                    self.assertNotIn(0, [i["line"] for i in record["slots"] + [i for b in record["blocks"] for i in b["operations"]]])
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
                self.assertEqual(snapshot["files"][0], str(EXAMPLE))
                for function in snapshot["functions"]:
                    record = text.from_snapshot(function, snapshot["files"])
                    self.assertEqual(text.roundtrip_errors(record), [])
                    self.assertEqual(text.parse_function(text.format_function(record))["symbol"], function["symbol"])
                    # (a record's line is the snapshot's location, as the compiler numbers lines)
                    for b, found in zip([{"operations": function["slots"]}] + function["blocks"],
                                        [{"operations": record["slots"]}] + record["blocks"], strict=True):
                        for ins, line in zip(b["operations"], [i["line"] for i in found["operations"]], strict=True):
                            self.assertEqual(ins["location"]["precision"], "line")
                            self.assertEqual((ins["location"]["file"], ins["location"]["line"]),
                                             (snapshot["files"][line // 10000000], line % 10000000))
            printed = subprocess.run([sys.executable, str(ROOT / "tools/typed_ir_text.py"), "print", str(output / "typed-after.json"),
                                      "--function", "score_samples"], check=True, capture_output=True, text=True, timeout=60).stdout
            self.assertEqual(text.parse_function(printed)["symbol"], "@f.score_samples")
            self.assertNotIn(" loc(", printed)
            located = subprocess.run([sys.executable, str(ROOT / "tools/typed_ir_text.py"), "print", str(output / "typed-after.json"),
                                      "--function", "score_samples", "--locations"], check=True, capture_output=True, text=True, timeout=60).stdout
            self.assertIn(" loc(", located)
            self.assertEqual(text.format_function(text.parse_function(located)), printed)
            listing = Path(directory) / "score.tir"
            for listed in (located, printed):
                listing.write_text(listed)
                checked = subprocess.run([sys.executable, str(ROOT / "tools/typed_ir_text.py"), "check", str(listing)],
                                         capture_output=True, text=True, timeout=60)
                self.assertEqual((checked.returncode, checked.stdout), (0, "typed_ir_text: 1 functions parse and print unchanged\n"))
            listing.write_text(printed.replace("  br -> ", "  br  -> ", 1))
            checked = subprocess.run([sys.executable, str(ROOT / "tools/typed_ir_text.py"), "check", str(listing)],
                                     capture_output=True, text=True, timeout=60)
            self.assertEqual(checked.returncode, 1)
            # (typed-before.json holds no module data: its functions print alone)
            before = subprocess.run([sys.executable, str(ROOT / "tools/typed_ir_text.py"), "print", str(output / "typed-before.json")],
                                    check=True, capture_output=True, text=True, timeout=60).stdout
            self.assertIsInstance(text.parse(before), list)

    def test_a_typed_after_snapshot_prints_as_its_module(self):
        program = ROOT / "tests/programs/classes/inheritance_secondary.py"
        tool = [sys.executable, str(ROOT / "tools/typed_ir_text.py")]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "inspect"
            subprocess.run([sys.executable, str(ROOT / "tools/inspect_compiler.py"), str(program), "--output", str(output),
                            "--typed-after-only", "--stop-after", "finalize"], check=True, capture_output=True, timeout=120)
            snapshot = json.loads((output / "typed-after.json").read_text())
            # (with locations, which module_from_snapshot's records hold)
            printed = subprocess.run(tool + ["print", str(output / "typed-after.json"), "--locations"],
                                     check=True, capture_output=True, text=True, timeout=60).stdout
            module = text.parse_module(printed)
            self.assertEqual(module, text.module_from_snapshot(snapshot))
            for table in ("dynamic_types", "dynamic_layouts") + text.LOWERING_TABLES:
                self.assertEqual(module[table], snapshot[table] if table in snapshot else snapshot["lowering"][table])
            # (a class's record is the snapshot's, and what lowering reads of it, in the compiler's order;
            # its tag the lowering record's number, where the snapshot says only whether it has one)
            lowering = snapshot["lowering"]
            self.assertEqual(list(module["classes"]), lowering["class_order"])
            self.assertEqual(module["classes"], {name: dict({k: v for k, v in snapshot["classes"][name].items() if k != "tagged"},
                                                            **lowering["classes"][name])
                                                 for name in lowering["class_order"]})
            tags = [c["tag"] for c in module["classes"].values() if c["tag"] != 0]
            self.assertEqual(tags, list(range(1, len(tags) + 1)))
            self.assertEqual(sorted(name for name, c in module["classes"].items() if c["tag"] != 0),
                             sorted(name for name, c in snapshot["classes"].items() if c["tagged"]))
            self.assertTrue(module["attributes"]["complete"])
            self.assertEqual(text.refusals(module), [])
            # (secondary bases, overlaps, and the DynTypes and layouts of a dynamic program are among them)
            self.assertTrue(any(c["roles"] for c in module["classes"].values()))
            self.assertTrue(any(c["overlaps"] for c in module["classes"].values()))
            self.assertTrue(any(t["role"] for t in module["dynamic_types"]))
            self.assertTrue(module["dynamic_layouts"])
            # (each class's struct: hidden fields, flags and identity boxes, a base's among a derived
            # class's fields; a layout's members are its class's struct, recorded apart)
            classes = module["classes"]
            self.assertTrue(any(f["name"].startswith(" ") for c in classes.values() for f in c["fields"]))
            self.assertTrue(all(c["flags"] and c["boxes"] for c in (classes["Storage"], classes["Both"])))
            self.assertEqual(classes["Both"]["fields"][:len(classes["Storage"]["fields"])], classes["Storage"]["fields"])
            for layout in module["dynamic_layouts"]:
                c = classes[layout["name"]]
                own = [sum(k >= len(c["fields"]) for k in c[key].values()) for key in ("flags", "boxes")]
                self.assertEqual(layout["members"], [f["type"] for f in c["fields"]] + ["bool"] * own[0] + ["dyn"] * own[1])
            # (its functions that address fields verify with its structs, but those that call
            # functions or need declarations the text does not hold)
            problems = text.verify_errors(printed)
            self.assertEqual([p for p in problems if "field.addr" in p], [])
            failing = {p.split(":")[0] for p in problems}
            addressing = {r["symbol"] for r in module["functions"] for b in r["blocks"] for i in b["operations"] if i["op"] == "field.addr"}
            self.assertGreaterEqual(len(addressing - failing), 3)
            # (its functions print as they do alone, after its declarations)
            alone = subprocess.run(tool + ["print", str(output / "typed-after.json"), "--function", "@", "--locations"],
                                   check=True, capture_output=True, text=True, timeout=60).stdout
            self.assertTrue(printed.endswith("}\n\n" + alone))
            listing = Path(directory) / "module.tir"
            listing.write_text(printed)
            checked = subprocess.run(tool + ["check", str(listing)], capture_output=True, text=True, timeout=60)
            declared = sum(len(module[table]) for table, _, _ in text.DECLARATIONS.values())
            self.assertEqual((checked.returncode, checked.stdout),
                             (0, f"typed_ir_text: a module of {declared} declarations and {len(module['functions'])} "
                                 "functions parses and prints unchanged\n"))
            listed = subprocess.run(tool + ["json", str(listing)], check=True, capture_output=True, text=True, timeout=60).stdout
            self.assertEqual(json.loads(listed), module)

    def test_a_snapshot_location_names_one_of_its_files(self):
        ret = {"op": "ret.none", "type": "", "text": "", "immediate": 0, "descriptor": "", "results": [], "operands": [],
               "targets": [], "location": {"file": "lib/heapq.py", "line": 12, "column": None, "precision": "line"}}
        function = {"symbol": "@f", "parameters": [], "return_representation": "None", "recursion": {"coroutine": False},
                    "effects": None, "slots": [], "blocks": [{"label": "entry", "handler": "", "operations": [ret]}],
                    "check_targets": {}, "loops": []}
        record = text.from_snapshot(function, ["main.py", "lib/os.py", "lib/heapq.py"])
        self.assertEqual(record["blocks"][0]["operations"][0]["line"], 20000012)
        self.assertEqual(text.format_function(record, True), "function @f() -> None {\nentry:\n  ret.none loc(2:12)\n}\n")
        with self.assertRaisesRegex(text.TextError, "lib/heapq.py, which the snapshot's files do not list"):
            text.from_snapshot(function, ["main.py"])
        for unknown in (None, "absent"):
            with self.subTest(location=unknown):
                if unknown is None:
                    ret["location"] = None
                else:
                    del ret["location"]
                self.assertEqual(text.from_snapshot(function)["blocks"][0]["operations"][0]["line"], 0)


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
        for pattern in (r"with \d+ operands, where", r"with \d+ labels, where", r"sets [tskx], where its row of the operation table names",
                        r"in a block, where entry storage", r"operand \d+ needs [a-z%]+, got",
                        r"operand \d+ needs a ", r"operand \d+ needs .* \(\$\w+ is ", r"needs &\$T, \$T ",
                        r"result needs ", r"the function's return type", r"reads %\S+ as \S+, but it is ",
                        r"reads the address %\S+ as a packed slot", r"a packed slot, as an address",
                        r"reads %\S+ as \S+, where .* reads it as ", r"rt \S+ operand \d+ needs ", r"rt \S+ result needs \*",
                        r"needs the LLVM type "):
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
            for fixture in (self.INVALID, self.CLASSES, self.FIELDS, self.STRUCTURE, self.CLASS_READS):
                result = subprocess.run([sys.executable, str(ROOT / "tools/typed_ir_text.py"), "verify", str(fixture)],
                                        capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("functions verify as expected", result.stdout)

    def test_annotated_fixtures_are_in_the_printed_form_but_for_their_comments(self):
        for fixture in (self.INVALID, self.CLASSES, self.FIELDS, self.OPTIONAL, self.STRUCTURE, self.CLASS_READS):
            with self.subTest(fixture=fixture.name):
                bare = "\n".join(line for line in fixture.read_text().split("\n") if not line.lstrip().startswith(";"))
                bare = re.sub(r"\n{3,}", "\n\n", bare).lstrip("\n")
                self.assertEqual(text.format_text(text.parse(bare)), bare)

    CLASSES = FIXTURES / "classes.tir"
    FIELDS = FIXTURES / "fields.tir"
    OPTIONAL = FIXTURES / "optional.tir"
    STRUCTURE = FIXTURES / "structure.tir"
    CLASS_READS = FIXTURES / "class_reads.tir"

    def test_a_class_read_needs_a_test_of_the_objects_class_word(self):
        source = self.CLASS_READS.read_text()
        self.assertEqual(text.verify_errors(source), [])
        expected = text.expectations(source)
        records = text.parse_functions(source)
        admitted = [r["symbol"] for r, e in zip(records, expected, strict=True) if not e]
        self.assertEqual((len(admitted), len(expected) - len(admitted)), (8, 9))
        for found in expected:
            for e in found:
                self.assertRegex(e["message"], r"^(field.addr|ret) operand 0 reads %\w+ as (\w+) without a proof that its class derives from \2$")
        # (a test of a class word against itself, or a switch on a constant, tells the proof
        # nothing: without their tests, the reads it admitted are errors, but for the one whose
        # class word the function stores)
        untested = re.sub(r"\((int|%ptr) (%t\d+), (int|%ptr) (\d+|@x\.\w+)\)", r"(\1 \2, \1 \2)", source)
        untested = untested.replace("switch(int %t1,", "switch(int 7,")
        self.assertNotIn("@x.F)", untested)
        problems = [p for p in text.verify_errors(untested) if ": unexpected error" in p]
        self.assertEqual(sorted(p.split(":")[0] for p in problems), sorted(a for a in admitted if a != "@the_class_word_a_constructor_stores"))
        for problem in problems:
            self.assertRegex(problem, r"reads %\w+ as \w+ without a proof that its class derives from \w+$")

    def test_a_union_read_at_a_union_without_its_members_needs_a_test_of_its_tag(self):
        def errors(source, utags):
            fn = text.to_ifn(text.parse_function(source))
            gen = text.gen_for(fn)
            gen.utags = utags
            reported = StringIO()
            try:
                with redirect_stderr(reported):
                    gen.verify(fn, False)
            except SystemExit:
                return reported.getvalue()
            return ""
        tested = """function @narrow(x: union[float,int,str], y: union[int,str]) -> union[int,str] {
entry:
  %t1 = union.tag(union[float,int,str] %a0) : int
  %t2 = num.cmp == (int %t1, int 2) : bool
  cbr(bool %t2) -> L3, L4
L3:
  ret(union[int,str] %a1)
L4:
  ret(union[int,str] %a0)
}
"""
        tags = {"int": 1, "float": 2, "str": 3}
        self.assertEqual(errors(tested, tags), "")
        # (a test of another member leaves the float in the box)
        self.assertIn("block L4: ret operand 0 reads %a0 as union[int,str] without a proof that it holds no float",
                      errors(tested.replace("int 2)", "int 1)"), tags))

    def test_control_flow_is_structured_and_loop_records_name_its_loops(self):
        from src.pystachy_compiler.structure import Structure
        source = self.STRUCTURE.read_text()
        self.assertEqual(text.verify_errors(source), [])
        expected = text.expectations(source)
        records = text.parse_functions(source)
        admitted = [r for r, e in zip(records, expected, strict=True) if not e]
        self.assertEqual((len(admitted), len(records) - len(admitted)), (3, 4))
        # (without their loop records, the functions whose records were wrong verify; the cycle
        # with two entries does not)
        bare = "\n".join(line for line in source.split("\n") if not line.startswith("loop "))
        unreported = sorted(p.split(":")[0] for p in text.verify_errors(bare) if "was not reported" in p)
        self.assertEqual(unreported, ["@a_loop_record_that_names_no_block", "@a_loop_record_whose_body_is_out_of_its_loop",
                                      "@a_loop_record_whose_exit_is_in_its_loop"])
        # (a structured backend finds each accepted loop at its record's head, in nesting order;
        # a body that always leaves closes no cycle, and a test before a loop may skip it)
        for record in admitted:
            fn = text.to_ifn(record)
            flow = Structure(fn)
            at = {b.label: j for j, b in enumerate(fn.blocks)}
            self.assertEqual(flow.irreducible(), [])
            for lp in fn.loops:
                with self.subTest(function=record["symbol"], head=lp.head):
                    blocks = flow.loop(at[lp.head])
                    self.assertEqual(at[lp.body] in blocks, record["symbol"] != "@a_loop_whose_body_always_leaves")
                    self.assertNotIn(at[lp.exit], blocks)
        nested = text.to_ifn(next(r for r in admitted if r["symbol"] == "@nested_loops"))
        flow = Structure(nested)
        self.assertEqual(sorted(nested.blocks[j].label for j in flow.loop(1)), ["L1", "L3", "L5"])
        self.assertEqual(sorted(nested.blocks[j].label for j in flow.loop(2)), ["L3", "L5"])
        skipped = text.to_ifn(next(r for r in admitted if r["symbol"] == "@a_loop_entered_after_a_test_that_may_skip_it"))
        flow = Structure(skipped)
        self.assertTrue(flow.dominates(0, 3) and not flow.dominates(1, 3))

    def test_an_optional_read_at_its_type_needs_a_test_that_it_is_not_none(self):
        source = self.OPTIONAL.read_text()
        self.assertEqual(text.verify_errors(source), [])
        expected = text.expectations(source)
        records = text.parse_functions(source)
        admitted = [r["symbol"] for r, e in zip(records, expected, strict=True) if not e]
        self.assertEqual((len(admitted), len(expected) - len(admitted)), (10, 7))
        for found in expected:
            for e in found:
                self.assertRegex(e["message"], r"^(rt operand 0|phi operand from \w+) reads %\w+ as str without a proof that it is not None$")
        # (a comparison of a value with itself tells the proof nothing: without their tests, the
        # reads it admitted are errors, but for the one whose slot holds a str)
        untested = re.sub(r"ptr\.cmp (==|!=) \(opt\[str\] (%\w+), None null\)", r"ptr.cmp \1 (opt[str] \2, opt[str] \2)", source)
        self.assertNotIn("None null", untested)
        problems = [p for p in text.verify_errors(untested) if ": unexpected error" in p]
        self.assertEqual(sorted(p.split(":")[0] for p in problems), sorted(a for a in admitted if a != "@a_reload_of_a_stored_str"))
        for problem in problems:
            self.assertRegex(problem, r"reads %\w+ as str without a proof that it is not None$")

    def test_private_optional_certificate_agrees_with_general_proof(self):
        from src.pystachy_compiler import ircheck

        source = self.OPTIONAL.read_text()
        results = {}
        certify = ircheck.private_optional_reads

        def checked(fn, narrowed, at, successors):
            accepted = certify(fn, narrowed, at, successors)
            results[fn.f.ll] = accepted
            if fn.f.ll == "@a_reload_after_a_test":
                self.assertTrue(accepted)
                # The two edges of the conditional have a defined order. An
                # extra or reversed successor must go back to the general proof.
                label = fn.blocks[0].label
                for targets in (successors[at[label]][::-1], successors[at[label]] + successors[at[label]][:1]):
                    changed = list(successors)
                    changed[at[label]] = targets
                    self.assertFalse(certify(fn, narrowed, at, changed))
            if fn.f.ll == "@private_short_circuit":
                self.assertTrue(accepted)
                phi = next(i for b in fn.blocks for i in b.code if i.op == "phi")
                with patch.object(phi, "b", [phi.b[0], phi.b[0]]):
                    self.assertFalse(certify(fn, narrowed, at, successors))
            return accepted

        with patch.object(ircheck, "private_optional_reads", checked):
            self.assertEqual(text.verify_errors(source), [])
        with patch.object(ircheck, "private_optional_reads", return_value=False):
            self.assertEqual(text.verify_errors(source), [])
        self.assertTrue(results["@a_loop_that_tests_in_its_head"])
        self.assertFalse(results["@a_reload_after_a_store"])
        self.assertFalse(results["@a_field_read_after_a_store_to_the_field"])

    def test_a_modules_classes_are_the_ones_its_class_view_relates(self):
        source = self.CLASSES.read_text()
        self.assertEqual(text.verify_errors(source), [])
        expected = text.expectations(source)
        admitted = [r["symbol"] for r, e in zip(text.parse_functions(source), expected, strict=True) if not e]
        self.assertEqual((len(admitted), len(expected) - len(admitted)), (6, 2))
        # (as functions alone the verifier knows no class: each reading the view admits is an error)
        alone = re.sub(r"(?ms)^module version=1 \{$.*?^\}$\n", "", source)
        self.assertIsInstance(text.parse(alone), list)
        problems = text.verify_errors(alone)
        self.assertEqual([p.split(":")[0] for p in problems], admitted)
        for problem in problems:
            self.assertRegex(problem, r": unexpected error in block \w+: ret operand 0 reads %a0 as \w+, but it is \w+$")

    def test_a_modules_structs_are_the_ones_field_addr_indexes(self):
        source = self.FIELDS.read_text()
        self.assertEqual(text.verify_errors(source), [])
        expected = text.expectations(source)
        admitted = [r["symbol"] for r, e in zip(text.parse_functions(source), expected, strict=True) if not e]
        self.assertEqual((len(admitted), len(expected) - len(admitted)), (6, 8))
        self.assertEqual({e["message"] for found in expected for e in found},
                         {"field.addr result must address the declared member type",
                          "field.addr needs a declared field, assignment flag or identity box index"})
        # (a class declared without its struct has no member to address: each reading the struct
        # admits is an error)
        bare = re.sub(r"(?m)^(  class .*?) fields=\[.*$", r"\1", source)
        self.assertNotIn("fields=", bare)
        problems = [p for p in text.verify_errors(bare) if ": unexpected error" in p]
        self.assertEqual([p.split(":")[0] for p in problems], admitted)
        for problem in problems:
            self.assertTrue(problem.endswith("field.addr needs a declared field, assignment flag or identity box index"), problem)

    def test_class_infos_hold_the_declared_structs(self):
        from src.pystachy_compiler.lower_module import struct_types
        infos = text.class_infos(text.parse_module(self.FIELDS.read_text()))
        leaf, root = infos["Leaf"], infos["Root"]
        self.assertEqual(leaf.fields, [" class", "count", "items", " Root.0", " Root.1", " Root.box.0", "tail"])
        self.assertEqual((leaf.ftypes["tail"], leaf.fpos["tail"]), ("str", 6))
        self.assertEqual((leaf.fflag, leaf.fbox, leaf.nflag, leaf.nbox), ({"count": 3, "items": 4, "tail": 7}, {"count": 5}, 1, 0))
        self.assertEqual((root.fflag, root.fbox, root.nflag, root.nbox), ({"count": 3, "items": 4}, {"count": 5}, 2, 1))
        # (the members lowering lays out: a derived class's struct begins with its base's)
        self.assertEqual(struct_types(root), ["i64", "i64", "ptr", "i1", "i1", "ptr"])
        self.assertEqual(struct_types(leaf), struct_types(root) + ["ptr", "i1"])

    def test_class_declarations_the_verifier_cannot_read_are_rejected(self):
        for declarations, expected in (("  class A roles=[B]\n", "class A: B is no declared class"),
                                       ("  class A overlaps=[B]\n", "class A: B is no declared class"),
                                       ("  class A base=B\n", "class A: its base B is neither a declared class nor a builtin exception class"),
                                       ("  class A base=B\n  class B base=A\n", "class A derives from itself"),
                                       # (a struct that no ClassInfo holds, or that lays out no struct)
                                       ("  class A fields=[x:int x:str]\n", "class A: field 'x' is declared twice"),
                                       ("  class A fields=[x:int] flags=[y:1]\n", "class A: 'y' has a flag, but is no field of it"),
                                       ("  class A fields=[x:int] boxes=[y:1]\n", "class A: 'y' has a box, but is no field of it"),
                                       ("  class A fields=[x:int] flags=[x:-1]\n", "class A: the flag of 'x' is at -1, which is no index"),
                                       ("  class A fields=[x:int] flags=[x:2]\n",
                                        "class A: the flag of 'x' is at 2, where its own flags are at 1, after its fields"),
                                       ("  class A fields=[x:int y:int] flags=[x:2 y:4]\n",
                                        "class A: the flag of 'y' is at 4, where its own flags are at 2 to 3, after its fields"),
                                       ("  class A fields=[x:int] flags=[x:1] boxes=[x:1]\n",
                                        "class A: the box of 'x' is at 1, where its own boxes are at 2, after its fields and own flags"),
                                       ("  class A fields=[x:int y:int] flags=[x:2 y:2]\n", "class A: the flag of 'x' and the flag of 'y' are both at 2"),
                                       ("  class A fields=[x:int] flags=[x:1] boxes=[x:0]\n",
                                        "class A: the box of 'x' is at 0, field 'x' of type int, where a base's box is a dyn field"),
                                       ('  class A fields=[x:int " B.0":int] flags=[x:1]\n',
                                        "class A: the flag of 'x' is at 1, field ' B.0' of type int, where a base's flag is a bool field"),
                                       ('  class A fields=[x:int " B.0":bool " B.1":bool] flags=[x:1] boxes=[x:1]\n',
                                        "class A: the box of 'x' is at 1, field ' B.0' of type bool, where a base's box is a dyn field")):
            with self.subTest(expected=expected):
                with self.assertRaises(text.TextError) as raised:
                    text.verify_errors("module version=1 {\n" + declarations + "}\n\n" + self.CASE)
                self.assertEqual(str(raised.exception), expected)
        self.assertEqual(text.verify_errors("module version=1 {\n  class A base=KeyError\n  class B base=A\n}\n\n" + self.CASE), [])
        # (a base's flag and box, at its hidden fields, and the derived class's own after its fields)
        self.assertEqual(text.verify_errors('module version=1 {\n  class A fields=[x:int " B.0":bool " B.box.0":dyn y:int] '
                                            'flags=[x:1 y:4] boxes=[x:2 y:5]\n}\n\n' + self.CASE), [])


class SettleTests(unittest.TestCase):
    # Gen.settle, once a function is built: each value whose type the frontend left open takes
    # the type the frontend decided for it (a hole's, Gen.decide_hole; a slot's or a value's,
    # FnBuild.decided) and the values that flow from it theirs, a runtime type variable that
    # nothing binds takes the one type its uses read it at, and a runtime call's word that an
    # operand reads as a typed value is read through a bits cast. Each settled function verifies.
    def settle(self, source, holes=(), decided=None, errors=()):
        fn = text.to_ifn(text.parse_function(source))
        gen = text.gen_for(fn)
        gen.holes = [""] + list(holes)
        gen.n = 100
        fn.build.decided = dict(decided or {})
        gen.settle(fn, False)
        gen.instantiate(fn)
        gen.settle(fn, True)
        out = text.format_function(text.from_ifn(fn))
        self.assertEqual(text.verify_errors(out), list(errors), out)
        return fn, out

    def test_an_empty_list_takes_the_type_its_use_decided(self):
        _, out = self.settle("""function @f(n: int) -> list[str] {
  %xs.1 = slot name=xs : list[?]
entry:
  %t2 = rt entry=list.new hole=1 (int 0) : list[?]
  mem.store(&list[?] %xs.1, list[?] %t2)
  %t3 = mem.load(&list[?] %xs.1) : list[?]
  %t4 = rt entry=str.int (int %a0) : str
  %t5 = slot.pack(str %t4) : *str
  rt entry=list.append (list[str] %t3, *str %t5) : None
  %t6 = mem.load(&list[str] %xs.1) : list[str]
  ret(list[str] %t6)
}
""", ["list[str]"])
        self.assertNotIn("?", out)
        self.assertIn("%xs.1 = slot name=xs : list[str]", out)
        self.assertIn("mem.store(&list[str] %xs.1, list[str] %t2)", out)
        self.assertIn("%t3 = mem.load(&list[str] %xs.1) : list[str]", out)

    def test_a_dicts_items_bind_its_runtime_calls_variables(self):
        _, out = self.settle("""function @g() -> dict[str,int] {
  %d.1 = slot name=d : dict[?,?]
entry:
  %t2 = rt entry=dict.new hole=1 (int 0, int 0) : dict[?,?]
  mem.store(&dict[?,?] %d.1, dict[?,?] %t2)
  %t3 = mem.load(&dict[?,?] %d.1) : dict[?,?]
  %t4 = slot.pack(str %a0) : *str
  rt entry=dict.set (dict[?,?] %t3, *str %t4, *V 1) : None
  %t5 = mem.load(&dict[str,int] %d.1) : dict[str,int]
  ret(dict[str,int] %t5)
}
""".replace("@g()", "@g(s: str)"), ["dict[str,int]"])
        self.assertNotIn("?", out)
        self.assertIn("rt entry=dict.set (dict[str,int] %t3, *str %t4, *int 1) : None", out)

    def test_the_type_a_use_decided_wins_over_a_view_of_it(self):
        # (bytes.join's runtime signature reads its list as a list[str]: the alias view)
        _, out = self.settle("""function @j(b: bytes) -> str {
entry:
  %t1 = rt entry=list.new hole=1 (int 0) : list[?]
  %t2 = slot.pack(bytes %a0) : *bytes
  rt entry=list.append (list[bytes] %t1, *bytes %t2) : None
  %t3 = rt entry=bytes.join (str %a0, list[str] %t1) : str
  ret(str %t3)
}
""".replace("(str %a0, list[str]", "(str @b.0, list[str]"), ["list[bytes]"])
        self.assertIn("%t1 = rt entry=list.new hole=1 (int 0) : list[bytes]", out)
        self.assertIn("(str @b.0, list[str] %t1)", out)

    def test_a_runtime_word_read_as_a_typed_value_is_read_through_a_cast(self):
        fn, out = self.settle("""function @k() -> int {
entry:
  %t1 = rt entry=alloc (int 8) : %ptr
  mem.store(&int %t1, int 0)
  %t2 = mem.load(&int %t1) : int
  ret(int %t2)
}
""")
        self.assertEqual(fn.casts, [101])
        self.assertIn("  %t1 = rt entry=alloc (int 8) : %ptr\n  %t101 = cast bits (%ptr %t1) : &int\n  mem.store(&int %t101, int 0)\n", out)
        self.assertIn("%t2 = mem.load(&int %t101) : int", out)

    def test_a_placeholder_the_frontend_decided_nothing_for_stays_open(self):
        source = """function @h() -> str {
  %b.1 = slot name=b : opt[None]
entry:
  mem.store(&opt[None] %b.1, opt[None] null)
  %t2 = mem.load(&str %b.1) : str
  %t3 = rt entry=list.new hole=1 (int 0) : list[?]
  %t4 = list.len(list[?] %t3) : int
  ret(str %t2)
}
"""
        _, out = self.settle(source, [""], errors=["@h: unexpected error in block entry: mem.load operand 0 reads %b.1 as &str, but it is &opt[None]"])
        self.assertEqual(out.split("\n", 1)[1], source.split("\n", 1)[1])  # (its body: not its effects)

    def test_a_use_that_reads_a_placeholder_decides_nothing(self):
        # (no reader's type decides a placeholder: the verifier rejects the read instead)
        _, out = self.settle("""function @u(s: str) -> None {
  %xs.1 = slot name=xs : list[?]
entry:
  %t2 = rt entry=list.new hole=1 (int 0) : list[?]
  mem.store(&list[?] %xs.1, list[?] %t2)
  %t3 = mem.load(&list[?] %xs.1) : list[?]
  %t4 = slot.pack(str %a0) : *str
  rt entry=list.append (list[str] %t3, *str %t4) : None
  ret.none
}
""", [""], errors=["@u: unexpected error in block entry: rt operand 0 reads %t3 as list[str], but it is list[?]"])
        self.assertIn("%xs.1 = slot name=xs : list[?]", out)

    def test_a_first_nones_slot_takes_the_type_the_frontend_decided(self):
        _, out = self.settle("""function @n(s: opt[str]) -> opt[str] {
  %b.1 = slot name=b : opt[None]
entry:
  mem.store(&opt[None] %b.1, opt[None] null)
  mem.store(&opt[str] %b.1, opt[str] %a0)
  %t2 = mem.load(&opt[str] %b.1) : opt[str]
  ret(opt[str] %t2)
}
""", decided={"%b.1": "opt[str]"})
        self.assertNotIn("opt[None]", out)
        self.assertIn("%b.1 = slot name=b : opt[str]", out)
        self.assertIn("mem.store(&opt[str] %b.1, opt[str] null)", out)

    def test_a_none_lists_items_take_the_type_its_local_was_given(self):
        _, out = self.settle("""function @l(s: str) -> list[opt[str]] {
  %xs.1 = slot name=xs : list[opt[?]]
entry:
  %t2 = rt entry=list.new (int 1) : list[opt[?]]
  rt entry=list.append (list[opt[?]] %t2, *opt[?] 0) : None
  mem.store(&list[opt[?]] %xs.1, list[opt[?]] %t2)
  %t3 = mem.load(&list[opt[str]] %xs.1) : list[opt[str]]
  ret(list[opt[str]] %t3)
}
""", decided={"%xs.1": "list[opt[str]]"})
        self.assertNotIn("?", out)
        self.assertIn("%t2 = rt entry=list.new (int 1) : list[opt[str]]", out)
        self.assertIn("rt entry=list.append (list[opt[str]] %t2, *opt[str] 0) : None", out)

    def test_a_value_takes_the_type_the_frontend_read_it_at(self):
        # (list(()) makes a list that its caller types: Gen.decide_value)
        _, out = self.settle("""function @c() -> list[str] {
entry:
  %t1 = rt entry=list.new (int 0) : list[?]
  %t2 = rt entry=list.copy (list[?] %t1) : list[?]
  ret(list[str] %t2)
}
""", decided={"%t1": "list[str]"})
        self.assertNotIn("?", out)
        self.assertIn("%t2 = rt entry=list.copy (list[str] %t1) : list[str]", out)


class DecidedTypesTests(unittest.TestCase):
    # The frontend gives each placeholder of a function the type it decides for it before the
    # function is built: an empty container's, a comprehension's, a [None] list's and a first
    # None's (docs/typed-ir.md#operand-types). Only a template's empty result, which each call
    # types (Gen.typed_empty), stays open in the template's own IR.
    SOURCE = """class P:
    def __init__(self, x: int) -> None:
        self.x = x


class Count:
    def __init__(self, n: int) -> None:
        self.i = 0
        self.n = n

    def __iter__(self) -> "Count":
        return self

    def __next__(self) -> int:
        if self.i >= self.n:
            raise StopIteration
        self.i += 1
        return self.i


def evens(n: int) -> list[int]:
    xs = []
    for i in range(n):
        if len(xs) > 3:
            break
        xs.append(i * 2)
    return xs


def best(n: int) -> int:
    b = None
    for i in range(n):
        p = P(i)
        if b is None or p.x > b.x:
            b = p
    return b.x if b is not None else -1


def counts(ws: list[str]) -> dict[str, int]:
    d = {}
    for w in ws:
        d[w] = d.get(w, 0) + 1
    return d


def slots(n: int) -> list[str | None]:
    out = [None] * n
    out[0] = "a"
    return out


def empty(n):
    return []


names: list[str] = empty(1)
names.append("x")
print(evens(5), best(4), counts(["a", "b", "a"]), slots(2), [x * x for x in range(3)], names, list(Count(3)))
"""

    def test_no_placeholder_reaches_a_built_function(self):
        # (each function's types as its building ends: later passes promote its slots)
        slot_types = {}
        open_types = {}
        settle = Gen.settle

        def capture(g, fn, late):
            settle(g, fn, late)
            if late:
                for i in fn.slots:
                    slot_types[(fn.f.name, i.s)] = i.t
                types = [i.t for i in fn.slots] + [i.t for b in fn.blocks for i in b.code] + [a.t for b in fn.blocks for i in b.code for a in i.a]
                open_types[fn.f.name] = sorted({t for t in types if "?" in t or "opt[None]" in t})

        with patch.object(Gen, "settle", capture):
            Gen().program(Loader([]).program("decided.py", self.SOURCE))
        self.assertTrue({"evens", "best", "counts", "slots", "empty"}.issubset(open_types), sorted(open_types))
        self.assertEqual(slot_types[("evens", "xs")], "list[int]")
        self.assertEqual(slot_types[("best", "b")], "P")
        self.assertEqual(slot_types[("counts", "d")], "dict[str,int]")
        self.assertEqual(slot_types[("slots", "out")], "list[opt[str]]")
        for name in open_types:
            self.assertEqual(open_types[name], ["list[?]"] if name == "empty" else [], name)


if __name__ == "__main__":
    unittest.main()
