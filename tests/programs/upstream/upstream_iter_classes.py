# Adapted from CPython 3.13.16 Lib/test/test_iter.py, class TestCase: the tests of iter(),
# next() and iterator classes that tests/programs/upstream/upstream_iter_builtins.py leaves out: test_iter_basic,
# test_iter_idempotency, test_iter_for_loop, test_iter_independence, test_iter_class_for,
# test_iter_class_iter, test_iter_big_range, test_iter_empty, test_iter_tuple, test_iter_range,
# test_iter_string, test_builtin_filter, test_builtin_max_min, test_builtin_zip,
# test_unicode_join_endcase, test_in_and_not_in, test_indexOf, test_unpack_iter and the
# test_sinkstate_* tests, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b, assertRaises a try statement. check_iterator() and check_for_loop() leave out their
# pickle round trips. TESTFN is a file in a tempfile.mkdtemp() directory; files have no seek()
# here, so where upstream rewinds with f.seek(0, 0), the file is opened again. The helper
# classes take annotated arguments where their fields need types. A range as a value is
# iter(range(...)) or list(range(...)); an empty display that nothing types is an annotated
# variable; Seq's iterator class is a module-level class (no class statement in a function), and
# Seq takes its values as a list rather than *args.
# EXCLUDED upstream cases:
# - pickle, __reduce__, __setstate__, two-argument iter(), sequence classes (iteration through
#   __getitem__ alone), generators, tracebacks and reference counting: as in
#   tests/programs/upstream/upstream_iter_builtins.py
# - test_nested_comprehensions_iter: tests/programs/upstream/upstream_iter_comprehensions.py adopts it
# - test_new_style_iter_class and test_error_iter: iter() of an object whose class has no
#   __next__ (or no __iter__) is a compile-time error here (tests/errors/generators/iterator_no_next.py)
# - test_in_and_not_in's items of other types than int ("abc", 42.42, (3, 4), [], {1: 1},
#   3-12j, sc5: a tuple whose items differ), ALWAYS_EQ and NEVER_EQ, BadIterableClass (an
#   __iter__ that only raises has no iterator type), its dict and file parts (already in
#   tests/programs/upstream/upstream_iter_builtins.py)
# - test_builtin_zip's TypeErrors and its sequence classes; test_unpack_iter's `a, b, c = len`,
#   `a, b, c = f` (unpacking a file) and `(c,) = {42: 24}` (unpacking a dict)
# - test_sinkstate_dict's loop over iter(a), a.keys(), a.items() and a.values() (a tuple whose
#   items differ): each is checked in turn; test_sinkstate_enumerate: enumerate() as a value;
#   test_3720 (deleting __next__); test_extending_list_with_iterator_does_not_segfault (a
#   generator)
import os
import tempfile
from operator import indexOf

TESTDIR = tempfile.mkdtemp()
TESTFN = os.path.join(TESTDIR, "upstream_iter_classes.txt")

# Test result of triple loop (too big to inline)
TRIPLETS = [(0, 0, 0), (0, 0, 1), (0, 0, 2),
            (0, 1, 0), (0, 1, 1), (0, 1, 2),
            (0, 2, 0), (0, 2, 1), (0, 2, 2),

            (1, 0, 0), (1, 0, 1), (1, 0, 2),
            (1, 1, 0), (1, 1, 1), (1, 1, 2),
            (1, 2, 0), (1, 2, 1), (1, 2, 2),

            (2, 0, 0), (2, 0, 1), (2, 0, 2),
            (2, 1, 0), (2, 1, 1), (2, 1, 2),
            (2, 2, 0), (2, 2, 1), (2, 2, 2)]

# Helper classes


class BasicIterClass:
    def __init__(self, n: int) -> None:
        self.n = n
        self.i = 0

    def __next__(self):
        res = self.i
        if res >= self.n:
            raise StopIteration
        self.i = res + 1
        return res

    def __iter__(self):
        return self


