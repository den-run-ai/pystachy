# Adapted from CPython 3.13.16 Lib/test/test_builtin.py, class BuiltinTest: test_all, test_any,
# test_filter and test_map, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b, assertRaises a try statement that prints the exception; an empty list display is an
# annotated variable (`all([])` is all(empty)). test_map's optional import of math's sqrt is at
# module level (in the test function, a closure cannot read it: bug below).
# EXCLUDED upstream cases:
# - TestFailingBool in a list with ints (`all([2, TestFailingBool(), 6])`, the short-circuit
#   cases `all([0, TestFailingBool()])` and `any([1, TestFailingBool()])`) and
#   filter(None, [1, 'hello', [], [3], '', None, 9, 0]): lists of items of several types
# - any([None, None, None]): a list display of only None (rejected: annotate it)
# - Squares, BadSeq and I (iteration through __getitem__ alone), map(int, Squares(10)), Max of
#   Squares, BadSeq's generator __iter__ (rejected)
# - the TypeErrors of all(10), all(), any(10), any(), filter(), map(), map(f, 42) (compile-time
#   errors here, with messages of their own); all([2, 4, 6], []), filter(42, (1, 2)) and
#   filter(badfunc, range(5)) are tests/errors/upstream/upstream_builtin_*.py (CPython's messages)
# - test_filter_pickle, test_map_pickle (pickle), test_filter_dealloc (filter objects as values,
#   gc); test_iter and test_next of the same class: iter() and next() (not supported)
# - test_map's `from math import sqrt` with its fallback def inside the test method: a lambda in
#   a function cannot read a name that the function's import of a builtin module binds
#   (bug: "the lambda reads 'sqrt', which is not assigned yet where it is defined"; #275)
from typing import Iterator

try:
    from math import sqrt
except ImportError:
    def sqrt(x):
        return pow(x, 0.5)


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


class TestFailingIter:
    def __iter__(self) -> Iterator[int]:
        raise RuntimeError


def test_all() -> None:
    empty: list[int] = []
    check("all([2, 4, 6])", all([2, 4, 6]), True)
    check("all([2, None, 6])", all([2, None, 6]), False)
    try:
        all(TestFailingIter())
    except RuntimeError as e:
        print("all(TestFailingIter()):", type(e).__name__)
    else:
        assert False, "expected RuntimeError"
    check("all([])", all(empty), True)                     # Empty iterator
    S = [50, 60]
    check("all(x > 42 for x in S)", all(x > 42 for x in S), True)
    S = [50, 40, 60]
    check("all(x > 42 for x in S)", all(x > 42 for x in S), False)


def test_any() -> None:
    empty: list[int] = []
    check("any([None, 4, None])", any([None, 4, None]), True)
    try:
        any(TestFailingIter())
    except RuntimeError as e:
        print("any(TestFailingIter()):", type(e).__name__)
    else:
        assert False, "expected RuntimeError"
    check("any([])", any(empty), False)                    # Empty iterator
    S = [40, 60, 30]
    check("any(x > 42 for x in S)", any(x > 42 for x in S), True)
    S = [10, 20, 30]
    check("any(x > 42 for x in S)", any(x > 42 for x in S), False)


def test_filter() -> None:
    check("filter(lambda c: 'a' <= c <= 'z', 'Hello World')",
          list(filter(lambda c: 'a' <= c <= 'z', 'Hello World')), list('elloorld'))
    check("filter(lambda x: x > 0, [1, -3, 9, 0, 2])",
          list(filter(lambda x: x > 0, [1, -3, 9, 0, 2])), [1, 9, 2])

    # test bltinmodule.c::filtertuple()
    check("filter(None, (1, 2))", list(filter(None, (1, 2))), [1, 2])
    check("filter(lambda x: x>=3, (1, 2, 3, 4))", list(filter(lambda x: x>=3, (1, 2, 3, 4))), [3, 4])


def test_map() -> None:
    check("map(lambda x: x*x, range(1,4))",
        list(map(lambda x: x*x, range(1,4))),
        [1, 4, 9]
    )
    check("map(lambda x: list(map(sqrt, x)), [[16, 4], [81, 9]])",
        list(map(lambda x: list(map(sqrt, x)), [[16, 4], [81, 9]])),
        [[4.0, 2.0], [9.0, 3.0]]
    )
    check("map(lambda x, y: x+y, [1,3,2], [9,1,4])",
        list(map(lambda x, y: x+y, [1,3,2], [9,1,4])),
        [10, 4, 6]
    )

    def plus(*v):
        accu = 0
        for i in v: accu = accu + i
        return accu
    check("map(plus, [1, 3, 7])",
        list(map(plus, [1, 3, 7])),
        [1, 3, 7]
    )
    check("map(plus, [1, 3, 7], [4, 9, 2])",
        list(map(plus, [1, 3, 7], [4, 9, 2])),
        [1+4, 3+9, 7+2]
    )
    check("map(plus, [1, 3, 7], [4, 9, 2], [1, 1, 0])",
        list(map(plus, [1, 3, 7], [4, 9, 2], [1, 1, 0])),
        [1+4+1, 3+9+1, 7+2+0]
    )
    def badfunc(x):
        raise RuntimeError
    try:
        list(map(badfunc, range(5)))
    except RuntimeError as e:
        print("map(badfunc, range(5)):", type(e).__name__)
    else:
        assert False, "expected RuntimeError"


test_all()
test_any()
test_filter()
test_map()
