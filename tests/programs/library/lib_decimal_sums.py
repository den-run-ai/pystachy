# sum() of Decimals, the constructor from a Decimal and a bool, and the exception hierarchy.
from dataclasses import dataclass
from decimal import (Context, Decimal, DecimalException, DivisionByZero, DivisionUndefined, FloatOperation, Inexact,
                     InvalidOperation, Overflow, Rounded, Underflow, getcontext, setcontext)


@dataclass
class Line:
    name: str
    price: Decimal
    quantity: int


def total(lines: list[Line]) -> Decimal:
    return sum((line.price * line.quantity for line in lines), Decimal(0))


def mean(values: list[Decimal]) -> Decimal:
    result = sum(values)
    if isinstance(result, Decimal):
        return result / len(values)
    return Decimal(result)


def scaled(value: "int | Decimal", factor: int) -> Decimal:
    if isinstance(value, Decimal):
        return value * factor
    return Decimal(value * factor)


prices = [Decimal("1.10"), Decimal("2.20"), Decimal("3.30")]
nothing: list[Decimal] = []
print(sum(prices), repr(sum(prices)), sum(nothing), repr(sum(nothing)))
print(sum(prices, Decimal(0)), sum(prices, Decimal(0)).quantize(Decimal("0.1")), sum(nothing, Decimal("0.00")), sum(prices, start=Decimal("10")))
print(sum(p * 2 for p in prices), sum((p for p in prices if p > 2), Decimal(0)), sum([1, 2, 3], Decimal("0.5")), sum(range(4), Decimal(1)))
lines = [Line("a", Decimal("1.25"), 4), Line("b", Decimal("0.10"), 3)]
print(total(lines), total([]), mean(prices), mean(nothing), scaled(3, 2), scaled(Decimal("1.5"), 2))
t = sum(prices)
z = sum(nothing)
print(t + 1, t * 2, t / 3, t - Decimal("0.6"), 1 + t, -t, abs(t), t > 5, t == Decimal("6.60"), t != 0, bool(t), bool(z))
print(f"{t:.1f} {z:.1f} {t!r} {t} {z:03d}", str(t), float(t), int(t), round(t, 1), format(z), z + 1, z == 0)
d = Decimal("1.50")
print(Decimal(d), Decimal(d) == d, repr(Decimal(Decimal("-0E+3"))), Decimal(Decimal("NaN123")), Decimal(Decimal("-Infinity")), Decimal(True), Decimal(False))
absent: Decimal = d if len("a") > 1 else None
try:
    print(Decimal(absent))
except TypeError as error:
    print("TypeError:", error)
for cls in [DivisionByZero, Overflow, Underflow, FloatOperation, DivisionUndefined, InvalidOperation]:
    print(cls.__name__, issubclass(cls, DecimalException), issubclass(cls, ZeroDivisionError), issubclass(cls, Rounded), issubclass(cls, Inexact), issubclass(cls, TypeError), issubclass(cls, ArithmeticError))
for kind in range(4):
    try:
        if kind < 2:
            print(Decimal(1) / Decimal(0))
        else:
            setcontext(Context(prec=3, Emax=5, Emin=-5))
            print(Decimal("9E+5") * 10)
    except DecimalException as error:
        if kind == 0:
            print("DecimalException", type(error).__name__, isinstance(error, ZeroDivisionError))
        elif kind == 2:
            print("DecimalException", type(error).__name__, isinstance(error, Rounded), isinstance(error, Inexact))
        else:
            try:
                raise
            except (ZeroDivisionError, Rounded) as inner:
                print("second base", type(inner).__name__)
print(getcontext().prec)
