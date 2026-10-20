# Adapted from CPython 3.13.16 Lib/test/test_enumerate.py: EnumerateTestCase.test_basicfunction
# with the data of EnumerateTestCase, TestEmpty, TestBig and TestStart, and
# TestReversed.test_simple, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test class's (seq, res) pair is checked by test_basicfunction's list() assertion.
# TestBig's seq, range(10,20000,2), is the list of its items (a range is not a value here, and
# enumerate(range(...)) as list()'s argument is rejected: bug below), and its res zips the list
# of range(20000). test_simple's loop over its data is written out.
# EXCLUDED upstream cases:
# - test_basicfunction's type(...) and iter(e) checks (enumerate objects are not values, nor
#   iter()), test_pickle and every check_pickle (pickle), test_getitemseqn (G iterates through
#   __getitem__ alone), test_iteratorseqn, test_noniterable, test_illformediterable,
#   test_exception_propagation (I, X, E and N: iterator classes), test_iteratorgenerator and
#   test_kwargs (Ig: a generator __iter__; enumerate(iterable=...) is rejected, worded
#   "unsupported expression 'kw'"), test_tuple_reuse and test_enumerate_result_gc (id(), gc)
# - test_argumentcheck's and TestReversed.test_args' TypeErrors: compile-time errors here, with
#   messages of their own; reversed([], a=1)
# - SubclassTestCase (MyEnum derives from enumerate), TestLongStart (sys.maxsize + 1: ints are
#   64-bit)
# - test_simple's tuple(enumerate('abc')) (tuple() of an iterable) and A() (reversed() of an
#   object); test_range_optimization, test_len (reversed objects as values, length_hint),
#   test_gc, test_bug1229429, test_objmethods (__reversed__, objects with __getitem__)
# - list(enumerate(range(10, 20000, 2))): range() nested in enumerate() as list()'s argument is
#   rejected ("make it a list first"), which docs/language.md lists for for loops only
#   (bug #276; the same as zip()'s in tests/programs/upstream/upstream_iter_builtins.py)


def check(label: str, got, expected) -> None:
    print(label, repr(got) if len(repr(got)) < 100 else repr(got)[:60] + "...")
    assert got == expected, label


def test_basicfunction(name: str, seq, res) -> None:
    check(name + ": list(enumerate(seq))", list(enumerate(seq)), res)


def test_start_basicfunction(name: str, seq, res) -> None:
    # TestStart.enum(iterable, start=11) is enumerate(iterable, start=start)
    check(name + ": list(enumerate(seq, start=11))", list(enumerate(seq, start=11)), res)


def test_simple() -> None:
    check("'abc'", list('abc')[::-1], list(reversed('abc')))
    check("range(5)", list(range(5))[::-1], list(reversed(range(5))))
    check("range(1,17,5)", list(range(1,17,5))[::-1], list(reversed(range(1,17,5))))
    fromkeys: dict[str, int | None] = dict.fromkeys('abcde')
    check("dict.fromkeys('abcde')", list(fromkeys)[::-1], list(reversed(fromkeys)))


# EnumerateTestCase
test_basicfunction("EnumerateTestCase", 'abc', [(0,'a'), (1,'b'), (2,'c')])
# TestEmpty
no_pairs: list[tuple[int, str]] = []
test_basicfunction("TestEmpty", '', no_pairs)
# TestBig
big_seq = list(range(10,20000,2))
test_basicfunction("TestBig", big_seq, list(zip(list(range(20000)), big_seq)))
# TestStart
test_start_basicfunction("TestStart", 'abc', [(11, 'a'), (12, 'b'), (13, 'c')])
# TestReversed
test_simple()
