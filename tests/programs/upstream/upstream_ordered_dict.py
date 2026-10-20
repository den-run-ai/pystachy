# Adapted from CPython 3.13.16 Lib/test/test_ordered_dict.py, class OrderedDictTests (run by
# CPythonOrderedDictTests, collections.OrderedDict): test_init, test_update, test_fromkeys,
# test_clear, test_delitem, test_setitem, test_iterators, test_sorted_iterators,
# test_iterators_empty, test_popitem, test_popitem_last, test_pop, test_equality, test_repr,
# test_setdefault, test_reinsert, test_move_to_end, test_move_to_end_issue25406 and
# test_merge_operator, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) and assertTrue(x)
# print and assert, assertRaises a try statement that prints the exception. An empty
# OrderedDict() or list that nothing types is annotated; fromkeys() of None values (rejected:
# "OrderedDict() cannot bind its type variables from the argument for 'other', a
# list[tuple[str,None]] ...", reported in lib/collections/__init__.py) has the value 0 where
# only the keys matter (test_detect_deletion_during_iteration aside, test_move_to_end*), and
# test_fromkeys' None values are left out; dict(od) is {k: v for k, v in od.items()}.
# EXCLUDED upstream cases:
# - keyword arguments to OrderedDict() and update() of ** of a dict (rejected:
#   "OrderedDict.__init__() got an unexpected keyword argument 'c'", "** of a dict[str,int] is
#   not supported", #516): test_init's kwds and mixed input and its d.__init__([...], g=7, d=4)
#   (without its keywords, a bug: calling __init__ of an existing OrderedDict empties it here,
#   where CPython's keeps its items), OrderedDict(self=42) & co, test_468,
#   test_update's **dict(pairs), test_pop's Missing(a=1); the TypeErrors of calls that do not fit
# - dict.__eq__ and dict.__or__ with an OrderedDict on the right (rejected: "cannot compare
#   dict[int,int] == collections.OrderedDict-1", "unsupported operand type(s) for |: 'dict' and
#   'OrderedDict'"): test_equality's dict(od2) == od1, test_merge_operator's dict(b) | a and
#   type(dict(a) | b); its type(a | b) is OrderedDict (rejected: "unsupported call
#   type(collections.OrderedDict-1)"), `|=` of a list, (), "" and the TypeErrors
# - test_detect_deletion_during_iteration: next() of an iterator over a changed OrderedDict
#   goes on, where CPython raises RuntimeError (documented: iteration is a snapshot)
# - test_init_calls, test_overridden_init, test_abc, test_copying, test_yaml_linkage,
#   test_reduce_not_too_fat, test_pickle_recursive, test_repr_recursive*, test_setdefault's
#   Missing subclass and setdefault() keyword, test_views, test_override_update,
#   test_highly_nested*, test_delitem_hash_collision, test_issue24347/8, test_issue24667,
#   test_dict_* (dict's methods called on an OrderedDict), test_reference_loop,
#   test_free_after_iterating, test_sizeof, the PurePython, subclass, slots and mapping_tests
#   variants
from collections import OrderedDict
from random import shuffle, seed

# (upstream's shuffles are the unseeded module function's)
seed(5)


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def test_init() -> None:
    pairs = [('a', 1), ('b', 2), ('c', 3), ('d', 4), ('e', 5)]
    check("dict input", sorted(OrderedDict(dict(pairs)).items()), pairs)
    check("pairs input", list(OrderedDict(pairs).items()), pairs)


def test_update() -> None:
    pairs = [('a', 1), ('b', 2), ('c', 3), ('d', 4), ('e', 5)]
    od: OrderedDict[str, int] = OrderedDict()
    od.update(dict(pairs))
    check("dict input", sorted(od.items()), pairs)
    od = OrderedDict()
    od.update(pairs)
    check("pairs input", list(od.items()), pairs)
    od = OrderedDict()
    od.update([('a', 1), ('b', 2), ('c', 9), ('d', 4)], c=3, e=5)
    check("mixed input", list(od.items()), pairs)
    od = OrderedDict()
    od.update(self=23)
    check("self", list(od.items()), [('self', 23)])
    od = OrderedDict()
    od.update(red=5, blue=6, other=7, self=8)
    check("kw", sorted(list(od.items())),
                     [('blue', 6), ('other', 7), ('red', 5), ('self', 8)])
    d = OrderedDict([('a', 1), ('b', 2), ('c', 3), ('d', 44), ('e', 55)])
    d.update([('e', 5), ('f', 6)], g=7, d=4)
    check("d", list(d.items()),
        [('a', 1), ('b', 2), ('c', 3), ('d', 4), ('e', 5), ('f', 6), ('g', 7)])


