# closed unions (A | B, Union[A, B]): values of member types boxed with their tag, isinstance()
# and assignments narrowing a local to its members (or fewer of them), early exits, printing,
# ==, truth, a union | None, a conditional expression whose arms differ, and in containers
from typing import Union


def describe(x: int | str) -> str:
    if isinstance(x, int):
        return f"int {x + 1}"
    return "str " + x.upper()


def norm(v: Union[int, float, str]) -> float:
    if isinstance(v, str):
        return float(len(v))
    if isinstance(v, (int, float)):
        return v * 2.0
    return 0.0


print(describe(41), describe("ab"), norm(3), norm(1.5), norm("xyz"))

xs: list[int | str] = [1, "two", 3]
xs.append("four")
print(xs, len(xs), xs[1], xs[-1])


def total(xs: list[int | str]) -> int:
    t = 0
    for x in xs:
        if isinstance(x, int):
            t += x
        else:
            t += len(x)
    return t


print(total(xs))

y: int | str = 5
print(y, repr(y), str(y), f"[{y}]", y == 5, y == "5", y != 5)
y = "five"
print(y, repr(y), y == "five", bool(y), [y])
z: int | str | None = None
print(z, z is None)
z = 0
print(z, z is None, bool(z))


def pick(flag: bool) -> int | str:
    return 7 if flag else "seven"


print(pick(True), pick(False), [pick(True), pick(False)])
d: dict[str, int | list[int]] = {"a": 1, "b": [2, 3]}
print(d, d["b"])


def show(d: dict[str, int | list[int]]) -> None:
    for k in d:
        v = d[k]
        if isinstance(v, list):
            print(k, sum(v))
        else:
            print(k, v)


show(d)


class Cat:
    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"Cat({self.name!r})"


pets: list[Cat | int] = [Cat("tom"), 3]
print(pets, isinstance(pets[0], Cat), isinstance(pets[1], Cat))
