# Adapted from CPython 3.13.16 Lib/test/test_defaultdict.py, class TestDefaultDict: test_basic,
# test_repr, test_copy, test_keyerror_without_factory and test_union, commit
# cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) and assertTrue(x)
# print and assert. A defaultdict(list) or defaultdict(int) is annotated with its key and value
# types (a builtin class as the factory binds no types: "defaultdict() cannot bind its type
# variables from the argument for 'default_factory', a <built-in function int> ..."); one
# defaultdict holds one value type, so test_basic's parts with list values and with int values
# are test_basic and test_basic_2 (defaultdict(int, {"foo": 1, "bar": 2}) for
# defaultdict(list, foo=1, bar=2)), test_basic_no_factory is its default_factory None part and
# test_repr_no_factory test_repr's; test_union's i holds strs ("1", "2") as s does. A mapping
# compared with a dict display or printed as a dict is compared with == (dict() of a defaultdict
# is rejected: "dict() of an object ('defaultdict') is not supported"), and dict(s) is
# {k: v for k, v in s.items()}.
# EXCLUDED upstream cases:
# - default_factory reads and writes (d1.default_factory = list, del d2.default_factory: a
#   factory is fixed by the type here; printing it is rejected: "printing a function, or
#   comparing containers of functions, is not supported"), test_basic's `defaultdict(list,
#   foo=1, bar=2)` with int keys too, defaultdict(1) and defaultdict({}) (compile-time errors),
#   test_missing (__missing__ as a method value), test_repr's eval(repr()) and function factory
#   repr, test_copy's type(d2) is defaultdict (rejected: "unsupported call
#   type(collections.defaultdict-1)"), test_shallow_copy, test_deep_copy, test_pickling,
#   test_recursive_repr, test_callable_arg, test_repr_recursive_factory
# - test_union's `dict(s) | i` (rejected: "unsupported operand type(s) for |: 'dict' and
#   'defaultdict'": reflected operators are not supported), its TypeErrors and `i |= None`;
#   test_union's assertIs(..default_factory, int)
# - test_factory_conflict_with_set_value (rejected: "default_factory() reads 'test_dict', which
#   may not be assigned yet where it is defined: not supported")
from collections import defaultdict


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def test_basic() -> None:
    d1: defaultdict[int, list[int]] = defaultdict(list)
    d1[12].append(42)
    check("d1", d1 == {12: [42]}, True)
    d1[12].append(24)
    check("d1", d1 == {12: [42, 24]}, True)
    d1[13]
    d1[14]
    check("d1", d1 == {12: [42, 24], 13: [], 14: []}, True)
    check("is not", d1[12] is not d1[13] is not d1[14], True)


def test_basic_2() -> None:
    d2 = defaultdict(int, {"foo": 1, "bar": 2})
    check("d2", d2 == {"foo": 1, "bar": 2}, True)
    check("foo", d2["foo"], 1)
    check("bar", d2["bar"], 2)
    check("in", "foo" in d2, True)
    check("in keys", "foo" in d2.keys(), True)
    check("not in", "baz" in d2, False)


def test_basic_no_factory() -> None:
    d2: defaultdict[int, int] = defaultdict()
    print(d2.default_factory is None)
    try:
        d2[15]
    except KeyError as err:
        print("KeyError", err)


def test_repr() -> None:
    d2: defaultdict[int, int] = defaultdict(int)
    d2[12] = 42
    check("repr", repr(d2), "defaultdict(<class 'int'>, {12: 42})")


def test_repr_no_factory() -> None:
    d1: defaultdict[int, int] = defaultdict()
    check("repr", repr(d1), "defaultdict(None, {})")
    d1[11] = 41
    check("repr", repr(d1), "defaultdict(None, {11: 41})")


def test_copy() -> None:
    d1: defaultdict[int, list[int]] = defaultdict(list)
    d3 = d1.copy()
    e: dict[int, list[int]] = {}
    check("d3", d3 == e, True)
    d1[42]
    d4 = d1.copy()
    e4: dict[int, list[int]] = {42: []}
    check("d4", d4 == e4, True)
    d4[12]
    e5: dict[int, list[int]] = {42: [], 12: []}
    check("d4", d4 == e5, True)
    d: defaultdict[str, int] = defaultdict(int)
    d['a'] = 42
    ee = d.copy()
    check("e['a']", ee['a'], 42)


def test_keyerror_without_factory() -> None:
    d1: defaultdict[tuple[int], int] = defaultdict()
    try:
        d1[(1,)]
    except KeyError as err:
        print("KeyError", err)


def test_union() -> None:
    i = defaultdict(str, {1: "1", 2: "2"})
    s = defaultdict(str, {0: "zero", 1: "one"})

    i_s = i | s
    check("i_s", i_s == {1: "one", 2: "2", 0: "zero"}, True)
    check("list", list(i_s), [1, 2, 0])

    s_i = s | i
    check("s_i", s_i == {0: "zero", 1: "1", 2: "2"}, True)
    check("list", list(s_i), [0, 1, 2])

    i_ds = i | {k: v for k, v in s.items()}
    check("i_ds", i_ds == {1: "one", 2: "2", 0: "zero"}, True)
    check("list", list(i_ds), [1, 2, 0])


def test_union_ior() -> None:
    i = defaultdict(str, {1: "1", 2: "2"})
    s = defaultdict(str, {0: "zero", 1: "one"})
    i |= list(s.items())
    check("i", i == {1: "one", 2: "2", 0: "zero"}, True)
    check("list", list(i), [1, 2, 0])


test_basic()
test_basic_2()
test_basic_no_factory()
test_repr()
test_repr_no_factory()
test_copy()
test_keyerror_without_factory()
test_union()
test_union_ior()
