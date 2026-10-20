# Adapted from CPython 3.13.16 Lib/test/test_slice.py (slice_indices(), the reference
# implementation of slice.indices(), and SliceTest.test_indices with its check_indices()),
# Lib/test/seq_tests.py (CommonTest.test_getslice's extended slices, for lists, tuples and strs),
# Lib/test/string_tests.py (StringLikeTest.test_slice and test_extended_getslice),
# Lib/test/list_tests.py (CommonTest.test_set_subscript, test_setslice,
# test_slice_assign_iterator, test_delslice, test_slice and test_extendedslicing) and
# Lib/test/test_list.py (ListTest.test_empty_slice and test_step_overflow), commit
# cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# There are no slice objects here (slice() is rejected: "unsupported call slice(int,int,int)",
# #501), so a slice is written as a subscript: slice_indices() takes the start, stop and step
# that upstream's slice object holds, test_indices checks `u[start:stop:step]` of
# u = list(range(10)) against list(range(*expected)) for each of upstream's
# slice(...).indices(10) == expected, and test_indices_check_indices runs check_indices()'s
# second half (range(length)[slice] == range(*slice.indices(length)), here
# list(range(length))[start:stop:step] against slice_indices()) for every start, stop and step
# of upstream's values and lengths but those past 64 bits (+-2**100, length 2**100) and the
# length 2**30 (a list that long); a ValueError on both sides (step 0) is equal. type2test is
# list, tuple or str, and test_extended_getslice's checkequal() is an assert, counted. Each
# assertEqual(a, b) prints a and asserts a == b; assertRaises is a try statement that prints
# the exception. list_test_extendedslicing_str is test_extendedslicing's a[2:3] = ["two",
# "elements"] on a list of strs (a list holds items of one type), without its b[slice(2,3)].
# EXCLUDED upstream cases:
# - test_constructor, test_repr, test_hash, test_cmp, test_members, test_indices' slice objects
#   with MyIndexable and float arguments, test_setslice_without_getslice (__setitem__ given a
#   slice), test_pickle, test_copy, test_deepcopy, test_cycle: slice objects (#501)
# - test_getslice's long ints (-pow(2,128), pow(2,145)) and test_extendedslicing's
#   del a[9::1<<333] (64-bit ints: OverflowError, documented)
# - test_set_subscript's a.__setitem__(slice(0, 10), 1) and a.__getitem__('x', 1), test_setslice's
#   a.__setitem__(slice(0, 1, 5)) and a.__setitem__() (special methods of lists, compile-time
#   type errors here)
import string
import sys


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def slice_indices(start0: int | None, stop0: int | None, step0: int | None,
                  length: int) -> tuple[int, int, int]:
    """
    Reference implementation for the slice.indices method.

    """
    # Compute step and length as integers.
    step = 1 if step0 is None else step0

    # Raise ValueError for negative length or zero step.
    if length < 0:
        raise ValueError("length should not be negative")
    if step == 0:
        raise ValueError("slice step cannot be zero")

    # Find lower and upper bounds for start and stop.
    lower = -1 if step < 0 else 0
    upper = length - 1 if step < 0 else length

    # Compute start.
    if start0 is None:
        start = upper if step < 0 else lower
    else:
        start = start0
        start = max(start + length, lower) if start < 0 else min(start, upper)

    # Compute stop.
    if stop0 is None:
        stop = lower if step < 0 else upper
    else:
        stop = stop0
        stop = max(stop + length, lower) if stop < 0 else min(stop, upper)

    return start, stop, step


