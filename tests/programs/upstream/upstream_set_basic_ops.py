# Adapted from CPython 3.13.16 Lib/test/test_set.py, commit cbc944f4bc59639a444dd971c737788ba2283a91:
# TestBasicOps (TestBasicOpsEmpty, TestBasicOpsSingleton, TestBasicOpsTuple, TestBasicOpsString),
# TestExceptionPropagation.test_changingSizeWhileIterating, TestBinaryOps, TestUpdateOps, TestMutate,
# TestSubsets (its five cases), TestOnlySetsInBinaryOps (TestOnlySetsDict, TestOnlySetsTuple and
# TestOnlySetsGenerator) and TestIdentities. PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt
# and THIRD_PARTY_NOTICES.
#
# unittest scaffolding becomes assertions, with prints of the values compared. A TestBasicOps case
# class becomes a call of the template basic_ops with its values; TestSubsets' eval("x" + case + "y")
# becomes compare(), and its cases tuples lists; TestOnlySetsInBinaryOps' calls of a method on an iterable print the result,
# which upstream does not check; the generator function of TestOnlySetsGenerator becomes a
# generator expression made for each call.
#
# Excluded:
# - TestBasicOpsTriple and TestBasicOpsMixedStringBytes (elements of several types), and
#   TestBasicOpsBytes (bytes): a set holds int, str or tuple elements of one type;
# - TestBasicOpsTuple.test_not_in (9 not in a set of tuples: an int and a tuple compared), and the
#   assertRaises(TypeError, ...) of TestOnlySetsInBinaryOps' operators and of its TestOnlySetsNumeric,
#   TestOnlySetsOperator and TestOnlySetsString cases (19 | s, s.update('abc') of a set of ints, ...),
#   and test_issue_37219 (set().difference(123)): errors at compile time in Pystachy, as is
#   TestOnlySetsInBinaryOps.test_eq_ne, a set compared with a dict, a tuple or a generator;
# - test_iteration's iter(s).__length_hint__(), test_pickling, TestExceptionPropagation's baditer
#   and gooditer (classes with __next__), TestSetOfSets and TestGraphs (frozensets as elements),
#   TestCopying (copy.copy, copy.deepcopy), TestVariousIteratorArgs (iterator classes with
#   __next__ and __getitem__ sequences), TestWeirdBugs and TestMethodsMutating /
#   TestBinaryOpsMutating (user classes as elements, iter()): outside the subset.
from typing import Iterator


def basic_ops(case: str, values, empty, rep: str) -> None:
    # TestBasicOps, for self.set = set(values), self.dup = set(values), empty_set = empty
    print("--", case)
    s = set(values)
    dup = set(values)
    if rep != "":
        assert repr(s) == rep  # test_repr
    else:
        # check_repr_against_values
        text = repr(s)
        assert text.startswith("{")
        assert text.endswith("}")
        result = text[1:-1].split(", ")
        result.sort()
        sorted_repr_values = [repr(value) for value in values]
        sorted_repr_values.sort()
        assert result == sorted_repr_values
    assert len(s) == len(values)  # test_length
    assert s == s  # test_self_equality
    assert s == dup  # test_equivalent_equality
    assert s.copy() == dup  # test_copy
    assert s | s == dup  # test_self_union
    assert s | empty == dup  # test_empty_union
    assert empty | s == dup  # test_union_empty
    assert s & s == dup  # test_self_intersection
    assert s & empty == empty  # test_empty_intersection
    assert empty & s == empty  # test_intersection_empty
    assert s.isdisjoint(s) == (not s)  # test_self_isdisjoint
    assert s.isdisjoint(empty)  # test_empty_isdisjoint
    assert empty.isdisjoint(s)  # test_isdisjoint_empty
    assert s ^ s == empty  # test_self_symmetric_difference
    assert s ^ empty == s  # test_empty_symmetric_difference
    assert s - s == empty  # test_self_difference
    assert s - empty == dup  # test_empty_difference
    assert empty - s == empty  # test_empty_difference_rev
    for v in s:  # test_iteration
        assert v in values
    # (a set of strs prints in the order of their hashes, which CPython varies from run to run)
    print(repr(s) if rep != "" else str(sorted(s)), len(s), s.isdisjoint(s), sorted(s ^ empty))


