"""C ABI discovery retains validated plans until consuming LLVM lowering."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_compiler_pipeline import ROOT, SETUP


class CompilerABIStageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith("PYSTACHY_")}
        self.env.update(PYSTACHY_HOME=str(ROOT), PYSTACHY_IRCHECK="1")

    def source(self, text):
        path = self.directory / "program.py"
        path.write_text(text, encoding="utf-8")
        return path

    def staged(self, path, script):
        return subprocess.run([sys.executable, "-c", SETUP + script, str(path)],
                              cwd=ROOT, env=self.env, text=True, capture_output=True,
                              timeout=45)

    def ordinary(self, path):
        return subprocess.run([sys.executable, str(ROOT / "pystachy.py"), "ir", str(path)],
                              cwd=ROOT, env=self.env, text=True, capture_output=True,
                              timeout=45)

    def succeeded(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_adapters_remain_plans_until_lowering(self):
        script = """
from src.pystachy_compiler import lower_module
from src.pystachy_compiler.lower_module import ExternDecl

def staged(gen, modules):
    with patch.object(lower_module, 'lower_extern', forbidden), \
         patch.object(lower_module, 'c_declaration', forbidden), \
         patch.object(Gen, 'lower', forbidden):
        gen.typed_program(modules)
    assert gen.pipeline.stage == 'finalize'
    assert gen.externs, 'the probe discovered no ABI adapters'
    assert all(isinstance(plan, ExternDecl) for plan in gen.externs.values())
    assert not gen.out, 'frontend retained LLVM function bodies'
    with patch.object(Gen, 'externtype', forbidden), \
         patch.object(Gen, 'cextern', forbidden), \
         patch.object(Gen, 'extern_decl', forbidden):
        return gen.lower_program()

with patch.object(Gen, 'program', staged):
    print(driver.compile_program(str(path), source, dirs, ''), end='')
"""
        # Cover converted C integers/strings, offset lists, captured integer and
        # identity policies, ctypes declarations, and direct embedded-CPython ABI.
        for name in ("c_libc", "c_at", "c_python_int", "c_list_identity",
                     "c_ctypes_scalars", "py_samesym"):
            with self.subTest(name=name):
                path = ROOT / "tests" / "ffi" / (name + ".py")
                expected = self.ordinary(path)
                actual = self.staged(path, script)
                self.succeeded(expected)
                self.succeeded(actual)
                self.assertEqual(actual.stdout, expected.stdout)
                self.assertEqual(actual.stderr, expected.stderr)

    def test_plans_capture_types_and_policies_without_borrowed_ast(self):
        path = ROOT / "tests" / "ffi" / "c_list_identity.py"
        result = self.staged(path, """
from src.pystachy_compiler import lower_module
from src.pystachy_compiler.lower_module import lower_extern

def staged(gen, modules):
    gen.typed_program(modules)
    before = {symbol: lower_extern(plan) for symbol, plan in gen.externs.items()}
    assert any(plan.dynamic for plan in gen.externs.values())
    for f in gen.funcs.values():
        if f.extern:
            f.ptypes.append('bool')
            f.ret = 'bool'
            f.csym = '@changed'
            f.lib = 'changed'
    # Serializing retained plans must not reread the AST, policies or generator.
    with patch.object(Gen, 'externtype', forbidden), \
         patch.object(Gen, 'runtime', forbidden), \
         patch.object(lower_module, 'dynamic_program', forbidden), \
         patch.object(lower_module, 'int_lists', forbidden):
        after = {symbol: lower_extern(plan) for symbol, plan in gen.externs.items()}
    assert before == after
    return ''

with patch.object(Gen, 'program', staged):
    driver.compile_program(str(path), source, dirs, '')
""")
        self.succeeded(result)

    def test_normalized_c_aliases_share_one_signature(self):
        path = self.source('''from ffi import extern, c_int64, c_ssize_t, c_void_p, c_buf
@extern("", "same")
def first(value: c_int64) -> c_int64: ...
@extern("", "same")
def second(value: c_ssize_t) -> c_ssize_t: ...
@extern("", "pointer")
def pointer(value: c_void_p) -> c_void_p: ...
@extern("", "pointer")
def buffer(value: c_buf) -> c_void_p: ...
''')
        result = self.staged(path, """
from src.pystachy_compiler.lower_module import c_signature

g, modules = fresh()
g.typed_program(modules)
assert c_signature(g.csyms['same']) == ['i64', 'i64']
assert c_signature(g.csyms['pointer']) == ['ptr', 'ptr']
assert len(g.externs) == 4
""")
        self.succeeded(result)

    def test_conflicting_c_signatures_fail_during_discovery(self):
        for name in ("c_dup", "c_rt", "c_bool"):
            with self.subTest(name=name):
                path = ROOT / "tests" / "ffi" / "errors" / (name + ".py")
                expected = self.ordinary(path)
                self.assertEqual(expected.returncode, 1, expected.stderr)
                result = self.staged(path, """
g, modules = fresh()
prepared = g.prepare_program(modules)
with redirect_stderr(StringIO()) as diagnostic:
    try:
        g.discover_program(prepared)
    except SystemExit as error:
        assert error.code == 1
    else:
        raise AssertionError('invalid C ABI completed discovery')
assert g.pipeline.stage == 'prepare'
assert g.pipeline.active == 'discover'
print(diagnostic.getvalue(), end='')
""")
                self.succeeded(result)
                self.assertEqual(result.stdout, expected.stderr)

    def test_signed_and_unsigned_c_attributes_remain_distinct(self):
        path = self.source('''from ffi import extern, c_int, c_uint
@extern("", "same")
def signed(value: c_int) -> c_int: ...
@extern("", "same")
def unsigned(value: c_uint) -> c_uint: ...
''')
        result = self.ordinary(path)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("declared again with other types", result.stderr)
        self.assertIn("signext i32 @same(i32 signext)", result.stderr)
        self.assertIn("zeroext i32 @same(i32 zeroext)", result.stderr)

    def test_runtime_declarations_are_plans(self):
        path = self.source('''def pys_text_len(value: str) -> int: ...
def pys_private_c(value: int) -> int: ...
def pys_example(value: str) -> int:
    return pys_private_c(pys_text_len(value))
''')
        result = self.staged(path, """
from src.pystachy_compiler import lower_module
from src.pystachy_compiler.lower_module import ExternDecl, lower_extern

seen = []
def staged(gen, modules):
    with patch.object(lower_module, 'lower_extern', forbidden):
        gen.typed_program(modules)
    assert gen.rtmode
    assert all(isinstance(plan, ExternDecl) for plan in gen.externs.values())
    assert any(plan.provided for plan in gen.externs.values())
    assert any(not plan.provided for plan in gen.externs.values())
    assert all(not plan.c for plan in gen.externs.values())
    assert any(lower_extern(plan).startswith('declare ') for plan in gen.externs.values())
    seen.append(gen)
    return gen.lower_program()
with patch.object(Gen, 'program', staged):
    output = driver.runtime_ir(str(path), source, False)
assert len(seen) == 1
assert 'declare i64 @pys_private_c(i64)' in output
""")
        self.succeeded(result)


if __name__ == "__main__":
    unittest.main()
