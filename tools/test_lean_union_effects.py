"""Union guards across effects: box immutability, joins and proved return domains.

Each refutation corrupts actual compiler IR of examples/union_effects.py; Lean must reject or
the adapter must fall back to its conservative rules, while the original stays proved.
"""
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
from test_lean_boundary import instruction as op

ROOT = Path(__file__).resolve().parent.parent
CHECKER = boundary.DEFAULT_CHECKER
EXAMPLES = ROOT / "tools/lean_boundary/examples"


def inspect(program, directory):
    env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
    env["PYSTACHY_HOME"] = str(ROOT)
    result = subprocess.run([sys.executable, str(ROOT / "tools/inspect_compiler.py"), str(program),
                             "--output", str(directory), "--guard-evidence", "--typed-after-only"],
                            cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return json.loads((directory / "typed-after.json").read_text())


class UnionEffectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CHECKER.is_file():
            if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1":
                raise RuntimeError("Lean checker required for union effect controls")
            raise unittest.SkipTest("build the Lean boundary checker")
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.snapshot = inspect(EXAMPLES / "union_effects.py", Path(cls.temp.name) / "effects")

    def sample(self):
        return copy.deepcopy(self.snapshot)

    @staticmethod
    def function(snapshot, name):
        return next(fn for fn in snapshot["functions"] if fn["symbol"] == "@f." + name)

    @staticmethod
    def block(function, label):
        return next(block for block in function["blocks"] if block["label"] == label)

    @staticmethod
    def record(report, name):
        return next(r for r in report["records"] if r["function"] == "@f." + name
                    and r.get("scope") != guards.REMOVALS)

    def lean(self, snapshot, function, **options):
        candidate, metadata = guards.normalize(snapshot, function, **options)
        metadata.pop("origins")
        return boundary.run_checker(CHECKER, boundary.encode(candidate), metadata)

    def test_example_proves_every_read_and_return(self):
        # (its tag test compares with literal 1, as `counter.count += 1` adds it: a literal is
        # no storage that would make that field's load a union read)
        self.assertEqual(len(guards.inventory(self.function(self.snapshot, "across_effects"))), 3)
        report, code = guards.check_all(self.sample(), CHECKER)
        self.assertEqual(code, 0, report)
        self.assertEqual(report["possible_box_writes"], 0)
        self.assertGreaterEqual(report["union_reads"], 12)
        self.assertEqual(report["proved_union_reads"], report["union_reads"])
        self.assertEqual((report["union_returns"], report["proved_union_returns"]), (1, 1))

    def test_reads_across_calls_and_writes_rest_on_immutable_boxes(self):
        snapshot = self.sample()
        effects = self.function(snapshot, "across_effects")
        with self.assertRaises(boundary.Unsupported):
            guards.normalize(snapshot, effects)
        self.assertTrue(self.lean(snapshot, effects, immutable_boxes=True))

    def test_possible_box_writes_anywhere_restore_conservative_rules(self):
        mutations = {
            "unknown runtime function": [op("rt", "None", "copybytes", operands=[("%t3", "%ptr")])],
            "store through a loaded pointer": [
                op("mach.load", "%ptr", results=[900], operands=[("%t3", "%ptr")]),
                op("mach.store", operands=[("%t900", "%ptr"), ("1", "int")])],
            "undefined callee": [op("call", "None", "@f.elsewhere")],
            "generator operation on a raw pointer": [op("gen.resume", operands=[("%t3", "%ptr")])],
            "field of an unknown class": [
                op("field.addr", "*int", results=[900], operands=[("%t3", "Unknown")]),
                op("mem.store", operands=[("%t900", "*int"), ("1", "int")])],
            "allocation used as a union": [
                op("rt", "%ptr", "alloc", results=[900], operands=[("16", "int")]),
                op("scalar.cast", "union[int,str]", "bitcast", [901], [("%t900", "%ptr")]),
                op("mach.store", operands=[("%t900", "%ptr"), ("1", "int")])],
            "box passed as a raw pointer": [
                op("rt", "%ptr", "ubox", results=[900], operands=[("1", "int"), ("7", "*T")]),
                op("rt", "int", "on_stack", results=[901], operands=[("%t900", "%ptr")])],
            "box passed as a receiver": [
                op("rt", "%ptr", "ubox", results=[900], operands=[("1", "int"), ("7", "*T")]),
                op("scalar.cast", "list[int]", "bitcast", [901], [("%t900", "%ptr")]),
                op("rt", "None", "list.append", operands=[("%t901", "S"), ("1", "*T")])],
            "list write into a box": [
                op("rt", "%ptr", "ubox", results=[900], operands=[("1", "int"), ("7", "*T")]),
                op("list.store", "", "", [], [("%t900", "list[int]"), ("0", "int"), ("1", "int")])],
            "box passed to a raw copy": [
                op("rt", "%ptr", "ubox", results=[900], operands=[("1", "int"), ("7", "*T")]),
                op("rt", "None", "memmove", operands=[("%t900", "%ptr"), ("%t3", "%ptr"), ("16", "int"),
                                                      ("false", "%i1")])],
        }
        for reason, operations in mutations.items():
            with self.subTest(reason=reason):
                snapshot = self.sample()
                entry = self.block(self.function(snapshot, "bump"), "entry")
                entry["operations"][-1:-1] = operations
                self.assertTrue(guards.box_writes(snapshot), reason)
                report, code = guards.check_all(snapshot, CHECKER)
                self.assertIn(code, (1, 2, 3), report)
                self.assertNotEqual(self.record(report, "across_effects")["status"], "accepted")
                self.assertLess(report["proved_union_reads"], report["union_reads"])

    def test_closure_cells_and_stack_storage_lie_outside_boxes(self):
        snapshot = inspect(EXAMPLES / "null_reloads.py", Path(self.temp.name) / "reloads")
        self.assertTrue(any(op["op"] in {"mem.store", "mach.store"} for fn in snapshot["functions"]
                            if fn["symbol"].startswith("@c.") for block in fn["blocks"]
                            for op in block["operations"]))
        self.assertEqual(guards.box_writes(snapshot), [])

    def test_return_outside_its_domain_is_not_assumed(self):
        tags = self.snapshot["union_tags"]
        for corruption in ("foreign tag", "reachable null"):
            with self.subTest(corruption=corruption):
                snapshot = self.sample()
                made = self.function(snapshot, "made")
                box, ret = self.block(made, "L4")["operations"]
                if corruption == "foreign tag":
                    box["operands"][0]["value"] = str(tags["float"])
                else:
                    ret["operands"][0]["value"] = "null"
                self.assertEqual(guards.proved_returns(snapshot, CHECKER), {})
                report, code = guards.check_all(snapshot, CHECKER)
                self.assertEqual(code, 1, report)
                self.assertEqual(report["proved_union_returns"], 0)
                self.assertEqual(self.record(report, "returned")["status"], "rejected")

    def test_caller_proof_rests_on_the_callee_return_proof(self):
        snapshot = self.sample()
        returned = self.function(snapshot, "returned")
        proved = guards.proved_returns(snapshot, CHECKER)
        self.assertEqual(set(proved), {"@f.made"})
        self.assertFalse(self.lean(snapshot, returned, immutable_boxes=True))
        self.assertTrue(self.lean(snapshot, returned, immutable_boxes=True, returns=proved))
        # (an assumption names a callee: another call's result stays unknown)
        self.assertFalse(self.lean(snapshot, returned, immutable_boxes=True, returns={"@f.other": proved["@f.made"]}))

    def test_join_without_its_test_is_rejected(self):
        snapshot = self.sample()
        joined = self.function(snapshot, "joined")
        test = self.block(joined, "L9")["operations"]
        test[-1] = op("br", targets=["L19"])
        report, code = guards.check_all(snapshot, CHECKER)
        self.assertEqual(code, 1, report)
        record = self.record(report, "joined")
        self.assertEqual(record["status"], "rejected")
        self.assertIn("union.payload at L19:1", record["error"])

    def test_swapped_phis_are_not_copied_in_sequence(self):
        snapshot = self.sample()
        joined = self.function(snapshot, "joined")
        joined["check_targets"] = {}
        joined["blocks"] = [
            {"label": "entry", "handler": "", "operations": [
                op("rt", "%ptr", "ubox", results=[900], operands=[("1", "int"), ("7", "*T")]),
                op("rt", "%ptr", "ubox", results=[901], operands=[("2", "int"), ("7", "*T")]),
                op("br", targets=["L1"])]},
            {"label": "L1", "handler": "", "operations": [
                op("phi", "union[int,str]", results=[902], operands=[("%t900", "union[int,str]"),
                                                                     ("%t903", "union[int,str]")],
                   targets=["entry", "L1"]),
                op("phi", "union[int,str]", results=[903], operands=[("%t901", "union[int,str]"),
                                                                     ("%t902", "union[int,str]")],
                   targets=["entry", "L1"]),
                op("union.payload", "%slot", "str", results=[904, 905], operands=[("%t903", "union[int,str]")]),
                op("cbr", operands=[("%a0", "bool")], targets=["L1", "L2"])]},
            {"label": "L2", "handler": "", "operations": [op("ret", operands=[("0", "int")])]}]
        # (the second iteration swaps the boxes: %t903 then holds the int box, which copies made
        # one after another would miss, as %t903 would copy the str box %t902 just received)
        self.assertFalse(self.lean(snapshot, joined, immutable_boxes=True))
        self.block(joined, "L1")["operations"][2]["text"] = "int"
        self.assertFalse(self.lean(snapshot, joined, immutable_boxes=True))


if __name__ == "__main__":
    unittest.main()