e: list[int] = []
basic_ops("empty set", e, set(e), "set()")
basic_ops("unit set (number)", [3], set(e), "{3}")
assert 3 in set([3])  # TestBasicOpsSingleton.test_in
assert 2 not in set([3])  # test_not_in
et: list[tuple[int, str]] = []
basic_ops("unit set (tuple)", [(0, "zero")], set(et), "{(0, 'zero')}")
assert (0, "zero") in set([(0, "zero")])  # TestBasicOpsTuple.test_in
es: list[str] = []
basic_ops("string set", ["a", "b", "c"], set(es), "")

# TestExceptionPropagation.test_changingSizeWhileIterating
s = set([1, 2, 3])
try:
    for i in s:
        s.update([4])
except RuntimeError as err:
    print("RuntimeError:", err)
else:
    assert False, "no exception when changing size during iteration"

# TestBinaryOps
print("-- TestBinaryOps")
bs = set((2, 4, 6))
assert bs == set({2: 1, 4: 3, 6: 5})  # test_eq, SF bug 643115
assert bs | set([2]) == set((2, 4, 6))  # test_union_subset
assert bs | set([2, 4, 6, 8]) == set([2, 4, 6, 8])  # test_union_superset
assert bs | set([3, 4, 5]) == set([2, 3, 4, 5, 6])  # test_union_overlap
assert bs | set([8]) == set([2, 4, 6, 8])  # test_union_non_overlap
assert bs & set((2, 4)) == set((2, 4))  # test_intersection_subset
assert bs & set([2, 4, 6, 8]) == set([2, 4, 6])  # test_intersection_superset
assert bs & set([3, 4, 5]) == set([4])  # test_intersection_overlap
assert bs & set([8]) == set()  # test_intersection_non_overlap
assert not bs.isdisjoint(set((2, 4)))  # test_isdisjoint_subset
assert not bs.isdisjoint(set([2, 4, 6, 8]))  # test_isdisjoint_superset
assert not bs.isdisjoint(set([3, 4, 5]))  # test_isdisjoint_overlap
assert bs.isdisjoint(set([8]))  # test_isdisjoint_non_overlap
assert bs ^ set((2, 4)) == set([6])  # test_sym_difference_subset
assert bs ^ set((2, 4, 6, 8)) == set([8])  # test_sym_difference_superset
assert bs ^ set((3, 4, 5)) == set([2, 3, 5, 6])  # test_sym_difference_overlap
assert bs ^ set([8]) == set([2, 4, 6, 8])  # test_sym_difference_non_overlap
print(sorted(bs ^ set((3, 4, 5))), bs.isdisjoint(set([8])))

# TestUpdateOps
print("-- TestUpdateOps")


def fresh() -> set[int]:
    return set((2, 4, 6))


u = fresh()
u |= set([2])  # test_union_subset
assert u == set((2, 4, 6))
u = fresh()
u |= set([2, 4, 6, 8])  # test_union_superset
assert u == set([2, 4, 6, 8])
u = fresh()
u |= set([3, 4, 5])  # test_union_overlap
assert u == set([2, 3, 4, 5, 6])
u = fresh()
u |= set([8])  # test_union_non_overlap
assert u == set([2, 4, 6, 8])
u = fresh()
u.update(set([3, 4, 5]))  # test_union_method_call
assert u == set([2, 3, 4, 5, 6])
u = fresh()
u &= set((2, 4))  # test_intersection_subset
assert u == set((2, 4))
u = fresh()
u &= set([2, 4, 6, 8])  # test_intersection_superset
assert u == set([2, 4, 6])
u = fresh()
u &= set([3, 4, 5])  # test_intersection_overlap
assert u == set([4])
u = fresh()
u &= set([8])  # test_intersection_non_overlap
assert u == set()
u = fresh()
u.intersection_update(set([3, 4, 5]))  # test_intersection_method_call
assert u == set([4])
u = fresh()
u ^= set((2, 4))  # test_sym_difference_subset
assert u == set([6])
u = fresh()
u ^= set((2, 4, 6, 8))  # test_sym_difference_superset
assert u == set([8])
u = fresh()
u ^= set((3, 4, 5))  # test_sym_difference_overlap
assert u == set([2, 3, 5, 6])
u = fresh()
u ^= set([8])  # test_sym_difference_non_overlap
assert u == set([2, 4, 6, 8])
u = fresh()
u.symmetric_difference_update(set([3, 4, 5]))  # test_sym_difference_method_call
assert u == set([2, 3, 5, 6])
u = fresh()
u -= set((2, 4))  # test_difference_subset
assert u == set([6])
u = fresh()
u -= set((2, 4, 6, 8))  # test_difference_superset
assert u == set([])
u = fresh()
u -= set((3, 4, 5))  # test_difference_overlap
assert u == set([2, 6])
u = fresh()
u -= set([8])  # test_difference_non_overlap
assert u == set([2, 4, 6])
u = fresh()
u.difference_update(set([3, 4, 5]))  # test_difference_method_call
assert u == set([2, 6])
print(sorted(u))

