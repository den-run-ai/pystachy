"""Union reads of typed union memory: each write proved in its union, each read assuming it.

Each refutation corrupts actual compiler IR of examples/union_memory.py or union_defaults.py: a write
outside its union (a field, a packed container item, a parameter), a definition order that lets a
read precede the store it relies on, or a lost initialization. Lean must then reject the read that
assumed the write, while the original example stays proved.
"""
import copy
import os
from pathlib import Path
import tempfile
import unittest

import check_lean_boundary as boundary
import check_lean_guards as guards
from test_lean_union_effects import inspect

ROOT = Path(__file__).resolve().parent.parent
CHECKER = boundary.DEFAULT_CHECKER
EXAMPLES = ROOT / "tools/lean_boundary/examples"
UNION = "union[int,str]"


class UnionMemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CHECKER.is_file():
            if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1":
                raise RuntimeError("Lean checker required for union memory controls")
            raise unittest.SkipTest("build the Lean boundary checker")
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.memory = inspect(EXAMPLES / "union_memory.py", Path(cls.temp.name) / "memory")
        cls.defaults = inspect(EXAMPLES / "union_defaults.py", Path(cls.temp.name) / "defaults")

    @staticmethod
    def function(snapshot, symbol):
        return next(fn for fn in snapshot["functions"] if fn["symbol"] == symbol)

    @staticmethod
    def operations(fn):
        return [(block, offset, op) for block in fn["blocks"] for offset, op in enumerate(block["operations"])]

    def status(self, snapshot, symbol):
        report, _ = guards.check_all(snapshot, CHECKER)
        return next(r["status"] for r in report["records"] if r["function"] == symbol
                    and r.get("scope") != guards.REMOVALS)

    def test_examples_prove_every_read(self):
        for snapshot in (self.memory, self.defaults):
            report, code = guards.check_all(copy.deepcopy(snapshot), CHECKER)
            self.assertEqual(code, 0, [r for r in report["records"] if r["status"] != "accepted"])
            self.assertEqual(report["proved_union_reads"], report["union_reads"])
            self.assertGreaterEqual(report["union_reads"], 12)

    def test_field_store_outside_its_union_is_rejected(self):
        snapshot = copy.deepcopy(self.memory)
        init = self.function(snapshot, "@m.Reading.__init__")
        store = next(op for _, _, op in self.operations(init) if op["op"] == "mem.store"
                     and op["operands"][0]["type"] == "*" + UNION and op["operands"][0]["value"].startswith("%t"))
        store["operands"][1] = {"value": "null", "type": UNION}
        self.assertEqual(self.status(snapshot, "@m.Reading.size"), "rejected")

    def test_uninitialized_field_is_rejected(self):
        # (the field checker rejects __init__: the class's field may be unassigned where read)
        snapshot = copy.deepcopy(self.memory)
        init = self.function(snapshot, "@m.Reading.__init__")
        for block in init["blocks"]:
            block["operations"] = [op for op in block["operations"] if not (
                op["op"] == "mem.store" and op["operands"][0]["value"].startswith("%t"))]
        self.assertEqual(self.status(snapshot, "@m.Reading.size"), "rejected")

    def test_packed_item_outside_its_union_is_rejected(self):
        snapshot = copy.deepcopy(self.memory)
        main = self.function(snapshot, "@main.init")
        pack = next(op for _, _, op in self.operations(main) if op["op"] == "slot.pack"
                    and op["operands"][0]["type"] == UNION)
        pack["operands"][0] = {"value": "null", "type": UNION}
        self.assertEqual(self.status(snapshot, "@f.total"), "rejected")
        self.assertEqual(self.status(snapshot, "@f.unpacked"), "rejected")

    def test_argument_outside_its_union_is_rejected(self):
        snapshot = copy.deepcopy(self.memory)
        main = self.function(snapshot, "@main.init")
        call = next(op for _, _, op in self.operations(main) if op["op"] == "call" and op["text"] == "@f.replaced")
        call["operands"][0] = {"value": "null", "type": UNION}
        self.assertEqual(self.status(snapshot, "@f.replaced"), "rejected")

    def test_argument_after_none_parameter_outside_its_union_is_rejected(self):
        # (a None parameter takes no operand: the union argument is the call's first operand)
        snapshot = copy.deepcopy(self.memory)
        noted = next(fn for fn in snapshot["functions"] if fn["symbol"].startswith("@f.noted"))
        self.assertEqual([p["representation"] for p in noted["parameters"]], ["None", UNION])
        main = self.function(snapshot, "@main.init")
        call = next(op for _, _, op in self.operations(main) if op["op"] == "call" and op["text"] == noted["symbol"])
        self.assertEqual(len(call["operands"]), 1)
        call["operands"][0] = {"value": "null", "type": UNION}
        self.assertEqual(self.status(snapshot, noted["symbol"]), "rejected")

    def test_chained_join_branch_swap_is_rejected(self):
        snapshot = copy.deepcopy(self.memory)
        single = self.function(snapshot, "@f.single")
        joins = [block for block in single["blocks"] if [op["op"] for op in block["operations"]] == ["phi", "cbr"]]
        self.assertGreaterEqual(len(joins), 2)
        branch = joins[1]["operations"][1]
        branch["targets"] = branch["targets"][::-1]
        self.assertEqual(self.status(snapshot, "@f.single"), "rejected")

    def test_default_read_before_its_definition_is_rejected(self):
        snapshot = copy.deepcopy(self.defaults)
        self.assertEqual(self.status(copy.deepcopy(snapshot), "@m.Span.grown"), "accepted")
        main = self.function(snapshot, "@main.init")
        entry = main["blocks"][0]["operations"]
        call = next(op for block in main["blocks"] for op in block["operations"]
                    if op["op"] == "call" and op["text"] == "@f.make")
        # (make, which reads Span's defaults, called before the class statement stores them)
        early = copy.deepcopy(call)
        early["results"] = [max(n for fn in snapshot["functions"] for _, _, op in self.operations(fn)
                                for n in op["results"]) + 1]
        entry.insert(0, early)
        self.assertEqual(self.status(snapshot, "@m.Span.grown"), "rejected")

    def test_late_functions_follow_main_init_order(self):
        late = guards.late_functions(self.defaults)
        word = "@d.m.Span.grown.by"
        self.assertIn("@f.make", late[word])
        self.assertNotIn("@main.init", late[word])


if __name__ == "__main__":
    unittest.main()
