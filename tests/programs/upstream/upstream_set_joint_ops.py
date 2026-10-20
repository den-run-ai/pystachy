# Adapted from CPython 3.13.16 Lib/test/test_set.py, commit cbc944f4bc59639a444dd971c737788ba2283a91:
# TestJointOps (run for set and frozenset, as TestSet and TestFrozenSet run it), and TestSet's and
# TestFrozenSet's own tests. PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and
# THIRD_PARTY_NOTICES.
#
# unittest scaffolding becomes assertions, with prints of the values compared. self.thetype becomes
# a template's parameter (make_set or make_frozenset), and each loop "for C in set, frozenset,
# dict.fromkeys, str, list, tuple" one call per C, of a template taking it. check_pass_thru(), a
# generator function, becomes a generator expression whose first item raises PassThru (and
# thetype(check_pass_thru()) set(...) or frozenset(...) of it).
# e.args[0] of a KeyError is compared as str(e), which is its repr.
#
# Excluded (each an error at compile time in Pystachy, where CPython raises TypeError at run time,
# or a feature the subset lacks):
# - C = tuple: tuple() of a str (a tuple of a length its type does not give);
# - assertRaises(TypeError, ...) of an unhashable element ([[]], []), of a set and a str under an
#   operator (s | 'abc'), and of thetype([], 2) and set().__init__(a=1) (test_new_or_init);
# - sets of frozensets and frozensets as elements (test_contains' last two lines, test_remove's and
#   test_discard's frozenset parts, test_remove_keyerror_set, test_setOfFrozensets,
#   test_set_membership): a set holds int, str or tuple elements;
# - test_remove_keyerror_unpacking's (1,) case: a tuple removed from a set of str;
# - type(u) == self.basetype: as isinstance(u, frozenset) == frozen;
# - test_init (s.__init__(...) of a set), test_hash (hash() of a set or frozenset),
#   test_set_literal_insertion_order ({1, 1.0, True}: elements of three types), test_pickling,
#   test_iterator_pickling, test_deepcopy, test_gc, test_weakref, test_subclass_with_custom_hash,
#   test_badcmp, test_cyclical_repr, test_do_not_rehash_dict_keys, test_container_iterator,
#   test_free_after_iterating, test_rich_compare, test_hash_collision_remove_add, the subclass
#   classes, and TestFrozenSet's test_frozen_as_dictkey, test_hash_caching and
#   test_hash_effectiveness: pickle, copy, gc, weakref, subclasses of set, user classes as
#   elements, hash() and frozenset keys are outside the subset.
# - test_intersection's "if self.thetype == frozenset()" compares a type with an empty frozenset,
#   which is never true: both types take its else branch, z is not s.

WORD = "simsalabim"
OTHERWORD = "madagascar"
LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


class PassThru(Exception):
    pass


def pass_thru(x: int) -> str:
    raise PassThru


def make_set(x: str) -> set[str]:
    return set(x)


def make_frozenset(x: str) -> frozenset[str]:
    return frozenset(x)


def c_set(x: str) -> set[str]:
    return set(x)


def c_frozenset(x: str) -> frozenset[str]:
    return frozenset(x)


def c_fromkeys(x: str) -> dict[str, int | None]:
    d: dict[str, int | None] = dict.fromkeys(x)
    return d


def c_str(x: str) -> str:
    return x


def c_list(x: str) -> list[str]:
    return list(x)


def word_dict() -> dict[str, int | None]:
    d: dict[str, int | None] = dict.fromkeys(WORD)
    return d


def test_uniquification(thetype, frozen: bool) -> None:
    s = thetype(WORD)
    actual = sorted(s)
    expected = sorted(word_dict())
    print("uniquification", actual)
    assert actual == expected
    try:
        if frozen:
            frozenset(pass_thru(x) for x in [0])
        else:
            set(pass_thru(x) for x in [0])
    except PassThru:
        print("PassThru from the iterable")
    else:
        assert False


def test_len(thetype) -> None:
    assert len(thetype(WORD)) == len(word_dict())
    print("len", len(thetype(WORD)))


def test_contains(thetype) -> None:
    s = thetype(WORD)
    d = word_dict()
    n = 0
    for c in LETTERS:
        assert (c in s) == (c in d)
        n += c in s
    print("contains", n)


