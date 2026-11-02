# CPython 3.13.16 Lib/test/test_reprlib.py (commit cbc944f4bc59639a444dd971c737788ba2283a91,
# SHA-256 ec84a6d632f43fce37efde8f18f6507dfec899bbbdae99000326a8c30fe17621),
# made mechanically by tools/cpython_test_methods.py: unittest scaffolding becomes plain
# statements that keep each test's inputs and assertions (tests/upstream/core-sweep.md).
# Tests: ReprTests.test_range.
"""
  Test cases for the repr module
  Nick Mathewson
"""

class ReprTests:

    def test_range(self):
        assert repr(range(1)) == 'range(0, 1)'
        assert repr(range(1, 2)) == 'range(1, 2)'
        assert repr(range(1, 4, 3)) == 'range(1, 4, 3)'


def _ReprTests__test_range():
    t = ReprTests()
    t.test_range()
    print('ok ReprTests.test_range')


_ReprTests__test_range()
