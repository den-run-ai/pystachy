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
from test_lean_boundary import instruction

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

        def field_store(snapshot, symbol, cls, name):
            """The store of a field of class cls in function symbol, removed."""
            init = self.function(snapshot, symbol)
            index = snapshot["class_layouts"][cls]["fields"].index(name)
            addresses = {f"%t{op['results'][0]}" for b in init["blocks"] for op in b["operations"]
                         if op["op"] == "field.addr" and op["immediate"] == index}
            self.remove(init, lambda b, op: op["op"] == "mem.store" and op["operands"][0]["value"] in addresses)

        def span(snapshot):
            """Gauge.__init__'s def, and where it loads self from its cell."""
            symbol = next(op["text"] for b in self.function(snapshot, "@m.Gauge.__init__")["blocks"]
                          for op in b["operations"] if op["op"] == "call" and op["text"].startswith("@c."))
            fn = self.function(snapshot, symbol)
            block = fn["blocks"][0]
            offset = next(i for i, op in enumerate(block["operations"]) if op["op"] == "mem.load" and op["type"] == "Gauge")
            return block, offset

        def closure_before_store(snapshot):  # span(), called by __init__, reads low before it is assigned
            field_store(snapshot, "@m.Gauge.__init__", "Gauge", "low")
            return "@m.Gauge.__init__"

        def escapes_before_store(snapshot):  # the lambda escapes, into log, before self.name is assigned
            field_store(snapshot, "@m.Watch.__init__", "Watch", "name")
            return "@m.Watch.__init__"

        def closure_rebinds_self(snapshot):  # span() assigns its cell: __init__'s later stores may miss self
            block, offset = span(snapshot)
            cell = block["operations"][offset]["operands"][0]["value"]
            block["operations"].insert(offset + 1, {"op": "mem.store", "type": "", "text": "", "immediate": 0, "descriptor": "",
                                                    "results": [], "targets": [], "operands": [
                                                        {"value": cell, "type": "*Gauge"}, {"value": "null", "type": "Gauge"}]})
            return "@main.init"

        def closure_lets_self_escape(snapshot):  # span() passes self on before __init__ assigns width
            block, offset = span(snapshot)
            obj = f"%t{block['operations'][offset]['results'][0]}"
            block["operations"].insert(offset + 1, {"op": "call", "type": "int", "text": "@m.Gauge.total", "immediate": 0,
                                                    "descriptor": "", "results": [9001], "targets": [],
                                                    "operands": [{"value": obj, "type": "Gauge"}]})
            return "@m.Gauge.__init__"

        def published_cell_store(snapshot):  # after the lambda escapes, its cell takes an object under construction
            ops = self.function(snapshot, "@m.Watch.__init__")["blocks"][0]["operations"]
            cell = next(op["operands"][0]["value"] for op in ops if op["op"] == "mem.store" and op["operands"][1]["value"] == "%a0")
            ops[len(ops) - 1:len(ops) - 1] = [
                {"op": "alloc.fixed", "type": "Watch", "text": "", "immediate": 0, "descriptor": "", "results": [9002],
                 "operands": [], "targets": []},
                {"op": "mem.store", "type": "", "text": "", "immediate": 0, "descriptor": "", "results": [], "targets": [],
                 "operands": [{"value": cell, "type": "*Watch"}, {"value": "%t9002", "type": "Watch"}]}]
            return "@m.Watch.__init__"

        def callable_before_store(snapshot):  # the Callable lambda, called by __init__, reads code before it is assigned
            field_store(snapshot, "@m.Ticket.__init__", "Ticket", "code")
            return "@m.Ticket.__init__"

        def adapter_does_more(snapshot):  # the lambda's adapter also uses the environment otherwise: not followed
            adapter = next(op["operands"][1]["value"] for b in self.function(snapshot, "@m.Ticket.__init__")["blocks"]
                           for op in b["operations"] if op["op"] == "mach.store"
                           and op["operands"][1]["value"].startswith("@cv."))
            ops = self.function(snapshot, adapter)["blocks"][0]["operations"]
            offset = next(i for i, op in enumerate(ops) if op["op"] == "mem.load")
            ops.insert(offset + 1, {"op": "ptr.cmp", "type": "bool", "text": "==", "immediate": 0, "descriptor": "",
                                    "results": [9003], "targets": [], "operands": [
                                        {"value": f"%t{ops[offset]['results'][0]}", "type": "%ptr"},
                                        {"value": "null", "type": "None"}]})
            return "@m.Ticket.__init__"

        for corruption in (no_store, no_init, no_default, no_class_tag, unflagged_base, chain_without_init,
                           read_before_store, flag_before_field, closure_before_store, escapes_before_store,
                           closure_rebinds_self, closure_lets_self_escape, published_cell_store,
                           callable_before_store, adapter_does_more):
            with self.subTest(corruption=corruption.__name__):
                snapshot = self.sample()
                name = corruption(snapshot)
                results, _ = self.statuses(snapshot)
                self.assertEqual(results[name]["status"], "rejected", results[name])

    def test_each_call_meets_its_contract(self):
        # (Python infers contracts; Lean checks every call against its callee's: a closure's
        # pre-condition that also demands width, which __init__ assigns after the call)
        original = fields.infer_contracts

        def tampered(ctx, proved, refused=frozenset()):
            contracts, wanted = original(ctx, proved, refused)
            width = ctx.layouts["Gauge"]["fields"].index("width")
            for (symbol, position), (pre, post, leaks) in list(contracts.items()):
                if position == "env0" and ctx.position_class(ctx.functions[symbol], position) == "Gauge":
                    contracts[(symbol, position)] = (pre | {width}, post, leaks)
            return contracts, wanted
        fields.infer_contracts = tampered
        try:
            results, _ = self.statuses(self.sample())
        finally:
            fields.infer_contracts = original
        self.assertEqual(results["@m.Gauge.__init__"]["status"], "rejected", results["@m.Gauge.__init__"])

    def test_none_parameters_do_not_shift_call_contracts(self):
        # None takes no call operand. touch assigns a.x, so only a may arrive without
        # __init__; its contract must never justify passing an uninitialized b.
        program = """class C:
    def __init__(self) -> None:
        self.x = 1

def touch(n, a: C, b: C) -> int:
    a.x = 2
    return b.x

def make() -> int:
    a = C()
    b = C()
    return touch(None, a, b)

print(make())
"""
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "none_parameters.py"
            source.write_text(program)
            original = inspect(source, Path(temporary) / "snapshot")
        touch = next(fn for fn in original["functions"] if fn["symbol"].startswith("@f.touch"))
        self.assertEqual([p["representation"] for p in touch["parameters"]], ["None", "C", "C"])
        results, _ = self.statuses(copy.deepcopy(original))
        self.assertTrue(all(r["status"] == "accepted" for r in results.values()), results)
        for missing, expected in ((0, "accepted"), (1, "rejected")):
            with self.subTest(missing_init=missing):
                snapshot = copy.deepcopy(original)
                make = self.function(snapshot, "@f.make")
                calls = [(block, index) for block in make["blocks"]
                         for index, op in enumerate(block["operations"])
                         if op["op"] == "call" and op["text"] == "@m.C.__init__"]
                self.assertEqual(len(calls), 2)
                block, index = calls[missing]
                del block["operations"][index]
                results, _ = self.statuses(snapshot)
                self.assertEqual(results["@f.make"]["status"], expected, results)

    def test_a_list_store_writes_its_operands_as_escapes(self):
        # (the shared validator's guard model refuses list.store; this model takes a write's
        # operands as escapes, and validates it as the runtime write it stores as: Watch's self
        # stored into log before or after __init__ assigns name, which Watch's lambda reads unflagged)
        def stored(after_name):
            snapshot = self.sample()
            block = self.function(snapshot, "@m.Watch.__init__")["blocks"][0]
            address = next(f"%t{op['results'][0]}" for op in block["operations"] if op["op"] == "field.addr")
            at = next(i for i, op in enumerate(block["operations"])
                      if op["op"] == "mem.store" and op["operands"][0]["value"] == address)
            block["operations"].insert(at + 1 if after_name else 0, instruction("list.store", operands=[
                ("%a1", "list[callable[str]]"), ("0", "int"), ("%a0", "*callable[str]")]))
            return self.statuses(snapshot)[0]["@m.Watch.__init__"]
        self.assertEqual(stored(True)["status"], "accepted")
        result = stored(False)
        self.assertEqual((result["status"], tuple(result["why"]["site"][:3])), ("rejected", ("entry", 0, "escapes")),
                         result)

    def test_a_type_past_the_validators_bound_is_validated_by_its_short_name(self):
        # (such as a constant table's tuple type: the model reads the IR's own types)
        snapshot = self.sample()
        watch = self.function(snapshot, "@m.Watch.__init__")
        long = json.dumps(watch).replace("callable[str]", "callable[" + "tuple[str," * 30 + "str" + "]" * 30 + "]")
        watch.clear()
        watch.update(json.loads(long))
        self.assertGreater(max(len(op["type"]) for block in watch["blocks"] for op in block["operations"]), 256)
        self.assertEqual(self.statuses(snapshot)[0]["@m.Watch.__init__"]["status"], "accepted")

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
