# Adapted from CPython 3.13.16 Lib/test/test_builtin.py, class BuiltinTest: test_max, test_min,
# test_sum and test_sum_accuracy, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b, assertRaises a try statement that prints the exception. An empty list display is an
# annotated variable. test_max and test_min draw their data with random.randrange(), seeded
# here so that the data are the same on every run, and keys.__getitem__, which the subset cannot
# bind as a value (issue #247), is a lambda that indexes keys.
# EXCLUDED upstream cases:
# - max(1, 2, 3.0), max(1, 2.0, 3), max(1.0, 2, 3) and the min() ones: a result that is an int
#   or a float by the values (rejected), and sum([0.5, 1]), sum([1, 0.5]): lists of ints and
#   floats (rejected: no int item in a list of floats)
# - default= of max() and min() (not supported), sum(..., start=1000) (start= not supported)
# - sum(range(10), 2**63-5) and the 2**63-3 start: ints are 64-bit (OverflowError)
# - sum([], False): a bool start (rejected, tests/errors/containers/sum_bool_start.py)
# - sum(iter(...)): iter() (not supported); Squares and BadSeq (iteration through __getitem__)
# - sum([[1], [2], [3]], []) and the `empty` list start: sum() of lists (not supported)
# - the TypeErrors of max(), min(), sum(), sum(42), sum of strs, bytes, lists and dicts, and the
#   exec()'d max()/min() calls with bad keywords (compile-time errors here, with messages of
#   their own); max(42) and min(42) are tests/errors/upstream/upstream_builtin_*.py (CPython's messages)
import math
from operator import neg
import random


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def test_max() -> None:
    check("max('123123')", max('123123'), '3')
    check("max(1, 2, 3)", max(1, 2, 3), 3)
    check("max((1, 2, 3, 1, 2, 3))", max((1, 2, 3, 1, 2, 3)), 3)
    check("max([1, 2, 3, 1, 2, 3])", max([1, 2, 3, 1, 2, 3]), 3)

    try:
        max(())
    except ValueError as e:
        print("ValueError:", e)
    else:
        assert False, "expected ValueError"

    check("max((1,), key=neg)", max((1,), key=neg), 1)     # one elem iterable
    check("max((1,2), key=neg)", max((1,2), key=neg), 1)    # two elem iterable
    check("max(1, 2, key=neg)", max(1, 2, key=neg), 1)     # two elems

    check("max((1, 2), key=None)", max((1, 2), key=None), 2)

    random.seed(2024)
    data = [random.randrange(200) for i in range(100)]
    keys: dict[int, int] = {}
    for elem in data:  # dict((elem, random.randrange(50)) for elem in data)
        keys[elem] = random.randrange(50)
    f = lambda elem: keys[elem]  # keys.__getitem__
    check("max(data, key=f)", max(data, key=f),
                     sorted(reversed(data), key=f)[-1])


def test_min() -> None:
    check("min('123123')", min('123123'), '1')
    check("min(1, 2, 3)", min(1, 2, 3), 1)
    check("min((1, 2, 3, 1, 2, 3))", min((1, 2, 3, 1, 2, 3)), 1)
    check("min([1, 2, 3, 1, 2, 3])", min([1, 2, 3, 1, 2, 3]), 1)

    try:
        min(())
    except ValueError as e:
        print("ValueError:", e)
    else:
        assert False, "expected ValueError"

    check("min((1,), key=neg)", min((1,), key=neg), 1)     # one elem iterable
    check("min((1,2), key=neg)", min((1,2), key=neg), 2)    # two elem iterable
    check("min(1, 2, key=neg)", min(1, 2, key=neg), 2)     # two elems

    check("min((1, 2), key=None)", min((1, 2), key=None), 1)

    random.seed(1913)
    data = [random.randrange(200) for i in range(100)]
    keys: dict[int, int] = {}
    for elem in data:  # dict((elem, random.randrange(50)) for elem in data)
        keys[elem] = random.randrange(50)
    f = lambda elem: keys[elem]  # keys.__getitem__
    check("min(data, key=f)", min(data, key=f),
                     sorted(data, key=f)[0])


def test_sum() -> None:
    empty: list[int] = []
    empty_floats: list[float] = []
    check("sum([])", sum(empty), 0)
    check("sum(list(range(2,8)))", sum(list(range(2,8))), 27)

    check("sum(range(10), 1000)", sum(range(10), 1000), 1045)
    check("sum(range(10), 2**31-5)", sum(range(10), 2**31-5), 2**31+40)

    check("sum(i % 2 != 0 for i in range(10))", sum(i % 2 != 0 for i in range(10)), 5)
    check("sum((i % 2 != 0 for i in range(10)), 2**31-3)", sum((i % 2 != 0 for i in range(10)), 2**31-3),
                     2**31+2)

    check("sum(i / 2 for i in range(10))", sum(i / 2 for i in range(10)), 22.5)
    check("sum((i / 2 for i in range(10)), 1000)", sum((i / 2 for i in range(10)), 1000), 1022.5)
    check("sum((i / 2 for i in range(10)), 1000.25)", sum((i / 2 for i in range(10)), 1000.25), 1022.75)
    check("repr(sum([-0.0]))", repr(sum([-0.0])), '0.0')
    check("repr(sum([-0.0], -0.0))", repr(sum([-0.0], -0.0)), '-0.0')
    check("repr(sum([], -0.0))", repr(sum(empty_floats, -0.0)), '-0.0')
    check("isinf(sum([inf, inf]))", math.isinf(sum([float("inf"), float("inf")])), True)
    check("isinf(sum([1e308, 1e308]))", math.isinf(sum([1e308, 1e308])), True)


def test_sum_accuracy() -> None:
    check("sum([0.1] * 10)", sum([0.1] * 10), 1.0)
    check("sum([1.0, 10E100, 1.0, -10E100])", sum([1.0, 10E100, 1.0, -10E100]), 2.0)


test_max()
test_min()
test_sum()
test_sum_accuracy()
