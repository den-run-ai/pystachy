from types import NotImplementedType


class Number:
    def __init__(self, value: int) -> None:
        self.value = value

    def __iadd__(self, other: int):
        print("iadd", self.value, other)
        del entries[0]
        self.value += 1
        return NotImplemented

    def __add__(self, other: int) -> "Number":
        print("add", self.value, other, len(entries))
        return Number(self.value + other)


entries = {0: Number(10)}
alias = entries[0]


def key() -> int:
    print("key")
    return 0


def amount() -> int:
    print("rhs")
    return 3


entries[key()] += amount()
print(entries[0].value, alias.value, len(entries))


class Base:
    def __init__(self, value: int) -> None:
        self.value = value

    def __add__(self, other: "Base") -> int:
        print("base add", self.value, other.value)
        return self.value * 100 + other.value


class Child(Base):
    def __radd__(self, other: Base) -> NotImplementedType:
        print("child radd", self.value, other.value)
        self.value += 1
        other.value += 2
        return NotImplemented


def make_left() -> Base:
    print("left")
    return Base(10)


def make_right() -> Base:
    print("right")
    return Child(20)


print(make_left() + make_right())


class Entry:
    def __init__(self, value: int) -> None:
        self.value = value

    def __eq__(self, other: object):
        print("entry eq", self.value)
        items.clear()
        return NotImplemented


items = [Entry(1), Entry(2)]
print(Entry(3) in items)
print(len(items))


class OptionalPower:
    def __pow__(self, exponent: int | None):
        print("optional power", exponent)
        return NotImplemented


def maybe_power(exponent: int | None) -> None:
    try:
        print(pow(OptionalPower(), exponent))
    except TypeError as error:
        print(error)


maybe_power(2)
maybe_power(None)


class AcceptNone:
    def __radd__(self, other: object) -> int:
        print("reflected None", other is None)
        return 8


class NullableOperand:
    def __add__(self, other: object):
        print("unexpected nonnull forward")
        return NotImplemented


def missing() -> NullableOperand:
    return None


print(missing() + AcceptNone())