def union_cases(thetype, C) -> None:
    assert thetype("abcba").union(C("cdc")) == set("abcd")
    assert thetype("abcba").union(C("efgfe")) == set("abcefg")
    assert thetype("abcba").union(C("ccb")) == set("abc")
    assert thetype("abcba").union(C("ef")) == set("abcef")
    assert thetype("abcba").union(C("ef"), C("fg")) == set("abcefg")
    print("union of", sorted(thetype("abcba").union(C("ef"), C("fg"))))


def test_union(thetype, frozen: bool) -> None:
    s = thetype(WORD)
    d = word_dict()
    u = s.union(OTHERWORD)
    for c in LETTERS:
        assert (c in u) == (c in d or c in OTHERWORD)
    assert s == thetype(WORD)
    assert isinstance(u, frozenset) == frozen
    try:
        s.union(pass_thru(x) for x in [0])
    except PassThru:
        print("PassThru from union")
    else:
        assert False
    union_cases(thetype, c_set)
    union_cases(thetype, c_frozenset)
    union_cases(thetype, c_fromkeys)
    union_cases(thetype, c_str)
    union_cases(thetype, c_list)
    # Issue #6573
    x = thetype("")
    assert x.union(set("1"), x, set("2")) == thetype("12")
    print("union", sorted(u), sorted(x.union(set("1"), x, set("2"))))


def test_or(thetype) -> None:
    s = thetype(WORD)
    i = s.union(OTHERWORD)
    assert s | set(OTHERWORD) == i
    assert s | frozenset(OTHERWORD) == i
    print("or", sorted(s | set(OTHERWORD)))


def intersection_cases(thetype, C) -> None:
    assert thetype("abcba").intersection(C("cdc")) == set("cc")
    assert thetype("abcba").intersection(C("efgfe")) == set("")
    assert thetype("abcba").intersection(C("ccb")) == set("bc")
    assert thetype("abcba").intersection(C("ef")) == set("")
    assert thetype("abcba").intersection(C("cbcf"), C("bag")) == set("b")
    print("intersection of", sorted(thetype("abcba").intersection(C("cbcf"), C("bag"))))


def test_intersection(thetype, frozen: bool) -> None:
    s = thetype(WORD)
    d = word_dict()
    i = s.intersection(OTHERWORD)
    for c in LETTERS:
        assert (c in i) == (c in d and c in OTHERWORD)
    assert s == thetype(WORD)
    assert isinstance(i, frozenset) == frozen
    try:
        s.intersection(pass_thru(x) for x in [0])
    except PassThru:
        print("PassThru from intersection")
    else:
        assert False
    intersection_cases(thetype, c_set)
    intersection_cases(thetype, c_frozenset)
    intersection_cases(thetype, c_fromkeys)
    intersection_cases(thetype, c_str)
    intersection_cases(thetype, c_list)
    s = thetype("abcba")
    z = s.intersection()
    assert z is not s
    assert z == s
    print("intersection", sorted(i), sorted(z))


def isdisjoint_f(s1, s2) -> bool:
    # 'Pure python equivalent of isdisjoint()'
    return not set(s1).intersection(s2)


def isdisjoint_cases(s1, C) -> int:
    n = 0
    for rarg in "", "a", "ab", "abc", "ababac", "cdc", "cc", "efgfe", "ccb", "ef":
        s2 = C(rarg)
        actual = s1.isdisjoint(s2)
        expected = isdisjoint_f(s1, s2)
        assert actual == expected
        assert isinstance(actual, bool)  # (upstream: actual is True or actual is False)
        n += actual
    return n


def test_isdisjoint(thetype) -> None:
    n = 0
    for larg in "", "a", "ab", "abc", "ababac", "cdc", "cc", "efgfe", "ccb", "ef":
        s1 = thetype(larg)
        n += isdisjoint_cases(s1, c_set)
        n += isdisjoint_cases(s1, c_frozenset)
        n += isdisjoint_cases(s1, c_fromkeys)
        n += isdisjoint_cases(s1, c_str)
        n += isdisjoint_cases(s1, c_list)
    print("isdisjoint", n)


def test_and(thetype) -> None:
    s = thetype(WORD)
    i = s.intersection(OTHERWORD)
    assert s & set(OTHERWORD) == i
    assert s & frozenset(OTHERWORD) == i
    print("and", sorted(i))


