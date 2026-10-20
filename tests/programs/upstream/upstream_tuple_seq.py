# Adapted from CPython 3.13.16 Lib/test/test_tuple.py, class TupleTest: test_truth, test_len,
# test_iadd, test_repr and test_lexicographic_ordering; and the methods of Lib/test/seq_tests.py's CommonTest that TupleTest
# runs: test_truth, test_getitem, test_getslice, test_contains, test_contains_fake,
# test_contains_order, test_len, test_minmax, test_add, test_mul, test_iadd, test_repeat,
# test_cmp (with _assert_cmp), test_count and test_index; commit
# cbc944f4bc59639a444dd971c737788ba2283a91. test.support's ALWAYS_EQ and NEVER_EQ are written
# out, and the classes of test_contains_order, test_count and test_index are at the module's top
# level (test_index's BadCmp and BadExc are test_count's).
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name, CommonTest's prefixed seq_; assertEqual(a,
# b) prints a and asserts a == b. `is` between bools is rejected here, so _assert_cmp's
# assertIs(a == b, r == 0) and the like print the comparison and assert that its repr is the
# expected bool's. type2test is tuple, and tuple() of an iterable is not supported, so
# self.type2test(x) is the tuple display of x's items. A tuple is indexed by integer constants
# here, so test_getitem's loops over indices and its u[int(i)] are written out, and test_repeat's
# loops over s and n are functions of s with each n written out.
# EXCLUDED upstream cases:
# - test_getitem's IndexErrors (u[-len(u)-1], u[len(u)], ()[0], ()[-1], a[-3], a[3]): a constant
#   tuple index out of range is a compile-time error here, with CPython's message
#   (tests/errors/upstream/upstream_tuple_index_*.py); u.__getitem__(slice(0,10,0)) and u.__getitem__()
#   (__getitem__ of a tuple and slice() are not supported)
# - test_getitem_error (t['a']: a compile-time error worded "tuple index must be an integer
#   constant" where CPython says "tuple indices must be integers or slices, not str")
# - test_constructors (TupleTest's and CommonTest's), test_keyword_args, test_tupleresizebug and
#   test_iadd's u = self.type2test("spam"): tuple() of an iterator object or of a generator
#   function's generator is not supported, nor tuple(sequence=()), tuple([]) without a type, or
#   tuple("spam") += tuple("eggs") (runtime-length tuples are not concatenated)
# - test_iadd's u += (2, 3) and u += (4, 5), TupleTest.test_iadd's u += (2, 3), and test_imul
#   (CommonTest's and TupleTest's: u *= 3, u *= 0): a variable has one type here, and these
#   change the tuple's length, which is part of its type
# - test_cmp's _assert_cmp(a, self.type2test([0]), 1): its == and != (a tuple compared with one
#   of another length by == or != is a compile-time error here, as documented: values of types
#   that cannot be equal); its <, <=, > and >= are assert_order's
# - test_contains_order's checklast.__contains__(1), which is `1 in checklast` here (tuple's
#   special methods are not supported)
# - test_contains' u.__contains__() and test_getitem's u.__getitem__() (TypeError; tuple's
#   special methods are not supported), test_subscript (a.__getitem__(), slice objects)
# - test_getslice's extended slices (tests/programs/upstream/upstream_slice_steps.py adopts them for tuples, lists
#   and strs) and its extreme cases with long ints (-pow(2,128) and pow(2,145) overflow)
# - test_count's a.count() and test_index's u.index() (TypeError: a compile-time error here, as
#   tests/errors/containers/tuple_count_arity.py's); test_index's a.index(0, -4*sys.maxsize, 4*sys.maxsize)
#   and a.index(0, 4*sys.maxsize, -4*sys.maxsize) (ints are 64-bit: 4*sys.maxsize overflows)
# - test_repeat's id(s) == id(s*1) (id() is not supported); test_bigrepeat (it runs only where
#   sys.maxsize <= 2**31 - 1)
# - test_repr_large, and test_repeat's (0, 1, 2)*4 (a tuple holds at most 9 items here: (0,) * 10
#   is rejected)
# - test_mul's subclass, test_keywords_in_subclass, test_getitemoverwriteiter and
#   test_no_comdat_folding (subclasses of tuple)
# - test_hash_exact and test_hash_optional (hash() is not supported; test_hash_optional does
#   nothing unless RUN_ALL_HASH_TESTS)
# - test_track_literals, test_track_dynamic, test_track_subtypes and test_bug7466 (gc), and
#   test_pickle, test_iterator_pickle, test_reversed_pickle and test_free_after_iterating
#   (pickle, support.check_free_after_iterating)


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def check_true(label: str, got: bool) -> None:
    print(label, repr(got))
    assert got, label


