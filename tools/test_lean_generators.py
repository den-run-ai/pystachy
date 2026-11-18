"""Generators in the union and field checks (check_lean_guards, check_lean_fields).

A call of a generator function returns at gen.start, before its body runs, and its caller runs
while it is suspended. Each refutation corrupts actual compiler IR of examples/generators.py as a
compiler bug could; Lean must reject it while the original stays proved.
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
import check_lean_gc as gc
import check_lean_guards as guards
from test_lean_boundary import instruction as op

ROOT = Path(__file__).resolve().parent.parent
CHECKER = boundary.DEFAULT_CHECKER
EXAMPLE = ROOT / "tools/lean_boundary/examples/generators.py"


def inspect(program, directory):
    env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
    env["PYSTACHY_HOME"] = str(ROOT)
    result = subprocess.run([sys.executable, str(ROOT / "tools/inspect_compiler.py"), str(program),
                             "--output", str(directory), "--guard-evidence", "--typed-after-only"],
                            cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return json.loads((directory / "typed-after.json").read_text())


class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CHECKER.is_file():
            if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1":
                raise RuntimeError("Lean checker required for generator controls")
            raise unittest.SkipTest("build the Lean boundary checker")
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.snapshot = inspect(EXAMPLE, Path(cls.temp.name) / "generators")

    def sample(self):
        return copy.deepcopy(self.snapshot)

    @staticmethod
    def function(snapshot, symbol):
        return next(fn for fn in snapshot["functions"] if fn["symbol"] == symbol)

    @staticmethod
    def union(snapshot, symbol):
        report, _ = guards.check_all(snapshot, CHECKER)
        return next(r for r in report["records"] if r["function"] == symbol and r.get("scope") != guards.REMOVALS)

    @staticmethod
    def construction(snapshot):
        results, _ = fields.check_all(snapshot, CHECKER)
        return next(r for r in results if r["function"] == "@m.Tally.__init__")

    @staticmethod
    def tag_tests(fn):
        """The blocks of fn that end in a branch on a union tag test, in order."""
        producers = {f"%t{n}": operation for block in fn["blocks"] for operation in block["operations"]
                     for n in operation["results"]}

        def tests_tag(value):
            test = producers.get(value)
            return (test is not None and test["op"] == "num.cmp"
                    and producers.get(test["operands"][0]["value"], {}).get("op") == "union.tag")
        return [block for block in fn["blocks"]
                if block["operations"][-1]["op"] == "cbr" and tests_tag(block["operations"][-1]["operands"][0]["value"])]

    @staticmethod
    def untest(block):
        """Branch to the member's side of the block's tag test, as if it had passed."""
        test = block["operations"][-1]
        block["operations"][-1] = op("br", targets=[test["targets"][0]])

    def test_generators_are_proved(self):
        snapshot = self.sample()
        for symbol, reads in (("@f.steps.1", 3), ("@f.bump.1", 2)):
            record = self.union(snapshot, symbol)
            self.assertEqual((record["status"], record["obligations"]), ("accepted", reads))
        self.assertEqual(self.construction(snapshot)["status"], "accepted")
        self.assertEqual(gc.check_all(snapshot, CHECKER)[0]["status"], "accepted")

    def test_a_tested_union_local_needs_its_test(self):
        # (steps tests s before it first suspends and reads it on both sides of that suspension)
        snapshot = self.sample()
        steps = self.function(snapshot, "@f.steps.1")
        tests = self.tag_tests(steps)
        self.assertEqual(len(tests), 1)
        self.untest(tests[0])
        self.assertEqual(self.union(snapshot, "@f.steps.1")["status"], "rejected")

    def test_a_suspension_may_change_a_global(self):
        # bump stores an int into the global state, suspends, and tests state's tag again before it
        # reads it: without the test the read is rejected, as a caller may store a str meanwhile
        snapshot = self.sample()
        bump = self.function(snapshot, "@f.bump.1")
        tests = self.tag_tests(bump)
        self.assertEqual(len(tests), 1)
        self.untest(tests[0])
        self.assertEqual(self.union(snapshot, "@f.bump.1")["status"], "rejected")
        # (the stored int is what the read would find if no caller ran there)
        suspends = next(block for block in bump["blocks"] if block["operations"][-1]["op"] == "gen.yield")
        suspends["operations"][-1] = op("br", targets=suspends["operations"][-1]["targets"])
        self.assertEqual(self.union(snapshot, "@f.bump.1")["status"], "accepted")

    def test_a_generator_call_returns_before_its_body(self):
        # A layout that lets Tally's code read total unflagged, and __init__ reading it right after
        # self.fill(): only fill's body assigns total, and the call does not run it.
        snapshot = self.sample()
        snapshot["class_layouts"]["Tally"]["flags"].pop("total")
        self.assertEqual(self.construction(snapshot)["status"], "accepted")
        block = self.function(snapshot, "@m.Tally.__init__")["blocks"][0]
        at = next(i for i, operation in enumerate(block["operations"])
                  if operation["op"] == "call" and operation["text"] == "@m.Tally.fill.1")
        obj = block["operations"][at]["operands"][0]["value"]
        total = snapshot["class_layouts"]["Tally"]["fields"].index("total")
        block["operations"][at + 1:at + 1] = [
            dict(op("field.addr", "*int", results=[900], operands=[(obj, "Tally")]), immediate=total),
            op("mem.load", "int", results=[901], operands=[("%t900", "*int")])]
        result = self.construction(snapshot)
        self.assertEqual(result["status"], "rejected", result)


if __name__ == "__main__":
    unittest.main()
