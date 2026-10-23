# pystachy: dynamic-any
# Adapted from CPython 3.13.16 Lib/test/test_deque.py, TestBasic.test_count
# (BadCompare and MutatingCompare fragments), test_insert_bug_26194 (full-deque
# heterogeneous None insertion) and test_copy_method, commit
# cbc944f4bc59639a444dd971c737788ba2283a91. PSF License v2;
# see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES. Source SHA-256:
# 15578b602865dfa5c80baa64006d64c5875765aab457d5b4bedd73a5e8436d73.
# unittest becomes asserts/try statements; local classes move to module scope.
# Explicit deque[Any] and list[Any] select heterogeneous storage. The mutation
# callback receives its deque through an annotated field. Copy also checks identity
# and mutation visibility explicitly. Other methods remain in lib_collections tests.
from collections import deque
from typing import Any


class BadCompare:
    def __eq__(self, other: Any) -> bool:
        raise ArithmeticError


class MutatingCompare:
    def __init__(self) -> None:
        self.d: Any = None

    def __eq__(self, other: Any) -> bool:
        self.d.pop()
        return True


def test_count() -> None:
    values: list[Any] = [1, 2, BadCompare(), 3]
    d: deque[Any] = deque(values)
    try:
        d.count(2)
    except ArithmeticError:
        print("count visits all items")
    else:
        raise AssertionError("comparison skipped")
    values = [1, 2, 3]
    d = deque(values)
    try:
        d.count(BadCompare())
    except ArithmeticError:
        print("count reflected comparison")
    else:
        raise AssertionError("comparison skipped")
    m = MutatingCompare()
    values = [1, 2, 3, m, 4, 5]
    d = deque(values)
    m.d = d
    try:
        d.count(3)
    except RuntimeError as exc:
        print("count mutation", str(exc))
    else:
        raise AssertionError("mutation undetected")


def test_insert_full() -> None:
    values: list[Any] = ['A', 'B', 'C']
    d: deque[Any] = deque(values, maxlen=len(values))
    try:
        d.insert(2, None)
    except IndexError as exc:
        print("full insert", str(exc))
    else:
        raise AssertionError("full insertion accepted")
    assert list(d) == values


def test_copy_method() -> None:
    mut: Any = [10]
    values: list[Any] = [mut]
    d: deque[Any] = deque(values)
    e = d.copy()
    assert list(d) == list(e)
    mut[0] = 11
    assert d is not e
    assert list(d) == list(e)
    assert d[0] is e[0] and e[0] is mut
    assert e[0][0] == 11
    print("shallow copy", list(e))


test_count()
test_insert_full()
test_copy_method()
