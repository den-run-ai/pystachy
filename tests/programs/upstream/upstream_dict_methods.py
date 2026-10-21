# Adapted from CPython 3.13.16 Lib/test/test_dict.py, class DictTest: test_constructor,
# test_merge_operator, test_bool, test_keys, test_values, test_items, test_contains, test_len,
# test_getitem, test_clear, test_update, test_fromkeys, test_copy, test_copy_fuzz,
# test_copy_noncompact, test_get, test_setdefault, test_popitem, test_pop, test_repr, test_eq,
# test_tuple_keyerror, test_resize1, test_empty_presized_dict_in_freelist and
# test_hash_collision_remove_add, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b, assertFalse(x) asserts not x, assertRaises a try statement that prints the exception.
# An empty display and dict() that nothing types get an annotation; a variable has one type, so
# where upstream rebinds `d` to another type the new value has a name of its own. Test-local
# exception classes are module classes. test_popitem asserts each item and prints a line for each size. test_copy_fuzz's
# random sizes come from random.randrange(), seeded here so that they are the same on every run,
# and its new key is -1, an int as the dict's keys, where upstream adds 'key'.
# test_tuple_keyerror checks repr() of the KeyError, as its args are not supported.
# test_hash_collision_remove_add's CustomHash(h) keys are ints that hash to h in CPython (h, and
# h + 2**61 - 1 for the colliding pair), and its values are strs (str(h) where upstream has h),
# as a dict holds one value type.
# EXCLUDED upstream cases (see also tests/programs/upstream/upstream_dict_iteration.py):
# - test_invalid_keyword_arguments (`**` of a dict with an int key, dict subclasses),
#   test_literal_constructor (eval(), random strings), test_views_mapping (.mapping, subclasses)
# - test_merge_operator's a.__or__(...) and a.__ior__(...) (a dict's special methods are not
#   methods to call here)
# - test_keys', test_values' and test_items' repr(dict(a=1).keys()) and the like: keys(),
#   values() and items() are list snapshots here (a documented deviation: "['a']")
# - TypeErrors of calls with arguments that do not fit (d.keys(None), d.__contains__(),
#   d.__getitem__(), d.clear(None), d.copy(None), d.get(None, None, None), d.setdefault(),
#   d.pop(), d.update(None), dict.fromkeys(3)): compile-time errors here, with messages of their
#   own; test_get's d.get() with no argument crashes the compiler (bug: IndexError in bmethod()
#   instead of a file:line: error; #274)
# - keys that are objects with __hash__ or __eq__, which a dict holds with no other key type:
#   test_getitem's and test_pop's second parts, test_setdefault's BadHash,
#   test_setdefault_atomic, test_setitem_atomic_at_resize, test_mutating_lookup, test_eq's
#   BadCmp, test_bad_key and test_resize2 are in tests/programs/upstream/upstream_dict_object_keys.py;
#   test_merge_and_mutate, test_equal_operator_modifying_operand,
#   test_dictitems_contains_use_after_free and test_init_use_after_free are not (see there)
# - test_update's SimpleUserDict, FailingUserDict and badseq (update() of objects), and
#   update([(1, 2, 3)]) (a list of 3-tuples is rejected)
# - test_fromkeys' d.fromkeys(...) through an instance and of a generator, dict subclasses
#   (dictlike, mydict, baddict1-4), BadSeq (an iterator class)
# - test_get's and test_setdefault's d.setdefault('key0') without a default (rejected:
#   "missing argument for setdefault()"); test_pop's d.pop(k, 1), an int default for str values
#   (rejected: the result would be a str or an int)
# - test_repr's `d[1] = d` (a dict holding itself has no type), test_repr_deep (RecursionError)
# - test_missing (hasattr() of a type, dict subclasses), test_copy_maintains_tracking, test_track_*,
#   test_string_keys_can_track_values,
#   test_container_iterator, test_free_after_iterating, test_store_evilattr, test_clear_reentrant_*,
#   test_clear_at_lookup, test_overwrite_managed_dict, test_splittable_*,
#   test_instance_dict_getattr_str_subclass, test_object_set_item_single_instance_non_str_key,
#   test_update_shared_keys, test_split_table_*, test_str_nonstr, test_dict_contain_use_after_free,
#   test_fromkeys_operator_modifying_*, test_reentrant_insertion, test_dict_copy_order
#   (OrderedDict): gc, weakref, __del__, instance __dict__, str/int/dict subclasses
# - the *_pickling tests (pickle), CAPITest (_testinternalcapi), GeneralMappingTests and
#   SubclassMappingTests (Lib/test/mapping_tests.py: its reference dict holds strs and a tuple)
import random


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def test_constructor() -> None:
    # calling built-in types without argument must return empty
    new: dict[int, int] = dict()
    empty: dict[int, int] = {}
    check("dict()", new, empty)
    other: dict[int, int] = dict()
    check("dict() is not {}", other is not empty, True)


