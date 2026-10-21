# Any in Annotated's type operand still requests inference; only metadata is ignored.
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


print(plain(3), plain("s"), qualified([4]), qualified(["v"]), backport(5), aliased(6))
