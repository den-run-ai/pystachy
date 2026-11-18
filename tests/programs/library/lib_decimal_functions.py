# exp(), ln(), log10() and powers with a Decimal exponent: correctly rounded as CPython's
# decimal rounds them, in every rounding mode and at several precisions; the special values,
# the errors, and a digest over a grid of operands.
from decimal import (ROUND_05UP, ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, ROUND_HALF_DOWN, ROUND_HALF_EVEN,
                     ROUND_HALF_UP, ROUND_UP, Context, Decimal, DivisionByZero, InvalidOperation, Overflow,
                     getcontext, localcontext, setcontext)

VALUES = ["0", "-0", "1", "-1", "2", "0.5", "10", "100", "0.001", "2.5", "-2.5", "3", "1E+3", "1E-7", "123456789",
          "0.99999", "1.00001", "7.25", "1E+20", "NaN", "Infinity", "-Infinity"]
EXPONENTS = ["0", "1", "-1", "2", "0.5", "-0.5", "2.5", "1E+2", "-3", "0.333", "10", "Infinity", "-Infinity", "NaN"]
ROUNDINGS = [ROUND_CEILING, ROUND_FLOOR, ROUND_UP, ROUND_DOWN, ROUND_HALF_UP, ROUND_HALF_DOWN, ROUND_HALF_EVEN, ROUND_05UP]


def attempt(label: str, value: Decimal, which: int) -> str:
    try:
        if which == 0:
            return str(value.exp())
        if which == 1:
            return str(value.ln())
        return str(value.log10())
    except InvalidOperation as error:
        return "InvalidOperation " + str(error)
    except Overflow as error:
        return "Overflow " + str(error)


def power(base: Decimal, exponent: Decimal) -> str:
    try:
        return str(base ** exponent)
    except InvalidOperation as error:
        return "InvalidOperation " + str(error)
    except Overflow as error:
        return "Overflow " + str(error)
    except DivisionByZero as error:
        return "DivisionByZero " + str(error)


def digest(text: str, seed: int) -> int:
    for ch in text:
        seed = (seed * 131 + ord(ch)) % 1000000007
    return seed


def grid() -> None:
    for prec in [1, 5, 9, 28, 40]:
        for rounding in ROUNDINGS:
            setcontext(Context(prec=prec, rounding=rounding))
            seed = 7
            for text in VALUES:
                value = Decimal(text)
                for which in range(3):
                    seed = digest(attempt(text, value, which), seed)
                for other in EXPONENTS:
                    seed = digest(power(value, Decimal(other)), seed)
            print(prec, rounding, seed)


print(Decimal(1).exp(), Decimal("2.5").exp(), Decimal(-3).exp(), Decimal("1E-30").exp(), Decimal(0).exp())
print(Decimal(10).ln(), Decimal("0.001").ln(), Decimal(2).ln(), Decimal(1).ln(), Decimal("1.0000001").ln())
print(Decimal(1000).log10(), Decimal(2).log10(), Decimal("0.01").log10(), Decimal(1).log10(), Decimal("1E+50").log10())
print(Decimal(2) ** Decimal("0.5"), Decimal(2) ** Decimal(3), Decimal("1.5") ** Decimal("-2.5"), pow(Decimal(9), Decimal("0.5")))
print(2 ** Decimal("0.5"), Decimal(2) ** 10, Decimal(4) ** Decimal("0.5"), Decimal("1.000") ** Decimal(3), Decimal(1) ** Decimal("0.5"))
print(repr(Decimal("Infinity").exp()), repr(Decimal("-Infinity").exp()), repr(Decimal(0).ln()), repr(Decimal("NaN").log10()))
for label, value in [("ln -1", Decimal(-1)), ("log10 -2", Decimal(-2)), ("exp big", Decimal("1E+10")), ("exp small", Decimal("-1E+10"))]:
    print(label, attempt(label, value, 1 if label.startswith("ln") else 2 if label.startswith("log") else 0))
for base, exponent in [("-2", "0.5"), ("0", "0"), ("0", "-1"), ("Infinity", "0.5"), ("0.5", "Infinity"), ("2", "-Infinity"), ("1", "Infinity"), ("-8", "3"), ("10", "1E+7")]:
    print(base, exponent, power(Decimal(base), Decimal(exponent)))
with localcontext() as context:
    context.prec = 50
    print(Decimal(2).ln(), Decimal(1).exp(), Decimal(2) ** Decimal("0.5"))
    print(context.exp(1), context.ln(Decimal(10)), context.log10(2), context.power(2, Decimal("0.5")), context.power(Decimal(2), 100))
power_in_place = Decimal(2)
power_in_place **= Decimal("1.5")
print(power_in_place, getcontext().prec)
grid()