def test_merge_operator() -> None:

    a = {0: 0, 1: 1, 2: 1}
    b = {1: 1, 2: 2, 3: 3}

    c = a.copy()
    c |= b

    check("a | b", a | b, {0: 0, 1: 1, 2: 2, 3: 3})
    check("c", c, {0: 0, 1: 1, 2: 2, 3: 3})

    c = b.copy()
    c |= a

    check("b | a", b | a, {1: 1, 2: 1, 3: 3, 0: 0})
    check("c", c, {1: 1, 2: 1, 3: 3, 0: 0})

    c = a.copy()
    c |= [(1, 1), (2, 2), (3, 3)]

    check("c", c, {0: 0, 1: 1, 2: 2, 3: 3})


def test_bool() -> None:
    empty: dict[int, int] = {}
    check("not {}", not empty, True)
    check("bool({1: 2})", bool({1: 2}), True)
    check("bool({})", bool(empty), False)
    check("bool({1: 2})", bool({1: 2}), True)


def test_keys() -> None:
    d: dict[str, int] = {}
    check("set(d.keys())", set(d.keys()) == set(), True)
    d = {'a': 1, 'b': 2}
    k = d.keys()
    check("set(k)", set(k) == {'a', 'b'}, True)
    check("'a' in k", 'a' in k, True)
    check("'b' in k", 'b' in k, True)
    check("'a' in d", 'a' in d, True)
    check("'b' in d", 'b' in d, True)


def test_values() -> None:
    d: dict[int, int] = {}
    check("set(d.values())", set(d.values()) == set(), True)
    d = {1:2}
    check("set(d.values())", set(d.values()), {2})


def test_items() -> None:
    d: dict[int, int] = {}
    check("set(d.items())", set(d.items()) == set(), True)

    d = {1:2}
    check("set(d.items())", set(d.items()), {(1, 2)})


def test_contains() -> None:
    d: dict[str, int] = {}
    check("'a' not in d", 'a' not in d, True)
    check("'a' in d", 'a' in d, False)
    check("'a' not in d", 'a' not in d, True)
    d = {'a': 1, 'b': 2}
    check("'a' in d", 'a' in d, True)
    check("'b' in d", 'b' in d, True)
    check("'c' not in d", 'c' not in d, True)


def test_len() -> None:
    d: dict[str, int] = {}
    check("len(d)", len(d), 0)
    d = {'a': 1, 'b': 2}
    check("len(d)", len(d), 2)


def test_getitem() -> None:
    d = {'a': 1, 'b': 2}
    check("d['a']", d['a'], 1)
    check("d['b']", d['b'], 2)
    d['c'] = 3
    d['a'] = 4
    check("d['c']", d['c'], 3)
    check("d['a']", d['a'], 4)
    del d['b']
    check("d", d, {'a': 4, 'c': 3})


def test_clear() -> None:
    d = {1:1, 2:2, 3:3}
    d.clear()
    check("d.clear()", d == {}, True)


def test_update() -> None:
    d: dict[int, int] = {}
    d.update({1:100})
    d.update({2:20})
    d.update({1:1, 2:2, 3:3})
    check("d", d, {1:1, 2:2, 3:3})

    d.update()
    check("d", d, {1:1, 2:2, 3:3})