def test_indices() -> None:
    u = list(range(10))
    check("[::2]", u[None:None:2], list(range(0, 10, 2)))
    check("[1::2]", u[1:None:2], list(range(1, 10, 2)))
    check("[::-1]", u[None:None:-1], list(range(9, -1, -1)))
    check("[::-2]", u[None:None:-2], list(range(9, -1, -2)))
    check("[3::-2]", u[3:None:-2], list(range(3, -1, -2)))
    check("[:-9]", u[:-9], list(range(0, 1, 1)))
    check("[:-10]", u[:-10], list(range(0, 0, 1)))
    check("[:-11]", u[:-11], list(range(0, 0, 1)))
    check("[:-10:-1]", u[:-10:-1], list(range(9, 0, -1)))
    check("[:-11:-1]", u[:-11:-1], list(range(9, -1, -1)))
    check("[:-12:-1]", u[:-12:-1], list(range(9, -1, -1)))
    check("[:9]", u[:9], list(range(0, 9, 1)))
    check("[:10]", u[:10], list(range(0, 10, 1)))
    check("[:11]", u[:11], list(range(0, 10, 1)))
    check("[:8:-1]", u[:8:-1], list(range(9, 8, -1)))
    check("[:9:-1]", u[:9:-1], list(range(9, 9, -1)))
    check("[:10:-1]", u[:10:-1], list(range(9, 9, -1)))
    check("[-100:100]", u[-100:100], u[:])
    check("[100:-100:-1]", u[100:-100:-1], u[::-1])
    check("[-100:100:2]", u[-100:100:2], list(range(0, 10, 2)))
    check("[::maxsize - 1]", list(range(10))[::sys.maxsize - 1], [0])


def check_indices(start: int | None, stop: int | None, step: int | None, length: int) -> int:
    try:
        i, j, k = slice_indices(start, stop, step, length)
        expected = list(range(i, j, k))
    except ValueError as e:
        expected = [-999]
    try:
        actual = list(range(length))[start:stop:step]
    except ValueError as e:
        actual = [-999]
    assert actual == expected, (start, stop, step, length)
    return len(actual)


def test_indices_check_indices() -> None:
    vals: list[int | None] = [None, -2**30, -53, -7, -1, 0, 1, 7, 53, 2**30]
    lengths = [0, 1, 7, 53]
    n = 0
    total = 0
    for a in vals:
        for b in vals:
            for c in vals:
                for length in lengths:
                    total += check_indices(a, b, c, length)
                    n += 1
    print(n, total)


def test_indices_zero_step() -> None:
    u = list(range(5))
    try:
        u[0:10:0]
    except ValueError as e:
        print("ValueError:", e)


def seq_test_getslice_list() -> None:
    l = [0, 1, 2, 3, 4]
    u = l[:]
    e: list[int] = []
    check("u[::]", u[::], u)
    check("u[::2]", u[::2], [0, 2, 4])
    check("u[1::2]", u[1::2], [1, 3])
    check("u[::-1]", u[::-1], [4, 3, 2, 1, 0])
    check("u[::-2]", u[::-2], [4, 2, 0])
    check("u[3::-2]", u[3::-2], [3, 1])
    check("u[3:3:-2]", u[3:3:-2], e)
    check("u[3:2:-2]", u[3:2:-2], [3])
    check("u[3:1:-2]", u[3:1:-2], [3])
    check("u[3:0:-2]", u[3:0:-2], [3, 1])
    check("u[::-100]", u[::-100], [4])
    check("u[100:-100:]", u[100:-100:], e)
    check("u[-100:100:]", u[-100:100:], u)
    check("u[100:-100:-1]", u[100:-100:-1], u[::-1])
    check("u[-100:100:-1]", u[-100:100:-1], e)
    check("u[-100:100:2]", u[-100:100:2], [0, 2, 4])
    a = [0,1,2,3,4]
    check("a[3::maxsize]", a[3::sys.maxsize], [3])


