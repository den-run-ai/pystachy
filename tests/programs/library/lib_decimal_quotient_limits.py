# An integer quotient is rounded to the context like any other result: // and divmod() raise
# Overflow where it lies past Emax, and a clamped context appends its zeros; % does neither.
from decimal import Context, Decimal, DefaultContext, Overflow, getcontext, setcontext, localcontext, ROUND_DOWN, InvalidOperation

c = Context(prec=5, Emin=-2, Emax=2)
setcontext(c)
for a, b in [("1000", "1"), ("999", "1"), ("99999", "1"), ("1E+3", "1"), ("-1000", "1"), ("5000", "3"), ("1000", "7")]:
    for name in ["floordiv", "divmod", "mod", "div"]:
        try:
            x = Decimal(a)
            y = Decimal(b)
            if name == "floordiv":
                print(a, b, name, x // y)
            elif name == "divmod":
                q, r = divmod(x, y)
                print(a, b, name, q, r)
            elif name == "mod":
                print(a, b, name, x % y)
            else:
                print(a, b, name, x / y)
        except Overflow as e:
            print(a, b, name, "Overflow", e)
        except InvalidOperation as e:
            print(a, b, name, "InvalidOperation", e)
print(c.divide_int(Decimal("100"), Decimal("1")), c.divide_int(Decimal("10"), Decimal("3")))
try:
    print(c.divide_int(Decimal("1000"), Decimal("1")))
except Overflow as e:
    print("Overflow", e)
try:
    print(c.divmod(Decimal("1000"), Decimal("1")))
except Overflow as e:
    print("Overflow", e)
c2 = Context(prec=5, Emin=-2, Emax=2, clamp=1)
setcontext(c2)
for a, b in [("100", "1"), ("1E+2", "1"), ("9E+2", "3"), ("10", "1")]:
    try:
        print(a, b, Decimal(a) // Decimal(b), divmod(Decimal(a), Decimal(b)))
    except Overflow as e:
        print(a, b, "Overflow", e)
# The zero quotient of an infinite divisor is not clamped; a zero dividend's quotient is.
print(Decimal("7") // Decimal("Infinity"), divmod(Decimal("7"), Decimal("-Infinity")), c2.divide_int(Decimal("0"), Decimal("3")))
print(c2.abs(Decimal("-Infinity")), c2.abs(Decimal("-1.5")), c2.abs(Decimal("-NaN7")), abs(Decimal("-Infinity")))
