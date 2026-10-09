from typing import Iterable


def total(xs: Iterable[int]) -> int:
    return sum(xs)


def keys(d: dict[float, int]) -> int:
    return len(d)


def count() -> int:
    return 3


def with_default(xs: Iterable[int] = [1, 2]) -> int:
    return 0


def mixed(x, ys: Iterable[int]) -> int:
    return x + sum(ys)


class Holder:
    def helper(self) -> Iterable[int]:
        return [3]

    def __init__(self) -> None:
        self.x = self.helper()
        self.y = 1


class Base:
    def __init__(self, v: int) -> None:
        self.v = v


class Derived(Base):
    pass


class Owner:
    def __init__(self) -> None:
        self.d = Derived(1)
        self.n = 2
