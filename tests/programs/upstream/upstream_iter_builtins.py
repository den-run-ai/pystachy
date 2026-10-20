# Adapted from CPython 3.13.16 Lib/test/test_iter.py, class TestCase: test_iter_dict,
# test_iter_file, test_builtin_list, test_builtin_filter, test_builtin_max_min,
# test_builtin_map, test_builtin_zip, test_countOf, test_indexOf, test_unpack_iter and
# test_extending_list_with_iterator_does_not_segfault, commit
# cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b, assertRaises a try statement. check_for_loop() leaves out its pickle round trip.
# TESTFN is a file in a tempfile.mkdtemp() directory; files have no seek() here, so where
# upstream rewinds with f.seek(0, 0), the file is opened again. test_indexOf's `fiter = iter(f)`
# is f itself (a file is its own iterator, as iter(f) returns it). An empty display that
# nothing types is an annotated variable. test_extending_list_with_iterator_does_not_segfault's
# gen() is a generator function, which the subset does not have: a generator expression gives
# the same items, also without a length hint.
# EXCLUDED upstream cases (Lib/test/test_iter.py has no other test this subset can run):
# - the tests of iter(), next() and iterator classes (an __iter__ that returns an object with
#   __next__: BasicIterClass, IteratingSequenceClass, IteratorProxyClass, IntsFrom, OhPhooey),
#   which tests/programs/upstream/upstream_iter_classes.py adapts: test_iter_basic, test_iter_idempotency,
#   test_iter_for_loop, test_iter_independence, test_iter_class_*, test_iter_big_range,
#   test_iter_empty, test_iter_tuple, test_iter_range, test_iter_string,
#   test_unicode_join_endcase, test_in_and_not_in, test_sinkstate_*, and the iterator parts of
#   the tests below
# - iter(callable, sentinel), sequence classes (iteration through __getitem__ alone:
#   SequenceClass, NoGuessLen5, ...), generators, pickle, __setstate__ and __reduce__:
#   test_seq_class_*, test_mutating_seq_class_*, test_reduce_mutating_builtins_iter,
#   test_new_style_iter_class, test_iter_callable, test_iter_function*, test_exception_*,
#   test_stop_sequence, test_3720, test_iter_overflow, test_iter_neg_setstate,
#   test_free_after_iterating, test_error_iter, test_exception_locations,
#   test_ref_counting_behavior (also __new__, __del__)
# - test_nested_comprehensions_* and test_builtin_tuple's tuple() of a list, a tuple and a str:
#   tests/programs/upstream/upstream_iter_comprehensions.py adopts them; test_builtin_tuple's tuple() of a dict
#   and of a file (not supported)
# - test_builtin_list's, test_builtin_filter's and test_builtin_zip's TypeErrors (list(42),
#   filter(None, 42), zip(None), ...): compile-time errors here; their SequenceClass parts
# - test_builtin_map's `expected`, which upstream computes and never checks; test_builtin_zip's
#   list(zip(range(5))) (rejected: range() nested in zip() as list()'s argument, which
#   docs/language.md lists only for for loops: bug #276)
# - test_countOf's and test_in_and_not_in's dicts with a complex key (1j: 2j)
# - test_writelines: writelines() of a tuple, a dict and an object with __iter__ (writelines()
#   takes a list[str] here: rejected at compile time)
# - test_unpack_iter: `a, b, c = len`, and `a, b, c = f` (unpacking a file: rejected at
#   compile time)
import os
import tempfile
from operator import countOf, indexOf

TESTDIR = tempfile.mkdtemp()
TESTFN = os.path.join(TESTDIR, "upstream_iter_builtins.txt")


def unlink(path: str) -> None:
    os.remove(path)


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


# Helper to check that a for loop generates a given sequence
def check_for_loop(label: str, expr, seq) -> None:
    res = []
    for val in expr:
        res.append(val)
    check(label, res, seq)


# Test a directory
def test_iter_dict() -> None:
    dict: dict[int, int | None] = {}
    for i in range(10):
        dict[i] = None
    check_for_loop("for val in dict", dict, list(dict.keys()))


