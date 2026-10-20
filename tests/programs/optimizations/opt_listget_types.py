# listget (docs/typed-ir.md 7.1) over what the typed IR adds: loops over the list an object's
# __iter__ steps through (also in zip() and enumerate()), whose body or __getitem__ shrinks it, an
# optional list, a NamedTuple's items, boxed items, and any() and all() of an object.
# Run with PYSTACHY_OPT=-listget too.
from typing import Iterator, NamedTuple, Optional


class Box:
    def __init__(self, xs: list[int]) -> None:
        self.xs = xs

    def __iter__(self) -> Iterator[int]:
        return iter(self.xs)

    def __len__(self) -> int:
        return len(self.xs)

    def __getitem__(self, i: int) -> int:
        self.xs.pop()  # a read that shrinks the list
        return i


class Pair(NamedTuple):
    a: int
    b: int


def through_iter() -> None:
    b = Box([1, 2, 3, 4, 5])
    for x in b:  # steps through b.xs, which the body shrinks
        if x == 2:
            b.xs.pop()
        print("iter", x, len(b))


def zip_dunder() -> None:
    b = Box([10, 20, 30, 40])
    ys = [1, 2, 3, 4]
    for x, y in zip(b, ys):
        print("zip", x, y, b[y])  # __getitem__ pops b.xs


def enum_obj() -> None:
    b = Box([5, 6, 7, 8])
    for i, x in enumerate(b, 100):
        b.xs.clear() if i == 101 else None
        print("enum", i, x)


def opt_list(xs: Optional[list[int]]) -> int:
    t = 0
    if xs is not None:
        for x in xs:
            t += x
            if x == 3:
                xs.clear()
    return t


def nt_items(p: Pair) -> int:
    t = 0
    for v in p:
        t = t * 10 + v
    return t


def boxed(xs: list[Optional[int]]) -> int:
    t = 0
    for x in xs:
        if x is not None:
            t += x
        else:
            xs.pop()
    return t


def any_all(b: Box) -> str:
    return f"{any(b)} {all(b)} {any([x > 3 for x in b])}"


through_iter()
zip_dunder()
enum_obj()
print(opt_list([1, 2, 3, 4, 5]), opt_list(None))
print(nt_items(Pair(1, 2)))
print(boxed([1, None, 2, 3, None, 4]))
print(any_all(Box([0, 0, 4])), any_all(Box([])))
