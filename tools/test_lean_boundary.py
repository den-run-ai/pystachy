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

from check_lean_boundary import Unsupported, check_all, normalize_snapshot


ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "tools" / "lean_boundary"
CHECKER = PROJECT / ".lake" / "build" / "bin" / "pystachy-boundary"
TOOL = ROOT / "tools" / "check_lean_boundary.py"
EXAMPLE = PROJECT / "examples" / "narrowed_float.py"
STATE_EXAMPLE = PROJECT / "examples" / "guarded_state.py"
CLASS_EXAMPLE = PROJECT / "examples" / "classes_and_ints.py"

if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1" and not CHECKER.is_file():
    raise RuntimeError("Lean boundary checker is required; build tools/lean_boundary first")

# Locals that share their slot's number with an "is assigned" flag (word) or with numeric
# identity companions (total, limit), as emission.py declares them. A numeric parameter
# (limit) also receives its caller's box as an identity argument, %aidN.
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


def flagged_limit(value: Any, limit: int) -> float:
    if isinstance(value, float):
        return value
    return 0.0


print(flagged_total(2.0), flagged_total("s"), flagged_word("a", True), flagged_word("a", False))
print(flagged_limit(2.0, 3), flagged_limit("s", 3))
'''


# A small shipped library function behind dynamic json.dumps: _Writer.key reads str and float
# payloads after exact type guards (lib/_pystachy_json_any.py).
JSON_KEYS = '''# pystachy: dynamic-any
import json
from typing import Any

data: Any = {1.5: "a", "k": 2, True: None}
print(json.dumps(data))
'''


# A star call on an Any value sizes its arguments with __length_hint__, in a try statement that
# ignores TypeError (dynamic.py: dyn_length_hint). This method cannot raise: exception lowering
# leaves its call a call and drops the landing block, whose name the covered block keeps.
LENGTH_HINT = '''# pystachy: dynamic-any
from typing import Any


class Items:
    def __init__(self) -> None:
        self.i = 0

    def __iter__(self) -> "Items":
        return self

    def __next__(self) -> int:
        self.i += 1
        if self.i > 2:
            raise StopIteration
        return self.i

    def __length_hint__(self) -> int:
        return 2


def total(a: int, b: int) -> int:
    return a + b


items: Any = Items()
function: Any = total
print(function(*items))
'''


GENERIC_FAMILY = '''# pystachy: dynamic-any
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value


def family_read(value: Any) -> Any:
    if isinstance(value, Box):
        return value.value
    return None