def check_false(label: str, got: bool) -> None:
    print(label, repr(got))
    assert not got, label


def check_is(label: str, got: bool, expected: bool) -> None:
    # assertIs(got, expected) of bools
    print(label, repr(got))
    assert repr(got) == repr(expected), label


# Lib/test/seq_tests.py, CommonTest, with type2test = tuple
def seq_test_truth() -> None:
    check_false("tuple()", bool(()))
    check_true("tuple([42])", bool((42,)))


def seq_test_getitem() -> None:
    u = (0, 1, 2, 3, 4)
    # for i in range(len(u)): self.assertEqual(u[i], i); self.assertEqual(u[int(i)], i)
    check("u[0]", u[0], 0)
    check("u[1]", u[1], 1)
    check("u[2]", u[2], 2)
    check("u[3]", u[3], 3)
    check("u[4]", u[4], 4)
    # for i in range(-len(u), -1): self.assertEqual(u[i], len(u)+i); and u[int(i)]
    check("u[-5]", u[-5], len(u)-5)
    check("u[-4]", u[-4], len(u)-4)
    check("u[-3]", u[-3], len(u)-3)
    check("u[-2]", u[-2], len(u)-2)

    a = (10, 11)
    check("a[0]", a[0], 10)
    check("a[1]", a[1], 11)
    check("a[-2]", a[-2], 10)
    check("a[-1]", a[-1], 11)


def seq_test_getslice() -> None:
    u = (0, 1, 2, 3, 4)  # self.type2test(l), l = [0, 1, 2, 3, 4]
    check("u[0:0]", u[0:0], ())
    check("u[1:2]", u[1:2], (1,))
    check("u[-2:-1]", u[-2:-1], (3,))
    check("u[-1000:1000]", u[-1000:1000], u)
    check("u[1000:-1000]", u[1000:-1000], ())
    check("u[:]", u[:], u)
    check("u[1:None]", u[1:None], (1, 2, 3, 4))
    check("u[None:3]", u[None:3], (0, 1, 2))


def seq_test_contains() -> None:
    u = (0, 1, 2)
    for i in u:
        check_true("%d in u" % i, i in u)
    for i in min(u)-1, max(u)+1:
        check_true("%d not in u" % i, i not in u)


class _ALWAYS_EQ:
    # test.support's ALWAYS_EQ: an object equal to everything
    def __eq__(self, other) -> bool:
        return True

    def __ne__(self, other) -> bool:
        return False


class _NEVER_EQ:
    # test.support's NEVER_EQ: an object equal to nothing
    def __eq__(self, other) -> bool:
        return False

    def __ne__(self, other) -> bool:
        return True


ALWAYS_EQ = _ALWAYS_EQ()
NEVER_EQ = _NEVER_EQ()


def seq_test_contains_fake() -> None:
    # Sequences must use rich comparison against each item
    # (unless "is" is true, or an earlier item answered)
    # So ALWAYS_EQ must be found in all non-empty sequences.
    check_false("ALWAYS_EQ in ()", ALWAYS_EQ in ())
    check_true("ALWAYS_EQ in (1,)", ALWAYS_EQ in (1,))
    check_true("1 in (ALWAYS_EQ,)", 1 in (ALWAYS_EQ,))
    check_false("NEVER_EQ in ()", NEVER_EQ in ())
    check_false("ALWAYS_EQ in (NEVER_EQ,)", ALWAYS_EQ in (NEVER_EQ,))
    check_true("NEVER_EQ in (ALWAYS_EQ,)", NEVER_EQ in (ALWAYS_EQ,))


class DoNotTestEq(Exception):
    pass


class StopCompares:
    def __eq__(self, other) -> bool:
        raise DoNotTestEq


def seq_test_contains_order() -> None:
    # Sequences must test in-order.  If a rich comparison has side
    # effects, these will be visible to tests against later members.
    # In this test, the "side effect" is a short-circuiting raise.
    checkfirst = (1, StopCompares())
    check_true("1 in checkfirst", 1 in checkfirst)
    checklast = (StopCompares(), 1)
    try:
        print("1 in checklast", 1 in checklast)
        assert False, "1 in checklast"
    except DoNotTestEq:
        print("1 in checklast: DoNotTestEq")