def seq_test_getslice_tuple() -> None:
    u = (0, 1, 2, 3, 4)
    check("u[::]", u[::], u)
    check("u[::2]", u[::2], (0, 2, 4))
    check("u[1::2]", u[1::2], (1, 3))
    check("u[::-1]", u[::-1], (4, 3, 2, 1, 0))
    check("u[::-2]", u[::-2], (4, 2, 0))
    check("u[3::-2]", u[3::-2], (3, 1))
    check("u[3:3:-2]", u[3:3:-2], ())
    check("u[3:2:-2]", u[3:2:-2], (3,))
    check("u[3:1:-2]", u[3:1:-2], (3,))
    check("u[3:0:-2]", u[3:0:-2], (3, 1))
    check("u[::-100]", u[::-100], (4,))
    check("u[100:-100:]", u[100:-100:], ())
    check("u[-100:100:]", u[-100:100:], u)
    check("u[100:-100:-1]", u[100:-100:-1], u[::-1])
    check("u[-100:100:-1]", u[-100:100:-1], ())
    check("u[-100:100:2]", u[-100:100:2], (0, 2, 4))
    a = (0,1,2,3,4)
    check("a[3::maxsize]", a[3::sys.maxsize], (3,))


def seq_test_getslice_str() -> None:
    u = "01234"
    check("u[::]", u[::], u)
    check("u[::2]", u[::2], "024")
    check("u[1::2]", u[1::2], "13")
    check("u[::-1]", u[::-1], "43210")
    check("u[::-2]", u[::-2], "420")
    check("u[3::-2]", u[3::-2], "31")
    check("u[3:3:-2]", u[3:3:-2], "")
    check("u[3:2:-2]", u[3:2:-2], "3")
    check("u[3:1:-2]", u[3:1:-2], "3")
    check("u[3:0:-2]", u[3:0:-2], "31")
    check("u[::-100]", u[::-100], "4")
    check("u[100:-100:]", u[100:-100:], "")
    check("u[-100:100:]", u[-100:100:], u)
    check("u[100:-100:-1]", u[100:-100:-1], u[::-1])
    check("u[-100:100:-1]", u[-100:100:-1], "")
    check("u[-100:100:2]", u[-100:100:2], "024")
    check("a[3::maxsize]", u[3::sys.maxsize], "3")


def string_test_slice() -> None:
    check("[0:1000]", 'abc'[0:1000], 'abc')
    check("[0:3]", 'abc'[0:3], 'abc')
    check("[0:2]", 'abc'[0:2], 'ab')
    check("[1:3]", 'abc'[1:3], 'bc')
    check("[1:2]", 'abc'[1:2], 'b')
    check("[2:2]", 'abc'[2:2], '')
    check("[1000:1000]", 'abc'[1000:1000], '')
    check("[2000:1000]", 'abc'[2000:1000], '')
    check("[2:1]", 'abc'[2:1], '')


def string_test_extended_getslice() -> None:
    s = string.ascii_letters + string.digits
    indices: list[int | None] = [0, None, 1, 3, 41, sys.maxsize, -1, -2, -37]
    n = 0
    for start in indices:
        for stop in indices:
            # Skip step 0 (invalid)
            for step in indices[1:]:
                L = list(s)[start:stop:step]
                check_s = "".join(L)
                assert s[start:stop:step] == check_s, (start, stop, step)
                n += 1
    print(n)


def list_test_set_subscript() -> None:
    a = list(range(20))
    try:
        a[0:10:0] = [1,2,3]
    except ValueError as e:
        print("ValueError:", e)
    try:
        a[0:10:2] = [1,2]
    except ValueError as e:
        print("ValueError:", e)
    a[2:10:3] = [1,2,3]
    check("a", a, [0, 1, 1, 3, 4, 2, 6, 7, 3,
                   9, 10, 11, 12, 13, 14, 15,
                   16, 17, 18, 19])