def difference_cases(thetype, C) -> None:
    assert thetype("abcba").difference(C("cdc")) == set("ab")
    assert thetype("abcba").difference(C("efgfe")) == set("abc")
    assert thetype("abcba").difference(C("ccb")) == set("a")
    assert thetype("abcba").difference(C("ef")) == set("abc")
    assert thetype("abcba").difference() == set("abc")
    assert thetype("abcba").difference(C("a"), C("b")) == set("c")
    print("difference of", sorted(thetype("abcba").difference(C("a"), C("b"))))


def test_difference(thetype, frozen: bool) -> None:
    s = thetype(WORD)
    d = word_dict()
    i = s.difference(OTHERWORD)
    for c in LETTERS:
        assert (c in i) == (c in d and c not in OTHERWORD)
    assert s == thetype(WORD)
    assert isinstance(i, frozenset) == frozen
    try:
        s.difference(pass_thru(x) for x in [0])
    except PassThru:
        print("PassThru from difference")
    else:
        assert False
    difference_cases(thetype, c_set)
    difference_cases(thetype, c_frozenset)
    difference_cases(thetype, c_fromkeys)
    difference_cases(thetype, c_str)
    difference_cases(thetype, c_list)
    print("difference", sorted(i))


def test_sub(thetype) -> None:
    s = thetype(WORD)
    i = s.difference(OTHERWORD)
    assert s - set(OTHERWORD) == i
    assert s - frozenset(OTHERWORD) == i
    print("sub", sorted(i))


def symmetric_difference_cases(thetype, C) -> None:
    assert thetype("abcba").symmetric_difference(C("cdc")) == set("abd")
    assert thetype("abcba").symmetric_difference(C("efgfe")) == set("abcefg")
    assert thetype("abcba").symmetric_difference(C("ccb")) == set("a")
    assert thetype("abcba").symmetric_difference(C("ef")) == set("abcef")
    print("symmetric_difference of", sorted(thetype("abcba").symmetric_difference(C("ef"))))


def test_symmetric_difference(thetype, frozen: bool) -> None:
    s = thetype(WORD)
    d = word_dict()
    i = s.symmetric_difference(OTHERWORD)
    for c in LETTERS:
        assert (c in i) == ((c in d) ^ (c in OTHERWORD))
    assert s == thetype(WORD)
    assert isinstance(i, frozenset) == frozen
    try:
        s.symmetric_difference(pass_thru(x) for x in [0])
    except PassThru:
        print("PassThru from symmetric_difference")
    else:
        assert False
    symmetric_difference_cases(thetype, c_set)
    symmetric_difference_cases(thetype, c_frozenset)
    symmetric_difference_cases(thetype, c_fromkeys)
    symmetric_difference_cases(thetype, c_str)
    symmetric_difference_cases(thetype, c_list)
    print("symmetric_difference", sorted(i))


def test_xor(thetype) -> None:
    s = thetype(WORD)
    i = s.symmetric_difference(OTHERWORD)
    assert s ^ set(OTHERWORD) == i
    assert s ^ frozenset(OTHERWORD) == i
    print("xor", sorted(i))


def test_equality(thetype) -> None:
    s = thetype(WORD)
    assert s == set(WORD)
    assert s == frozenset(WORD)
    assert s != set(OTHERWORD)
    assert s != frozenset(OTHERWORD)
    print("equality", s == set(WORD), s != frozenset(OTHERWORD))


def test_sub_and_super(thetype) -> None:
    p, q, r = thetype("ab"), thetype("abcde"), thetype("def")
    assert p < q
    assert p <= q
    assert q <= q
    assert q > p
    assert q >= p
    assert not q < r
    assert not q <= r
    assert not q > r
    assert not q >= r
    assert set("a").issubset("abc")
    assert set("abc").issuperset("a")
    assert not set("a").issubset("cbs")
    assert not set("cbs").issuperset("a")
    print("sub and super", p < q, q >= r)


def joint_ops(thetype, frozen: bool) -> None:
    print("--", "frozenset" if frozen else "set")
    test_uniquification(thetype, frozen)
    test_len(thetype)
    test_contains(thetype)
    test_union(thetype, frozen)
    test_or(thetype)
    test_intersection(thetype, frozen)
    test_isdisjoint(thetype)
    test_and(thetype)
    test_difference(thetype, frozen)
    test_sub(thetype)
    test_symmetric_difference(thetype, frozen)
    test_xor(thetype)
    test_equality(thetype)
    test_sub_and_super(thetype)


