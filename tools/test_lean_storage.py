"""Negative controls for the storage adapter and its executable Lean certificate check."""
from __future__ import annotations

import copy
import os
import unittest

import check_lean_boundary as boundary
import check_lean_storage as storage


def ins(op, typ="", operands=(), result=None, text="", targets=(), immediate=0):
    return {"op": op, "type": typ, "text": text, "immediate": immediate, "descriptor": "",
            "results": [] if result is None else [result],
            "operands": [{"value": value, "type": kind} for value, kind in operands],
            "targets": list(targets)}


def block(label, *operations, handler=""):
    return {"label": label, "handler": handler, "operations": list(operations)}


def function(blocks, parameters=("int+", "int+")):
    return {"symbol": "@test", "name": "test", "parameters": [
        {"name": f"a{i}", "type": typ, "representation": typ} for i, typ in enumerate(parameters)],
        "slots": [], "check_targets": {}, "blocks": blocks,
        "representation_metadata": {"version": 1, "int_containers": True,
            "scope": "definition and container-read representations; not physical allocation extents",
            "sources": [{"value": f"%a{i}", "representation": typ, "origin": "parameter"}
                        for i, typ in enumerate(parameters) if typ.startswith("tuple[")]}}


def guarded_low(used="%a0"):
    return function([
        block("entry", ins("big.hi", "%ptr", [("%a0", "int+")], 1),
              ins("ptr.cmp", "bool", [("%t1", "%ptr"), ("null", "%ptr")], 2, "eq"),
              ins("cbr", operands=[("%t2", "bool")], targets=["yes", "no"])),
        block("yes", ins("big.lo", "int", [(used, "int+")], 3),
              ins("ret", operands=[("%t3", "int")])),
        block("no", ins("ret", operands=[("0", "int")])),
    ])


if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1" and not storage.DEFAULT_CHECKER.is_file():
    raise RuntimeError("Lean storage checks require the built boundary executable")


@unittest.skipUnless(storage.DEFAULT_CHECKER.is_file(), "build the Lean checker")
class StorageGuardTests(unittest.TestCase):
    def accepted(self, fn):
        candidate, metadata = storage.Normalize(fn).build()
        self.assertGreater(metadata["obligations"], 0, "control must exercise an obligation")
        return boundary.run_checker(storage.DEFAULT_CHECKER, boundary.encode(candidate), metadata)

    def test_fit_guard_must_test_the_used_value(self):
        self.assertTrue(self.accepted(guarded_low()))
        self.assertFalse(self.accepted(guarded_low("%a1")))

    def test_bypassed_fit_guard_is_rejected(self):
        fn = guarded_low()
        fn["blocks"][0]["operations"][-1]["operands"][0]["value"] = "true"
        self.assertFalse(self.accepted(fn))

    def test_exception_handler_cannot_bypass_fit_guard(self):
        fn = guarded_low()
        fn["blocks"][0]["handler"] = "yes"
        fn["blocks"][0]["operations"].insert(0,
            ins("rt", "void", [("0", "int")], text="print.int"))
        self.assertFalse(self.accepted(fn))

    def test_empty_handler_does_not_reach_an_unnamed_dead_block(self):
        fn = guarded_low()
        fn["blocks"][0]["operations"].insert(0,
            ins("rt", "void", [("0", "int")], text="print.int"))
        # The exporter preserves an unlabeled unreachable LLVM block after a
        # terminator. Empty handler means no handler, not an edge to this block.
        fn["blocks"].append(block("", ins("br", targets=["yes"])))
        self.assertTrue(self.accepted(fn))
        fn["blocks"][0]["operations"][-1]["targets"][0] = ""
        with self.assertRaisesRegex(ValueError, "unknown control-flow target"):
            storage.Normalize(fn).build()

    def test_guard_temporary_must_dominate_its_use(self):
        fn = guarded_low()
        test = fn["blocks"][0]["operations"].pop(0)
        fn["blocks"][1]["operations"].insert(0, test)
        with self.assertRaisesRegex(ValueError, "does not dominate"):
            storage.Normalize(fn).build()

    def test_low_word_cannot_disappear_through_integer_phi(self):
        fn = function([
            block("entry", ins("big.lo", "int", [("%a0", "int+")], 1),
                  ins("br", targets=["join"])),
            block("join", ins("phi", "int", [("%t1", "int")], 2, targets=["entry"]),
                  ins("ret", operands=[("%t2", "int")])),
        ])
        self.assertFalse(self.accepted(fn))

    def test_two_null_select_arms_do_not_prove_reconstruction(self):
        fn = function([block("entry",
            ins("big.lo", "int", [("%a0", "int+")], 1),
            ins("select", "%ptr", [("true", "bool"), ("null", "%ptr"), ("null", "%ptr")], 2),
            ins("big.make", "int+", [("%t1", "int"), ("%t2", "%ptr")], 3),
            ins("ret", operands=[("%t3", "int+")]))])
        self.assertFalse(self.accepted(fn))

    def test_speculative_total_comparison_can_be_masked_by_fit(self):
        fn = function([block("entry",
            ins("big.hi", "%ptr", [("%a0", "int+")], 1),
            ins("ptr.cmp", "bool", [("%t1", "%ptr"), ("null", "%ptr")], 2, "eq"),
            ins("big.lo", "int", [("%a0", "int+")], 3),
            ins("scalar.cmp", "bool", [("%t3", "int"), ("0", "int")], 4, "sge"),
            ins("scalar.bin", "bool", [("%t2", "bool"), ("%t4", "bool")], 5, "and"),
            ins("ret", operands=[("%t5", "bool")]))])
        self.assertTrue(self.accepted(fn))
        bad = copy.deepcopy(fn)
        bad["blocks"][0]["operations"][3]["operands"][0]["value"] = "%other"
        # Use another promoting value's low word while retaining the first fit guard.
        bad["blocks"][0]["operations"].insert(3, ins("big.lo", "int", [("%a1", "int+")], 6))
        bad["blocks"][0]["operations"][4]["operands"][0]["value"] = "%t6"
        self.assertFalse(self.accepted(bad))

    def test_potentially_trapping_operation_is_not_speculative(self):
        fn = function([block("entry",
            ins("big.lo", "int", [("%a0", "int+")], 1),
            ins("scalar.bin", "int", [("1", "int"), ("%t1", "int")], 2, "sdiv"),
            ins("select", "int", [("false", "bool"), ("%t2", "int"), ("0", "int")], 3),
            ins("ret", operands=[("%t3", "int")]))])
        self.assertFalse(self.accepted(fn))

    def test_tuple_write_invalidates_marker_fact(self):
        typ = "tuple[int+]"
        fn = function([
            block("entry", ins("alloc.fixed", typ, result=10),
                  ins("tuple.load", "int", [("%t10", typ)], 1, "int", immediate=0),
                  ins("scalar.cmp", "bool", [("%t1", "int"), (storage.MIN, "int")], 2, "eq"),
                  ins("cbr", operands=[("%t2", "bool")], targets=["yes", "no"])),
            block("yes", ins("tuple.load", "int", [("%t10", typ)], 3, "int", immediate=1),
                  ins("ret", operands=[("0", "int")])),
            block("no", ins("ret", operands=[("0", "int")])),
        ], parameters=(typ,))
        self.assertTrue(self.accepted(fn))
        fn["blocks"][1]["operations"].insert(0,
            ins("tuple.store", operands=[("%t10", typ), ("0", "int")], text="int", immediate=0))
        self.assertFalse(self.accepted(fn))

    def test_kwargs_parameter_views_preserve_integer_widths(self):
        for source, target in (("kw[x:int]", "tuple[int+]"), ("kw[x:int+]", "tuple[int]"),
                               ("kw[x:tuple[int,int+]]", "tuple[tuple[int+,int]]")):
            with self.subTest(source=source, target=target):
                fn = function([block("entry", ins("ret", operands=[("%a0", target)]))], (source,))
                self.assertFalse(self.accepted(fn))