def list_test_setslice() -> None:
    e: list[int] = []
    l = [0, 1]
    a = l[:]
    a2 = a[:]
    for i in range(-3, 4):
        a[:i] = l[:i]
        check("a", a, l)
        a2 = a[:]
        a2[:i] = a[:i]
        check("a2", a2, a)
        a[i:] = l[i:]
        check("a", a, l)
        a2 = a[:]
        a2[i:] = a[i:]
        check("a2", a2, a)
        for j in range(-3, 4):
            a[i:j] = l[i:j]
            check("a", a, l)
            a2 = a[:]
            a2[i:j] = a[i:j]
            check("a2", a2, a)

    aa2 = a2[:]
    aa2[:0] = [-2, -1]
    check("aa2", aa2, [-2, -1, 0, 1])
    aa2[0:] = []
    check("aa2", aa2, e)

    a = [1, 2, 3, 4, 5]
    a[:-1] = a
    check("a", a, [1, 2, 3, 4, 5, 5])
    a = [1, 2, 3, 4, 5]
    a[1:] = a
    check("a", a, [1, 1, 2, 3, 4, 5])
    a = [1, 2, 3, 4, 5]
    a[1:-1] = a
    check("a", a, [1, 1, 2, 3, 4, 5, 5])

    a = []
    a[:] = tuple(range(10))
    check("a", a, list(range(10)))


def list_test_slice_assign_iterator() -> None:
    x = list(range(5))
    x[0:3] = reversed(range(3))
    check("x", x, [2, 1, 0, 3, 4])
    x[:] = reversed(range(3))
    check("x", x, [2, 1, 0])


def list_test_delslice() -> None:
    e: list[int] = []
    a = [0, 1]
    del a[1:2]
    del a[0:1]
    check("a", a, e)

    a = [0, 1]
    del a[-2:-1]
    check("a", a, [1])

    a = [0, 1]
    del a[1:]
    del a[:1]
    check("a", a, e)

    a = [0, 1]
    del a[-1:]
    check("a", a, [0])

    a = [0, 1]
    del a[:]
    check("a", a, e)


def list_test_slice() -> None:
    u = list("spam")
    u[:2] = "h"
    check("u", u, list("ham"))


def list_test_extendedslicing() -> None:
    a = [0,1,2,3,4]
    del a[::2]
    check("a", a, [1,3])
    a = list(range(5))
    del a[1::2]
    check("a", a, [0,2,4])
    a = list(range(5))
    del a[1::-2]
    check("a", a, [0,2,3,4])
    a = list(range(10))
    del a[::1000]
    check("a", a, [1, 2, 3, 4, 5, 6, 7, 8, 9])
    #  assignment
    a = list(range(10))
    a[::2] = [-1]*5
    check("a", a, [-1, 1, -1, 3, -1, 5, -1, 7, -1, 9])
    a = list(range(10))
    a[::-4] = [10]*3
    check("a", a, [0, 10, 2, 3, 4, 10, 6, 7, 8 ,10])
    a = list(range(4))
    a[::-1] = a
    check("a", a, [3, 2, 1, 0])
    a = list(range(10))
    a[::2] = tuple(range(5))
    check("a", a, [0, 1, 1, 3, 2, 5, 3, 7, 4, 9])


def list_test_extendedslicing_str() -> None:
    a = [str(i) for i in range(10)]
    b = a[:]
    c = a[:]
    a[2:3] = ["two", "elements"]
    c[2:3:] = ["two", "elements"]
    check("a", a, c)
    print(a)


def test_empty_slice() -> None:
    x: list[int] = []
    x[:] = x
    e: list[int] = []
    check("x", x, e)


def test_step_overflow() -> None:
    a = [0, 1, 2, 3, 4]
    a[1::sys.maxsize] = [0]
    check("a[3::maxsize]", a[3::sys.maxsize], [3])
    print(a)


test_indices()
test_indices_check_indices()
test_indices_zero_step()
seq_test_getslice_list()
seq_test_getslice_tuple()
seq_test_getslice_str()
string_test_slice()
string_test_extended_getslice()
list_test_set_subscript()
list_test_setslice()
list_test_slice_assign_iterator()
list_test_delslice()
list_test_slice()
list_test_extendedslicing()
list_test_extendedslicing_str()
test_empty_slice()
test_step_overflow()
