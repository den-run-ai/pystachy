# sum() of objects adds them as CPython does: start + first (0 + first where no start is given,
# the item's __radd__), then sum + item for each next one, in order, each item evaluated just
# before its addition. No items give the start itself: the int 0 by default, so the result of
# sum(items) is an int or the items' sum, a union that is narrowed or used as it is.
from typing import Iterator


class Value:
    def __init__(self, x: float, log: bool = False) -> None:
        self.x = x
        self.log = log

    def __repr__(self) -> str:
        return f"Value({self.x})"

    def __add__(self, other: "Value | int | float") -> "Value":
        if isinstance(other, Value):
            if self.log or other.log:
                print("  add", self.x, other.x)
            return Value(self.x + other.x, self.log or other.log)
        if self.log:
            print("  add", self.x, other)
        return Value(self.x + other, self.log)

    def __radd__(self, other: int) -> "Value":
        if self.log:
            print("  radd", self.x, other)
        return Value(self.x + other, self.log)


class Paired:
    def __init__(self, n: int) -> None:
        self.n = n

    def __add__(self, other: "Paired") -> "Paired":
        return Paired(self.n + other.n)


class Steps:
    def __init__(self) -> None:
        self.i = 0

    def __iter__(self) -> "Steps":
        return self

    def __next__(self) -> Value:
        self.i += 1
        if self.i > 3:
            raise StopIteration
        return Value(float(self.i))


def values(n: int, log: bool = False) -> list[Value]:
    return [Value(float(i), log) for i in range(1, n + 1)]


def show(total: "int | Value") -> None:
    if isinstance(total, Value):
        print("Value", total.x)
    else:
        print("int", total)


def item(i: int) -> Value:
    print("item", i)
    return Value(float(i), True)


def iterable() -> list[Value]:
    print("iterable")
    return values(2)


def start() -> Value:
    print("start")
    return Value(0.5)


def stream() -> Iterator[Value]:
    for i in range(3):
        yield Value(float(i))


def mean(xs: list[Value]) -> float:
    total = sum(xs)
    if isinstance(total, Value):
        return total.x / len(xs)
    return float(total)


show(sum(values(3)))
show(sum(values(0)))
print(sum(values(2)), sum(values(0)), sum(values(3, True)))
kept = Value(5.0)
same = sum(values(0), kept)
print(sum(values(3), Value(100.0)).x, same is kept, same.x)
print(sum(Value(float(i)) for i in range(3)), sum((Value(float(i)) for i in range(3)), Value(10.0)).x)
print(sum((item(i) for i in range(3)), Value(10.0, True)).x)
print(sum(item(i) for i in range(2)))
print(sum(iterable(), start()).x)
pair = (Value(1.0), Value(2.0))
table = {1: Value(1.0), 2: Value(4.0)}
print(sum(pair), sum(pair, Value(1.0)).x, sum(table.values()), sum(table.values(), Value(0.0)).x)
print(sum(values(2), 5), sum([1, 2, 3], Value(0.0)).x, sum(Steps()), sum(Steps(), Value(0.0)).x)
print(sum(stream()), sum(stream(), Value(1.0)).x, sum(map(lambda i: Value(float(i)), range(3)), Value(0.0)).x)
print(sum([Paired(1), Paired(2)], Paired(10)).n, sum(values(2), start=Value(1.0)).x)
print(mean(values(3)), mean(values(0)))
total = sum(values(2))
print(total + Value(1.0), total + 1, 1 + total, bool(total), total == 0, sum(values(0)) == 0)
holed: list[Value] = [Value(1.0), None, Value(2.0)]
try:
    print(sum(holed))
except TypeError as error:
    print("TypeError:", error)
