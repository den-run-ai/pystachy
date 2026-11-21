"""The operation table is the one definition of an instruction's shape.

Run with python3 -m unittest discover -s tools -p test_typed_ir_ops.py.
"""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import typed_ir_ops
from src.pystachy_compiler import specs
from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import Blk, IFn, Ins, Val
from src.pystachy_compiler.ircheck import OpTypes, op_shape_error, op_type_error, value_types
from src.pystachy_compiler.symbols import ClassInfo, FnInfo
from src.pystachy_compiler.syntax import Node


def ins(op, t="", s="", operands=0, labels=0, k=0, x=""):
    i = Ins(op, t, s)
    i.a = [Val("%a0", "int") for _ in range(operands)]
    i.b = ["next" for _ in range(labels)]
    i.k = k
    i.x = x
    return i


def function(code):
    fn = IFn(FnInfo("shape", "@shape", Node("def", "shape", 1), ""))
    fn.n = 8
    fn.blocks[0].code = code
    fn.blocks.append(Blk("next"))
    fn.blocks[1].code = [Ins("ret.none", "", "")]
    return fn


class OperationTableTests(unittest.TestCase):
    def test_rows_are_well_formed_and_cover_the_registry(self):
        rows = typed_ir_ops.rows()
        self.assertEqual([row["name"] for row in rows], list(specs.IROPS))
        self.assertEqual(len({row["name"] for row in rows}), len(rows))
        self.assertEqual([row["name"] for row in rows if row["entry"]], ["slot"])

    def test_derived_views_agree_with_the_rows(self):
        for row in typed_ir_ops.rows():
            op = row["name"]
            with self.subTest(op=op):
                effects = specs.IROPS[op].split()
                self.assertEqual("T" in effects, row["terminator"])
                self.assertEqual("*" in effects, row["varies"])
                self.assertEqual([e for e in effects if e not in ("T", "*")], row["effects"])
                self.assertEqual(specs.RESULT_NUMBERS.get(op, 0), row["results"] or 0)
                self.assertEqual(specs.OP_TEMPS.get(op, []), row["temporaries"])
                self.assertEqual(specs.VALUE_AT.get(op, 0), row["value"])
                self.assertEqual(specs.OP_ENTRY[op], row["entry"])
                self.assertEqual(specs.OP_MIN[op], row["min"])
                self.assertEqual(specs.OP_MAX[op], -1 if row["max"] is None else row["max"])
                self.assertEqual(specs.OP_LABELS[op], {"a": specs.OP_PER_OPERAND, "i": specs.OP_INVOKE}.get(row["labels"]) or int(row["labels"]))
                self.assertEqual(specs.OP_FIELDS[op], sum(typed_ir_ops.FIELD_BITS[f] for f in row["fields"]))
                self.assertEqual(specs.OP_OPERAND_TYPES.get(op), row["operand_types"])
                self.assertEqual(specs.OP_RESULT_TYPE.get(op), row["result_type"])

    def test_each_field_is_named_for_its_op(self):
        named = {row["name"]: row["names"] for row in typed_ir_ops.rows()}
        self.assertEqual(named["rt"], {"s": "entry", "k": "hole", "x": "descriptor"})
        self.assertEqual(named["mach.addr"], {"s": "element", "k": "inbounds"})
        self.assertEqual(named["field.addr"], {"k": "index"})
        self.assertEqual(named["br"], {})
        for row in typed_ir_ops.rows():
            self.assertEqual(set(row["names"]), set(row["fields"]) - {"t"})
        # (an operator selects an arithmetic, conversion or comparison op's computation)
        self.assertEqual(sorted(op for op, names in named.items() if names.get("s") == typed_ir_ops.OPERATOR),
                         ["cast", "int.ucmp", "num.cmp", "ovf", "ptr.cmp", "scalar.bin", "scalar.cast", "scalar.cmp"])

    def test_malformed_rows_are_rejected(self):
        for text, why in (("T|0|0|1|", "columns"), ("Q|0|0|0||0|", "effect"), ("T T|0|0|0||0|", "effect"),
                          ("|1-0|0|0||0|", "operand count"), ("|01|0|0||0|", "operand count"),
                          ("|0|-1|0||0|", "results"), ("|0|0|b||0|", "label count"), ("|0|0|0|s:name t|0|", "fields"),
                          ("|0|0|0|t t|0|", "fields"), ("|0|1|0||2|", "names no number"), ("|0|0|0||4|", "names no number"),
                          # the fields column: t, or s, k or x with its name, one name per field of the op,
                          # no field's letter as a name, and operator only for an s
                          ("|0|0|0|s|0|", "with its name"), ("|0|0|0|t:type|0|", "with its name"),
                          ("|0|0|0|s:Name|0|", "with its name"), ("|0|0|0|k:index s:item|0|", "in that order"),
                          ("|0|0|0|s:k|0|", "cannot be named k"), ("|0|0|0|s:index k:index|0|", "cannot be named index"),
                          ("|0|0|0|k:operator|0|", "cannot be named operator"),
                          ("E T|0|1|0||0|", "entry storage"), ("E|0|1|1||0|", "entry storage"), ("|0|vv|0||0|", "results"),
                          ("|0|v.x|0||0|", "results"), ("|0|..1|0||0|", "results"), ("|0||0||0|", "results"),
                          # the types column: one type per operand the count admits, a result type
                          # where the op sets Ins.t, known classes, one variable per type
                          ("|1|1|0|t|0|-> int", "operand types"), ("|0|1|0|t|0|int -> int", "operand types"),
                          ("|1|1|0|t|0|int, int, int -> int", "operand types"), ("|1|1|0||0|int -> int", "result type"),
                          ("|1|1|0|t|0|int", "result type"), ("|1|1|0|t|0|int ->", "needs a result type"),
                          ("|1|1|0|t|0|$T:nope -> $T", "class"), ("|2|1|0|t|0|$T:native, $T:number -> $T", "class"),
                          ("|1|1|0|t|0|dict[$K,$V] -> int", "more than one variable"), ("|1|1|0|t|0|$ -> int", "stray"),
                          ("|1|1|0|t|0|in t -> int", "invalid type")):
            with self.subTest(text=text), patch.dict(typed_ir_ops.OPS, {"probe": text}, clear=True):
                with self.assertRaisesRegex(ValueError, why):
                    typed_ir_ops.rows()

    def test_types_column_is_read_into_operand_and_result_constraints(self):
        with patch.dict(typed_ir_ops.OPS, {"probe": "|1-2|1|0|t|1|*$T:native, list[$E] -> $T"}, clear=True):
            row = typed_ir_ops.rows()[0]
        self.assertEqual((row["operand_types"], row["result_type"]), (["*$T:native", "list[$E]"], "$T"))
        self.assertEqual(specs.type_list("dict[str,int], $T,int"), ["dict[str,int]", "$T", "int"])
        self.assertEqual((specs.OP_OPERAND_TYPES["switch"], specs.OP_RESULT_TYPE["switch"]), (["int", "int"], ""))
        self.assertEqual((specs.OP_OPERAND_TYPES["alloc.fixed"], specs.OP_RESULT_TYPE["alloc.fixed"]), ([], "layout"))
        for op in ("rt", "call", "icall", "init"):
            self.assertNotIn(op, specs.OP_OPERAND_TYPES)

    def test_lowering_temporaries_are_the_ops_own_numbers(self):
        # (each is a number its lowering names an intermediate LLVM value with: lowering.py)
        self.assertEqual(specs.OP_TEMPS["ovf"], [0])
        self.assertEqual(specs.OP_TEMPS["list.load"], [1, 2, 3])
        self.assertEqual(specs.OP_TEMPS["list.store"], [0, 1, 2])
        self.assertNotIn("list.len", specs.OP_TEMPS)
        for op, temps in specs.OP_TEMPS.items():
            with self.subTest(op=op):
                self.assertTrue(all(0 <= j < specs.RESULT_NUMBERS[op] for j in temps))

    def test_documentation_reference_is_current(self):
        text = typed_ir_ops.DOC.read_text(encoding="utf-8")
        self.assertEqual(typed_ir_ops.current(text), typed_ir_ops.reference())
        self.assertEqual(text.count(typed_ir_ops.BEGIN), 1)
        self.assertIsNone(typed_ir_ops.current(text.replace(typed_ir_ops.END, "")))

    def test_schema_matches_the_lean_checker_fields(self):
        for row, spec in zip(typed_ir_ops.rows(), typed_ir_ops.schema(), strict=True):
            self.assertEqual(set(spec), {"terminator", "entry", "min", "max", "results", "labels", "fields"})
            self.assertEqual(spec["labels"][0], {"a": 2, "i": 1}.get(row["labels"], 0))


