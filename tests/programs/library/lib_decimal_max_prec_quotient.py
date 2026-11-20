# //, % and divmod() at the largest precision, where 10 ** prec has as many digits as the
# precision: a quotient of no more bits than the precision is below it without that power.
# A quotient longer than a small precision is still DivisionImpossible, at each boundary.
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

for prec, pairs in [(3, [("999", "1"), ("1000", "1"), ("12345", "7"), ("-999", "1"), ("-1000", "1"), ("7", "2")]),
                    (2, [("99", "1"), ("100", "1"), ("63", "1"), ("64", "1"), ("127", "1"), ("128", "1")]),
                    (40, [("9" * 40, "1"), ("1" + "0" * 40, "1"), ("1" + "0" * 80, "1" + "0" * 41)])]:
    c.prec = prec
    for a, b in pairs:
        try:
            print(prec, a, b, Decimal(a) // Decimal(b), Decimal(a) % Decimal(b))
        except InvalidOperation as e:
            print(prec, a, b, "InvalidOperation", e)
