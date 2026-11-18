"""Closure-cell identity must survive reads, and no intervening heap mutation."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import check_lean_access as access
import test_lean_access as access_tests
from test_lean_access import op

ROOT = Path(__file__).resolve().parent.parent


class ClosureCellTests(unittest.TestCase):
    @staticmethod
    def snapshot():
        snapshot = access_tests.NegatedComparisonTests.snapshot("dict", 0)
        fn = snapshot["functions"][0]
        fn["parameters"] = [{"name": "env", "type": "env", "representation": "env"}]
        prefix = [op("mach.addr", [("%a0", "%ptr"), ("0", "int")], [20], text="%ptr", typ="%ptr"),
                  op("mach.load", [("%t20", "%ptr")], [21], typ="%ptr"),
                  op("mem.load", [("%t21", "*dict[str,int]")], [22], typ="dict[str,int]")]
        fn["blocks"][0]["operations"][0]["operands"][0]["value"] = "%t22"
        fn["blocks"][0]["operations"][:0] = prefix
        read = fn["blocks"][1]["operations"]
        read[0]["operands"][0]["value"] = "%t23"
        read.insert(0, op("mem.load", [("%t21", "*dict[str,int]")], [23], typ="dict[str,int]"))
        return snapshot

    def assert_verdict(self, snapshot, expected):
        candidate, metadata = access.normalize_snapshot(snapshot, "@f.guarded")
        self.assertEqual(metadata["unproved"] == 0, expected)
        self.assertEqual(access.explain(candidate) is None, expected)
        if access.DEFAULT_CHECKER.is_file():
            self.assertEqual(access.run_checker(access.DEFAULT_CHECKER, access.encode(candidate), metadata), expected)

    def test_repeated_cell_reads_retain_the_same_guarded_dict(self):
        self.assert_verdict(self.snapshot(), True)

    def test_writes_through_same_or_unknown_alias_kill_cell_identity(self):
        for address in ("%t21", "%a2"):
            for kind in ("mem.store", "mach.store"):
                with self.subTest(address=address, kind=kind):
                    snapshot = self.snapshot()
                    snapshot["functions"][0]["blocks"][1]["operations"].insert(0,
                        op(kind, [(address, "*dict[str,int]" if kind == "mem.store" else "%ptr"),
                                  ("null", "dict[str,int]")]))
                    self.assert_verdict(snapshot, False)

    def test_callback_and_generator_resumption_kill_cell_identity(self):
        snapshot = self.snapshot()
        snapshot["functions"][0]["blocks"][1]["operations"].insert(0, op("icall", typ="None"))
        self.assert_verdict(snapshot, False)
        snapshot = self.snapshot()
        fn = snapshot["functions"][0]
        continuation = copy.deepcopy(fn["blocks"][1])
        continuation["label"] = "resumed"
        fn["blocks"][1]["operations"] = [op("gen.yield", targets=["resumed"])]
        fn["blocks"].append(continuation)
        self.assert_verdict(snapshot, False)

    def test_cells_of_other_word_values_are_read_like_containers(self):
        # (a bound method or object in a cell: one word, so a reload equals the earlier read;
        # a promoting int's two words or a narrower scalar is not such a value)
        for typ, expected in (("fn[m:Acc.add]", True), ("Acc", True), ("int", True), ("int+", False),
                              ("bool", False)):
            with self.subTest(typ=typ):
                snapshot = self.snapshot()
                fn = snapshot["functions"][0]
                for block in fn["blocks"]:
                    for operation in block["operations"]:
                        if operation["op"] == "mem.load" and operation["operands"][0]["value"] == "%t21":
                            operation["type"] = typ
                # (the cell's value, compared with a dict register, stands for the dict below)
                fn["blocks"][0]["operations"].insert(3, op("ptr.cmp", [("%t22", typ), ("null", typ)], [24],
                                                            text="==", typ="bool"))
                candidate, metadata = access.normalize_snapshot(snapshot, "@f.guarded")
                nodes = candidate["program"]["nodes"]
                reads = [node for node in nodes if node["op"] == "read_field" and node["class"] == "<closure-cell>"]
                self.assertEqual(len(reads) == 2, expected)

    def test_arbitrary_pointer_and_different_cell_cannot_borrow_identity(self):
        snapshot = self.snapshot()
        snapshot["functions"][0]["parameters"][0]["representation"] = "%ptr"
        self.assert_verdict(snapshot, False)
        snapshot = self.snapshot()
        snapshot["functions"][0]["blocks"][1]["operations"][0]["operands"][0]["value"] = "%a2"
        self.assert_verdict(snapshot, False)

    @unittest.skipUnless(access.DEFAULT_CHECKER.is_file(), "build the Lean checker")
    def test_actual_closure_corpus_has_no_unproved_access(self):
        with tempfile.TemporaryDirectory() as directory:
            inspected = Path(directory) / "snapshot"
            result = subprocess.run([sys.executable, str(ROOT / "tools/inspect_compiler.py"),
                                     str(ROOT / "tests/programs/language/closures.py"),
                                     "--output", str(inspected), "--typed-after-only"],
                                    cwd=ROOT, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            snapshot = json.loads((inspected / "typed-after.json").read_text())
            report, code = access.check_all(snapshot)
            self.assertEqual(code, 0, report)
            fib = next(record for record in report["functions"] if record["function"] == "@c.3.1")
            self.assertEqual((fib["status"], fib["accesses"]), ("accepted", 1))
            self.assertEqual(report["totals"]["accesses"], report["totals"]["proved_accesses"])


if __name__ == "__main__":
    unittest.main()
