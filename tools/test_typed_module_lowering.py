"""Keep module declarations and ABI wrappers behind the LLVM lowering boundary."""
import ast
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import Data, FnInfo, IFn, Ins, Val
from src.pystachy_compiler.loader import Loader
from src.pystachy_compiler.lower_module import lower_data
from src.pystachy_compiler.syntax import Node


ROOT = Path(__file__).resolve().parents[1]
# Source-line metadata is emitted after LLVM lowering (see src/README.md).
BACKENDS = {"lowering.py", "lower_module.py", "llvm_abi.py", "source_lines.py", "jit_helpers.py"}


class ModuleLoweringTests(unittest.TestCase):
    def test_completed_functions_keep_one_output_chunk_without_rewriting_prior_output(self):
        g = Gen()
        output = g.out
        output.append("; earlier output\n; preserved in order")
        expected = output.copy()
        for name in ("first", "second"):
            fn = IFn(FnInfo(name, "@" + name, Node("def", name, 1), ""))
            fn.f.ret = "None"
            fn.blocks[0].code = [Ins("ret.none", "", "")]
            g.lower(fn)
            expected.append(f"define internal void @{name}() {{\nentry:\n  ret void\n}}")
            self.assertIs(g.out, output)
            self.assertEqual(output, expected)
        llvm = g.lower_module()
        self.assertIn("\n".join(expected) + "\n", llvm)

    def test_module_assembly_keeps_body_and_final_newline_in_each_mode(self):
        body = ["define void @body() {", "entry:", "  ret void", "}"]
        extension = ["define ptr @PyInit_probe() {", "  ret ptr null", "}"]
        for mode in ("program", "runtime", "extension"):
            with self.subTest(mode=mode):
                g = Gen()
                g.rtmode = mode == "runtime"
                g.ext = "probe" if mode == "extension" else ""
                g.out = body.copy()
                with patch.object(Gen, "pyext", return_value=extension):
                    llvm = g.lower_module()
                    self.assertEqual(g.lower_module(), llvm)
                self.assertEqual(g.out, body)
                self.assertEqual(llvm.count("\n".join(body) + "\n"), 1)
                self.assertTrue(llvm.endswith("\n"))
                self.assertFalse(llvm.endswith("\n\n"))
                if mode == "extension":
                    self.assertTrue(llvm.endswith("\n".join(extension) + "\n"))
                elif mode == "program":
                    self.assertTrue(llvm.endswith("  ret i32 0\n}\n"))

    def test_string_literal_header_matches_runtime_caches(self):
        for text, chars1 in [("", 1), ("ascii", 6), ("a\x00b", 4), ("\xc3\xa9", 0), ("\xf0\x9f\x98\x80", 0)]:
            with self.subTest(text=text):
                data = Data("string", "@s.probe")
                data.text = text
                llvm = lower_data(data)
                n = len(text) + 1
                self.assertIn(f"global {{i64, i64, i64, [{n} x i8]}}", llvm)
                self.assertIn(f"{{i64 {n - 1}, i64 0, i64 {chars1}, [{n} x i8]", llvm)

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