def test_fromkeys() -> None:
    od = OrderedDict.fromkeys('abc', value=0)
    check("od", list(od.items()), [(c, 0) for c in 'abc'])
    od2 = OrderedDict.fromkeys('abc', 0)
    check("od", list(od2.items()), [(c, 0) for c in 'abc'])


def test_clear() -> None:
    pairs = [('c', 1), ('b', 2), ('a', 3), ('d', 4), ('e', 5), ('f', 6)]
    shuffle(pairs)
    od = OrderedDict(pairs)
    check("len", len(od), len(pairs))
    od.clear()
    check("len", len(od), 0)


def test_delitem() -> None:
    pairs = [('c', 1), ('b', 2), ('a', 3), ('d', 4), ('e', 5), ('f', 6)]
    od = OrderedDict(pairs)
    del od['a']
    check("not in", 'a' in od, False)
    try:
        del od['a']
    except KeyError as e:
        print("KeyError", e)
    check("items", list(od.items()), pairs[:2] + pairs[3:])


def test_setitem() -> None:
    od = OrderedDict([('d', 1), ('b', 2), ('c', 3), ('a', 4), ('e', 5)])
    od['c'] = 10           # existing element
    od['f'] = 20           # new element
    check("items", list(od.items()),
                     [('d', 1), ('b', 2), ('c', 10), ('a', 4), ('e', 5), ('f', 20)])


def test_iterators() -> None:
    pairs = [('c', 1), ('b', 2), ('a', 3), ('d', 4), ('e', 5), ('f', 6)]
    shuffle(pairs)
    od = OrderedDict(pairs)
    check("list", list(od), [t[0] for t in pairs])
    check("keys", list(od.keys()), [t[0] for t in pairs])
    check("values", list(od.values()), [t[1] for t in pairs])
    check("items", list(od.items()), pairs)
    check("reversed", list(reversed(od)),
                     [t[0] for t in reversed(pairs)])
    check("reversed keys", list(reversed(od.keys())),
                     [t[0] for t in reversed(pairs)])
    check("reversed values", list(reversed(od.values())),
                     [t[1] for t in reversed(pairs)])
    check("reversed items", list(reversed(od.items())), list(reversed(pairs)))


def test_sorted_iterators() -> None:
    pairs = [('a', 1), ('b', 2), ('c', 3), ('d', 4), ('e', 5)]
    od = OrderedDict(pairs)
    check("sorted", sorted(od), [t[0] for t in pairs])
    check("keys", sorted(od.keys()), [t[0] for t in pairs])
    check("values", sorted(od.values()), [t[1] for t in pairs])
    check("items", sorted(od.items()), pairs)
    check("reversed", sorted(reversed(od)),
                     sorted([t[0] for t in reversed(pairs)]))


def test_iterators_empty() -> None:
    od: OrderedDict[str, int] = OrderedDict()
    empty: list[str] = []
    check("list", list(od), empty)
    check("keys", list(od.keys()), empty)
    check("reversed", list(reversed(od)), empty)
    check("reversed keys", list(reversed(od.keys())), empty)
    ev: list[int] = []
    check("values", list(od.values()), ev)
    check("reversed values", list(reversed(od.values())), ev)
    ei: list[tuple[str, int]] = []
    check("items", list(od.items()), ei)
    check("reversed items", list(reversed(od.items())), ei)


def test_popitem() -> None:
    pairs = [('c', 1), ('b', 2), ('a', 3), ('d', 4), ('e', 5), ('f', 6)]
    shuffle(pairs)
    od = OrderedDict(pairs)
    while pairs:
        check("popitem", od.popitem(), pairs.pop())
    try:
        od.popitem()
    except KeyError as e:
        print("KeyError", e)
    check("len", len(od), 0)


def test_popitem_last() -> None:
    pairs = [(i, i) for i in range(30)]
    obj = OrderedDict(pairs)
    for i in range(8):
        obj.popitem(True)
    obj.popitem(True)
    obj.popitem(last=True)
    check("len", len(obj), 20)