# Test a file
def test_iter_file() -> None:
    f = open(TESTFN, "w", encoding="utf-8")
    try:
        for i in range(5):
            f.write("%d\n" % i)
    finally:
        f.close()
    f = open(TESTFN, "r", encoding="utf-8")
    try:
        check_for_loop("for val in f", f, ["0\n", "1\n", "2\n", "3\n", "4\n"])
        no_lines: list[str] = []
        check_for_loop("for val in f (exhausted)", f, no_lines)
    finally:
        f.close()
        try:
            unlink(TESTFN)
        except OSError:
            pass


# Test list()'s use of iterators.
def test_builtin_list() -> None:
    from_empty_tuple: list[int] = list(())
    no_ints: list[int] = []
    check("list(())", from_empty_tuple, no_ints)

    d = {"one": 1, "two": 2, "three": 3}
    check("list(d)", list(d), list(d.keys()))

    f = open(TESTFN, "w", encoding="utf-8")
    try:
        for i in range(5):
            f.write("%d\n" % i)
    finally:
        f.close()
    f = open(TESTFN, "r", encoding="utf-8")
    try:
        check("list(f)", list(f), ["0\n", "1\n", "2\n", "3\n", "4\n"])
        f.close()
        f = open(TESTFN, "r", encoding="utf-8")  # f.seek(0, 0)
        check("list(f)", list(f),
                         ["0\n", "1\n", "2\n", "3\n", "4\n"])
    finally:
        f.close()
        try:
            unlink(TESTFN)
        except OSError:
            pass


# Test filter()'s use of iterators.
def test_builtin_filter() -> None:
    nothing: list[int] = list(filter(None, ()))
    no_ints: list[int] = []
    check("list(filter(None, ()))", nothing, no_ints)
    check("list(filter(None, 'abc'))", list(filter(None, "abc")), ["a", "b", "c"])

    d = {"one": 1, "two": 2, "three": 3}
    check("list(filter(None, d))", list(filter(None, d)), list(d.keys()))


# Test max() and min()'s use of iterators.
def test_builtin_max_min() -> None:
    check("max(8, -1)", max(8, -1), 8)
    check("min(8, -1)", min(8, -1), -1)

    d = {"one": 1, "two": 2, "three": 3}
    check("max(d)", max(d), "two")
    check("min(d)", min(d), "one")
    check("max(d.values())", max(d.values()), 3)

    f = open(TESTFN, "w", encoding="utf-8")
    try:
        f.write("medium line\n")
        f.write("xtra large line\n")
        f.write("itty-bitty line\n")
    finally:
        f.close()
    f = open(TESTFN, "r", encoding="utf-8")
    try:
        check("min(f)", min(f), "itty-bitty line\n")
        f.close()
        f = open(TESTFN, "r", encoding="utf-8")  # f.seek(0, 0)
        check("max(f)", max(f), "xtra large line\n")
    finally:
        f.close()
        try:
            unlink(TESTFN)
        except OSError:
            pass


# Test map()'s use of iterators.
def test_builtin_map() -> None:
    d = {"one": 1, "two": 2, "three": 3}
    check("list(map(lambda k, d=d: (k, d[k]), d))", list(map(lambda k, d=d: (k, d[k]), d)),
                     list(d.items()))

    f = open(TESTFN, "w", encoding="utf-8")
    try:
        for i in range(10):
            f.write("xy" * i + "\n") # line i has len 2*i+1
    finally:
        f.close()
    f = open(TESTFN, "r", encoding="utf-8")
    try:
        check("list(map(len, f))", list(map(len, f)), list(range(1, 21, 2)))
    finally:
        f.close()
        try:
            unlink(TESTFN)
        except OSError:
            pass


# Test zip()'s use of iterators.
def test_builtin_zip() -> None:
    d = {"one": 1, "two": 2, "three": 3}
    check("list(d.items())", list(d.items()), list(zip(d, d.values())))