class StorageSchemaTests(unittest.TestCase):
    def test_kwargs_read_layout_preserves_order_and_nested_types(self):
        typ = "kw[plain:int,nested:tuple[int+,int],large:int+]"
        fn = function([block("entry", ins("mem.load", typ, [("%a1", "*" + typ)], 1),
                             ins("slot.pack", "%slot", [("%t1", typ)], 2),
                             ins("slot.unpack", "tuple[int+,int+,int+]", [("%t2", "%slot")], 3),
                             ins("ret.none"))], (typ, "*" + typ))
        normalized = storage.Normalize(fn)
        for value in ("%a0", "%t1", "%t2", "%t3"):
            self.assertEqual(normalized.layout_type(value), "tuple[int,tuple[int+,int],int+]")

    def test_kwargs_join_and_call_results_remain_unsupported(self):
        typ = "kw[x:int+]"
        for producer in (
            ins("phi", typ, [("%a0", typ)], 1, targets=["entry"]),
            ins("select", typ, [("true", "bool"), ("%a0", typ), ("%a0", typ)], 1),
            ins("call", typ, [("@callee", "fn")], 1),
        ):
            with self.subTest(producer=producer["op"]):
                fn = function([block("entry", ins("br", targets=["join"])),
                               block("join", producer, ins("ret", operands=[("%t1", "tuple[int+]")]))],
                              (typ,))
                with self.assertRaisesRegex(storage.Unsupported, "unknown source representation"):
                    storage.Normalize(fn).build()

    def test_tuple_store_through_parameter_is_outside_fresh_construction(self):
        fn = function([block("entry",
            ins("tuple.store", operands=[("%a0", "tuple[int+]"), ("0", "int")], immediate=0),
            ins("ret.none"))], parameters=("tuple[int+]",))
        with self.assertRaises(storage.Unsupported):
            storage.Normalize(fn).build()

    def test_missing_layout_metadata_fails_closed(self):
        fn = guarded_low()
        del fn["representation_metadata"]
        with self.assertRaises((ValueError, storage.Unsupported)):
            storage.Normalize(fn).build()

    def test_unknown_operation_fails_closed(self):
        fn = guarded_low()
        fn["blocks"][1]["operations"].insert(0, ins("new.unknown.effect"))
        with self.assertRaises((ValueError, storage.Unsupported)):
            storage.Normalize(fn).build()


if __name__ == "__main__":
    unittest.main()
