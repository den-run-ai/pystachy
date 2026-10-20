# Adapted from CPython 3.13.16 Lib/test/test_set.py: TestJointOps' test_badcmp (for set and
# frozenset, which run it) and TestSet.test_hash_collision_remove_add, with the module's
# CustomHash and BadCmp; TestWeirdBugs' test_8420_set_merge,
# test_merge_and_mutate and test_hash_collision_concurrent_add; and Lib/test/test_hash.py:
# HashInheritanceTestCase's test_default_hash, test_fixed_hash and test_error_hash (in
# test_hash_inheritance and test_error_hash) and HashEqualityTestCase's test_numeric_literals
# and test_coerced_integers; commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Objects of classes with __hash__ and __eq__ as set elements and dict keys (#484). Each test
# method becomes a function of the same name; assertEqual(a, b) is eq(a, b), which prints a and
# asserts a == b; assertRaises(E, f, *args) is a try statement that prints the exception
# (s.__contains__(x) is `x in s`). The classes' special methods are annotated (__eq__ takes an
# object, returns a bool). test_8420_set_merge's second half is test_8420_set_merge_dict_clear;
# its globals set2 and dict2 are annotated, and `be_bad` a global bool. test_merge_and_mutate's
# local X and set are module-level (its __eq__ clears the module's set), test_hash_collision_
# concurrent_add's X and Y too (Y, with the flag as a field, subclasses X so that s holds both),
# and it prints len(set() | s) of an annotated empty set. test_hash_inheritance's
# InheritedHashWithInequality subclasses FixedHash and defines OnlyInequality's __ne__ itself
# (no multiple inheritance), and hash(obj) == _default_hash(obj) is hash(obj) == hash(obj) (no
# object.__hash__). same_hash(a, b, ...) asserts hash(b) == hash(a) for each pair.
# EXCLUDED upstream cases:
# - same_hash() itself (a loop over a tuple of an int and floats, rejected: "cannot iterate
#   over tuple[int,int,float]: its items have different types", #503), complex numbers,
#   int(2**63) and int(-2**63) (64-bit ints: OverflowError, documented: -2**63 overflows as
#   2**63 is computed), test_coerced_floats
# - NoHash's `__hash__ = None` (rejected: "cannot infer the type of class attribute
#   '__hash__'; annotate it") and so test_error_hash's NoHash, test_hashable and
#   test_not_hashable (collections.abc.Hashable); test_set's HashCountingInt (int subclass),
#   test_subclass_with_custom_hash (set subclass), TestOperationsMutating (random hashes),
#   the other test_set tests (tests/programs/upstream/upstream_set_basic_ops.py and tests/programs/upstream/upstream_set_joint_ops.py
#   adopt set tests of int and str elements), HashBuiltinsTestCase and the hash randomization
#   tests (subprocesses)
def eq(got, expected) -> None:
    print(repr(got))
    assert got == expected, (got, expected)


class CustomHash:
    def __init__(self, hash: int) -> None:
        self.hash = hash
    def __hash__(self) -> int:
        return self.hash


class BadCmp:
    def __hash__(self) -> int:
        return 1
    def __eq__(self, other: object) -> bool:
        raise RuntimeError


def test_hash_collision_remove_add() -> None:
    n = 64
    elems = [CustomHash(h) for h in range(n)]
    # Elements with hash collision.
    a = CustomHash(n)
    b = CustomHash(n)
    elems += [a, b]
    s = set(elems)
    eq(len(s), len(elems))
    s.remove(a)
    # "a" has been replaced with a dummy.
    del elems[n]
    eq(len(s), len(elems))
    eq(s == set(elems), True)
    s.add(b)
    # "b" should not replace the dummy.
    eq(len(s), len(elems))
    eq(s == set(elems), True)


def test_badcmp() -> None:
    s = set([BadCmp()])
    try:
        set([BadCmp(), BadCmp()])
    except RuntimeError as e:
        print("RuntimeError", e)
    try:
        BadCmp() in s
    except RuntimeError as e:
        print("RuntimeError", e)
    try:
        s.add(BadCmp())
    except RuntimeError as e:
        print("RuntimeError", e)
    try:
        s.discard(BadCmp())
    except RuntimeError as e:
        print("RuntimeError", e)
    try:
        s.remove(BadCmp())
    except RuntimeError as e:
        print("RuntimeError", e)


