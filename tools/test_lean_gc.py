"""Lists, dicts and sets whose arrays the collector does not scan: no pointer-typed use reaches one.

Each refutation corrupts actual compiler IR of examples/gc_arrays.py as a compiler bug could: an
empty list's type hole resolved to a numeric list where its items are strs (#603's shape), the
atomic allocator where items may be pointers, an int key kind for a dict of str keys, a set's key
hole resolved to ints, a function returning an atomic list as a list of strs, an atomic list stored
where memory holds a list of strs, one passed for a parameter that is a list of strs, dicts and
sets that only runtime functions hold made atomic where strs are written into them, an int key
kind for a set or dict.fromkeys keys a list's strs fill, a str stored by list.store into a list of
ints, atomic lists in globals that an open view stores (another view loads them as lists of strs)
or that every view leaves open (their loads assume what their stores hold), an atomic open
template result, a dict of str keys re-kinded to int keys by empty.kind, and a generator of lists
of ints declared to yield lists of strs. Lean must reject each, while the original stays proved.
"""
import copy
import os
from pathlib import Path
import tempfile
import unittest

import check_lean_boundary as boundary
import check_lean_gc as gc
from test_lean_union_effects import inspect

ROOT = Path(__file__).resolve().parent.parent
CHECKER = boundary.DEFAULT_CHECKER


class ArrayKindTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CHECKER.is_file():
            if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1":
                raise RuntimeError("Lean checker required for array kind controls")
            raise unittest.SkipTest("build the Lean boundary checker")
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.snapshot = inspect(ROOT / "tools/lean_boundary/examples/gc_arrays.py", Path(cls.temp.name) / "arrays")

    def sample(self):
        return copy.deepcopy(self.snapshot)

    @staticmethod
    def function(snapshot, symbol):
        return next(fn for fn in snapshot["functions"] if fn["symbol"] == symbol)

    @staticmethod
    def maker(fn, name):
        return next(op for block in fn["blocks"] for op in block["operations"] if op["op"] == "rt" and op["text"] == name)

    def status(self, snapshot, symbol):
        report, _ = gc.check_all(snapshot, CHECKER)
        return next(r["status"] for r in report["records"] if r["function"] == symbol)

    def test_example_proves_every_use(self):
        report, code = gc.check_all(self.sample(), CHECKER)
        self.assertEqual(code, 0, [r for r in report["records"] if r["status"] != "accepted"])
        self.assertEqual(report["proved_obligations"], report["obligations"])
        self.assertGreaterEqual(report["obligations"], 20)

    def test_hole_resolved_to_numbers_for_strs_is_rejected(self):
        snapshot = self.sample()
        hole = self.maker(self.function(snapshot, "@f.labels"), "list.new")["immediate"]
        self.assertEqual(snapshot["holes"][hole], "list[str]")
        snapshot["holes"][hole] = "list[int]"
        self.assertEqual(self.status(snapshot, "@f.labels"), "rejected")

    def test_atomic_allocator_for_pointer_items_is_rejected(self):
        snapshot = self.sample()
        main = self.function(snapshot, "@main.init")
        self.maker(main, "list.new")["text"] = "list.new_atomic"
        self.assertEqual(self.status(snapshot, "@main.init"), "rejected")

    def test_int_key_kind_for_str_keys_is_rejected(self):
        snapshot = self.sample()
        made = self.maker(self.function(snapshot, "@f.counts"), "dict.new_atomic")
        self.assertEqual(made["operands"][0]["value"], "1")
        made["operands"][0]["value"] = "0"
        self.assertEqual(self.status(snapshot, "@f.counts"), "rejected")

    def test_set_key_hole_resolved_to_ints_for_tuples_is_rejected(self):
        snapshot = self.sample()
        hole = self.maker(self.function(snapshot, "@f.pairs"), "set.new")["immediate"]
        snapshot["holes"][hole] = "set[int]"
        self.assertEqual(self.status(snapshot, "@f.pairs"), "rejected")

    def test_atomic_result_declared_pointer_list_is_rejected(self):
        snapshot = self.sample()
        self.function(snapshot, "@f.numbers")["return_representation"] = "list[str]"
        self.assertEqual(self.status(snapshot, "@f.numbers"), "rejected")

    def test_atomic_list_stored_in_pointer_list_memory_is_rejected(self):
        snapshot = self.sample()
        main = self.function(snapshot, "@main.init")
        store = next(op for block in main["blocks"] for op in block["operations"]
                     if op["op"] == "mem.store" and op["operands"][0]["value"] == "@g.squares")
        store["operands"][0]["type"] = "*list[str]"
        self.assertEqual(self.status(snapshot, "@main.init"), "rejected")

    def test_atomic_argument_for_pointer_list_parameter_is_rejected(self):
        # (the caller's view agrees with what it passes; the callee's declared parameter does not)
        snapshot = self.sample()
        main = self.function(snapshot, "@main.init")
        call = next(op for block in main["blocks"] for op in block["operations"]
                    if op["op"] == "call" and op["text"] == "@f.counts")
        squares = next(op for block in main["blocks"] for op in block["operations"]
                       if op["op"] == "call" and op["text"] == "@f.numbers")
        call["operands"][0] = {"value": f"%t{squares['results'][0]}", "type": "list[int]"}
        self.assertEqual(self.status(snapshot, "@main.init"), "rejected")

    def test_runtime_held_dict_with_numeric_hole_is_rejected(self):
        # (only dict.set and len hold it: its item writes are checked, not a typed use)
        for resolved in ("dict[str,int]", "dict[int,str]"):
            snapshot = self.sample()
            hole = self.maker(self.function(snapshot, "@f.distinct"), "dict.new")["immediate"]
            self.assertEqual(snapshot["holes"][hole], "dict[str,str]")
            snapshot["holes"][hole] = resolved
            self.assertEqual(self.status(snapshot, "@f.distinct"), "rejected", resolved)

    def test_runtime_held_set_with_numeric_hole_is_rejected(self):
        snapshot = self.sample()
        made = next(op for block in self.function(snapshot, "@f.distinct")["blocks"] for op in block["operations"]
                    if op["op"] == "rt" and op["text"] == "set.new" and op["immediate"] > 0)
        self.assertEqual(snapshot["holes"][made["immediate"]], "set[str]")
        snapshot["holes"][made["immediate"]] = "set[int]"
        self.assertEqual(self.status(snapshot, "@f.distinct"), "rejected")

    def test_int_key_kind_for_set_of_listed_strs_is_rejected(self):
        # (set(words): set.update_list writes the list's strs, whatever the set's views say)
        snapshot = self.sample()
        made = next(op for block in self.function(snapshot, "@f.distinct")["blocks"] for op in block["operations"]
                    if op["op"] == "rt" and op["text"] == "set.new" and op["immediate"] == 0)
        self.assertEqual(made["operands"][0]["value"], "1")
        made["operands"][0]["value"] = "0"
        self.assertEqual(self.status(snapshot, "@f.distinct"), "rejected")

    def test_int_key_kind_for_keys_of_listed_strs_is_rejected(self):
        # (dict.fromkeys(words, 0): the new dict's keys are the list's strs)
        snapshot = self.sample()
        made = self.maker(self.function(snapshot, "@f.distinct"), "dict.fromkeys")
        self.assertEqual(made["operands"][0]["value"], "1")
        made["operands"][0]["value"] = "0"
        self.assertEqual(self.status(snapshot, "@f.distinct"), "rejected")

    @staticmethod
    def accesses(snapshot, address):
        return [op for fn in snapshot["functions"] for block in fn["blocks"] for op in block["operations"]
                if op["op"] in ("mem.load", "mem.store") and op["operands"][0]["value"] == address]

    def stored_list(self, snapshot, address):
        store = next(op for op in self.accesses(snapshot, address) if op["op"] == "mem.store")
        main = self.function(snapshot, "@main.init")
        return next(op for block in main["blocks"] for op in block["operations"]
                    if f"%t{op['results'][0] if op['results'] else -1}" == store["operands"][1]["value"])

    def test_atomic_list_stored_by_an_open_view_is_rejected(self):
        # (queue's store views it as list[?], a later load as list[str]: a store holds for every view)
        snapshot = self.sample()
        self.assertEqual({op["operands"][0]["type"] for op in self.accesses(snapshot, "@g.queue")}, {"*list[?]", "*list[str]"})
        made = self.stored_list(snapshot, "@g.queue")
        self.assertEqual(snapshot["holes"][made["immediate"]], "list[str]")
        snapshot["holes"][made["immediate"]] = "list[int]"
        report, _ = gc.check_all(snapshot, CHECKER)
        record = next(r for r in report["records"] if r["function"] == "@main.init")
        self.assertEqual(record["status"], "rejected")
        self.assertIn("mem.store at", record["error"])
        self.assertIn(f"%t{made['results'][0]} in", record["error"])

    def test_atomic_open_result_is_rejected(self):
        # (fresh() returns list[?], which its caller types as a list of strs: open items are scanned)
        snapshot = self.sample()
        fresh = next(fn for fn in snapshot["functions"] if fn["symbol"].startswith("@f.fresh"))
        self.assertEqual(fresh["return_representation"], "list[?]")
        made = self.maker(fresh, "list.new")
        snapshot["holes"][made["immediate"]] = "list[int]"
        self.assertEqual(self.status(snapshot, fresh["symbol"]), "rejected")

    def test_dict_rekinded_to_int_keys_is_rejected(self):
        # (an empty.kind storing int keys' kind into the dict of str keys counts() fills: its next key
        # table is atomic, whatever table it has)
        snapshot = self.sample()
        counts = self.function(snapshot, "@f.counts")
        made = self.maker(counts, "dict.new_atomic")
        block = next(block for block in counts["blocks"] if made in block["operations"])
        fresh = max(n for block in counts["blocks"] for op in block["operations"] for n in op["results"]) + 1
        block["operations"].insert(block["operations"].index(made) + 1, {
            "op": "empty.kind", "text": "", "type": "", "immediate": 0, "descriptor": "", "results": [fresh],
            "targets": [], "operands": [{"value": f"%t{made['results'][0]}", "type": "dict[int,int]"}]})
        self.assertEqual(self.status(snapshot, "@f.counts"), "rejected")

    def test_open_global_holds_what_its_stores_hold(self):
        # (every view of spare made open, as the compiler leaves some globals: its loads assume what
        # its stores are checked to hold)
        snapshot = self.sample()
        for op in self.accesses(snapshot, "@g.spare"):
            op["operands"][0]["type"] = "*list[?]"
            if op["op"] == "mem.load":
                op["type"] = "list[?]"
        self.assertEqual(self.status(copy.deepcopy(snapshot), "@main.init"), "accepted")
        made = self.stored_list(snapshot, "@g.spare")
        snapshot["holes"][made["immediate"]] = "list[int]"
        self.assertEqual(self.status(snapshot, "@main.init"), "rejected")

    def test_str_item_stored_into_list_of_ints_is_rejected(self):
        # (out[i] = ... as list.store: a word the IR types as a str written into a list of ints,
        # whose array may be atomic: the item write is checked whatever the list's view says)
        snapshot = self.sample()
        bumped = self.function(snapshot, "@f.bumped")
        store = next(op for block in bumped["blocks"] for op in block["operations"] if op["op"] == "list.store")
        self.assertEqual([a["type"] for a in store["operands"]], ["list[int]", "int", "*int"])
        store["operands"][2]["type"] = "*str"
        self.assertEqual(self.status(snapshot, "@f.bumped"), "rejected")

    def test_generator_yielding_atomic_lists_as_strs_is_rejected(self):
        # (rows() yields copies of a list of ints, atomic: declared to yield lists of strs, its
        # consumers would keep strs in them. Each suspension is checked by the yield type)
        snapshot = self.sample()
        rows = next(fn for fn in snapshot["functions"] if fn["symbol"].startswith("@f.rows"))
        self.assertEqual(rows["return_representation"], "gen[list[int]]")
        self.assertTrue(any(op["op"] == "gen.yield" for block in rows["blocks"] for op in block["operations"]))
        self.assertEqual(self.status(copy.deepcopy(snapshot), rows["symbol"]), "accepted")
        rows["return_representation"] = "gen[list[str]]"
        self.assertEqual(self.status(snapshot, rows["symbol"]), "rejected")

    def test_missing_holes_fail_closed(self):
        snapshot = self.sample()
        del snapshot["holes"]
        with self.assertRaisesRegex(ValueError, "type holes missing"):
            gc.check_all(snapshot, CHECKER)


if __name__ == "__main__":
    unittest.main()