joint_ops(make_set, False)
joint_ops(make_frozenset, True)

# TestSet


def test_constructor_identity() -> None:
    s = set(range(3))
    t = set(s)
    assert s is not t
    print("constructor identity", s is t)


def test_set_literal() -> None:
    s = set([1, 2, 3])
    t = {1, 2, 3}
    assert s == t
    print("literal", s == t)


def test_set_literal_evaluation_order() -> None:
    # Expect left to right expression evaluation
    events: list[int] = []

    def record(obj: int) -> int:
        events.append(obj)
        return obj
    s = {record(1), record(2), record(3)}
    assert events == [1, 2, 3]
    print("evaluation order", events, len(s))


def test_clear() -> None:
    s = set(WORD)
    s.clear()
    assert s == set()
    assert len(s) == 0
    print("clear", len(s))


def test_copy() -> None:
    s = set(WORD)
    dup = s.copy()
    assert s == dup
    assert s is not dup
    assert isinstance(dup, set)
    print("copy", sorted(dup))


def test_add() -> None:
    s = set(WORD)
    s.add("Q")
    assert "Q" in s
    dup = s.copy()
    s.add("Q")
    assert s == dup
    print("add", sorted(s))


def test_remove() -> None:
    s = set(WORD)
    s.remove("a")
    assert "a" not in s
    try:
        s.remove("Q")
    except KeyError as e:
        print("KeyError", e)
    else:
        assert False
    print("remove", sorted(s))


def test_remove_keyerror_unpacking() -> None:
    # https://bugs.python.org/issue1576657
    s = set(WORD)
    for v1 in ["Q"]:
        try:
            s.remove(v1)
        except KeyError as e:
            v2 = str(e)
            assert repr(v1) == v2
            print("KeyError unpacking", v2)
        else:
            assert False


def test_discard() -> None:
    s = set(WORD)
    s.discard("a")
    assert "a" not in s
    s.discard("Q")
    print("discard", sorted(s))


def test_pop() -> None:
    s = set(WORD)
    for i in range(len(s)):
        elem = s.pop()
        assert elem not in s
    try:
        s.pop()
    except KeyError as e:
        print("KeyError", e)
    else:
        assert False


def update_cases(C) -> None:
    for p, q in (("cdc", "abcd"), ("efgfe", "abcefg"), ("ccb", "abc"), ("ef", "abcef")):
        s = set("abcba")
        assert s.update(C(p)) is None
        assert s == set(q)
    for p in ("cdc", "efgfe", "ccb", "ef", "abcda"):
        q = "ahi"
        s = set("abcba")
        assert s.update(C(p), C(q)) is None
        assert s == set(s) | set(p) | set(q)
    print("update of", sorted(s))


def test_update() -> None:
    s = set(WORD)
    retval = s.update(OTHERWORD)
    assert retval is None
    for c in (WORD + OTHERWORD):
        assert c in s
    try:
        s.update(pass_thru(x) for x in [0])
    except PassThru:
        print("PassThru from update")
    else:
        assert False
    update_cases(c_set)
    update_cases(c_frozenset)
    update_cases(c_fromkeys)
    update_cases(c_str)
    update_cases(c_list)
    print("update", sorted(s))


def test_ior() -> None:
    s = set(WORD)
    s |= set(OTHERWORD)
    for c in (WORD + OTHERWORD):
        assert c in s
    print("ior", sorted(s))


def intersection_update_cases(C) -> None:
    for p, q in (("cdc", "c"), ("efgfe", ""), ("ccb", "bc"), ("ef", "")):
        s = set("abcba")
        assert s.intersection_update(C(p)) is None
        assert s == set(q)
        ss = "abcba"
        s = set(ss)
        t = "cbc"
        assert s.intersection_update(C(p), C(t)) is None
        assert s == set("abcba") & set(p) & set(t)
    print("intersection_update of", sorted(s))


def test_intersection_update() -> None:
    s = set(WORD)
    retval = s.intersection_update(OTHERWORD)
    assert retval is None
    for c in (WORD + OTHERWORD):
        if c in OTHERWORD and c in WORD:
            assert c in s
        else:
            assert c not in s
    try:
        s.intersection_update(pass_thru(x) for x in [0])
    except PassThru:
        print("PassThru from intersection_update")
    else:
        assert False
    intersection_update_cases(c_set)
    intersection_update_cases(c_frozenset)
    intersection_update_cases(c_fromkeys)
    intersection_update_cases(c_str)
    intersection_update_cases(c_list)
    print("intersection_update", sorted(s))


