"""Corrupt actual compiler IR; failures must remain failures under Lean."""
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

print(twice(Box(2)), narrow(3), narrow("abc"), optional(None), optional(7), optional("guard"))
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

    def removal_proof(self, snap, fn, removed):
        """Both Lean models' verdict on removed checks, as check_all reaches them."""
        if not (CHECKER.is_file() and access.DEFAULT_CHECKER.is_file()):
            if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1":
                self.fail("Lean checkers required")
            self.skipTest("Lean checkers not built")
        return guards.prove_removals(snap, fn, removed, summaries(snap), CHECKER, access.DEFAULT_CHECKER)

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
        result = self.removal_proof(snap, record["before"], removed)
        self.assertEqual([(a["model"], a["status"]) for a in result["attempts"]],
                         [("access", "rejected"), ("finite-tag", "rejected")])

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

    def test_raw_union_bits_are_read_as_their_member(self):
        # (a raw read claims no member: the reads of its bits as a member's are the obligations)
        snap = self.sample()
        fn = self.union(snap)
        op = next(op for b in fn["blocks"] for op in b["operations"] if op["op"] == "union.payload")
        op["op"], op["text"] = "union.raw", ""
        candidate, meta = guards.normalize(snap, fn)
        self.assertGreater(meta["payload_obligations"], 0)
        self.assertTrue(self.lean(candidate, meta))
        test = next(op for b in fn["blocks"] for op in b["operations"] if op["op"] == "num.cmp")
        test["operands"][1]["value"] = next(str(tag) for tag in snap["union_tags"].values()
                                            if str(tag) != test["operands"][1]["value"])
        self.assertFalse(self.lean(*guards.normalize(snap, fn)))

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
        with self.assertRaisesRegex(boundary.Unsupported, "opaque call"):
            guards.normalize(snap, fn)

    def test_threading_keeps_phi_used_by_other_operations(self):
        from test_lean_boundary import instruction
        snap = self.sample()
        fn = next(fn for fn in snap["functions"] if fn["name"] == "optional")
        self.assertTrue(self.lean(*guards.normalize(snap, fn)))
        join = next(b for b in fn["blocks"] if len(b["operations"]) == 2
                    and b["operations"][0]["op"] == "phi" and b["operations"][0]["type"] == "bool")
        value = f"%t{join['operations'][0]['results'][0]}"
        successor = next(b for b in fn["blocks"] if b["label"] == join["operations"][1]["targets"][0])
        union, tag = "union[int,str]", str(snap["union_tags"]["int"])
        # The join stays threaded, but its phi's other uses test it as an opaque condition: a union
        # select on it may be either operand, so reading it as an int needs a guard.
        successor["operations"][:0] = [
            instruction("rt", "%ptr", "ubox", [100], [(tag, "int"), ("5", "*T")]),
            instruction("mem.load", union, results=[99], operands=[("@g.unknown", "*" + union)]),
            instruction("select", union, results=[101], operands=[(value, "bool"), ("%t100", union), ("%t99", union)]),
            instruction("union.payload", "%slot", "int", [102, 103], [("%t101", union)])]
        self.assertFalse(self.lean(*guards.normalize(snap, fn)))
        successor["operations"][2]["operands"][2] = {"value": "%t100", "type": union}
        self.assertTrue(self.lean(*guards.normalize(snap, fn)))

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

    def test_transports_cannot_make_null_union_nonnull(self):
        from test_lean_boundary import instruction
        for transport in ("select", "phi", "scalar.cast", "slot.unpack", "scalar.bin", "rt"):
            with self.subTest(transport=transport):
                snap = self.sample()
                fn = self.union(snap)
                entry = fn["blocks"][0]
                index = next(n for n, op in enumerate(entry["operations"]) if op["op"] == "union.tag")
                read = entry["operations"][index]
                loaded = read["operands"][0]["value"]
                slot = next(slot for slot in fn["slots"] if slot["text"] == "value")
                address = f"%value.{slot['results'][0]}"
                entry["operations"] = entry["operations"][:index]
                entry["operations"].insert(1, instruction("mach.store", operands=[(address, "%ptr"), ("null", "%ptr")]))
                args = [(loaded, "union[int,str]")]
                text, targets, prefix = "", [], []
                if transport == "select":
                    args = [("true", "bool")] + args * 2
                elif transport == "phi":
                    targets = [entry["label"]]
                elif transport == "scalar.cast":
                    text = "bitcast"
                elif transport == "slot.unpack":
                    prefix = [instruction("slot.pack", "%slot", results=[101], operands=args)]
                    args = [("%t101", "%slot")]
                elif transport == "scalar.bin":
                    text, args = "or", [(loaded, "%ptr"), ("0", "int")]
                elif transport == "rt":
                    text = "unmodeled_union_result"
                operation = instruction(transport, "union[int,str]", text, results=[100], operands=args, targets=targets)
                read["operands"][0]["value"] = "%t100"
                tail = prefix + [operation, read, instruction("ret", operands=[("0", "int")])]
                if transport == "phi":
                    entry["operations"].append(instruction("br", targets=["join"]))
                    fn["blocks"] = [entry, {"label": "join", "handler": "", "operations": tail}]
                else:
                    entry["operations"].extend(tail)
                    fn["blocks"] = [entry]
                self.assertEqual(len(guards.inventory(fn)), 1)
                if transport == "rt":
                    with self.assertRaisesRegex(boundary.Unsupported, "opaque call"):
                        guards.normalize(snap, fn)
                    continue
                candidate, meta = guards.normalize(snap, fn)
                self.assertEqual(meta["payloads"], 1)
                self.assertFalse(self.lean(candidate, meta))

    def test_actual_literal_union_constructor_domain(self):
        from test_lean_boundary import instruction
        snap = self.sample()
        fn = next(fn for fn in snap["functions"] if fn["name"] == "<module>")
        block, index, constructor = next((block, index, op) for block in fn["blocks"]
                                         for index, op in enumerate(block["operations"])
                                         if op["op"] == "rt" and op["text"] == "ubox")
        value = f"%t{constructor['results'][0]}"
        # Isolate the compiler-emitted constructor from earlier unrelated calls.
        block["operations"] = [constructor, instruction("union.tag", "int", results=[900], operands=[(value, "%ptr")]),
                               instruction("ret")]
        fn["blocks"] = [block]
        self.assertEqual(len(guards.inventory(fn)), 1)
        self.assertTrue(self.lean(*guards.normalize(snap, fn)))
        constructor["text"] = "ubox_opt"
        self.assertEqual(len(guards.inventory(fn)), 1)
        self.assertFalse(self.lean(*guards.normalize(snap, fn)))

    def test_transport_annotation_cannot_erase_union_member(self):
        from test_lean_boundary import instruction
        snap = self.sample()
        fn = self.union(snap)
        fn["parameters"][0]["representation"] = "union[int,float,str]"
        entry = fn["blocks"][0]
        index = next(n for n, op in enumerate(entry["operations"]) if op["op"] == "union.tag")
        loaded = entry["operations"][index]["operands"][0]["value"]
        tail = entry["operations"][index:]
        entry["operations"] = entry["operations"][:index] + [
            instruction("select", "union[int,str]", results=[100],
                        operands=[("true", "bool"), (loaded, "union[int,str]"), (loaded, "union[int,str]")]),
            instruction("ptr.cmp", "bool", "!=", results=[101],
                        operands=[("%t100", "union[int,str]"), ("null", "union[int,str]")]),
            instruction("cbr", operands=[("%t101", "bool")], targets=["nonnull", "nullret"])]
        fn["blocks"].insert(1, {"label": "nonnull", "handler": "", "operations": tail})
        fn["blocks"].append({"label": "nullret", "handler": "", "operations": [instruction("ret", operands=[("0", "int")])]})
        for block in fn["blocks"]:
            for op in block["operations"]:
                if op["op"] in {"union.tag", "union.payload"}:
                    op["operands"][0]["value"] = "%t100"
        self.assertEqual(len(guards.inventory(fn)), 3)
        candidate, meta = guards.normalize(snap, fn)
        self.assertEqual(meta["payloads"] - meta["payload_obligations"], 3)
        # Even an explicit null guard cannot turn the incoming float into a str.
        self.assertFalse(self.lean(candidate, meta))

    def test_duplicate_check_removal_cannot_borrow_later_guard(self):
        from test_lean_boundary import instruction
        snap = self.sample()
        record = self.nullrecord(snap)
        before = record["before"]
        checks = [(block, offset, op) for block in before["blocks"]
                  for offset, op in enumerate(block["operations"])
                  if op["op"] == "check" and "AttributeError" in op["text"]]
        self.assertEqual(len(checks), 2)
        first, second = checks
        second[2]["operands"] = copy.deepcopy(first[2]["operands"])
        record["after"] = copy.deepcopy(before)
        after_block = next(b for b in record["after"]["blocks"] if b["label"] == first[0]["label"])
        after_block["operations"][first[1]] = instruction("br", targets=first[2]["targets"])
        # The earlier check is necessary, but the later identical check is
        # redundant. A multiset cannot identify which occurrence disappeared.
        self.assertFalse(self.lean(*guards.normalize(snap, before, [(first[0]["label"], first[1])])))
        self.assertTrue(self.lean(*guards.normalize(snap, before, [(second[0]["label"], second[1])])))
        with self.assertRaisesRegex(boundary.Unsupported, "ambiguous partial removal"):
            guards.removed_checks(record)
        report, code = guards.check_all(snap, CHECKER)
        self.assertEqual(code, 2)
        self.assertEqual(report["removed_checks"], 1)
        self.assertEqual(report["proved_removed_checks"], 0)
        # Removing every occurrence has an unambiguous inventory, and still
        # exposes the unsafe first removal to Lean.
        other = next(b for b in record["after"]["blocks"] if b["label"] == second[0]["label"])
        other["operations"][second[1]] = instruction("br", targets=second[2]["targets"])
        record["reported_rewrites"] = 2
        removed = guards.removed_checks(record)
        self.assertEqual(len(removed), 2)
        self.assertFalse(self.lean(*guards.normalize(snap, before, removed)))
        self.assertEqual(self.removal_proof(snap, before, removed)["status"], "rejected")
        snap["guard_inventory"]["removed_checks"] += 1
        report, code = guards.check_all(snap, CHECKER)
        self.assertEqual((code, report["removed_checks"], report["proved_removed_checks"]), (1, 2, 0))

    def test_declared_domains_parse_nested_members(self):
        self.assertEqual(guards.union_members("opt[union[int,tuple[int,str]]]"),
                         ["member:int", "member:tuple[int,str]", "null"])

    def test_raw_transports_remain_in_inventory(self):
        from test_lean_boundary import instruction as op
        for transport in ("big", "tuple", "address", "reverse_address", "opaque"):
            with self.subTest(transport=transport):
                snap = self.sample()
                fn = self.union(snap)
                union = "union[int,str]"
                slot = next(slot for slot in fn["slots"] if slot["text"] == "value")
                address = f"%value.{slot['results'][0]}"
                if transport == "big":
                    operations = [
                        op("scalar.cast", "%ptr", "bitcast", [100], [("%a0", union)]),
                        op("big.make", "int+", results=[101], operands=[("-9223372036854775808", "int"), ("%t100", "%ptr")]),
                        op("big.hi", "%ptr", results=[102], operands=[("%t101", "int+")])]
                elif transport == "tuple":
                    operations = [
                        op("slot.pack", "%slot", results=[100], operands=[("%a0", union)]),
                        op("alloc.fixed", "tuple[union[int,str]]", results=[101]),
                        op("tuple.store", operands=[("%t101", "tuple[union[int,str]]"), ("%t100", "%slot")]),
                        op("tuple.load", "%slot", results=[103], operands=[("%t101", "tuple[union[int,str]]")]),
                        op("slot.unpack", "int", results=[104], operands=[("%t103", "%slot")]),
                        op("scalar.cast", "%ptr", "inttoptr", [102], [("%t104", "int")])]
                elif transport in {"address", "reverse_address"}:
                    cast = op("scalar.cast", "%ptr", "bitcast", [100], [(address, "*" + union)])
                    if transport == "address":
                        operations = [op("mem.store", operands=[(address, "*" + union), ("%a0", union)]), cast]
                        source = "%t100"
                    else:
                        operations = [cast, op("mem.store", operands=[("%t100", "%ptr"), ("%a0", union)])]
                        source = address
                    operations.append(op("mach.load", "%ptr", results=[102], operands=[(source, "%ptr")]))
                else:
                    operations = [op("rt", "%ptr", "unmodeled_transport", [102], [("%a0", union)])]
                operations.extend([op("mach.load", "int", results=[105], operands=[("%t102", "%ptr")]),
                                   op("ret", operands=[("0", "int")])])
                fn["blocks"] = [{"label": "entry", "handler": "", "operations": operations}]
                self.assertEqual(len(guards.inventory(fn)), 1)
                self.assertEqual(len(guards.inventory(fn, guards.union_context(snap))), 1)
                with self.assertRaisesRegex(boundary.Unsupported, "declared source domain|nonprivate writes|opaque call"):
                    guards.normalize(snap, fn)
                snap["functions"], snap["nullcheck_evidence"] = [fn], []
                snap["guard_inventory"] = {"nullcheck_passes": 0, "removed_checks": 0}
                report, code = guards.check_all(snap, CHECKER)
                self.assertEqual(code, 2)
                self.assertEqual(report["union_reads"], 1)
                self.assertEqual(report["proved_union_reads"], 0)


    def test_typed_union_memory_keeps_retyped_reads(self):
        # Typed union memory (a field word or tuple item some view types as a union, a private slot,
        # a call's result) is read as that union; each way of reading the word as anything else and
        # then reading through it as a box must stay inventoried. Reads of other words must not be.
        from test_lean_boundary import instruction as op
        union, holder = "union[int,str]", "Holder"
        def field(results, typ, index=0):
            made = op("field.addr", "*" + typ, results=results, operands=[("%a1", holder)])
            made["immediate"] = index
            return made
        def box_read(word):
            return [op("scalar.cast", "%ptr", "inttoptr", [150], [(word, "int")]),
                    op("mach.load", "int", results=[151], operands=[("%t150", "%ptr")])]
        def tuple_item(kind, typ, text, results, operands):
            made = op(kind, typ, text, results, operands)
            made["immediate"] = 0
            return made
        cases = {
            "raw object": ([field([100], union), op("mem.store", operands=[("%t100", "*" + union), ("%a0", union)]),
                            op("mach.addr", "%ptr", "%ptr", [101], [("%a1", holder), ("1", "int")]),
                            op("mach.load", "int", results=[102], operands=[("%t101", "%ptr")])], "%t102", 1),
            "other view": ([field([100], union), op("mem.store", operands=[("%t100", "*" + union), ("%a0", union)]),
                            field([101], "int"), op("mem.load", "int", results=[102], operands=[("%t101", "*int")])],
                           "%t102", 1),
            "other field": ([field([100], union), op("mem.store", operands=[("%t100", "*" + union), ("%a0", union)]),
                             field([101], "int", 1), op("mem.load", "int", results=[102], operands=[("%t101", "*int")])],
                            "%t102", 0),
            "item text": ([op("slot.pack", "%slot", results=[100], operands=[("%a0", union)]),
                           op("alloc.fixed", f"tuple[{union}]", results=[101]),
                           tuple_item("tuple.store", "", union, [], [("%t101", f"tuple[{union}]"), ("%t100", "%slot")]),
                           tuple_item("tuple.load", "%slot", "int", [103, 104], [("%t101", f"tuple[{union}]")]),
                           op("slot.unpack", "int", results=[102], operands=[("%t104", "%slot")])], "%t102", 1),
            "tuple view": ([op("slot.pack", "%slot", results=[100], operands=[("%a0", union)]),
                            op("alloc.fixed", f"tuple[{union}]", results=[101]),
                            tuple_item("tuple.store", "", union, [], [("%t101", f"tuple[{union}]"), ("%t100", "%slot")]),
                            op("select", "tuple[int]", results=[105], operands=[
                                ("true", "bool"), ("%t101", "tuple[int]"), ("%t101", "tuple[int]")]),
                            tuple_item("tuple.load", "%slot", "int", [103, 104], [("%t105", "tuple[int]")]),
                            op("slot.unpack", "int", results=[102], operands=[("%t104", "%slot")])], "%t102", 1),
            "tuple cast": ([op("slot.pack", "%slot", results=[100], operands=[("%a0", union)]),
                            op("alloc.fixed", f"tuple[{union}]", results=[101]),
                            tuple_item("tuple.store", "", union, [], [("%t101", f"tuple[{union}]"), ("%t100", "%slot")]),
                            op("scalar.cast", "tuple[int]", "bitcast", [105], [("%t101", f"tuple[{union}]")]),
                            tuple_item("tuple.load", "%slot", "int", [103, 104], [("%t105", "tuple[int]")]),
                            op("slot.unpack", "int", results=[102], operands=[("%t104", "%slot")])], "%t102", 1),
            "slot": ([op("mem.store", operands=[("%value.9", "*" + union), ("%a0", union)]),
                      op("mem.load", "int", results=[102], operands=[("%value.9", "*int")])], "%t102", 1),
            "transport": ([op("call", "int", "@f.leak", [102], [("%a0", union)])], "%t102", 1),
        }
        for name, (operations, word, expected) in cases.items():
            with self.subTest(case=name):
                snap = self.sample()
                fn = self.union(snap)
                fn["parameters"] = fn["parameters"] + [dict(fn["parameters"][0], representation=holder)]
                fn["slots"] = fn["slots"] + [dict(fn["slots"][0], text="value", type=union, results=[9])]
                fn["blocks"] = [{"label": "entry", "handler": "", "operations": operations + box_read(word) + [
                    op("ret", operands=[("0", "int")])]}]
                leak = copy.deepcopy(fn)
                leak.update(symbol="@f.leak", name="leak", return_representation="int", slots=[])
                leak["blocks"] = [{"label": "entry", "handler": "", "operations": [
                    op("scalar.cast", "int", "ptrtoint", [100], [("%a0", union)]), op("ret", operands=[("%t100", "int")])]}]
                snap["functions"] = [fn, leak]
                snap["classes"][holder] = {"base": "", "role": "", "overlaps": [], "tagged": False}
                snap["class_layouts"][holder] = {"fields": ["u", "n"], "flags": {}, "sure": []}
                context = guards.union_context(snap)
                self.assertEqual(context["transports"], {"@f.leak"})
                self.assertEqual(len(guards.inventory(fn, context)), expected)


