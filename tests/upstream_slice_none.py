# CPython 3.13.16 Lib/test/seq_tests.py CommonTest.test_getslice (PSF license).
# Upstream cbc944f4bc59639a444dd971c737788ba2283a91, lines 181-192.
# Full upstream license: tests/upstream/CPYTHON-LICENSE.txt.
# Remove type2test/unittest scaffolding; keep the explicit None assertions.
u = [0, 1, 2, 3, 4]
assert u[1:None] == [1, 2, 3, 4]
assert u[None:3] == [0, 1, 2]

# Extensions: cover both bounds, str, None-valued expressions, and effect order.
assert u[None:None] == u
assert 'abcde'[1:None] == 'bcde'
assert 'abcde'[None:3] == 'abc'
assert 'abcde'[None:None] == 'abcde'
n = None
assert u[n:3] == [0, 1, 2]


def sequence() -> list[int]:
    print('sequence')
    return u


def none_bound(label: str) -> None:
    print(label)
    return None


assert sequence()[none_bound('start'):none_bound('stop')] == u
assert 'abcde'[none_bound('text-start'):none_bound('text-stop')] == 'abcde'


def optional_cut(values: list[int], start: int | None, stop: int | None) -> list[int]:
    return values[start:stop]


def optional_text(value: str, start: int | None, stop: int | None) -> str:
    return value[start:stop]


def bool_cut(values: list[int], start: bool | None, stop: bool | None) -> list[int]:
    return values[start:stop]


assert optional_cut(u, None, 3) == [0, 1, 2]
assert optional_cut(u, 1, None) == [1, 2, 3, 4]
assert optional_cut(u, None, None) == u
assert optional_text('abcde', None, 3) == 'abc'
assert optional_text('abcde', 1, None) == 'bcde'
assert optional_text('abcde', None, None) == 'abcde'
assert bool_cut(u, True, None) == [1, 2, 3, 4]
assert bool_cut(u, None, False) == []
assert bool_cut(u, None, None) == u
assert u[-9223372036854775808:None] == u
assert u[None:-9223372036854775808] == []
assert optional_cut(u, -9223372036854775808, None) == u
assert optional_cut(u, None, -9223372036854775808) == []
assert optional_text('abcde', -9223372036854775808, None) == 'abcde'
assert optional_text('abcde', None, -9223372036854775808) == ''
assert u[True:None] == [1, 2, 3, 4]
assert u[None:False] == []
print('ok')
