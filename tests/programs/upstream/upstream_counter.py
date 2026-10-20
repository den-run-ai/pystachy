# Adapted from CPython 3.13.16 Lib/test/test_collections.py, class TestCounter: test_basics,
# test_total, test_order_preservation, test_update, test_copying, test_conversions,
# test_invariant_for_the_in_operator, test_multiset_operations, test_inplace_operations,
# test_subtract, test_unary, test_helper_function, test_eq, test_le, test_lt, test_ge and
# test_gt, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) and assertTrue(x)
# print and assert; loops over random multisets assert without printing. Counter(a=3, b=2, c=1)
# and dict(a=3, ...) (keyword constructors, rejected: "Counter.__init__() got an unexpected
# keyword argument 'a'", #516) are displays, Counter({'a': 3, ...}); dict(c) of a Counter
# (rejected: "dict() of an object ('Counter') is not supported") is compared with the dict as
# it is (c == {...}); dict((elem, n) for ...) is dict([...]) of a list comprehension. Where
# upstream compares counters with ==, test_comparisons asserts each of test_eq to test_gt;
# test_inplace_operations compares `c += q` (and -=, |=, &=) with `c + q`, and
# test_inplace_operations_identity checks that c is still c. test_basics_fromkeys is test_basics'
# Counter.fromkeys() NotImplementedError. test_order_preservation's dict.fromkeys() is
# annotated, test_copying's check() is check_dup().
# EXCLUDED upstream cases:
# - test_basics' c.__init__('a' * 500 + 'b' * 300), c.__init__('cdc') and c.__init__() and the
#   assertions after them (c == dict(a=555, b=333, c=3, d=1), setdefault()): calling __init__ of
#   an existing Counter empties it here, where CPython's adds the counts (a bug: Counter('ab')
#   then c.__init__('a') prints Counter({'a': 1}), CPython Counter({'a': 2, 'b': 1})); the
#   counter after the update() calls before them is printed instead. Its isinstance() and
#   issubclass() of Mapping and dict, c.__contains__(), hash(c), and c.update(dict(a=5, b=3))
#   (a display here)
# - test_init and test_update's and test_subtract's TypeErrors (Counter(self=42), ...,
#   iterable=None), test_update_reentrant_add_clears_counter (int subclass), test_copy_subclass,
#   test_repr_nonsortable (a None count), test_copying's copy/deepcopy/pickle/eval(repr()),
#   test_helper_function's OrderedDict and Counter subclasses
# - test_multiset_operations' Counter.__add__ & co as values (the operators are called) and its
#   set.__sub__ & co (the operators on sets); test_inplace_operations' id()
# - test_multiset_operations_equivalent_to_set_operations: itertools (product, chain,
#   combinations) is not a module here ("module 'itertools' is not supported")
from collections import Counter, _count_elements
from random import randrange, seed

# (upstream's random multisets come from the unseeded module functions)
seed(5)


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def test_basics() -> None:
    c = Counter('abcaba')
    check("c", c, Counter({'a':3 , 'b': 2, 'c': 1}))
    check("len", len(c), 3)
    check("sum", sum(c.values()), 6)
    check("values", list(c.values()), [3, 2, 1])
    check("keys", list(c.keys()), ['a', 'b', 'c'])
    check("list", list(c), ['a', 'b', 'c'])
    check("items", list(c.items()),
                     [('a', 3), ('b', 2), ('c', 1)])
    check("c['b']", c['b'], 2)
    check("c['z']", c['z'], 0)
    check("'c' in c", 'c' in c, True)
    check("'z' in c", 'z' in c, False)
    check("get b", c.get('b', 10), 2)
    check("get z", c.get('z', 10), 10)
    check("== dict", c == {'a': 3, 'b': 2, 'c': 1}, True)
    check("repr", repr(c), "Counter({'a': 3, 'b': 2, 'c': 1})")
    check("most_common", c.most_common(), [('a', 3), ('b', 2), ('c', 1)])
    for i in range(5):
        check("most_common(i)", c.most_common(i),
                         [('a', 3), ('b', 2), ('c', 1)][:i])
    check("elements", ''.join(c.elements()), 'aaabbc')
    c['a'] += 1         # increment an existing value
    c['b'] -= 2         # sub existing value to zero
    del c['c']          # remove an entry
    del c['c']          # make sure that del doesn't raise KeyError
    c['d'] -= 2         # sub from a missing value
    c['e'] = -5         # directly assign a missing value
    c['f'] += 4         # add to a missing value
    check("c", c == {'a': 4, 'b': 0, 'd': -2, 'e': -5, 'f': 4}, True)
    check("elements", ''.join(c.elements()), 'aaaaffff')
    check("pop", c.pop('f'), 4)
    check("'f' in c", 'f' in c, False)
    for i in range(3):
        elem, cnt = c.popitem()
        check("elem in c", elem in c, False)
    c.clear()
    e: dict[str, int] = {}
    check("c == {}", c == e, True)
    check("repr", repr(c), 'Counter()')
    c.update({'a': 5, 'b': 3})
    c.update(c=1)
    c.update(Counter('a' * 50 + 'b' * 30))
    c.update()          # test case with no args
    print(c)