def typed(op, t, operands, s="", labels=0):
    i = Ins(op, t, s)
    i.a = [Val(v, ty) for v, ty in operands]
    i.b = ["next" for _ in range(labels)]
    return i


class TypeCheckTests(unittest.TestCase):
    def error(self, i, ret="None"):
        fn = function([])
        fn.f.ret = ret
        return op_type_error(OpTypes(fn, {}, {}), i)

    def test_each_kind_of_constraint_is_enforced(self):
        for i, expected in (
                # a type
                (typed("cbr", "", [("%a0", "int")], labels=2), "cbr operand 0 needs bool, got int"),
                # a type class
                (typed("ptr.cmp", "bool", [("%a0", "int"), ("null", "None")], "=="),
                 "ptr.cmp operand 0 needs a native reference type or None, got int"),
                # a variable, the same type wherever the row names it, and of its class
                (typed("select", "int", [("%a0", "bool"), ("1", "int"), ("2.0", "float")]),
                 "select operand 2 needs int ($T is int at operand 1), got float"),
                (typed("select", "float", [("%a0", "bool"), ("1", "int"), ("2", "int")]),
                 "select result needs int ($T is int at operand 1), got float"),
                (typed("select", "None", [("%a0", "bool"), ("null", "None"), ("null", "None")]),
                 "select operand 1 needs a native value type other than None, a machine scalar (%ptr, %byte, %i32, %slot) or a packed slot, got None"),
                # a type around a variable
                (typed("mem.load", "int", [("%a0", "int")]), f"mem.load operand 0 needs &$T, $T {specs.TYPE_CLASSES['native']}, got int"),
                (typed("mem.load", "%ptr", [("%a0", "&%ptr")]), f"mem.load operand 0 needs &$T, $T {specs.TYPE_CLASSES['native']}, got &%ptr"),
                (typed("mem.load", "int", [("%a0", "*int")]), f"mem.load operand 0 needs &$T, $T {specs.TYPE_CLASSES['native']}, got *int"),
                (typed("list.store", "", [("%a0", "list[int]"), ("0", "int"), ("%a1", "*float")]),
                 "list.store operand 2 needs *int ($E is int at operand 0), got *float"),
                (typed("list.len", "int", [("%a0", "list[int+]")]),
                 "list.len operand 0 needs list[$E], $E a list's item type: one type, no machine representation, got list[int+]"),
                # the last operand's constraint holds for any further operands
                (typed("switch", "", [("%a0", "int"), ("1", "int"), ("2", "float")], labels=3), "switch operand 2 needs int, got float"),
                # a result type
                (typed("num.cmp", "int", [("%a0", "int"), ("1", "int")], "<"), "num.cmp result needs bool, got int"),
                (typed("landing", "", [("%a0", "%addr")], labels=1), "landing result needs exc, got no type")):
            with self.subTest(expected=expected):
                self.assertEqual(self.error(i), expected)

    def test_rows_admit_what_the_compiler_emits(self):
        for i in (typed("cbr", "", [("%a0", "bool")], labels=2), typed("select", "%slot", [("%a0", "bool"), ("%a1", "%slot"), ("%a2", "%slot")]),
                  typed("mem.load", "None", [("%a0", "&None")]), typed("list.store", "", [("%a0", "list[int]"), ("0", "int"), ("%a1", "*int")]),
                  typed("switch", "", [("%a0", "int"), ("1", "int"), ("2", "int")], labels=3), typed("phi", "int", [("1", "int"), ("2", "int")], labels=2),
                  typed("vtuple.make", "vtuple[dyn]", [("%a0", "dyn"), ("%a1", "dyn")]), typed("vtuple.make", "vtuple[int]", []),
                  typed("gen.ret", "", []), typed("gen.yield", "", [("%a0", "%slot"), ("null", "%ptr"), ("%a1", "dyn")], labels=1)):
            with self.subTest(op=i.op):
                self.assertEqual(self.error(i), "")

    def test_a_return_has_the_functions_type_its_reference_or_an_empty_containers(self):
        for value, returned in (("dict[str,int]", "dict[str,int]"), ("dict[?,?]", "dict[str,int]"),
                                ("str", "opt[str]"), ("list[?]", "opt[list[int]]")):
            with self.subTest(value=value, returned=returned):
                self.assertEqual(self.error(typed("ret", "", [("%a0", value)]), returned), "")
        # (a boxed int | None is no int: the int needs its box first)
        for value, returned in (("list[?]", "dict[str,int]"), ("int", "opt[int]"), ("str", "opt[bytes]")):
            with self.subTest(value=value, returned=returned):
                self.assertEqual(self.error(typed("ret", "", [("%a0", value)]), returned),
                                 f"ret operand 0 needs {specs.TYPE_CLASSES['return']}, got {value}")

    def test_a_union_is_validated_once_and_its_members_kept_for_the_proofs(self):
        unions = {}
        check = OpTypes(function([]), {}, unions)
        for _ in range(3):
            self.assertEqual(op_type_error(check, typed("union.tag", "int", [("%a0", "union[int,str]")])), "")
        self.assertEqual(unions, {"union[int,str]": ["int", "str"]})
        for u in ("union[int,int]", "union[int]", "opt[int]", "union[int,opt[str]]"):
            with self.subTest(u=u):
                self.assertEqual(op_type_error(check, typed("union.tag", "int", [("%a0", u)])),
                                 f"union.tag operand 0 needs {specs.TYPE_CLASSES['union']}, got {u}")

    def test_reused_variable_binds_at_each_instruction(self):
        check = OpTypes(function([]), {}, {})
        bindings, positions = check.bound, check.where
        for t in ("int", "float", "int"):
            operands = [("true", "bool"), ("%a0", t), ("%a1", t)]
            self.assertEqual(op_type_error(check, typed("select", t, operands)), "")
            self.assertIs(check.bound, bindings)
            self.assertIs(check.where, positions)
        self.assertEqual(op_type_error(check, typed("mem.load", "int", [("%slot.0", "&float")])),
                         "mem.load result needs float ($T is float at operand 0), got int")

    def test_calls_are_left_to_their_signatures(self):
        self.assertEqual(self.error(typed("rt", "anything", [("%a0", "S")], "list.len")), "")

    def test_verifier_checks_types_after_the_shape(self):
        for code, expected in (([typed("cbr", "", [("%a0", "int")], labels=2)], "cbr operand 0 needs bool, got int"),
                               ([typed("cbr", "", [("%a0", "int")], labels=1)], "cbr with 1 labels")):
            with self.subTest(expected=expected):
                errors = StringIO()
                with redirect_stderr(errors), self.assertRaises(SystemExit):
                    Gen().verify(function(code), False)
                self.assertIn(expected, errors.getvalue())


