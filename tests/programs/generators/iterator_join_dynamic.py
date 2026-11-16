# pystachy: dynamic-any
# In a module that compiles Any dynamically, a display of distinct iterators keeps its Any items,
# which compare and reflect as their objects; the other locations where distinct iterators meet
# hold Iterator[T], as in other modules.
import sys


def gen(n: int):
    for i in range(n):
        yield i * 10


class Holder:
    def __init__(self) -> None:
        self.it = iter([1, 2])

    def refill(self) -> None:
        self.it = gen(2)


def source(n: int):
    if n > 0:
        return iter([7, 8])
    return gen(3)


items = [iter([1]), gen(1)]
print(items[0] == items[1], items[0] is items[0], type(items[1]).__name__, [list(x) for x in items])
table = {"list": iter([5]), "gen": gen(2)}
print(type(table["list"]).__name__, {k: list(v) for k, v in table.items()})
h = Holder()
print(next(h.it))
h.refill()
print(list(h.it))
print(list(source(1)), list(source(0)))
pick = iter([3, 4]) if len(sys.argv) > 5 else gen(2)
print(list(pick))
