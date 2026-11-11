"""Union membership facts must not outlive possible box-header mutation."""
import copy
import os
import unittest

import check_lean_boundary as boundary
import check_lean_guards as guards
import test_lean_guards as fixtures
from test_lean_boundary import instruction as op

CHECKER = boundary.DEFAULT_CHECKER


class UnionMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CHECKER.is_file():
            if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1":
                raise RuntimeError("Lean checker required for union mutation controls")
            raise unittest.SkipTest("build the Lean boundary checker")
        fixtures.GuardTests.setUpClass()
        cls.addClassCleanup(fixtures.GuardTests.doClassCleanups)
        cls.snapshot = copy.deepcopy(fixtures.GuardTests.snapshot)

    def sample(self):
        snapshot = copy.deepcopy(self.snapshot)
        function = next(fn for fn in snapshot["functions"] if fn["name"] == "narrow")
        return snapshot, function

    @staticmethod
    def int_read(function):
        return next((block, offset, instruction) for block in function["blocks"]
                    for offset, instruction in enumerate(block["operations"])
                    if instruction["op"] == "union.payload" and instruction["text"] == "int")

    def accepted(self, snapshot, function):
        candidate, metadata = guards.normalize(snapshot, function)
        return boundary.run_checker(CHECKER, boundary.encode(candidate), metadata)

    def refused(self, snapshot, function, reads=3):
        self.assertEqual(len(guards.inventory(function)), reads)
        try:
            self.assertFalse(self.accepted(snapshot, function))
        except boundary.Unsupported:
            pass
        snapshot["functions"], snapshot["nullcheck_evidence"] = [function], []
        snapshot["guard_inventory"] = {"nullcheck_passes": 0, "removed_checks": 0}
        report, code = guards.check_all(snapshot, CHECKER)
        self.assertIn(code, (1, 2), report)
        self.assertEqual(report["union_reads"], reads)
        self.assertEqual(report["proved_union_reads"], 0)

    def test_original_guard_and_post_read_call_remain_accepted(self):
        snapshot, function = self.sample()
        self.assertTrue(self.accepted(snapshot, function))

    def test_direct_and_transported_box_stores_are_not_ignored(self):
        for mode in ("mach.store", "mem.store", "mach.addr", "field.addr", "cast", "slot", "tuple.store"):
            with self.subTest(mode=mode):
                snapshot, function = self.sample()
                block, offset, payload = self.int_read(function)
                source = payload["operands"][0]["value"]
                address, prefix = source, []
                tag = str(snapshot["union_tags"]["str"])
                if mode == "mach.addr":
                    prefix = [op("mach.addr", "%ptr", "int", [100], [(source, "%ptr"), ("0", "int")])]
                    address = "%t100"
                elif mode == "field.addr":
                    prefix = [op("field.addr", "*int", results=[100], operands=[(source, "Box")])]
                    address = "%t100"
                elif mode == "cast":
                    prefix = [op("scalar.cast", "%ptr", "bitcast", [100], [(source, "union[int,str]")])]
                    address = "%t100"
                elif mode == "slot":
                    prefix = [op("slot.pack", "%slot", results=[100], operands=[(source, "union[int,str]")]),
                              op("slot.unpack", "int", results=[101], operands=[("%t100", "%slot")]),
                              op("scalar.cast", "%ptr", "inttoptr", [102], [("%t101", "int")])]
                    address = "%t102"
                if mode == "tuple.store":
                    store = op("tuple.store", text="int", operands=[(source, "tuple[int]"), (tag, "%slot")])
                else:
                    typed = mode in {"mem.store", "field.addr"}
                    store = op("mem.store" if typed else "mach.store",
                               operands=[(address, "*int" if typed else "%ptr"), (tag, "int")])
                block["operations"][offset:offset] = prefix + [store]
                self.refused(snapshot, function)

    def test_independent_raw_pointer_can_alias_guarded_box(self):
        snapshot, function = self.sample()
        function["parameters"].append({"name": "alias", "type": "%ptr", "representation": "%ptr"})
        block, offset, _ = self.int_read(function)
        block["operations"].insert(offset, op("mach.store", operands=[
            ("%a1", "%ptr"), (str(snapshot["union_tags"]["str"]), "int")]))
        self.refused(snapshot, function)

    def test_box_reloaded_through_another_slot_is_same_mutable_object(self):
        snapshot, function = self.sample()
        function["slots"].append(op("slot", "union[int,str]", "alias", [100]))
        block, offset, payload = self.int_read(function)
        source = payload["operands"][0]["value"]
        block["operations"][offset:offset] = [
            op("mem.store", operands=[("%alias.100", "*union[int,str]"), (source, "union[int,str]")]),
            op("mem.load", "union[int,str]", results=[101], operands=[("%alias.100", "*union[int,str]")]),
            op("mach.store", operands=[("%t101", "%ptr"), (str(snapshot["union_tags"]["str"]), "int")])]
        self.refused(snapshot, function)

    def test_runtime_calls_and_generator_cleanup_may_mutate_boxes(self):
        for mode in ("memmove", "copybytes", "call", "gen.drop", "gen.resume"):
            with self.subTest(mode=mode):
                snapshot, function = self.sample()
                function["parameters"].append({"name": "other", "type": "%ptr", "representation": "%ptr"})
                block, offset, payload = self.int_read(function)
                source = payload["operands"][0]["value"]
                if mode.startswith("gen."):
                    operation = op(mode, operands=[("%a1", "%ptr")])
                elif mode == "call":
                    operation = op("call", "None", "@f.opaque_mutation")
                else:
                    operation = op("rt", "None", mode, operands=[
                        (source, "%ptr"), ("%a1", "%ptr"), ("16", "int"), ("false", "%i1")])
                block["operations"].insert(offset, operation)
                self.refused(snapshot, function)

    def test_call_havoc_cannot_revalidate_a_stale_tag_comparison(self):
        snapshot, function = self.sample()
        entry = function["blocks"][0]
        source = next(ins["operands"][0]["value"] for ins in entry["operations"] if ins["op"] == "union.tag")
        entry["operations"].insert(len(entry["operations"]) - 1,
                                   op("rt", "None", "copybytes", operands=[(source, "%ptr")]))
        for block in function["blocks"]:
            if any(ins["op"] == "union.payload" and ins["text"] == "str" for ins in block["operations"]):
                block["operations"] = [op("ret", operands=[("0", "int")])]
        self.refused(snapshot, function, reads=2)

    def test_call_mutation_then_exception_cannot_reuse_handler_guard(self):
        for invoke in (False, True):
            with self.subTest(invoke=invoke):
                snapshot, function = self.sample()
                block, offset, payload = self.int_read(function)
                guarded_payload = copy.deepcopy(payload)
                guarded_payload["operands"][0]["value"] = "%a0"
                call = op("rt", "None", "copybytes", operands=[("%a0", "%ptr")],
                          targets=["normal", "mutated"] if invoke else [])
                block["operations"] = block["operations"][:offset] + [call]
                if not invoke:
                    block["handler"] = "mutated"
                    block["operations"].append(op("br", targets=["normal"]))
                function["blocks"].extend([
                    {"label": "normal", "handler": "", "operations": [op("ret", operands=[("0", "int")])]},
                    {"label": "mutated", "handler": "", "operations": [guarded_payload, op("ret", operands=[("0", "int")])]}])
                for candidate in function["blocks"]:
                    if candidate["label"] in {"L16", "L15"}:
                        candidate["operations"] = [op("ret", operands=[("0", "int")])]
                self.refused(snapshot, function)

    def test_call_after_read_can_mutate_next_loop_iteration(self):
        snapshot, function = self.sample()
        block, offset, _ = self.int_read(function)
        block["operations"] = block["operations"][:offset + 1] + [
            op("rt", "None", "copybytes", operands=[("%a0", "%ptr")]),
            op("br", targets=[block["label"]])]
        for candidate in function["blocks"]:
            if candidate["label"] in {"L16", "L15"}:
                candidate["operations"] = [op("ret", operands=[("0", "int")])]
        self.refused(snapshot, function)

    def test_write_only_union_helper_is_not_vacuously_accepted(self):
        snapshot, function = self.sample()
        function["blocks"] = [{"label": "entry", "handler": "", "operations": [
            op("mach.store", operands=[("%a0", "%ptr"), (str(snapshot["union_tags"]["str"]), "int")]),
            op("ret", operands=[("0", "int")])]}]
        self.refused(snapshot, function, reads=0)


if __name__ == "__main__":
    unittest.main()
