# pystachy: python-int
from contextlib import contextmanager
from typing import Callable, Iterator


class Stack(list[int]):
    pass


value = Stack([1])


def save(items: list[list[int]]) -> None:
    items.append(value)


callback: Callable[[list[list[int]]], None] = save
items: list[list[int]] = [[0]]
alias: list[list[int]] = items
callback(items)
print(alias is items, alias[-1] is value, isinstance(alias[-1], Stack))


class Scope:
    @contextmanager
    def opened(self, number: int, *, extra: int = 0) -> Iterator[int]:
        print(number, extra)
        yield 1


scope = Scope()
with scope.opened(2**80, extra=2**81) as result:
    print(result)


@scope.opened(2**82, extra=2**83)
def decorated() -> int:
    return 7


print(decorated())
print(alias[-1] is value)
