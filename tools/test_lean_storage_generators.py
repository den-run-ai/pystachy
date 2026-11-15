"""Paired generator transport keeps every independent identity operand checked."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import check_lean_boundary as boundary
import check_lean_storage as storage
from test_lean_storage import block, function, ins

ROOT = Path(__file__).resolve().parent.parent
PROGRAM = ROOT / "tests/programs/numbers/python_int_generator_identity.py"


def paired_generator(kind="gen.yield", companion=True):
    operands = [("%t1", "%slot"), ("%t2", "%ptr")]
    if companion:
        operands.append(("%a2", "dyn"))
    operation = ins(kind, operands=operands, targets=["resume"] if kind == "gen.yield" else [])
    blocks = [block("entry", ins("big.lo", "int", [("%a0", "int+")], 1),
                    ins("big.hi", "%ptr", [("%a0", "int+")], 2), operation)]
    if kind == "gen.yield":
        blocks.append(block("resume", ins("gen.ret")))
    return function(blocks, parameters=("int+", "int+", "dyn"))


class GeneratorStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not storage.DEFAULT_CHECKER.is_file():
            if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1":
                raise RuntimeError("Lean checker required for generator storage controls")
            raise unittest.SkipTest("build the Lean boundary checker")

    def checked(self, fn):
        candidate, metadata = storage.Normalize(fn).build()
        accepted = boundary.run_checker(storage.DEFAULT_CHECKER, boundary.encode(candidate), metadata)
        return accepted, metadata["obligations"]

    def test_two_word_yields_and_returns_remain_transport(self):
        for kind in ("gen.yield", "gen.ret"):
            with self.subTest(kind=kind):
                self.assertEqual(self.checked(paired_generator(kind, companion=False)), (True, 0))

    def test_yield_pair_allows_null_or_existing_identity(self):
        for identity in ("null", "%a2"):
            with self.subTest(identity=identity):
                fn = paired_generator()
                fn["blocks"][0]["operations"][-1]["operands"][2]["value"] = identity
                self.assertEqual(self.checked(fn), (True, 0))

    def test_yield_pair_requires_the_same_integer(self):
        fn = paired_generator()
        fn["blocks"][0]["operations"][1]["operands"][0]["value"] = "%a1"
        self.assertEqual(self.checked(fn), (False, 1))

    def test_yield_identity_operand_still_requires_its_own_fit(self):
        fn = paired_generator()
        operations = fn["blocks"][0]["operations"]
        operations[-1]["operands"][2]["value"] = "%t4"
        operations[-1:-1] = [
            ins("big.lo", "int", [("%a1", "int+")], 3),
            ins("scalar.cast", "dyn", [("%t3", "int")], 4, "inttoptr")]
        self.assertEqual(self.checked(fn), (False, 1))

    def test_yield_transport_requires_exact_operand_shape(self):
        for changed in (0, 1, 2, 3):
            with self.subTest(changed=changed):
                fn = paired_generator()
                operands = fn["blocks"][0]["operations"][-1]["operands"]
                if changed == 3:
                    operands.append({"value": "null", "type": "dyn"})
                else:
                    operands[changed]["type"] = "int"
                self.assertEqual(self.checked(fn), (False, 1))

    def test_return_does_not_acquire_a_third_operand(self):
        self.assertEqual(self.checked(paired_generator("gen.ret")), (False, 1))

    def test_compiled_numeric_generator_and_broken_pair(self):
        env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
        env["PYSTACHY_HOME"] = str(ROOT)
        env["PYSTACHY_PATH"] = PROGRAM.with_suffix(".path").read_text().strip()
        with tempfile.TemporaryDirectory(prefix="pystachy-generator-storage-") as directory:
            output = Path(directory) / "inspection"
            result = subprocess.run(
                [sys.executable, str(ROOT / "tools/inspect_compiler.py"), str(PROGRAM),
                 "--output", str(output), "--typed-after-only", "--timeout", "60"],
                cwd=ROOT, env=env, capture_output=True, text=True, timeout=70)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            snapshot = json.loads((output / "typed-after.json").read_text())
        report, _ = storage.check_all(snapshot)
        self.assertEqual(report["status"], "accepted", report)
        self.assertEqual(report["totals"]["low_word_uses"], 34)
        self.assertEqual(report["totals"]["obligations"], 22)
        self.assertEqual(report["totals"]["proved_obligations"], 22)
        fresh = next(fn for fn in snapshot["functions"] if fn["symbol"] == "@f.fresh.1")
        changed = copy.deepcopy(fresh)
        first = next(op for b in changed["blocks"] for op in b["operations"] if op["op"] == "gen.yield")
        self.assertEqual([a["type"] for a in first["operands"]], ["%slot", "%ptr", "dyn"])
        first["operands"][1]["value"] = "null"
        self.assertEqual(self.checked(changed), (False, 1))


if __name__ == "__main__":
    unittest.main()
