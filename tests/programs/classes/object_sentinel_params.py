# A parameter annotated T whose default is a module's sentinel (_dummy = object(), as mypy's
# Bogus[...] = _dummy parameters) takes a T, or the sentinel where a call leaves it out: each
# call's specialization decides p is _dummy, so a conditional expression or an if statement
# keeps the branch that runs. Also for bool, int and optional parameters, keywords, the
# sentinel passed explicitly and a module-level function; a parameter annotated object, which
# holds any object(), keeps its test.
from typing import Any, Final

_dummy: Final[Any] = object()


class Node:
    def __init__(self, items: list[int], name: str | None, flag: bool, n: int) -> None:
        self.items = items
        self.name = name
        self.flag = flag
        self.n = n

    def copy_modified(self, items: list[int] = _dummy, name: str | None = _dummy, flag: bool = _dummy) -> "Node":
        return Node(
            items if items is not _dummy else self.items,
            self.name if name is _dummy else name,
            flag if flag is not _dummy else self.flag,
            self.n,
        )

    def with_n(self, n: int = _dummy) -> "Node":
        if n is _dummy:
            n = self.n
        return Node(self.items, self.name, self.flag, n + 1)

    def show(self) -> str:
        return f"{self.items} {self.name} {self.flag} {self.n}"


def pick(a: str = _dummy, b: float = _dummy) -> str:
    return (a if a is not _dummy else "-") + str(b if b is not _dummy else 0.5)


_OTHER = object()


def held(x: object = _dummy) -> bool:
    # (an object annotation holds any object(): no sentinel parameter, its test runs)
    return x is _dummy


x = Node([1], "x", False, 3)
print(x.copy_modified().show(), x.copy_modified([2], None).show(), x.copy_modified(flag=True).show())
print(x.copy_modified(items=_dummy, name="y").show(), x.with_n().show(), x.with_n(10).show())
print(pick(), pick("a"), pick(b=2.0), pick("c", _dummy), held(), held(_OTHER), held(_dummy))