class IteratingSequenceClass:
    def __init__(self, n: int) -> None:
        self.n = n

    def __iter__(self):
        return BasicIterClass(self.n)


class IteratorProxyClass:
    def __init__(self, i):
        self.i = i

    def __next__(self):
        return next(self.i)

    def __iter__(self):
        return self


def unlink(path: str) -> None:
    os.remove(path)


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


# Helper to check that an iterator returns a given sequence
def check_iterator(label: str, it, seq) -> None:
    res = []
    while 1:
        try:
            val = next(it)
        except StopIteration:
            break
        res.append(val)
    check(label, res, seq)


# Helper to check that a for loop generates a given sequence
def check_for_loop(label: str, expr, seq) -> None:
    res = []
    for val in expr:
        res.append(val)
    check(label, res, seq)


# Test basic use of iter() function
def test_iter_basic() -> None:
    check_iterator("iter(range(10))", iter(range(10)), list(range(10)))


# Test that iter(iter(x)) is the same as iter(x)
def test_iter_idempotency() -> None:
    seq = list(range(10))
    it = iter(seq)
    it2 = iter(it)
    check("it is it2", it is it2, True)


# Test that for loops over iterators work
def test_iter_for_loop() -> None:
    check_for_loop("for val in iter(range(10))", iter(range(10)), list(range(10)))


# Test several independent iterators over the same list
def test_iter_independence() -> None:
    res = []
    for i in iter(range(3)):
        for j in iter(range(3)):
            for k in iter(range(3)):
                res.append((i, j, k))
    check("triple loop", res, TRIPLETS)


# Test a class with __iter__ in a for loop
def test_iter_class_for() -> None:
    check_for_loop("for val in IteratingSequenceClass(10)", IteratingSequenceClass(10), list(range(10)))


# Test a class with __iter__ with explicit iter()
def test_iter_class_iter() -> None:
    check_iterator("iter(IteratingSequenceClass(10))", iter(IteratingSequenceClass(10)), list(range(10)))


# Test a big range
def test_iter_big_range() -> None:
    res = []
    for val in iter(range(10000)):
        res.append(val)
    check("len(iter(range(10000)))", len(res), 10000)
    assert res == list(range(10000))


# Test an empty list
def test_iter_empty() -> None:
    empty: list[int] = []
    check_for_loop("for val in iter([])", iter(empty), empty)


# Test a tuple
def test_iter_tuple() -> None:
    check_for_loop("for val in iter((0, ..., 9))", iter((0, 1, 2, 3, 4, 5, 6, 7, 8, 9)), list(range(10)))


# Test a range
def test_iter_range() -> None:
    check_for_loop("for val in iter(range(10))", iter(range(10)), list(range(10)))


# Test a string
def test_iter_string() -> None:
    check_for_loop("for val in iter('abcde')", iter("abcde"), ["a", "b", "c", "d", "e"])


class Boolean:
    def __init__(self, truth: bool) -> None:
        self.truth = truth

    def __bool__(self) -> bool:
        return self.truth

    def __repr__(self) -> str:
        return f"Boolean({self.truth})"


class SeqIter:
    def __init__(self, vals: list[Boolean]) -> None:
        self.vals = vals
        self.i = 0

    def __iter__(self):
        return self

    def __next__(self):
        i = self.i
        self.i = i + 1
        if i < len(self.vals):
            return self.vals[i]
        else:
            raise StopIteration


class Seq:
    def __init__(self, args: list[Boolean]) -> None:
        self.vals = args

    def __iter__(self):
        return SeqIter(self.vals)


# Test filter()'s use of iterators.
def test_builtin_filter() -> None:
    bTrue = Boolean(True)
    bFalse = Boolean(False)
    seq = Seq([bTrue, bFalse] * 25)
    check("list(filter(lambda x: not x, seq))", list(filter(lambda x: not x, seq)), [bFalse] * 25)
    check("list(filter(lambda x: not x, iter(seq)))", list(filter(lambda x: not x, iter(seq))), [bFalse] * 25)


