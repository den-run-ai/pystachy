# pystachy: python-int
# asdict/astuple copy immutable promoting scalars and recursively copy their containers.
from dataclasses import asdict, astuple, dataclass


@dataclass
class Number:
    value: int


@dataclass
class Maybe:
    value: int | None


@dataclass
class Pair:
    value: tuple[int, int]


@dataclass
class Numbers:
    values: list[int]


big = 2 ** 80
for value in [1, -2 ** 63, big, -big]:
    print(asdict(Number(value)))
print(astuple(Number(1)), astuple(Number(-2 ** 63)))
print(asdict(Maybe(None)), astuple(Maybe(None)))
print(asdict(Maybe(7)), astuple(Maybe(7)))
print(asdict(Pair((big, -2 ** 63))))
print(astuple(Pair((1, -2 ** 63))))
source = [big, -big]
copied = asdict(Numbers(source))["values"]
copied.append(big + 1)
print(source, copied, source is copied)
tuple_copy = astuple(Numbers(source))[0]
tuple_copy[0] = 3
print(source, tuple_copy, source is tuple_copy)
