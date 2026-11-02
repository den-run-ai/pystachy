# CPython 3.13.16 Lib/test/test_richcmp.py (commit cbc944f4bc59639a444dd971c737788ba2283a91,
# SHA-256 87ffd49f08a617224cdbb84f0eeb7cef643f3cd918090c606a311a25d929d135),
# made mechanically by tools/cpython_test_methods.py: unittest scaffolding becomes plain
# statements that keep each test's inputs and assertions (tests/upstream/core-sweep.md).
# Tests: ListTest.test_coverage.
class ListTest:

    def test_coverage(self):
        x = [42]
        assert (x < x) is False
        assert (x <= x) is True
        assert (x == x) is True
        assert (x != x) is False
        assert (x > x) is False
        assert (x >= x) is True
        y = [42, 42]
        assert (x < y) is True
        assert (x <= y) is True
        assert (x == y) is False
        assert (x != y) is True
        assert (x > y) is False
        assert (x >= y) is False


def _ListTest__test_coverage():
    t = ListTest()
    t.test_coverage()
    print('ok ListTest.test_coverage')


_ListTest__test_coverage()
