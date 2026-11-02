# CPython 3.13.16 Lib/test/test_positional_only_arg.py (commit
#   cbc944f4bc59639a444dd971c737788ba2283a91,
# SHA-256 3f34be8648b28a6baccb20d65ee65241a14ae2494cf9e3cfc4d12b7362358f6b),
# made mechanically by tools/cpython_test_methods.py: unittest scaffolding becomes plain
# statements that keep each test's inputs and assertions (tests/upstream/core-sweep.md).
# Tests: PositionalOnlyTestCase.test_pos_only_call_via_unpacking.
import re
'Unit tests for the positional only argument syntax specified in PEP 570.'

class PositionalOnlyTestCase:

    def assertRaisesSyntaxError(self, codestr, regex='invalid syntax'):
        try:
            compile(codestr + '\n', '<test>', 'single')
        except SyntaxError as _exc:
            assert re.search(regex, str(_exc))
        else:
            raise AssertionError('did not raise')

    def test_pos_only_call_via_unpacking(self):

        def f(a, b, /):
            return a + b
        assert f(*[1, 2]) == 3


def _PositionalOnlyTestCase__test_pos_only_call_via_unpacking():
    t = PositionalOnlyTestCase()
    t.test_pos_only_call_via_unpacking()
    print('ok PositionalOnlyTestCase.test_pos_only_call_via_unpacking')


_PositionalOnlyTestCase__test_pos_only_call_via_unpacking()
