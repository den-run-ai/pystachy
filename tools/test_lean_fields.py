"""Field initialization: each field a class's code reads without an "is assigned" flag test is
assigned before that code can see an object under construction (check_lean_fields).

Each refutation corrupts actual compiler IR of examples/field_init.py, or its class layouts, as
a compiler bug could; Lean must reject it, or the adapter refuse it, while the original stays
proved. The layout refutation is the shape of a bug these checks found: an exception subclass's
class variable gave a field of its base a flag that the base's code, which read the field
unflagged, never tested.
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
import check_lean_fields as fields

ROOT = Path(__file__).resolve().parent.parent
CHECKER = boundary.DEFAULT_CHECKER
EXAMPLE = ROOT / "tools/lean_boundary/examples/field_init.py"


def inspect(program, directory):
    env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
    env["PYSTACHY_HOME"] = str(ROOT)
    result = subprocess.run([sys.executable, str(ROOT / "tools/inspect_compiler.py"), str(program),
                             "--output", str(directory), "--guard-evidence", "--typed-after-only"],
                            cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return json.loads((directory / "typed-after.json").read_text())


class FieldInitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CHECKER.is_file():
            if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1":
                raise RuntimeError("Lean checker required for field initialization controls")
            raise unittest.SkipTest("build the Lean boundary checker")
        with tempfile.TemporaryDirectory() as temporary:
            cls.snapshot = inspect(EXAMPLE, Path(temporary) / "fields")

    def sample(self):
        return copy.deepcopy(self.snapshot)

    @staticmethod
    def function(snapshot, symbol):
        return next(fn for fn in snapshot["functions"] if fn["symbol"] == symbol)

    @staticmethod
    def statuses(snapshot):
        results, contracts = fields.check_all(snapshot, CHECKER)
        return {r["function"]: r for r in results}, contracts

    @staticmethod
    def remove(function, predicate):
        """Delete the first operation predicate(block, operation) selects; return it."""
        for block in function["blocks"]:
            for offset, op in enumerate(block["operations"]):
                if predicate(block, op):
                    return block["operations"].pop(offset)
        raise AssertionError("no such operation")

    def test_example_proves_every_construction(self):
        results, contracts = self.statuses(self.sample())
        self.assertEqual({name for name, r in results.items() if r["status"] != "accepted"}, set(), results)
        totals = {kind: sum(r["counts"][kind] for r in results.values()) for kind in fields.KINDS}
        for kind in fields.KINDS:
            self.assertGreater(totals[kind], 0, kind)
        layouts = self.snapshot["class_layouts"]
        point = layouts["Point"]["fields"]
        pre, post, leaks = contracts[("@m.Point.__init__", 0)]
        # (the class attribute's default is stored first; __init__ assigns every unflagged field)
        self.assertEqual(pre, {point.index("scale")})
        self.assertEqual(post, {point.index(f) for f in ("scale", "x", "y", "name")})
        self.assertFalse(leaks)
        # (fmt, given CodeError's object before AppError.__init__ ran, reads none of its fields)
        self.assertIn("msg", layouts["AppError"]["flags"])
        self.assertEqual(results["@f.chain"]["status"], "accepted")

    def test_corruptions_are_rejected(self):
        def no_store(snapshot):  # __init__ forgets self.y
            init = self.function(snapshot, "@m.Point.__init__")
            y = snapshot["class_layouts"]["Point"]["fields"].index("y")
            addresses = {f"%t{op['results'][0]}" for b in init["blocks"] for op in b["operations"]
                         if op["op"] == "field.addr" and op["immediate"] == y}
            self.remove(init, lambda b, op: op["op"] == "mem.store" and op["operands"][0]["value"] in addresses)
            return "@f.either"

        def no_init(snapshot):  # an object escapes that no __init__ was given
            self.remove(self.function(snapshot, "@f.either"),
                        lambda b, op: op["op"] == "call" and op["text"] == "@m.Point.__init__")
            return "@f.either"

        def no_default(snapshot):  # the class attribute's default, which __init__ reads, not stored
            either = self.function(snapshot, "@f.either")
            address = next(f"%t{op['results'][0]}" for b in either["blocks"] for op in b["operations"]
                           if op["op"] == "field.addr" and op["immediate"] == 0)
            self.remove(either, lambda b, op: op["op"] == "mem.store" and op["operands"][0]["value"] == address)
            return "@f.either"

        def no_class_tag(snapshot):  # a Square, which areas() dispatches on, without its class tag
            main = self.function(snapshot, "@main.init")
            allocations = [f"%t{op['results'][0]}" for b in main["blocks"] for op in b["operations"]
                           if op["op"] == "alloc.fixed" and op["type"] == "Square"]
            self.remove(main, lambda b, op: op["op"] == "mach.store" and op["operands"][0]["value"] == allocations[-1])
            return "@main.init"

        def unflagged_base(snapshot):  # (the bug) AppError's code reads msg, which Labeled never assigns
            snapshot["class_layouts"]["AppError"]["flags"].pop("msg")
            return "@main.init"

        def chain_without_init(snapshot):  # each node escapes, into the next one, before __init__
            self.remove(self.function(snapshot, "@f.chain"),
                        lambda b, op: op["op"] == "call" and op["text"] == "@m.Node.__init__")
            return "@f.chain"

        def read_before_store(snapshot):  # self.name reads self.x, which __init__ no longer stores
            init = self.function(snapshot, "@m.Point.__init__")
            x = snapshot["class_layouts"]["Point"]["fields"].index("x")
            addresses = {f"%t{op['results'][0]}" for b in init["blocks"] for op in b["operations"]
                         if op["op"] == "field.addr" and op["immediate"] == x}
            self.remove(init, lambda b, op: op["op"] == "mem.store" and op["operands"][0]["value"] in addresses)
            return "@m.Point.__init__"

        def flag_before_field(snapshot):  # hasattr would find table assigned before it is
            init = self.function(snapshot, "@m.Memo.__init__")
            flag = snapshot["class_layouts"]["Memo"]["flags"]["table"]
            for block in init["blocks"]:
                ops = block["operations"]
                addresses = {f"%t{op['results'][0]}": op["immediate"] for op in ops if op["op"] == "field.addr"}
                stores = [i for i, op in enumerate(ops) if op["op"] == "mem.store" and op["operands"][0]["value"] in addresses]
                if len(stores) == 2 and addresses[ops[stores[1]]["operands"][0]["value"]] == flag:
                    # (the flag's address and store, moved before the field's store)
                    address = next(i for i, op in enumerate(ops) if op["op"] == "field.addr" and op["immediate"] == flag)
                    moved = [ops[address], ops[stores[1]]]
                    del ops[stores[1]], ops[address]
                    ops[stores[0]:stores[0]] = moved
                    return "@m.Memo.__init__"
            raise AssertionError("no field and flag stores")

        for corruption in (no_store, no_init, no_default, no_class_tag, unflagged_base, chain_without_init,
                           read_before_store, flag_before_field):
            with self.subTest(corruption=corruption.__name__):
                snapshot = self.sample()
                name = corruption(snapshot)
                results, _ = self.statuses(snapshot)
                self.assertEqual(results[name]["status"], "rejected", results[name])

    def test_forms_beyond_the_model_are_refused(self):
        snapshot = self.sample()
        del snapshot["class_layouts"]
        with self.assertRaisesRegex(ValueError, "missing class_layouts"):
            fields.check_all(snapshot, CHECKER)
        snapshot = self.sample()
        either = self.function(snapshot, "@f.either")
        block = next(b for b in either["blocks"] if any(op["op"] == "alloc.fixed" for op in b["operations"]))
        offset = next(i for i, op in enumerate(block["operations"]) if op["op"] == "alloc.fixed")
        allocation = f"%t{block['operations'][offset]['results'][0]}"
        block["operations"].insert(offset + 1, {"op": "mach.load", "type": "int", "text": "", "immediate": 2,
                                                "descriptor": "", "results": [9999], "targets": [],
                                                "operands": [{"value": allocation, "type": "%ptr"}]})
        results, _ = self.statuses(snapshot)
        self.assertEqual(results["@f.either"]["status"], "unsupported")
        self.assertIn("raw read", results["@f.either"]["why"])


if __name__ == "__main__":
    unittest.main()
