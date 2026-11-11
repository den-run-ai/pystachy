"""Positive-step loops retain the lower bound needed by negative offsets."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import check_lean_access as access
from test_lean_access import CHECKER  # imports the mandatory-checker guard too

ROOT = Path(__file__).resolve().parent.parent


class RangeLowerBoundTests(unittest.TestCase):
    def candidate(self, start, step, offset):
        nodes = [
            {"op": "lit", "dst": "i", "value": start, "next": 1},
            {"op": "length", "dst": "n", "list": "xs", "next": 2},
            {"op": "test", "cond": {"cmp": "sle", "a": "stop", "b": "n"}, "yes": 3, "no": 10},
            {"op": "jump", "next": 4},
            {"op": "test", "cond": {"cmp": "slt", "a": "i", "b": "stop"}, "yes": 5, "no": 10},
            {"op": "add_checked", "dst": "j", "src": "i", "k": offset, "next": 6, "overflow": 10},
            {"op": "load", "list": "xs", "index": "j", "next": 7},
            {"op": "add_checked", "dst": "next_i", "src": "i", "k": step, "next": 8, "overflow": 10},
            {"op": "copy", "dst": "i", "src": "next_i", "next": 9},
            {"op": "jump", "next": 4}, {"op": "stop"},
        ]
        certificate, _ = access.infer_certificate(nodes)
        return {"schema_version": 1, "program": {"entry": 0, "nodes": nodes}, "certificate": certificate}

    def assert_checked(self, candidate, expected):
        self.assertEqual(access.explain(candidate) is None, expected)
        if CHECKER.is_file():
            self.assertEqual(access.run_checker(CHECKER, access.encode(candidate), {"nodes": 11, "accesses": 1}), expected)

    def test_positive_steps_preserve_each_required_initial_bound(self):
        for start in (1, 2, 5):
            for step in (1, 2, 3):
                with self.subTest(start=start, step=step):
                    self.assert_checked(self.candidate(start, step, -start), True)

    def test_invalid_start_and_descending_induction_still_fail(self):
        self.assert_checked(self.candidate(0, 2, -1), False)
        self.assert_checked(self.candidate(1, -2, -1), False)

    @unittest.skipUnless(CHECKER.is_file(), "build the Lean checker")
    def test_compiled_stride_two_and_reused_index_loop(self):
        source = """def offsets(xs: list[int], out: list[int], n: int, step: int) -> None:
    for i in range(1, n, 2):
        out[i-1] = xs[i-1] + xs[i]
    for i in range(1, n, step):
        out[i-1] += 1

out = [0] * 4
offsets([1, 2, 3, 4], out, 4, 2)
print(out)
"""
        with tempfile.TemporaryDirectory() as directory:
            program, inspected = Path(directory) / "offsets.py", Path(directory) / "snapshot"
            program.write_text(source)
            result = subprocess.run([sys.executable, str(ROOT / "tools/inspect_compiler.py"), str(program),
                                     "--output", str(inspected), "--typed-after-only"],
                                    cwd=ROOT, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report, code = access.check_all(json.loads((inspected / "typed-after.json").read_text()))
            self.assertEqual(code, 0, report)
            self.assertGreater(report["totals"]["accesses"], 0)
            self.assertEqual(report["totals"]["accesses"], report["totals"]["proved_accesses"])


if __name__ == "__main__":
    unittest.main()
