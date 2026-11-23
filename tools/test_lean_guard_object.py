"""isinstance(x, int) of a value of object: its int | bool is made where the closed-union checks
see its tag (examples/object_narrowing.py). Corrupting how the caller makes it must be refused:
a bool's bits boxed with the int member's tag, and a union taken from an indirect call's result,
whose tag only the callee's code knows."""
import copy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import check_lean_boundary as boundary
import check_lean_guards as guards

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "tools/lean_boundary/examples/object_narrowing.py"
CHECKER = boundary.DEFAULT_CHECKER


class ObjectNarrowingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CHECKER.is_file():
            if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1":
                raise RuntimeError("Lean checker required for the object narrowing controls")
            raise unittest.SkipTest("build the Lean boundary checker")
        temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temp.cleanup)
        out = Path(temp.name) / "inspection"
        env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
        env["PYSTACHY_HOME"] = str(ROOT)
        result = subprocess.run([sys.executable, str(ROOT / "tools/inspect_compiler.py"), str(EXAMPLE),
                                 "--output", str(out), "--guard-evidence", "--typed-after-only"],
                                cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.snapshot = boundary.read_snapshot(out / "typed-after.json", boundary.MAX_PROGRAM_BYTES)[0]

    def bump(self):
        snapshot = copy.deepcopy(self.snapshot)
        return snapshot, next(fn for fn in snapshot["functions"] if fn["name"] == "bump")

    @staticmethod
    def boxes(function):
        # the caller's two literal-tag boxes of the narrowed int | bool, by their tags
        found = {}
        for block in function["blocks"]:
            for operation in block["operations"]:
                if operation["op"] == "rt" and operation["text"] == "ubox" and operation["type"].startswith("union["):
                    found[operation["operands"][0]["value"]] = (block, operation)
        return found

    def accepted(self, snapshot, function):
        # (as check_all normalizes a function where no compiled store may write a union box: the
        # example has none, which test_union_made_by_the_caller_is_proved also checks)
        candidate, metadata = guards.normalize(snapshot, function, immutable_boxes=True)
        return boundary.run_checker(CHECKER, boundary.encode(candidate), metadata)

    def refused(self, snapshot, function):
        reads = len(guards.inventory(function))
        self.assertGreater(reads, 0)
        try:
            self.assertFalse(self.accepted(snapshot, function))
        except boundary.Unsupported:
            pass
        snapshot["functions"], snapshot["nullcheck_evidence"] = [function], []
        snapshot["guard_inventory"] = {"nullcheck_passes": 0, "removed_checks": 0}
        report, code = guards.check_all(snapshot, CHECKER)
        self.assertIn(code, (1, 2), report)
        self.assertEqual(report["union_reads"], reads)

    def test_union_made_by_the_caller_is_proved(self):
        snapshot, function = self.bump()
        self.assertEqual(sorted(self.boxes(function)), ["1", "2"])
        self.assertGreater(len(guards.inventory(function)), 0)
        self.assertTrue(self.accepted(snapshot, function))
        report, code = guards.check_all(copy.deepcopy(self.snapshot), CHECKER)
        self.assertEqual(code, 0, report)
        self.assertEqual(report["possible_box_writes"], 0)
        self.assertEqual(report["proved_union_reads"], report["union_reads"])

    def test_bool_bits_boxed_with_the_int_tag_are_refused(self):
        snapshot, function = self.bump()
        boxes = self.boxes(function)
        _, bool_box = boxes["1"]
        bool_box["operands"][0]["value"] = "2"  # (the bool entry's bits, boxed as the int member)
        self.refused(snapshot, function)

    def test_union_of_an_indirect_call_is_refused(self):
        snapshot, function = self.bump()
        boxes = self.boxes(function)
        block, int_box = boxes["2"]
        calls = [op for op in block["operations"] if op["op"] == "icall"]
        self.assertEqual(len(calls), 1)
        # (the int entry's call declared to return the union itself, and the box dropped)
        calls[0]["type"] = int_box["type"]
        result = f"%t{calls[0]['results'][0]}"
        made = f"%t{int_box['results'][0]}"
        block["operations"].remove(int_box)
        for other in function["blocks"]:
            for operation in other["operations"]:
                for operand in operation["operands"]:
                    if operand["value"] == made:
                        operand["value"] = result
        self.refused(snapshot, function)


if __name__ == "__main__":
    unittest.main()
