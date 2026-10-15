"""Keep module declarations and ABI wrappers behind the LLVM lowering boundary."""
import ast
from pathlib import Path
import re
import unittest

from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import Data, Val
from src.pystachy_compiler.loader import Loader
from src.pystachy_compiler.lower_module import lower_data


ROOT = Path(__file__).resolve().parents[1]
BACKENDS = {"lowering.py", "lower_module.py", "llvm_abi.py"}


class ModuleLoweringTests(unittest.TestCase):
    def test_frontend_has_no_module_or_abi_llvm_templates(self):
        declaration = re.compile(
            r"(?:^|\n)\s*(?:define|declare)\s|"
            r" = (?:type \{|(?:private|internal)(?: unnamed_addr)? (?:constant|global) )"
        )
        for path in sorted((ROOT / "src/pystachy_compiler").glob("*.py")):
            if path.name in BACKENDS:
                continue
            with self.subTest(module=path.name):
                tree = ast.parse(path.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, ast.Constant) and isinstance(node.value, str):
                        self.assertIsNone(declaration.search(node.value),
                                          f"LLVM module template at {path.name}:{node.lineno}")
                    if (isinstance(node, ast.Attribute) and node.attr == "out"
                            and isinstance(node.value, ast.Name) and node.value.id == "self"):
                        # Gen owns the backend output buffer; only lowering may write it.
                        self.assertEqual(path.name, "gen.py",
                                         f"backend output access at {path.name}:{node.lineno}")

    def test_frontend_records_native_globals_and_structured_constants(self):
        source = '''from typing import Callable

def ident(x: int) -> int:
    return x

callback: Callable[[int], int] = ident
number = 3
text = "quoted \\\"\\\\\\x00"
class Trouble(Exception):
    pass
print(callback(number), text)
raise Trouble("failure")
'''
        g = Gen()
        llvm = g.program(Loader([]).program("module_data.py", source))
        self.assertTrue(g.globs)
        self.assertTrue(all(isinstance(v, Val) for v in g.globs))
        self.assertIn("int", [v.t for v in g.globs])
        self.assertTrue(all(isinstance(d, Data) for d in g.consts))
        self.assertEqual({d.kind for d in g.consts}, {"string", "callable", "exception"})
        for d in g.consts:
            self.assertIn(lower_data(d), llvm)
        self.assertIn("@g.number = internal global i64 zeroinitializer", llvm)
        self.assertTrue(llvm.endswith("  ret i32 0\n}\n"))


if __name__ == "__main__":
    unittest.main()
