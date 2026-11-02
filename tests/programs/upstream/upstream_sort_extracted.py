# CPython 3.13.16 Lib/test/test_sort.py (commit cbc944f4bc59639a444dd971c737788ba2283a91,
# SHA-256 dd8cee99c70a21f6a220f64bf40e2ab9099c6df79f15859577cea4c4377fb382),
# made mechanically by tools/cpython_test_methods.py: unittest scaffolding becomes plain
# statements that keep each test's inputs and assertions (tests/upstream/core-sweep.md).
# Tests: TestBase.test_small_stability, TestDecorateSortUndecorate.test_decorated,
#   TestDecorateSortUndecorate.test_key_with_exception,
#   TestDecorateSortUndecorate.test_key_with_mutation, TestDecorateSortUndecorate.test_reverse,
#   TestDecorateSortUndecorate.test_reverse_stability, TestDecorateSortUndecorate.test_stability,
#   TestOptimizedCompares.test_none_in_tuples.
import random
from functools import cmp_to_key

class TestBase:

    def test_small_stability(self):
        from itertools import product
        from operator import itemgetter
        NELTS = 3
        MAXSIZE = 9
        pick0 = itemgetter(0)
        for length in range(MAXSIZE + 1):
            for t in product(range(NELTS), repeat=length):
                xs = list(zip(t, range(length)))
                forced = sorted(xs)
                native = sorted(xs, key=pick0)
                assert forced == native

class TestDecorateSortUndecorate:

    def test_decorated(self):
        data = 'The quick Brown fox Jumped over The lazy Dog'.split()
        copy = data[:]
        random.shuffle(data)
        data.sort(key=str.lower)

        def my_cmp(x, y):
            xlower, ylower = (x.lower(), y.lower())
            return (xlower > ylower) - (xlower < ylower)
        copy.sort(key=cmp_to_key(my_cmp))

    def test_stability(self):
        data = [(random.randrange(100), i) for i in range(200)]
        copy = data[:]
        data.sort(key=lambda t: t[0])
        copy.sort()
        assert data == copy

    def test_key_with_exception(self):
        data = list(range(-2, 2))
        dup = data[:]
        try:
            data.sort(key=lambda x: 1 / x)
        except ZeroDivisionError:
            pass
        else:
            raise AssertionError('did not raise')
        assert data == dup

    def test_key_with_mutation(self):
        data = list(range(10))

        def k(x):
            del data[:]
            data[:] = range(20)
            return x
        try:
            data.sort(key=k)
        except ValueError:
            pass
        else:
            raise AssertionError('did not raise')

    def test_reverse(self):
        data = list(range(100))
        random.shuffle(data)
        data.sort(reverse=True)
        assert data == list(range(99, -1, -1))

    def test_reverse_stability(self):
        data = [(random.randrange(100), i) for i in range(200)]
        copy1 = data[:]
        copy2 = data[:]

        def my_cmp(x, y):
            x0, y0 = (x[0], y[0])
            return (x0 > y0) - (x0 < y0)

        def my_cmp_reversed(x, y):
            x0, y0 = (x[0], y[0])
            return (y0 > x0) - (y0 < x0)
        data.sort(key=cmp_to_key(my_cmp), reverse=True)
        copy1.sort(key=cmp_to_key(my_cmp_reversed))
        assert data == copy1
        copy2.sort(key=lambda x: x[0], reverse=True)
        assert data == copy2

class TestOptimizedCompares:

    def test_none_in_tuples(self):
        expected = [(None, 1), (None, 2)]
        actual = sorted([(None, 2), (None, 1)])
        assert actual == expected


def _TestBase__test_small_stability():
    t = TestBase()
    t.test_small_stability()
    print('ok TestBase.test_small_stability')


def _TestDecorateSortUndecorate__test_decorated():
    t = TestDecorateSortUndecorate()
    t.test_decorated()
    print('ok TestDecorateSortUndecorate.test_decorated')


def _TestDecorateSortUndecorate__test_key_with_exception():
    t = TestDecorateSortUndecorate()
    t.test_key_with_exception()
    print('ok TestDecorateSortUndecorate.test_key_with_exception')


def _TestDecorateSortUndecorate__test_key_with_mutation():
    t = TestDecorateSortUndecorate()
    t.test_key_with_mutation()
    print('ok TestDecorateSortUndecorate.test_key_with_mutation')


def _TestDecorateSortUndecorate__test_reverse():
    t = TestDecorateSortUndecorate()
    t.test_reverse()
    print('ok TestDecorateSortUndecorate.test_reverse')


def _TestDecorateSortUndecorate__test_reverse_stability():
    t = TestDecorateSortUndecorate()
    t.test_reverse_stability()
    print('ok TestDecorateSortUndecorate.test_reverse_stability')


def _TestDecorateSortUndecorate__test_stability():
    t = TestDecorateSortUndecorate()
    t.test_stability()
    print('ok TestDecorateSortUndecorate.test_stability')


def _TestOptimizedCompares__test_none_in_tuples():
    t = TestOptimizedCompares()
    t.test_none_in_tuples()
    print('ok TestOptimizedCompares.test_none_in_tuples')


_TestBase__test_small_stability()
_TestDecorateSortUndecorate__test_decorated()
_TestDecorateSortUndecorate__test_key_with_exception()
_TestDecorateSortUndecorate__test_key_with_mutation()
_TestDecorateSortUndecorate__test_reverse()
_TestDecorateSortUndecorate__test_reverse_stability()
_TestDecorateSortUndecorate__test_stability()
_TestOptimizedCompares__test_none_in_tuples()
