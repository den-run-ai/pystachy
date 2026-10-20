# _collections_abc is collections.abc (CPython's collections binds sys.modules['collections.abc']
# to it): import _collections_abc, its alias, from-imports of the ABCs (also in a function and in
# an optional import), annotations through the module, and isinstance() of the ABCs, which finds
# str, bytes and tuple Sequences, a list a MutableSequence and a dict a MutableMapping
import _collections_abc
import _collections_abc as cabc
import collections.abc
from _collections_abc import Mapping, MutableMapping as MM, Sequence, Iterator, Callable

try:
    from _collections_abc import Sortable  # (CPython's module has no Sortable either)
except ImportError:
    Sortable = None


def keys(m: _collections_abc.Mapping[str, int]) -> list[str]:
    return sorted(m)


def total(xs: cabc.Sequence[int]) -> int:
    return sum(xs)


def count(n: int) -> Iterator[int]:
    i = 0
    while i < n:
        yield i
        i += 1


def twice(f: Callable[[int], int], x: int) -> int:
    return f(f(x))


def local() -> str:
    import _collections_abc
    from _collections_abc import MutableSequence
    return f"{isinstance([1], _collections_abc.MutableSequence)} {isinstance('s', MutableSequence)} {isinstance((1,), MutableSequence)}"


def same(xs: collections.abc.Sequence[str]) -> _collections_abc.Sequence[str]:
    return xs


d: dict[str, int] = {"b": 1, "a": 2}
print(isinstance(d, _collections_abc.Mapping), isinstance(d, cabc.MutableMapping), isinstance(d, MM), isinstance(d, Sequence))
print(isinstance("s", Sequence), isinstance(b"x", Sequence), isinstance((1, 2), _collections_abc.Sequence), isinstance([1], Mapping))
print(isinstance(b"x", cabc.MutableSequence), isinstance(3, Sequence), isinstance(None, Mapping))
print(keys(d), total([1, 2, 3]), list(count(3)), twice(lambda v: v * 3, 2))
print(local(), same(["x", "y"]), Sortable)