# Test iterators with operator.countOf (PySequence_Count).
def test_countOf() -> None:
    check("countOf([1,2,2,3,2,5], 2)", countOf([1,2,2,3,2,5], 2), 3)
    check("countOf((1,2,2,3,2,5), 2)", countOf((1,2,2,3,2,5), 2), 3)
    check("countOf('122325', '2')", countOf("122325", "2"), 3)
    check("countOf('122325', '6')", countOf("122325", "6"), 0)

    f = open(TESTFN, "w", encoding="utf-8")
    try:
        f.write("a\n" "b\n" "c\n" "b\n")
    finally:
        f.close()
    for letter, count in ("a", 1), ("b", 2), ("c", 1), ("d", 0):
        f = open(TESTFN, "r", encoding="utf-8")  # f.seek(0, 0)
        try:
            check("countOf(f, %r)" % (letter + "\n"), countOf(f, letter + "\n"), count)
        finally:
            f.close()
    try:
        unlink(TESTFN)
    except OSError:
        pass


# Test iterators with operator.indexOf (PySequence_Index).
def test_indexOf() -> None:
    check("indexOf([1,2,2,3,2,5], 1)", indexOf([1,2,2,3,2,5], 1), 0)
    check("indexOf((1,2,2,3,2,5), 2)", indexOf((1,2,2,3,2,5), 2), 1)
    check("indexOf((1,2,2,3,2,5), 3)", indexOf((1,2,2,3,2,5), 3), 3)
    check("indexOf((1,2,2,3,2,5), 5)", indexOf((1,2,2,3,2,5), 5), 5)
    for missing in 0, 6:
        try:
            indexOf((1,2,2,3,2,5), missing)
        except ValueError as e:
            print("indexOf((1,2,2,3,2,5), %d): ValueError: %s" % (missing, e))
        else:
            assert False, "expected ValueError"

    check("indexOf('122325', '2')", indexOf("122325", "2"), 1)
    check("indexOf('122325', '5')", indexOf("122325", "5"), 5)
    try:
        indexOf("122325", "6")
    except ValueError as e:
        print("indexOf('122325', '6'): ValueError:", e)
    else:
        assert False, "expected ValueError"

    f = open(TESTFN, "w", encoding="utf-8")
    try:
        f.write("a\n" "b\n" "c\n" "d\n" "e\n")
    finally:
        f.close()
    f = open(TESTFN, "r", encoding="utf-8")
    try:
        fiter = f  # iter(f)
        check("indexOf(fiter, 'b\\n')", indexOf(fiter, "b\n"), 1)
        check("indexOf(fiter, 'd\\n')", indexOf(fiter, "d\n"), 1)
        check("indexOf(fiter, 'e\\n')", indexOf(fiter, "e\n"), 0)
        try:
            indexOf(fiter, "a\n")
        except ValueError as e:
            print("indexOf(fiter, 'a\\n'): ValueError:", e)
        else:
            assert False, "expected ValueError"
    finally:
        f.close()
        try:
            unlink(TESTFN)
        except OSError:
            pass


# Test iterators on RHS of unpacking assignments.
def test_unpack_iter() -> None:
    a, b = 1, 2
    check("(a, b)", (a, b), (1, 2))

    a, b, c = {1: 42, 2: 42, 3: 42}.values()
    check("(a, b, c)", (a, b, c), (42, 42, 42))


def test_extending_list_with_iterator_does_not_segfault() -> None:
    # The code to extend a list with an iterator has a fair
    # amount of nontrivial logic in terms of guessing how
    # much memory to allocate in advance, "stealing" refs,
    # and then shrinking at the end.  This is a basic smoke
    # test for that scenario.
    lst = [0] * 500
    for i in range(240):
        lst.pop(0)
    lst.extend(i for i in range(500))  # lst.extend(gen())
    check("len(lst)", len(lst), 760)


test_iter_dict()
test_iter_file()
test_builtin_list()
test_builtin_filter()
test_builtin_max_min()
test_builtin_map()
test_builtin_zip()
test_countOf()
test_indexOf()
test_unpack_iter()
test_extending_list_with_iterator_does_not_segfault()
os.rmdir(TESTDIR)
