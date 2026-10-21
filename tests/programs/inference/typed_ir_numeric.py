"""Typed casts and comparisons preserve numeric boundaries and evaluation order."""


def real(value):
    return float(value)


def integer(value):
    return int(value)


def compare(a, b):
    return (a == b, a != b, a < b, a <= b, a > b, a >= b)


def truth(value):
    return bool(value)


def positive(value: int | None) -> bool:
    return value is not None and value > 0


def optional_real(value: int | float | None) -> float:
    if value is None:
        return -1.0
    if isinstance(value, int):
        return real(value)
    return value


print(real(True), real(False), real(-7), integer(True), integer(False))
print(compare(2, 3), compare(True, False), compare(-1.5, 0.5))
print(compare(True, 1.0), compare(1.0, False))
nan = float("nan")
print(compare(nan, nan), compare(nan, 1.0), compare(1.0, nan))
print(compare(-0.0, 0.0), real(-0.0))
print(truth(False), truth(True), truth(0), truth(-1))
print(truth(0.0), truth(-0.0), truth(nan), truth(float("inf")))
print(truth(5e-324), truth(-5e-324))
# The int/float path must retain exact integer comparisons instead of rounding first.
print(compare(-9223372036854775808, 9223372036854775807))
print(compare(9007199254740993, 9007199254740992.0))
print(compare(-9007199254740993, -9007199254740992.0))
print(compare(9223372036854775807, 9223372036854775808.0))
print(compare(-9223372036854775808, -9223372036854775808.0))
print(compare(9007199254740992.0, 9007199254740993))
print(compare(nan, 1), compare(1, nan))
print(positive(None), positive(0), positive(3))
print(optional_real(None), optional_real(4), optional_real(-0.0))

events: list[int] = []


def mark(value: int) -> int:
    events.append(value)
    return value


print(mark(1) < mark(2) < mark(3), events)
events.clear()
print(mark(3) < mark(2) < mark(1), events)