def test_badcmp_frozenset() -> None:
    s = frozenset([BadCmp()])
    try:
        frozenset([BadCmp(), BadCmp()])
    except RuntimeError as e:
        print("RuntimeError", e)
    try:
        BadCmp() in s
    except RuntimeError as e:
        print("RuntimeError", e)


class bad_eq:
    def __eq__(self, other: object) -> bool:
        if be_bad:
            set2.clear()
            raise ZeroDivisionError
        return self is other
    def __hash__(self) -> int:
        return 0


be_bad = False
set2: set[bad_eq] = set()


def test_8420_set_merge() -> None:
    global be_bad, set2
    be_bad = False
    set1 = {bad_eq()}
    set2 = {bad_eq() for i in range(75)}
    be_bad = True
    try:
        set1.update(set2)
    except ZeroDivisionError as e:
        print("ZeroDivisionError", e)


class bad_dict_clear:
    def __eq__(self, other: object) -> bool:
        if be_bad:
            dict2.clear()
        return self is other
    def __hash__(self) -> int:
        return 0


dict2: dict[bad_dict_clear, None] = {}


def test_8420_set_merge_dict_clear() -> None:
    global be_bad, dict2
    be_bad = False
    set1 = {bad_dict_clear()}
    dict2 = {bad_dict_clear(): None}
    be_bad = True
    set1.symmetric_difference_update(dict2)
    print(len(set1))


class X:
    def __hash__(self) -> int:
        return hash(0)
    def __eq__(self, o: object) -> bool:
        other.clear()
        return False


other: set[X] = set()


def test_merge_and_mutate() -> None:
    global other
    other = {X() for i in range(10)}
    s = {X()}
    s.update(other)
    print("ok")


class X_2:
    def __hash__(self) -> int:
        return 0


class Y(X_2):
    def __init__(self) -> None:
        self.flag = False
    def __hash__(self) -> int:
        return 0
    def __eq__(self, other: object) -> bool:
        if not self.flag:
            self.flag = True
            s.add(X_2())
        return self is other


s: set[X_2] = set()


def test_hash_collision_concurrent_add() -> None:
    a = X_2()
    s.add(a)
    s.add(X_2())
    s.remove(a)
    s.add(Y())
    repr(s)
    list(s)
    e: set[X_2] = set()
    print(len(e | s))


_FIXED_HASH_VALUE = 42


class DefaultHash(object): pass


class FixedHash(object):
    def __hash__(self) -> int:
        return _FIXED_HASH_VALUE


class OnlyInequality(object):
    def __ne__(self, other: object) -> bool:
        return self is not other


class InheritedHashWithInequality(FixedHash):
    def __ne__(self, other: object) -> bool:
        return self is not other


def test_hash_inheritance() -> None:
    eq(hash(FixedHash()), _FIXED_HASH_VALUE)
    eq(hash(InheritedHashWithInequality()), _FIXED_HASH_VALUE)
    d = DefaultHash()
    eq(hash(d) == hash(d), True)
    o = OnlyInequality()
    eq(hash(o) == hash(o), True)


class OnlyEquality(object):
    def __eq__(self, other: object) -> bool:
        return self is other


def test_error_hash() -> None:
    try:
        hash(OnlyEquality())
    except TypeError as e:
        print("TypeError", e)


def test_numeric_literals() -> None:
    # same_hash(1, 1, 1.0), same_hash(0, 0.0), same_hash(-1, -1.0), same_hash(-2, -2.0)
    eq(hash(1) == hash(1), True)
    eq(hash(1.0) == hash(1), True)
    eq(hash(0.0) == hash(0), True)
    eq(hash(-1.0) == hash(-1), True)
    eq(hash(-2.0) == hash(-2), True)


def test_coerced_integers() -> None:
    eq(hash(int(1)) == hash(int(1)), True)
    eq(hash(float(1)) == hash(int(1)), True)
    eq(hash(int('1')) == hash(int(1)), True)
    eq(hash(float('1.0')) == hash(int(1)), True)
    eq(hash(float(-2**31)) == hash(int(-2**31)), True)
    eq(hash(float(1-2**31)) == hash(int(1-2**31)), True)
    eq(hash(float(2**31-1)) == hash(int(2**31-1)), True)
    eq(hash(float(2**31)) == hash(int(2**31)), True)


test_hash_collision_remove_add()
test_badcmp()
test_badcmp_frozenset()
test_8420_set_merge()
test_8420_set_merge_dict_clear()
test_merge_and_mutate()
test_hash_collision_concurrent_add()
test_hash_inheritance()
test_error_hash()
test_numeric_literals()
test_coerced_integers()