# Test max() and min()'s use of iterators.
def test_builtin_max_min() -> None:
    d = {"one": 1, "two": 2, "three": 3}
    check("min(iter(d.values()))", min(iter(d.values())), 1)
    check("max(iter(d))", max(iter(d)), "two")


# Generate all ints starting at constructor arg.
class IntsFrom:
    def __init__(self, start: int) -> None:
        self.i = start

    def __iter__(self):
        return self

    def __next__(self):
        i = self.i
        self.i = i + 1
        return i


# Test zip()'s use of iterators.
def test_builtin_zip() -> None:
    check("list(zip(IteratingSequenceClass(3)))", list(zip(IteratingSequenceClass(3))),
          [(0,), (1,), (2,)])

    f = open(TESTFN, "w", encoding="utf-8")
    try:
        f.write("a\n" "bbb\n" "cc\n")
    finally:
        f.close()
    f = open(TESTFN, "r", encoding="utf-8")
    try:
        check("list(zip(IntsFrom(0), f, IntsFrom(-100)))", list(zip(IntsFrom(0), f, IntsFrom(-100))),
              [(0, "a\n", -100),
               (1, "bbb\n", -99),
               (2, "cc\n", -98)])
    finally:
        f.close()
        try:
            unlink(TESTFN)
        except OSError:
            pass


# This class inserts a Unicode object into its argument's natural
# iteration, in the 3rd position.
class OhPhooey:
    def __init__(self, seq) -> None:
        self.it = iter(seq)
        self.i = 0

    def __iter__(self):
        return self

    def __next__(self):
        i = self.i
        self.i = i + 1
        if i == 2:
            return "fooled you!"
        return next(self.it)


def test_unicode_join_endcase() -> None:
    f = open(TESTFN, "w", encoding="utf-8")
    try:
        f.write("a\n" + "b\n" + "c\n")
    finally:
        f.close()

    f = open(TESTFN, "r", encoding="utf-8")
    # Nasty:  string.join(s) can't know whether unicode.join() is needed
    # until it's seen all of s's elements.  But in this case, f's
    # iterator cannot be restarted.  So what we're testing here is
    # whether string.join() can manage to remember everything it's seen
    # and pass that on to unicode.join().
    try:
        got = " - ".join(OhPhooey(f))
        check("' - '.join(OhPhooey(f))", got, "a\n - b\n - fooled you! - c\n")
    finally:
        f.close()
        try:
            unlink(TESTFN)
        except OSError:
            pass


# Test iterators with 'x in y' and 'x not in y'.
def test_in_and_not_in() -> None:
    sc5 = IteratingSequenceClass(5)
    for i in range(5):
        check(f"{i} in sc5", i in sc5, True)
    for i in -1, 5:
        check(f"{i} not in sc5", i not in sc5, True)
    check("1 in IteratorProxyClass(iter([1]))", 1 in IteratorProxyClass(iter([1])), True)


# Test iterators with operator.indexOf (PySequence_Index).
def test_indexOf() -> None:
    f = open(TESTFN, "w", encoding="utf-8")
    try:
        f.write("a\n" "b\n" "c\n" "d\n" "e\n")
    finally:
        f.close()
    f = open(TESTFN, "r", encoding="utf-8")
    try:
        fiter = iter(f)
        check("indexOf(fiter, 'b\\n')", indexOf(fiter, "b\n"), 1)
        check("indexOf(fiter, 'd\\n')", indexOf(fiter, "d\n"), 1)
        check("indexOf(fiter, 'e\\n')", indexOf(fiter, "e\n"), 0)
        try:
            indexOf(fiter, "a\n")
            print("no ValueError")
        except ValueError:
            print("indexOf(fiter, 'a\\n'): ValueError")
    finally:
        f.close()
        try:
            unlink(TESTFN)
        except OSError:
            pass

    iclass = IteratingSequenceClass(3)
    for i in range(3):
        check(f"indexOf(iclass, {i})", indexOf(iclass, i), i)
    try:
        indexOf(iclass, -1)
        print("no ValueError")
    except ValueError:
        print("indexOf(iclass, -1): ValueError")


