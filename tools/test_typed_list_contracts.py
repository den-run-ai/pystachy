"""Native list writes share semantic, storage and identity checks before LLVM.

Run with python3 -m unittest discover -s tools -p test_typed_list_contracts.py.
"""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler import diagnostics
from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import FnInfo, IFn, Ins, Val
from src.pystachy_compiler.loader import Loader
from src.pystachy_compiler.specs import LIST_WRITES
from src.pystachy_compiler.syntax import Node
from src.pystachy_compiler.utils import ListLayout, list_write_error, rtsym


def list_write(key="list.append", element="int"):
    i = Ins("rt", "None", key)
    i.a = [Val("%a0", f"list[{element}]")]
    if not key.startswith("list.append"):
        i.a.append(Val("0", "int"))
    i.a.append(Val("%a1", "%ptr" if key.endswith("_big") else "*" + element))
    if key.endswith("_identity"):
        i.a.extend([Val("%a2", "dyn"), Val("2" if element == "float" else "1", "int")])
    return i


def function_with(i):
    fn = IFn(FnInfo("list_write", "@list_write", Node("def", "list_write", 1), ""))
    fn.n = 2
    fn.blocks[0].code = [i, Ins("ret.none", "", "")]
    return fn


class ListLayoutTests(unittest.TestCase):
    def test_promoting_representation_keeps_semantic_element_and_atomic_payload(self):
        checked = ListLayout("list[int]", False)
        wide = ListLayout("list[int]", True)
        self.assertEqual((checked.element, checked.slot, checked.value), ("int", "*int", "int"))
        self.assertEqual((wide.element, wide.slot, wide.value), ("int", "*int", "int+"))
        self.assertFalse(checked.wide)
        self.assertTrue(wide.wide)
        self.assertTrue(checked.atomic and wide.atomic)
        self.assertEqual((checked.identity_kind, wide.identity_kind), (1, 1))

    def test_dynamic_descriptor_uses_native_storage_policy(self):
        for promoting in (False, True):
            with patch.dict(diagnostics.INTFILES, {0: True} if promoting else {}, clear=True):
                g = Gen()
                for element in ("int", "dyn", "float", "str", "bool", "list[int]"):
                    with self.subTest(promoting=promoting, element=element):
                        t = f"list[{element}]"
                        layout = ListLayout(t, promoting)
                        if element in ("int", "dyn"):
                            expected = "pys_dyntype_list" if element == "dyn" else "pys_dyntype_biglist" if promoting else "pys_dyntype_intlist"
                            self.assertEqual(layout.dynamic_type, expected)
                            self.assertEqual(g.dyn_type(t), "@" + expected)
                            self.assertEqual(g.dyn_boxable(t), "")
                            self.assertTrue(g.dyn_unboxable(t))
                        else:
                            self.assertEqual(layout.dynamic_type, "")
                            self.assertNotEqual(g.dyn_boxable(t), "")
                            self.assertFalse(g.dyn_unboxable(t))

    def test_reference_payloads_and_numeric_identity_are_independent(self):
        for element, atomic, identity in (("float", True, 2), ("bool", True, 0),
                                          ("str", False, 0), ("dyn", False, 0),
                                          ("list[int]", False, 0)):
            with self.subTest(element=element):
                layout = ListLayout(f"list[{element}]", True)
                self.assertEqual((layout.element, layout.slot, layout.value),
                                 (element, "*" + element, element))
                self.assertEqual((layout.atomic, layout.identity_kind), (atomic, identity))
                self.assertFalse(layout.wide)


