# Supported assertions adapted from CPython 3.13.16 TestReduce.test_reduce
# and test_iterator_usage, Lib/test/test_functools.py at commit
# cbc944f4bc59639a444dd971c737788ba2283a91. SHA-256:
# ec00d729ddde2de6412237b3f8f4196bc0777ce9d0bf99fd69071fb44ce72fd5.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt.
# Both upstream methods are PARTIAL: custom __getitem__/__iter__ classes,
# noncallable unused callbacks, untyped empty tuples and arbitrary objects are
# excluded. range arguments become list(range(...)) with the same values, as
# range is not a first-class subset value. Empty lists receive element types.
from functools import reduce
from operator import add, mul, sub
from io import StringIO


assert reduce(add, ['a', 'b', 'c'], '') == 'abc'
empty_words: list[str] = []
assert reduce(add, [['a', 'c'], empty_words, ['d', 'w']], empty_words) == ['a', 'c', 'd', 'w']
assert reduce(mul, list(range(2, 8)), 1) == 5040
assert reduce(mul, list(range(2, 21)), 1) == 2432902008176640000
empty_ints: list[int] = []
assert reduce(add, empty_ints, 42) == 42
for sequence in [empty_ints, [42]]:
    if sequence:
        assert reduce(add, sequence) == 42
    else:
        try:
            reduce(add, sequence)
        except TypeError as error:
            assert str(error) == 'reduce() of empty iterable with no initial value'
        else:
            raise AssertionError('empty reduction did not fail')
try:
    reduce(add, '')
except TypeError as error:
    assert str(error) == 'reduce() of empty iterable with no initial value'
else:
    raise AssertionError('empty text reduction did not fail')
d = {'one': 1, 'two': 2, 'three': 3}
assert reduce(add, d) == ''.join(d.keys())

# Additional subset regressions: order, one-pass input, initial type different
# from item type, explicit None, closure callbacks, list iteration and exceptions.
assert reduce(sub, [10, 3, 2]) == 5
assert reduce(sub, [10, 3, 2], 100) == 85
assert reduce(add, (1, 2, 3)) == 6
assert reduce(add, 'abc') == 'abc'
stream = StringIO('first\nsecond\nthird\n')
assert reduce(add, stream) == 'first\nsecond\nthird\n'
assert stream.read() == ''
stream_initial = StringIO('a\nb\n')
assert reduce(add, stream_initial, 'prefix\n') == 'prefix\na\nb\n'


def add_length(acc: int, item: str) -> int:
    return acc + len(item)


assert reduce(add_length, ['a', 'bc', 'def'], 10) == 16


def keep_none(acc: int | None, item: int) -> int | None:
    return acc


assert reduce(keep_none, empty_ints, None) is None
assert reduce(keep_none, [1, 2, 3], None) is None
assert reduce(lambda acc, item: acc * 10 + item, [1, 2, 3], 0) == 123

appended = [1, 2]


def append_next(acc: int, item: int) -> int:
    if item == 2:
        appended.append(3)
    return acc + item


assert reduce(append_next, appended) == 6
deleted = [1, 2, 3, 4]


def delete_first(acc: int, item: int) -> int:
    if item == 2:
        del deleted[0]
    return acc + item


assert reduce(delete_first, deleted) == 7
seen: list[int] = []


def fail_callback(acc: int, item: int) -> int:
    seen.append(item)
    if item == 3:
        raise ValueError('callback failed')
    return acc + item


try:
    reduce(fail_callback, [1, 2, 3, 4])
except ValueError as error:
    assert str(error) == 'callback failed'
else:
    raise AssertionError('callback failure was swallowed')
assert seen == [2, 3]
try:
    reduce(add, [1], 2, 3)
except TypeError as error:
    assert str(error) == 'reduce expected at most 3 arguments, got 4'
else:
    raise AssertionError('extra initial value accepted')
print('reduce: supported upstream assertions and subset edge cases')
