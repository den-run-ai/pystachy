"""Actual overflow edges in compiler IR and independent negative controls."""
import copy
import os
import unittest

import check_lean_boundary as bridge
import check_lean_inline as inline
from test_lean_int import compile_snapshot, function

PROGRAM = '''# pystachy: python-int
def add(x: int, y: int) -> int:
    return x + y


def sub(x: int, y: int) -> int:
    return x - y


def mul(x: int, y: int) -> int:
    return x * y


def loop(n: int) -> int:
    x = 1
    while n > 0:
        x = x * 2
        n = n - 1
    return x


def handled(x: int, y: int) -> int:
    try:
        return (x + y) // y
    except ZeroDivisionError:
        return x - y


print(add(2 ** 63 - 1, 1), sub(-2 ** 63, 1), mul(-2 ** 63, -1))
print(loop(70), handled(2 ** 63, 0), handled(10, 2))
'''
CHECKER = bridge.DEFAULT_CHECKER
if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1" and not CHECKER.is_file():
    raise RuntimeError("Lean boundary checker is required; build tools/lean_boundary first")


def overflow(fn):
    return next(op for block in fn["blocks"] for op in block["operations"] if op["op"] == "ovf")


def branch_on(fn, value):
    return next(op for block in fn["blocks"] for op in block["operations"]
                if op["op"] == "cbr" and inline.args(op) == [value])


class InlineInventoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = compile_snapshot(PROGRAM)

    def test_unchecked_reconstruction_cannot_remove_inventory(self):
        for symbol, scalar in (("add", "add"), ("sub", "sub"), ("mul", "mul")):
            with self.subTest(symbol=symbol):
                fn = copy.deepcopy(function(self.snapshot, "@f." + symbol))
                op = overflow(fn)
                word, flag = (f"%t{n}" for n in op["results"][1:])
                branch = branch_on(fn, flag)
                branch["operands"][0]["value"] = "false"
                op["op"], op["text"], op["results"] = "scalar.bin", scalar, [int(word[2:])]
                with self.assertRaisesRegex(bridge.Unsupported, "unchecked promoting"):
                    inline.Normalize(fn)

    def test_transport_cannot_hide_unchecked_reconstruction(self):
        for transport in ("cast", "num.cast", "mask", "select", "phi"):
            with self.subTest(transport=transport):
                fn = copy.deepcopy(function(self.snapshot, "@f.add"))
                op = overflow(fn)
                word, flag = (f"%t{n}" for n in op["results"][1:])
                branch_on(fn, flag)["operands"][0]["value"] = "false"
                op.update(op="scalar.bin", text="add", results=[int(word[2:])])
                block = next(block for block in fn["blocks"] if any(
                    item["op"] == "big.make" and inline.args(item)[0] == word for item in block["operations"]))
                reconstruction = next(item for item in block["operations"] if item["op"] == "big.make")
                moved = copy.deepcopy(op)
                moved["results"] = [999999]
                if transport in {"cast", "num.cast"}:
                    moved.update(op="scalar.cast" if transport == "cast" else "num.cast", text="bitcast",
                                 operands=[{"value": word, "type": "int"}])
                elif transport == "mask":
                    moved.update(text="and", operands=[{"value": word, "type": "int"}, {"value": "-1", "type": "int"}])
                elif transport == "select":
                    moved.update(op="select", text="", operands=[{"value": "true", "type": "bool"},
                                 {"value": word, "type": "int"}, {"value": "0", "type": "int"}])
                else:
                    predecessor = next(b["label"] for b in fn["blocks"] if any(
                        block["label"] in item["targets"] for item in b["operations"]))
                    moved.update(op="phi", text="", operands=[{"value": word, "type": "int"}], targets=[predecessor])
                block["operations"].insert(0, moved)
                reconstruction["operands"][0]["value"] = "%t999999"
                with self.assertRaisesRegex(bridge.Unsupported, "unchecked promoting"):
                    inline.Normalize(fn)

    def test_transformed_checked_result_cannot_remove_inventory(self):
        fn = copy.deepcopy(function(self.snapshot, "@f.add"))
        op = overflow(fn)
        word = f"%t{op['results'][1]}"
        block = next(block for block in fn["blocks"]
                     if any(item["op"] == "big.make" and inline.args(item)[0] == word for item in block["operations"]))
        reconstruction = next(item for item in block["operations"] if item["op"] == "big.make")
        transformed = copy.deepcopy(op)
        transformed.update(op="scalar.bin", text="add", results=[999999],
                           operands=[{"value": word, "type": "int"}, {"value": "0", "type": "int"}])
        block["operations"].insert(0, transformed)
        reconstruction["operands"][0]["value"] = "%t999999"
        with self.assertRaisesRegex(bridge.Unsupported, "transformed checked"):
            inline.Normalize(fn)

    def test_missing_and_duplicate_definitions_fail_closed(self):
        for mutation in ("missing", "duplicate"):
            with self.subTest(mutation=mutation):
                fn = copy.deepcopy(function(self.snapshot, "@f.add"))
                block = next(block for block in fn["blocks"] if any(op["op"] == "ovf" for op in block["operations"]))
                op = overflow(fn)
                if mutation == "missing":
                    block["operations"].remove(op)
                else:
                    block["operations"].insert(0, copy.deepcopy(op))
                with self.assertRaises(ValueError):
                    inline.Normalize(fn)

    def test_undefined_transported_word_fails_closed(self):
        fn = copy.deepcopy(function(self.snapshot, "@f.add"))
        op = overflow(fn)
        word, flag = (f"%t{n}" for n in op["results"][1:])
        branch_on(fn, flag)["operands"][0]["value"] = "false"
        block = next(block for block in fn["blocks"] if op in block["operations"])
        block["operations"].remove(op)
        for block in fn["blocks"]:
            for reconstruction in block["operations"]:
                if reconstruction["op"] == "big.make" and inline.args(reconstruction)[0] == word:
                    moved = copy.deepcopy(op)
                    moved.update(op="scalar.cast", text="bitcast", results=[999999],
                                 operands=[{"value": word, "type": "int"}])
                    block["operations"].insert(0, moved)
                    reconstruction["operands"][0]["value"] = "%t999999"
                    break
        with self.assertRaisesRegex(ValueError, "undefined arithmetic provenance"):
            inline.Normalize(fn)

    def test_each_loop_definition_forgets_prior_flags(self):
        fn = function(self.snapshot, "@f.loop")
        normal = inline.Normalize(fn)
        candidate = normal.build()
        resets = {node["dst"] for node in candidate["program"]["nodes"] if node["op"] == "havoc"}
        self.assertEqual(resets, set(normal.flags))
        self.assertGreater(len(resets), 1)


