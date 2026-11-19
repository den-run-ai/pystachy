"""The Lean shape checker accepts the compiler's IR and rejects each malformed shape.

Run with python3 -m unittest discover -s tools -p test_lean_boundary_shape.py.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_lean_shape as shape
import typed_ir_ops
import typed_ir_text as text
from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.loader import Loader

ROOT = Path(__file__).resolve().parent.parent
CHECKER = shape.DEFAULT_CHECKER
if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1" and not CHECKER.is_file():
    raise RuntimeError("Lean shape checker is required; build tools/lean_boundary first")
FIXTURE = ROOT / "tools/fixtures/typed_ir/score_samples.listget.after.tir"
SHAPE = "an instruction's shape, a parameter or a branch to the entry block"


def compiled(case):
    """Each function of a corpus program before the passes and as lowering takes it."""
    records = []
    optimize, lower = Gen.optimize, Gen.lower

    def passes(g, fn, on):
        records.append(text.from_ifn(fn))
        return optimize(g, fn, on)

    def lowering(g, fn):
        records.append(text.from_ifn(fn))
        lower(g, fn)

    path = next((ROOT / "tests").glob(f"programs/*/{case}"))
    with patch.object(Gen, "optimize", passes), patch.object(Gen, "lower", lowering):
        Gen().program(Loader([str(ROOT / "lib")]).program(str(path), path.read_text()))
    return records


def operations(record, label):
    return next(b for b in record["blocks"] if b["label"] == label)["operations"]


def find(record, op):
    return next(i for b in record["blocks"] for i in b["operations"] if i["op"] == op)


def run(candidate):
    done = subprocess.run([str(CHECKER)], input=json.dumps(candidate), capture_output=True, text=True, timeout=120)
    return done.returncode, json.loads(done.stdout)


class NormalizationTests(unittest.TestCase):
    """The adapter's projection needs no Lean build."""

    def setUp(self):
        self.record = text.parse_function(FIXTURE.read_text())

    def test_operands_are_classified_and_labels_interned(self):
        function = shape.candidate([self.record])["functions"][0]
        self.assertEqual(function["params"], 1)
        self.assertEqual([b["label"] for b in function["blocks"]], list(range(len(function["blocks"]))))
        entry = function["blocks"][0]["code"]
        self.assertEqual(entry[0]["a"], [[shape.SLOT, 2], [shape.PARAM, 0]])
        self.assertEqual(entry[1]["a"], [[shape.SLOT, 3], [shape.CONSTANT, 0]])
        self.assertEqual(entry[-1]["b"], [1])
        self.assertEqual(function["slots"][0], {"op": 0, "a": [], "r": [2], "b": [], "e": [], "f": 3, "j": False})
        names = [row["name"] for row in typed_ir_ops.rows()]
        self.assertEqual(names[entry[-1]["op"]], "br")

    def test_unknown_spellings_registers_and_operations_have_no_kind(self):
        entry = operations(self.record, "entry")
        entry[0]["operands"][0]["value"] = "%nosuch.2"
        entry[0]["operands"][1]["value"] = "add (i64 1, i64 2)"
        entry[1]["op"] = "raw"
        function = shape.candidate([self.record])["functions"][0]
        self.assertEqual(function["blocks"][0]["code"][0]["a"], [[shape.UNKNOWN, 2], [shape.UNKNOWN, 0]])
        self.assertEqual(function["blocks"][0]["code"][1]["op"], len(typed_ir_ops.rows()))

    def test_a_flag_register_is_its_own_slot(self):
        self.record["slots"].append({"op": "slot", "type": "bool", "text": "score", "immediate": 1, "descriptor": "",
                                     "results": [3], "operands": [], "targets": []})
        entry = operations(self.record, "entry")
        entry[1]["operands"][0]["value"] = "%score.def.3"
        self.assertEqual(shape.candidate([self.record])["functions"][0]["blocks"][0]["code"][1]["a"][0], [shape.SLOT, 3])
        entry[1]["operands"][0]["value"] = "%sample.def.16"
        self.assertEqual(shape.candidate([self.record])["functions"][0]["blocks"][0]["code"][1]["a"][0], [shape.UNKNOWN, 16])


