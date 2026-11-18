# The remaining operations of the specification, as methods of Decimal and of Context, and int
# operands where a method takes another number: CPython's results and errors.
from decimal import (ROUND_HALF_EVEN, ROUND_UP, Context, Decimal, DivisionByZero, InvalidOperation, Overflow,
                     getcontext, setcontext)


def attempt(number: int) -> None:
    d = Decimal("12345.678")
    small = Context(prec=5)
    if number == 0:
        print(Decimal(1).next_plus(), Decimal(1).next_minus(), Decimal(1).next_toward(2), Decimal(1).next_toward(Decimal("-1")))
    elif number == 1:
        print(Decimal("Infinity").next_minus(), Decimal("-Infinity").next_plus(), Decimal(0).next_plus(), Decimal(0).next_minus(), Decimal("1.2345678").next_plus(small))
    elif number == 2:
        print(Decimal("9.999999999999999999999999999E+999999").next_toward(Decimal("Infinity")))
    elif number == 3:
        print(Decimal("1E+5").logb(), Decimal("0.00123").logb(), Decimal("-Infinity").logb(), Decimal("NaN").logb())
    elif number == 4:
        print(Decimal(0).logb())
    elif number == 5:
        print(Decimal("1100").logical_and(Decimal("1010")), Decimal("1100").logical_or(1010), Decimal("1100").logical_xor(Decimal("1010")), Decimal("101").logical_invert(small))
    elif number == 6:
        print(Decimal("1200").logical_and(Decimal("1010")))
    elif number == 7:
        print(Decimal("12345").rotate(2, small), Decimal("12345").rotate(-2, small), Decimal("12345").shift(2, small), Decimal("12345").shift(-2), d.rotate(0), Decimal("-Infinity").shift(1))
    elif number == 8:
        print(Decimal("12345").rotate(6, small))
    elif number == 9:
        print(Decimal(1).shift(Decimal("1.5")))
    elif number == 10:
        print(Decimal("2").compare_total(Decimal("2.0")), Decimal("-0").compare_total(0), Decimal("NaN").compare_total(Decimal("sNaN")), Decimal("NaN1").compare_total(Decimal("NaN2")), Decimal("-NaN1").compare_total(Decimal("-NaN2")), Decimal("Infinity").compare_total(Decimal("NaN")))
    elif number == 11:
        print(Decimal("1").compare_total_mag(Decimal("-2")), Decimal("3").max_mag(Decimal("-4")), Decimal("3").min_mag(-4), Decimal("-3").max_mag(3), Decimal("NaN").max_mag(1))
    elif number == 12:
        print(Decimal(1).compare_signal(2), Decimal(3).compare_signal(Decimal(3)))
    elif number == 13:
        print(Decimal(1).compare_signal(Decimal("NaN")))
    elif number == 14:
        print(d.max(99999), d.min(8), d.compare(12345), d.quantize(1), d.remainder_near(7), d.fma(2, 1), d.scaleb(2), d.scaleb(Decimal(-1)), d.copy_sign(-1), d.same_quantum(1))
    elif number == 15:
        print(d.scaleb(Decimal("1.5")))
    elif number == 16:
        c = getcontext()
        print(c.add(1, 2), c.subtract(Decimal("1.5"), 4), c.multiply(Decimal("1.5"), 4), c.divide(1, 3), c.divide_int(7, 2), c.remainder(7, Decimal(2)), c.divmod(7, 2), c.power(2, Decimal("0.5")))
    elif number == 17:
        c = getcontext()
        print(c.sqrt(2), c.abs(-5), c.minus(3), c.plus(Decimal("-0")), c.compare(1, Decimal(2)), c.max(1, 2), c.min(1, 2), c.quantize(Decimal("1.2345"), Decimal("0.01")), c.fma(2, 3, 4), c.normalize(Decimal("1.500")))
    elif number == 18:
        c = Context(prec=4, rounding=ROUND_UP)
        print(c.next_plus(1), c.next_minus(1), c.next_toward(1, 0), c.logb(1234), c.scaleb(1, 3), c.rotate(1234, 1), c.shift(1234, -1), c.logical_xor(1100, 1010), c.logical_invert(1010))
    elif number == 19:
        c = Context(prec=4)
        print(c.compare_total(1, Decimal("1.0")), c.compare_total_mag(-1, 1), c.compare_signal(2, 1), c.max_mag(-3, 2), c.min_mag(-3, 2), c.same_quantum(1, 2), c.copy_sign(1, -2), c.copy_abs(-1), c.copy_negate(1), c.copy_decimal(Decimal("1.50")))
    elif number == 20:
        c = Context(prec=4)
        print(c.is_zero(0), c.is_nan(1), c.is_qnan(Decimal("NaN")), c.is_snan(Decimal("sNaN")), c.is_finite(1), c.is_infinite(1), c.is_signed(-1), c.is_normal(1), c.is_subnormal(Decimal("1E-1000000")), c.is_canonical(Decimal(1)), c.number_class(-1), c.radix(), c.canonical(Decimal(5)))
    elif number == 21:
        c = Context(prec=4)
        print(c.to_sci_string(Decimal("1E+5")), c.to_eng_string(Decimal("1E+5")), c.to_integral_value(Decimal("1.5")), c.to_integral_exact(Decimal("2.5")), c.to_integral(Decimal("-1.5")), c.exp(1), c.ln(2), c.log10(3))
    elif number == 22:
        print(Decimal(7).quantize(1, ROUND_HALF_EVEN), Decimal("7.5").quantize(1, ROUND_UP), Decimal("7.5").quantize(Decimal("1E+1")))
    else:
        print(Decimal("Infinity").next_toward(Decimal("Infinity")), Decimal("-0").next_toward(Decimal("0")), Decimal("1").next_toward(Decimal("1.0")))


for number in range(24):
    try:
        attempt(number)
    except InvalidOperation as error:
        print(number, "InvalidOperation", error)
    except DivisionByZero as error:
        print(number, "DivisionByZero", error)
    except Overflow as error:
        print(number, "Overflow", error)
setcontext(Context(prec=3))
print(Decimal(1).next_plus(), Decimal("9.99").next_plus(), Decimal("1.00").next_minus(), getcontext().next_toward(Decimal("1.2345"), 2))
