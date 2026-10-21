# Adapted from CPython 3.13.16 Lib/test/test_builtin.py: BuiltinTest.test_zip and
# test_zip_bad_iterable, and class TestSorted: test_basic, test_bad_arguments and
# test_inputtypes, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b, assertRaises a try statement; zip() is list()'s argument (a zip object is no value).
# A variable has one type here, so test_zip's b is b2 and b3 where upstream rebinds it to a list
# and a longer tuple. test_basic shuffles with random.shuffle(), seeded here so that the
# shuffles are the same on every run.
# test_inputtypes loops over the types to call; here each call is written out, and
# dict.fromkeys(s) gets the annotation the subset needs.
# EXCLUDED upstream cases:
# - test_zip: class I and SequenceWithoutALength (iteration through __getitem__ alone), BadSeq;
#   zip() and zip(*[]) (zip() without arguments: not supported); the TypeErrors of zip(None) and
#   zip(a, G()) (compile-time errors here); zip(a, TestFailingIter()) is kept, as list()'s argument
# - test_zip_pickle*, test_zip_strict* (zip(strict=...) is rejected), test_zip_result_gc (gc)
# - test_bad_arguments' TypeErrors (sorted(iterable=[]), sorted([], None)) and test_baddecorator
#   (sorted(data, None, lambda x,y: 0)): compile-time errors here, worded "sorted() takes exactly
#   one argument (N given)" where CPython says "sorted expected 1 argument, got N" (bug: message
#   wording; #277), and "keyword argument 'iterable' of sorted() is not supported"
# - test_inputtypes' tuple(s) (tuple() of an iterable: not supported)
import random
from typing import Iterator


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


class TestFailingIter:
    def __iter__(self) -> Iterator[int]:
        raise RuntimeError


def test_zip() -> None:
    a = (1, 2, 3)
    b = (4, 5, 6)
    t = [(1, 4), (2, 5), (3, 6)]
    check("zip(a, b)", list(zip(a, b)), t)
    b2 = [4, 5, 6]
    check("zip(a, [4, 5, 6])", list(zip(a, b2)), t)
    b3 = (4, 5, 6, 7)
    check("zip(a, (4, 5, 6, 7))", list(zip(a, b3)), t)
    try:
        list(zip(a, TestFailingIter()))
    except RuntimeError as e:
        print("zip(a, TestFailingIter()):", type(e).__name__)
    else:
        assert False, "expected RuntimeError"


exception = TypeError()


class BadIterable:
    def __iter__(self) -> Iterator[int]:
        raise exception


def test_zip_bad_iterable() -> None:
    try:
        list(zip(BadIterable()))
    except TypeError as cm_exception:
        check("cm.exception is exception", cm_exception is exception, True)
    else:
        assert False, "expected TypeError"


def test_basic() -> None:
    random.seed(7)
    data = list(range(100))
    copy = data[:]
    random.shuffle(copy)
    check("data == sorted(copy)", data == sorted(copy), True)
    check("data != copy", data != copy, True)

    data.reverse()
    random.shuffle(copy)
    check("data == sorted(copy, key=lambda x: -x)", data == sorted(copy, key=lambda x: -x), True)
    check("data != copy", data != copy, True)
    random.shuffle(copy)
    check("data == sorted(copy, reverse=True)", data == sorted(copy, reverse=True), True)
    check("data != copy", data != copy, True)


def test_bad_arguments() -> None:
    # Issue #29327: The first argument is positional-only.
    empty: list[int] = []
    print("sorted([])", sorted(empty))
    # Other arguments are keyword-only
    print("sorted([], key=None)", sorted(empty, key=None))


def test_inputtypes() -> None:
    s = 'abracadabra'
    # types = [list, tuple, str]
    check("sorted(list(s))", sorted(s) == sorted(list(s)), True)
    check("sorted(str(s))", sorted(s) == sorted(str(s)), True)

    s = ''.join(set(s))  # unique letters only
    # types = [str, set, frozenset, list, tuple, dict.fromkeys]
    check("sorted(str(s))", sorted(s) == sorted(str(s)), True)
    check("sorted(set(s))", sorted(s) == sorted(set(s)), True)
    check("sorted(frozenset(s))", sorted(s) == sorted(frozenset(s)), True)
    check("sorted(list(s))", sorted(s) == sorted(list(s)), True)
    fromkeys: dict[str, int | None] = dict.fromkeys(s)
    check("sorted(dict.fromkeys(s))", sorted(s) == sorted(fromkeys), True)


test_zip()
test_zip_bad_iterable()
test_basic()
test_bad_arguments()
test_inputtypes()
