"""Keep the raw LLVM escape hatch closed as the language and compiler grow."""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import ast
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import FnInfo, IFn, Ins
from src.pystachy_compiler.loader import Loader
from src.pystachy_compiler.specs import IROPS
from src.pystachy_compiler.syntax import Node


class NoRawIRTests(unittest.TestCase):
    def test_raw_operation_is_rejected(self):
        self.assertNotIn("raw", IROPS)
        fn = IFn(FnInfo("bad", "@bad", Node("def", "bad", 1), ""))
        fn.blocks[0].code = [Ins("raw", "", "store i64 1, ptr @g.x"),
                             Ins("ret.none", "", "")]
        error = StringIO()
        with redirect_stderr(error), self.assertRaises(SystemExit):
            Gen().verify(fn, False)
        self.assertIn("unknown op raw", error.getvalue())

    def test_frontend_has_no_instruction_text_api(self):
        self.assertFalse(hasattr(Gen, "ins"))
        self.assertFalse(hasattr(Gen, "emit"))
        compiler = Path(__file__).resolve().parent.parent / "src" / "pystachy_compiler"
        for path in compiler.glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    self.assertNotIn(node.func.attr, ("ins", "emit"), (path.name, node.lineno))

    def test_lowering_receives_only_registered_typed_operations(self):
        root = Path(__file__).resolve().parent.parent
        lower = Gen.lower
        seen = set()

        def capture(g, fn):
            g.verify(fn, True)
            for block in fn.blocks:
                for instruction in block.code:
                    self.assertIn(instruction.op, IROPS)
                    self.assertNotEqual(instruction.op, "raw")
                    seen.add(instruction.op)
            lower(g, fn)

        cases = ("typed_ir_slots.py", "typed_ir_numeric.py", "closures_more.py",
                 "tuple_runtime_operations.py", "tuples_and_classes.py")
        with patch.object(Gen, "lower", capture):
            for case in cases:
                path = root / "tests" / case
                Gen().program(Loader([]).program(str(path), path.read_text()))
        self.assertTrue({"slot.pack", "slot.unpack", "mem.load", "mem.store",
                         "field.addr", "alloc.fixed", "ovf"}.issubset(seen), seen)


if __name__ == "__main__":
    unittest.main()
