# CPython 3.13.16 Lib/test/test_range.py (commit cbc944f4bc59639a444dd971c737788ba2283a91,
# SHA-256 603d1ca7b740d2e4702b3ff42202de4c261b41d51078227526c7447caa3bf80e),
# made mechanically by tools/cpython_test_methods.py: unittest scaffolding becomes plain
# statements that keep each test's inputs and assertions (tests/upstream/core-sweep.md).
# Tests: RangeTest.test_empty, RangeTest.test_repr, RangeTest.test_strided_limits.
import itertools

class RangeTest:

    def assert_iterators_equal(self, xs, ys, test_id, limit=None):
        if limit is not None:
            xs = itertools.islice(xs, limit)
            ys = itertools.islice(ys, limit)
        sentinel = object()
        pairs = itertools.zip_longest(xs, ys, fillvalue=sentinel)
        for i, (x, y) in enumerate(pairs):
            if x == y:
                continue
            elif x == sentinel:
                raise AssertionError('{}: iterator ended unexpectedly at position {}; expected {}'.format(test_id, i, y))
            elif y == sentinel:
                raise AssertionError('{}: unexpected excess element {} at position {}'.format(test_id, x, i))
            else:
                raise AssertionError('{}: wrong element at position {}; expected {}, got {}'.format(test_id, i, y, x))

    def test_repr(self):
        assert repr(range(1)) == 'range(0, 1)'
        assert repr(range(1, 2)) == 'range(1, 2)'
        assert repr(range(1, 2, 3)) == 'range(1, 2, 3)'

    def test_strided_limits(self):
        r = range(0, 101, 2)
        assert 0 in r
        assert 1 not in r
        assert 2 in r
        assert 99 not in r
        assert 100 in r
        assert 101 not in r
        r = range(0, -20, -1)
        assert 0 in r
        assert -1 in r
        assert -19 in r
        assert -20 not in r
        r = range(0, -20, -2)
        assert -18 in r
        assert -19 not in r
        assert -20 not in r

    def test_empty(self):
        r = range(0)
        assert 0 not in r
        assert 1 not in r
        r = range(0, -10)
        assert 0 not in r
        assert -1 not in r
        assert 1 not in r

    def assert_attrs(self, rangeobj, start, stop, step):
        assert rangeobj.start == start
        assert rangeobj.stop == stop
        assert rangeobj.step == step
        assert type(rangeobj.start) is int
        assert type(rangeobj.stop) is int
        assert type(rangeobj.step) is int
        try:
            rangeobj.start = 0
        except AttributeError:
            pass
        else:
            raise AssertionError('did not raise')
        try:
            rangeobj.stop = 10
        except AttributeError:
            pass
        else:
            raise AssertionError('did not raise')
        try:
            rangeobj.step = 1
        except AttributeError:
            pass
        else:
            raise AssertionError('did not raise')
        try:
            del rangeobj.start
        except AttributeError:
            pass
        else:
            raise AssertionError('did not raise')
        try:
            del rangeobj.stop
        except AttributeError:
            pass
        else:
            raise AssertionError('did not raise')
        try:
            del rangeobj.step
        except AttributeError:
            pass
        else:
            raise AssertionError('did not raise')


def _RangeTest__test_empty():
    t = RangeTest()
    t.test_empty()
    print('ok RangeTest.test_empty')


def _RangeTest__test_repr():
    t = RangeTest()
    t.test_repr()
    print('ok RangeTest.test_repr')


def _RangeTest__test_strided_limits():
    t = RangeTest()
    t.test_strided_limits()
    print('ok RangeTest.test_strided_limits')


_RangeTest__test_empty()
_RangeTest__test_repr()
_RangeTest__test_strided_limits()