def made(op, t, r, operands=(), s=""):
    """An op that defines value %t<r>."""
    i = typed(op, t, list(operands), s)
    i.r = [r]
    return i


def slot(name, t, r):
    i = Ins("slot", t, name)
    i.r = [r]
    return i


class ValueTypeTests(unittest.TestCase):
    """An operand reads its value at its definition's type or by a view (specs.TYPE_VIEWS)."""

    def error(self, code, params=(), slots=(), mod="", classes=()):
        fn = function(code)
        fn.n = 64
        fn.f.params = [f"p{j}" for j in range(len(params))]
        fn.f.ptypes = list(params)
        fn.f.mod = mod
        fn.slots = list(slots)
        g = Gen()
        for name, base in classes:
            g.classes[name] = ClassInfo(name, Node("class", name, 1))
            g.classes[name].base = base
        errors = StringIO()
        try:
            with redirect_stderr(errors):
                value_types(g, fn)
        except SystemExit:
            return errors.getvalue().split(": ")[-1].strip()
        return ""

    def test_each_view_is_admitted(self):
        classes = (("Base", ""), ("Derived", "Base"))
        for view, code, params, slots in (
                ("machine", [typed("mach.load", "int", [("%a0", "%ptr")])], ["str"], ()),
                ("machine", [typed("mach.store", "", [("%x.1", "%ptr"), ("0", "int")])], (), [slot("x", "int", 1)]),
                ("bits", [made("rt", "%ptr", 1, [("%a0", "*T")], "box"), typed("ret", "", [("%t1", "opt[int]")])], ["int"], ()),
                ("bits", [made("rt", "%ptr", 1, [], "x"), typed("mem.load", "int", [("%t1", "&int")])], (), ()),
                ("instance", [made("rt", "list[T]", 1, [("3", "int")], "list.new"), typed("list.len", "int", [("%t1", "list[str]")])], (), ()),
                ("instance", [typed("mem.load", "list[str]", [("%x.1", "&list[str]")])], (), [slot("x", "list[?]", 1)]),
                ("instance", [typed("rt", "int", [("%a0", "S")], "dict.len")], ["dict[str,int]"], ()),
                ("alias", [typed("ret", "", [("%a0", "bytes")])], ["str"], ()),
                ("alias", [typed("slot.pack", "%slot", [("%a0", "tuple[int,str]")])], ["tuple[bool,str]"], ()),
                ("int slot", [made("list.load", "*int", 1, [("%a0", "list[int]"), ("0", "int")]), typed("ret", "", [("%t1", "int")])],
                 ["list[int]"], ()),
                ("optional", [typed("ret", "", [("%a0", "opt[str]")])], ["str"], ()),
                ("optional", [typed("rt", "str", [("%a0", "list[str]")], "str.join")], ["list[opt[str]]"], ()),
                ("class", [typed("ret", "", [("%a0", "Base")])], ["Derived"], ()),
                ("class", [typed("ret", "", [("%a0", "Derived")])], ["Base"], ()),
                ("runtime bool", [made("rt", "bool", 1, [], "eq"), typed("num.cmp", "bool", [("%t1", "int"), ("0", "int")], "!=")], (), ()),
                ("method", [typed("ptr.cmp", "bool", [("%a0", "Base"), ("null", "None")], "==")], ["fn[m:Base.f]"], ())):
            with self.subTest(view=view, params=params):
                self.assertEqual(self.error(code, params, slots, classes=classes), "")

    def test_other_readings_are_rejected(self):
        classes = (("Base", ""), ("Derived", "Base"), ("Other", ""))
        for code, params, slots, expected in (
                ([typed("ret", "", [("%a0", "float")])], ["int"], (), "ret operand 0 reads %a0 as float, but it is int"),
                ([typed("list.len", "int", [("%a0", "list[str]")])], ["list[int]"], (), "list.len operand 0 reads %a0 as list[str], but it is list[int]"),
                ([typed("ret", "", [("%a0", "Other")])], ["Base"], (), "ret operand 0 reads %a0 as Other, but it is Base"),
                ([typed("ret", "", [("%a0", "int+")])], ["int"], (), "ret operand 0 reads %a0 as int+, but it is int"),
                ([typed("ret", "", [("%a0", "opt[int]")])], ["int"], (), "ret operand 0 reads %a0 as opt[int], but it is int"),
                ([typed("ret", "", [("%a0", "Base")])], ["str"], (), "ret operand 0 reads %a0 as Base, but it is str"),
                ([typed("slot.pack", "%slot", [("%a0", "tuple[int,str]")])], ["tuple[str,str]"], (),
                 "slot.pack operand 0 reads %a0 as tuple[int,str], but it is tuple[str,str]"),
                ([typed("mach.load", "int", [("%a0", "%ptr")])], ["int"], (), "mach.load operand 0 reads %a0 as %ptr, but it is int"),
                ([typed("slot.unpack", "str", [("%a0", "%slot")])], ["str"], (), "slot.unpack operand 0 reads %a0 as %slot, but it is str"),
                ([made("rt", "%slot", 1, [], "x"), typed("ret", "", [("%t1", "str")])], (), (), "ret operand 0 reads %t1 as str, but it is %slot"),
                ([made("rt", "list[T]", 1, [], "list.new"), typed("ret", "", [("%t1", "dict[str,int]")])], (), (),
                 "ret operand 0 reads %t1 as dict[str,int], but it is list[T]"),
                ([typed("rt", "%ptr", [("%x.1", "*T")], "box")], (), [slot("x", "int", 1)], "rt operand 0 reads the address %x.1 as a packed slot"),
                ([made("list.load", "*int", 1, [("%a0", "list[int]"), ("0", "int")]), typed("mem.load", "int", [("%t1", "&int")])], ["list[int]"], (),
                 "mem.load operand 0 reads %t1, a packed slot, as an address"),
                ([made("rt", "%ptr", 1, [], "x"), typed("mem.store", "", [("%s.2", "&str"), ("%t1", "str")]), typed("ret", "", [("%t1", "list[int]")])],
                 (), [slot("s", "str", 2)], "ret operand 0 reads %t1 as list[int], where mem.store operand 1 reads it as str"),
                # (another op's machine word is read at a type only through a cast: bits are an rt op's)
                ([made("mach.load", "%ptr", 1, [("%a0", "%ptr")]), typed("ret", "", [("%t1", "str")])], ["str"], (),
                 "ret operand 0 reads %t1 as str, but it is %ptr"),
                ([made("slot.pack", "%slot", 1, [("%a0", "float")]), typed("num.cast", "float", [("%t1", "int")])], ["float"], (),
                 "num.cast operand 0 reads %t1 as int, but it is %slot"),
                # (nor is a value read as a closed union of classes and as one of its members: casts do)
                ([made("rt", "%ptr", 1, [], "x"), typed("ptr.cmp", "bool", [("%t1", "union[Base,Other]"), ("null", "None")], "=="),
                  typed("ret", "", [("%t1", "Other")])], (), (), "ret operand 0 reads %t1 as Other, where ptr.cmp operand 0 reads it as union[Base,Other]")):
            with self.subTest(expected=expected):
                self.assertEqual(self.error(code, params, slots, classes=classes), expected)
        # (lib/_pystachy_copy.py's memo reads a reference as a str through opaque casts)
        self.assertEqual(self.error([typed("ret", "", [("%a0", "Base")])], ["str"], mod="_pystachy_copy", classes=classes),
                         "ret operand 0 reads %a0 as Base, but it is str")

    def test_a_value_its_definition_types_loosely_is_read_at_related_types(self):
        classes = (("Base", ""), ("Derived", "Base"))
        code = [made("rt", "%ptr", 1, [], "x"), typed("ptr.cmp", "bool", [("%t1", "opt[Base]"), ("null", "None")], "=="),
                typed("ret", "", [("%t1", "Derived")])]
        self.assertEqual(self.error(code, classes=classes), "")


