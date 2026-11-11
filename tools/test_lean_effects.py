"""A false or omitted call summary must not hide writes from Lean access checks."""
import copy
import unittest

import check_lean_access as access
import check_lean_effects as effects
from test_lean_access import NegatedComparisonTests, op


def function(symbol, operations, summary="", slots=()):
    return {"name": symbol[1:], "symbol": symbol, "effects": summary, "recursion": {},
            "slots": list(slots), "blocks": [
                {"label": "entry", "handler": "", "operations": operations + [op("ret")]}]}


class EffectSummaryTests(unittest.TestCase):
    def guarded(self, kind, operations, summary="", intermediate=False):
        snapshot = NegatedComparisonTests.snapshot(kind, 0)
        symbol = "@forward" if intermediate else "@mutate"
        snapshot["functions"][0]["blocks"][1]["operations"].insert(
            0, op("call", [("%a0", "list[int]" if kind == "list" else "dict[str,int]")],
                  text=symbol, typ="None"))
        snapshot["functions"].append(function("@mutate", operations, summary))
        if intermediate:
            snapshot["functions"].append(function("@forward", [op("call", text="@mutate", typ="None")]))
        return snapshot

    def assert_verdict(self, snapshot, accepted):
        candidate, metadata = access.normalize_snapshot(snapshot, "@f.guarded")
        self.assertEqual(metadata["unproved"] == 0, accepted)
        self.assertEqual(access.explain(candidate) is None, accepted)
        if access.DEFAULT_CHECKER.is_file():
            self.assertEqual(access.run_checker(access.DEFAULT_CHECKER, access.encode(candidate), metadata), accepted)

    def test_erased_direct_summary_cannot_hide_list_or_dict_mutation(self):
        for kind in ("list", "dict"):
            for intermediate in (False, True):
                with self.subTest(kind=kind, intermediate=intermediate):
                    typ = "list[int]" if kind == "list" else "dict[str,int]"
                    mutation = op("rt", [("%a0", typ)], text=kind + ".clear", typ="None")
                    self.assert_verdict(self.guarded(kind, [mutation], intermediate=intermediate), False)

    def test_pure_body_preserves_guard_and_declared_effects_still_count(self):
        self.assert_verdict(self.guarded("list", []), True)
        self.assert_verdict(self.guarded("list", [], "wL"), False)

    def test_unknown_callback_cannot_hide_behind_empty_summary(self):
        self.assert_verdict(self.guarded("list", [op("icall", typ="None")]), False)
        # A descriptor permitting callbacks invalidates other containers too.
        callback = op("rt", [("%a1", "dict[object,int]"), ("%a2", "object")], [1],
                      text="dict.find", typ="int", descriptor="H1")
        self.assert_verdict(self.guarded("list", [callback]), False)

    def test_mutually_recursive_summaries_reach_a_fixed_point(self):
        snapshot = self.guarded("list", [op("call", text="@cycle", typ="None")])
        snapshot["functions"].append(function("@cycle", [op("call", text="@mutate", typ="None"),
            op("rt", [("%a0", "list[int]")], text="list.clear", typ="None")]))
        found = effects.summaries(snapshot)
        self.assertIn("wL", found["@mutate"])
        self.assertIn("wL", found["@cycle"])
        self.assert_verdict(snapshot, False)

    def test_init_and_missing_callees_are_included(self):
        snapshot = self.guarded("list", [op("init", text="module")])
        snapshot["functions"].append(function("@init.module", [
            op("rt", [("%a0", "list[int]")], text="list.clear", typ="None")]))
        self.assert_verdict(snapshot, False)
        self.assert_verdict(self.guarded("list", [op("call", text="@not_exported", typ="None")]), False)

    def test_memory_roles_and_escaping_slots(self):
        slot = op("slot", results=[1], typ="int", text="local")
        private = function("@private", [op("mem.store", [("%local.1", "*int"), ("1", "int")])], slots=[slot])
        raw = function("@raw", [op("mach.store", [("%a0", "%ptr"), ("1", "int")])])
        field = function("@field", [op("field.addr", [("%a0", "Thing")], [1], typ="*int"),
                                    op("mem.store", [("%t1", "*int"), ("1", "int")])])
        global_ = function("@global", [op("mem.store", [("@saved", "*int"), ("1", "int")])])
        found = effects.summaries({"functions": [private, raw, field, global_]})
        self.assertFalse(found["@private"] & effects.WRITES)
        self.assertEqual(found["@raw"] & effects.WRITES, effects.WRITES)
        self.assertEqual(found["@field"] & effects.WRITES, {"wO"})
        self.assertEqual(found["@global"] & effects.WRITES, {"wG"})
        # An escaped slot is still the function's own stack memory: others may read or write it
        # through its address, but a store to it changes no global, object, list or dict.
        private["blocks"][0]["operations"].insert(0, op("slot.pack", [("%local.1", "*int")], [2], typ="%slot"))
        self.assertFalse(effects.summaries({"functions": [private]})["@private"] & effects.WRITES)
        # Its address passed on lets a callee write anything through that parameter, though.
        writer = function("@writer", [op("mach.store", [("%a0", "%ptr"), ("1", "int")])])
        private["blocks"][0]["operations"].insert(1, op("call", [("%local.1", "*int")], text="@writer", typ="None"))
        found = effects.summaries({"functions": [private, writer]})
        self.assertEqual(found["@private"] & effects.WRITES, effects.WRITES)

    def test_stores_into_memory_the_body_allocates_change_no_prior_state(self):
        # (a closure's cell and environment, as _first in examples/ndarray builds them, and a
        # fixed object's field: new memory on each execution)
        cell = [op("rt", [("8", "int")], [1], text="alloc", typ="%ptr"),
                op("mem.store", [("%t1", "*int"), ("%a0", "int")])]
        environment = [op("rt", [("16", "int")], [2], text="alloc", typ="%ptr"),
                       op("mach.addr", [("%t2", "%ptr"), ("1", "int")], [3], text="%ptr", typ="%ptr"),
                       op("mach.store", [("%t3", "%ptr"), ("null", "%ptr")])]
        obj = [op("alloc.fixed", [], [4], typ="Thing"),
               op("field.addr", [("%t4", "Thing")], [5], typ="*int", immediate=1),
               op("mem.store", [("%t5", "*int"), ("1", "int")])]
        # (a promoting program's closure cell: 23 bytes requested for a 24-byte slot, its identity
        # box in the third word, functions.py)
        identity_cell = [op("rt", [("23", "int")], [8], text="alloc", typ="%ptr"),
                         op("mach.addr", [("%t8", "%ptr"), ("2", "int")], [9], text="%ptr", typ="%ptr"),
                         op("mem.store", [("%t9", "*dyn"), ("null", "dyn")])]
        # (a fixed tuple's last word: lru_cache's _call copies its key into a new tuple)
        pair = [op("alloc.fixed", [], [6], typ="tuple[str,int,int]"),
                op("mach.addr", [("%t6", "%ptr"), ("2", "int")], [7], text="int", typ="%ptr"),
                op("mach.store", [("%t7", "%ptr"), ("1", "int")])]
        for operations in (cell, environment, obj, pair, identity_cell, cell + environment + obj + pair):
            with self.subTest(operations=[o["op"] for o in operations]):
                found = effects.summaries({"functions": [function("@fresh", copy.deepcopy(operations))]})
                self.assertFalse(found["@fresh"] & effects.WRITES)
                self.assert_verdict(self.guarded("list", copy.deepcopy(operations)), True)

    def test_other_derivations_of_fresh_memory_still_write_anything(self):
        alloc = op("rt", [("8", "int")], [1], text="alloc", typ="%ptr")
        bodies = {
            "computed index": [alloc, op("mach.addr", [("%t1", "%ptr"), ("%a0", "int")], [2], text="int", typ="%ptr"),
                               op("mach.store", [("%t2", "%ptr"), ("1", "int")])],
            "index past the end": [alloc, op("mach.addr", [("%t1", "%ptr"), ("1", "int")], [2], text="int", typ="%ptr"),
                                   op("mach.store", [("%t2", "%ptr"), ("1", "int")])],
            # (an allocation of n bytes holds n + 1: a word at byte 2 of 8 ends past them)
            "word at a late byte": [alloc, op("mach.addr", [("%t1", "%ptr"), ("2", "int")], [2], text="%byte",
                                              typ="%ptr"), op("mach.store", [("%t2", "%ptr"), ("1", "int")])],
            "unknown size": [op("rt", [("%a0", "int")], [1], text="alloc", typ="%ptr"),
                             op("mach.store", [("%t1", "%ptr"), ("1", "int")])],
            "join with a parameter": [alloc, op("select", [("%a1", "bool"), ("%t1", "%ptr"), ("%a2", "%ptr")], [2],
                                                typ="%ptr"), op("mach.store", [("%t2", "%ptr"), ("1", "int")])],
            "pointer read from it": [alloc, op("mach.load", [("%t1", "%ptr")], [2], typ="%ptr"),
                                     op("mach.store", [("%t2", "%ptr"), ("1", "int")])],
            "other allocator": [op("rt", [("8", "int")], [1], text="list.new", typ="%ptr"),
                                op("mach.store", [("%t1", "%ptr"), ("1", "int")])],
            "word past a tuple": [op("alloc.fixed", [], [1], typ="tuple[str,int]"),
                                  op("mach.addr", [("%t1", "%ptr"), ("2", "int")], [2], text="int", typ="%ptr"),
                                  op("mach.store", [("%t2", "%ptr"), ("1", "int")])],
            "variadic tuple": [op("alloc.fixed", [], [1], typ="tuple[int,...]"),
                               op("mach.addr", [("%t1", "%ptr"), ("0", "int")], [2], text="int", typ="%ptr"),
                               op("mach.store", [("%t2", "%ptr"), ("1", "int")])],
        }
        for name, operations in bodies.items():
            with self.subTest(name=name):
                found = effects.summaries({"functions": [function("@stale", copy.deepcopy(operations))]})
                self.assertIn("wL", found["@stale"])
                self.assert_verdict(self.guarded("list", copy.deepcopy(operations)), False)
        # (a promoting int's two words need 16 bytes from the address: 15 requested holds them, 8
        # does not, nor does the last word of a 23-byte cell)
        for size, index, fits in (("15", "0", True), ("8", "0", False), ("23", "2", False), ("23", "1", True)):
            with self.subTest(size=size, index=index):
                body = [op("rt", [(size, "int")], [1], text="alloc", typ="%ptr"),
                        op("mach.addr", [("%t1", "%ptr"), (index, "int")], [2], text="%ptr", typ="%ptr"),
                        op("mem.store", [("%t2", "*int+"), ("%a0", "int+")])]
                found = effects.summaries({"functions": [function("@wide", body)]})["@wide"]
                self.assertEqual(found & effects.WRITES, set() if fits else effects.WRITES)
        # (an object's first word is its class tag only for a tagged class)
        header = [op("alloc.fixed", [], [1], typ="Thing"), op("mach.store", [("%t1", "%ptr"), ("2", "int")])]
        for tagged in (True, False):
            with self.subTest(tagged=tagged):
                snapshot = {"functions": [function("@header", copy.deepcopy(header))],
                            "classes": {"Thing": {"base": "", "role": "", "overlaps": [], "tagged": tagged}}}
                found = effects.summaries(snapshot)["@header"]
                self.assertEqual(found & effects.WRITES, set() if tagged else effects.WRITES)
        # (a field of memory that is not a fixed object's stays an object write)
        untyped = [alloc, op("field.addr", [("%t1", "Thing")], [2], typ="*int"),
                   op("mem.store", [("%t2", "*int"), ("1", "int")])]
        self.assertEqual(effects.summaries({"functions": [function("@stale", untyped)]})["@stale"]
                         & effects.WRITES, {"wO"})

    def test_identity_return_stores_are_the_caller_slot_only_where_every_call_passes_one(self):
        returner = function("@returner", [op("mem.store", [("%idret", "*dyn"), ("null", "dyn")])])
        slot = op("slot", results=[1], typ="dyn", text="h")
        for argument, writes in (("%h.1", set()), ("%idret", set()), ("null", set()),
                                 ("%a0", effects.WRITES), ("@g.saved", effects.WRITES)):
            with self.subTest(argument=argument):
                caller = function("@caller", [op("mem.store", [("%h.1", "*dyn"), ("null", "dyn")]),
                                              op("call", [("1", "int"), (argument, "*dyn")], [2],
                                                 text="@returner", typ="int")], slots=[slot])
                found = effects.summaries({"functions": [copy.deepcopy(returner), caller]})
                self.assertEqual(found["@returner"] & effects.WRITES, writes)
                self.assertEqual(found["@caller"] & effects.WRITES, writes)
        # (an argument of another type is no identity-return buffer)
        caller = function("@caller", [op("call", [("1", "int"), ("%h.1", "*int")], [2], text="@returner",
                                         typ="int")], slots=[slot])
        self.assertEqual(effects.summaries({"functions": [copy.deepcopy(returner), caller]})["@returner"]
                         & effects.WRITES, effects.WRITES)

    def test_unknown_store_may_rebind_a_global_before_later_length_test(self):
        snapshot = NegatedComparisonTests.snapshot("list", 0)
        fn = snapshot["functions"][0]
        entry = fn["blocks"][0]["operations"]
        entry[0]["operands"][0]["value"] = "%t30"
        entry[:0] = [op("mem.load", [("@saved", "*list[int]")], [30], typ="list[int]"),
                     op("call", [("%a2", "%ptr")], text="@raw", typ="None")]
        read = fn["blocks"][1]["operations"]
        read[0]["operands"][0]["value"] = "%t31"
        read.insert(0, op("mem.load", [("@saved", "*list[int]")], [31], typ="list[int]"))
        snapshot["functions"].append(function("@raw", [
            op("mach.store", [("%a0", "%ptr"), ("null", "list[int]")])], "wL wD wO"))
        # Clearing list facts at the call is insufficient: the length is read
        # afterwards. The earlier @saved == %t30 relation must be killed too.
        self.assert_verdict(snapshot, False)
        entry[1] = op("mem.store", [("%a2", "*list[int]"), ("null", "list[int]")])
        self.assert_verdict(snapshot, False)

    def test_missing_summary_and_unknown_operations_stay_conservative(self):
        unknown = function("@unknown", [op("future.operation")])
        missing = function("@missing", [])
        del missing["effects"]
        found = effects.summaries({"functions": [unknown, missing]})
        self.assertEqual(found["@unknown"] & effects.WRITES, effects.WRITES)
        self.assertEqual(found["@missing"] & effects.WRITES, effects.WRITES)

    def test_duplicate_callee_symbols_fail_closed(self):
        fn = function("@duplicate", [])
        with self.assertRaisesRegex(ValueError, "duplicate function symbol"):
            effects.summaries({"functions": [fn, copy.deepcopy(fn)]})

    def test_malformed_callee_body_fails_closed(self):
        fn = function("@malformed", [{"op": "call"}])
        with self.assertRaisesRegex(ValueError, "invalid effect instruction"):
            effects.summaries({"functions": [fn]})

    def test_list_store_is_not_reported_as_dictionary_access(self):
        snapshot = NegatedComparisonTests.snapshot("list", 0)
        read = snapshot["functions"][0]["blocks"][1]["operations"][0]
        read.update(op="list.store", type="", results=[50, 51, 52])
        read["operands"].append({"value": "0", "type": "int"})
        _, metadata = access.normalize_snapshot(snapshot, "@f.guarded")
        self.assertEqual((metadata["accesses"], metadata["list_stores"], metadata["dict_entries"]), (1, 1, 0))


if __name__ == "__main__":
    unittest.main()