def seq_test_len() -> None:
    check("len(tuple())", len(()), 0)
    check("len(tuple([]))", len(()), 0)
    check("len(tuple([0]))", len((0,)), 1)
    check("len(tuple([0, 1, 2]))", len((0, 1, 2)), 3)


def seq_test_minmax() -> None:
    u = (0, 1, 2)
    check("min(u)", min(u), 0)
    check("max(u)", max(u), 2)


def seq_test_add() -> None:
    u1 = (0,)
    u2 = (0, 1)
    check("u1 + tuple()", u1 + (), u1)
    check("tuple() + u1", () + u1, u1)
    check("u1 + (1,)", u1 + (1,), u2)
    check("(-1,) + u1", (-1,) + u1, (-1, 0))


def seq_test_mul() -> None:
    u2 = (0, 1)
    check("u2*0", u2*0, ())
    check("0*u2", 0*u2, ())
    check("u2*1", u2*1, u2)
    check("1*u2", 1*u2, u2)
    check("u2*2", u2*2, u2+u2)
    check("2*u2", 2*u2, u2+u2)
    check("u2*3", u2*3, u2+u2+u2)
    check("3*u2", 3*u2, u2+u2+u2)


def seq_test_iadd() -> None:
    u = (0, 1)
    u += ()
    check("u += tuple()", u, (0, 1))


def repeat_cases(s) -> None:
    # for n in range(-3, 5): self.assertEqual(self.type2test(s*n), self.type2test(s)*n)
    check("%r*-3" % (s,), s*-3, s*-3)
    check("%r*-2" % (s,), s*-2, s*-2)
    check("%r*-1" % (s,), s*-1, s*-1)
    check("%r*0" % (s,), s*0, s*0)
    check("%r*1" % (s,), s*1, s*1)
    check("%r*2" % (s,), s*2, s*2)
    check("%r*3" % (s,), s*3, s*3)
    check("%r*(-4)" % (s,), s*(-4), ())


def repeat_4(s) -> None:
    check("%r*4" % (s,), s*4, s*4)


def seq_test_repeat() -> None:
    # for m in range(4): s = tuple(range(m))
    repeat_cases(())
    repeat_4(())
    repeat_cases((0,))
    repeat_4((0,))
    repeat_cases((0, 1))
    repeat_4((0, 1))
    repeat_cases((0, 1, 2))  # (0, 1, 2)*4 has 12 items


def assert_cmp(label: str, a, b, r: int) -> None:
    check_is(label + " ==", a == b, r == 0)
    check_is(label + " !=", a != b, r != 0)
    check_is(label + " >", a > b, r > 0)
    check_is(label + " <=", a <= b, r <= 0)
    check_is(label + " <", a < b, r < 0)
    check_is(label + " >=", a >= b, r >= 0)


def assert_order(label: str, a, b, r: int) -> None:
    # _assert_cmp's orderings of tuples of different lengths, whose == and != are rejected here
    check_is(label + " >", a > b, r > 0)
    check_is(label + " <=", a <= b, r <= 0)
    check_is(label + " <", a < b, r < 0)
    check_is(label + " >=", a >= b, r >= 0)


def seq_test_cmp() -> None:
    a = (0, 1)
    assert_cmp("a, a", a, a, 0)
    assert_cmp("a, (0, 1)", a, (0, 1), 0)
    assert_order("a, (0,)", a, (0,), 1)
    assert_cmp("a, (0, 2)", a, (0, 2), -1)


# Lib/test/test_tuple.py, TupleTest
def test_truth() -> None:
    seq_test_truth()
    check_true("not ()", not ())
    check_true("(42, )", bool((42, )))


def test_len() -> None:
    seq_test_len()
    check("len(())", len(()), 0)
    check("len((0,))", len((0,)), 1)
    check("len((0, 1, 2))", len((0, 1, 2)), 3)


def test_iadd() -> None:
    seq_test_iadd()


def test_lexicographic_ordering() -> None:
    # Issue 21100
    a = (1, 2)
    b = (1, 2, 0)
    c = (1, 3)
    check_true("a < b", a < b)
    check_true("b < c", b < c)


class BadExc(Exception):
    pass


class BadCmp:
    def __eq__(self, other) -> bool:
        if other == 2:
            raise BadExc()
        return False


