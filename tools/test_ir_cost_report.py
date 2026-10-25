"""Keep diagnostic call counts distinct from declarations and runtime profiles."""
from contextlib import redirect_stderr
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import ir_cost_report as report


IR = b'''declare ptr @pys_alloc(i64)
declare void @sink(ptr)
declare void @callee()
define i32 @main() {
entry:
  %p = tail call ptr @pys_alloc(i64 16)
  call void @sink(ptr @pys_alloc) ; not a call to the allocator
  call void %fp(ptr @pys_alloc)
  invoke void @callee() to label %ok unwind label %bad
  ret i32 0
}
define void @unused() {
  call ptr @pys_alloc(i64 32)
  ret void
}
'''


class InventoryTests(unittest.TestCase):
    def test_counts_calls_not_symbol_mentions_and_keeps_indirect_calls(self):
        result = report.inventory(IR, '^main$')
        self.assertEqual(result['calls'], {'<indirect>': 1, '@callee': 1, '@pys_alloc': 1, '@sink': 1})
        self.assertEqual(result['call_kinds'], {'call': 3, 'invoke': 1})
        self.assertEqual(result['runtime_definitions'], 0)
        self.assertEqual(result['runtime_declarations'], 1)
        self.assertEqual(result['defined_functions'], 2)
        self.assertEqual(result['selected_functions'], 1)
        self.assertEqual(result['sha256'], hashlib.sha256(IR).hexdigest())

    def test_linked_runtime_is_distinguished_and_attributes_are_retained(self):
        linked = IR.replace(b'declare ptr @pys_alloc(i64)', b'''define noalias nonnull ptr @pys_alloc(i64 %n) #0 {
  ret ptr null
}
attributes #0 = { noinline allocsize(0) }
''')
        result = report.inventory(linked)
        symbol = result['runtime_symbols']['pys_alloc']
        self.assertEqual(result['runtime_definitions'], 1)
        self.assertEqual(result['runtime_declarations'], 0)
        self.assertIn('noalias nonnull', symbol['header'])
        self.assertEqual(symbol['attribute_groups'], ['{ noinline allocsize(0) }'])
        self.assertEqual(result['calls']['@pys_alloc'], 2)

    def test_quoted_names_comments_and_unknown_calls(self):
        result = report.inventory(b'''define void @"f;a"() {
  ; call void @fake()
  call void @"pys_odd;name"()
  call void asm sideeffect "call @pys_fake()", ""()
  callbr void @jump() to label %end [label %end]
  ret void
}
''')
        self.assertEqual(result['calls'], {'<unresolved>': 1, '@jump': 1, '@pys_odd;name': 1})
        self.assertEqual(result['functions']['f;a']['unresolved_lines'], [4])

    def test_bad_inputs_are_not_reported_as_zero_cost(self):
        for data in (b'', b'; not a module', b'define void @f()\n{\n}',
                     b'define void @f() {\n', b'declare void @f() #7'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                report.inventory(data)

    def test_cli_preserves_stage_identity_and_does_not_overwrite_input(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'raw.ll'
            output = Path(directory) / 'report.json'
            source.write_bytes(IR)
            report.main(['--ir', f'raw={source}', '--ir', f'control={source}', '-o', str(output)])
            result = json.loads(output.read_text())
            self.assertEqual(set(result['modules']), {'raw', 'control'})
            for args in ([f'raw={source}', f'raw={source}'], ['invalid']):
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    report.main([value for arg in args for value in ('--ir', arg)])
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                report.main(['--ir', f'raw={source}', '-o', str(source)])
            self.assertEqual(source.read_bytes(), IR)


if __name__ == '__main__':
    unittest.main()
