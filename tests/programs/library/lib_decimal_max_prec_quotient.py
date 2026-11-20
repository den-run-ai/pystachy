# //, % and divmod() at the largest precision: the quotient's digits are counted, because
# 10 ** prec has as many digits as the precision. A quotient longer than a small precision
# is still DivisionImpossible.
from decimal import Decimal, InvalidOperation, MAX_EMAX, MAX_PREC, MIN_EMIN, getcontext

c = getcontext()
c.prec = MAX_PREC
c.Emax = MAX_EMAX
c.Emin = MIN_EMIN
print(Decimal(500) // 2, Decimal(7) % 4, Decimal(-7) // 2, Decimal(-7) % 2)
q, r = divmod(Decimal("12345.678"), Decimal("0.25"))
print(q, r)
print(Decimal("1E+30") // 7, Decimal("1E+30") % 7, 9 // Decimal(2), 9 % Decimal(2))
x = Decimal(1)
for n in range(1, 60):
    x *= n
print(x // Decimal("1E+40"), x % 1000000007, c.divide_int(x, Decimal(59)) * 59 == x)

c.prec = 3
for a, b in [("999", "1"), ("1000", "1"), ("12345", "7"), ("-999", "1"), ("-1000", "1")]:
    try:
        print(a, b, Decimal(a) // Decimal(b), Decimal(a) % Decimal(b))
    except InvalidOperation as e:
        print(a, b, "InvalidOperation", e)