def test_pop() -> None:
    pairs = [('c', 1), ('b', 2), ('a', 3), ('d', 4), ('e', 5), ('f', 6)]
    shuffle(pairs)
    od = OrderedDict(pairs)
    shuffle(pairs)
    k = ''
    while pairs:
        k, v = pairs.pop()
        check("pop", od.pop(k), v)
    try:
        od.pop('xyz')
    except KeyError as e:
        print("KeyError", e)
    check("len", len(od), 0)
    check("pop default", od.pop(k, 12345), 12345)


def test_equality() -> None:
    pairs = [('c', 1), ('b', 2), ('a', 3), ('d', 4), ('e', 5), ('f', 6)]
    shuffle(pairs)
    od1 = OrderedDict(pairs)
    od2 = OrderedDict(pairs)
    check("==", od1 == od2, True)
    pairs = pairs[2:] + pairs[:2]
    od2 = OrderedDict(pairs)
    check("!=", od1 != od2, True)
    check("== dict", od1 == {k: v for k, v in od2.items()}, True)
    check("!= shorter", od1 != OrderedDict(pairs[:-1]), True)


def test_repr() -> None:
    od = OrderedDict([('c', 1), ('b', 2), ('a', 3), ('d', 4), ('e', 5), ('f', 6)])
    check("repr", repr(od),
        "OrderedDict({'c': 1, 'b': 2, 'a': 3, 'd': 4, 'e': 5, 'f': 6})")
    e: OrderedDict[str, int] = OrderedDict()
    check("repr", repr(e), "OrderedDict()")


def test_setdefault() -> None:
    pairs = [('c', 1), ('b', 2), ('a', 3), ('d', 4), ('e', 5), ('f', 6)]
    shuffle(pairs)
    od = OrderedDict(pairs)
    pair_order = list(od.items())
    check("a", od.setdefault('a', 10), 3)
    check("order", list(od.items()), pair_order)
    check("x", od.setdefault('x', 10), 10)
    check("last", list(od.items())[-1], ('x', 10))
    check("g", od.setdefault('g', default=9), 9)


def test_reinsert() -> None:
    od: OrderedDict[str, int] = OrderedDict()
    od['a'] = 1
    od['b'] = 2
    del od['a']
    check("items", list(od.items()), [('b', 2)])
    od['a'] = 1
    check("items", list(od.items()), [('b', 2), ('a', 1)])


def test_move_to_end() -> None:
    od = OrderedDict.fromkeys('abcde', 0)
    check("od", list(od), list('abcde'))
    od.move_to_end('c')
    check("od", list(od), list('abdec'))
    od.move_to_end('c', False)
    check("od", list(od), list('cabde'))
    od.move_to_end('c', False)
    check("od", list(od), list('cabde'))
    od.move_to_end('e')
    check("od", list(od), list('cabde'))
    od.move_to_end('b', last=False)
    check("od", list(od), list('bcade'))
    try:
        od.move_to_end('x')
    except KeyError as e:
        print("KeyError", e)
    try:
        od.move_to_end('x', False)
    except KeyError as e:
        print("KeyError", e)


def test_move_to_end_issue25406() -> None:
    od = OrderedDict.fromkeys('abc', 0)
    od.move_to_end('c', last=False)
    check("od", list(od), list('cab'))
    od.move_to_end('a', last=False)
    check("od", list(od), list('acb'))

    od = OrderedDict.fromkeys('abc', 0)
    od.move_to_end('a')
    check("od", list(od), list('bca'))
    od.move_to_end('c')
    check("od", list(od), list('bac'))


def test_merge_operator() -> None:
    a = OrderedDict({0: 0, 1: 1, 2: 1})
    b = OrderedDict({1: 1, 2: 2, 3: 3})

    c = a.copy()
    d = a.copy()
    c |= b
    d |= list(b.items())
    expected = OrderedDict({0: 0, 1: 1, 2: 2, 3: 3})
    check("a | dict(b)", a | {k: v for k, v in b.items()}, expected)
    check("a | b", a | b, expected)
    check("c", c, expected)
    check("d", d, expected)

    c = b.copy()
    c |= a
    expected = OrderedDict({1: 1, 2: 1, 3: 3, 0: 0})

    check("b | a", b | a, expected)
    check("c", c, expected)


test_init()
test_update()
test_fromkeys()
test_clear()
test_delitem()
test_setitem()
test_iterators()
test_sorted_iterators()
test_iterators_empty()
test_popitem()
test_popitem_last()
test_pop()
test_equality()
test_repr()
test_setdefault()
test_reinsert()
test_move_to_end()
test_move_to_end_issue25406()
test_merge_operator()