class CastTests(unittest.TestCase):
    """A cast reads its operand at another type of its LLVM type, by its kind's rule (specs.CAST_KINDS)."""

    def error(self, code, params=(), mod=""):
        fn = function(code + [typed("br", "", [], labels=1)])
        fn.n = 64
        fn.f.params = [f"p{j}" for j in range(len(params))]
        fn.f.ptypes = list(params)
        fn.f.mod = mod
        g = Gen()
        for name in ("A", "B", "C", "D"):
            g.classes[name] = ClassInfo(name, Node("class", name, 1))
        g.classes["C"].base = "A"
        errors = StringIO()
        try:
            with redirect_stderr(errors):
                g.verify(fn, False)
        except SystemExit:
            return errors.getvalue().split(": ", 3)[-1].strip()
        return ""

    def test_each_kind_reads_what_its_rule_admits(self):
        for code, params, mod in (
                ([made("cast", "&int", 1, [("%a0", "%ptr")], "bits")], ["%ptr"], ""),
                ([made("cast", "str", 1, [("%a0", "%ptr")], "bits")], ["%ptr"], ""),
                ([made("cast", "int", 1, [("%a0", "%slot")], "bits")], ["%slot"], ""),
                ([made("cast", "*float", 1, [("%a0", "%slot")], "bits")], ["%slot"], ""),
                # (another op's word, which the bits view reads at a type only where an rt op makes it
                # or reads it at a type variable)
                ([made("slot.pack", "%slot", 1, [("%a0", "float")]), made("cast", "int", 2, [("%t1", "%slot")], "bits"),
                  made("num.cmp", "bool", 3, [("%t2", "int"), ("0", "int")], "==")], ["float"], ""),
                ([made("cast", "union[A,B]", 1, [("%a0", "%ptr")], "object"), made("cast", "C", 2, [("%t1", "union[A,B]")], "member"),
                  made("ptr.cmp", "bool", 3, [("%t1", "union[A,B]"), ("null", "None")], "=="), made("mach.load", "%ptr", 4, [("%t1", "%ptr")])],
                 ["%ptr"], ""),
                ([made("cast", "str", 1, [("%a0", "A")], "opaque"), made("cast", "A", 2, [("%t1", "str")], "opaque")], ["A"], "_pystachy_copy")):
            with self.subTest(kinds=[i.s for i in code if i.op == "cast"]):
                self.assertEqual(self.error(code, params, mod), "")

    def test_each_kind_rejects_what_its_rule_does_not(self):
        for code, params, mod, expected in (
                ([made("cast", "int", 1, [("%a0", "%ptr")], "bits")], ["%ptr"], "", "cast bits of a %ptr to a int, where a cast reads"),
                ([made("cast", "%ptr", 1, [("%a0", "%ptr")], "bits")], ["%ptr"], "", "cast bits of a %ptr to a %ptr, where a cast reads"),
                ([made("cast", "*str", 1, [("%a0", "%ptr")], "bits")], ["%ptr"], "", "cast bits of a %ptr to a *str, where a cast reads"),
                ([made("cast", "str", 1, [("%a0", "A")], "bits")], ["A"], "", "cast bits of a A to a str, where a cast of kind bits reads a machine word"),
                ([made("cast", "bool", 1, [("%a0", "%slot")], "bits")], ["%slot"], "", "cast bits of a %slot to a bool, where a cast reads"),
                ([made("cast", "int", 1, [("%a0", "%slot")], "wide")], ["%slot"], "", "cast wide, where a cast is of a kind"),
                ([made("cast", "union[A,int]", 1, [("%a0", "%ptr")], "object")], ["%ptr"], "", "cast object of a %ptr to a union[A,int], where a cast of kind object reads"),
                ([made("cast", "A", 1, [("%a0", "union[A,B]")], "member")], ["union[A,B]"], "", "cast member of a union[A,B] to a A, where a cast of kind member reads"),
                ([made("cast", "union[A,B]", 1, [("%a0", "%ptr")], "object"), made("cast", "str", 2, [("%t1", "union[A,B]")], "member")],
                 ["%ptr"], "", "cast member of a union[A,B] to a str, where a cast of kind member reads"),
                ([made("cast", "union[A,B]", 1, [("%a0", "%ptr")], "object"), made("union.tag", "int", 2, [("%t1", "union[A,B]")])],
                 ["%ptr"], "", "union.tag reads %t1, an object cast's value"),
                ([made("cast", "union[A,B]", 1, [("%a0", "%ptr")], "object"), made("mach.load", "str", 2, [("%t1", "%ptr")])],
                 ["%ptr"], "", "mach.load reads %t1, an object cast's value"),
                # (a rule holds of the value at its definition's type, which no view may change: a %ptr
                # reads any reference, a %slot any packed slot, a union one with a common member)
                ([made("cast", "list[int]", 1, [("%a0", "%ptr")], "bits")], ["str"], "",
                 "cast bits of %a0, a str read as a %ptr, where a cast of kind bits reads a machine word"),
                ([made("slot.pack", "*float", 1, [("%a0", "float")]), made("cast", "int", 2, [("%t1", "%slot")], "bits")], ["float"], "",
                 "cast bits of %t1, a *float read as a %slot, where a cast of kind bits reads a machine word"),
                ([made("cast", "B", 1, [("%a0", "%ptr")], "bits")], ["A"], "", "cast bits of %a0, a A read as a %ptr, where"),
                ([made("cast", "union[A,B]", 1, [("%a0", "%ptr")], "object"), made("cast", "A", 2, [("%t1", "union[A,B]")], "member")],
                 ["union[A,B]"], "", "cast object of %a0, a union[A,B] read as a %ptr, where a cast of kind object reads"),
                ([made("cast", "union[A,B]", 1, [("%a0", "%ptr")], "object"), made("cast", "D", 2, [("%t1", "union[B,D]")], "member")],
                 ["%ptr"], "", "cast member of %t1, a union[A,B] read as a union[B,D], where a cast of kind member reads"),
                ([made("cast", "str", 1, [("%a0", "A")], "opaque")], ["A"], "", "cast opaque of a A to a str, where a cast of kind opaque reads"),
                ([made("cast", "B", 1, [("%a0", "A")], "opaque")], ["A"], "_pystachy_copy", "cast opaque of a A to a B, where a cast of kind opaque reads")):
            with self.subTest(expected=expected):
                self.assertIn(expected, self.error(code, params, mod))


