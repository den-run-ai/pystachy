"""Differential semantics and native execution for bounded regex residuals."""
import os
from pathlib import Path
import random
import re
import shlex
import subprocess
import sys
import tempfile
import types
import unittest

import regex_specialize as emitter


ROOT = Path(__file__).resolve().parents[1]
DATE = r'(\d{4})-(\d{2})-(\d{2})'


def helper(pattern=DATE, flags=0, port=False):
    module = types.ModuleType('generated_regex_probe')
    exec(emitter.generate(pattern, flags), module.__dict__)
    if port:
        module.re = emitter.load_port()
    return module


class ResidualTests(unittest.TestCase):
    def compare(self, pattern, strings, flags=0):
        theirs = re.compile(pattern, flags)
        for port in [False, True]:
            own = helper(pattern, flags, port)
            rx = own.re.compile(pattern, flags)
            for string in strings:
                for pos, end in [(0, len(string)), (-2, len(string) + 2), (1, len(string)),
                                 (0, -1), (3, 1), (len(string) + 1, len(string) + 2)]:
                    expected = theirs.findall(string, pos, end)
                    with self.subTest(pattern=pattern, port=port, string=string, pos=pos, end=end):
                        self.assertEqual(own.findall_generic(rx, string, pos, end), expected)
                        self.assertEqual(own.findall_vm(rx, string, pos, end), expected)
                        self.assertEqual(own.findall_specialized(rx, string, pos, end), expected)
                        self.assertEqual(own.findall_concrete(rx, string, pos, end), expected)

    def test_checked_in_example_is_reproducible(self):
        self.assertEqual(emitter.generate(DATE), (ROOT / 'bench/regex_date_generated.py').read_text())

    def test_random_dates_and_ranges(self):
        rng = random.Random(14026)
        strings = ['', '2026-10-142027-01-09', '99999-12-34', '٢٠٢٦-١٠-١٤', 'é 2026-10-14']
        for _ in range(120):
            chunks = [''.join(rng.choices('abc0123456789-/. ', k=rng.randrange(30))),
                      f'{rng.randrange(10000):04}-{rng.randrange(100):02}-{rng.randrange(100):02}']
            rng.shuffle(chunks)
            strings.append(''.join(chunks))
        self.compare(DATE, strings)

    def test_arity_nested_and_empty_captures(self):
        cases = [r'([a-z]{2})([0-9]{2})', r'(a(b))(c)', r'(a)()(b)',
                 r'(a)(b)(c)(d)', r'(a)(b)(c)(d)(e)', r'(?:ab)(c)(d)']
        for pattern in cases:
            self.compare(pattern, ['', 'xxab12abcdeabcdabxx', 'abcdcde', 'é abcde'])

    def test_categories_cover_entire_ascii_domain(self):
        for category in [r'\d', r'\D', r'\s', r'\S', r'\w', r'\W']:
            for flags in [0, re.ASCII]:
                self.compare('(' + category + ')(x)', [chr(c) + 'x' for c in range(128)], flags)
        self.compare(r'(\w{2})(\s)(\D)', ['ab x', 'ab\x1cx', 'éβ x', 'ab\u00a0x'])

    def test_classes_and_negation(self):
        for pattern in [r'([^\d])(x)', r'([a-zA-Z_]{2})([0-9])', r'([\s])(x)', r'(a|b)(c)',
                        r'([^a-c])(x)', r'(?P<first>a)(?P<second>b)']:
            self.compare(pattern, ['ab1 Ax1', '\x1cx', 'dx', 'éx', 'ab', 'xxabxx'])

    def test_guard_misses_keep_fixed_result_abi(self):
        for port in [False, True]:
            own = helper(port=port)
            for pattern, flags in [(r'(\d{4})/(\d{2})/(\d{2})', 0), (DATE, re.ASCII),
                                   (r'(\d+)-(\d+)-(\d+)', 0), (r'(a)?(b)(c)', 0),
                                   (r'()(a?)()', 0)]:
                rx = own.re.compile(pattern, flags)
                self.assertFalse(own.compatible(rx))
                for string in ['2026/10/14 2026-10-14', 'é ٢٠٢٦-١٠-١٤', 'abc bc aaa']:
                    self.assertEqual(own.findall_specialized(rx, string), re.findall(pattern, string, flags))
            with self.assertRaises(ValueError):
                own.findall_specialized(own.re.compile('(a)(b)'), 'ab')

    def test_portable_large_bounds_preserve_overflow(self):
        own = helper()
        rx = re.compile(DATE)
        for bounds in [(2**100, 20), (0, 2**100), (-2**100, 20)]:
            with self.assertRaises(OverflowError):
                own.findall_specialized(rx, '2026-10-14', *bounds)

    def test_bytecode_mutation_is_guarded(self):
        own = helper(port=True)
        rx = own.re.compile(DATE)
        original = rx._code[:]
        literal = own.re.LITERAL
        index = next(i + 1 for i in range(len(rx._code) - 1)
                     if rx._code[i] == literal and rx._code[i + 1] == ord('-'))
        try:
            rx._code[index] = ord('/')
            self.assertFalse(own.compatible(rx))
            string = '2026/10-14 2026-10-14'
            self.assertEqual(own.findall_specialized(rx, string), [('2026', '10', '14')])
            self.assertEqual(own.findall_specialized(rx, string), own.findall_vm(rx, string))
        finally:
            rx._code[:] = original

    def test_rejections_and_bounded_empty_expansion(self):
        patterns = [r'(a+)(b)', r'(ab|cd)(x)', r'(?=(a))(b)', r'(a)(b)\1',
                    r'(a?)(b)', r'(a)(b).*', r'((a){2})(b)', r'(a){33}(b)',
                    r'()(a*)', r'(?i:(a))(b)', '()()(?:(?:){32}){32}x',
                    '(a)(b)' + 'x' * 5000, '(a)(b)' + 'x' * 129]
        for pattern in patterns:
            with self.subTest(pattern=pattern), self.assertRaises(ValueError):
                emitter.generate(pattern)
        with self.assertRaises(ValueError):
            emitter.generate('(a)(b)', re.IGNORECASE)


class NativeTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('PYSTACHY_LLVM'), 'LLVM is required for native probes')
    def test_compiled_generated_shapes(self):
        compiler = shlex.split(os.environ.get('REGEX_SPECIALIZATION_COMPILER',
                                              sys.executable + ' ' + str(ROOT / 'pystachy.py')))
        env = dict(os.environ, PYSTACHY_HOME=str(ROOT), PYSTACHY_IRCHECK='1')
        patterns = [r'(\s)(x)', r'(a(b))(c)', r'(a)(b)(c)(d)', r'(a)(b)(c)(d)(e)']
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            lines = ['import re']
            for index, pattern in enumerate(patterns):
                name = f'residual{index}'
                (directory / (name + '.py')).write_text(emitter.generate(pattern))
                lines.extend([f'import {name}',
                              f'print({name}.findall_specialized(re.compile({pattern!r}), "ab abc abcde \\x1cx"))'])
            program = directory / 'shape_probe.py'
            program.write_text('\n'.join(lines) + '\n')
            expected = subprocess.run([sys.executable, str(program)], capture_output=True, text=True,
                                      check=True).stdout
            result = subprocess.run(compiler + ['run', str(program)], cwd=ROOT, env=env,
                                    capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout, expected)

    @unittest.skipUnless(os.environ.get('PYSTACHY_LLVM'), 'LLVM is required for native probes')
    def test_jit_aot_and_gc_fallback(self):
        compiler = shlex.split(os.environ.get('REGEX_SPECIALIZATION_COMPILER',
                                              sys.executable + ' ' + str(ROOT / 'pystachy.py')))
        env = dict(os.environ, PYSTACHY_HOME=str(ROOT), PYSTACHY_IRCHECK='1')
        program = ROOT / 'bench/regex_specialized.py'
        result = subprocess.run(compiler + ['run', str(program), 'check'], cwd=ROOT, env=env,
                                capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, 'check ok\n')
        with tempfile.TemporaryDirectory() as temporary:
            executable = str(Path(temporary) / 'regex-check')
            subprocess.run(compiler + ['build', str(program), '-o', executable], cwd=ROOT, env=env,
                           capture_output=True, text=True, check=True)
            for stress in ['0', '1']:
                result = subprocess.run([executable, 'check'], env=dict(env, PYSTACHY_GC_STRESS=stress),
                                        capture_output=True, text=True, check=True)
                self.assertEqual(result.stdout, 'check ok\n')


if __name__ == '__main__':
    unittest.main()
