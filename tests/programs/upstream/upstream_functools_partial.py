# Adapted from CPython 3.13.16 Lib/test/test_functools.py, class TestPartial (run with
# functools.partial, as lib/functools.py adapts the pure-Python class): test_error_propagation
# and test_with_bound_and_unbound_methods, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# assertEqual(a, b) prints a and asserts a == b; assertRaises(E, f, *args) is a try statement
# that prints the exception; test_error_propagation's f is a module function.
# EXCLUDED upstream cases:
# - the tests of capture(*args, **kw), which returns its **kw to compare it with dicts
#   (rejected: "cannot compare kw[a:int,b:int] == dict[str,int]", or for no keywords "cannot
#   infer the type of an empty dict"), and of dict(a=10, ...) (#516): test_basic_examples,
#   test_attributes, test_kwargs_copy, test_arg_combinations, test_kw_combinations,
#   test_positional, test_keyword, test_no_side_effects, test_nested_optimization, test_repr
#   (also: "printing a function ... is not supported")
# - test_basic_examples' partial(map, ...) (map() as a value, rejected inside lib/functools.py),
#   test_protection_of_callers_dict_argument (p(**d) of a dict[str,int], #516), test_weakref,
#   test_argument_checking, test_nested_optimization_bug (__getattr__), the pickling, copy,
#   setstate, recursion and subclass tests, TestPartialMethod
from functools import partial


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def f(x, y):
    x / y


def test_error_propagation() -> None:
    try:
        partial(f, 1, 0)()
    except ZeroDivisionError as e:
        print("ZeroDivisionError", e)
    try:
        partial(f, 1)(0)
    except ZeroDivisionError as e:
        print("ZeroDivisionError", e)
    try:
        partial(f)(1, 0)
    except ZeroDivisionError as e:
        print("ZeroDivisionError", e)
    try:
        partial(f, y=0)(1)
    except ZeroDivisionError as e:
        print("ZeroDivisionError", e)


def test_with_bound_and_unbound_methods() -> None:
    data = list(map(str, range(10)))
    join = partial(str.join, '')
    check("join", join(data), '0123456789')
    join2 = partial(''.join)
    check("join", join2(data), '0123456789')


test_error_propagation()
test_with_bound_and_unbound_methods()
