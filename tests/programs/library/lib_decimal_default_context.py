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