def seq_test_count() -> None:
    a = (0, 1, 2)*3
    check("a.count(0)", a.count(0), 3)
    check("a.count(1)", a.count(1), 3)
    check("a.count(3)", a.count(3), 0)

    check("a.count(ALWAYS_EQ)", a.count(ALWAYS_EQ), 9)
    check("(ALWAYS_EQ, ALWAYS_EQ).count(1)", (ALWAYS_EQ, ALWAYS_EQ).count(1), 2)
    check("(ALWAYS_EQ, ALWAYS_EQ).count(NEVER_EQ)", (ALWAYS_EQ, ALWAYS_EQ).count(NEVER_EQ), 2)
    check("(NEVER_EQ, NEVER_EQ).count(ALWAYS_EQ)", (NEVER_EQ, NEVER_EQ).count(ALWAYS_EQ), 0)

    try:
        a.count(BadCmp())
        assert False, "a.count(BadCmp())"
    except BadExc:
        print("a.count(BadCmp()): BadExc")


def seq_test_index() -> None:
    u = (0, 1)
    check("u.index(0)", u.index(0), 0)
    check("u.index(1)", u.index(1), 1)
    try:
        u.index(2)
        assert False, "u.index(2)"
    except ValueError as e:
        print("u.index(2): ValueError", e)

    u2 = (-2, -1, 0, 0, 1, 2)  # (u, rebound)
    check("u.count(0)", u2.count(0), 2)
    check("u.index(0)", u2.index(0), 2)
    check("u.index(0, 2)", u2.index(0, 2), 2)
    check("u.index(-2, -10)", u2.index(-2, -10), 0)
    check("u.index(0, 3)", u2.index(0, 3), 3)
    check("u.index(0, 3, 4)", u2.index(0, 3, 4), 3)
    try:
        u2.index(2, 0, -10)
        assert False, "u.index(2, 0, -10)"
    except ValueError as e:
        print("u.index(2, 0, -10): ValueError", e)

    check("u.index(ALWAYS_EQ)", u2.index(ALWAYS_EQ), 0)
    check("(ALWAYS_EQ, ALWAYS_EQ).index(1)", (ALWAYS_EQ, ALWAYS_EQ).index(1), 0)
    check("(ALWAYS_EQ, ALWAYS_EQ).index(NEVER_EQ)", (ALWAYS_EQ, ALWAYS_EQ).index(NEVER_EQ), 0)
    try:
        (NEVER_EQ, NEVER_EQ).index(ALWAYS_EQ)
        assert False, "(NEVER_EQ, NEVER_EQ).index(ALWAYS_EQ)"
    except ValueError as e:
        print("(NEVER_EQ, NEVER_EQ).index(ALWAYS_EQ): ValueError", e)

    a = (0, 1, 2, 3)
    try:
        a.index(BadCmp())
        assert False, "a.index(BadCmp())"
    except BadExc:
        print("a.index(BadCmp()): BadExc")

    a2 = (-2, -1, 0, 0, 1, 2)  # (a, rebound)
    check("a.index(0)", a2.index(0), 2)
    check("a.index(0, 2)", a2.index(0, 2), 2)
    check("a.index(0, -4)", a2.index(0, -4), 2)
    check("a.index(-2, -10)", a2.index(-2, -10), 0)
    check("a.index(0, 3)", a2.index(0, 3), 3)
    check("a.index(0, -3)", a2.index(0, -3), 3)
    check("a.index(0, 3, 4)", a2.index(0, 3, 4), 3)
    check("a.index(0, -3, -2)", a2.index(0, -3, -2), 3)
    try:
        a2.index(2, 0, -10)
        assert False, "a.index(2, 0, -10)"
    except ValueError as e:
        print("a.index(2, 0, -10): ValueError", e)


def test_repr() -> None:
    l0 = ()  # tuple()
    l2 = (0, 1, 2)
    a0 = l0  # self.type2test(l0)
    a2 = l2
    check("str(a0)", str(a0), repr(l0))
    check("str(a2)", str(a2), repr(l2))
    check("repr(a0)", repr(a0), "()")
    check("repr(a2)", repr(a2), "(0, 1, 2)")


test_truth()
seq_test_getitem()
seq_test_getslice()
seq_test_contains()
seq_test_contains_fake()
seq_test_contains_order()
test_len()
seq_test_minmax()
seq_test_add()
seq_test_mul()
test_iadd()
seq_test_repeat()
seq_test_cmp()
seq_test_count()
seq_test_index()
test_repr()
test_lexicographic_ordering()
