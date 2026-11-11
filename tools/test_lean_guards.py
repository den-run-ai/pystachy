"""Corrupt actual compiler IR; failures must remain failures under Lean."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import check_lean_boundary as boundary
import check_lean_guards as guards

ROOT = Path(__file__).resolve().parent.parent
CHECKER = boundary.DEFAULT_CHECKER
SOURCE = '''
class Box:
    def __init__(self, value: int) -> None:
        self.value = value

def twice(box: Box) -> int:
    return box.value + box.value

def narrow(value: int | str) -> int:
    if isinstance(value, int):
        return value + 1
    return len(value)

def optional(value: int | str | None) -> int:
    if isinstance(value, int):
        return value + 1
    if isinstance(value, str):
        return len(value)
    return 0

print(twice(Box(2)), narrow(3), narrow("abc"), optional(None))
'''


class GuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        root = Path(cls.temp.name)
        source = root / "example.py"
        source.write_text(SOURCE)
        env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
        env["PYSTACHY_HOME"] = str(ROOT)
        result = subprocess.run([sys.executable, str(ROOT / "tools/inspect_compiler.py"),
                                 str(source), "--output", str(root / "inspection"),
                                 "--guard-evidence", "--typed-after-only"],
                                cwd=ROOT, env=env, capture_output=True, text=True, timeout=40)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.snapshot = json.loads((root / "inspection/typed-after.json").read_text())

    def sample(self):
        return copy.deepcopy(self.snapshot)

    def lean(self, candidate, meta):
        if not CHECKER.is_file():
            if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1":
                self.fail("Lean checker required")
            self.skipTest("Lean checker not built")
        return boundary.run_checker(CHECKER, boundary.encode(candidate), meta)

    def union(self, snap):
        return next(fn for fn in snap["functions"] if fn["name"] == "narrow")

    def nullrecord(self, snap):
        return next(record for record in snap["nullcheck_evidence"] if record["reported_rewrites"])

    def test_real_guards_and_actual_removals(self):
        snap = self.sample()
        self.assertEqual(len(guards.inventory(self.union(snap))), 3)
        record = self.nullrecord(snap)
        self.assertEqual(len(guards.removed_checks(record)), 1)
        self.assertTrue(self.lean(*guards.normalize(snap, self.union(snap))))
        self.assertTrue(self.lean(*guards.normalize(snap, record["before"], guards.removed_checks(record))))

    def test_wrong_union_member_is_rejected(self):
        snap = self.sample()
        fn = self.union(snap)
        payload = next(op for b in fn["blocks"] for op in b["operations"] if op["op"] == "union.payload")
        payload["text"] = "str" if payload["text"] == "int" else "int"
        self.assertFalse(self.lean(*guards.normalize(snap, fn)))

    def test_swapped_tag_guard_is_rejected(self):
        snap = self.sample()
        fn = self.union(snap)
        branch = next(op for b in fn["blocks"] for op in b["operations"] if op["op"] == "cbr")
        branch["targets"].reverse()
        self.assertFalse(self.lean(*guards.normalize(snap, fn)))

    def test_no_union_guard_is_rejected(self):
        snap = self.sample()
        fn = self.union(snap)
        branch = next(op for b in fn["blocks"] for op in b["operations"] if op["op"] == "cbr")
        branch["operands"][0]["value"] = "true"
        self.assertFalse(self.lean(*guards.normalize(snap, fn)))

    def test_narrowed_use_annotation_cannot_hide_nullable_source(self):
        snap = self.sample()
        fn = self.union(snap)
        fn["parameters"][0]["representation"] = "opt[union[int,str]]"
        self.assertFalse(self.lean(*guards.normalize(snap, fn)))

    def test_machine_union_tag_stays_in_inventory(self):
        snap = self.sample()
        fn = self.union(snap)
        op = next(op for b in fn["blocks"] for op in b["operations"] if op["op"] == "union.tag")
        op["op"] = "mach.load"
        op["operands"][0]["type"] = "%ptr"
        self.assertEqual(len(guards.inventory(fn)), 3)
        self.assertTrue(self.lean(*guards.normalize(snap, fn)))

    def test_null_guard_bypass_is_rejected(self):
        snap = self.sample()
        record = self.nullrecord(snap)
        removed = guards.removed_checks(record)
        for block in record["before"]["blocks"]:
            for offset, op in enumerate(block["operations"]):
                if op["op"] == "check" and (block["label"], offset) not in removed:
                    op["operands"][0]["value"] = "false"
        self.assertFalse(self.lean(*guards.normalize(snap, record["before"], removed)))

    def test_removed_count_mismatch_fails_closed(self):
        record = self.nullrecord(self.sample())
        record["reported_rewrites"] += 1
        with self.assertRaisesRegex(ValueError, "inventory disagrees"):
            guards.removed_checks(record)

    def test_missing_pass_record_fails_closed(self):
        snap = self.sample()
        snap["nullcheck_evidence"] = []
        with self.assertRaisesRegex(ValueError, "manifest mismatch"):
            guards.check_all(snap)

    def test_missing_tag_metadata_fails_closed(self):
        snap = self.sample()
        del snap["union_tags"]
        with self.assertRaisesRegex(ValueError, "inventory missing"):
            guards.check_all(snap)

    def test_duplicate_tags_fail_closed(self):
        snap = self.sample()
        snap["union_tags"]["str"] = snap["union_tags"]["int"]
        with self.assertRaisesRegex(ValueError, "tag inventory"):
            guards.normalize(snap, self.union(snap))

    def test_raw_union_is_explicitly_unsupported(self):
        snap = self.sample()
        fn = self.union(snap)
        op = next(op for b in fn["blocks"] for op in b["operations"] if op["op"] == "union.payload")
        op["op"], op["text"] = "union.raw", ""
        with self.assertRaisesRegex(boundary.Unsupported, "raw union"):
            guards.normalize(snap, fn)

    def test_unknown_union_guard_stays_rejected(self):
        snap = self.sample()
        fn = self.union(snap)
        op = next(op for b in fn["blocks"] for op in b["operations"] if op["op"] == "num.cmp")
        op["operands"][1]["value"] = "999999"
        self.assertFalse(self.lean(*guards.normalize(snap, fn)))

    def test_exception_before_entry_store_cannot_invent_alias(self):
        from test_lean_boundary import instruction
        snap = self.sample()
        fn = self.union(snap)
        slot = next(slot for slot in fn["slots"] if slot["text"] == "value")
        address = f"%value.{slot['results'][0]}"
        fn["blocks"][0]["handler"] = "catch"
        fn["blocks"][0]["operations"].insert(0, instruction(
            "rt", "int", "int.str", results=[100], operands=[("@s.6", "str"), ("10", "int")]))
        fn["blocks"].append({"label": "catch", "handler": "", "operations": [
            instruction("mem.load", "union[int,str]", results=[101], operands=[(address, "*union[int,str]")]),
            instruction("union.tag", "int", results=[102], operands=[("%t101", "union[int,str]")]),
            instruction("ret", operands=[("0", "int")])]})
        self.assertFalse(self.lean(*guards.normalize(snap, fn)))

    def test_threading_keeps_phi_used_by_other_operations(self):
        from test_lean_boundary import instruction
        snap = self.sample()
        fn = next(fn for fn in snap["functions"] if fn["name"] == "optional")
        self.assertTrue(self.lean(*guards.normalize(snap, fn)))
        join = next(b for b in fn["blocks"] if len(b["operations"]) == 2
                    and b["operations"][0]["op"] == "phi" and b["operations"][0]["type"] == "bool")
        value = f"%t{join['operations'][0]['results'][0]}"
        successor = next(b for b in fn["blocks"] if b["label"] == join["operations"][1]["targets"][0])
        successor["operations"].insert(0, instruction("select", "int", results=[100],
                                                    operands=[(value, "bool"), ("1", "int"), ("0", "int")]))
        # No per-edge phi assignment is modeled: keep this join and fail closed.
        self.assertFalse(self.lean(*guards.normalize(snap, fn)))

    def test_union_address_rewrite_cannot_drop_inventory(self):
        from test_lean_boundary import instruction
        snap = self.sample()
        fn = self.union(snap)
        block, offset, op = next((b, n, op) for b in fn["blocks"] for n, op in enumerate(b["operations"])
                                 if op["op"] == "union.tag")
        source = op["operands"][0]["value"]
        block["operations"].insert(offset, instruction("mach.addr", "%ptr", "int", results=[100],
                                                       operands=[(source, "%ptr"), ("0", "int")]))
        op["op"], op["operands"] = "mach.load", [{"value": "%t100", "type": "%ptr"}]
        self.assertEqual(len(guards.inventory(fn)), 3)
        with self.assertRaisesRegex(boundary.Unsupported, "declared source domain"):
            guards.normalize(snap, fn)

    def test_machine_slot_write_cannot_preserve_guard(self):
        from test_lean_boundary import instruction
        snap = self.sample()
        fn = self.union(snap)
        slot = next(slot for slot in fn["slots"] if slot["text"] == "value")
        address = f"%value.{slot['results'][0]}"
        target = next(b for b in fn["blocks"] if any(op["op"] == "union.payload" for op in b["operations"]))
        target["operations"].insert(0, instruction("mach.store", operands=[(address, "%ptr"), ("null", "%ptr")]))
        self.assertFalse(self.lean(*guards.normalize(snap, fn)))

    def test_cast_cannot_make_machine_union_read_disappear(self):
        from test_lean_boundary import instruction
        snap = self.sample()
        fn = self.union(snap)
        block, offset, op = next((b, n, op) for b in fn["blocks"] for n, op in enumerate(b["operations"])
                                 if op["op"] == "union.tag")
        source = op["operands"][0]["value"]
        block["operations"].insert(offset, instruction("scalar.cast", "%ptr", "bitcast", results=[100],
                                                       operands=[(source, "%ptr")]))
        op["op"], op["operands"] = "mach.load", [{"value": "%t100", "type": "%ptr"}]
        self.assertEqual(len(guards.inventory(fn)), 3)
        with self.assertRaisesRegex(boundary.Unsupported, "declared source domain"):
            guards.normalize(snap, fn)

    def test_machine_null_store_invalidates_even_tag_only_read(self):
        from test_lean_boundary import instruction
        snap = self.sample()
        fn = self.union(snap)
        entry = fn["blocks"][0]
        index = next(n for n, op in enumerate(entry["operations"]) if op["op"] == "union.tag")
        entry["operations"] = entry["operations"][:index + 1] + [instruction("ret", operands=[("0", "int")])]
        fn["blocks"] = [entry]
        slot = next(slot for slot in fn["slots"] if slot["text"] == "value")
        address = f"%value.{slot['results'][0]}"
        entry["operations"].insert(1, instruction("mach.store", operands=[(address, "%ptr"), ("null", "%ptr")]))
        self.assertEqual(len(guards.inventory(fn)), 1)
        self.assertFalse(self.lean(*guards.normalize(snap, fn)))

    def test_unnamed_dead_block_is_not_an_exception_handler(self):
        from test_lean_boundary import instruction
        snap = self.sample()
        fn = self.union(snap)
        fn["blocks"].append({"label": "", "handler": "", "operations": [instruction("ret", operands=[("0", "int")])]})
        self.assertTrue(self.lean(*guards.normalize(snap, fn)))

    def test_declared_domains_parse_nested_members(self):
        self.assertEqual(guards.union_members("opt[union[int,tuple[int,str]]]"),
                         ["member:int", "member:tuple[int,str]", "null"])


class GuardCorpusAccountingTests(unittest.TestCase):
    def record(self, **updates):
        return {"program": "p.py", "status": "accepted", "inventory_complete": True,
                "union_reads": 1, "proved_union_reads": 1, "removed_checks": 2,
                "proved_removed_checks": 2} | updates

    def test_empty_inventory_cannot_pass(self):
        from check_lean_guard_corpus import summarize
        with self.assertRaisesRegex(ValueError, "program inventory"):
            summarize([], [], 0)

    def test_missing_or_inconsistent_counts_cannot_pass(self):
        from check_lean_guard_corpus import summarize
        record = self.record()
        del record["union_reads"]
        with self.assertRaisesRegex(ValueError, "missing obligation counts"):
            summarize(["p.py"], [record], 0)
        with self.assertRaisesRegex(ValueError, "omitted obligations"):
            summarize(["p.py"], [self.record(proved_removed_checks=1)], 0)

    def test_uninventoried_errors_are_explicit(self):
        from check_lean_guard_corpus import failed, summarize
        report = summarize(["p.py"], [failed("p.py", "compile failed")], 0)
        self.assertFalse(report["inventory_complete"])
        self.assertEqual(report["totals"]["uninventoried_programs"], 1)
        self.assertIsNone(report["programs"][0]["union_reads"])

    def test_zero_obligation_program_is_labeled_vacuous(self):
        from check_lean_guard_corpus import summarize
        record = self.record(union_reads=0, proved_union_reads=0, removed_checks=0, proved_removed_checks=0)
        report = summarize(["p.py"], [record], 0)
        self.assertEqual(report["totals"]["vacuous_programs"], 1)


if __name__ == "__main__":
    unittest.main()