class ListWriteContractTests(unittest.TestCase):
    def assert_rejected(self, i, fragment, promoting=False, builder=True):
        with patch.dict(diagnostics.INTFILES, {0: True} if promoting else {}, clear=True):
            error = list_write_error(i, promoting)
            self.assertIn(fragment, error)
            for construction in ((True, False) if builder else (False,)):
                with self.subTest(builder=construction):
                    g = Gen()
                    errors = StringIO()
                    if not construction:
                        g.runtime(rtsym(i.s))
                    with redirect_stderr(errors), self.assertRaises(SystemExit) as raised:
                        if construction:
                            g.list_write(i.s, i.a)
                        else:
                            g.verify(function_with(i), False)
                    self.assertEqual(raised.exception.code, 1)
                    self.assertIn(error, errors.getvalue())
                    if construction:
                        self.assertEqual(g.fn.blocks[0].code, [])

    def test_all_registered_variants_construct_and_verify_with_typed_operands(self):
        for key in LIST_WRITES:
            with self.subTest(key=key), patch.dict(diagnostics.INTFILES, {0: True}, clear=True):
                i = list_write(key, "float" if key.endswith("_identity") else "int")
                g = Gen()
                g.list_write(key, i.a)
                emitted = g.fn.blocks[0].code[0]
                self.assertIs(emitted.a, i.a)
                self.assertEqual((emitted.op, emitted.t, emitted.r), ("rt", "None", []))
                self.assertIn(key, g.rtfns)
                g.verify(function_with(emitted), False)
                self.assertEqual(g.nums(emitted), 0)

    def test_same_machine_slots_cannot_substitute_different_semantic_elements(self):
        for receiver, packed in (("int", "dyn"), ("dyn", "int"), ("float", "int"),
                                 ("str", "dyn"), ("list[int]", "list[dyn]")):
            i = list_write(element=receiver)
            i.a[1].t = "*" + packed
            with self.subTest(receiver=receiver, packed=packed):
                self.assert_rejected(i, "operand 1 needs *" + receiver)

    def test_erased_and_malformed_receivers_are_rejected_before_codegen(self):
        for receiver in ("S", "%ptr", "dyn", "list[]", "list[int,float]", "list[int"):
            i = list_write()
            i.a[0].t = receiver
            with self.subTest(receiver=receiver):
                self.assert_rejected(i, "list receiver")

        # Equal bracket counts alone do not make these single outer lists.
        # Match the spurious slot too, so operand agreement cannot mask the bug.
        for element in ("int][str", "int]][[str"):
            with self.subTest(element=element):
                self.assert_rejected(list_write(element=element), "list receiver")

        for element in ("%ptr", "int+"):
            with self.subTest(element=element):
                self.assert_rejected(list_write(element=element), "semantic item type")

    def test_deferred_none_element_keeps_its_matching_zero_slot(self):
        # Agreement preserves a None-only display while existing refinement owns its hole.
        # This contract does not prove that semantic type resolution has completed.
        i = list_write(element="opt[?]")
        i.a[-1].v = "0"
        g = Gen()
        g.list_write(i.s, i.a)
        emitted = g.fn.blocks[0].code[0]
        self.assertEqual([(a.v, a.t) for a in emitted.a],
                         [("%a0", "list[opt[?]]"), ("0", "*opt[?]")])
        g.verify(function_with(emitted), False)

    def test_builder_retains_runtime_self_recursion_guard(self):
        g = Gen()
        g.rtmode = True
        g.curfn.ll = "@pys_list_append"
        i = list_write()
        errors = StringIO()
        with redirect_stderr(errors), self.assertRaises(SystemExit):
            g.list_write(i.s, i.a)
        self.assertIn("pys_list_append() implements an operation that it uses", errors.getvalue())
        self.assertEqual(g.fn.blocks[0].code, [])
        g.curfn.ll = "@other_runtime_function"
        g.list_write(i.s, i.a)
        self.assertEqual(len(g.fn.blocks[0].code), 1)

    def test_operation_contract_accepts_two_invoke_continuations(self):
        # The ordinary CFG verifier owns the targets and landing-block requirements.
        i = list_write("list.set_identity")
        i.b = ["normal", "unwind"]
        self.assertEqual(list_write_error(i, False), "")

    def test_wrong_counts_indexes_and_unencoded_payloads_are_rejected(self):
        for key in ("list.append", "list.set", "list.insert"):
            i = list_write(key)
            i.a.pop()
            with self.subTest(key=key):
                self.assert_rejected(i, "invalid operands or results")
        for wrong in ("float", "bool", "int+"):
            i = list_write("list.set")
            i.a[1].t = wrong
            self.assert_rejected(i, "operand 1 needs int")
        for wrong in ("int", "%slot", "*T", "%ptr"):
            i = list_write()
            i.a[-1].t = wrong
            self.assert_rejected(i, "operand 1 needs *int")

    def test_big_payload_requires_promoting_integer_list_storage(self):
        self.assert_rejected(list_write("list.append_big"), "promoting list[int] storage")
        for element in ("float", "dyn"):
            self.assert_rejected(list_write("list.insert_big", element),
                                 "promoting list[int] storage", promoting=True)
        i = list_write("list.set_big")
        i.a[-1].t = "dyn"
        self.assert_rejected(i, "needs %ptr", promoting=True)

    def test_identity_requires_numeric_kind_and_dynamic_box(self):
        for element, wrong_kind in (("int", "2"), ("float", "1"), ("int", "%a3"), ("dyn", "1")):
            i = list_write("list.append_identity", element)
            i.a[-1].v = wrong_kind
            self.assert_rejected(i, "numeric identity kind")
        i = list_write("list.set_identity")
        i.a[-2].t = "%ptr"
        self.assert_rejected(i, "needs dyn")
        i = list_write("list.insert_identity", "float")
        i.a[-1].t = "bool"
        self.assert_rejected(i, "needs int")

    def test_verifier_rejects_postconstruction_result_and_metadata_corruption(self):
        for field, value in (("t", "int"), ("r", [1]), ("x", "int"), ("k", 1), ("b", ["entry"])):
            i = list_write()
            setattr(i, field, value)
            self.assert_rejected(i, "invalid", builder=False)

    def test_concrete_semantics_retain_the_existing_runtime_abi(self):
        for element in ("int", "float", "str", "dyn"):
            with self.subTest(element=element):
                i = list_write(element=element)
                g = Gen()
                g.runtime(rtsym(i.s))
                g.lower_ins(function_with(i), i)
                self.assertEqual(g.out, ["  call void @pys_list_append(ptr %a0, i64 %a1)"])