class PlaceholderSlotTests(unittest.TestCase):
    def test_resolved_placeholder_slot_types(self):
        # (a local's slot keeps the type it had when made; its accesses name the resolved one)
        for declared, used in (("list[?]", "*list[int]"), ("dict[?,?]", "*dict[str,int]"),
                               ("opt[None]", "*str"), ("opt[None]", "*opt[int]"),
                               ("opt[None]", "*opt[union[int,str]]")):
            self.assertTrue(boundary.resolved_container(declared, used), (declared, used))
        for declared, used in (("list[?]", "*dict[str,int]"), ("list[int]", "*list[str]"),
                               ("list[?]", "list[int]"), ("opt[None]", "*int"), ("opt[None]", "*dyn"),
                               ("opt[None]", "*opt[dyn]"), ("opt[None]", "*union[int,str]"),
                               ("opt[None]", "*opt[?]"), ("opt[None]", "*%slot")):
            self.assertFalse(boundary.resolved_container(declared, used), (declared, used))


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

    def test_payload_obligations_are_counted_and_not_vacuous(self):
        from check_lean_guard_corpus import summarize
        record = self.record(union_reads=0, proved_union_reads=0, removed_checks=0, proved_removed_checks=0,
                             payload_obligations=3, proved_payload_obligations=3)
        report = summarize(["p.py"], [record], 0)
        self.assertEqual(report["totals"]["vacuous_programs"], 0)
        self.assertEqual(report["totals"]["proved_payload_obligations"], 3)
        with self.assertRaisesRegex(ValueError, "omitted obligations"):
            summarize(["p.py"], [self.record(payload_obligations=3, proved_payload_obligations=2)], 0)
        with self.assertRaisesRegex(ValueError, "invalid payload obligation counts"):
            summarize(["p.py"], [self.record(status="rejected", payload_obligations=1,
                                             proved_payload_obligations=2)], 0)

    def test_field_obligations_are_counted_and_not_vacuous(self):
        from check_lean_guard_corpus import summarize
        record = self.record(union_reads=0, proved_union_reads=0, removed_checks=0, proved_removed_checks=0,
                             field_obligations=4, proved_field_obligations=4)
        report = summarize(["p.py"], [record], 0)
        self.assertEqual(report["totals"]["vacuous_programs"], 0)
        self.assertEqual(report["totals"]["proved_field_obligations"], 4)
        with self.assertRaisesRegex(ValueError, "omitted obligations"):
            summarize(["p.py"], [self.record(field_obligations=4, proved_field_obligations=3)], 0)
        with self.assertRaisesRegex(ValueError, "invalid field obligation counts"):
            summarize(["p.py"], [self.record(status="rejected", field_obligations=1,
                                             proved_field_obligations=2)], 0)

    def test_unsupported_write_only_program_is_not_vacuous(self):
        from check_lean_guard_corpus import summarize
        record = self.record(status="unsupported", union_reads=0, proved_union_reads=0,
                             removed_checks=0, proved_removed_checks=0, union_box_writes=1)
        report = summarize(["p.py"], [record], 0)
        self.assertEqual(report["totals"]["vacuous_programs"], 0)


if __name__ == "__main__":
    unittest.main()
