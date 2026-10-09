# A module-level T = TypeVar("T") makes a module-level function whose parameters mention T a
# template, compiled for each call's argument types, as def f[T](x: T) is
from collections.abc import Callable
from typing import Optional, TypeVar, Union

import typing_extensions
from mods.generic import Box, get, pair

T = TypeVar("T")
_D = typing_extensions.TypeVar("_D", bound="object")
K = TypeVar("K")


def first(xs: list[T], d: T | None = None) -> T | None:
    return xs[0] if xs else d


def lookup(key: str, default: _D | None = None, convert: Callable[[str], T] | None = None) -> "_D | str | None":
    if key.startswith("x"):
        return default
    return key


def both(a: T, b: Union[T, None]) -> list[T]:
    return [a] if b is None else [a, b]


def ident(x: T) -> T:
    return x


def invert(d: dict[K, T]) -> dict[T, K]:
    out = {}
    for k, v in d.items():
        out[v] = k
    return out


def count(xs: "list[Optional[T]]") -> int:
    return len([x for x in xs if x is not None])


print(first(["a"]), first(["a"], "b"), first([[1]]))
empty: list[str] = []
print(first(empty, "e"), first(empty))
print(lookup("x", "dflt"), lookup("y"), lookup("x"))
print(both(1, None), both("a", "b"), ident(1.5), ident([1]), ident("s"), ident(True))
print(invert({"a": 1, "b": 2}), invert({1: "x"}))
print(count(["a", None, "b"]), count([None, "c"]))
print(get({"a": 1}, "a", 0), get({"a": "x"}, "b", "y"), pair(1, 2), pair("p", "q"))
print(Box(3).v)