class ListWriteEmissionTests(unittest.TestCase):
    def test_real_sources_preserve_receiver_and_payload_types_through_optimization(self):
        function = """def mutate(xs: list[int], n: int):
    xs.append(n)
    xs[0] = n
    xs.insert(0, n)
    print(xs)
mutate([1], 2)
"""
        cases = (("ordinary", function, "list[int]", ""),
                 ("promoting", diagnostics.INTPRAGMA + "\n" + function, "list[int]", "_big"),
                 ("identity", diagnostics.DYNPRAGMA + "\n" + function, "list[int]", "_identity"),
                 ("dynamic", diagnostics.DYNPRAGMA + "\nfrom typing import Any\n" +
                  function.replace("list[int]", "list[Any]"), "list[dyn]", ""))
        lower = Gen.lower
        for name, source, receiver, suffix in cases:
            captured = []

            def capture(g, fn, captured=captured):
                for b in fn.blocks:
                    for i in b.code:
                        if i.op == "rt" and i.s in LIST_WRITES:
                            self.assertEqual(list_write_error(i, diagnostics.int_lists()), "")
                            captured.append((i.s, tuple(a.t for a in i.a)))
                lower(g, fn)

            with self.subTest(policy=name), patch.dict(diagnostics.INTFILES, {}, clear=True), \
                    patch.dict(diagnostics.DYNFILES, {}, clear=True), patch.object(Gen, "lower", capture):
                Gen().program(Loader([]).program(name + ".py", source))
                for method in ("append", "set", "insert"):
                    writes = [types for key, types in captured if key.startswith("list." + method)]
                    self.assertTrue(any(key == "list." + method + suffix for key, _ in captured),
                                    (name, method, captured))
                    self.assertTrue(any(types[0] == receiver for types in writes), (receiver, writes))
                self.assertTrue(any("*" + receiver[5:-1] in types for _, types in captured), captured)


if __name__ == "__main__":
    unittest.main()