# TestMutate
print("-- TestMutate")
VALUES = ["a", "b", "c"]
m = set(VALUES)
m.add("c")  # test_add_present
assert m == set("abc")
m = set(VALUES)
m.add("d")  # test_add_absent
assert m == set("abcd")
tmp: set[str] = set()  # test_add_until_full
expected_len = 0
for v in VALUES:
    tmp.add(v)
    expected_len += 1
    assert len(tmp) == expected_len
assert tmp == set(VALUES)
m = set(VALUES)
m.remove("b")  # test_remove_present
assert m == set("ac")
m = set(VALUES)
try:  # test_remove_absent
    m.remove("d")
    assert False, "Removing missing element should have raised LookupError"
except LookupError as err:
    print("LookupError:", err)
m = set(VALUES)
expected_len = len(m)  # test_remove_until_empty
for v in VALUES:
    m.remove(v)
    expected_len -= 1
    assert len(m) == expected_len
m = set(VALUES)
m.discard("c")  # test_discard_present
assert m == set("ab")
m = set(VALUES)
m.discard("d")  # test_discard_absent
assert m == set("abc")
m = set(VALUES)
m.clear()  # test_clear
assert len(m) == 0
m = set(VALUES)
popped: dict[str, int | None] = {}  # test_pop
while m:
    popped[m.pop()] = None
assert len(popped) == len(VALUES)
for v in VALUES:
    assert v in popped
m = set(VALUES)
m.update(())  # test_update_empty_tuple
assert m == set(VALUES)
m = set(VALUES)
m.update(("a",))  # test_update_unit_tuple_overlap
assert m == set(VALUES)
m = set(VALUES)
m.update(("a", "z"))  # test_update_unit_tuple_non_overlap
assert m == set(VALUES + ["z"])
print(sorted(m), sorted(popped))

# TestSubsets
print("-- TestSubsets")
REVERSE = {"==": "==", "!=": "!=", "<": ">", ">": "<", "<=": ">=", ">=": "<="}


def compare(x: set[int], case: str, y: set[int]) -> bool:
    # eval("x" + case + "y")
    if case == "==":
        return x == y
    if case == "!=":
        return x != y
    if case == "<":
        return x < y
    if case == "<=":
        return x <= y
    if case == ">":
        return x > y
    return x >= y


def method(x: set[int], case: str, y: set[int]) -> bool:
    # getattr(x, case2method[case])(y)
    return x.issubset(y) if case == "<=" else x.issuperset(y)


def test_issubset(name: str, x: set[int], y: set[int], cases: list[str]) -> None:
    got: list[str] = []
    for case in "!=", "==", "<", "<=", ">", ">=":
        expected = case in cases
        # Test the binary infix spelling.
        result = compare(x, case, y)
        assert result == expected
        # Test the "friendly" method-name spelling, if one exists.
        if case == "<=" or case == ">=":
            result = method(x, case, y)
            assert result == expected
        # Now do the same for the operands reversed.
        rcase = REVERSE[case]
        result = compare(y, rcase, x)
        assert result == expected
        if rcase == "<=" or rcase == ">=":
            result = method(y, rcase, x)
            assert result == expected
        if result:
            got.append(case)
    print(name, got)