def test_fromkeys() -> None:
    fromkeys: dict[str, int | None] = dict.fromkeys('abc')
    nones: dict[str, int | None] = {'a':None, 'b':None, 'c':None}
    check("dict.fromkeys('abc')", fromkeys, nones)

    # test fast path for dictionary inputs
    res = dict(zip(list(range(6)), [0]*6))  # (range() in zip() is made a list here)
    d = dict(zip(list(range(6)), list(range(6))))
    check("dict.fromkeys(d, 0)", dict.fromkeys(d, 0), res)
    # test fast path for set inputs
    d_set = set(range(6))
    check("dict.fromkeys(set(range(6)), 0)", dict.fromkeys(d_set, 0), res)
    # test slow path for other iterable inputs
    d_list = list(range(6))
    check("dict.fromkeys(list(range(6)), 0)", dict.fromkeys(d_list, 0), res)


def test_copy() -> None:
    d = {1: 1, 2: 2, 3: 3}
    check("d.copy() is not d", d.copy() is not d, True)
    check("d.copy()", d.copy(), d)
    check("d.copy()", d.copy(), {1: 1, 2: 2, 3: 3})

    copy = d.copy()
    d[4] = 4
    check("copy != d", copy != d, True)

    empty: dict[int, int] = {}
    check("{}.copy()", empty.copy() == {}, True)