def test_basics_fromkeys() -> None:
    try:
        Counter.fromkeys('abc')
    except NotImplementedError as e:
        print("NotImplementedError:", e)


def test_total() -> None:
    c = Counter({'a': 10, 'b': 5, 'c': 0})
    check("total", c.total(), 15)


def test_order_preservation() -> None:
    check("abracadabra", list(Counter('abracadabra').items()),
           [('a', 5), ('b', 2), ('r', 2), ('c', 1), ('d', 1)])
    check("xyz", list(Counter('xyzpdqqdpzyx').items()),
           [('x', 2), ('y', 2), ('z', 2), ('p', 2), ('d', 2), ('q', 2)])
    check("elements", list(Counter('abracadabra simsalabim').elements()),
            ['a', 'a', 'a', 'a', 'a', 'a', 'a', 'b', 'b', 'b','r',
             'r', 'c', 'd', ' ', 's', 's', 'i', 'i', 'm', 'm', 'l'])

    ps = 'aaabbcdddeefggghhijjjkkl'
    qs = 'abbcccdeefffhkkllllmmnno'
    letters: dict[str, int | None] = dict.fromkeys(ps + qs)
    order = {letter: i for i, letter in enumerate(letters)}
    def correctly_ordered(seq: Counter[str]) -> bool:
        'Return true if the letters occur in the expected order'
        positions = [order[letter] for letter in seq]
        return positions == sorted(positions)

    p, q = Counter(ps), Counter(qs)
    check("+p", correctly_ordered(+p), True)
    check("-p", correctly_ordered(-p), True)
    check("p + q", correctly_ordered(p + q), True)
    check("p - q", correctly_ordered(p - q), True)
    check("p | q", correctly_ordered(p | q), True)
    check("p & q", correctly_ordered(p & q), True)

    p, q = Counter(ps), Counter(qs)
    p += q
    check("p += q", correctly_ordered(p), True)

    p, q = Counter(ps), Counter(qs)
    p -= q
    check("p -= q", correctly_ordered(p), True)

    p, q = Counter(ps), Counter(qs)
    p |= q
    check("p |= q", correctly_ordered(p), True)

    p, q = Counter(ps), Counter(qs)
    p &= q
    check("p &= q", correctly_ordered(p), True)

    p, q = Counter(ps), Counter(qs)
    p.update(q)
    check("update", correctly_ordered(p), True)

    p, q = Counter(ps), Counter(qs)
    p.subtract(q)
    check("subtract", correctly_ordered(p), True)


def test_update() -> None:
    c: Counter[str] = Counter()
    c.update(self=42)
    check("self", list(c.items()), [('self', 42)])
    c = Counter()
    c.update(iterable=42)
    check("iterable", list(c.items()), [('iterable', 42)])


def test_copying() -> None:
    words = Counter('which witch had which witches wrist watch'.split())
    def check_dup(dup: Counter[str]) -> None:
        check("is not", dup is not words, True)
        check("==", dup, words)
    check_dup(words.copy())
    update_test: Counter[str] = Counter()
    update_test.update(words)
    check_dup(update_test)
    check_dup(Counter(words))


def test_conversions() -> None:
    s = 'she sells sea shells by the sea shore'
    check("elements", sorted(Counter(s).elements()), sorted(s))
    check("sorted", sorted(Counter(s)), sorted(set(s)))
    check("dict", Counter(s) == dict(Counter(s).items()), True)
    check("set", set(Counter(s)) == set(s), True)


def test_invariant_for_the_in_operator() -> None:
    c = Counter({'a': 10, 'b': -2, 'c': 0})
    for elem in c:
        check("in", elem in c, True)


def test_multiset_operations() -> None:
    c = Counter({'a': 10, 'b': -2, 'c': 0}) + Counter()
    check("c", c == {'a': 10}, True)

    elements = 'abcd'
    for i in range(1000):
        p = Counter(dict([(elem, randrange(-2,4)) for elem in elements]))
        p.update(e=1, f=-1, g=0)
        q = Counter(dict([(elem, randrange(-2,4)) for elem in elements]))
        q.update(h=1, i=-1, j=0)
        result = p + q
        for x in elements:
            assert max(0, p[x]+q[x]) == result[x]
        result = p - q
        for x in elements:
            assert max(0, p[x]-q[x]) == result[x]
        result = p | q
        for x in elements:
            assert max(0, p[x], q[x]) == result[x]
        result = p & q
        for x in elements:
            assert max(0, min(p[x], q[x])) == result[x]

    elements = 'abcdef'
    for i in range(100):
        p = Counter(dict([(elem, randrange(0, 2)) for elem in elements]))
        q = Counter(dict([(elem, randrange(0, 2)) for elem in elements]))
        assert p - q == dict.fromkeys(set(p.elements()) - set(q.elements()), 1)
        assert p | q == dict.fromkeys(set(p.elements()) | set(q.elements()), 1)
        assert p & q == dict.fromkeys(set(p.elements()) & set(q.elements()), 1)
    print("ok")


