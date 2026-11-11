"""Check the real-IR bridge and independently corrupt its proof obligations."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from check_lean_boundary import Unsupported, normalize_snapshot


ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "tools" / "lean_boundary"
CHECKER = PROJECT / ".lake" / "build" / "bin" / "pystachy-boundary"
TOOL = ROOT / "tools" / "check_lean_boundary.py"
EXAMPLE = PROJECT / "examples" / "narrowed_float.py"
STATE_EXAMPLE = PROJECT / "examples" / "guarded_state.py"

if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1" and not CHECKER.is_file():
    raise RuntimeError("Lean boundary checker is required; build tools/lean_boundary first")

# Locals that share their slot's number with an "is assigned" flag (word) or with numeric
# identity companions (total), as emission.py declares them.
SHARED_SLOTS = '''# pystachy: dynamic-any
from typing import Any


def flagged_total(value: Any) -> float:
    total = 0.0
    if isinstance(value, float):
        total = value + 1.0
    return total


def flagged_word(value: Any, flag: bool) -> str:
    if flag:
        word: Any = value
    if flag and isinstance(word, str):
        return word
    return ""


print(flagged_total(2.0), flagged_total("s"), flagged_word("a", True), flagged_word("a", False))
'''


def store(address, value, typ):
    return {"op": "mem.store", "type": "", "text": "", "immediate": 0, "descriptor": "",
            "results": [], "targets": [],
            "operands": [{"value": address, "type": "*" + typ}, {"value": value, "type": typ}]}


class SnapshotFixture(unittest.TestCase):
    example = EXAMPLE
    function_filter = "float"

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        output = cls.directory / "inspection"
        env = {key: value for key, value in os.environ.items()
               if not key.startswith("PYSTACHY_")}
        env["PYSTACHY_HOME"] = str(ROOT)
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "inspect_compiler.py"), str(cls.example),
             "--output", str(output), "--function", cls.function_filter],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=40,
        )
        if completed.returncode:
            raise AssertionError(completed.stdout + completed.stderr)
        cls.snapshot_path = output / "typed-after.json"
        cls.snapshot = json.loads(cls.snapshot_path.read_text())

    def selected(self, name="narrowed_float"):
        snapshot = copy.deepcopy(self.snapshot)
        function = next(fn for fn in snapshot["functions"] if fn["name"] == name)
        return snapshot, function

    @staticmethod
    def operation(function, name):
        return next((block, index, operation) for block in function["blocks"]
                    for index, operation in enumerate(block["operations"])
                    if operation["op"] == name)

    def normalized(self, snapshot=None, function="narrowed_float"):
        return normalize_snapshot(self.snapshot if snapshot is None else snapshot, function)[0]

    def with_shared_slots(self):
        # The flag and identity companions of `value`, under its number, each written before
        # its guard. Lowering names them by text and kind: %value.def.N, %value.box.N, ...
        snapshot, function = self.selected()
        local = next(slot for slot in function["slots"] if slot["text"] == "value")
        number = local["results"][0]
        for text, typ, kind in (("value", "bool", 1), ("value.box", "dyn", 0), ("value.boxgen", "int", 0)):
            function["slots"].append({**copy.deepcopy(local), "text": text, "type": typ, "immediate": kind})
        function["blocks"][0]["operations"][0:0] = [
            store(f"%value.def.{number}", "true", "bool"), store(f"%value.box.{number}", "%a1", "dyn"),
            store(f"%value.boxgen.{number}", "1", "int")]
        return snapshot, function, number


class AdapterTests(SnapshotFixture):
    def test_real_snapshot_is_not_modified_and_contains_projection(self):
        original = copy.deepcopy(self.snapshot)
        candidate = self.normalized()
        self.assertEqual(self.snapshot, original)
        self.assertEqual(candidate["schema_version"], 1)
        self.assertTrue(any(node["op"] == "payload" for node in candidate["program"]["nodes"]))
        self.assertEqual(len(candidate["program"]["nodes"]), len(candidate["certificate"]))
        self.assertEqual(candidate["certificate"][candidate["program"]["entry"]], [])

    def test_unknown_function_and_ambiguous_name_are_rejected(self):
        with self.assertRaises((Unsupported, ValueError)):
            self.normalized(function="not_a_function")
        snapshot, function = self.selected()
        duplicate = copy.deepcopy(function)
        duplicate["symbol"] += ".duplicate"
        snapshot["functions"].append(duplicate)
        with self.assertRaises((Unsupported, ValueError)):
            self.normalized(snapshot)

    def test_partial_or_unknown_schema_is_not_accepted(self):
        for field, value in (("status", "partial"), ("schema_version", 2),
                             ("schema_version", True), ("stage", "typed-before")):
            with self.subTest(field=field, value=value):
                snapshot = copy.deepcopy(self.snapshot)
                snapshot[field] = value
                with self.assertRaises((Unsupported, ValueError)):
                    self.normalized(snapshot)

    def test_unknown_instruction_or_exception_handler_is_unsupported(self):
        snapshot, function = self.selected()
        _, _, operation = self.operation(function, "scalar.bin")
        operation["op"] = "new.unmodeled.operation"
        with self.assertRaises(Unsupported):
            self.normalized(snapshot)
        snapshot, function = self.selected()
        function["blocks"][0]["handler"] = "exception_target"
        with self.assertRaises(Unsupported):
            self.normalized(snapshot)

    def test_missing_target_or_duplicate_result_is_malformed(self):
        snapshot, function = self.selected()
        _, _, branch = self.operation(function, "cbr")
        branch["targets"][0] = "not_a_block"
        with self.assertRaises(ValueError):
            self.normalized(snapshot)
        snapshot, function = self.selected()
        _, _, load = self.operation(function, "mem.load")
        _, _, tag = self.operation(function, "dyn.type")
        tag["results"] = list(load["results"])
        with self.assertRaises(ValueError):
            self.normalized(snapshot)

    def test_slots_sharing_a_local_number_are_named_by_text_and_kind(self):
        snapshot, _, number = self.with_shared_slots()
        copies = {(node["dst"], node["src"]) for node in self.normalized(snapshot)["program"]["nodes"]
                  if node["op"] == "copy"}
        self.assertIn((f"%value.box.{number}", "%a1"), copies)
        self.assertIn((f"%value.{number}", "%a0"), copies)

    def test_slot_kinds_outside_the_prototype_or_malformed(self):
        # A stack tuple is outside the prototype. An unknown kind, a flag that is not a bool
        # and a second declaration of one slot name are malformed.
        for kind, typ, text, unsupported in ((2, "tuple[int,int]", "", True), (3, "bool", "value", False),
                                             (1, "int", "value", False), (0, "dyn", "value", False)):
            with self.subTest(kind=kind, typ=typ):
                snapshot, function = self.selected()
                local = next(slot for slot in function["slots"] if slot["text"] == "value")
                function["slots"].append({**copy.deepcopy(local), "text": text, "type": typ, "immediate": kind})
                with self.assertRaises(ValueError) as raised:
                    self.normalized(snapshot)
                self.assertEqual(isinstance(raised.exception, Unsupported), unsupported, raised.exception)

    def test_malformed_parameter_reports_structured_error(self):
        snapshot, function = self.selected()
        function["parameters"][0]["representation"] = []
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "malformed.json"
            source.write_text(json.dumps(snapshot))
            completed = subprocess.run(
                [sys.executable, str(TOOL), "--snapshot", str(source),
                 "--function", "narrowed_float"], capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(completed.returncode, 3, completed.stdout + completed.stderr)
            self.assertEqual(json.loads(completed.stdout)["status"], "error")
            self.assertNotIn("Traceback", completed.stderr)

    def test_emit_never_claims_checker_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "candidate.json"
            completed = subprocess.run(
                [sys.executable, str(TOOL), "--snapshot", str(self.snapshot_path),
                 "--function", "narrowed_float", "--emit", str(output)],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            report = json.loads(completed.stdout)
            self.assertEqual(report["status"], "prepared")
            self.assertFalse(report["checked"])
            self.assertEqual(json.loads(output.read_text()), self.normalized())

    def test_missing_checker_is_an_error(self):
        completed = subprocess.run(
            [sys.executable, str(TOOL), "--snapshot", str(self.snapshot_path),
             "--function", "narrowed_float", "--checker", str(self.directory / "missing")],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(completed.returncode, 3, completed.stdout + completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["status"], "error")


@unittest.skipUnless(CHECKER.is_file(), "build tools/lean_boundary to run the proved checker")
class ProvedCheckerTests(SnapshotFixture):
    def check(self, candidate):
        completed = subprocess.run([str(CHECKER)], input=json.dumps(candidate),
                                   capture_output=True, text=True, timeout=10)
        self.assertIn(completed.returncode, (0, 1), completed.stdout + completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["accepted"], completed.returncode == 0)
        return result["accepted"]

    def rejected_mutation(self, mutate):
        snapshot, function = self.selected()
        mutate(function)
        self.assertFalse(self.check(self.normalized(snapshot)))

    def test_real_guard_and_nested_branch_accept(self):
        self.assertTrue(self.check(self.normalized()))
        self.assertTrue(self.check(self.normalized(function="nested_float")))

    def test_equivalent_tag_comparisons_accept(self):
        for reverse_operands, invert_predicate in ((True, False), (False, True), (True, True)):
            with self.subTest(reverse_operands=reverse_operands, invert_predicate=invert_predicate):
                snapshot, function = self.selected()
                _, _, comparison = self.operation(function, "ptr.cmp")
                if reverse_operands:
                    comparison["operands"].reverse()
                if invert_predicate:
                    comparison["text"] = "!="
                    _, _, branch = self.operation(function, "cbr")
                    branch["targets"].reverse()
                self.assertTrue(self.check(self.normalized(snapshot)))

    def test_unrelated_slot_store_does_not_invalidate_guard(self):
        snapshot, function = self.selected()
        block, index, _ = self.operation(function, "cbr")
        unrelated = next(op for op in block["operations"] if op["op"] == "mem.store"
                         and op["operands"][1]["value"] == "%a1")
        block["operations"].insert(index, copy.deepcopy(unrelated))
        self.assertTrue(self.check(self.normalized(snapshot)))

    def test_cross_block_comparison_does_not_invent_guard(self):
        snapshot, function = self.selected()
        block, index, branch = self.operation(function, "cbr")
        function["blocks"].insert(1, {"label": "split_guard", "handler": "",
                                      "operations": [copy.deepcopy(branch)]})
        block["operations"][index] = {"op": "br", "type": "", "text": "", "immediate": 0,
                                      "descriptor": "", "results": [], "operands": [],
                                      "targets": ["split_guard"]}
        self.assertFalse(self.check(self.normalized(snapshot)))

    def test_guard_survives_shared_slot_numbers_but_never_proves_the_companion_box(self):
        snapshot, function, number = self.with_shared_slots()
        self.assertTrue(self.check(self.normalized(snapshot)))
        block, index, payload = self.operation(function, "dyn.payload")
        block["operations"].insert(index, {
            "op": "mem.load", "type": "dyn", "text": "", "immediate": 0, "descriptor": "",
            "results": [9999], "targets": [],
            "operands": [{"value": f"%value.box.{number}", "type": "*dyn"}]})
        payload["operands"][0]["value"] = "%t9999"
        self.assertFalse(self.check(self.normalized(snapshot)))

    def test_wrong_value_and_wrong_tag_reject(self):
        def wrong_value(function):
            _, _, payload = self.operation(function, "dyn.payload")
            payload["operands"][0]["value"] = "%a1"
        self.rejected_mutation(wrong_value)

        def wrong_tag(function):
            _, _, payload = self.operation(function, "dyn.payload")
            payload["text"] = "bool"
        self.rejected_mutation(wrong_tag)

    def test_missing_guard_and_reversed_edges_reject(self):
        def missing_guard(function):
            _, _, branch = self.operation(function, "cbr")
            branch["operands"] = [{"value": "true", "type": "bool"}]
        self.rejected_mutation(missing_guard)

        def reversed_edges(function):
            _, _, branch = self.operation(function, "cbr")
            branch["targets"].reverse()
        self.rejected_mutation(reversed_edges)

    def test_rebinding_after_guard_or_between_compare_and_branch_rejects(self):
        def assignment(function):
            _, _, load = self.operation(function, "mem.load")
            return {"op": "mem.store", "type": "", "text": "", "immediate": 0,
                    "descriptor": "", "results": [], "targets": [],
                    "operands": [copy.deepcopy(load["operands"][0]),
                                 {"value": "%a1", "type": "dyn"}]}

        def after_guard(function):
            block, _, _ = self.operation(function, "dyn.payload")
            block["operations"].insert(0, assignment(function))
        self.rejected_mutation(after_guard)

        def before_branch(function):
            block, index, _ = self.operation(function, "cbr")
            block["operations"].insert(index, assignment(function))
        self.rejected_mutation(before_branch)

    def test_join_without_guard_rejects(self):
        snapshot, function = self.selected()
        _, _, branch = self.operation(function, "cbr")
        false_block = next(block for block in function["blocks"]
                           if block["label"] == branch["targets"][1])
        old_target = false_block["operations"][-1]["targets"][0]
        false_block["operations"][-1]["targets"] = branch["targets"][:1]
        function["blocks"] = [block for block in function["blocks"] if block["label"] != old_target]
        self.assertFalse(self.check(self.normalized(snapshot)))

    def test_certificate_cannot_seed_entry_or_cycle(self):
        candidate = self.normalized()
        candidate["certificate"][candidate["program"]["entry"]] = [["%a0", "float"]]
        self.assertFalse(self.check(candidate))
        circular = {"schema_version": 1, "program": {"entry": 0, "nodes": [
            {"op": "jump", "next": 1},
            {"op": "payload", "value": "x", "tag": "float", "next": 1}]},
            "certificate": [[], [["x", "float"]]]}
        self.assertFalse(self.check(circular))

    def test_checker_schema_and_input_limits_fail_closed(self):
        too_large = {"schema_version": 1, "program": {"entry": 0, "nodes": [{"op": "stop"}] * 4097},
                     "certificate": []}
        for candidate in ({}, {**self.normalized(), "schema_version": 2},
                          {**self.normalized(), "ignored": "field"}, too_large):
            completed = subprocess.run([str(CHECKER)], input=json.dumps(candidate),
                                       capture_output=True, text=True, timeout=10)
            self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
            self.assertFalse(json.loads(completed.stdout)["accepted"])

    def test_full_cli_reports_actual_checker_result_and_input_hash(self):
        completed = subprocess.run(
            [sys.executable, str(TOOL), "--snapshot", str(self.snapshot_path),
             "--function", "narrowed_float", "--checker", str(CHECKER)],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["status"], "accepted")
        self.assertTrue(report["checked"])
        self.assertEqual(report["snapshot_sha256"], hashlib.sha256(self.snapshot_path.read_bytes()).hexdigest())
        self.assertGreater(report["payloads"], 0)


@unittest.skipUnless(CHECKER.is_file(), "build tools/lean_boundary to run the proved checker")
class StateGuardTests(SnapshotFixture):
    example = STATE_EXAMPLE
    function_filter = "boundary_"
    check = ProvedCheckerTests.check

    def test_real_bool_string_copy_and_loop_accept(self):
        expected = {"boundary_bool": 1, "boundary_str": 1,
                    "boundary_copy": 2, "boundary_loop": 1}
        self.assertEqual({fn["name"] for fn in self.snapshot["functions"]}, set(expected))
        for name, payloads in expected.items():
            with self.subTest(function=name):
                candidate, metadata = normalize_snapshot(self.snapshot, name)
                self.assertEqual(metadata["payloads"], payloads)
                self.assertTrue(self.check(candidate))

    def test_saved_copy_survives_rebinding_but_reloaded_original_does_not(self):
        snapshot, function = self.selected("boundary_copy")
        branches = [op for block in function["blocks"] for op in block["operations"]
                    if op["op"] == "cbr"]
        self.assertEqual(len(branches), 2)
        # Remove the second tag proof: only the original guard and copied value
        # can justify the final read, after the original slot has changed.
        branches[1]["operands"] = [{"value": "true", "type": "bool"}]
        self.assertTrue(self.check(self.normalized(snapshot, "boundary_copy")))
        _, _, original_load = self.operation(function, "mem.load")
        payload_block = next(block for block in function["blocks"]
                             if any(op["op"] == "ret" and op["operands"]
                                    and op["operands"][0]["value"].startswith("%")
                                    for op in block["operations"]))
        reload = next(op for op in payload_block["operations"] if op["op"] == "mem.load")
        reload["operands"] = copy.deepcopy(original_load["operands"])
        self.assertFalse(self.check(self.normalized(snapshot, "boundary_copy")))

    def test_loop_rebinding_requires_rechecking_tag(self):
        snapshot, function = self.selected("boundary_loop")
        guard_block, _, branch = self.operation(function, "cbr")
        body = next(block for block in function["blocks"] if block["label"] == branch["targets"][0])
        self.assertEqual(body["operations"][-1]["targets"], [guard_block["label"]])
        # Bypassing the guard after value = other must lose the payload fact.
        body["operations"][-1]["targets"] = [body["label"]]
        self.assertFalse(self.check(self.normalized(snapshot, "boundary_loop")))
        # A forged cyclic certificate must not rescue that malformed loop.
        candidate = self.normalized(snapshot, "boundary_loop")
        _, _, load = self.operation(function, "mem.load")
        slot = load["operands"][0]["value"]
        for facts in candidate["certificate"][1:]:
            facts.append([slot, "bool"])
        self.assertFalse(self.check(candidate))

    def test_string_and_bool_payloads_reject_wrong_descriptor(self):
        for name, wrong_tag in (("boundary_bool", "str"), ("boundary_str", "bool")):
            with self.subTest(function=name):
                snapshot, function = self.selected(name)
                _, _, payload = self.operation(function, "dyn.payload")
                payload["text"] = wrong_tag
                self.assertFalse(self.check(self.normalized(snapshot, name)))


class SharedSlotNumberTests(SnapshotFixture):
    function_filter = "flagged_"

    @classmethod
    def setUpClass(cls):
        source = tempfile.TemporaryDirectory()
        cls.addClassCleanup(source.cleanup)
        cls.example = Path(source.name) / "shared_slots.py"
        cls.example.write_text(SHARED_SLOTS)
        super().setUpClass()

    def test_real_flags_and_companions_are_unsupported_not_malformed(self):
        for name, shared in (("flagged_total", {("total", 0), ("total.box", 0), ("total.boxgen", 0)}),
                             ("flagged_word", {("word", 0), ("word", 1)})):
            with self.subTest(function=name):
                function = next(fn for fn in self.snapshot["functions"] if fn["name"] == name)
                by_number = {}
                for slot in function["slots"]:
                    by_number.setdefault(slot["results"][0], set()).add((slot["text"], slot["immediate"]))
                # (if the compiler stops sharing these numbers, this case no longer tests them)
                self.assertIn(shared, by_number.values())
                completed = subprocess.run(
                    [sys.executable, str(TOOL), "--snapshot", str(self.snapshot_path), "--function", name],
                    capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
                self.assertEqual(json.loads(completed.stdout)["status"], "unsupported")


if __name__ == "__main__":
    unittest.main()
