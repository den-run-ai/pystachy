from types import NotImplementedType


class Left:
    def __init__(self, accept: bool) -> None:
        self.accept = accept
        self.calls = 0

    def __add__(self, other: object) -> int | NotImplementedType:
        self.calls += 1
        print("left", self.calls)
        if self.accept:
            return 10
        return NotImplemented


class Right:
    def __radd__(self, other: Left) -> int:
        print("right", other.calls)
        other.calls += 10
        return other.calls


def left(accept: bool) -> Left:
    print("evaluate left")
    return Left(accept)


def right() -> Right:
    print("evaluate right")
    return Right()


print(left(True) + right())
print(left(False) + right())
value = Left(False)
print(value.__add__(Right()) is NotImplemented)
value.accept = True
print(value.__add__(Right()) is not NotImplemented)
print(repr(NotImplemented), str(NotImplemented), NotImplemented is NotImplemented)


class NoneResult:
    def __init__(self, accept: bool) -> None:
        self.accept = accept

    def __add__(self, other: object) -> NotImplementedType | None:
        print("maybe None")
        if self.accept:
            return None
        return NotImplemented


class NoneFallback:
    def __radd__(self, other: object) -> None:
        print("None fallback")


print(NoneResult(True) + NoneFallback())
print(NoneResult(False) + NoneFallback())
print(NoneResult(True).__add__(0) is NotImplemented)
print(NoneResult(False).__add__(0) is NotImplemented)


class Base:
    def __add__(self, other: object):
        print("base decline")
        return NotImplemented


class Child(Base):
    def __radd__(self, other: object):
        print("child decline")
        return NotImplemented


def declined(left: Base, right: Base) -> None:
    try:
        print(left + right)
    except TypeError as error:
        print(error)


declined(Base(), Child())
declined(Child(), Base())
declined(Child(), Child())


class Mutable:
    def __init__(self, value: int) -> None:
        self.value = value

    def __iadd__(self, other: int):
        print("inplace decline", self.value)
        self.value += 1
        return NotImplemented

    def __add__(self, other: int) -> "Mutable":
        print("binary after inplace", self.value)
        return Mutable(self.value + other)


current = Mutable(4)
alias = current
current += 5
print(current.value, alias.value, current is alias)


class Raising:
    def __add__(self, other: object) -> int:
        print("raises first")
        raise ValueError("stop")


class Unreached:
    def __radd__(self, other: object) -> int:
        print("unexpected fallback")
        return 99


try:
    print(Raising() + Unreached())
except ValueError as error:
    print(error)


class Quotient:
    def __init__(self, accept: bool) -> None:
        self.accept = accept

    def __divmod__(self, other: object) -> tuple[int, int] | NotImplementedType:
        print("divmod forward")
        if self.accept:
            return (1, 2)
        return NotImplemented


class Divisor:
    def __rdivmod__(self, other: object) -> tuple[int, int]:
        print("divmod reflected")
        return (3, 4)


print(divmod(Quotient(True), Divisor()))
print(divmod(Quotient(False), Divisor()))


class Power:
    def __init__(self, accept: bool) -> None:
        self.accept = accept

    def __pow__(self, exponent: object, modulus: int = 100) -> int | NotImplementedType:
        print("power", modulus)
        if self.accept:
            return modulus
        return NotImplemented


class Exponent:
    def __rpow__(self, other: object) -> int:
        print("reflected power")
        return 200


print(pow(Power(True), Exponent(), 7))
print(pow(Power(True), Exponent(), None))
print(pow(Power(False), Exponent(), None))
try:
    print(pow(Power(False), Exponent(), 7))
except TypeError as error:
    print(error)


class ReferenceResult:
    def __init__(self, accept: bool) -> None:
        self.accept = accept

    def __add__(self, other: object) -> "ReferenceResult | NotImplementedType":
        print("reference result", self.accept)
        if self.accept:
            return self
        return NotImplemented


class ReferenceFallback:
    def __radd__(self, other: ReferenceResult) -> ReferenceResult:
        print("reference fallback")
        return ReferenceResult(True)


accepted = ReferenceResult(True)
declined_reference = ReferenceResult(False)
print((accepted + ReferenceFallback()) is accepted)
print((declined_reference + ReferenceFallback()).accept)
print(pow(2, 3, None))


class NullableNumber:
    def __init__(self, kind: int) -> None:
        self.kind = kind

    def __add__(self, other: object) -> int | NotImplementedType | None:
        if self.kind == 0:
            return None
        if self.kind == 1:
            return 10
        return NotImplemented


class NumericFallback:
    def __radd__(self, other: object) -> int:
        return 20


print(NullableNumber(0) + NumericFallback())
print(NullableNumber(1) + NumericFallback())
print(NullableNumber(2) + NumericFallback())
try:
    print(pow(2, Exponent(), 7))
except TypeError as error:
    print(error)