def test_inplace_operations() -> None:
    elements = 'abcd'
    for i in range(1000):
        p = Counter(dict([(elem, randrange(-2,4)) for elem in elements]))
        p.update(e=1, f=-1, g=0)
        q = Counter(dict([(elem, randrange(-2,4)) for elem in elements]))
        q.update(h=1, i=-1, j=0)
        c = p.copy()
        regular_result = c + q
        c += q
        assert c == regular_result
        c = p.copy()
        regular_result = c - q
        c -= q
        assert c == regular_result
        c = p.copy()
        regular_result = c | q
        c |= q
        assert c == regular_result
        c = p.copy()
        regular_result = c & q
        c &= q
        assert c == regular_result
    print("ok")


def test_inplace_operations_identity() -> None:
    p = Counter('abc')
    q = Counter('bcd')
    c = p.copy()
    c2 = c
    c += q
    check("is", c is c2, True)
    c -= q
    check("is", c is c2, True)
    c |= q
    check("is", c is c2, True)
    c &= q
    check("is", c is c2, True)


def test_subtract() -> None:
    c = Counter({'a': -5, 'b': 0, 'c': 5, 'd': 10, 'e': 15, 'g': 40})
    c.subtract(a=1, b=2, c=-3, d=10, e=20, f=30, h=-50)
    check("c", c, Counter({'a': -6, 'b': -2, 'c': 8, 'd': 0, 'e': -5, 'f': -30, 'g': 40, 'h': 50}))
    c = Counter({'a': -5, 'b': 0, 'c': 5, 'd': 10, 'e': 15, 'g': 40})
    c.subtract(Counter({'a': 1, 'b': 2, 'c': -3, 'd': 10, 'e': 20, 'f': 30, 'h': -50}))
    check("c", c, Counter({'a': -6, 'b': -2, 'c': 8, 'd': 0, 'e': -5, 'f': -30, 'g': 40, 'h': 50}))
    c = Counter('aaabbcd')
    c.subtract('aaaabbcce')
    check("c", c, Counter({'a': -1, 'b': 0, 'c': -1, 'd': 1, 'e': -1}))

    c = Counter()
    c.subtract(self=42)
    check("self", list(c.items()), [('self', -42)])
    c = Counter()
    c.subtract(iterable=42)
    check("iterable", list(c.items()), [('iterable', -42)])


def test_unary() -> None:
    c = Counter({'a': -5, 'b': 0, 'c': 5, 'd': 10, 'e': 15, 'g': 40})
    check("+c", +c == {'c': 5, 'd': 10, 'e': 15, 'g': 40}, True)
    check("-c", -c == {'a': 5}, True)



def test_helper_function() -> None:
    elems = list('abracadabra')
    d: dict[str, int] = dict()
    _count_elements(d, elems)
    check("d", d, {'a': 5, 'r': 2, 'b': 2, 'c': 1, 'd': 1})


def test_comparisons() -> None:
    check("eq", Counter({'a': 3, 'b': 2, 'c': 0}) == Counter('ababa'), True)
    check("ne", Counter({'a': 3, 'b': 2}) != Counter('babab'), True)
    check("le", Counter({'a': 3, 'b': 2, 'c': 0}) <= Counter('ababa'), True)
    check("not le", Counter({'a': 3, 'b': 2}) <= Counter('babab'), False)
    check("lt", Counter({'a': 3, 'b': 1, 'c': 0}) < Counter('ababa'), True)
    check("not lt", Counter({'a': 3, 'b': 2, 'c': 0}) < Counter('ababa'), False)
    check("ge", Counter({'a': 2, 'b': 1, 'c': 0}) >= Counter('aab'), True)
    check("not ge", Counter({'a': 3, 'b': 2, 'c': 0}) >= Counter('aabd'), False)
    check("gt", Counter({'a': 3, 'b': 2, 'c': 0}) > Counter('aab'), True)
    check("not gt", Counter({'a': 2, 'b': 1, 'c': 0}) > Counter('aab'), False)


test_basics()
test_basics_fromkeys()
test_total()
test_order_preservation()
test_update()
test_copying()
test_conversions()
test_invariant_for_the_in_operator()
test_multiset_operations()
test_inplace_operations()
test_inplace_operations_identity()
test_subtract()
test_unary()
test_helper_function()
test_comparisons()
