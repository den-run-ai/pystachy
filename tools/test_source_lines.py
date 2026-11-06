"""Python source locations survive native code generation; disabled IR is unchanged."""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = '''import sys
from helper import imported

def identity(value):
    return value

def outer(values: list[int]) -> int:
    def twice(x: int) -> int:
        return x * 2
    result = 0
    for value in values:
        result += twice(imported(value))
    return result

print(outer([identity(int(sys.argv[1])), 2, 3]))
print(identity("!pysdi0; pystachy source locations"))
'''
HELPER = '''def imported(value: int) -> int:
    result = value * value
    return result + 3
'''


class SourceLinesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        # The tracked path is ASCII; this exercises actual filesystem encodings.
        self.directory = Path(temporary.name) / 'quote"-bang!-café-路径'
        self.directory.mkdir()
        self.path = self.directory / 'program.py'
        self.path.write_text(PROGRAM)
        (self.directory / 'helper.py').write_text(HELPER)
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith('PYSTACHY_') or key == 'PYSTACHY_LLVM'}
        self.env.update(PYSTACHY_HOME=str(ROOT), PYSTACHY_IRCHECK='1')

    def compile_ir(self, setting=None):
        env = dict(self.env)
        if setting is not None:
            env['PYSTACHY_DEBUG_LINES'] = setting
        result = subprocess.run([sys.executable, '-m', 'pystachy', 'ir', str(self.path)],
                                cwd=ROOT, env=env, capture_output=True, check=True, timeout=90)
        self.assertEqual(result.stderr, b'')
        return result.stdout.decode('latin-1')

    def tool(self, name):
        directory = self.env.get('PYSTACHY_LLVM', '')
        found = str(Path(directory) / name) if directory else shutil.which(name)
        if not found or not Path(found).is_file():
            self.skipTest(f'{name} is required for native DWARF validation')
        return found

    def run_tool(self, command):
        return subprocess.run(command, capture_output=True, text=True, check=True, timeout=90)

    def test_disabled_output_and_enabled_instructions(self):
        off = self.compile_ir()
        self.assertEqual(off, self.compile_ir('0'))
        enabled = self.compile_ir('1')
        self.assertEqual(enabled, self.compile_ir('1'))
        self.assertNotIn('!dbg', off)
        body = enabled.split('; pystachy source locations\n')[0]
        body = re.sub(r',? !dbg ![0-9]+', '', body)
        self.assertEqual(off, body)
        self.assertIn('DILocation(line: 0,', enabled)
        self.assertIn('DILocation(line: 12,', enabled)
        self.assertIn('DILocation(line: 2,', enabled)
        self.assertIn('name: "helper.imported"', enabled)
        self.assertIn('name: "outer"', enabled)
        self.assertIn('linkageName:', enabled)
        self.assertIn('!pysdi0; pystachy source locations', enabled)
        self.assertIn('\\22-bang\\21-caf\\C3\\A9-', enabled)
        self.assertIn('\\E8\\B7\\AF\\E5\\BE\\84', enabled)

    def test_native_dwarf_verifies_after_optimization(self):
        opt, clang, dwarf = [self.tool(name) for name in ('opt', 'clang', 'llvm-dwarfdump')]
        ir = self.directory / 'program.ll'
        optimized = self.directory / 'optimized.ll'
        obj = self.directory / 'program.o'
        ir.write_text(self.compile_ir('1'), encoding='latin-1')
        self.run_tool([opt, '-S', '-passes=default<O2>,verify', str(ir), '-o', str(optimized)])
        self.run_tool([clang, '-O2', '-c', str(optimized), '-o', str(obj)])
        verified = self.run_tool([dwarf, '--verify', str(obj)])
        self.assertIn('No errors.', verified.stdout)
        lines = self.run_tool([dwarf, '--debug-line', str(obj)]).stdout
        self.assertIn('program.py', lines)
        self.assertIn('helper.py', lines)
        # These are native address/line rows, not just metadata strings.
        rows = [line.split() for line in lines.splitlines() if line.startswith('0x')]
        self.assertTrue(any(len(row) > 2 and row[1] == '12' for row in rows), lines)
        self.assertTrue(any(len(row) > 2 and row[1] == '2' for row in rows), lines)
        info = self.run_tool([dwarf, '--debug-info', str(obj)]).stdout
        self.assertIn('DW_LANG_Python', info)
        self.assertIn('imported', info)
        self.assertIn('outer', info)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'observes the ELF GDB JIT interface')
    def test_default_orc_registers_python_line_table(self):
        clang, dwarf = [self.tool(name) for name in ('clang', 'llvm-dwarfdump')]
        self.tool('lli')
        library = self.directory / 'observer.so'
        obj = self.directory / 'registered.o'
        source = self.directory / 'jit_program.py'
        self.run_tool([clang, '-shared', '-fPIC', '-O2', str(ROOT / 'tools/source_lines_jit.c'),
                       '-o', str(library), '-ldl'])
        source.write_text('import sys\nfrom ffi import extern, c_int64\n'
                          f'@extern({str(library)!r})\n'
                          'def source_debug_registered(source: str, output: str) -> c_int64: ...\n'
                          'def square(value: float) -> float:\n    return value * value\n'
                          'print(square(float(sys.argv[1])))\n'
                          f'print(source_debug_registered("jit_program.py", {str(obj)!r}))\n')
        for setting in ('0', '1'):
            env = dict(self.env, PYSTACHY_DEBUG_LINES=setting)
            result = subprocess.run([sys.executable, '-m', 'pystachy', 'run', str(source), '3.5'],
                                    cwd=ROOT, env=env, capture_output=True, text=True,
                                    check=True, timeout=180)
            self.assertEqual(result.stdout, '12.25\n' + setting + '\n')
            if setting == '0':
                self.assertFalse(obj.exists())
        verified = self.run_tool([dwarf, '--verify', str(obj)])
        self.assertIn('No errors.', verified.stdout)
        lines = self.run_tool([dwarf, '--debug-line', str(obj)]).stdout
        # The returned ELF must have actual file/line entries; a string constant
        # containing the filename alone is not evidence of registered debug info.
        self.assertIn('name: "jit_program.py"', lines)
        rows = [line.split() for line in lines.splitlines() if line.startswith('0x')]
        self.assertTrue(any(len(row) > 2 and row[1] in ('6', '7') for row in rows), lines)


class ProfileCostTests(unittest.TestCase):
    def test_exclusive_costs_and_shared_identifier_tables(self):
        from bench.source_attribution.run import callgrind_summary
        # Call targets may introduce compressed IDs reused by later definitions.
        # Inclusive call-edge cost must not be counted twice, and its source
        # position still participates in the next relative position.
        fixture = """positions: line
events: Ir
summary: 21
fl=(1) sample.py
fn=(1) f
10 5
+2 7
cfl=(2) callee.py
cfn=(2) g
calls=1 2
* 999
+1 2
fl=(2)
fn=(2)
2 7
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'profile'
            path.write_text(fixture)
            result = callgrind_summary(path)
        self.assertEqual(result['summary_Ir'], 21)
        self.assertEqual(result['exclusive_Ir'], 21)
        self.assertEqual(result['python_line_Ir'], 21)
        self.assertEqual({(row['file'], row['line'], row['function'], row['Ir'])
                          for row in result['top_python_lines']},
                         {('sample.py', 10, 'f', 5), ('sample.py', 12, 'f', 7),
                          ('sample.py', 13, 'f', 2), ('callee.py', 2, 'g', 7)})


if __name__ == '__main__':
    unittest.main()