# Test iterators on RHS of unpacking assignments.
def test_unpack_iter() -> None:
    a, b = 1, 2
    check("(a, b)", (a, b), (1, 2))

    a, b, c = IteratingSequenceClass(3)
    check("(a, b, c)", (a, b, c), (0, 1, 2))

    try:    # too many values
        a, b = IteratingSequenceClass(3)
    except ValueError:
        print("too many values: ValueError")
    else:
        print("should have raised ValueError")

    try:    # not enough values
        a, b, c = IteratingSequenceClass(2)
    except ValueError:
        print("not enough values: ValueError")
    else:
        print("should have raised ValueError")

    a, b, c = {1: 42, 2: 42, 3: 42}.values()
    check("(a, b, c)", (a, b, c), (42, 42, 42))

    (a, b), c = IteratingSequenceClass(2), 42
    check("(a, b, c)", (a, b, c), (0, 1, 42))


# Make sure StopIteration is a "sink state".
# This tests various things that weren't sink states in Python 2.2.1,
# plus various things that always were fine.

def test_sinkstate_list() -> None:
    # This used to fail
    a = list(range(5))
    b = iter(a)
    check("list(b)", list(b), list(range(5)))
    a.extend(range(5, 10))
    no_ints: list[int] = []
    check("list(b)", list(b), no_ints)


def test_sinkstate_tuple() -> None:
    a = (0, 1, 2, 3, 4)
    b = iter(a)
    check("list(b)", list(b), list(range(5)))
    no_ints: list[int] = []
    check("list(b)", list(b), no_ints)


def test_sinkstate_string() -> None:
    a = "abcde"
    b = iter(a)
    check("list(b)", list(b), ['a', 'b', 'c', 'd', 'e'])
    no_strs: list[str] = []
    check("list(b)", list(b), no_strs)


def test_sinkstate_dict() -> None:
    # XXX For a more thorough test, see towards the end of:
    # http://mail.python.org/pipermail/python-dev/2002-July/026512.html
    a = {1: 1, 2: 2, 0: 0, 4: 4, 3: 3}
    no_ints: list[int] = []
    no_items: list[tuple[int, int]] = []
    b = iter(a)
    check("len(list(b))", len(list(b)), 5)
    check("list(b)", list(b), no_ints)
    k = iter(a.keys())
    check("len(list(k))", len(list(k)), 5)
    check("list(k)", list(k), no_ints)
    i = iter(a.items())
    check("len(list(i))", len(list(i)), 5)
    check("list(i)", list(i), no_items)
    v = iter(a.values())
    check("len(list(v))", len(list(v)), 5)
    check("list(v)", list(v), no_ints)


def test_sinkstate_range() -> None:
    b = iter(range(5))
    check("list(b)", list(b), list(range(5)))
    no_ints: list[int] = []
    check("list(b)", list(b), no_ints)


test_iter_basic()
test_iter_idempotency()
test_iter_for_loop()
test_iter_independence()
test_iter_class_for()
test_iter_class_iter()
test_iter_big_range()
test_iter_empty()
test_iter_tuple()
test_iter_range()
test_iter_string()
test_builtin_filter()
test_builtin_max_min()
test_builtin_zip()
test_unicode_join_endcase()
test_in_and_not_in()
test_indexOf()
test_unpack_iter()
test_sinkstate_list()
test_sinkstate_tuple()
test_sinkstate_string()
test_sinkstate_dict()
test_sinkstate_range()
os.rmdir(TESTDIR)
