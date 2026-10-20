# pystachy: dynamic-any
# Unions and Any values. A union's value becomes an Any value by its member: an int | float that a
# join gives a variable or a function's result, and unions the program annotates, with None or of
# classes. A variable or result that a join made a union, and that is given an Any value later,
# is dynamic instead. An Any value narrows into a union without None by its member.
from typing import Any


class P:
    def __init__(self, x: int) -> None:
        self.x = x

    def __repr__(self) -> str:
        return f"P({self.x})"


class Q:
    def __repr__(self) -> str:
        return "Q()"


def show(v: Any) -> str:
    return type(v).__name__ + " " + repr(v)


def get(i: int) -> Any:
    return [1, "s", 2.5, None][i]


def half(n: int):
    if n % 2 == 0:
        return n // 2
    return n / 2


def pick(k: int):
    if k == 0:
        return 1
    if k == 1:
        return "one"
    return get(k)


def mix(n: int):
    x = 1
    for i in range(n):
        if i == 1:
            x = "a"
    print(show(x))
    x = get(2)
    return x


total = 0
for i in range(3):
    total += 0.5
print(show(total), show(half(4)), show(half(5)))
u: int | str | None = None
print(show(u))
u = "s"
print(show(u))
w: P | Q = P(3)
print(show(w))
w = Q()
print(show(w))
items: list[Any] = [half(3), half(6), u, w, None]
print(items)
print(pick(0), pick(1), pick(2), mix(3))


def narrow(i: int) -> None:
    n: int | str = get(i)
    print(show(n))
    if isinstance(n, int):
        print(n + 1)


narrow(1)
narrow(0)
