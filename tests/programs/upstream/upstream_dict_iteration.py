# Adapted from CPython 3.13.16 Lib/test/test_dict.py, class DictTest: test_mutating_iteration,
# test_mutating_iteration_delete, test_mutating_iteration_delete_over_values,
# test_mutating_iteration_delete_over_items, test_reversed and
# test_reverse_iterator_for_empty_dict, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertEqual(a, b) prints a and asserts
# a == b, and `with assertRaises(RuntimeError)` a try statement that prints the exception. An
# empty display and dict() that nothing types get an annotation. test_reversed's iterator r is
# list(reversed(d)) itself (reversed objects are not values, nor next()).
# EXCLUDED upstream cases (see also tests/programs/upstream/upstream_dict_methods.py):
# - test_reversed's `next(r)` raising StopIteration once r is exhausted (next() is not supported)
# - test_reversed_dict_after_clear_and_restore and
#   test_reversed_dict_keys_changed_during_iteration: reversed objects kept across changes of
#   the dict, and next() (reversed() is a consumer's argument or a for loop's iterable here)
# - test_oob_indexing_dictiter_iternextitem (an int subclass with __del__),
#   test_reverse_iterator_for_shared_shared_dicts (instance __dict__),
#   test_dict_items_result_gc* (gc)
# - test_keys_contained, test_errors_in_view_containment_check, test_dictview_set_operations_*,
#   test_items_symmetric_difference, test_dictview_mixed_set_operations: keys() and items() are
#   list snapshots here (a documented deviation), so their comparisons and set operators are a
#   list's, or rejected


def check(label: str, got, expected) -> None:
    print(label, repr(got))
    assert got == expected, label


def test_mutating_iteration() -> None:
    # changing dict size during iteration
    d: dict[int, int] = {}
    d[1] = 1
    try:
        for i in d:
            d[i+1] = 1
    except RuntimeError as e:
        print("RuntimeError:", e)
    else:
        assert False, "expected RuntimeError"
    print(d)


def test_mutating_iteration_delete() -> None:
    # change dict content during iteration
    d: dict[int, int] = {}
    d[0] = 0
    try:
        for i in d:
            del d[0]
            d[0] = 0
    except RuntimeError as e:
        print("RuntimeError:", e)
    else:
        assert False, "expected RuntimeError"
    print(d)


def test_mutating_iteration_delete_over_values() -> None:
    # change dict content during iteration
    d: dict[int, int] = {}
    d[0] = 0
    try:
        for i in d.values():
            del d[0]
            d[0] = 0
    except RuntimeError as e:
        print("RuntimeError:", e)
    else:
        assert False, "expected RuntimeError"
    print(d)


def test_mutating_iteration_delete_over_items() -> None:
    # change dict content during iteration
    d: dict[int, int] = {}
    d[0] = 0
    try:
        for i in d.items():
            del d[0]
            d[0] = 0
    except RuntimeError as e:
        print("RuntimeError:", e)
    else:
        assert False, "expected RuntimeError"
    print(d)


def test_reversed() -> None:
    d = {"a": 1, "b": 2, "foo": 0, "c": 3, "d": 4}
    del d["foo"]
    r = list(reversed(d))  # reversed(d)
    check("list(r)", r, list('dcba'))


def test_reverse_iterator_for_empty_dict() -> None:
    # bpo-38525: reversed iterator should work properly

    # empty dict is directly used for reference count test
    empty: dict[int, int] = {}
    no_keys: list[int] = []
    no_items: list[tuple[int, int]] = []
    check("list(reversed({}))", list(reversed(empty)), no_keys)
    check("list(reversed({}.items()))", list(reversed(empty.items())), no_items)
    check("list(reversed({}.values()))", list(reversed(empty.values())), no_keys)
    check("list(reversed({}.keys()))", list(reversed(empty.keys())), no_keys)

    # dict() and {} don't trigger the same code path
    new: dict[int, int] = dict()
    check("list(reversed(dict()))", list(reversed(new)), no_keys)
    check("list(reversed(dict().items()))", list(reversed(new.items())), no_items)
    check("list(reversed(dict().values()))", list(reversed(new.values())), no_keys)
    check("list(reversed(dict().keys()))", list(reversed(new.keys())), no_keys)


test_mutating_iteration()
test_mutating_iteration_delete()
test_mutating_iteration_delete_over_values()
test_mutating_iteration_delete_over_items()
test_reversed()
test_reverse_iterator_for_empty_dict()
