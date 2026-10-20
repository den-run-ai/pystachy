# Starred items in list and tuple displays: [a, *xs] takes each starred iterable's items where it
# stands (a list's as they are then, a str's characters, a dict's keys, what __iter__, range() or a
# generator expression gives); a tuple display is a tuple of its items, or a runtime-length tuple
# where a starred item's length is known only at run time
from typing import Iterator, NamedTuple


class P(NamedTuple):
    x: int
    y: int


class Bag:
    def __init__(self, items: list[int]) -> None:
        self.items = items

    def __iter__(self) -> Iterator[int]:
        print("iter")
        return iter(self.items)


def note(tag: str, v: list[int]) -> list[int]:
    print("eval", tag)
    return v


a = [1, 2]
b = (3, 4)
print([*a, *b, 5])
print([0, *a], [*a], (*(),))
print((*b, 9), (*b,), (*a, *b))
print([*"hello"[:2], "z"], [*range(3), *reversed(a)])
print([*{"k": 1, "j": 2}], [*{7}], [*P(5, 6)], [*Bag([8, 9])])
print([*(i * 2 for i in range(3))], [*map(str, a)], [*enumerate("xy")])
t = (*a, 10)
print(t, len(t), t[2], t == (1, 2, 10))
mixed = (*b, "s", 2.5)
print(mixed)
xs = [1, 2, 3]
print([*xs, xs.pop()], xs)
ys: list[float] = [*[1.5], 2.0]
print(ys)
both: list[int | str] = [*a, "s", *["é", "ü"]]
print(both)
print([*[1, 2], None], (None, *a))
print([*note("first", [1]), *note("second", [2])])
for v in [*a, *b]:
    print(v, end=" ")
print()
first, second = *a,
print(first, second)
p, q, r = *b, 7
print(p, q, r)


def spread(*args: int) -> list[int]:
    return [*args, *args]


def generic(xs):
    return (*xs, *xs)


print(spread(1, 2), generic([3]), generic("ab"))
print(*[0, *a], *(9, *b))
print(max(*(1, *b)))
nothing: list[int] | None = None if len(a) < 5 else a
try:
    print([*a, *nothing])
except TypeError as e:
    print("TypeError:", e)
try:
    u, w = (*a, 3)
except ValueError as e:
    print("ValueError:", e)