def test_copy_fuzz() -> None:
    random.seed(3)
    for dict_size in [10, 100, 1000, 10000, 100000]:
        dict_size = random.randrange(
            dict_size // 2, dict_size + dict_size // 2)
        # with self.subTest(dict_size=dict_size):
        d: dict[int, int] = {}
        for i in range(dict_size):
            d[i] = i

        d2 = d.copy()
        print("dict_size", dict_size, end=": ")
        check("d2 is not d", d2 is not d, True)
        check("d == d2", d == d2, True)
        d2[-1] = -1  # d2['key'] = 'value'
        check("d != d2", d != d2, True)
        check("len(d2) == len(d) + 1", len(d2), len(d) + 1)


def test_copy_noncompact() -> None:
    # Dicts don't compact themselves on del/pop operations.
    # Copy will use a slow merging strategy that produces
    # a compacted copy when roughly 33% of dict is a non-used
    # keys-space (to optimize memory footprint).
    # In this test we want to hit the slow/compacting
    # branch of dict.copy() and make sure it works OK.
    d = {k: k for k in range(1000)}
    for k in range(950):
        del d[k]
    d2 = d.copy()
    check("d2 == d", d2 == d, True)
    print(list(d2.items())[:3])


def test_popitem() -> None:
    # dict.popitem()
    for copymode in -1, +1:
        # -1: b has same structure as a
        # +1: b is a.copy()
        for log2size in range(12):
            size = 2**log2size
            a: dict[str, int] = {}
            b: dict[str, int] = {}
            for i in range(size):
                a[repr(i)] = i
                if copymode < 0:
                    b[repr(i)] = i
            if copymode > 0:
                b = a.copy()
            for i in range(size):
                ka, va = ta = a.popitem()
                assert va == int(ka)
                kb, vb = tb = b.popitem()
                assert vb == int(kb)
                assert not (copymode < 0 and ta != tb)
            assert not a
            assert not b
            print("popitem", copymode, size, ta, tb)

    d: dict[int, int] = {}
    try:
        d.popitem()
    except KeyError as e:
        print("KeyError", e)


def test_get() -> None:
    d: dict[str, int] = {}
    check("d.get('c') is None", d.get('c') is None, True)
    check("d.get('c', 3)", d.get('c', 3), 3)
    d = {'a': 1, 'b': 2}
    check("d.get('c') is None", d.get('c') is None, True)
    check("d.get('c', 3)", d.get('c', 3), 3)
    check("d.get('a')", d.get('a'), 1)
    check("d.get('a', 3)", d.get('a', 3), 1)


def test_setdefault() -> None:
    # dict.setdefault()
    d: dict[str, list[int]] = {}
    d.setdefault('key', []).append(3)
    check("d['key'][0]", d['key'][0], 3)
    d.setdefault('key', []).append(4)
    check("len(d['key'])", len(d['key']), 2)


def test_pop() -> None:
    # Tests for pop with specified key
    d: dict[str, str] = {}
    k, v = 'abc', 'def'
    d[k] = v
    try:
        d.pop('ghi')
    except KeyError as e:
        print("d.pop('ghi'): KeyError", e)
    else:
        assert False, "expected KeyError"

    check("d.pop(k)", d.pop(k), v)
    check("len(d)", len(d), 0)

    try:
        d.pop(k)
    except KeyError as e:
        print("d.pop(k): KeyError", e)
    else:
        assert False, "expected KeyError"

    check("d.pop(k, v)", d.pop(k, v), v)


class Exc(Exception): pass


class BadRepr(object):
    def __repr__(self) -> str:
        raise Exc()


def test_repr() -> None:
    d: dict[int, int] = {}
    check("repr(d)", repr(d), '{}')
    d[1] = 2
    check("repr(d)", repr(d), '{1: 2}')

    d2 = {1: BadRepr()}
    try:
        repr(d2)
    except Exc as e:
        print("repr({1: BadRepr()}):", type(e).__name__)
    else:
        assert False, "expected Exc"


def test_eq() -> None:
    empty: dict[int, int] = {}
    check("{} == {}", empty == {}, True)
    check("{1: 2} == {1: 2}", {1: 2} == {1: 2}, True)


def test_tuple_keyerror() -> None:
    # SF #1576657
    d: dict[tuple[int], int] = {}
    try:
        d[(1,)]
    except KeyError as c:
        check("repr(c.exception)", repr(c), "KeyError((1,))")  # c.exception.args == ((1,),)
    else:
        assert False, "expected KeyError"


def test_resize1() -> None:
    # Dict resizing bug, found by Jack Jansen in 2.2 CVS development.
    # This version got an assert failure in debug build, infinite loop in
    # release build.  Unfortunately, provoking this kind of stuff requires
    # a mix of inserts and deletes hitting exactly the right hash codes in
    # exactly the right order, and I can't think of a randomized approach
    # that would be *likely* to hit a failing case in reasonable time.

    d: dict[int, int] = {}
    for i in range(5):
        d[i] = i
    for i in range(5):
        del d[i]
    for i in range(5, 9):  # i==8 was the problem
        d[i] = i
    print("test_resize1", d)


def test_empty_presized_dict_in_freelist() -> None:
    # Bug #3537: if an empty but presized dict with a size larger
    # than 7 was in the freelist, it triggered an assertion failure
    try:
        d = {'a': 1 // 0, 'b': None, 'c': None, 'd': None, 'e': None,
             'f': None, 'g': None, 'h': None}
    except ZeroDivisionError as e:
        print("ZeroDivisionError:", e)
    else:
        assert False, "expected ZeroDivisionError"
    d2: dict[int, int] = {}
    print("test_empty_presized_dict_in_freelist", d2)


def test_hash_collision_remove_add() -> None:
    # There should be enough space, so all elements with unique hash
    # will be placed in corresponding cells without collision.
    n = 64
    items = [(h, str(h)) for h in range(n)]  # [(CustomHash(h), h) for h in range(n)]
    # Keys with hash collision.
    a = n               # CustomHash(n)
    b = n + 2**61 - 1   # CustomHash(n): hash(b) == n
    items += [(a, 'a'), (b, 'b')]
    d = dict(items)
    check("len(d)", len(d), len(items))
    del d[a]
    # "a" has been replaced with a dummy.
    del items[n]
    check("len(d)", len(d), len(items))
    check("d == dict(items)", d == dict(items), True)
    d[b] = 'c'
    # "b" should not replace the dummy.
    items[n] = (b, 'c')
    check("len(d)", len(d), len(items))
    check("d == dict(items)", d == dict(items), True)
    print(list(d.items())[-3:])


test_constructor()
test_merge_operator()
test_bool()
test_keys()
test_values()
test_items()
test_contains()
test_len()
test_getitem()
test_clear()
test_update()
test_fromkeys()
test_copy()
test_copy_fuzz()
test_copy_noncompact()
test_get()
test_setdefault()
test_popitem()
test_pop()
test_repr()
test_eq()
test_tuple_keyerror()
test_resize1()
test_empty_presized_dict_in_freelist()
test_hash_collision_remove_add()
