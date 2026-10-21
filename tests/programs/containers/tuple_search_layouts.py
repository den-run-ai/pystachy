# Tuple searches use ordinary equality across compatible element layouts.
from typing import NamedTuple


class Pair(NamedTuple):
    x: int
    y: int


p = Pair(1, 2)
print((p,).count((1, 2)), ((1, 2),).count(p))
print((p,).index((1, 2)), ((1, 2),).index(p))
a: tuple[int | None, int] = (1, 2)
print((a,).count((1, 2)), (a,).index((1, 2)))
print((tuple([1, 2]),).count((1, 2)))
print((tuple([1, 2]),).count((1.0, 2.0)))
print((((1.0, 2.0),)).count(tuple([1, 2])))
print((((1, 2),)).count(tuple([1, 2])))
print(([1], [2], [1]).count([1.0]))
print(([1], [2], [1]).index([1.0], 1))
print((p,).count((1, 2)), (p,).index((1, 2)))
print(tuple([1, 2]).count("x"))
try:
    print(tuple([1, 2]).index("x"))
except ValueError as error:
    print(error)


class Equal:
    def __eq__(self, value: int) -> bool:
        print("eq", value)
        return value == 2


print((1, 2, 3).count(Equal()))
print(tuple([1, 2, 3]).index(Equal()))

print(({1, 2},).count(frozenset([1, 2])))
print((frozenset([1, 2]),).count({1, 2}))
print(({1, 2},).index(frozenset([1, 2])))


class FloatPair(NamedTuple):
    x: float


shared = FloatPair(float("nan"))
print((shared,).count(shared), (shared,).index(shared))


class Plain:
    pass


print((Plain(),).count("x"), ([1],).count("x"), ({1},).count("x"))
