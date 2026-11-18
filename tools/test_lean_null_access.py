"""Removed null checks proved through memory in the Lean access model.

The nullcheck pass removes a check where an equal value passed a null test on every path
(Gen.canon follows loads of fields and globals across writes it deems unrelated). These
tests compile tools/lean_boundary/examples/null_reloads.py and corrupt the pass's input
graph: each corruption makes a removed check fallible, and Lean must then reject it in both
of its models.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import check_lean_access as access
import check_lean_boundary as boundary
import check_lean_guards as guards
from check_lean_effects import summaries

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "tools/lean_boundary/examples/null_reloads.py"
CHECKERS = (boundary.DEFAULT_CHECKER, access.DEFAULT_CHECKER)

if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1" and not all(path.is_file() for path in CHECKERS):
    raise RuntimeError("Lean checkers are required; build tools/lean_boundary first")


def op(kind, operands=(), results=(), text="", typ="", targets=(), immediate=0, descriptor=""):
    return {"op": kind, "type": typ, "text": text, "immediate": immediate, "descriptor": descriptor,
            "results": list(results), "operands": [{"value": value, "type": kind_} for value, kind_ in operands],
            "targets": list(targets)}


class NullAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        output = Path(temporary.name) / "inspection"
        env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
        env["PYSTACHY_HOME"] = str(ROOT)
        result = subprocess.run([sys.executable, str(ROOT / "tools/inspect_compiler.py"), str(EXAMPLE),
                                 "--output", str(output), "--typed-after-only", "--guard-evidence"],
                                cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.snapshot = json.loads((output / "typed-after.json").read_text())

    def setUp(self):
        if not all(path.is_file() for path in CHECKERS):
            self.skipTest("Lean checkers not built")
        self.snap = copy.deepcopy(self.snapshot)
        self.effects = summaries(self.snap)

    def record(self, name):
        found = [r for r in self.snap["nullcheck_evidence"]
                 if name in (r["before"]["name"], r["before"]["symbol"]) and guards.removed_checks(r)]
        self.assertEqual(len(found), 1, name)
        return found[0]

    def prove(self, fn, removed):
        return guards.prove_removals(self.snap, fn, removed, self.effects, *CHECKERS)

    @staticmethod
    def block(fn, label):
        return next(block for block in fn["blocks"] if block["label"] == label)

    @staticmethod
    def check_site(fn, message):
        # (the block and position of the check that raises message)
        for block in fn["blocks"]:
            last = block["operations"][-1]
            if last["op"] == "check" and (last["descriptor"] or last["text"]) == message:
                yield block["label"], len(block["operations"]) - 1

    def insert(self, fn, removed, label, position, operations):
        """Insert operations into a block, renumbering the removed checks after them."""
        block = self.block(fn, label)
        block["operations"][position:position] = operations
        return [(site, offset + len(operations) if site == label and offset >= position else offset)
                for site, offset in removed]

    def field_case(self):
        record = self.record("field_reload")
        fn = copy.deepcopy(record["before"])
        removed = guards.removed_checks(record)
        # The test of h.inner (L6's cbr) guards the reloads of h.inner after it.
        tested = next(op_ for op_ in self.block(fn, "L6")["operations"] if op_["op"] == "field.addr")
        return fn, removed, tested

    def assert_proved(self, fn, removed, model="access"):
        result = self.prove(fn, removed)
        self.assertEqual(result["status"], "accepted", result)
        self.assertEqual(result["model"], model)
        self.assertEqual(result["obligations"], len(removed))

    def assert_refuted(self, fn, removed):
        result = self.prove(fn, removed)
        self.assertNotEqual(result["status"], "accepted", result)
        self.assertEqual([attempt["model"] for attempt in result["attempts"]], ["access", "finite-tag"])
        self.assertEqual(result["attempts"][0]["status"], "rejected", result)
        return result

    def test_actual_removals_prove_through_fields_and_globals(self):
        for name, count in (("field_reload", 4), ("field_reload_other_field", 5), ("global_reload", 2),
                            ("@c.0.1", 1), ("through_own_cell", 4)):
            with self.subTest(name=name):
                record = self.record(name)
                removed = guards.removed_checks(record)
                self.assertEqual(len(removed), count)
                self.assert_proved(record["before"], removed)

    def test_finite_tag_model_alone_misses_field_correlation(self):
        # (the gap this route closes: the tag model has no field or global cells)
        record = self.record("field_reload")
        candidate, meta = guards.normalize(self.snap, record["before"], guards.removed_checks(record))
        self.assertFalse(boundary.run_checker(CHECKERS[0], boundary.encode(candidate), meta))

    def test_a_null_store_to_the_tested_field_refutes(self):
        fn, removed, tested = self.field_case()
        address = dict(tested, results=[9001])
        removed = self.insert(fn, removed, "L12", 0, [address, op("mem.store", [("%t9001", tested["type"]),
                                                                                ("null", "Inner")])])
        self.assert_refuted(fn, removed)

    def test_a_write_of_the_same_field_of_another_object_refutes(self):
        fn, removed, tested = self.field_case()
        other = op("rt", [("4", "int")], [9000], text="box", typ=tested["operands"][0]["type"])
        address = dict(tested, results=[9001], operands=[{"value": "%t9000", "type": tested["operands"][0]["type"]}])
        removed = self.insert(fn, removed, "L12", 0, [other, address, op("mem.store", [("%t9001", tested["type"]),
                                                                                       ("null", "Inner")])])
        self.assert_refuted(fn, removed)

    def other_class_write(self):
        # (a write of an Inner field through the register that holds the Holder)
        fn, removed, tested = self.field_case()
        address = dict(tested, results=[9001], immediate=tested["immediate"],
                       operands=[{"value": tested["operands"][0]["value"], "type": "Inner"}])
        removed = self.insert(fn, removed, "L12", 0, [address, op("mem.store", [("%t9001", "*Inner"),
                                                                                ("null", "Inner")])])
        return fn, removed

    def test_a_write_of_an_unrelated_class_keeps_the_proof(self):
        # (no object is both an Inner and a Holder: the classes table relates neither to the other)
        self.assertEqual(self.snap["classes"]["Inner"], {"base": "", "role": "", "overlaps": [], "tagged": False})
        self.assert_proved(*self.other_class_write())

    def test_a_write_through_a_related_or_unknown_class_view_refutes(self):
        # (a base and a derived class, or a secondary base, may view one object; a class the
        # table lacks may be anything)
        for relate in ("base", "derived", "role", "overlap", "missing", "no table"):
            with self.subTest(relate=relate):
                self.setUp()
                classes = self.snap["classes"]
                if relate == "base":
                    classes["Inner"]["base"] = "Holder"
                elif relate == "derived":
                    classes["Holder"]["base"] = "Inner"
                elif relate == "role":
                    classes["Holder"]["role"] = "Inner"
                elif relate == "overlap":
                    classes["Holder"]["overlaps"] = ["Inner"]
                elif relate == "missing":
                    del classes["Inner"]
                else:
                    del self.snap["classes"]
                self.assert_refuted(*self.other_class_write())

    def test_lean_rejects_a_write_that_lists_its_own_class(self):
        # (the semantics keeps the fields of each listed class: listing the written class would
        # leave the write no transition, accepted_write_progress)
        fn, removed = self.other_class_write()
        nodes, meta = access.normalize_program(self.snap, fn["symbol"], self.effects, derefs=removed, record=fn)
        candidate, meta = access.certify(nodes, meta)
        self.assertTrue(access.run_checker(access.DEFAULT_CHECKER, access.encode(candidate), meta))
        writes = [node for node in candidate["program"]["nodes"] if node["op"] == "write_field"]
        self.assertTrue(writes and all(node["class"] == "Inner" and "Holder" in node["unrelated"] for node in writes))
        for node in writes:
            node["unrelated"] = node["unrelated"] + [node["class"]]
        self.assertFalse(access.run_checker(access.DEFAULT_CHECKER, access.encode(candidate), meta))

    def test_a_write_of_another_field_of_the_class_keeps_the_proof(self):
        fn, removed, tested = self.field_case()
        other_index = 1 - tested["immediate"]
        address = dict(tested, results=[9001], type="*int", immediate=other_index)
        removed = self.insert(fn, removed, "L12", 0, [address, op("mem.store", [("%t9001", "*int"), ("7", "int")])])
        self.assert_proved(fn, removed)

    def test_calls_that_may_write_objects_refute(self):
        for callee in ("@m.Holder.__init__", "@f.unknown_elsewhere"):
            with self.subTest(callee=callee):
                fn, removed, tested = self.field_case()
                receiver = tested["operands"][0]["value"]
                call = op("call", [(receiver, "Holder"), ("null", "Inner")], text=callee, typ="None")
                removed = self.insert(fn, removed, "L12", 0, [call])
                self.assert_refuted(fn, removed)

    def test_raw_machine_and_unknown_stores_refute(self):
        for store in (op("mach.store", [("%t9000", "%ptr"), ("0", "int")], text=""),
                      op("mem.store", [("%t9000", "*Inner"), ("null", "Inner")])):
            with self.subTest(store=store["op"]):
                fn, removed, _ = self.field_case()
                pointer = op("rt", [("4", "int")], [9000], text="box", typ="%ptr")
                removed = self.insert(fn, removed, "L12", 0, [pointer, store])
                self.assert_refuted(fn, removed)

    def test_a_store_to_an_escaped_slot_of_the_function_keeps_the_proof(self):
        # (an identity-return buffer's shape: the slot's address leaves through an operand, but a
        # store to it is a store to the function's own stack memory)
        fn, removed, _ = self.field_case()
        fn["slots"].append(op("slot", results=[9010], typ="dyn", text="h"))
        removed = self.insert(fn, removed, "L12", 0, [op("slot.pack", [("%h.9010", "*dyn")], [9011], typ="%slot"),
                                                      op("mem.store", [("%h.9010", "*dyn"), ("null", "dyn")])])
        self.assert_proved(fn, removed)

    def test_reversing_the_null_test_refutes(self):
        fn, removed, _ = self.field_case()
        branch = self.block(fn, "L6")["operations"][-1]
        branch["targets"].reverse()
        self.assert_refuted(fn, removed)

    def test_an_exception_edge_around_the_test_refutes(self):
        # (a landing block reached from the entry, before the test, that continues to the reload)
        fn, removed, _ = self.field_case()
        fn["blocks"][0]["handler"] = "L12"
        self.assert_refuted(fn, removed)

    def test_an_escaped_parameter_slot_refutes(self):
        fn, removed, _ = self.field_case()
        slot = next(op_["operands"][0]["value"] for op_ in fn["blocks"][0]["operations"] if op_["op"] == "mem.store")
        removed = self.insert(fn, removed, "L12", 0, [op("call", [(slot, "*Holder")], text="@f.unknown_elsewhere",
                                                         typ="None")])
        self.assert_refuted(fn, removed)

    def global_case(self):
        record = self.record("global_reload")
        return copy.deepcopy(record["before"]), guards.removed_checks(record)

    def test_global_writes_between_refute(self):
        writes = (
            [op("mem.store", [("@g.current", "*Inner"), ("null", "Inner")])],
            [op("init", text="collections")],
            [op("call", text="@f.unknown_elsewhere", typ="None")],
            [op("rt", [("4", "int")], [9000], text="box", typ="%ptr"),
             op("mem.store", [("%t9000", "*Inner"), ("null", "Inner")])],
        )
        for operations in writes:
            with self.subTest(write=operations[-1]["op"]):
                fn, removed = self.global_case()
                removed = self.insert(fn, removed, "L10", 0, copy.deepcopy(operations))
                self.assert_refuted(fn, removed)

    def test_a_store_into_memory_the_function_allocated_keeps_the_global(self):
        # (a new object's class tag, as gen_new_obj writes it: no global changes where the class's
        # objects begin with the tag; of another class, the word may not be the object's, and an
        # unknown pointer's store refutes too, test_global_writes_between_refute)
        for tagged in (True, False):
            with self.subTest(tagged=tagged):
                self.setUp()
                self.snap["classes"]["Inner"]["tagged"] = tagged
                fn, removed = self.global_case()
                removed = self.insert(fn, removed, "L10", 0, [op("alloc.fixed", [], [9000], typ="Inner"),
                                                              op("mach.store", [("%t9000", "%ptr"), ("2", "int")])])
                if tagged:
                    self.assert_proved(fn, removed)
                else:
                    self.assert_refuted(fn, removed)

    def test_a_store_to_another_global_keeps_the_proof(self):
        fn, removed = self.global_case()
        removed = self.insert(fn, removed, "L10", 0, [op("mem.store", [("@g.log", "*list[str]"), ("null", "list[str]")])])
        self.assert_proved(fn, removed)

    def test_closure_cell_writes_between_reads_refute(self):
        # (the lambda reloads `inner` from its closure cell; a write through the cell, or a call
        # that may run code assigning it, makes the reload unknown)
        for write in ("store", "icall", "call"):
            with self.subTest(write=write):
                record = self.record("@c.0.1")
                fn = copy.deepcopy(record["before"])
                removed = guards.removed_checks(record)
                (label, offset), = removed
                reload = self.block(fn, label)["operations"][0]
                self.assertEqual(reload["op"], "mem.load")
                cell = reload["operands"][0]["value"]
                inserted = {"store": op("mem.store", [(cell, "*Inner"), ("null", "Inner")]),
                            "icall": op("icall", typ="None"),
                            "call": op("call", text="@f.unknown_elsewhere", typ="None")}[write]
                removed = self.insert(fn, removed, label, 0, [inserted])
                self.assert_refuted(fn, removed)

    def test_own_cell_writes_between_reads_refute(self):
        # (through_own_cell reloads `h` from the cell it shares with `peek`: a store to the cell,
        # through its environment or an unknown pointer, or a call that may run `peek`'s writer,
        # makes the reload unknown; a write of a known class's field leaves the cell alone)
        record = self.record("through_own_cell")
        entry = record["before"]["blocks"][0]["operations"]
        cell = entry[0]["results"][0]
        self.assertEqual((entry[0]["op"], entry[0]["text"]), ("rt", "alloc"))
        environment_slot = next(o for o in entry if o["op"] == "mach.addr")["results"][0]
        for write in ("cell", "environment", "unknown", "icall", "call"):
            with self.subTest(write=write):
                fn = copy.deepcopy(record["before"])
                removed = guards.removed_checks(record)
                inserted = {
                    "cell": [op("mem.store", [(f"%t{cell}", "*Holder"), ("null", "Holder")])],
                    "environment": [op("mach.load", [(f"%t{environment_slot}", "%ptr")], [9020], typ="%ptr"),
                                    op("mem.store", [("%t9020", "*Holder"), ("null", "Holder")])],
                    "unknown": [op("rt", [("4", "int")], [9020], text="box", typ="%ptr"),
                                op("mach.store", [("%t9020", "%ptr"), ("0", "int")])],
                    "icall": [op("icall", typ="None")],
                    "call": [op("call", text="@f.unknown_elsewhere", typ="None")]}[write]
                removed = self.insert(fn, removed, "L15", 0, inserted)
                self.assert_refuted(fn, removed)
        fn = copy.deepcopy(record["before"])
        removed = guards.removed_checks(record)
        address = op("field.addr", [("%a0", "Inner")], [9030], typ="*int", immediate=0)
        removed = self.insert(fn, removed, "L15", 0, [address, op("mem.store", [("%t9030", "*int"), ("7", "int")])])
        self.assert_proved(fn, removed)

    @staticmethod
    def function_record(symbol, operations):
        return {"name": symbol[1:], "symbol": symbol, "effects": "", "recursion": {}, "parameters": [],
                "check_targets": {}, "slots": [],
                "blocks": [{"label": "entry", "handler": "", "operations": operations + [op("ret")]}]}

    def identity_case(self, argument, callee, snapshot_call=None):
        # (@f.null_idret stores null through %idret, the buffer its caller passes last;
        # @f.forward_idret passes its own on. The pass input calls one of them before the reload)
        self.snap["functions"] += [
            self.function_record("@f.null_idret", [op("mem.store", [("%idret", "*dyn"), ("null", "dyn")])]),
            self.function_record("@f.forward_idret", [op("call", [("1", "int"), ("%idret", "*dyn")], [900],
                                                         text="@f.null_idret", typ="int")])]
        if snapshot_call is not None:
            # (a call elsewhere in the snapshot that passes forward_idret something else)
            self.snap["functions"].append(self.function_record("@f.elsewhere", [
                op("call", [("1", "int"), (snapshot_call, "*dyn")], [901], text="@f.forward_idret", typ="int")]))
        fn, removed, tested = self.field_case()
        fn["slots"].append(op("slot", results=[9040], typ="dyn", text="h"))
        call = op("call", [("1", "int"), (argument, "*dyn")], [9041], text=callee, typ="int")
        prefix = [dict(tested, results=[9042])] if argument == "%t9042" else []
        removed = self.insert(fn, removed, "L12", 0, prefix + [call])
        self.effects = summaries(self.snap)
        return fn, removed

    def test_identity_return_buffers_must_be_slots_of_the_caller(self):
        # (passing h.inner's address as the buffer lets the callee null it)
        for callee in ("@f.null_idret", "@f.forward_idret"):
            with self.subTest(callee=callee):
                self.setUp()
                self.assert_refuted(*self.identity_case("%t9042", callee))
        # A buffer of the function's own keeps the proof.
        self.setUp()
        self.assert_proved(*self.identity_case("%h.9040", "@f.null_idret"))

    def test_identity_return_forwarding_carries_an_unverified_buffer(self):
        # (another caller passes forward_idret a field's address, which it forwards to null_idret:
        # neither may leave its %idret stores out of its summary, wherever it is called)
        self.assert_refuted(*self.identity_case("%h.9040", "@f.forward_idret", snapshot_call="%a0"))
        for symbol in ("@f.null_idret", "@f.forward_idret"):
            self.assertNotIn(symbol, self.effects.exempt)
            self.assertEqual(self.effects[symbol] & {"wL", "wD", "wO", "wG"}, {"wL", "wD", "wO", "wG"})

    def test_inventory_must_name_actual_checks(self):
        fn, removed, _ = self.field_case()
        for forged in ([("L12", 0)], [("L6", 3)]):
            with self.subTest(forged=forged):
                result = self.prove(fn, removed + forged)
                self.assertNotEqual(result["status"], "accepted", result)
        # (a check of something other than a null equality is not a removed null check)
        site = next(self.check_site(fn, "OverflowError: integer result does not fit in 64 bits"))
        result = self.prove(fn, removed + [site])
        self.assertEqual(result["attempts"][0]["status"], "error", result)


if __name__ == "__main__":
    unittest.main()
