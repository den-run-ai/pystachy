# Adapted from CPython 3.13.16 Lib/test/test_iter.py, class TestCase:
# test_nested_comprehensions_iter, test_nested_comprehensions_for and test_builtin_tuple; and
# Lib/test/test_builtin.py, BuiltinTest.test_iter; commit
# cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# (tests/programs/upstream/upstream_iter_classes.py and tests/programs/upstream/upstream_iter_builtins.py adopt test_iter.py's other
# tests.) Each test method becomes a function of the same name; assertEqual(a, b) is eq(a, b),
# which prints a and asserts a == b; assertRaises(StopIteration, next, it) is a try statement.
# `seq = range(3)` is list(range(3)) (a range as a value is not supported). test_iter's loop over
# a tuple, a list and a str (a list whose items differ) is written out for each.
# EXCLUDED upstream cases:
# - test_builtin_tuple's tuple() of a dict (rejected: "tuple() of dict[str,int] is not
#   supported: use a list, string or tuple") and of a file (rejected: "tuple() of file is not
#   supported"), its SequenceClass parts and TypeErrors; tuple([]) is of an annotated empty list
# - test_writelines: writelines() of a tuple, a dict or an object with __iter__ (rejected:
#   "expected list[str], got tuple[str,str]", "expected list[str], got Whatever")
# - test_builtin.py test_iter's TypeErrors (iter(), iter(42, 42)): compile-time errors here
TRIPLETS = [(0, 0, 0), (0, 0, 1), (0, 0, 2),
            (0, 1, 0), (0, 1, 1), (0, 1, 2),
            (0, 2, 0), (0, 2, 1), (0, 2, 2),

            (1, 0, 0), (1, 0, 1), (1, 0, 2),
            (1, 1, 0), (1, 1, 1), (1, 1, 2),
            (1, 2, 0), (1, 2, 1), (1, 2, 2),

            (2, 0, 0), (2, 0, 1), (2, 0, 2),
            (2, 1, 0), (2, 1, 1), (2, 1, 2),
            (2, 2, 0), (2, 2, 1), (2, 2, 2)]


def eq(got, expected) -> None:
    print(repr(got))
    assert got == expected, (got, expected)


def test_nested_comprehensions_iter() -> None:
    seq = list(range(3))
    res = [(i, j, k)
           for i in iter(seq) for j in iter(seq) for k in iter(seq)]
    eq(res, TRIPLETS)


def test_nested_comprehensions_for() -> None:
    seq = list(range(3))
    res = [(i, j, k) for i in seq for j in seq for k in seq]
    eq(res, TRIPLETS)


def test_builtin_tuple() -> None:
    e: list[int] = []
    eq(tuple(e), ())
    eq(tuple(()), ())
    eq(tuple("abc"), ("a", "b", "c"))


def test_iter() -> None:
    i = iter(("1", "2"))
    eq(next(i), '1')
    eq(next(i), '2')
    try:
        next(i)
    except StopIteration:
        print("StopIteration")
    j = iter(["1", "2"])
    eq(next(j), '1')
    eq(next(j), '2')
    try:
        next(j)
    except StopIteration:
        print("StopIteration")
    k = iter("12")
    eq(next(k), '1')
    eq(next(k), '2')
    try:
        next(k)
    except StopIteration:
        print("StopIteration")


test_nested_comprehensions_iter()
test_nested_comprehensions_for()
test_builtin_tuple()
test_iter()
