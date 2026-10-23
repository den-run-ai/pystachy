# pystachy: dynamic-any
# Adapted from CPython 3.13.16 Lib/test/test_dict.py, DictTest.test_setdefault,
# test_pop, test_repr and test_hash_collision_remove_add, commit
# cbc944f4bc59639a444dd971c737788ba2283a91; SHA-256
# ab8c3107f3390867750c19a3024c0284c34c62fb6f2297024627b1c66b48d406.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Restore supported fragments that upstream_dict_methods changed/excluded for
# homogeneous storage: None defaults, heterogeneous values/defaults, self-reference
# and original CustomHash keys. unittest becomes assert; dict/list Any annotations
# select dynamic storage. setdefault's default None is explicit: its omitted-default
# form is still unsupported. Wrong-arity and callback-exception fragments stay elsewhere.
from typing import Any


def test_setdefault() -> None:
    d: Any = {}
    assert d.setdefault('key0', None) is None
    d.setdefault('key0', [])
    assert d.setdefault('key0', None) is None
    d.setdefault('key', []).append(3)
    assert d['key'][0] == 3
    d.setdefault('key', []).append(4)
    assert len(d['key']) == 2
    print(d)


def test_pop() -> None:
    d: Any = {}
    k, v = 'abc', 'def'
    d[k] = v
    try:
        d.pop('ghi')
    except KeyError:
        pass
    else:
        raise AssertionError('missing KeyError')
    assert d.pop(k) == v
    assert len(d) == 0
    assert d.pop(k, v) == v
    d[k] = v
    assert d.pop(k, 1) == v
    # Additional missing-key control actually returns the heterogeneous default.
    assert d.pop(k, 1) == 1
    print("heterogeneous pop")


def test_repr() -> None:
    d: Any = {}
    assert repr(d) == '{}'
    d[1] = 2
    assert repr(d) == '{1: 2}'
    d = {}
    d[1] = d
    assert repr(d) == '{1: {...}}'
    print(d)


class CustomHash:
    def __init__(self, value: int) -> None:
        self.value = value

    def __hash__(self) -> int:
        return self.value


def test_hash_collision_remove_add() -> None:
    n = 64
    items: list[tuple[CustomHash, Any]] = [(CustomHash(h), h) for h in range(n)]
    a = CustomHash(n)
    b = CustomHash(n)
    items += [(a, 'a'), (b, 'b')]
    d: dict[CustomHash, Any] = dict(items)
    assert len(d) == len(items)
    del d[a]
    del items[n]
    assert len(d) == len(items)
    assert d == dict(items)
    d[b] = 'c'
    items[n] = (b, 'c')
    assert len(d) == len(items)
    assert d == dict(items)
    print("collision", len(d), d[b])


test_setdefault()
test_pop()
test_repr()
test_hash_collision_remove_add()