class ShapeCheckTests(unittest.TestCase):
    def test_each_count_and_field_of_a_row_is_enforced(self):
        self.assertEqual(op_shape_error(ins("br", labels=1), False), "")
        self.assertEqual(op_shape_error(ins("slot", "int", "x", k=1), True), "")
        for i, entry, expected in (
                (ins("br"), False, "br with 0 labels, where the operation table has 1"),
                (ins("br", labels=2), False, "br with 2 labels, where the operation table has 1"),
                (ins("br", operands=1, labels=1), False, "br with 1 operands, where the operation table has 0"),
                (ins("cbr", operands=1, labels=1), False, "cbr with 1 labels, where the operation table has 2"),
                (ins("phi", "int", operands=2, labels=1), False, "phi with 1 labels, where the operation table has a"),
                (ins("switch", operands=1, labels=1), False, "switch with 1 operands, where the operation table has 2+"),
                (ins("rt", "int", "list.len", operands=1, labels=1), False, "rt with 1 labels, where the operation table has i"),
                (ins("ret", operands=2), False, "ret with 2 operands, where the operation table has 0-1"),
                (ins("br", s="text", labels=1), False, "br sets s, where its row of the operation table names no field"),
                (ins("br", "int", labels=1), False, "br sets t, where its row of the operation table names no field"),
                (ins("throw", operands=1, k=1), False, "throw sets k, where its row of the operation table names no field"),
                (ins("icall", "int", operands=1, x="inline"), False, "icall sets x, where its row of the operation table names t"),
                (ins("num.cmp", "bool", "<", operands=2, k=1), False,
                 "num.cmp sets k, where its row of the operation table names t, s:operator"),
                (ins("slot", "int", "x"), False, "slot in a block, where entry storage belongs among the slots"),
                (ins("br", labels=1), True, "br among the slots")):
            with self.subTest(op=i.op, expected=expected):
                self.assertEqual(op_shape_error(i, entry), expected)

    def test_an_invoke_keeps_its_two_labels(self):
        for op in ("rt", "call", "icall", "init", "gen.resume"):
            with self.subTest(op=op):
                self.assertEqual(specs.OP_LABELS[op], specs.OP_INVOKE)
                operands = max(specs.OP_MIN[op], 1 if op != "init" else 0)
                self.assertEqual(op_shape_error(ins(op, operands=operands, labels=2), False), "")
                self.assertEqual(op_shape_error(ins(op, operands=operands), False), "")

    def test_verifier_reports_a_shape_no_specific_check_names(self):
        for code, expected in (([ins("cbr", operands=1, labels=1)], "cbr with 1 labels"),
                               ([ins("slot", "int", "x"), ins("br", labels=1)], "slot in a block"),
                               ([ins("throw", operands=2)], "throw with 2 operands")):
            with self.subTest(expected=expected):
                for i in code:
                    for a in i.a:
                        a.t = "bool"
                errors = StringIO()
                with redirect_stderr(errors), self.assertRaises(SystemExit):
                    Gen().verify(function(code), False)
                self.assertIn(expected, errors.getvalue())

    def test_verifier_rejects_an_operand_that_names_a_lowering_temporary(self):
        for temporary, value in (("%t3", "%t4"), ("%t5", "%t4")):
            with self.subTest(temporary=temporary):
                read = ins("list.load", "*int", operands=2)
                read.a = [Val("%a0", "list[int]"), Val("0", "int")]
                read.r = [4, 3, 5, 6]
                use = Ins("ret", "", "")
                use.a = [Val(temporary, "int")]
                fn = function([read, use])
                fn.f.ret = "int"
                fn.blocks.pop()
                errors = StringIO()
                with redirect_stderr(errors), self.assertRaises(SystemExit):
                    Gen().verify(fn, False)
                self.assertIn(f"ret operand {temporary} is a temporary of a list.load op's lowering, which no op may use",
                              errors.getvalue())
                use.a = [Val(value, "int")]
                Gen().verify(fn, False)

    def test_verifier_holds_slots_to_the_table(self):
        fn = function([ins("br", labels=1)])
        slot = ins("slot", "int", "x", x="descriptor")
        slot.r = [1]
        fn.slots = [slot]
        errors = StringIO()
        with redirect_stderr(errors), self.assertRaises(SystemExit):
            Gen().verify(fn, False)
        self.assertIn("slot sets x, where its row of the operation table names t, s:name, k:kind", errors.getvalue())
        slot.x = ""
        Gen().verify(fn, False)


if __name__ == "__main__":
    unittest.main()
