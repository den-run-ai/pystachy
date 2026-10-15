"""Class layout addresses remain typed until LLVM lowering."""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import ClassInfo, FnInfo, IFn, Ins, Val, Values
from src.pystachy_compiler.loader import Loader
from src.pystachy_compiler.specs import FXBIT
from src.pystachy_compiler.syntax import Node


def fixture():
    g = Gen()
    ci = ClassInfo("Box", Node("class", "Box", 1))
    ci.fields = ["value", "text", " inherited.flag"]
    ci.ftypes = {"value": "int", "text": "str", " inherited.flag": "bool"}
    ci.fpos = {name: i for i, name in enumerate(ci.fields)}
    ci.fflag = {"text": 3}
    ci.nflag = 1
    g.classes["Box"] = ci
    return g


def address(index=0, t="*int"):
    i = Ins("field.addr", t, "")
    i.k = index
    i.a = [Val("%a0", "Box")]
    i.r = [1]
    return i


def function(i):
    fn = IFn(FnInfo("fields", "@fields", Node("def", "fields", 1), ""))
    fn.n = 2
    fn.blocks[0].code = [i, Ins("ret.none", "", "")]
    return fn


class TypedFieldTests(unittest.TestCase):
    def test_fields_flags_and_exact_lowering(self):
        for index, t in enumerate(("*int", "*str", "*bool", "*bool")):
            with self.subTest(index=index):
                g = fixture()
                i = address(index, t)
                g.verify(function(i), False)
                self.assertEqual(g.nums(i), 1)
                self.assertEqual(g.opfx(i, {}), 0)
                g.lower_ins(function(i), i)
                self.assertEqual(g.out, [f"  %t1 = getelementptr %C.Box, ptr %a0, i32 0, i32 {index}"])

    def test_invalid_layout_index_type_shape_and_metadata(self):
        cases = [("k", -1), ("k", 4), ("t", "int"), ("t", "*float"),
                 ("s", "value"), ("x", "int"), ("b", ["entry"]),
                 ("a", []), ("a", [Val("%a0", "opt[Box]")]),
                 ("a", [Val("%a0", "Missing")]),
                 ("a", [Val("%a0", "Box"), Val("%a1", "Box")]),
                 ("r", []), ("r", [1, 2])]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                i = address()
                setattr(i, field, value)
                error = StringIO()
                with redirect_stderr(error), self.assertRaises(SystemExit):
                    fixture().verify(function(i), False)
                self.assertIn("field.addr", error.getvalue())

    def test_repeated_field_addresses_are_canonical(self):
        g = fixture()
        a = address()
        b = address()
        b.r = [2]
        fn = function(a)
        fn.blocks[0].code.insert(1, b)
        vs = Values(fn, {"entry": []})
        self.assertEqual(g.canon(vs, "%t1"), g.canon(vs, "%t2"))

    def test_field_addresses_keep_memory_effects(self):
        g = fixture()
        p = g.fgep(Val("%a0", "Box"), 1)
        self.assertEqual(g.fn.blocks[0].code[-1].t, "*str")
        load = Ins("mach.load", "%ptr", "")
        load.a = [Val(p, "%ptr")]
        store = Ins("mach.store", "", "")
        store.a = [Val(p, "%ptr"), Val("%a1", "%ptr")]
        self.assertEqual(g.opfx(load, g.fn.fa), FXBIT["rO"])
        self.assertEqual(g.opfx(store, g.fn.fa), FXBIT["wO"])

    def test_semantic_field_keys_retain_inheritance_aliases(self):
        g = fixture()
        for name, base in (("Child", "Box"), ("Other", "")):
            ci = ClassInfo(name, Node("class", name, 1))
            ci.base = base
            ci.fields = ["value"]
            ci.ftypes = {"value": "int"}
            g.classes[name] = ci
        fields = [g.fgep(Val("%a0", cls), index)
                  for cls, index in (("Box", 0), ("Box", 1), ("Box", 0),
                                     ("Child", 0), ("Other", 0))]
        g.fn.n = g.n
        vs = Values(g.fn, {"entry": []})
        first, distinct, same, inherited, unrelated = [g.canon(vs, p) for p in fields]
        self.assertEqual(first, same)
        self.assertFalse(g.disjoint(vs, first, same))
        self.assertTrue(g.disjoint(vs, first, distinct))
        self.assertFalse(g.disjoint(vs, first, inherited))
        self.assertFalse(g.disjoint(vs, inherited, first))
        self.assertTrue(g.disjoint(vs, first, unrelated))

    def test_native_and_machine_accesses_share_field_alias_barriers(self):
        for native_store in (False, True):
            for native_load in (False, True):
                for cls, index, expected in (("Box", 0, "99"), ("Box", 1, "41"),
                                              ("Child", 0, None), ("Other", 0, "41")):
                    with self.subTest(store=native_store, load=native_load,
                                      intervening_class=cls, index=index):
                        g = fixture()
                        for name, base in (("Child", "Box"), ("Other", "")):
                            ci = ClassInfo(name, Node("class", name, 1))
                            ci.base = base
                            ci.fields = ["value"]
                            ci.ftypes = {"value": "int"}
                            g.classes[name] = ci
                        p = g.fgep(Val("%a0", "Box"), 0)
                        same = g.fgep(Val("%a0", "Box"), 0)
                        other = g.fgep(Val("%a0", cls), index)
                        if native_store:
                            g.mem_store(Val(p, "*int"), Val("41", "int"))
                        else:
                            g.mstore("int", "41", p)
                        g.mstore("str" if index == 1 else "int",
                                 "@text" if index == 1 else "99", other)
                        result = g.mem_load(Val(same, "*int")).v if native_load else g.mload("int", same)
                        g.fn.n = g.n
                        vs = Values(g.fn, {"entry": []})
                        self.assertEqual(g.canon(vs, result), result if expected is None else expected)

    def test_source_uses_typed_declared_layouts(self):
        root = Path(__file__).resolve().parent.parent / "tests"
        captured = []
        lower = Gen.lower

        def capture(g, fn):
            g.verify(fn, False)
            for b in fn.blocks:
                for i in b.code:
                    self.assertFalse(i.op == "raw" and "getelementptr %C." in i.s)
                    if i.op == "field.addr":
                        captured.append(i)
                        self.assertTrue(i.t.startswith("*"))
                        self.assertIn(i.a[0].t, g.classes)
            lower(g, fn)

        with patch.object(Gen, "lower", capture):
            for name in ("reference_union_inheritance.py", "typed_ir_slots.py"):
                Gen().program(Loader([]).program(name, (root / name).read_text()))
        self.assertTrue(captured)


if __name__ == "__main__":
    unittest.main()
