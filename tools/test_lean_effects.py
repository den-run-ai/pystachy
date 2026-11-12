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
        private["blocks"][0]["operations"].insert(0, op("slot.pack", [("%local.1", "*int")], [2], typ="%slot"))
        self.assertEqual(effects.summaries({"functions": [private]})["@private"] & effects.WRITES,
                         effects.WRITES)

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