print(family_read(None), family_read(Box(1)), family_read(Box("text")))
'''


def store(address, value, typ):
    return {"op": "mem.store", "type": "", "text": "", "immediate": 0, "descriptor": "",
            "results": [], "targets": [],
            "operands": [{"value": address, "type": "*" + typ}, {"value": value, "type": typ}]}


def instruction(op, typ="", text="", results=(), operands=(), targets=(), descriptor=""):
    return {"op": op, "type": typ, "text": text, "immediate": 0, "descriptor": descriptor,
            "results": list(results), "targets": list(targets),
            "operands": [{"value": value, "type": operand_type} for value, operand_type in operands]}


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

    @staticmethod
    def block(function, label):
        return next(block for block in function["blocks"] if block["label"] == label)

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
        self.assertEqual(candidate["schema_version"], 3)
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

    def test_unknown_instruction_is_unsupported(self):
        snapshot, function = self.selected()
        _, _, operation = self.operation(function, "scalar.bin")
        operation["op"] = "new.unmodeled.operation"
        with self.assertRaises(Unsupported):
            self.normalized(snapshot)

    def test_a_dropped_landing_block_leaves_no_edge_but_an_unwind_edge_needs_one(self):
        # Exception lowering drops a landing block no invoke reaches; the blocks it covered
        # keep its name, which then adds no edge. An unwind edge to a missing block is malformed.
        snapshot, function = self.selected()
        function["blocks"][0]["handler"] = "exception_target"
        self.assertEqual(self.normalized(snapshot), self.normalized())
        snapshot, function = self.selected()
        self.block(function, "L8")["operations"] = [
            instruction("call", "dyn", "@f.raises", [9020], targets=["L9", "exception_target"])]
        with self.assertRaisesRegex(ValueError, "unknown branch target") as caught:
            self.normalized(snapshot)
        self.assertNotIsInstance(caught.exception, Unsupported)

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

    def test_stack_tuples_are_values_and_bad_slot_declarations_are_malformed(self):
        # A stack tuple's register is a tuple value, not storage. An unknown kind, a flag that
        # is not a bool and a second declaration of one slot name are malformed.
        snapshot, function = self.selected()
        local = next(slot for slot in function["slots"] if slot["text"] == "value")
        function["slots"].append({**copy.deepcopy(local), "text": "", "type": "tuple[int,int]",
                                  "immediate": 2, "results": [9000]})
        self.block(function, "L8")["operations"][0:0] = [
            instruction("tuple.store", operands=[("%stk.9000", "tuple[int,int]"), ("0", "int"), ("1", "int")])]
        self.normalized(snapshot)
        for kind, typ in ((3, "bool"), (1, "int"), (0, "dyn")):
            with self.subTest(kind=kind, typ=typ):
                snapshot, function = self.selected()
                local = next(slot for slot in function["slots"] if slot["text"] == "value")
                function["slots"].append({**copy.deepcopy(local), "type": typ, "immediate": kind})
                with self.assertRaises(ValueError) as raised:
                    self.normalized(snapshot)
                self.assertNotIsInstance(raised.exception, Unsupported)

    def test_generators_and_box_stores_stay_outside(self):
        def generator(function):
            function["recursion"]["generator"] = True

        def suspension(function):
            self.block(function, "L9")["operations"][0:0] = [instruction("gen.promise", "%ptr", results=[9001])]

        def box_store(function):
            # an address derived from a box: only the runtime may write boxes
            self.block(function, "L9")["operations"][0:0] = [
                instruction("mach.addr", "%ptr", "int", [9002], [("%a0", "%ptr"), ("1", "int")]),
                instruction("mach.store", operands=[("%t9002", "%ptr"), ("0", "int")])]

        def chosen_box_store(function):
            # through a select, from an address computed in a block listed later (L8, which
            # dominates L9)
            late = self.block(function, "L8")
            function["blocks"].remove(late)
            function["blocks"].append(late)
            late["operations"][0:0] = [
                instruction("field.addr", "%ptr", results=[9003], operands=[("%a1", "%ptr")])]
            self.block(function, "L9")["operations"][0:0] = [
                instruction("select", "%ptr", results=[9004],
                            operands=[("true", "bool"), ("%t9003", "%ptr"), ("null", "%ptr")]),
                instruction("mach.store", operands=[("%t9004", "%ptr"), ("0", "int")])]

        for mutate in (generator, suspension, box_store, chosen_box_store):
            with self.subTest(mutate.__name__):
                snapshot, function = self.selected()
                mutate(function)
                with self.assertRaises(Unsupported):
                    self.normalized(snapshot)

    def test_tag_read_of_a_value_not_used_as_dyn_is_malformed(self):
        # Only values used as dyn get fresh tags at each definition; a guard needs one.
        snapshot, function = self.selected()
        _, _, tag = self.operation(function, "dyn.type")
        tag["operands"][0]["type"] = "%ptr"
        with self.assertRaises(ValueError) as raised:
            self.normalized(snapshot)
        self.assertNotIsInstance(raised.exception, Unsupported)

    def test_payload_unpack_must_match_the_guarded_projection(self):
        snapshot, function = self.selected()
        _, _, unpack = self.operation(function, "slot.unpack")
        unpack["type"] = "int"
        with self.assertRaisesRegex(ValueError, "invalid slot.unpack shape"):
            self.normalized(snapshot)

    def test_payload_bits_cannot_escape_through_opaque_transport(self):
        # A forged operand annotation must not hide the projection's raw slot.
        for kind in ("call", "select", "phi", "mem.store", "scalar.cast"):
            with self.subTest(kind=kind):
                snapshot, function = self.selected()
                block, index, payload = self.operation(function, "dyn.payload")
                bits = f"%t{payload['results'][1]}"
                block["operations"].insert(index + 1, instruction(
                    kind, "int", text="opaque", results=[9030], operands=[(bits, "int")]))
                with self.assertRaisesRegex(Unsupported, "direct slot.unpack"):
                    self.normalized(snapshot)

    def test_payload_internal_address_cannot_escape(self):
        snapshot, function = self.selected()
        block, index, payload = self.operation(function, "dyn.payload")
        address = f"%t{payload['results'][0]}"
        block["operations"].insert(index + 1, instruction(
            "mach.load", "int", results=[9030], operands=[(address, "%ptr")]))
        with self.assertRaisesRegex(ValueError, "internal address cannot be used"):
            self.normalized(snapshot)

    def test_payload_unpack_cannot_launder_its_operand_type(self):
        snapshot, function = self.selected()
        _, _, unpack = self.operation(function, "slot.unpack")
        unpack["operands"][0]["type"] = "int"
        with self.assertRaisesRegex(ValueError, "unpack requires a slot operand"):
            self.normalized(snapshot)

    def test_unreachable_and_unlabeled_blocks_are_omitted(self):
        snapshot, function = self.selected()
        _, _, payload = self.operation(function, "dyn.payload")
        unguarded = {**copy.deepcopy(payload), "results": [9030, 9031]}
        function["blocks"] += [{"label": "", "handler": "", "operations": [instruction("br", targets=["L9"])]},
                               {"label": "dead", "handler": "", "operations": [
                                   unguarded, instruction("br", targets=["L9"])]}]
        candidate, metadata = normalize_snapshot(snapshot, "narrowed_float")
        self.assertEqual(metadata["omitted_blocks"], 2)
        self.assertEqual(candidate, self.normalized())

    def test_check_needs_its_error_block(self):
        snapshot, function = self.selected()
        self.block(function, "L8")["operations"] = [
            instruction("check", text="ValueError: no", operands=[("%t6", "bool")], targets=["L9"])]
        with self.assertRaises(Unsupported):
            self.normalized(snapshot)
        function["check_targets"] = {"ValueError: no": "L9"}
        self.normalized(snapshot)

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

    def test_cross_block_comparison_guards_its_value_and_slot_until_a_store(self):
        snapshot, function = self.selected()
        block, index, branch = self.operation(function, "cbr")
        split = {"label": "split_guard", "handler": "", "operations": [copy.deepcopy(branch)]}
        function["blocks"].insert(1, split)
        block["operations"][index] = instruction("br", targets=["split_guard"])
        # (the compared box, defined before the comparison, is unchanged where its result is used)
        self.assertTrue(self.check(self.normalized(snapshot)))
        # A store into the slot it was loaded from, before the branch, ends their pairing: the
        # payload's reload of the slot then has no fact.
        _, _, load = self.operation(function, "mem.load")
        split["operations"].insert(0, store(load["operands"][0]["value"], "%a1", "dyn"))
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
            _, _, unpack = self.operation(function, "slot.unpack")
            unpack["type"] = "bool"
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

    def test_null_store_gives_an_unknown_tag(self):
        # An unbound local or an identity box not made yet holds null, which has no tag.
        snapshot, function = self.selected()
        slots = {slot["text"]: f"%{slot['text']}.{slot['results'][0]}" for slot in function["slots"]}
        payload_block, _, _ = self.operation(function, "dyn.payload")
        payload_block["operations"][0:0] = [store(slots["other"], "null", "dyn")]
        self.assertTrue(self.check(self.normalized(snapshot)))
        payload_block["operations"][0:0] = [store(slots["value"], "null", "dyn")]
        self.assertFalse(self.check(self.normalized(snapshot)))

    def test_calls_keep_private_slots_but_their_dynamic_results_are_unknown(self):
        snapshot, function = self.selected()
        payload_block, index, payload = self.operation(function, "dyn.payload")
        payload_block["operations"][0:0] = [
            instruction("call", "dyn", "@f.anything", [9010], [("%a1", "dyn")]),
            instruction("rt", "None", "anything", operands=[("%t9010", "dyn")])]
        self.assertTrue(self.check(self.normalized(snapshot)))
        payload["operands"][0]["value"] = "%t9010"
        self.assertFalse(self.check(self.normalized(snapshot)))

    def test_a_slot_whose_address_escapes_loses_its_guard(self):
        # A callee given the slot's address may store into it: reloads get unknown tags.
        for label in ("entry", "L9"):
            with self.subTest(escape_in=label):
                snapshot, function = self.selected()
                load = next(op for op in function["blocks"][0]["operations"] if op["op"] == "mem.load")
                address = copy.deepcopy(load["operands"][0])
                block = self.block(function, label)
                block["operations"].insert(len(block["operations"]) - 1, instruction(
                    "call", "None", "@f.writer", operands=[(address["value"], address["type"])]))
                candidate, metadata = normalize_snapshot(snapshot, "narrowed_float")
                self.assertEqual(metadata["escaped_slots"], 1)
                self.assertFalse(self.check(candidate))

    def test_check_switch_invoke_and_landing_edges_are_followed(self):
        # From L8, where the tag is not float, each form below can reach the payload in L7.
        def check(function):
            self.block(function, "L8")["operations"] = [
                instruction("check", text="ValueError: no", operands=[("true", "bool")], targets=["L9"])]
            function["check_targets"] = {"ValueError: no": "L7"}

        def switch(function):
            self.block(function, "L8")["operations"] = [
                instruction("switch", operands=[("0", "int"), ("1", "int")], targets=["L9", "L7"])]

        def invoke(function):
            self.block(function, "L8")["operations"] = [
                instruction("call", "dyn", "@f.raises", [9020], targets=["L9", "L7"])]

        def covered(function):
            # every point of a block a try statement covers may reach its landing block
            self.block(function, "L8")["handler"] = "L7"

        def throw(function):
            self.block(function, "L8")["operations"] = [
                instruction("throw", operands=[("null", "exc")], targets=["L7"])]

        for mutate in (check, switch, invoke, covered, throw):
            with self.subTest(mutate.__name__):
                snapshot, function = self.selected()
                mutate(function)
                self.assertFalse(self.check(self.normalized(snapshot)))
                # the same forms, with every edge leading away from the payload, are accepted
                for block in function["blocks"]:
                    block["handler"] = "L9" if block["handler"] else ""
                    last = block["operations"][-1]
                    if block["label"] == "L8":
                        last["targets"] = ["L9"] * len(last["targets"])
                function["check_targets"] = {key: "L9" for key in function.get("check_targets", {})}
                self.assertTrue(self.check(self.normalized(snapshot)))

    def test_certificate_cannot_seed_entry_or_cycle(self):
        candidate = self.normalized()
        candidate["certificate"][candidate["program"]["entry"]] = [["%a0", ["@pys_dyntype_float"]]]
        self.assertFalse(self.check(candidate))
        circular = {"schema_version": 2, "program": {"entry": 0, "nodes": [
            {"op": "jump", "next": 1},
            {"op": "payload", "value": "x", "tags": ["float"], "next": 1}]},
            "certificate": [[], [["x", ["float"]]]]}
        self.assertFalse(self.check(circular))

    def test_checker_schema_and_input_limits_fail_closed(self):
        too_large = {"schema_version": 2, "program": {"entry": 0, "nodes": [{"op": "stop"}] * 16385},
                     "certificate": []}
        def read(tags):
            return {"schema_version": 2, "program": {"entry": 0, "nodes": [
                {"op": "payload", "value": "x", "tags": tags, "next": 1}, {"op": "stop"}]},
                "certificate": [[], []]}
        # (an empty or repeating set of accepted tags is malformed, not merely unprovable)
        for candidate in ({}, {**self.normalized(), "schema_version": 1},
                          {**self.normalized(), "ignored": "field"}, too_large, read([]), read(["a", "a"])):
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
            facts.append([slot, ["@pys_dyntype_bool"]])
        self.assertFalse(self.check(candidate))

    def test_string_and_bool_payloads_reject_wrong_descriptor(self):
        for name, wrong_tag in (("boundary_bool", "str"), ("boundary_str", "bool")):
            with self.subTest(function=name):
                snapshot, function = self.selected(name)
                _, _, payload = self.operation(function, "dyn.payload")
                payload["text"] = wrong_tag
                _, _, unpack = self.operation(function, "slot.unpack")
                unpack["type"] = wrong_tag
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

    def test_real_flags_and_companions_are_named_not_malformed(self):
        for name, shared in (("flagged_total", {("total", 0), ("total.box", 0), ("total.boxgen", 0)}),
                             ("flagged_word", {("word", 0), ("word", 1)}),
                             ("flagged_limit", {("limit", 0), ("limit.box", 0), ("limit.boxgen", 0)})):
            with self.subTest(function=name):
                function = next(fn for fn in self.snapshot["functions"] if fn["name"] == name)
                by_number = {}
                for slot in function["slots"]:
                    by_number.setdefault(slot["results"][0], set()).add((slot["text"], slot["immediate"]))
                # (if the compiler stops sharing these numbers, this case no longer tests them)
                self.assertIn(shared, by_number.values())
        candidate, metadata = normalize_snapshot(self.snapshot, "flagged_word")
        self.assertGreater(metadata["threaded_edges"], 0)
        # (flagged_total stores null in its float's identity box before boxing it)
        normalize_snapshot(self.snapshot, "flagged_total")

    @unittest.skipUnless(CHECKER.is_file(), "build tools/lean_boundary to run the proved checker")
    def test_short_circuit_guard_accepts_only_through_its_known_edges(self):
        for name in ("flagged_word", "flagged_total", "flagged_limit"):
            completed = subprocess.run(
                [sys.executable, str(TOOL), "--snapshot", str(self.snapshot_path), "--function", name],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        # "flag and isinstance(word, str)": the join's phi takes the comparison from one edge and
        # the false flag from the other. Claiming either edge's value is true skips the guard.
        snapshot, function = self.selected("flagged_word")
        phi = next(op for block in function["blocks"] for op in block["operations"] if op["op"] == "phi")
        self.assertEqual(len(phi["operands"]), 2)
        for index in range(2):
            with self.subTest(incoming=phi["targets"][index]):
                mutated = copy.deepcopy(snapshot)
                join = next(op for block in next(fn for fn in mutated["functions"] if fn["name"] == "flagged_word")["blocks"]
                            for op in block["operations"] if op["op"] == "phi")
                join["operands"][index]["value"] = "true"
                self.assertFalse(ProvedCheckerTests.check(self, self.normalized(mutated, "flagged_word")))


    def test_identity_arguments_are_unknown_only_for_numeric_parameters(self):
        # %aidN may be null, so it starts with no known tag. Its real numeric
        # argument is accepted; another parameter's number or a non-box type is malformed.
        self.normalized(function="flagged_limit")
        for field, value, message in (("value", "%aid0", "undefined operand"),
                                      ("type", "int", "identity argument has wrong type")):
            with self.subTest(field=field, value=value):
                snapshot, function = self.selected("flagged_limit")
                argument = next(operand for block in function["blocks"] for op in block["operations"]
                                for operand in op["operands"] if operand["value"].startswith("%aid"))
                argument[field] = value
                with self.assertRaisesRegex(ValueError, message) as raised:
                    self.normalized(snapshot, "flagged_limit")
                self.assertNotIsInstance(raised.exception, Unsupported)

@unittest.skipUnless(CHECKER.is_file(), "build tools/lean_boundary to run the proved checker")
class ClassAndIntTests(SnapshotFixture):
    example = CLASS_EXAMPLE
    function_filter = ""
    check = ProvedCheckerTests.check

    def mutated(self, name, mutate):
        snapshot, function = self.selected(name)
        mutate(snapshot, function)
        return self.check(self.normalized(snapshot, function["symbol"]))

    def test_class_int_and_dispatch_reads_accept(self):
        for name in ("boundary_class", "boundary_int", "dyn.call.label.0"):
            with self.subTest(function=name):
                self.assertTrue(self.check(self.normalized(function=self.selected(name)[1]["symbol"])))

    def test_isinstance_of_a_class_needs_its_none_exclusion(self):
        # pys_dyn_isa also admits None, which the compiled test excludes with a second comparison.
        def drop_none_test(snapshot, function):
            _, _, both = self.operation(function, "scalar.bin")
            self.assertEqual(both["text"], "and")
            for operand in both["operands"]:
                definition = next(op for block in function["blocks"] for op in block["operations"]
                                  if op["results"] and f"%t{op['results'][0]}" == operand["value"])
                if definition["op"] == "ptr.cmp":
                    operand["value"] = "true"
        self.assertFalse(self.mutated("boundary_class", drop_none_test))

    def test_a_base_class_test_does_not_prove_a_subclass_read(self):
        def read_subclass(snapshot, function):
            _, _, payload = self.operation(function, "dyn.payload")
            payload["text"] = "Sub"
            _, _, unpack = self.operation(function, "slot.unpack")
            unpack["type"] = "Sub"
        self.assertFalse(self.mutated("boundary_class", read_subclass))

    def test_int_read_accepts_bool_but_not_another_tag(self):
        def float_instead_of_bool(snapshot, function):
            for block in function["blocks"]:
                for op in block["operations"]:
                    for operand in op["operands"]:
                        if operand["value"] == "@pys_dyntype_bool":
                            operand["value"] = "@pys_dyntype_float"
        self.assertFalse(self.mutated("boundary_int", float_instead_of_bool))

        def read_as_bool(snapshot, function):
            block, index, payload = self.operation(function, "dyn.payload")
            # Add a well-shaped bool projection under the existing int-or-bool
            # guard. Even an unused read must satisfy its exact tag obligation.
            block["operations"].insert(index, {**copy.deepcopy(payload),
                                              "text": "bool", "results": [9030, 9031]})
        self.assertFalse(self.mutated("boundary_int", read_as_bool))

    def test_int_payload_cannot_be_reannotated_as_a_pointer(self):
        snapshot, function = self.selected("boundary_int")
        _, _, payload = self.operation(function, "dyn.payload")
        bits = f"%t{payload['results'][1]}"
        use = next(operand for block in function["blocks"] for op in block["operations"]
                   for operand in op["operands"] if operand["value"] == bits)
        use["type"] = "%ptr"
        with self.assertRaisesRegex(ValueError, "int bits require an int operand"):
            self.normalized(snapshot, "boundary_int")

    def test_int_payload_allows_only_the_runtime_box_slot_argument(self):
        for kind, prefix in (("box", []), ("ubox", [("1", "int")])):
            with self.subTest(constructor=kind):
                snapshot, function = self.selected("boundary_int")
                block, index, payload = self.operation(function, "dyn.payload")
                bits = f"%t{payload['results'][1]}"
                constructor = instruction("rt", "%ptr", text=kind, results=[9030],
                                          operands=prefix + [(bits, "*T")])
                block["operations"].insert(index + 1, constructor)
                self.assertTrue(self.check(self.normalized(snapshot, "boundary_int")))
                constructor["text"] = "opaque"
                with self.assertRaisesRegex(ValueError, "int bits require an int operand"):
                    self.normalized(snapshot, "boundary_int")

    def test_dispatch_cases_select_their_own_class(self):
        def swap_cases(snapshot, function):
            _, _, switch = self.operation(function, "switch")
            switch["targets"][1:] = switch["targets"][:0:-1]
        self.assertFalse(self.mutated("dyn.call.label.0", swap_cases))

        def read_another_word(snapshot, function):
            _, _, address = self.operation(function, "mach.addr")
            address["operands"][1]["value"] = "2"
        self.assertFalse(self.mutated("dyn.call.label.0", read_another_word))

        def renumber_subclass(snapshot, function):
            # (the class number the case names now belongs to no descriptor)
            next(t for t in snapshot["dynamic_types"] if t["symbol"] == "@dt.Sub")["cls"] = 7
        with self.assertRaisesRegex(ValueError, "descriptor and class layout disagree"):
            self.mutated("dyn.call.label.0", renumber_subclass)

    def test_descriptor_table_is_required_and_validated(self):
        snapshot, function = self.selected("dyn.call.label.0")
        del snapshot["dynamic_types"]
        with self.assertRaisesRegex(Unsupported, "dynamic_types"):
            self.normalized(snapshot, function["symbol"])
        for corrupt in (lambda types: types.append(dict(types[0])),
                        lambda types: types[0].update(base=types[1]["symbol"]),
                        lambda types: types[1].update(base="@dt.Missing"),
                        lambda types: types[0].update(symbol="@pys_dyntype_int")):
            snapshot, function = self.selected("dyn.call.label.0")
            corrupt(snapshot["dynamic_types"])
            with self.subTest(table=snapshot["dynamic_types"]), self.assertRaises(ValueError):
                self.normalized(snapshot, function["symbol"])


@unittest.skipUnless(CHECKER.is_file(), "build tools/lean_boundary to run the proved checker")
class GenericFamilyTests(SnapshotFixture):
    function_filter = ""
    check = ProvedCheckerTests.check

    @classmethod
    def setUpClass(cls):
        source = tempfile.TemporaryDirectory()
        cls.addClassCleanup(source.cleanup)
        cls.example = Path(source.name) / "generic_family.py"
        cls.example.write_text(GENERIC_FAMILY)
        super().setUpClass()

    def test_family_membership_preserves_separate_payload_guards(self):
        report, status = check_all(self.snapshot, CHECKER)
        self.assertEqual(status, 0, report)
        self.assertGreater(report["totals"]["reads"], 0)
        for name in ("family_read", "dyn.isinstance.Box"):
            candidate, metadata = normalize_snapshot(self.snapshot, name)
            self.assertEqual(metadata["payloads"], 0)
            self.assertTrue(self.check(candidate))

    def test_family_guard_cannot_justify_a_concrete_specialization_read(self):
        payloads = [entry["payload"] for entry in self.snapshot["dynamic_types"]
                    if entry["kind"] == 8 and entry["payload"].startswith("Box-")]
        self.assertEqual(len(payloads), 2)
        for payload_type in payloads:
            with self.subTest(payload=payload_type):
                snapshot, function = self.selected("family_read")
                _, _, branch = self.operation(function, "cbr")
                success = self.block(function, branch["targets"][0])
                success["operations"].insert(0, instruction(
                    "dyn.payload", "%slot", text=payload_type, results=[9030, 9031],
                    operands=[("%a0", "dyn")]))
                self.assertFalse(self.check(self.normalized(snapshot, "family_read")))


class LibraryFunctionTests(SnapshotFixture):
    function_filter = "_Writer.key"
    symbol = "@m._pystachy_json_any$_Writer.key"

    @classmethod
    def setUpClass(cls):
        source = tempfile.TemporaryDirectory()
        cls.addClassCleanup(source.cleanup)
        cls.example = Path(source.name) / "json_keys.py"
        cls.example.write_text(JSON_KEYS)
        super().setUpClass()

    def test_shipped_json_key_writer_normalizes(self):
        _, metadata = normalize_snapshot(self.snapshot, self.symbol)
        self.assertEqual(metadata["payloads"], 2)
        # (each type test also guards the slot its box was loaded from, which the reads reload)
        self.assertGreaterEqual(metadata["paired_guards"], 2)

    @unittest.skipUnless(CHECKER.is_file(), "build tools/lean_boundary to run the proved checker")
    def test_shipped_json_key_writer_is_accepted_and_needs_both_guards(self):
        self.assertTrue(ProvedCheckerTests.check(self, normalize_snapshot(self.snapshot, self.symbol)[0]))
        snapshot = copy.deepcopy(self.snapshot)
        function = next(fn for fn in snapshot["functions"] if fn["symbol"] == self.symbol)
        # the branches on "type(k) is str" and "type(k) is float"
        guards = [block["operations"][-1] for block in function["blocks"]
                  for op in block["operations"]
                  if op["op"] == "ptr.cmp" and op["text"] == "==" and op["results"]
                  and op["operands"][1]["value"] in {"@pys_dyntype_str", "@pys_dyntype_float"}
                  and block["operations"][-1]["op"] == "cbr"
                  and block["operations"][-1]["operands"][0]["value"] == f"%t{op['results'][0]}"]
        self.assertEqual(len(guards), 2)
        for guard in guards:
            with self.subTest(guard=guard["targets"][0]):
                original = copy.deepcopy(guard["operands"])
                guard["operands"] = [{"value": "true", "type": "bool"}]
                self.assertFalse(ProvedCheckerTests.check(self, normalize_snapshot(snapshot, self.symbol)[0]))
                guard["operands"] = original


class DroppedLandingTests(SnapshotFixture):
    function_filter = "dyn.lengthhint"

    @classmethod
    def setUpClass(cls):
        source = tempfile.TemporaryDirectory()
        cls.addClassCleanup(source.cleanup)
        cls.example = Path(source.name) / "length_hint.py"
        cls.example.write_text(LENGTH_HINT)
        super().setUpClass()

    def test_real_length_hint_keeps_a_dropped_landing_blocks_name(self):
        _, function = self.selected("dyn.lengthhint")
        labels = {block["label"] for block in function["blocks"]} | {""}
        # (if lowering stops dropping it, this case no longer tests it)
        self.assertTrue(any(block["handler"] not in labels for block in function["blocks"]))
        _, metadata = normalize_snapshot(self.snapshot, "dyn.lengthhint")
        self.assertGreater(metadata["payloads"], 0)

    @unittest.skipUnless(CHECKER.is_file(), "build tools/lean_boundary to run the proved checker")
    def test_real_length_hint_is_accepted(self):
        self.assertTrue(ProvedCheckerTests.check(self, self.normalized(function="dyn.lengthhint")))


@unittest.skipUnless(CHECKER.is_file(), "build tools/lean_boundary to run the proved checker")
class WholeSnapshotTests(SnapshotFixture):
    example = CLASS_EXAMPLE
    function_filter = ""

    def reads(self):
        found = {fn["symbol"]: sum(op["op"] == "dyn.payload" for block in fn["blocks"] for op in block["operations"])
                 for fn in self.snapshot["functions"]}
        return {symbol: count for symbol, count in found.items() if count}

    def test_all_checks_every_function_that_reads_a_payload(self):
        completed = subprocess.run(
            [sys.executable, str(TOOL), "--snapshot", str(self.snapshot_path), "--all", "--checker", str(CHECKER)],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        report = json.loads(completed.stdout)
        reads = self.reads()
        self.assertGreaterEqual(len(reads), 3)
        self.assertEqual({fn["function"]: fn["reads"] for fn in report["functions"]}, reads)
        self.assertEqual((report["status"], report["checked"]), ("accepted", True))
        self.assertEqual(report["totals"]["functions"], len(self.snapshot["functions"]))
        self.assertEqual(report["totals"]["proved_reads"], sum(reads.values()))
        self.assertEqual(report["snapshot_sha256"], hashlib.sha256(self.snapshot_path.read_bytes()).hexdigest())

    def test_the_worst_function_decides_the_status(self):
        def unguarded(function):
            # (its isinstance test now names float, so nothing guards its int read)
            for block in function["blocks"]:
                for op in block["operations"]:
                    for operand in op["operands"]:
                        if operand["value"] in ("@pys_dyntype_int", "@pys_dyntype_bool"):
                            operand["value"] = "@pys_dyntype_float"

        def unmodeled(function):
            next(op for block in function["blocks"] for op in block["operations"]
                 if op["op"] == "mem.load")["op"] = "new.unmodeled.operation"

        def malformed(function):
            operations = [op for block in function["blocks"] for op in block["operations"] if op["results"]]
            operations[1]["results"] = list(operations[0]["results"])

        for changes, status, code in (((), "accepted", 0),
                                      ((("boundary_int", unguarded),), "rejected", 1),
                                      ((("boundary_class", unmodeled),), "unsupported", 2),
                                      ((("boundary_int", unguarded), ("boundary_class", unmodeled)), "rejected", 1),
                                      ((("boundary_int", unguarded), ("dyn.call.label.0", malformed)), "error", 3)):
            with self.subTest(changes=[name for name, _ in changes]):
                snapshot = copy.deepcopy(self.snapshot)
                symbols = {}
                for name, change in changes:
                    function = next(fn for fn in snapshot["functions"] if fn["name"] == name)
                    change(function)
                    symbols[function["symbol"]] = change
                fields, result = check_all(snapshot, CHECKER)
                self.assertEqual((fields["status"], result), (status, code))
                # (checked: Lean ran on every function that reads a payload)
                self.assertEqual(fields["checked"], all(change is unguarded for _, change in changes))
                for record in fields["functions"]:
                    expected = {unguarded: "rejected", unmodeled: "unsupported", malformed: "error"}.get(
                        symbols.get(record["function"]), "accepted")
                    self.assertEqual(record["status"], expected, record)

    def test_all_writes_no_candidate(self):
        target = self.directory / "never-written.json"
        completed = subprocess.run(
            [sys.executable, str(TOOL), "--snapshot", str(self.snapshot_path), "--all", "--emit", str(target)],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
        self.assertFalse(target.exists())


class SnapshotHeaderTests(unittest.TestCase):
    """--all reads a snapshot's header before its functions: a snapshot with no payload read
    passes only as a completed typed-after snapshot of this schema."""

    @staticmethod
    def run_all(snapshot):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "typed-after.json"
            path.write_text(json.dumps(snapshot))
            completed = subprocess.run([sys.executable, str(TOOL), "--snapshot", str(path), "--all"],
                                       capture_output=True, text=True, timeout=30)
        return completed.returncode, json.loads(completed.stdout)

    def test_only_a_completed_typed_after_snapshot_passes_without_reads(self):
        header = {"schema_version": 1, "stage": "typed-after", "status": "completed", "functions": []}
        for change, status, code in (({}, "accepted", 0), ({"status": "partial"}, "unsupported", 2),
                                     ({"status": "failed"}, "unsupported", 2),
                                     ({"stage": "typed-before"}, "unsupported", 2),
                                     ({"schema_version": 2}, "error", 3), ({"schema_version": True}, "error", 3)):
            with self.subTest(change=change):
                result, report = self.run_all({**header, **change})
                self.assertEqual((result, report["status"], report["checked"]), (code, status, code == 0), report)
                if code == 0:
                    self.assertEqual(report["totals"]["payload_functions"], 0)

    def test_check_all_reads_the_header_first(self):
        header = {"schema_version": 1, "stage": "typed-after", "status": "completed", "functions": []}
        for change, error in (({"status": "partial"}, Unsupported), ({"schema_version": 2}, ValueError)):
            with self.subTest(change=change), self.assertRaises(error):
                check_all({**header, **change})



if __name__ == "__main__":
    unittest.main()
