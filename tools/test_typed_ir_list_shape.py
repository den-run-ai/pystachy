"""Bounds proofs distinguish element/identity writes from shape changes."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import Ins
from src.pystachy_compiler.loader import Loader
from src.pystachy_compiler.optimizations import list_shape_clobber
from src.pystachy_compiler.specs import FXALL, FXBIT, LIST_STABLE_SHAPE, RUNTIME


class ListShapeTests(unittest.TestCase):
    def test_stable_primitives_keep_their_observable_write_effects(self):
        for name, mutation in LIST_STABLE_SHAPE.items():
            with self.subTest(name=name):
                self.assertIn("identity", mutation.split())
                effects = RUNTIME[name].split("|")[1].split()
                self.assertIn("wL", effects)
                self.assertNotIn("U", effects)
                self.assertNotIn("U?", effects)
                mask = sum(FXBIT[item] for item in effects)
                self.assertFalse(list_shape_clobber(Ins("rt", "", name), mask))
                # An effect newly allowing arbitrary code invalidates the audit.
                self.assertTrue(list_shape_clobber(Ins("rt", "", name), FXALL))
        self.assertIn("fresh", LIST_STABLE_SHAPE["list.copy"].split())
        self.assertIn("A", RUNTIME["list.copy"].split("|")[1].split())

    def test_missing_contract_and_nonprimitive_writes_are_barriers(self):
        for name in ("list.append", "list.pop", "list.clear", "list.set_slice",
                     "list.del_slice", "list.take", "list.give", "list.sort_r"):
            with self.subTest(name=name):
                self.assertTrue(list_shape_clobber(Ins("rt", "", name), FXBIT["wL"]))
        for kind in ("call", "icall", "mem.store", "mach.store", "tuple.store"):
            with self.subTest(kind=kind):
                self.assertTrue(list_shape_clobber(Ins(kind, "", "list.set"), FXBIT["wL"]))
        self.assertFalse(list_shape_clobber(Ins("list.load", "%slot", ""), FXBIT["rL"]))

    def test_real_updates_retain_fresh_reads_and_checked_fallbacks(self):
        path = Path(__file__).resolve().parents[1] / "tests/programs/optimizations/opt_listget_shape.py"
        shapes = {}
        original = Gen.listget

        def observe(gen, fn):
            changed = original(gen, fn)
            ops = [op for block in fn.blocks for op in block.code]
            shapes[fn.f.name] = (changed, sum(op.op == "rt" and op.s == "list.get" for op in ops))
            if fn.f.name == "updated":
                retained = [(op.op, op.s) for op in ops
                            if op.op == "list.load" or (op.op == "rt" and op.s == "list.set")]
                self.assertEqual(retained, [("list.load", ""), ("rt", "list.set"), ("list.load", "")])
                self.assertNotEqual(fn.fx & FXBIT["wL"], 0)
            return changed

        with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "1", "PYSTACHY_OPT": ""}), \
                patch.object(Gen, "listget", observe):
            Gen().program(Loader([]).program(str(path), path.read_text()))
        self.assertEqual(shapes["updated"], (2, 0))
        for name in ("reversed_read", "copied_read", "sliced_read", "alias_updated"):
            with self.subTest(name=name):
                self.assertEqual(shapes[name], (1, 0))
        for name in ("shrinking", "alias_shrinking", "indirect_write", "direct_write", "changing_length"):
            with self.subTest(name=name):
                self.assertEqual(shapes[name], (0, 1))


if __name__ == "__main__":
    unittest.main()
