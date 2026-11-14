# DefaultContext is the prototype of new contexts: what a program sets on it before any
# arithmetic is what Context() starts from (but capitals) and what the current context is.
from decimal import BasicContext, Context, Decimal, DefaultContext, ExtendedContext, getcontext, localcontext, setcontext, ROUND_DOWN

DefaultContext.prec = 4
DefaultContext.rounding = ROUND_DOWN
DefaultContext.capitals = 0
DefaultContext.Emax = 50
print(Decimal(2) / Decimal(3), Decimal("1e60").is_finite())
c = getcontext()
print(c.prec, c.rounding, c.capitals, c.Emax, c is DefaultContext)
print(Decimal("1E+30") * 1)
c.prec = 6
print(DefaultContext.prec, Context().prec, Context().capitals, Context(capitals=0).capitals)
with localcontext() as lc:
    print(lc.prec, lc.capitals)
print(BasicContext.prec, ExtendedContext.rounding, Context().copy().Emax)
d = DefaultContext.copy()
print(d.prec, d.capitals)
setcontext(Context(prec=3))
print(Decimal(1) / Decimal(7), getcontext().prec, repr(Context(prec=5)))
# create_decimal() takes a number's text as the specification writes it: the constructor's
# surrounding whitespace and underscores are a syntax error there.
from decimal import InvalidOperation
strict = Context(prec=5)
for text in [" 1.23 ", "1_000", "1.23", "5\n", "+1.5E+2", "1.23456789", ""]:
    try:
        print(repr(text), repr(strict.create_decimal(text)), repr(Decimal(text if text != "" else "0")))
    except InvalidOperation as error:
        print(repr(text), "InvalidOperation", error)
print(repr(strict.create_decimal(7)), repr(strict.create_decimal(1.5)), repr(strict.create_decimal()))
