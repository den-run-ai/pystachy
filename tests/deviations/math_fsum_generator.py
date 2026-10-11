# math.fsum(), min() and max() make all the items of a generator expression before they add or
# compare them, so where CPython stops at an item (fsum's intermediate overflow, a __lt__ that
# raises), the expressions of the later items have run (docs/language.md)
import math


class V:
    def __init__(self, x: int) -> None:
        self.x = x

    def __lt__(self, o: "V") -> bool:
        if self.x == 2:
            raise ValueError("2 < " + str(o.x))
        return self.x < o.x


def item(x: float) -> float:
    print("item", x)
    return x


def mk(x: int) -> V:
    print("mk", x)
    return V(x)


try:
    print(math.fsum(item(x) for x in [1e308, 1e308, 1.0]))
except OverflowError as e:
    print("OverflowError:", e)
try:
    print(min(mk(x) for x in range(4)).x)
except ValueError as e:
    print("ValueError:", e)
