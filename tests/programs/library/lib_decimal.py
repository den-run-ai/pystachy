# decimal: construction, text, inspection, arithmetic with Decimals and ints on either side,
# comparison, hashing, rounding and quantizing in every mode, square roots, integer powers,
# formatting, contexts (getcontext, setcontext, localcontext, Context's own operations), and the
# signals that raise, with CPython's classes and messages.
import copy
import math
from decimal import (ROUND_05UP, ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, ROUND_HALF_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_UP,
                     BasicContext, Context, Decimal, DecimalException, DecimalTuple, DefaultContext, DivisionByZero, ExtendedContext,
                     InvalidOperation, Overflow, getcontext, localcontext, setcontext)

ROUNDINGS = [ROUND_CEILING, ROUND_FLOOR, ROUND_UP, ROUND_DOWN, ROUND_HALF_UP, ROUND_HALF_DOWN, ROUND_HALF_EVEN, ROUND_05UP]
values = [Decimal(text) for text in ["0", "-0", "1", "-1.50", "2.5", "3.5", "0.125", "1E+3", "1234.5678", "-0.0000001", "9.99", "Infinity", "-Infinity", "NaN", "1E-7", "123456789012345678901234567890"]]
for d in values:
    print(repr(d), str(d), d.to_eng_string(), d.adjusted(), d.as_tuple(), d.number_class(), bool(d))
    print("  ", d.is_nan(), d.is_qnan(), d.is_snan(), d.is_infinite(), d.is_finite(), d.is_zero(), d.is_signed(), d.is_normal(), d.is_subnormal(), d.is_canonical())
    print("  ", d.copy_abs(), d.copy_negate(), d.copy_sign(Decimal(-1)), d.canonical(), d.conjugate(), d.real, d.imag, d.radix(), d.same_quantum(Decimal(1)))
    print("  ", -d, +d, abs(d), d.normalize(), [str(d.to_integral_value(mode)) for mode in ROUNDINGS], d.to_integral(), d.to_integral_exact())
    if d.is_finite() and d.adjusted() < 20:
        print("  ", int(d), float(d), round(d), round(d, 2), round(d, -1), math.floor(d), math.ceil(d), math.trunc(d), d.as_integer_ratio(), hash(d) == hash(int(d)) if d == int(d) else hash(d) == hash(float(d)))
        print("  ", [str(d.quantize(Decimal("0.1"), rounding=mode)) for mode in ROUNDINGS], d.quantize(Decimal("1E+1")), d.scaleb(2), d ** 2, d ** 3)
        print("  ", f"{d}|{d:f}|{d:.2f}|{d:e}|{d:.3E}|{d:g}|{d:>14.3f}|{d:+,.1f}|{d:%}|{d:012.2f}|{d:^12}|{d:z.0f}|")
    if not d.is_nan():
        print("  ", [d < v for v in values[:6]], [d <= v for v in values[:6]], [d == v for v in values[:6]], d > 0, d >= 1, d == 2.5, d < 3.5, d != 1)
        print("  ", [str(d.max(v)) for v in values[:6]], [str(d.min(v)) for v in values[:6]], [str(d.compare(v)) for v in values[:6]])
    for other in values[2:8]:
        print("  ", d + other, d - other, d * other, d / other, d.fma(other, Decimal(1)), d + 2, d - 2, d * 2, d / 2, 2 + d, 2 - d, 2 * d)
        if d.is_finite() and d.adjusted() < 20:
            print("  ", d // other, d % other, divmod(d, other), d.remainder_near(other), d // 2, d % 2, 7 // other, 7 % other, 7 / other)
for text in ["2", "0.25", "1E+2", "123.456", "0", "1E-9", "152415787532388367501905199875019052100"]:
    print(Decimal(text).sqrt(), Decimal(text).sqrt(Context(prec=5)))
print(Decimal(2) ** -3, Decimal("1.1") ** 100, Decimal(10) ** 30, Decimal("2.0") ** 2, Decimal(-3) ** 3, Decimal(1) ** 1000, Decimal("1.00") ** 5, Decimal(0) ** 5, Decimal(7) ** 0)
print(Decimal(0.1), Decimal(-0.0), Decimal(1e300), Decimal(5e-324), Decimal(float("inf")), Decimal(float("nan")), Decimal.from_float(0.75), Decimal.from_float(3))
print(Decimal(" 1_000.50 "), Decimal("+.5"), Decimal("5."), Decimal("1e5"), Decimal("-1E-5"), Decimal("inf"), Decimal("-INFINITY"), Decimal("nan12"), Decimal("sNaN"), Decimal("٣.٥"))
print(copy.copy(values[4]) is values[4], copy.deepcopy(values[4]) == values[4], {Decimal("1.0"): "one"}[Decimal(1)], sorted(values[:11]), max(values[:11]), min(values[:11]))
print(DecimalTuple(0, (1, 2), -1), Decimal("7.325").quantize(Decimal(".01"), rounding=ROUND_DOWN), Decimal("7.325").quantize(Decimal("1."), rounding=ROUND_UP))
ctx = getcontext()
print(ctx.prec, ctx.rounding, ctx.Emin, ctx.Emax, ctx.capitals, ctx.clamp, ctx.Etiny(), ctx.Etop())
ctx.prec = 6
ctx.rounding = ROUND_HALF_UP
print(Decimal(1) / 7, Decimal("1.2345675") + 0, +Decimal("9.9999995"), ctx.create_decimal("3.14159265"), ctx.create_decimal(2.5), ctx.create_decimal_from_float(0.1))
print(ctx.add(Decimal(1), Decimal(2)), ctx.subtract(Decimal(1), Decimal(2)), ctx.multiply(Decimal(3), Decimal(2)), ctx.divide(Decimal(1), Decimal(3)), ctx.divide_int(Decimal(7), Decimal(2)), ctx.remainder(Decimal(7), Decimal(2)), ctx.divmod(Decimal(7), Decimal(2)))
print(ctx.power(Decimal(2), 10), ctx.sqrt(Decimal(2)), ctx.quantize(Decimal("1.2345"), Decimal("0.01")), ctx.normalize(Decimal("1.200")), ctx.plus(Decimal("1.23456789")), ctx.minus(Decimal("1.23456789")), ctx.abs(Decimal("-1.23456789")))
print(ctx.to_integral_value(Decimal("2.5")), ctx.to_integral_exact(Decimal("2.5")), ctx.to_integral(Decimal("-2.5")), ctx.compare(Decimal(1), Decimal(2)), ctx.max(Decimal(1), Decimal(2)), ctx.min(Decimal(1), Decimal(2)))
print(ctx.to_sci_string(Decimal("123E+5")), ctx.to_eng_string(Decimal("123E+5")), ctx.is_finite(Decimal(1)), ctx.is_infinite(Decimal(1)), ctx.is_nan(Decimal(1)), ctx.is_zero(Decimal(0)), ctx.is_signed(Decimal(-1)), ctx.is_normal(Decimal(1)), ctx.is_subnormal(Decimal(1)))
second = ctx.copy()
second.prec = 3
print(second.prec, ctx.prec, copy.copy(ctx).prec, Context(prec=4, rounding=ROUND_DOWN).divide(Decimal(2), Decimal(3)), Context(Emax=5, Emin=-5).Etiny())
ctx.clear_flags()
setcontext(Context(prec=10))
print(getcontext().prec, Decimal(2).sqrt())
with localcontext() as local:
    local.prec = 3
    print(Decimal(2).sqrt(), getcontext().prec)
with localcontext(Context(prec=4)) as local:
    print(Decimal(2).sqrt(), local.prec)
with localcontext(prec=2, rounding=ROUND_CEILING, Emax=10, Emin=-10, capitals=0, clamp=1) as local:
    print(Decimal(2).sqrt(), Decimal("1E+10") * 1, Decimal("123E+20").to_eng_string() if False else Decimal("1.5E+9") * 3, local.Etop())
print(getcontext().prec, DefaultContext.prec, BasicContext.prec, BasicContext.rounding, ExtendedContext.rounding)
setcontext(DefaultContext)
getcontext().prec = 12
print(DefaultContext.prec, getcontext().prec)
setcontext(Context())


def attempt(label: str, kind: int) -> None:
    try:
        if kind == 0:
            print(Decimal(1) / Decimal(0))
        elif kind == 1:
            print(Decimal(0) / Decimal(0))
        elif kind == 2:
            print(Decimal("x1"))
        elif kind == 3:
            print(Decimal("9E+999999") * 10)
        elif kind == 4:
            print(Decimal(1) + 1.5)
        elif kind == 5:
            print(Decimal("NaN") < 1)
        elif kind == 6:
            print(int(Decimal("NaN")))
        elif kind == 7:
            print(int(Decimal("Infinity")))
        elif kind == 8:
            print(Decimal(-1).sqrt())
        elif kind == 9:
            print(Decimal(1).quantize(Decimal("1E-30")))
        elif kind == 10:
            print(Decimal("sNaN") + 1)
        elif kind == 11:
            print(hash(Decimal("sNaN")))
        elif kind == 12:
            print(Decimal(5) % 0, Decimal(5) // 0)
        elif kind == 13:
            print(divmod(Decimal(5), Decimal(0)))
        elif kind == 14:
            print(Decimal("Infinity") - Decimal("Infinity"))
        elif kind == 15:
            print(Decimal("Infinity") * 0)
        elif kind == 16:
            print(Decimal(0) ** 0)
        elif kind == 17:
            print(Decimal("1E+30") // Decimal("0.1"))
        elif kind == 18:
            getcontext().prec = 0
        elif kind == 19:
            print(f"{Decimal(1):.2x}")
        elif kind == 20:
            print(round(Decimal("NaN")))
        elif kind == 21:
            print(Decimal(1).quantize(Decimal("0.1"), rounding="ROUND_SIDEWAYS"))
        elif kind == 22:
            print(float(Decimal("sNaN")))
        elif kind == 23:
            print(Decimal("NaN").as_integer_ratio())
    except ZeroDivisionError as error:
        print(label, "ZeroDivisionError:", type(error).__name__, error, isinstance(error, DivisionByZero))
    except Overflow as error:
        print(label, "Overflow:", type(error).__name__, error, isinstance(error, DecimalException))
    except InvalidOperation as error:
        print(label, "InvalidOperation:", type(error).__name__, error, isinstance(error, ArithmeticError))
    except (TypeError, ValueError, OverflowError) as error:
        print(label, type(error).__name__, error)


for number in range(24):
    attempt(f"case {number}", number)