@unittest.skipUnless(CHECKER.is_file(), "build tools/lean_boundary to run the proved checker")
class InlineGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = compile_snapshot(PROGRAM)

    def test_real_guarded_arithmetic_and_handlers_pass(self):
        report, code = inline.check_all(self.snapshot)
        self.assertEqual((report["status"], code), ("accepted", 0), report)
        self.assertGreaterEqual(report["totals"]["proved_uses"], 7)
        self.assertEqual(report["totals"]["proved_uses"], report["totals"]["uses"])
        for name in ("add", "sub", "mul", "loop", "handled"):
            self.assertIn("@f." + name, {record["function"] for record in report["functions"]})

    def test_changed_actual_edges_are_rejected(self):
        for symbol in ("add", "sub", "mul", "loop"):
            for mutation in ("unconditional", "swapped", "wrong_flag"):
                with self.subTest(symbol=symbol, mutation=mutation):
                    snapshot = copy.deepcopy(self.snapshot)
                    fn = function(snapshot, "@f." + symbol)
                    ovf = overflow(fn)
                    branch = branch_on(fn, f"%t{ovf['results'][2]}")
                    if mutation == "unconditional":
                        branch["operands"][0]["value"] = "false"
                    elif mutation == "swapped":
                        branch["targets"].reverse()
                    else:
                        # A valid, dominating Boolean input-fit predicate does
                        # not establish that this arithmetic step did not overflow.
                        branch["operands"][0]["value"] = next(
                            inline.args(op)[0] for block in fn["blocks"] for op in block["operations"]
                            if op["op"] == "cbr" and op is not branch)
                    report, code = inline.check_all(snapshot)
                    self.assertNotEqual(code, 0, report)
                    self.assertIn(report["status"], {"rejected", "error"}, report)

    def test_lean_rejects_forged_exact_fact_after_weakened_guard(self):
        fn = copy.deepcopy(function(self.snapshot, "@f.add"))
        ovf = overflow(fn)
        branch_on(fn, f"%t{ovf['results'][2]}")["operands"][0]["value"] = "false"
        normal = inline.Normalize(fn)
        candidate = normal.build()
        for site in normal.sites:
            candidate["certificate"][site["node"]] = [[site["overflow_flag"], ["exact"]]]
        self.assertFalse(bridge.run_checker(CHECKER, bridge.encode(candidate),
                                           {"nodes": len(normal.nodes), "payloads": len(normal.sites)}))


if __name__ == "__main__":
    unittest.main()