def test_iand() -> None:
    s = set(WORD)
    s &= set(OTHERWORD)
    for c in (WORD + OTHERWORD):
        if c in OTHERWORD and c in WORD:
            assert c in s
        else:
            assert c not in s
    print("iand", sorted(s))


def difference_update_cases(C) -> None:
    for p, q in (("cdc", "ab"), ("efgfe", "abc"), ("ccb", "a"), ("ef", "abc")):
        s = set("abcba")
        assert s.difference_update(C(p)) is None
        assert s == set(q)

        s = set("abcdefghih")
        s.difference_update()
        assert s == set("abcdefghih")

        s = set("abcdefghih")
        s.difference_update(C("aba"))
        assert s == set("cdefghih")

        s = set("abcdefghih")
        s.difference_update(C("cdc"), C("aba"))
        assert s == set("efghih")
    print("difference_update of", sorted(s))


def test_difference_update() -> None:
    s = set(WORD)
    retval = s.difference_update(OTHERWORD)
    assert retval is None
    for c in (WORD + OTHERWORD):
        if c in WORD and c not in OTHERWORD:
            assert c in s
        else:
            assert c not in s
    try:
        s.difference_update(pass_thru(x) for x in [0])
    except PassThru:
        print("PassThru from difference_update")
    else:
        assert False
    difference_update_cases(c_set)
    difference_update_cases(c_frozenset)
    difference_update_cases(c_fromkeys)
    difference_update_cases(c_str)
    difference_update_cases(c_list)
    print("difference_update", sorted(s))


def test_isub() -> None:
    s = set(WORD)
    s -= set(OTHERWORD)
    for c in (WORD + OTHERWORD):
        if c in WORD and c not in OTHERWORD:
            assert c in s
        else:
            assert c not in s
    print("isub", sorted(s))


def symmetric_difference_update_cases(C) -> None:
    for p, q in (("cdc", "abd"), ("efgfe", "abcefg"), ("ccb", "a"), ("ef", "abcef")):
        s = set("abcba")
        assert s.symmetric_difference_update(C(p)) is None
        assert s == set(q)
    print("symmetric_difference_update of", sorted(s))


def test_symmetric_difference_update() -> None:
    s = set(WORD)
    retval = s.symmetric_difference_update(OTHERWORD)
    assert retval is None
    for c in (WORD + OTHERWORD):
        if (c in WORD) ^ (c in OTHERWORD):
            assert c in s
        else:
            assert c not in s
    try:
        s.symmetric_difference_update(pass_thru(x) for x in [0])
    except PassThru:
        print("PassThru from symmetric_difference_update")
    else:
        assert False
    symmetric_difference_update_cases(c_set)
    symmetric_difference_update_cases(c_frozenset)
    symmetric_difference_update_cases(c_fromkeys)
    symmetric_difference_update_cases(c_str)
    symmetric_difference_update_cases(c_list)
    print("symmetric_difference_update", sorted(s))


def test_ixor() -> None:
    s = set(WORD)
    s ^= set(OTHERWORD)
    for c in (WORD + OTHERWORD):
        if (c in WORD) ^ (c in OTHERWORD):
            assert c in s
        else:
            assert c not in s
    print("ixor", sorted(s))


def test_inplace_on_self() -> None:
    s = set(WORD)
    t = s.copy()
    t |= t
    assert t == s
    t &= t
    assert t == s
    t -= t
    assert t == set()
    t = s.copy()
    t ^= t
    assert t == set()
    print("inplace on self", len(t))


print("-- TestSet")
test_constructor_identity()
test_set_literal()
test_set_literal_evaluation_order()
test_clear()
test_copy()
test_add()
test_remove()
test_remove_keyerror_unpacking()
test_discard()
test_pop()
test_update()
test_ior()
test_intersection_update()
test_iand()
test_difference_update()
test_isub()
test_symmetric_difference_update()
test_ixor()
test_inplace_on_self()

# TestFrozenSet
print("-- TestFrozenSet")
fs = frozenset(WORD)
assert frozenset(fs) is fs  # test_constructor_identity
dup = fs.copy()  # test_copy
assert fs is dup
print("frozenset identity", frozenset(fs) is fs, fs.copy() is fs)
