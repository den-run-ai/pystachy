# pystachy: dynamic-any
# Annotated[Any, metadata] is Any in a module that compiles typing.Any as dynamic values, as it
# requests inference elsewhere: only its first argument is a type (#782). Also through an
# imported alias, typing., typing_extensions. and a generic type alias.
from typing import Annotated as Marked, Any
import typing as t
import typing_extensions as tx

type Tagged[T] = t.Annotated[T, "Any"]


def plain(x: Marked[Any, "label"]) -> Any:
    return x


def qualified(x: t.Annotated[list[Any], "label"]) -> t.Annotated[Any, "result"]:
    return x[0]


def backport(x: tx.Annotated[Any, tx.Any]) -> str:
    return str(x)


def aliased(x: Tagged[Any]) -> Any:
    return x


v: Marked[Any, "v"] = 1
v = "now a str"
print(plain(3), plain("s"), qualified([4]), qualified(["v"]), backport(5), aliased(6), v)