none: set[int] = set()
test_issubset("both empty", set(none), set(none), ["==", "<=", ">="])
test_issubset("equal pair", set([1, 2]), set([1, 2]), ["==", "<=", ">="])
test_issubset("one empty, one non-empty", set(none), set([1, 2]), ["!=", "<", "<="])
test_issubset("one a non-empty proper subset of other", set([1]), set([1, 2]), ["!=", "<", "<="])
test_issubset("neither empty, neither contains", set([1]), set([2]), ["!="])

# TestOnlySetsInBinaryOps, for the iterables: TestOnlySetsDict, TestOnlySetsTuple, TestOnlySetsGenerator


def only_sets(name: str, other) -> None:
    print("--", name)
    s = set((1, 2, 3))
    s.update(other)  # test_update
    print("update", sorted(s))
    print("union", sorted(set((1, 2, 3)).union(other)))  # test_union
    s = set((1, 2, 3))
    s.intersection_update(other)  # test_intersection_update
    print("intersection_update", sorted(s))
    print("intersection", sorted(set((1, 2, 3)).intersection(other)))  # test_intersection
    s = set((1, 2, 3))
    s.symmetric_difference_update(other)  # test_sym_difference_update
    print("symmetric_difference_update", sorted(s))
    print("symmetric_difference", sorted(set((1, 2, 3)).symmetric_difference(other)))  # test_sym_difference
    s = set((1, 2, 3))
    s.difference_update(other)  # test_difference_update
    print("difference_update", sorted(s))
    print("difference", sorted(set((1, 2, 3)).difference(other)))  # test_difference


only_sets("TestOnlySetsDict", {1: 2, 3: 4})
only_sets("TestOnlySetsTuple", (2, 4, 6))
print("-- TestOnlySetsGenerator")
g = set((1, 2, 3))
g.update(i for i in range(0, 10, 2))
print("update", sorted(g))
print("union", sorted(set((1, 2, 3)).union(i for i in range(0, 10, 2))))
g = set((1, 2, 3))
g.intersection_update(i for i in range(0, 10, 2))
print("intersection_update", sorted(g))
print("intersection", sorted(set((1, 2, 3)).intersection(i for i in range(0, 10, 2))))
g = set((1, 2, 3))
g.symmetric_difference_update(i for i in range(0, 10, 2))
print("symmetric_difference_update", sorted(g))
print("symmetric_difference", sorted(set((1, 2, 3)).symmetric_difference(i for i in range(0, 10, 2))))
g = set((1, 2, 3))
g.difference_update(i for i in range(0, 10, 2))
print("difference_update", sorted(g))
print("difference", sorted(set((1, 2, 3)).difference(i for i in range(0, 10, 2))))

# TestIdentities
print("-- TestIdentities")
a = set("abracadabra")
b = set("alacazam")
assert a - b < a  # test_binopsVsSubsets
assert b - a < b
assert a & b < a
assert a & b < b
assert a | b > a
assert a | b > b
assert a ^ b < a | b
assert a & b == b & a  # test_commutativity
assert a | b == b | a
assert a ^ b == b ^ a
if a != b:
    assert a - b != b - a
# check that sums of parts equal the whole (test_summations)
assert (a - b) | (a & b) | (b - a) == a | b
assert (a & b) | (a ^ b) == a | b
assert a | (b - a) == a | b
assert (a - b) | b == a | b
assert (a - b) | (a & b) == a
assert (b - a) | (a & b) == b
assert (a - b) | (b - a) == a ^ b
# check that inverse operations show non-overlap (test_exclusion)
zero: set[str] = set()
assert (a - b) & b == zero
assert (b - a) & a == zero
assert (a & b) & (a ^ b) == zero
print(sorted(a - b), sorted(a & b), sorted(a ^ b))


class Evens:
    # (not upstream: an iterable object as TestOnlySets' other)
    def __iter__(self) -> Iterator[int]:
        return iter([0, 2, 4])


only_sets("an object with __iter__", Evens())