@unittest.skipUnless(CHECKER.is_file(), "build tools/lean_boundary to run the proved shape checker")
class ShapeCheckerTests(unittest.TestCase):
    def setUp(self):
        self.record = text.parse_function(FIXTURE.read_text())

    def rejected(self, record, reason):
        verdict, accepted = shape.check([record], CHECKER)
        self.assertFalse(accepted)
        self.assertEqual(verdict["rejected"], [{"symbol": record["symbol"], "reason": reason}])

    def test_fixtures_and_compiled_programs_are_accepted(self):
        for name in ("before", "after"):
            records = text.parse_functions((FIXTURE.parent / f"score_samples.listget.{name}.tir").read_text())
            verdict, accepted = shape.check(records, CHECKER)
            self.assertTrue(accepted, verdict)
        total = 0
        for case in ("typed_ir_slots.py", "tuples_and_classes.py", "closures_more.py", "gen_basic.py", "gen_close.py",
                     "exc_as_rebind.py"):
            with self.subTest(case=case):
                records = compiled(case)
                verdict, accepted = shape.check(records, CHECKER)
                self.assertTrue(accepted, verdict["rejected"][:3])
                self.assertEqual(verdict["functions"], len(records))
                total += verdict["instructions"]
        self.assertGreater(total, 10000)

    def test_each_malformed_shape_is_rejected_for_its_reason(self):
        def twice(r):
            find(r, "num.cmp")["results"] = list(find(r, "list.len")["results"])

        def undefined(r):
            find(r, "cbr")["operands"][0]["value"] = "%t99"

        def unterminated(r):
            operations(r, "L20").pop()

        def early(r):
            operations(r, "L19").insert(0, copy.deepcopy(operations(r, "L20")[0]))

        def invoke_inside(r):
            call = {"op": "init", "type": "", "text": "m", "immediate": 0, "descriptor": "", "results": [],
                    "operands": [], "targets": ["L21", "L20"]}
            operations(r, "L19").insert(0, call)

        def missing(r):
            find(r, "cbr")["targets"][1] = "L404"

        def repeated(r):
            r["blocks"][-1]["label"] = "L20"

        def unknown(r):
            find(r, "num.cmp")["op"] = "raw"

        def operands(r):
            find(r, "cbr")["operands"].append({"value": "true", "type": "bool"})

        def labels(r):
            find(r, "cbr")["targets"].pop()

        def results(r):
            find(r, "list.load")["results"].pop()

        def field(r):
            find(r, "cbr")["text"] = "note"

        def slot_in_block(r):
            operations(r, "entry").insert(0, copy.deepcopy(r["slots"][0]))

        def code_in_slots(r):
            r["slots"].append(copy.deepcopy(operations(r, "L20")[0]))

        def instruction_text(r):
            find(r, "num.cmp")["operands"][1]["value"] = "add (i64 1, i64 2)"

        def parameter(r):
            operations(r, "entry")[0]["operands"][1]["value"] = "%a1"

        def register(r):
            operations(r, "entry")[0]["operands"][0]["value"] = "%samples.3"

        def back_to_entry(r):
            find(r, "cbr")["targets"][1] = "entry"

        def no_error_block(r):
            cbr = find(r, "cbr")
            cbr.update({"op": "check", "text": "IndexError: x", "targets": cbr["targets"][:1]})

        for change, reason in ((twice, "a value number defined twice"), (undefined, "a value that no instruction defines"),
                               (unterminated, "a block's terminator"), (early, "a block's terminator"),
                               (invoke_inside, "a block's terminator"), (missing, "a label that names no block"),
                               (repeated, "a repeated block label"), (no_error_block, "a label that names no block"),
                               (unknown, SHAPE), (operands, SHAPE), (labels, SHAPE), (results, SHAPE), (field, SHAPE),
                               (slot_in_block, SHAPE), (code_in_slots, SHAPE), (instruction_text, SHAPE),
                               (parameter, SHAPE), (register, SHAPE), (back_to_entry, SHAPE)):
            with self.subTest(change=change.__name__):
                record = copy.deepcopy(self.record)
                change(record)
                self.rejected(record, reason)

    def test_a_phi_may_name_the_entry_block_and_a_check_its_error_block(self):
        record = copy.deepcopy(self.record)
        phi = {"op": "phi", "type": "int", "text": "", "immediate": 0, "descriptor": "", "results": [40],
               "operands": [{"value": "0", "type": "int"}, {"value": "%t26", "type": "int"}], "targets": ["entry", "L8"]}
        operations(record, "L7").insert(0, phi)
        cbr = find(record, "cbr")
        cbr.update({"op": "check", "text": "IndexError: x", "targets": cbr["targets"][:1]})
        record["check_targets"]["IndexError: x"] = "L9"
        verdict, accepted = shape.check([record], CHECKER)
        self.assertTrue(accepted, verdict)

    def test_the_checker_reads_the_table_it_is_given(self):
        candidate = shape.candidate([self.record])
        self.assertEqual(run(candidate)[0], 0)
        names = [row["name"] for row in typed_ir_ops.rows()]
        for op, key, value in (("cbr", "labels", [0, 3, 3]), ("cbr", "terminator", False), ("list.load", "results", 1),
                               ("mem.load", "fields", 0), ("slot", "entry", False), ("ret", "max", 0)):
            with self.subTest(op=op, key=key):
                changed = copy.deepcopy(candidate)
                changed["table"][names.index(op)][key] = value
                status, verdict = run(changed)
                self.assertEqual((status, verdict["accepted"]), (1, False))

    def test_lean_holds_a_slot_operand_to_the_slots(self):
        candidate = shape.candidate([self.record])
        candidate["functions"][0]["blocks"][0]["code"][0]["a"][0] = [shape.SLOT, 99]
        status, verdict = run(candidate)
        self.assertEqual(status, 1)
        self.assertEqual(verdict["rejected"][0]["reason"], "a slot that the function does not hold")

    def test_malformed_candidates_fail_closed(self):
        candidate = shape.candidate([self.record])
        for change in (lambda c: c.pop("table"), lambda c: c["functions"][0].pop("params"),
                       lambda c: c["functions"][0]["blocks"][0]["code"][0].__setitem__("extra", 1),
                       lambda c: c["table"][0].__setitem__("labels", [9]),
                       lambda c: c["functions"][0]["blocks"][0]["code"][0]["a"].__setitem__(0, [0])):
            changed = copy.deepcopy(candidate)
            change(changed)
            status, verdict = run(changed)
            self.assertEqual((status, verdict["accepted"]), (2, False))
            self.assertIn("error", verdict)
        done = subprocess.run([str(CHECKER)], input="not json", capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 2)

    def test_command_reports_each_path(self):
        done = subprocess.run([sys.executable, str(ROOT / "tools/check_lean_shape.py"), str(FIXTURE), "/nonexistent.tir"],
                              capture_output=True, text=True, timeout=120)
        lines = [json.loads(line) for line in done.stdout.splitlines()]
        self.assertEqual(done.returncode, 2)
        self.assertEqual([line["accepted"] for line in lines], [True, False])
        self.assertEqual(lines[0]["functions"], 1)
        self.assertIn("limitations", lines[0])


if __name__ == "__main__":
    unittest.main()
